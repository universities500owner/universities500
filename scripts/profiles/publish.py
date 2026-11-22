#!/usr/bin/env python3
"""Turn the checked profiles (profiles_ai.json) into the file the site reads: src/data/university_profiles.json.

Only what the checks let through goes in:
  brief         only when its numbers are all in the sources (and not written from the Wikipedia lead alone)
  established   the university's own year, or Wikidata's when the university is silent; with the small source line
  students      the official figure with its year, or Wikidata's within five years; with the small source line
  campuses      only those the university's own page names as a campus (the sentence is checked), each with a Google Maps link and, when one passed
                the checks, a Commons photo. A city that only Wikidata gives is not a campus list; it becomes a plain "place" with a map link
  faculties     named on the university's own page (or Wikidata), three or more; a link to the faculty only when one is known
  links         admissions, programmes, scholarships, partners, faculties: only pages that were graded 'verified'
  social        the official Instagram, LinkedIn and YouTube pages (found on the university's site, or official on Wikidata)
  partners      organisations the university names itself, plus its partnerships page
  gallery       four or more photos that passed the gate; every photo carries its author, licence and Commons page

Usage: python3 scripts/profiles/publish.py --in out/profiles_ai.json --out src/data/university_profiles.json
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# names that are menu labels or headings, not a faculty
GENERIC = {'schools colleges', 'schools and colleges', 'colleges', 'schools', 'faculties', 'departments', 'academics', 'academic units', 'all faculties',
           'faculties schools', 'faculties and schools', 'faculties and departments', 'programs', 'programmes', 'courses', 'majors programs',
           'majors and programs', 'graduate programs', 'graduate programmes', 'undergraduate programs', 'interdisciplinary programs', 'research', 'study', 'about us'}
# a campus name that is really a building, a service, a hospital or a menu label
CAMPUS_NOISE = re.compile(r'\b(?:buildings?|house|hospital|library|museum|stadium|hall|water sports|bus|shuttle|alerts?|status|visits?|policy|traditions?|'
                          r'technology|initiatives?|communications?|recreation|eateries|activities|carry|days|a-z|faculty|open campus|beyond campus|around campus|extended campus)\b', re.I)
# faculty names that are not a faculty
FACULTY_NOISE = re.compile(r'librar|exploratory|continuing|research units|^institute$|faculties|space studies|centre for lifelong|summer school', re.I)
# a Wikidata place that is a region, not somewhere to put a pin
REGION_RX = re.compile(r'\b(?:county|district|region|province|state|shire|prefecture|canton|borough|territory)\b|^(?:queensland|victoria|new south wales|tasmania|western australia|south australia|ontario|quebec|alberta|british columbia|manitoba|saskatchewan)$', re.I)
MIN_FACULTIES = 3
PLANNED_RX = re.compile(r'\b(?:planned|proposed|future|coming soon|will open|will be|under construction|upcoming)\b', re.I)
LINK_ROLES = ('admissions', 'courses', 'scholarships', 'partners', 'faculties')
SOCIAL_OK = ('verified', 'wikidata-only')
MAX = {'faculties': 24, 'partners': 40, 'gallery': 8}


def plain(s):
    return re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', ' ', (s or '').lower())).strip()


def photo(p, size=None, wide=False):
    """The fields a page needs to show a Commons photo and credit it."""
    url = (p.get('thumb') or '').split('?')[0]
    if size:
        url = re.sub(r'/\d+px-', f'/{size}px-', url)
    w = size or p.get('thumbWidth') or 960
    h = round(w * p['height'] / p['width']) if p.get('width') and p.get('height') else None          # the page reserves the space, so nothing jumps while it loads
    out = {'u': url, 'w': w, 'h': h, 'by': (p.get('author') or '')[:80], 'lic': p.get('licence') or '', 'licUrl': p.get('licenceUrl') or '',
           'page': p.get('page') or '', 'y': p.get('year') or None}
    if wide and p.get('width') and p['width'] >= 1280 and p.get('height'):
        out['u2'] = re.sub(r'/\d+px-', '/1280px-', url)                       # a 1280px copy for the big header and the gallery slider
        out['o'] = p['width']
    return out


def one(r):
    pub = r.get('publish') or {}
    out = {'name': r['name'], 'generated': r.get('generated') or ''}
    br = r.get('brief') or {}
    if pub.get('brief') and br.get('text'):
        out['brief'] = br['text']
    fo = r.get('founded') or {}
    if pub.get('founded') and fo.get('v'):
        out['established'] = {'v': fo['v'], 'note': (f"Present form {fo['present_form']['v']}" if fo.get('present_form') else ''), 'source': fo.get('source_text') or '', 'src': fo.get('src') or ''}
    st = r.get('students') or {}
    if pub.get('students') and st.get('v'):
        out['students'] = {'v': st['v'], 'asof': st.get('asof'), 'source': st.get('source_text') or '', 'src': st.get('src') or ''}

    camps = []
    for c in r.get('campuses') or []:
        # only a campus the university's own page names (the sentence was checked); Wikidata gives where the university is, not its campuses
        if c.get('from') != 'university page' or not c.get('maps') or PLANNED_RX.search(c.get('quote') or ''):
            continue
        if CAMPUS_NOISE.search(c['name']) and not re.search(r'\bcampus\b', c['name'], re.I):
            continue
        if re.search(r'\b(?:buildings?|faculty|hospital|library)\b', c['name'], re.I):
            continue
        camps.append({'name': c['name'], 'maps': c['maps'], 'photo': photo(c['photo'], 500) if c.get('photo') else None})
    if camps:
        out['campuses'] = camps
    else:
        wd = [c for c in r.get('campuses') or [] if c.get('from') == 'wikidata' and c.get('name') and not REGION_RX.search(c['name'])]
        if wd:
            out['place'] = {'name': wd[0]['name'], 'maps': 'https://www.google.com/maps/search/?api=1&query=' + re.sub(r'%20|\s+', '+', r['name'])}

    fac, seen = [], set()
    for f in r.get('faculties') or []:
        n = (f.get('name') or '').strip()
        if not n or len(n) > 70 or plain(n) in GENERIC or plain(n) in seen or re.search(r'\b(?:programs?|programmes|majors)\b$', plain(n)) or FACULTY_NOISE.search(n):
            continue
        if plain(n).startswith(plain(r['name'])) and not re.search(r'\b(?:faculty|school|college|institute|department)\b', plain(n)):
            continue                                                                                # 'University of Toronto Scarborough' is a campus, not a faculty
        seen.add(plain(n))
        fac.append({'name': n, 'url': f.get('url') or ''})
    if len(fac) >= MIN_FACULTIES:                                                                   # one or two entries would read as the whole list
        out['faculties'] = fac[:MAX['faculties']]

    links = {}
    for role in LINK_ROLES:
        l = (r.get('links') or {}).get(role) or {}
        if l.get('grade') == 'verified' and (l.get('final') or l.get('url')):
            links[role] = l.get('final') or l['url']
    if links:
        out['links'] = links

    soc = {k: v['url'] for k, v in (r.get('social') or {}).items() if v and v.get('status') in SOCIAL_OK and v.get('url')}
    if soc:
        out['social'] = soc

    pn = [x['name'] for x in (r.get('partners') or {}).get('names') or []]
    if pn:
        out['partners'] = pn[:MAX['partners']]

    if pub.get('gallery'):
        out['gallery'] = [photo(p, wide=True) for p in ((r.get('gallery') or {}).get('photos') or [])[:MAX['gallery']]]
    return out


def build(recs):
    return {r['slug']: one(r) for r in recs}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--in', dest='inp', default='out/profiles_ai.json')
    ap.add_argument('--out', default=str(HERE.parent.parent / 'src' / 'data' / 'university_profiles.json'))
    a = ap.parse_args()
    recs = json.loads(Path(a.inp).read_text(encoding='utf-8'))
    data = build(recs)
    Path(a.out).write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    n = len(data)
    count = lambda k: sum(1 for v in data.values() if v.get(k))  # noqa: E731
    print(f'{n} profiles written to {a.out}', file=sys.stderr)
    for k in ('brief', 'established', 'students', 'campuses', 'faculties', 'links', 'social', 'partners', 'gallery'):
        print(f'  {k}: {count(k)} of {n}', file=sys.stderr)


if __name__ == '__main__':
    main()
