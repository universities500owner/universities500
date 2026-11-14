#!/usr/bin/env python3
"""Reads internship postings from employers' public job-board feeds and two public-sector / open feeds,
and writes src/data/internships.json. No AI. See README.md."""
import argparse
import csv
import hashlib
import json
import os
import sys
import time
import urllib.parse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import places as P  # noqa: E402
import sources as S  # noqa: E402
from fetcher import Fetcher  # noqa: E402
from titles import classify, clean_title  # noqa: E402

DROP_AFTER = 2  # a posting missing from a board that was read fine, this many runs in a row, is dropped


def load(p, default):
    try:
        return json.loads(Path(p).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def item_id(url, country):
    return hashlib.sha1(f'{url}|{country}'.encode()).hexdigest()[:12]


EXTRA = ('team', 'pay', 'deadline', 'mode')
ENRICH_CAP = 150  # Greenhouse postings read one by one per run, so a run stays short. The rest follow on later runs.
ORG_ALIAS = {}  # lower-case name an open feed uses -> the company's own name (set from the sources file)


def normalise(raw, source, board, org, unplaced):
    """One raw posting -> zero or more items (one per destination it is posted in)."""
    title = clean_title(raw.get('title'))
    url = (raw.get('url') or '').strip()
    if not title or not url.lower().startswith(('http://', 'https://')):
        return []
    places = []
    for loc in raw.get('locations') or []:
        if isinstance(loc, tuple):
            places.append(loc)
        else:
            places.extend(P.resolve(loc))
    out, seen = [], set()
    for city, country in places:
        kind = classify(title, country, raw.get('structured'))
        if not kind or (city, country) in seen:
            continue
        seen.add((city, country))
        who = (raw.get('org') or org or '').strip()
        who = ORG_ALIAS.get(who.lower(), who)
        it = {'id': item_id(url, country), 'title': title, 'org': who, 'city': city or '',
              'country': country, 'kind': kind, 'url': url, 'source': source, 'board': board, 'posted': raw.get('posted') or ''}
        # Optional facts, copied only when the feed states them: department, pay range, closing date, on-site/hybrid/remote.
        for k in EXTRA:
            if raw.get(k):
                it[k] = raw[k]
        if source == 'greenhouse' and raw.get('ref'):
            it['ref'] = raw['ref']
        out.append(it)
    if not places and classify(title, None, raw.get('structured')):
        for loc in raw.get('locations') or []:
            if isinstance(loc, str):
                unplaced[loc.strip()[:80]] += 1
    return out


def recheck(items):
    """Saved postings are checked again with today's rules, so an old mistake does not stay. Returns (kept, removed_count)."""
    kept = []
    for it in items:
        # The employer's own 'intern' flag is not saved. Give the benefit of it only to postings saved as internships,
        # so a title that only just stopped matching (for example 'student worker') cannot come back as one.
        kind = classify(it.get('title'), it.get('country'), it.get('kind') == 'Internship' and it.get('source') != 'jobtech')
        if not kind:
            continue
        it = dict(it)
        it['kind'] = kind
        it['city'] = P.tidy_city(it.get('city', ''))
        it['org'] = ORG_ALIAS.get((it.get('org') or '').lower(), it.get('org'))
        kept.append(it)
    return kept, len(items) - len(kept)


def enrich_greenhouse(fx, items, prev_items, cap=ENRICH_CAP):
    """Reads each Greenhouse posting's own page of data once, for its department and pay range.
    Postings read before are skipped. Returns (read_ok, with_pay, tried)."""
    done = {i['id'] for i in prev_items if i.get('detail')}
    todo = [i for i in items if i.get('source') == 'greenhouse' and i.get('ref') and i['id'] not in done][:cap]
    ok = paid = 0
    for it in todo:
        st, d = S.greenhouse_job(fx, it['board'], it['ref'])
        if st != 'ok':
            continue
        ok += 1
        it['detail'] = 1
        for k in ('team', 'pay'):
            if d.get(k):
                it[k] = d[k]
        paid += 1 if d.get('pay') else 0
    return ok, paid, len(todo)


def merge(prev_items, new_items, ok_boards, today):
    prev = {i['id']: i for i in prev_items}
    out = {}
    for it in new_items:
        old = prev.get(it['id'])
        it['firstSeen'] = old['firstSeen'] if old and old.get('firstSeen') else today
        if old and old.get('detail') and it.get('source') == 'greenhouse':  # the list feed does not carry these: keep what we read before
            for k in ('team', 'pay', 'detail'):
                if old.get(k) and not it.get(k):
                    it[k] = old[k]
        out[it['id']] = it
    for pid, old in prev.items():
        if pid in out:
            continue
        if f"{old['source']}:{old['board']}" in ok_boards:
            old['misses'] = old.get('misses', 0) + 1
            if old['misses'] >= DROP_AFTER:
                continue
        out[pid] = old
    for it in out.values():
        if not it.get('misses'):
            it.pop('misses', None)
    return sorted(out.values(), key=lambda i: (i['country'], i['org'].lower(), i['title'].lower(), i['url']))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sources', default=str(ROOT / 'data/internship_sources.json'))
    ap.add_argument('--prev', default=str(ROOT / 'src/data/internships.json'))
    ap.add_argument('--out', default=str(ROOT / 'src/data/internships.json'))
    ap.add_argument('--report', default=str(ROOT / 'out'))
    ap.add_argument('--only', default='', help='comma-separated slugs, or "open" for the open feeds only')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--workers', type=int, default=6)
    ap.add_argument('--delay', type=float, default=2.0)
    ap.add_argument('--max-minutes', type=float, default=60)
    ap.add_argument('--if-older-than-hours', type=float, default=0)
    ap.add_argument('--contact', default=os.environ.get('CONTACT_EMAIL', ''))
    ap.add_argument('--today', default='')
    ap.add_argument('--allow-drop', action='store_true')
    ap.add_argument('--skip-portals', action='store_true')
    ap.add_argument('--recheck-only', action='store_true', help='apply the current rules to the saved data and stop; no websites are read')
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    today = args.today or now.date().isoformat()
    prev = load(args.prev, {})
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

    cfg = load(args.sources, {})
    ORG_ALIAS.update({k.lower(): v for k, v in (cfg.get('orgAliases') or {}).items()})
    if prev.get('items'):
        prev['items'], dropped_old = recheck(prev['items'])
        if dropped_old:
            print(f'{dropped_old} saved postings no longer pass the title rules and were removed.')
    if args.recheck_only:
        prev['items'] = prev.get('items', [])
        prev['stats'] = {**prev.get('stats', {}), 'items': len(prev['items']), 'byCountry': dict(sorted(Counter(i['country'] for i in prev['items']).items())),
                         'bySource': dict(sorted(Counter(i['source'] for i in prev['items']).items()))}
        Path(args.out).write_text(json.dumps(prev, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        print(f"re-checked {args.out}: {len(prev['items'])} postings")
        return 0
    employers = cfg.get('employers', [])
    open_feeds = cfg.get('openFeeds', {})
    if args.only:
        want = set(args.only.split(','))
        employers = [e for e in employers if e['slug'] in want]
        open_feeds = {k: v for k, v in open_feeds.items() if k in want or 'open' in want}
    if args.limit:
        employers = employers[:args.limit]

    ua = f"Universities500Bot/1.0 (+https://universities500.com/bot/{'; ' + args.contact if args.contact else ''})"
    t0 = time.monotonic()
    fx = Fetcher(ua, delay=args.delay, deadline=t0 + args.max_minutes * 60, max_bytes=40_000_000)
    print('User-Agent:', ua)

    jobs = [('employer', e) for e in employers]
    if open_feeds.get('jobtech', {}).get('enabled'):
        jobs.append(('open', {'name': 'Platsbanken', 'ats': 'jobtech', 'slug': 'sweden'}))
    if open_feeds.get('arbeitnow', {}).get('enabled'):
        jobs.append(('open', {'name': 'Arbeitnow', 'ats': 'arbeitnow', 'slug': 'germany'}))

    unplaced = Counter()
    boards = {}  # (source, slug) -> dict
    new_items = []

    def work(job):
        kind, e = job
        try:
            if e['ats'] == 'jobtech':
                st, rows = S.jobtech(fx)
            elif e['ats'] == 'arbeitnow':
                st, rows = S.arbeitnow(fx)
            else:
                st, rows = S.ATS[e['ats']](fx, e['slug'])
        except Exception as ex:  # one bad board must not stop the run
            return e, 'error', [], f'{type(ex).__name__}: {ex}'
        return e, st, rows, ''

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(work, jobs))

    ok_boards = set()
    for e, st, rows, note in results:
        items = []
        for raw in rows:
            items.extend(normalise(raw, e['ats'], e['slug'], e['name'], unplaced))
        boards[(e['ats'], e['slug'])] = {'name': e['name'], 'status': st, 'postings': len(rows), 'matched': len(items), 'note': note}
        if st == 'ok':
            ok_boards.add(f"{e['ats']}:{e['slug']}")
            new_items.extend(items)

    # the same posting can be listed twice by one source (for example under two search words): keep one
    uniq = {}
    for it in new_items:
        uniq.setdefault(it['id'], it)
    enr = enrich_greenhouse(fx, list(uniq.values()), prev.get('items', []))
    print(f'Greenhouse detail: {enr[2]} postings asked, {enr[0]} read, {enr[1]} with a pay range.')
    merged = merge(prev.get('items', []), list(uniq.values()), ok_boards, today)

    # ---- link-only portals: is the link alive? We read the front page and robots.txt, nothing else ----
    portals = []
    if not args.skip_portals:
        for p in cfg.get('portals', []):
            res = fx.get(p['url'])
            alive = res.ok or res.robots_blocked  # a site that has a robots.txt which says "no bots" is still a live link
            host = urllib.parse.urlsplit(p['url']).netloc
            portals.append({**p, 'ok': bool(alive), 'checked': today if alive else None,
                            'robotsText': fx.robots_text.get(host, '')[:1200]})
    else:
        portals = [{**p, 'ok': False, 'checked': None, 'robotsText': ''} for p in cfg.get('portals', [])]

    prev_n = len(prev.get('items', []))
    n_ok = sum(1 for v in boards.values() if v['status'] == 'ok')
    gate_failed = None
    if jobs and n_ok == 0:
        gate_failed = 'No source could be read, so nothing was written and the previous data stays.'
    elif prev_n >= 40 and len(merged) < 0.5 * prev_n and not args.allow_drop:
        gate_failed = f'The new list has {len(merged)} postings against {prev_n} before (less than half). Nothing was written. Check the report, then re-run with --allow-drop if this is real.'

    write_report(args, fx, boards, merged, prev_n, unplaced, portals, today, now, t0, gate_failed)
    if gate_failed:
        print('STOPPED:', gate_failed)
        return 3

    by_country = Counter(i['country'] for i in merged)
    by_source = Counter(i['source'] for i in merged)
    out = {
        'version': 1,
        'generatedAt': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'today': today,
        'stats': {'items': len(merged), 'byCountry': dict(sorted(by_country.items())), 'bySource': dict(sorted(by_source.items())),
                  'boardsRead': len(boards), 'boardsOk': n_ok},
        'items': merged,
        'portals': portals,
    }
    for p in out['portals']:
        p.pop('robotsText', None)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(f"wrote {args.out}: {len(merged)} postings ({prev_n} before), {n_ok}/{len(boards)} sources read")
    return 0


def write_report(args, fx, boards, merged, prev_n, unplaced, portals, today, now, t0, gate_failed):
    rep = Path(args.report)
    rep.mkdir(parents=True, exist_ok=True)
    L = [f'# Internship run {now.strftime("%Y-%m-%d %H:%M")} UTC', '']
    if gate_failed:
        L += [f'**STOPPED.** {gate_failed}', '']
    st = Counter(v['status'] for v in boards.values())
    L += [f'- Sources: {len(boards)} asked, {st.get("ok", 0)} read, {st.get("missing", 0)} do not exist, {st.get("blocked", 0)} blocked by robots.txt, {st.get("error", 0)} errors',
          f'- Postings kept: {len(merged)} (before this run: {prev_n})',
          f'- Requests: {fx.stats.get("requests", 0)}, took {int(time.monotonic() - t0)} s', '']
    per = defaultdict(Counter)
    for (a, _s), v in boards.items():
        per[a][v['status']] += 1
        per[a]['postings read'] += v['postings']
        per[a]['internships kept'] += v['matched']
    L += ['## By source type', '| Type | Asked | ok | missing | blocked | error | Postings read | Internships kept |', '|---|---|---|---|---|---|---|---|']
    for a, c in sorted(per.items()):
        asked = sum(1 for (x, _s) in boards if x == a)
        L.append(f'| {a} | {asked} | {c["ok"]} | {c["missing"]} | {c["blocked"]} | {c["error"]} | {c["postings read"]} | {c["internships kept"]} |')
    L.append('')
    by_c = Counter(i['country'] for i in merged)
    L += ['## By destination', '| Destination | Postings |', '|---|---|'] + [f'| {P.COUNTRY_NAMES.get(c, c)} | {n} |' for c, n in sorted(by_c.items())] + ['']
    by_k = Counter(i['kind'] for i in merged)
    L += ['## By kind', ', '.join(f'{k}: {n}' for k, n in by_k.most_common()), '']
    ok_zero = [f'{k[0]}:{k[1]}' for k, v in boards.items() if v['status'] == 'ok' and v['matched'] == 0]
    missing = [f'{k[0]}:{k[1]}' for k, v in boards.items() if v['status'] == 'missing']
    blocked = [f'{k[0]}:{k[1]}' for k, v in boards.items() if v['status'] == 'blocked']
    errs = [f'{k[0]}:{k[1]} {v["note"]}' for k, v in boards.items() if v['status'] == 'error']
    L += [f'## Boards that do not exist ({len(missing)}): remove them from data/internship_sources.json', ', '.join(missing) or 'none', '']
    L += [f'## Boards read but with no internships ({len(ok_zero)})', ', '.join(ok_zero) or 'none', '']
    L += [f'## Blocked by robots.txt ({len(blocked)})', ', '.join(blocked) or 'none', '']
    L += [f'## Errors ({len(errs)})', '\n'.join(f'- {e}' for e in errs) or 'none', '']
    L += ['## Internship-like postings whose place could not be told (top 40): extend scripts/internships/places.py if these are real destinations', '']
    L += [f'- {k}: {n}' for k, n in unplaced.most_common(40)] or ['none']
    L += ['', '## Link-only portals', '| Portal | Alive | robots.txt text |', '|---|---|---|']
    for p in portals:
        rt = (p.get('robotsText') or '').replace('\n', ' / ')[:160]
        L.append(f'| {p["title"]} | {"yes" if p["ok"] else "no"} | {rt} |')
    (rep / 'internship_report.md').write_text('\n'.join(L) + '\n', encoding='utf-8')
    # The run's log is readable without downloading the artifact, so the diagnostics go there too (not the portal table).
    cut = next((n for n, l in enumerate(L) if l.startswith('## Link-only portals')), len(L))
    print('\n'.join(L[:cut]))
    summ = os.environ.get('GITHUB_STEP_SUMMARY')  # the run's summary page on GitHub shows the top of the report
    if summ:
        Path(summ).open('a', encoding='utf-8').write('\n'.join(L[:60]) + '\n')
    with (rep / 'boards.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['source', 'slug', 'name', 'status', 'postings', 'matched', 'note'])
        for (a, s), v in sorted(boards.items()):
            w.writerow([a, s, v['name'], v['status'], v['postings'], v['matched'], v['note']])
    per = defaultdict(list)
    for i in merged:
        per[i['country']].append(i)
    sample = [it for c in sorted(per) for it in per[c][:4]]
    (rep / 'sample_items.json').write_text(json.dumps(sample, ensure_ascii=False, indent=1), encoding='utf-8')
    (rep / 'robots_blocked.txt').write_text('\n'.join(f'{h}{p}' for h, p in fx.robots_blocked) + '\n', encoding='utf-8')


if __name__ == '__main__':
    sys.exit(main())
