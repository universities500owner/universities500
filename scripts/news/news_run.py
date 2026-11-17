#!/usr/bin/env python3
"""Daily reader of official news about international students, for the 14 countries on the site.

Reads the sources in data/news_sources.json (government and immigration bodies, and official study agencies), keeps the items that are
about international students, and writes src/data/industry_news.json. Nothing is rewritten: the headline and the summary are the official text,
shortened at a sentence end, with the official link and the date the official body gave. No AI.

  python3 scripts/news/news_run.py --report out                 # the normal daily run
  python3 scripts/news/news_run.py --probe --report out         # read and report only; write no data file
  python3 scripts/news/news_run.py --only uk,canada --probe     # a few countries
"""
import argparse
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / 'scripts' / 'scholarships'))
from fetcher import Fetcher  # noqa: E402
import news_read as NR  # noqa: E402
import news_rules as R  # noqa: E402

KEEP_DAYS = 120          # an item older than this is dropped
PER_COUNTRY = 30         # at most this many items kept per country
RECHECK = 6              # stored items re-opened each run to see that their official page still exists
COUNTRIES = ['usa', 'uk', 'canada', 'australia', 'new-zealand', 'ireland', 'germany', 'france', 'netherlands', 'sweden', 'norway', 'singapore', 'malaysia', 'uae']


def item_id(url):
    import hashlib
    return hashlib.sha1(url.encode()).hexdigest()[:12]


def load(p, default):
    try:
        return json.loads(Path(p).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def dump(doc):
    """One item per line so a git diff shows what changed."""
    parts = ['{']
    for k in doc:
        if k != 'items':
            parts.append(f'"{k}": {json.dumps(doc[k], ensure_ascii=False)},')
    parts.append('"items": [')
    parts.append(',\n'.join(json.dumps(i, ensure_ascii=False) for i in doc['items']))
    parts.append(']')
    parts.append('}')
    return '\n'.join(parts) + '\n'


def merge(prev_items, fresh, today, keep_days=KEEP_DAYS, per_country=PER_COUNTRY):
    """Previous items stay until they age out; fresh items are added or updated. An item missing from today's feed is not removed:
    official notices stay on the official site. (A page that no longer exists is removed by recheck().)"""
    by_url = {i['url']: dict(i) for i in prev_items}
    for it in fresh:
        old = by_url.get(it['url'])
        rec = dict(it, id=item_id(it['url']), firstSeen=old['firstSeen'] if old else today, lastSeen=today)
        if old and (old.get('title') != it['title'] or old.get('summary') != it['summary']):
            rec['updated'] = today
        elif old and old.get('updated'):
            rec['updated'] = old['updated']
        by_url[it['url']] = rec
    kept = [i for i in by_url.values() if (R.age_days(i.get('published'), today) or 0) <= keep_days]
    out = []
    for c in COUNTRIES:
        rows = sorted((i for i in kept if i['country'] == c), key=lambda i: (i['published'], i['title']), reverse=True)
        out.extend(rows[:per_country])
    return out


def recheck(items, fx, today, n=RECHECK):
    """Open the official page of the items we have not seen in a feed for longest. A page that answers 404 or 410 is removed."""
    stale = sorted((i for i in items if i.get('lastSeen') != today), key=lambda i: i.get('lastSeen', ''))[:n]
    gone = set()
    for i in stale:
        res = fx.get(i['url'])
        if res.status in (404, 410):
            gone.add(i['url'])
        elif res.ok:
            i['lastSeen'] = today
    return [i for i in items if i['url'] not in gone], len(gone)


def why_empty(info):
    """For a source that gave no items: blocked (robots.txt, or the site refuses us), unreadable (the page loads but shows no headlines we can read), or failed."""
    tried = info['tried']
    if info['robotsBlocked'] and not any(t['status'] == 200 for t in tried):
        return 'blocked'
    if tried and all(t['status'] in (401, 403, 429) for t in tried if not t.get('error', '').startswith('blocked')):
        return 'blocked'
    if any(t['status'] == 200 for t in tried):
        return 'unreadable'
    return 'failed'


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--sources', default=str(ROOT / 'data' / 'news_sources.json'))
    ap.add_argument('--data', default=str(ROOT / 'src' / 'data' / 'industry_news.json'))
    ap.add_argument('--report', default=str(ROOT / 'out'))
    ap.add_argument('--only', default='', help='country codes, comma-separated (blank = all)')
    ap.add_argument('--probe', action='store_true', help='read and report; do not write the data file')
    ap.add_argument('--today', default='')
    ap.add_argument('--delay', type=float, default=3.0)
    ap.add_argument('--max-minutes', type=float, default=40)
    ap.add_argument('--contact', default=os.environ.get('CONTACT_EMAIL', ''))
    args = ap.parse_args(argv)

    today = args.today or datetime.now(timezone.utc).date().isoformat()
    now_iso = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    cfg = load(args.sources, {})
    sources = cfg.get('sources', [])
    keep_days = int(cfg.get('keepDays', KEEP_DAYS))
    only = {x.strip() for x in args.only.split(',') if x.strip()}
    if only:
        sources = [s for s in sources if s['country'] in only]
    ua = 'Universities500Bot/1.0 (+https://universities500.com/bot/' + (f'; {args.contact}' if args.contact else '') + ')'
    print('User-Agent:', ua)
    fx = Fetcher(ua, delay=args.delay, deadline=time.monotonic() + args.max_minutes * 60)

    prev = load(args.data, {'items': [], 'sources': {}})
    known = {i['url']: i for i in prev.get('items', [])}
    fresh, infos = [], []
    for src in sources:
        items, info = NR.read_source(src, fx, today, keep_days, known)
        fresh.extend(items)
        infos.append(info)
        print(f"[{src['country']}] {src['id']}: {info['kept']} kept of {info['found']} found ({info['via'] or info['error']})", flush=True)

    ok_sources = [i for i in infos if i['found'] > 0]
    status = dict(prev.get('sources', {}))
    for src, info in zip(sources, infos):
        st = 'ok' if info['kept'] else ('no-recent-item' if info['found'] else why_empty(info))
        status[src['id']] = {'country': src['country'], 'body': src['body'], 'kind': src.get('kind', 'government'), 'url': src.get('home') or src.get('list') or (src.get('feeds') or [''])[0],
                             'status': st, 'checked': today, 'found': info['found'], 'kept': info['kept'], 'via': info['via'].split(' ')[0] if info['via'] else ''}
    # drop status rows of sources that left the list
    live = {s['id'] for s in cfg.get('sources', [])}
    status = {k: v for k, v in status.items() if k in live}

    merged = merge(prev.get('items', []), fresh, today, keep_days)
    merged, removed = recheck(merged, fx, today)
    doc = {'generatedAt': now_iso, 'keepDays': keep_days, 'sources': status, 'items': merged}

    wrote = False
    if args.probe:
        pass
    elif not ok_sources and sources:
        print('STOPPED: no source answered. The data file was left as it was.')
        report(args, sources, infos, merged, removed, today, wrote, True)
        return 3
    else:
        Path(args.data).parent.mkdir(parents=True, exist_ok=True)
        Path(args.data).write_text(dump(doc), encoding='utf-8')
        wrote = True
    report(args, sources, infos, merged, removed, today, wrote, False)
    return 0


def report(args, sources, infos, merged, removed, today, wrote, stopped):
    rep = Path(args.report)
    rep.mkdir(parents=True, exist_ok=True)
    (rep / 'news_probe.json').write_text(json.dumps([{**i, 'drops': dict(i['drops'])} for i in infos], indent=1, ensure_ascii=False), encoding='utf-8')
    by_c = Counter(i['country'] for i in merged)
    L = [f'# Industry news run, {today}', '',
         f'{len(sources)} sources read. Items on file: **{len(merged)}**. {"Data file written." if wrote else ("STOPPED, nothing written." if stopped else "Probe only, nothing written.")} Removed because the official page is gone: {removed}.', '',
         '## Items per country', '', ', '.join(f'{c} {by_c.get(c, 0)}' for c in COUNTRIES), '', '## Sources', '',
         '| country | source | result | how | found | kept | dropped because | sample |', '|---|---|---|---|---|---|---|---|']
    for i in infos:
        res = 'ok' if i['kept'] else ('no recent item' if i['found'] else (i['error'] or 'failed'))
        drops = ', '.join(f'{k} {v}' for k, v in i['drops'].most_common(4))
        L.append(f"| {i['country']} | {i['id']} | {res} | {i['via'].split(' ')[0] or '-'} | {i['found']} | {i['kept']} | {drops or '-'} | {(i['samples'][0] if i['samples'] else '-')[:70]} |")
    L += ['', '## Addresses tried, for sources that gave nothing', '']
    for i in infos:
        if not i['kept']:
            L.append(f"- **{i['id']}**: " + '; '.join(f"{t['url']} -> {t.get('error') or t['status']}" for t in i['tried'][:6]))
    L += ['', '## What the pages looked like when no items could be read', '(chars = visible text; many scripts and few chars usually means the headlines are loaded by script; dates = date-like strings on the page)', '']
    for i in infos:
        if i['found'] or not (i.get('profiles') or i.get('sections')):
            continue
        if i.get('sections'):
            L.append(f"- **{i['id']}** news pages found on the home page and tried: " + ', '.join(i['sections']))
        for pr in i.get('profiles', [])[:3]:
            L.append(f"- **{i['id']}** {pr['url']}: \"{pr['title']}\" | chars {pr['chars']}, links {pr['links']}, time-tags {pr['timeTags']}, dates {pr['dates']}, scripts {pr['scripts']}")
            for sm in pr['sample'][:4]:
                L.append(f"    - {sm}")
    L += ['', '## Examples the relevance rule rejected (check these are really not about students)', '']
    for i in infos:
        for r in i['rejected']:
            L.append(f"- {i['id']}: {r}")
    L += ['', '## Items on file (newest first)', '']
    for it in sorted(merged, key=lambda x: (x['published'], x['title']), reverse=True)[:80]:
        L.append(f"- {it['country']} | {it['published']} | {it['title'][:110]} | {it['url']}")
    text = '\n'.join(L) + '\n'
    (rep / 'news_report.md').write_text(text, encoding='utf-8')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        Path(os.environ['GITHUB_STEP_SUMMARY']).open('a').write(text)
    print(text)      # the whole report goes to the job log, so a run can be read without opening the artifact


if __name__ == '__main__':
    sys.exit(main())
