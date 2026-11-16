#!/usr/bin/env python3
"""Read scholarship pages and write src/data/scholarships.json.

Runs from GitHub Actions every two days. No AI: patterns and page structure only.
Usage: python3 scripts/scholarships/run.py [--limit N] [--only slug,slug] [--force]
"""
import argparse
import json
import os
import random
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import discover  # noqa: E402
import quality as Q  # noqa: E402
import official  # noqa: E402
import textutil as T  # noqa: E402
from fetcher import Fetcher  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
MISS_LIMIT = 3  # a record disappears after this many runs in which its university was readable but the record was not found


def load(p, default):
    try:
        return json.loads(Path(p).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--universities', default=str(ROOT / 'src/data/universities.json'))
    ap.add_argument('--sources', default=str(ROOT / 'data/scholarship_sources.json'))
    ap.add_argument('--seeds', default=str(ROOT / 'data/scholarship_seeds.json'), help='scholarship pages checked by hand, by university slug')
    ap.add_argument('--prev', default=str(ROOT / 'src/data/scholarships.json'))
    ap.add_argument('--out', default=str(ROOT / 'src/data/scholarships.json'))
    ap.add_argument('--report', default=str(ROOT / 'out'))
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--only', default='')
    ap.add_argument('--workers', type=int, default=12)
    ap.add_argument('--delay', type=float, default=3.0)
    ap.add_argument('--max-pages', type=int, default=60)
    ap.add_argument('--max-minutes', type=float, default=150)
    ap.add_argument('--if-older-than-hours', type=float, default=0)
    ap.add_argument('--contact', default=os.environ.get('CONTACT_EMAIL', ''))
    ap.add_argument('--today', default='')
    ap.add_argument('--allow-drop', action='store_true')
    ap.add_argument('--skip-official', action='store_true')
    ap.add_argument('--strict-robots', action='store_true',
                    help='treat a 401/403 answer for robots.txt as "everything disallowed" (RFC 9309 lets a crawler go ahead)')
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    today = args.today or now.date().isoformat()
    prev = load(args.prev, {})
    # Records saved before a quality rule existed are checked again, so old mistakes do not linger.
    kept = [i for i in prev.get('items', []) if not Q.problem(i, today)]
    args.cleaned = len(prev.get('items', [])) - len(kept)
    if args.cleaned:
        prev['items'] = kept

    # cadence guard: the workflow fires daily, we only work when the last good run is old enough
    gh_out = os.environ.get('GITHUB_OUTPUT')
    if args.if_older_than_hours and prev.get('generatedAt'):
        last = datetime.fromisoformat(prev['generatedAt'].replace('Z', '+00:00'))
        if now - last < timedelta(hours=args.if_older_than_hours):
            print(f"Last run was {prev['generatedAt']}, less than {args.if_older_than_hours} hours ago. Nothing to do.")
            if gh_out:
                Path(gh_out).open('a').write('skip=true\n')
            return 0
    if gh_out:
        Path(gh_out).open('a').write('skip=false\n')

    unis = load(args.universities, [])
    if args.only:
        want = set(args.only.split(','))
        unis = [u for u in unis if u['slug'] in want]
    unis = [u for u in unis if u.get('web')]
    if args.limit:
        unis = unis[:args.limit]
    sources = load(args.sources, {})
    seed_doc = load(args.seeds, {})
    seeds = {k: v.get('urls', []) for k, v in (seed_doc.get('seeds') or {}).items()}
    seeds_checked = seed_doc.get('checked')

    ua = f"Universities500Bot/1.0 (+https://universities500.com/bot/{'; ' + args.contact if args.contact else ''})"
    deadline = time.monotonic() + args.max_minutes * 60
    fx = Fetcher(ua, delay=args.delay, deadline=deadline, strict_forbidden=args.strict_robots)
    t0 = time.monotonic()
    print('User-Agent:', ua)

    # ---- official programmes and directories ----
    off_records, off_report, directories, third = [], [], [], []
    if not args.skip_official:
        off_records, off_report = official.read_programmes(sources, fx, today)
        directories = official.read_directories(sources, fx, today)
        third = official.read_third_party(sources, fx)
        print(f'official: {len(off_records)} programmes, {sum(d["ok"] for d in directories)}/{len(directories)} directories reachable')

    # ---- universities ----
    results = {}
    def work(u):
        try:
            return u['slug'], discover.crawl_university(u, fx, today, args.max_pages, seeds=seeds.get(u['slug']))
        except Exception as e:  # one bad site must not stop the run
            return u['slug'], {'slug': u['slug'], 'status': 'error', 'records': [], 'hub': None, 'pages': 0, 'reasons': Counter(), 'note': f'{type(e).__name__}: {e}'}

    skipped_by_deadline = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(work, u): u for u in unis}
        done = 0
        for f in as_completed(futs):
            slug, r = f.result()
            results[slug] = r
            done += 1
            if done % 10 == 0 or done == len(unis):
                print(f'[{done}/{len(unis)}] {int(time.monotonic() - t0)}s requests={fx.stats["requests"]} records so far={sum(len(x["records"]) for x in results.values())}', flush=True)
    for u in unis:
        r = results.get(u['slug'])
        if r and r['status'] == 'unreachable' and r['note'] in ('no response',) and time.monotonic() > deadline:
            skipped_by_deadline.append(u['slug'])

    # ---- merge with the previous run ----
    prev_items = {i['id']: i for i in prev.get('items', [])}
    uni_by_slug = {u['slug']: u for u in unis}
    readable = {s for s, r in results.items() if r['status'] in ('ok', 'no-scholarship-pages') and not r.get('partial') and s not in skipped_by_deadline}
    fresh = {}
    miss_log = []  # sentences that look like a deadline or value the reader did not take (printed for the run log only)
    for rec in off_records + [x for r in results.values() for x in r['records']]:
        miss = rec.pop('_miss', None)
        if miss:
            miss_log.append((rec['provider'], rec['name'], rec['url'], miss))
        fresh[rec['id']] = rec

    merged = {}
    used_slugs = {i.get('slug') for i in prev_items.values() if i.get('slug')}
    changed = added = carried = dropped = 0
    for rid, rec in fresh.items():
        old = prev_items.get(rid)
        rec['lastVerified'] = today
        rec['misses'] = 0
        if old:
            rec['slug'] = old.get('slug')
            rec['firstSeen'] = old.get('firstSeen', today)
            if old.get('hash') != rec['hash']:
                rec['lastChanged'] = today
                changed += 1
            else:
                rec['lastChanged'] = old.get('lastChanged', old.get('firstSeen', today))
        else:
            rec['firstSeen'] = rec['lastChanged'] = today
            added += 1
        merged[rid] = rec
    for rid, old in prev_items.items():
        if rid in fresh:
            continue
        gone_url = old['url'] in fx.gone
        slug = old.get('providerSlug')
        if old.get('origin') == 'official':
            # official programme not read this time (site down or page changed): keep, but do not refresh the date
            merged[rid] = old
            carried += 1
            continue
        if gone_url:
            old['misses'] = old.get('misses', 0) + 2
        elif slug in readable:
            old['misses'] = old.get('misses', 0) + 1
        if old.get('misses', 0) >= MISS_LIMIT:
            dropped += 1
            continue
        merged[rid] = old
        carried += 1
    # slugs: stable once given
    def mk_slug(rec):
        base = T.slugify(rec['name'], 60)
        prov = T.slugify(rec['provider'], 24)
        s = f'{base}-{prov}'.strip('-')
        n, cand = 2, s
        while cand in used_slugs:
            cand = f'{s}-{n}'
            n += 1
        used_slugs.add(cand)
        return cand
    for rec in sorted(merged.values(), key=lambda r: r['id']):
        if not rec.get('slug'):
            rec['slug'] = mk_slug(rec)

    # ---- sanity gate ----
    old_n, new_n = len(prev_items), len(merged)
    if not args.allow_drop and old_n >= 20 and new_n < 0.5 * old_n:
        write_report(args, fx, results, off_report, directories, third, merged, prev_items, today, now, t0, gate_failed=(old_n, new_n))
        print_diagnostics(merged.values(), miss_log)
        print(f'STOP: records fell from {old_n} to {new_n}. Not writing. Re-run with --allow-drop if this is real.')
        return 3

    # ---- university hub pages and status ----
    unis_out = dict(prev.get('universities', {}))
    for slug, r in results.items():
        if slug in skipped_by_deadline:
            continue
        old = unis_out.get(slug, {})
        entry = {
            'status': r['status'], 'checked': today if r['status'] in ('ok', 'no-scholarship-pages') else old.get('checked'),
            'hubUrl': (r['hub'] or {}).get('url') if r['status'] in ('ok',) else old.get('hubUrl'),
            'hubTitle': (r['hub'] or {}).get('title') if r['status'] in ('ok',) else old.get('hubTitle'),
        }
        if r.get('robotsReason'):
            entry['robotsReason'] = r['robotsReason']
        supplied = seeds.get(slug) or []
        if supplied and not (r['hub'] and r['status'] == 'ok'):
            # the reader could not open the page checked by hand, but that page is still the best link to give a student
            entry['hubUrl'], entry['hubTitle'], entry['hubSource'] = supplied[0], None, 'supplied'
            entry['checked'] = seeds_checked or entry['checked']
        elif r['hub'] and r['status'] == 'ok':
            entry['hubSource'] = 'supplied' if r['hub'].get('supplied') else 'read'
        unis_out[slug] = entry
    for slug, entry in unis_out.items():
        entry['count'] = sum(1 for i in merged.values() if i.get('providerSlug') == slug)

    items = sorted(merged.values(), key=lambda i: (i['country'], i['provider'].lower(), i['name'].lower()))
    # directories: keep the last known good address when this run could not reach one
    prev_dirs = {d['id']: d for d in prev.get('directories', [])}
    for d in directories:
        if not d['ok'] and d['id'] in prev_dirs and prev_dirs[d['id']].get('ok'):
            d.update({k: prev_dirs[d['id']][k] for k in ('url', 'ok', 'checked')})
    doc = {
        'version': 1,
        'generatedAt': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'today': today,
        'stats': {
            'items': len(items), 'added': added, 'changed': changed, 'carriedOver': carried, 'dropped': dropped,
            'universitiesRead': len(readable), 'universitiesTried': len(unis),
            'requests': fx.stats['requests'],
        },
        'items': items,
        'universities': unis_out,
        'directories': directories or prev.get('directories', []),
        'thirdParty': [{k: v for k, v in t.items() if k not in ('robotsText',)} for t in third] or prev.get('thirdParty', []),
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    write_report(args, fx, results, off_report, directories, third, merged, prev_items, today, now, t0)
    print_diagnostics(items, miss_log)
    print(f'wrote {len(items)} scholarships ({added} new, {changed} changed, {dropped} removed) to {args.out}')
    return 0


FIELDS = ('value', 'deadline', 'deadlinePartial', 'opens', 'rolling', 'description', 'eligibility', 'applyUrl',
          'awards', 'duration', 'covers', 'applyMode', 'india')


def print_diagnostics(items, miss_log, sample=18):
    """Fill rates and a sample of what the reader missed, printed so they show in the GitHub Actions log."""
    items = list(items)
    n = len(items) or 1
    print('\nFill rates (share of records with each field):')
    for f in FIELDS:
        have = sum(1 for i in items if i.get(f))
        print(f'  {f:16} {have:4} / {len(items)}  ({100 * have // n}%)')
    full = sum(1 for i in items if i.get('value') and i.get('deadline') and i.get('eligibility') and i.get('description'))
    print(f'  value+deadline+eligibility+description: {full}')
    if not miss_log:
        return
    print(f'\nPages where the text looks like it holds a deadline or value that was not taken: {len(miss_log)}')
    random.Random(7).shuffle(miss_log)
    for prov, name, url, miss in miss_log[:sample]:
        print(f'- {prov} | {name} | {url}')
        for k, lines in miss.items():
            for ln in lines:
                print(f'    [{k}] {ln}')


def write_report(args, fx, results, off_report, directories, third, merged, prev_items, today, now, t0, gate_failed=None):
    out = Path(args.report)
    out.mkdir(parents=True, exist_ok=True)
    L = []
    L.append(f'# Scholarship run {now.strftime("%Y-%m-%d %H:%M UTC")}\n')
    if gate_failed:
        L.append(f'**Stopped by the sanity check: records fell from {gate_failed[0]} to {gate_failed[1]}. Nothing was written.**\n')
    L.append(f'- Time: {int(time.monotonic() - t0)} s, requests: {fx.stats["requests"]}, data read: {fx.stats["bytes"] // 1024} KB')
    L.append(f'- Records now: {len(merged)} (before: {len(prev_items)})')
    if getattr(args, 'cleaned', 0):
        L.append(f'- Removed from the old data by the name and page rules: {args.cleaned}')
    st = Counter(r['status'] for r in results.values())
    L.append('- Universities by outcome: ' + ', '.join(f'{k} {v}' for k, v in st.most_common()))
    L.append(f'- Robots.txt blocked {fx.stats["robots_blocked"]} requests')
    if fx.stats['robots_forbidden']:
        L.append(f'- {fx.stats["robots_forbidden"]} sites answered robots.txt with 401/403; ' + ('strict mode: treated as closed' if getattr(args, 'strict_robots', False) else 'treated as "no rules" as RFC 9309 allows') + '\n')
    else:
        L.append('')
    rb = Counter(r.get('robotsReason') for r in results.values() if r['status'] == 'robots')
    if rb:
        L.append('## Universities skipped because of robots.txt, by reason\n')
        names = {'disallow': 'a rule in robots.txt says no', 'forbidden': 'robots.txt answered 401/403 (strict mode)', 'unreachable': 'robots.txt could not be read (server error or no answer)'}
        for k, v in rb.most_common():
            L.append(f'- {names.get(k, k or "unknown")}: {v}')
        L.append('')
    by_c = Counter(i['country'] for i in merged.values())
    L.append('## Records by country\n')
    L.append('| Country | Records | With deadline | With value | With eligibility |\n|---|---|---|---|---|')
    for c, n in sorted(by_c.items()):
        its = [i for i in merged.values() if i['country'] == c]
        L.append(f'| {c} | {n} | {sum(bool(i.get("deadline")) for i in its)} | {sum(bool(i.get("value")) for i in its)} | {sum(bool(i.get("eligibility")) for i in its)} |')
    seeded = [(slug, u, st) for slug, r in sorted(results.items()) for u, st in (r.get('seeds') or {}).items()]
    if seeded:
        L.append('\n## Pages checked by hand: what the reader found\n')
        bad = sum(1 for _s, _u, st in seeded if st != 'ok')
        L.append(f'{len(seeded) - bad} of {len(seeded)} opened and mention scholarships.\n')
        for slug, u, st in seeded:
            L.append(f'- {"OK " if st == "ok" else "LOOK"} {slug}: {st} ({u})')
    L.append('\n## Official programmes\n')
    for pid, url, status in off_report:
        L.append(f'- {pid}: {status} ({url})')
    L.append('\n## Official directories\n')
    for d in directories:
        L.append(f'- {"OK " if d["ok"] else "FAIL"} {d["title"]}: {d["url"]}' + ('' if d['ok'] else f' ({d.get("error")})'))
    L.append('\n## Third-party sites (link-out only). What their robots.txt says\n')
    for t in third:
        L.append(f'### {t["title"]}: root allowed = {t["robotsAllowsRoot"]}')
        L.append('```\n' + (t.get('robotsText') or '(no robots.txt text read)') + '\n```')
    L.append('\n## Universities that could not be read\n')
    for s, r in sorted(results.items()):
        if r['status'] not in ('ok',):
            L.append(f'- {s}: {r["status"]} {r.get("note", "")}')
    L.append('\n## Why pages were not turned into records (all universities)\n')
    reasons = Counter()
    for r in results.values():
        reasons.update(r['reasons'])
    for k, v in reasons.most_common():
        L.append(f'- {k}: {v}')
    (out / 'scholarship_report.md').write_text('\n'.join(L) + '\n', encoding='utf-8')
    rows = ['slug,status,robots_reason,pages,records,hub,note']
    for s, r in sorted(results.items()):
        rows.append(','.join([s, r['status'], r.get('robotsReason') or '', str(r['pages']), str(len(r['records'])), (r['hub'] or {}).get('url', ''), '"' + (r.get('note') or '').replace('"', "'") + '"']))
    (out / 'universities.csv').write_text('\n'.join(rows) + '\n', encoding='utf-8')
    sample = random.Random(1).sample(list(merged.values()), min(40, len(merged))) if merged else []
    (out / 'sample_records.json').write_text(json.dumps(sample, ensure_ascii=False, indent=1), encoding='utf-8')
    (out / 'errors.txt').write_text('\n'.join(f'{u}\t{e}' for u, e in fx.errors[:500]) + '\n', encoding='utf-8')
    (out / 'robots_blocked.txt').write_text('\n'.join(f'{h}{p}' for h, p in fx.robots_blocked[:500]) + '\n', encoding='utf-8')
    summ = os.environ.get('GITHUB_STEP_SUMMARY')
    if summ:
        Path(summ).open('a', encoding='utf-8').write('\n'.join(L[:60]) + '\n')


if __name__ == '__main__':
    sys.exit(main())
