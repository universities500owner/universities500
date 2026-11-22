#!/usr/bin/env python3
"""University profile pilot: collect the facts, links, social accounts and photos for a list of universities,
keep the evidence for every value, and write a fill-rate report.

Run by the 'Profile pilot' workflow (the sandbox cannot reach these sites). Standard library plus beautifulsoup4 and lxml.

  python collect.py --out out                      # the 25 in pilot_25.json
  python collect.py --out out --only monash-university,curtin-university

A value is only marked publishable when it has a source link and passes its check. Everything else is kept, labelled,
and listed in the report for a person to look at. Nothing here writes into src/data."""
import argparse
import re
import concurrent.futures as cf
import datetime
import json
import os
import sys
import time
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / 'scripts' / 'scholarships'))

import commons as CM  # noqa: E402
import sitereader as SITE  # noqa: E402
from api import Api  # noqa: E402
from fetcher import Fetcher  # noqa: E402
import wikidata as WD  # noqa: E402

MAPS = 'https://www.google.com/maps/search/?api=1&query='


def maps_link(*parts):
    return MAPS + urllib.parse.quote_plus(' '.join(p for p in parts if p))


def agree(a, b, tol=0.15):
    return bool(a and b and abs(a - b) / max(a, b) <= tol)


YEAR_CTX = re.compile(r'(?:founded|established|formed|created|chartered|opened|since)\D{0,25}?((?:1[0-9]|20)\d\d)', re.I)


def founded_block(wd, overview):
    """Wikidata's year, checked against the year the Wikipedia lead gives. Wikidata 'inception' is sometimes the date of a merger or of
    university status, not the heritage year a university quotes, so a year the lead contradicts is sent for review."""
    f = wd.get('founded')
    if not f:
        return {'v': None, 'status': 'missing'}
    said = sorted({int(y) for y in YEAR_CTX.findall(overview or '')})
    if f['conflict']:
        status = 'conflict'
    elif not said:
        status = 'ok'
    else:
        status = 'confirmed' if f['v'] in said else 'check'
    return {'v': f['v'], 'status': status, 'all': f['all'], 'lead_years': said, 'src': wd['src']}


def students_block(wd, site):
    """The student total, the year it is 'as on', and whether the university's own site says about the same."""
    cand = [c for c in site.get('students2', []) if not c['intl']]
    w = wd.get('students')
    if w:
        second = next((c for c in cand if agree(w['v'], c['v'])), None)
        status = 'missing-year' if not w['asof'] else ('verified' if second else 'single-source')
        return {'v': w['v'], 'asof': w['asof'], 'status': status, 'src': wd['src'], 'others': [x for x in w['all'] if x['v'] != w['v']][:4],
                'second': {'v': second['v'], 'asof': second['asof'], 'snippet': second['snippet'][:200]} if second else None}
    if cand:
        top = sorted(cand, key=lambda c: (c['asof'] is None, -(c['asof'] or 0)))[0]
        return {'v': top['v'], 'asof': top['asof'], 'status': 'site-only', 'src': site['home'].get('final', ''), 'second': None,
                'candidates': [{'v': c['v'], 'asof': c['asof']} for c in cand[:5]]}
    return {'v': None, 'asof': None, 'status': 'missing', 'src': '', 'second': None}


def campuses_block(uni, site, photos):
    names = []
    for c in uni.get('campuses') or []:
        names.append({'name': c['n'], 'from': 'wikidata'})
    for c in site.get('campuses', []):
        if c['name'].lower() not in {n['name'].lower() for n in names}:
            names.append({'name': c['name'], 'from': 'site', 'url': c['url']})
    if not names:
        names = [{'name': 'Main campus', 'from': 'default'}]
    out = []
    for n in names[:6]:
        label = n['name']
        query = [uni['name']] if n['from'] == 'default' else [label if uni['name'].split()[0].lower() in label.lower() else label, uni['name']]
        out.append({'name': label, 'maps': maps_link(*query), 'from': n['from'], 'photo': photos.get(label)})
    return out


def social_block(site, wd):
    out = {}
    got = site.get('social', {})
    for kind in ('instagram', 'linkedin', 'youtube'):
        if kind in got:
            s = got[kind]
            out[kind] = {'url': s['url'], 'from': s['from'], 'agree': s['agree'], 'others': s['others'],
                         'status': 'verified' if (s['from'] in ('footer', 'jsonld') and s['agree'] is not False) or s['agree'] is True else 'check'}
        elif wd.get(kind):
            out[kind] = {'url': WD.social_url(kind, wd[kind]), 'from': 'wikidata', 'agree': None, 'others': [], 'status': 'wikidata-only'}
    return out


def faculties_block(wd_fac, site):
    merged = {}
    for f in wd_fac:
        merged[f['name'].lower()] = {'name': f['name'], 'url': f['url'], 'from': 'wikidata'}
    for f in site.get('faculties', []):
        k = f['name'].lower()
        if k in merged:
            if not merged[k]['url']:
                merged[k]['url'], merged[k]['from'] = f['url'], 'wikidata+site'
        else:
            merged[k] = {'name': f['name'], 'url': f['url'], 'from': 'site'}
    return sorted(merged.values(), key=lambda x: x['name'])[:60]


def process(uni, wd_facts, api, fetcher, today):
    """One university -> its profile record. Every step is caught so one failure never stops the run."""
    t0 = time.monotonic()
    rec = {'slug': uni['slug'], 'name': uni['name'], 'country': uni['countryName'], 'generated': today.isoformat(), 'errors': []}
    wd = wd_facts or {}

    def step(name, fn, default):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 - recorded, never silent
            rec['errors'].append(f'{name}: {type(e).__name__}: {e}'[:200])
            return default

    site = step('site', lambda: SITE.crawl(fetcher, uni.get('web') or wd.get('website') or ''), {'home': {'error': 'crawl failed'}, 'links': {}, 'social': {}, 'faculties': [], 'campuses': [], 'students2': [], 'cache': {}})
    site['social'] = SITE.socials(site.pop('social_links', []), site.pop('_same_as', []), wd)
    wd_fac = step('wikidata faculties', lambda: WD.faculties(api, uni['qid'], uni['name']), [])
    gallery, counts = step('commons gallery', lambda: CM.gallery(api, wd['commons'], today.year, want=12), ([], {})) if wd.get('commons') else ([], {'note': 'no Commons category on Wikidata'})

    # photos for campuses: one search each, at most 4 per university
    photos = {}
    for c in ((uni.get('campuses') or []) + [{'n': c['name']} for c in site.get('campuses', [])])[:4]:
        label = c['n']
        if label in photos:
            continue
        ph = step(f'campus photo {label}', lambda: CM.campus_photo(api, label, uni['name'], today.year), None)
        if ph:
            photos[label] = ph

    rec['website'] = {'url': site['home'].get('final') or uni.get('web'), 'status': site['home'].get('status'),
                      'error': site['home'].get('error', ''), 'robots': site['home'].get('robots', False)}
    rec['founded'] = founded_block(wd, uni.get('overview', ''))
    rec['students'] = students_block(wd, site)
    rec['campuses'] = campuses_block(uni, site, photos)
    rec['faculties'] = faculties_block(wd_fac, site)
    rec['links'] = {k: {kk: v.get(kk) for kk in ('url', 'final', 'grade', 'title', 'source', 'status')} for k, v in site['links'].items()}
    rec['social'] = social_block(site, wd)
    rec['gallery'] = {'photos': gallery, 'counts': counts, 'category': wd.get('commons')}
    rec['brief'] = {'text': uni.get('overview', ''), 'src': uni.get('overviewSrc', ''), 'status': 'pending-ai'}
    rec['partners'] = {'page': (site['links'].get('partners') or {}).get('url'), 'names': [], 'status': 'pending-ai'}
    rec['seconds'] = round(time.monotonic() - t0, 1)
    return rec, site.get('cache', {})


def run(args):
    unis = {u['slug']: u for u in json.load(open(ROOT / 'src/data/universities.json', encoding='utf-8'))}
    pilot = json.load(open(HERE / 'pilot_25.json', encoding='utf-8'))['universities']
    slugs = [p['slug'] for p in pilot]
    if args.only:
        wanted = [s.strip() for s in args.only.split(',') if s.strip()]
        slugs = [s for s in wanted if s in unis]
    out = Path(args.out)
    (out / 'pages').mkdir(parents=True, exist_ok=True)
    today = datetime.date.today()
    ua = f"Universities500Bot/1.0 (+https://universities500.com/bot/{'; ' + args.contact if args.contact else ''})"
    api = Api(args.contact)
    fetcher = Fetcher(ua, delay=args.delay, deadline=time.monotonic() + args.minutes * 60)

    ents = WD.entities(api, [unis[s]['qid'] for s in slugs])
    facts = {qid: WD.parse(e) for qid, e in ents.items()}
    records, started = [], time.monotonic()
    with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(process, unis[s], facts.get(unis[s]['qid']), api, fetcher, today): s for s in slugs}
        for fut in cf.as_completed(futs):
            s = futs[fut]
            try:
                rec, cache = fut.result()
            except Exception as e:  # noqa: BLE001
                rec, cache = {'slug': s, 'name': unis[s]['name'], 'country': unis[s]['countryName'], 'errors': [f'fatal: {e}'[:200]]}, {}
            records.append(rec)
            (out / 'pages' / f'{s}.json').write_text(json.dumps(cache, ensure_ascii=False), encoding='utf-8')
            print(f"[{len(records)}/{len(slugs)}] {s}  {rec.get('seconds', '?')}s  errors={len(rec['errors'])}", flush=True)
    order = {s: i for i, s in enumerate(slugs)}
    records.sort(key=lambda r: order.get(r['slug'], 999))
    (out / 'profiles.json').write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding='utf-8')
    import report
    (out / 'report.md').write_text(report.build(records, {'requests_site': fetcher.stats['requests'], 'requests_api': api.requests,
                                                         'seconds': round(time.monotonic() - started), 'robots_blocked': fetcher.robots_blocked}), encoding='utf-8')
    print(f'done: {len(records)} profiles in {round(time.monotonic() - started)}s; {fetcher.stats["requests"]} site requests, {api.requests} API requests')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='out')
    ap.add_argument('--only', default='')
    ap.add_argument('--contact', default=os.environ.get('CONTACT_EMAIL', ''))
    ap.add_argument('--delay', type=float, default=3.0)
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--minutes', type=int, default=45)
    run(ap.parse_args())


if __name__ == '__main__':
    main()
