#!/usr/bin/env python3
"""Run the course-detail reader: Claude Haiku 5.5 through the Batch API, on course pages the reader already accepted.

    python3 scripts/courses/detail_run.py run --per-uni 2 --limit-unis 15 --wait-minutes 120      # a small pilot, start to finish
    python3 scripts/courses/detail_run.py prepare ...    # fetch the pages, write out/detail/requests.jsonl and out/detail/pages.json
    python3 scripts/courses/detail_run.py submit         # send the batch, write out/detail/batch.json
    python3 scripts/courses/detail_run.py collect        # wait for the batch, check every answer against the page, write src/data/course-detail/

Needs ANTHROPIC_API_KEY (GitHub secret) and `pip install anthropic`. Batch only: half the price of normal requests, results within 24 hours.
Pages are fetched politely (robots.txt, 3 seconds between requests to one site, identified User-Agent) by the same fetcher as the course reader.
The model is given the page's own text and never browses. Every quote and name it returns is checked against that text; what is not on the page is dropped.
A page is read again only when its text changed (page hash), so a monthly run costs little.
"""
import argparse
import hashlib
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / 'scholarships'))
sys.path.insert(0, str(HERE))
import detail as D  # noqa: E402
import extract as X  # noqa: E402
from fetcher import Fetcher  # noqa: E402

OUT = ROOT / 'out/detail'
DETAIL_DIR = ROOT / 'src/data/course-detail'
BATCH_PRICE = {'in': 0.05, 'out': 0.25}      # USD per million tokens, Haiku 5.5 batch, prompts up to 100,000 tokens
CHUNK = 2000                                  # requests per batch


def load(path, default):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def cid(url):
    return 'c' + hashlib.sha1(url.encode('utf-8')).hexdigest()[:24]


def accepted_courses(items_path, only=''):
    """{university slug: [course items]}: the courses the site publishes (src/data/courses.json), each with the address of its page."""
    want = set(filter(None, only.split(',')))
    out = {}
    for c in load(items_path, {}).get('items') or []:
        if c.get('url') and c.get('uni') and (not want or c['uni'] in want):
            out.setdefault(c['uni'], []).append(c)
    return out


def pick(recs, per_uni):
    """A spread over the list, not just the first few: every k-th course by address."""
    recs = sorted(recs, key=lambda c: c['url'])
    if not per_uni or per_uni >= len(recs):
        return recs
    step = len(recs) / per_uni
    return [recs[int(i * step)] for i in range(per_uni)]


def prepare(a, fx=None):
    """Fetch the chosen course pages and cut them into sections. Returns (requests, pages)."""
    OUT.mkdir(parents=True, exist_ok=True)
    chosen = accepted_courses(a.courses_file, a.only)
    unis = sorted(chosen)[:a.limit_unis] if a.limit_unis else sorted(chosen)
    if fx is None:
        ua = f"Universities500Bot/1.0 (+https://universities500.com/bot/{'; ' + a.contact if a.contact else ''})"
        fx = Fetcher(ua, delay=a.delay, deadline=time.monotonic() + a.max_minutes * 60)
    requests, pages, skipped, failed = [], {}, Counter(), Counter()
    for slug in unis:
        prev = load(DETAIL_DIR / f'{slug}.json', {}).get('pages', {})
        for rec in pick(chosen[slug], a.per_uni):
            url = rec['url']
            res = fx.get(url)
            if not res.ok:
                failed[slug] += 1
                continue
            secs = D.sections_of(res.text, res.final_url)
            if len(' '.join(s['text'] for s in secs)) < 400:
                failed[slug] += 1                       # nothing readable (a script-built page)
                continue
            if getattr(a, 'preview', False):
                heads = ' | '.join(f"{x['heading'][:38] or '(none)'} [{len(x['text'])}]" for x in secs[:40])
                print(f"PAGE {url}\n  {len(secs)} sections, {sum(len(x['text']) for x in secs)} chars: {heads}")
            h = D.page_hash(secs)
            if prev.get(url, {}).get('hash') == h and not a.force:
                skipped[slug] += 1
                continue
            requests.append(D.request_of(cid(url), secs, url, a.model))
            pages[cid(url)] = {'uni': slug, 'url': url, 'hash': h, 'sections': secs}
    (OUT / 'requests.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in requests), encoding='utf-8')
    (OUT / 'pages.json').write_text(json.dumps(pages, ensure_ascii=False), encoding='utf-8')
    print(f'{len(requests)} pages to read ({sum(skipped.values())} unchanged, {sum(failed.values())} could not be read) from {len(unis)} universities')
    return requests, pages


def make_client():
    import anthropic
    return anthropic.Anthropic()          # ANTHROPIC_API_KEY from the environment


def submit(client, requests):
    """Send the requests in batches. Returns the batch ids."""
    ids = []
    for i in range(0, len(requests), CHUNK):
        b = client.messages.batches.create(requests=requests[i:i + CHUNK])
        ids.append(b.id)
        print(f'submitted batch {b.id} ({len(requests[i:i + CHUNK])} requests)')
    (OUT / 'batch.json').write_text(json.dumps({'ids': ids, 'submitted': datetime.now(timezone.utc).isoformat(timespec='seconds')}), encoding='utf-8')
    return ids


def wait(client, ids, minutes, sleep=60):
    """Poll until every batch has ended or the time is up. Returns True when all ended."""
    deadline = time.monotonic() + minutes * 60
    while True:
        states = [client.messages.batches.retrieve(i).processing_status for i in ids]
        print('batch status:', states, flush=True)
        if all(s == 'ended' for s in states):
            return True
        if time.monotonic() > deadline:
            return False
        time.sleep(sleep)


def usage_of(message):
    u = getattr(message, 'usage', None)
    if u is None:
        return 0, 0
    return getattr(u, 'input_tokens', 0) or 0, getattr(u, 'output_tokens', 0) or 0


def collect(client, ids, pages, today, model=D.MODEL):
    """Check every answer against its page and merge what survives into src/data/course-detail/<university>.json. Returns the report dict."""
    by_uni, rep = {}, {'ok': 0, 'failed': 0, 'rejected': Counter(), 'fields': Counter(), 'sections': Counter(), 'in': 0, 'out': 0, 'samples': []}
    for bid in ids:
        for entry in client.messages.batches.results(bid):
            page = pages.get(entry.custom_id)
            if not page:
                continue
            res = entry.result
            if getattr(res, 'type', '') != 'succeeded':
                rep['failed'] += 1
                continue
            i, o = usage_of(res.message)
            rep['in'] += i
            rep['out'] += o
            ti = D.parse_tool_input(res.message.content)
            if not ti:
                rep['failed'] += 1
                continue
            detail, rejected = D.verify(ti, page['sections'])
            for what, why in rejected:
                rep['rejected'][f'{what}: {why}'] += 1
            detail.update({'hash': page['hash'], 'readOn': today, 'model': model})
            rep['ok'] += 1
            for k, v in detail['facts'].items():
                if v:
                    rep['fields'][k] += 1
            for t in detail['sections']:
                rep['sections'][t] += 1
            by_uni.setdefault(page['uni'], {})[page['url']] = detail
            if len(rep['samples']) < 12:
                rep['samples'].append({'url': page['url'], 'detail': detail, 'rejected': rejected})
    DETAIL_DIR.mkdir(parents=True, exist_ok=True)
    for slug, new in by_uni.items():
        path = DETAIL_DIR / f'{slug}.json'
        doc = load(path, {'slug': slug, 'pages': {}})
        doc['slug'] = slug
        doc['pages'].update(new)
        path.write_text(D.dump(doc), encoding='utf-8')
    rep['cost_usd'] = round(rep['in'] / 1e6 * BATCH_PRICE['in'] + rep['out'] / 1e6 * BATCH_PRICE['out'], 4)
    return rep


def write_report(rep, total):
    n = rep['ok'] or 1
    lines = [f"# Course detail run", '',
             f"- Pages answered: {rep['ok']} of {total} ({rep['failed']} failed or empty)",
             f"- Tokens: {rep['in']:,} in, {rep['out']:,} out; cost at the batch rate: ${rep['cost_usd']} (about ${rep['cost_usd'] / n:.4f} a page)", '',
             '## Facts found (pages with the fact, after checking)']
    for k, v in sorted(rep['fields'].items(), key=lambda kv: -kv[1]):
        lines.append(f'- {k}: {v} ({100 * v // n}%)')
    lines += ['', '## Sections copied from the page']
    for k, v in sorted(rep['sections'].items(), key=lambda kv: -kv[1]):
        lines.append(f'- {k}: {v} ({100 * v // n}%)')
    lines += ['', '## Thrown away because the page does not show it']
    for k, v in rep['rejected'].most_common():
        lines.append(f'- {k}: {v}')
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    (OUT / 'samples.json').write_text(json.dumps(rep['samples'], ensure_ascii=False, indent=1), encoding='utf-8')
    print('\n'.join(lines))
    for smp in rep['samples'][:8]:
        f = smp['detail']['facts']
        print(f"\nSAMPLE {smp['url']}")
        print('  duration:', (f.get('duration') or {}).get('text'), '| mode:', (f.get('studyMode') or {}).get('text'), '| campus:', (f.get('campus') or {}).get('text'))
        print('  starts:', [x['text'] for x in f.get('starts') or []], '| ielts:', (f.get('ielts') or {}).get('overall'), '| other tests:', [(x['test'], x['score']) for x in f.get('otherEnglish') or []])
        print('  fees:', [(x['audience'], x['amount'], x['currency'], x['period']) for x in f.get('fees') or []])
        print('  deadlines:', [(x['label'], x['date']) for x in f.get('deadlines') or []][:4])
        print('  modules:', len(f.get('coreModules') or []), 'core,', len(f.get('optionalModules') or []), 'optional | employers:', (f.get('employers') or [])[:6])
        print('  sections:', {k: sum(len(b['text']) for b in v) for k, v in smp['detail']['sections'].items()})
        if smp['rejected']:
            print('  thrown away:', smp['rejected'][:6])
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf-8') as fh:
            fh.write('\n'.join(lines) + '\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['run', 'prepare', 'submit', 'collect'])
    ap.add_argument('--courses-file', default=str(ROOT / 'src/data/courses.json'))
    ap.add_argument('--only', default='')
    ap.add_argument('--per-uni', type=int, default=2, help='courses read per university (0 = all)')
    ap.add_argument('--limit-unis', type=int, default=0)
    ap.add_argument('--model', default=D.MODEL)
    ap.add_argument('--preview', action='store_true', help='print each page\'s headings and sizes (no API key needed with prepare)')
    ap.add_argument('--force', action='store_true', help='read a page again even if its text has not changed')
    ap.add_argument('--delay', type=float, default=3.0)
    ap.add_argument('--max-minutes', type=float, default=120)
    ap.add_argument('--wait-minutes', type=float, default=180)
    ap.add_argument('--contact', default=os.environ.get('CONTACT_EMAIL', ''))
    a = ap.parse_args()
    today = datetime.now(timezone.utc).date().isoformat()
    if a.cmd in ('run', 'prepare'):
        requests, pages = prepare(a)
        if a.cmd == 'prepare' or not requests:
            return 0
    else:
        pages = load(OUT / 'pages.json', {})
    if not os.environ.get('ANTHROPIC_API_KEY'):
        print('ANTHROPIC_API_KEY is not set: nothing was sent. Add it as a repository secret.')
        return 2
    client = make_client()
    if a.cmd in ('run', 'submit'):
        ids = submit(client, requests if a.cmd == 'run' else [json.loads(x) for x in (OUT / 'requests.jsonl').read_text(encoding='utf-8').splitlines() if x])
    else:
        ids = load(OUT / 'batch.json', {}).get('ids', [])
    if a.cmd == 'submit':
        return 0
    if not wait(client, ids, a.wait_minutes):
        print('The batch has not finished yet. Run `collect` later.')
        return 0
    rep = collect(client, ids, pages, today, a.model)
    write_report(rep, len(pages))
    return 0


if __name__ == '__main__':
    sys.exit(main())
