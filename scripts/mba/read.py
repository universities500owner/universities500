#!/usr/bin/env python3
"""Read the pages of the MBA programmes in data/mba_sources.json and write data/mba/read/<id>.json.

No AI and no API key: patterns and page structure only (see mbafacts.py). Polite: identifies itself, obeys robots.txt, waits
between requests to one website, and never works around a 403, a bot challenge or a robots.txt rule: that page is reported and skipped.
The output is data for review. It does not change the website until build_site_data.py runs.

Usage: python3 scripts/mba/read.py [--only id,id] [--limit N] [--force] [--delay 3] [--contact you@example.com]
"""
import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.resolve().parents[1]
for p in (HERE, HERE.parent / 'scholarships', HERE.parent / 'courses'):
    sys.path.insert(0, str(p))
import mbafacts as M  # noqa: E402
from fetcher import Fetcher  # noqa: E402

COMPARE = ('length', 'fee', 'exp', 'degree', 'test', 'english', 'start', 'deadlines', 'employment')


def load(p, default):
    try:
        return json.loads(Path(p).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def page_result(fx, url):
    """('ok', html) or (reason, '') for one page. Nothing here retries or goes around a refusal."""
    r = fx.get(url)
    if r.robots_blocked:
        return f'robots-blocked ({r.robots_reason})', ''
    if r.status in (401, 403, 429):
        return f'refused (HTTP {r.status})', ''
    if not r.ok:
        return f'not-read ({r.status or r.error})', ''
    if 'html' not in (r.ctype or '').lower() and '<html' not in r.text[:2000].lower():
        return 'not-html', ''
    return 'ok', r.text


def read_programme(fx, prog, country):
    """Fetch the programme's pages in the register's order and merge what they say. Returns the output document."""
    per_page, pages, hashes = [], [], []
    for url in prog.get('pages', []):
        status, html = page_result(fx, url)
        entry = {'url': url, 'status': status}
        if status == 'ok':
            facts, rejected = M.read_page(html, url, country)
            entry['facts'] = sorted(facts)
            per_page.append((facts, rejected))
            hashes.append(hashlib.sha256(html.encode('utf-8', 'replace')).hexdigest()[:16])
        pages.append(entry)
    facts, rejected = M.merge(per_page)
    return {'id': prog['id'], 'pages': pages, 'hash': hashlib.sha256('|'.join(hashes).encode()).hexdigest()[:16] if hashes else '',
            'facts': facts, 'rejected': [{'fact': a, 'why': b} for a, b in rejected]}


def same(a, b):
    """Do a hand-read fact and a program-read fact say the same thing? Compared by what the site would show and the numbers behind it."""
    if not a or not b:
        return False
    for k in ('amount', 'min', 'max', 'months', 'ielts', 'overall'):
        if (a.get(k) is not None or b.get(k) is not None) and a.get(k) != b.get(k):
            return False
    return (a.get('t') or '').lower() == (b.get('t') or '').lower() or any(a.get(k) is not None for k in ('amount', 'min', 'months', 'ielts'))


def diff_against(pilot_rec, facts):
    """{fact: 'same' | 'differs' | 'only read by program' | 'only read by hand'} so a person can check where the program and the hand reading disagree."""
    out = {}
    for k in COMPARE:
        a, b = (pilot_rec or {}).get(k), facts.get(k)
        if a and b:
            out[k] = 'same' if same(a, b) else 'differs'
        elif b:
            out[k] = 'only read by program'
        elif a:
            out[k] = 'only read by hand'
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--register', default=str(ROOT / 'data' / 'mba_sources.json'))
    ap.add_argument('--pilot', default=str(HERE / 'pilot.json'))
    ap.add_argument('--out', default=str(ROOT / 'data' / 'mba' / 'read'))
    ap.add_argument('--only', default='')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--delay', type=float, default=3.0)
    ap.add_argument('--max-minutes', type=float, default=25)
    ap.add_argument('--contact', default=os.environ.get('CONTACT_EMAIL', ''))
    ap.add_argument('--force', action='store_true', help='read again even when the page has not changed')
    ap.add_argument('--allow-http-local', action='store_true', help='tests only: allow http://127.0.0.1')
    args = ap.parse_args()

    reg = load(args.register, {})
    pilot = {r['id']: r for r in load(args.pilot, {}).get('items', [])}
    progs = [p for p in reg.get('programmes', []) if p.get('pages')]
    if args.only:
        want = set(args.only.split(','))
        progs = [p for p in progs if p['id'] in want]
    if args.limit:
        progs = progs[:args.limit]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    ua = f"Universities500Bot/1.0 (+https://universities500.com/bot/{'; ' + args.contact if args.contact else ''})"
    fx = Fetcher(ua, delay=args.delay, deadline=time.monotonic() + args.max_minutes * 60, allow_http_local=args.allow_http_local)
    print('User-Agent:', ua)
    today = datetime.now(timezone.utc).date().isoformat()
    rows = []
    for prog in progs:
        pid = prog['id']
        country = (pilot.get(pid) or {}).get('country') or prog.get('country')
        prev = load(out_dir / f'{pid}.json', {})
        doc = read_programme(fx, prog, country)
        ok_pages = [p for p in doc['pages'] if p['status'] == 'ok']
        if not ok_pages:
            # a bad day, not a changed programme: keep what we had and say why
            rows.append((pid, 'not read', ', '.join(f"{p['status']}" for p in doc['pages']) or 'no pages', {}))
            continue
        if prev.get('hash') and prev['hash'] == doc['hash'] and not args.force:
            rows.append((pid, 'unchanged', 'pages have not changed since the last read', diff_against(pilot.get(pid), prev.get('facts', {}))))
            continue
        doc['readOn'] = today
        doc['diff'] = diff_against(pilot.get(pid), doc['facts'])
        (out_dir / f'{pid}.json').write_text(json.dumps(doc, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
        failed = [p for p in doc['pages'] if p['status'] != 'ok']
        rows.append((pid, 'read', f"{len(ok_pages)} of {len(doc['pages'])} pages" + (f"; {len(failed)} not read" if failed else ''), doc['diff']))

    # ---- the report: what was read, and where the program and the hand reading disagree ----
    lines = ['## MBA reader', '', f'Read on {today}. {len(rows)} programmes. {fx.stats.get("requests", 0)} requests. No AI.', '',
             '| Programme | Result | Notes | Agrees with hand reading | Differs | Only by program |', '|---|---|---|---|---|---|']
    for pid, status, note, d in rows:
        agree = ', '.join(k for k, v in d.items() if v == 'same')
        differs = ', '.join(k for k, v in d.items() if v == 'differs')
        extra = ', '.join(k for k, v in d.items() if v == 'only read by program')
        lines.append(f'| {pid} | {status} | {note} | {agree} | {differs} | {extra} |')
    errs = getattr(fx, 'errors', None)
    if errs:
        lines += ['', 'Pages that could not be read:', ''] + [f'- {e}' for e in (list(errs.items()) if isinstance(errs, dict) else errs)[:30]]
    report = '\n'.join(lines) + '\n'
    print(report)
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf-8') as fh:
            fh.write(report)
    return 0


if __name__ == '__main__':
    sys.exit(main())
