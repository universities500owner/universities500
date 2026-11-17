#!/usr/bin/env python3
"""Read course pages of the listed universities and write data/courses/<slug>.json.

Bachelor's and Master's only, full-time on campus only, open to international students only. No AI: patterns and page structure.
Nothing here changes the website: the output is data for a later review. Run it by hand from GitHub Actions.

Usage: python3 scripts/courses/run.py [--only slug,slug] [--limit N] [--shard 1/4] [--max-pages 150]
"""
import argparse
import csv
import json
import re
import os
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'scholarships'))  # fetcher, extract, textutil are shared with the scholarship reader
import checks as Q  # noqa: E402
import crawl  # noqa: E402
import cricos  # noqa: E402
from fetcher import Fetcher  # noqa: E402

ROOT = HERE.resolve().parents[1]
MISS_LIMIT = 3        # a course disappears after this many runs in which its page was read but is no longer an eligible course
SITE_TROUBLE = 0.5    # if more than this share of the known pages we re-read fail, the site probably changed: count no misses
NOT_A_MISS = {'fetch-failed', 'robots-blocked-page', 'not-html', 'parse-error', 'page-error', 'js-only-or-empty'}  # a bad day, not a removed course


def load(p, default):
    try:
        return json.loads(Path(p).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def dump(doc):
    """One course per line and one seen page per line, so a git diff shows what changed."""
    parts = ['{']
    keys = [k for k in doc if k not in ('courses', 'seen')]
    for k in keys:
        parts.append(f'"{k}": {json.dumps(doc[k], ensure_ascii=False)},')
    parts.append('"courses": [')
    parts.append(',\n'.join(json.dumps(c, ensure_ascii=False) for c in doc['courses']))
    parts.append('],')
    parts.append('"seen": {')
    parts.append(',\n'.join(f'{json.dumps(u, ensure_ascii=False)}: {json.dumps(e)}' for u, e in sorted(doc['seen'].items())))
    parts.append('}')
    parts.append('}')
    return '\n'.join(parts) + '\n'


YEAR_TAIL = re.compile(r'(?:/\d{1,3})?/(?:19|20)\d\d/?$|[-/](?:19|20)\d\d(?:[-/]\d{1,2})?/?$')


def _facts_count(rec):
    return sum(1 for k in ('fee', 'duration', 'intakes', 'ielts', 'cricos') if rec.get(k))


def duplicates(courses_by_url):
    """URLs of records that repeat another record of the same programme: the same name, level and degree at addresses that differ only by a
    query string or a year ('/course/706AA/9/2026', '...?year=2027'). The record with more facts stays; a tie keeps the newer address."""
    groups = {}
    for url, c in courses_by_url.items():
        base = YEAR_TAIL.sub('', url.split('?')[0].split('#')[0]).rstrip('/')
        groups.setdefault((c['name'].lower(), c['level'], base), []).append(c)
    drop = []
    for cs in groups.values():
        if len(cs) > 1:
            cs.sort(key=lambda c: (_facts_count(c), c['url']), reverse=True)
            drop.extend(c['url'] for c in cs[1:])
    return drop


def merge(uni, prev, out, today, now_iso):
    """Combine the previous file with what this run read. Returns (doc, stats)."""
    stats = {'new': 0, 'changed': 0, 'dropped': 0, 'kept': 0}
    prev_courses = [c for c in prev.get('courses', []) if not Q.problem(c)]
    cleaned = len(prev.get('courses', [])) - len(prev_courses)
    by_url = {c['url']: c for c in prev_courses}
    doc = {'slug': uni['slug'], 'name': uni['name'], 'country': uni['country'], 'web': uni.get('web'),
           'generatedAt': now_iso, 'status': out['status'], 'note': out['note'], 'robotsReason': out.get('robotsReason', ''),
           'pagesRead': out['pages'], 'intlOpen': out.get('intlOpen'), 'partial': bool(out.get('partial'))}
    if out['status'] != 'ok':
        # the website could not be read: keep everything as it was
        doc['courses'] = prev_courses
        doc['seen'] = prev.get('seen', {})
        doc['counts'] = {'eligible': len(prev_courses), 'held': {}}
        doc['heldSamples'] = {}
        stats['kept'] = len(prev_courses)
        return doc, stats
    trouble = out['knownRead'] >= 5 and out['knownFailed'] / max(out['knownRead'], 1) > SITE_TROUBLE
    keep = {}
    for url, c in by_url.items():
        r = out['results'].get(url)
        if r is None or r == 'ok':
            keep[url] = c
            continue
        if r in NOT_A_MISS or trouble:
            keep[url] = c
            continue
        c = dict(c)
        c['misses'] = c.get('misses', 0) + 1
        if c['misses'] >= MISS_LIMIT:
            stats['dropped'] += 1
            continue
        keep[url] = c
    for asked, rec in out['records'].items():
        old = by_url.get(rec['url']) or by_url.get(asked)
        if asked != rec['url']:
            keep.pop(asked, None)   # the address now redirects: keep one record, under the new address
        if old:
            rec['firstSeen'] = old.get('firstSeen', rec['firstSeen'])
            if old.get('hash') == rec['hash']:
                rec['lastChanged'] = old.get('lastChanged', rec['lastChanged'])
            else:
                stats['changed'] += 1
        else:
            stats['new'] += 1
        keep[rec['url']] = rec
    for url in duplicates(keep):      # the same programme under several addresses (one per intake year, say): keep one
        keep.pop(url, None)
        stats['dropped'] += 1
    stats['kept'] = len(keep) - stats['new']
    doc['courses'] = sorted(keep.values(), key=lambda c: (c['level'], c['name'].lower(), c['url']))
    seen = dict(prev.get('seen', {}))
    seen.update(out['seen'])
    # a page that is a known eligible course is always in `seen`
    for c in doc['courses']:
        seen.setdefault(c['url'], [c['lastVerified'], 'ok'])
    if len(seen) > crawl.SEEN_CAP:  # keep the freshest
        seen = dict(sorted(seen.items(), key=lambda kv: kv[1][0], reverse=True)[:crawl.SEEN_CAP])
    doc['seen'] = seen
    held = {k: v for k, v in out['reasons'].items() if k not in ('eligible',)}
    doc['counts'] = {'eligible': len(doc['courses']), 'held': dict(sorted(held.items(), key=lambda kv: -kv[1]))}
    doc['heldSamples'] = {k: v for k, v in out['samples'].items() if k != 'eligible'}
    doc['cleaned'] = cleaned
    doc['pageErrors'] = out.get('pageErrors', [])[:10]
    return doc, stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--universities', default=str(ROOT / 'src/data/universities.json'))
    ap.add_argument('--seeds', default=str(ROOT / 'data/course_seeds.json'), help='course list pages checked by hand, by university slug (optional)')
    ap.add_argument('--out-dir', default=str(ROOT / 'data/courses'))
    ap.add_argument('--report', default=str(ROOT / 'out'))
    ap.add_argument('--only', default='')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--shard', default='', help='i/n: read every n-th university, starting at the i-th (1-based). Lets several jobs share the list.')
    ap.add_argument('--workers', type=int, default=12)
    ap.add_argument('--delay', type=float, default=3.0)
    ap.add_argument('--max-pages', type=int, default=150, help='pages read per university in one run')
    ap.add_argument('--max-minutes', type=float, default=300)
    ap.add_argument('--refresh-days', type=int, default=14, help='re-read a known eligible course after this many days')
    ap.add_argument('--held-days', type=int, default=45, help='re-read a page that was held back after this many days')
    ap.add_argument('--contact', default=os.environ.get('CONTACT_EMAIL', ''))
    ap.add_argument('--today', default='')
    ap.add_argument('--allow-drop', action='store_true', help='write the files even if the number of courses fell by more than half')
    ap.add_argument('--strict-robots', action='store_true', help='treat a 401/403 answer for robots.txt as "everything disallowed"')
    ap.add_argument('--strict-international', action='store_true',
                    help='keep a course only if its own page shows it is open to international students (default also accepts the university-wide admissions page)')
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    today = args.today or now.date().isoformat()
    now_iso = now.strftime('%Y-%m-%dT%H:%M:%SZ')
    out_dir = Path(args.out_dir)
    unis = [u for u in load(args.universities, []) if u.get('web')]
    unis.sort(key=lambda u: u['slug'])
    if args.only:
        want = set(args.only.split(','))
        unis = [u for u in unis if u['slug'] in want]
    if args.shard:
        i, n = (int(x) for x in args.shard.split('/'))
        unis = unis[i - 1::n]
    if args.limit:
        unis = unis[:args.limit]
    seed_doc = load(args.seeds, {})
    seeds = {k: v.get('urls', []) for k, v in (seed_doc.get('seeds') or {}).items()}

    ua = f"Universities500Bot/1.0 (+https://universities500.com/bot/{'; ' + args.contact if args.contact else ''})"
    deadline = time.monotonic() + args.max_minutes * 60
    fx = Fetcher(ua, delay=args.delay, deadline=deadline, strict_forbidden=args.strict_robots)
    print('User-Agent:', ua)
    print(f'{len(unis)} universities, up to {args.max_pages} pages each, {args.delay}s between requests to one website')
    t0 = time.monotonic()

    def work(u):
        prev = load(out_dir / f"{u['slug']}.json", {})
        if time.monotonic() > deadline:
            return u['slug'], prev, {'slug': u['slug'], 'status': 'skipped', 'note': 'run ran out of time before this university', 'pages': 0,
                                      'results': {}, 'records': {}, 'seen': {}, 'reasons': Counter(), 'samples': {}, 'knownRead': 0, 'knownFailed': 0}
        try:
            return u['slug'], prev, crawl.crawl_university(u, fx, today, args.max_pages, prev=prev, seeds=seeds.get(u['slug']),
                                                           refresh_days=args.refresh_days, held_days=args.held_days,
                                                           strict_international=args.strict_international,
                                                           register=cricos.Register.load(u['slug']))
        except Exception as e:  # one bad site must not stop the run
            return u['slug'], prev, {'slug': u['slug'], 'status': 'error', 'note': f'{type(e).__name__}: {e}', 'pages': 0, 'results': {}, 'records': {},
                                      'seen': {}, 'reasons': Counter(), 'samples': {}, 'knownRead': 0, 'knownFailed': 0}

    docs, stats_by, prevs = {}, {}, {}
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(work, u): u for u in unis}
        done = 0
        for f in as_completed(futs):
            slug, prev, res = f.result()
            u = futs[f]
            docs[slug], stats_by[slug] = merge(u, prev, res, today, now_iso)
            prevs[slug] = prev
            done += 1
            if done % 5 == 0 or done == len(unis):
                n = sum(len(d['courses']) for d in docs.values())
                print(f'[{done}/{len(unis)}] {int(time.monotonic() - t0)}s requests={fx.stats["requests"]} courses so far={n}', flush=True)

    # ---- safety gate: do not overwrite good data with a bad run ----
    before = sum(len(prevs[s].get('courses', [])) for s in docs if docs[s]['status'] == 'ok')
    after = sum(len(docs[s]['courses']) for s in docs if docs[s]['status'] == 'ok')
    gate_failed = before >= 100 and after < before * 0.5 and not args.allow_drop
    if not gate_failed:
        out_dir.mkdir(parents=True, exist_ok=True)
        for slug, doc in docs.items():
            (out_dir / f'{slug}.json').write_text(dump(doc), encoding='utf-8')
    # the files this run wrote, so a workflow with several shards can collect exactly those and nothing stale
    rep_dir = Path(args.report)
    rep_dir.mkdir(parents=True, exist_ok=True)
    (rep_dir / 'written.txt').write_text(''.join(f'{out_dir / (slug + ".json")}\n' for slug in docs) if not gate_failed else '', encoding='utf-8')

    report(args, unis, docs, stats_by, prevs, fx, today, gate_failed, before, after, time.monotonic() - t0)
    if gate_failed:
        print(f'STOPPED: courses fell from {before} to {after}. Nothing was written. Check the report; use --allow-drop if this is expected.')
        return 3
    return 0


def report(args, unis, docs, stats_by, prevs, fx, today, gate_failed, before, after, secs):
    rep = Path(args.report)
    rep.mkdir(parents=True, exist_ok=True)
    status = Counter(d['status'] for d in docs.values())
    tot = Counter()
    for s in stats_by.values():
        tot.update(s)
    courses = [c for d in docs.values() for c in d['courses']]
    held = Counter()
    for d in docs.values():
        held.update(d['counts']['held'])
    n = len(courses) or 1
    fill = {k: sum(1 for c in courses if c.get(k)) for k in ('fee', 'duration', 'intakes', 'ielts', 'field', 'cricos')}
    how = Counter(c['international']['how'] for c in courses)
    lv = Counter(c['level'] for c in courses)
    bycountry = Counter(d['country'] for d in docs.values() for _ in d['courses'])
    with (rep / 'universities.csv').open('w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['slug', 'country', 'status', 'robots_reason', 'pages_read', 'eligible', 'new', 'changed', 'dropped', 'top_held_reasons', 'international_page', 'note'])
        for u in unis:
            d = docs.get(u['slug'])
            if not d:
                continue
            st = stats_by[u['slug']]
            top = '; '.join(f'{k}={v}' for k, v in list(d['counts']['held'].items())[:4])
            w.writerow([u['slug'], u['country'], d['status'], d.get('robotsReason', ''), d['pagesRead'], len(d['courses']), st['new'], st['changed'], st['dropped'],
                        top, (d.get('intlOpen') or {}).get('url', ''), d['note']])
    held_samples = {s: d.get('heldSamples') for s, d in docs.items() if d.get('heldSamples')}
    (rep / 'held_samples.json').write_text(json.dumps(held_samples, indent=1, ensure_ascii=False), encoding='utf-8')   # example addresses for each held-back reason
    samples = {s: d['courses'][:3] for s, d in docs.items() if d['courses']}
    (rep / 'course_samples.json').write_text(json.dumps(samples, indent=1, ensure_ascii=False), encoding='utf-8')
    L = [f'# Course reader run, {today}', '',
         f'{len(unis)} universities in this run, {int(secs // 60)} minutes, {fx.stats["requests"]} requests, {fx.stats["robots_blocked"]} blocked by robots.txt.', '']
    if gate_failed:
        L += [f'**Stopped.** Courses fell from {before} to {after}, so no file was written.', '']
    L += ['## Result', '',
          f'- Eligible courses now: **{len(courses)}** (Bachelor {lv["Bachelor"]}, Master {lv["Master"]}); before this run (readable universities): {before}',
          f'- New {tot["new"]}, changed {tot["changed"]}, dropped {tot["dropped"]}',
          f'- Universities: {dict(status)}',
          f'- International evidence: {dict(how)} (cricos = Australian CRICOS code, fee = international fee on the page, page = international sentence on the page, university = admissions page of the university)',
          f'- Fields found: ' + ', '.join(f'{k} {v} ({round(100 * v / n)}%)' for k, v in fill.items()), '',
          '## Held back (counted, not published)', '']
    for k, v in held.most_common(14):
        L.append(f'- {k}: {v}')
    crashed = [(s, d['pageErrors']) for s, d in docs.items() if d.get('pageErrors')]
    if crashed:
        L += ['', f'## Pages the reader could not handle ({sum(len(e) for _s, e in crashed)} in {len(crashed)} universities)', '']
        for slug, errs in crashed[:20]:
            L.append(f'- {slug}: {errs[0]}')
    L += ['', '## Universities that need a look', '']
    bad = [(u['slug'], docs[u['slug']]) for u in unis if u['slug'] in docs and docs[u['slug']]['status'] != 'ok']
    for slug, d in bad[:60]:
        L.append(f'- {slug}: {d["status"]}' + (f' ({d["robotsReason"]})' if d.get('robotsReason') else '') + (f', {d["note"]}' if d['note'] else ''))
    zero = [(u['slug'], docs[u['slug']]) for u in unis if u['slug'] in docs and docs[u['slug']]['status'] == 'ok' and not docs[u['slug']]['courses']]
    L += ['', f'## Readable, but no eligible course found ({len(zero)})', '']
    for slug, d in zero[:60]:
        top = ', '.join(f'{k} {v}' for k, v in list(d['counts']['held'].items())[:3])
        L.append(f'- {slug}: {d["pagesRead"]} pages read; {top}')
    L += ['', '## Courses per country', '', ', '.join(f'{k} {v}' for k, v in bycountry.most_common())]
    text = '\n'.join(L) + '\n'
    (rep / 'course_report.md').write_text(text, encoding='utf-8')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        Path(os.environ['GITHUB_STEP_SUMMARY']).open('a').write(text)
    print(text[:3000])


if __name__ == '__main__':
    sys.exit(main())
