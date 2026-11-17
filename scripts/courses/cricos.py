#!/usr/bin/env python3
"""The Australian government register of courses open to international students (CRICOS).

Source: Commonwealth Register of Institutions and Courses for Overseas Students, Australian Government Department of Education,
licensed Creative Commons Attribution 2.5 Australia (https://data.gov.au/data/dataset/cricos). The licence needs a credit wherever
the data is shown; the course page carries it.

What the register gives us for each course: a code, the official level, length in weeks, the tuition fee for the WHOLE course, the
field of education, and the campuses. It does not give a web address, start months or English scores, so it never replaces the
university's own page. This file is used for three things, and nothing else:

  1. Checking and naming the code: a page whose programme name matches one registered course (and only one) at that university
     is registered for international students. The reader accepts it as "open to international students" (how: "cricos").
  2. Adding the official length, campuses and field to a course the reader already found.
  3. Showing the registered tuition on the course page as an OLDER, whole-course figure. It is never put in the fee field, on a
     card or in the fee filter: the register's fees are often behind what a university charges now (Flinders' Bachelor of Accounting
     is AU$105,700 over 156 weeks in the register, about AU$35,200 a year, against AU$40,900 a year in Flinders' own 2027 schedule).

    python3 scripts/courses/cricos.py build --csv-dir <folder with the four CRICOS CSV files> [--out data/cricos]

The four files are CRICOS_Institutions.csv, CRICOS_Courses.csv, CRICOS_Locations.csv and CRICOS_Course_Locations.csv from
the dataset page. Nothing is invented: every value is a column of the register. A fee of zero or blank is "not published".
"""
import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DIR = ROOT / 'data/cricos'

# Bachelor's and Master's only. Doctorates, research Master's, diplomas, certificates, Non-AQF awards and school levels are left out.
LEVELS = {
    'Bachelor Degree': 'Bachelor',
    'Bachelor Honours Degree': 'Bachelor',
    'Masters Degree (Coursework)': 'Master',
    'Masters Degree (Extended)': 'Master',
}
# titles the site does not list: a professional "Doctor of ..." (registered as an Extended Master's), a diploma or certificate bundled into a degree
DOCTOR_TITLE = re.compile(r'\bDoctor\b', re.I)
BUNDLED = re.compile(r'\b(?:diploma|certificate)\b', re.I)
DEGREE_WORD = re.compile(r'\b(?:Bachelor|Master|MBA)\b', re.I)
BACHELOR_WORD = re.compile(r'\bBachelor\b', re.I)
MASTER_WORD = re.compile(r'\bMaster\b', re.I)


def read_csv(path):
    with open(path, encoding='utf-8-sig', newline='') as fh:
        return list(csv.DictReader(fh))


def money(text):
    """'$105,700.00' -> 105700. Zero or blank is "not published" (None)."""
    t = re.sub(r'[^0-9.]', '', text or '')
    if not t:
        return None
    v = float(t)
    return int(round(v)) if v > 0 else None


def whole(text):
    t = re.sub(r'[^0-9]', '', text or '')
    return int(t) if t else None


def name_key(text):
    """A course name reduced to letters and digits so '&' and 'and', commas and spacing do not matter."""
    t = (text or '').lower().replace('&', ' and ')
    t = re.sub(r'[^a-z0-9()]+', ' ', t)
    return re.sub(r'\s+', ' ', t).strip()


def why_left_out(row):
    """'' when the register row is a Bachelor's or Master's the site can list, else a short reason."""
    if row.get('Expired', '').strip().lower() == 'yes':
        return 'expired'
    if row.get('Course Level') not in LEVELS:
        return 'level'
    name = row.get('Course Name', '')
    if row['Course Level'] == 'Masters Degree (Extended)' and DOCTOR_TITLE.search(name):
        return 'doctor-titled'
    if BUNDLED.search(name):
        return 'diploma-or-certificate-in-name'
    if not DEGREE_WORD.search(name):
        return 'not-a-named-degree'
    return ''


def titlecase_city(city):
    c = (city or '').strip()
    return c.title() if c.isupper() else c


def build(csv_dir, providers, today=''):
    """Return ({slug: document}, stats). `providers` maps a site slug to its CRICOS provider codes."""
    csv_dir = Path(csv_dir)
    courses = read_csv(csv_dir / 'CRICOS_Courses.csv')
    locs = defaultdict(list)
    for r in read_csv(csv_dir / 'CRICOS_Course_Locations.csv'):
        place = (titlecase_city(r.get('Location City')), (r.get('Location State') or '').strip())
        if place[0] and place not in locs[(r['CRICOS Provider Code'], r['CRICOS Course Code'])]:
            locs[(r['CRICOS Provider Code'], r['CRICOS Course Code'])].append(place)
    owner = {code: slug for slug, codes in providers.items() for code in codes}
    docs = {slug: {'slug': slug, 'providers': list(codes), 'courses': []} for slug, codes in providers.items()}
    stats = {'rows': 0, 'kept': 0, 'left_out': defaultdict(int)}
    for row in courses:
        slug = owner.get(row.get('CRICOS Provider Code'))
        if not slug:
            continue
        stats['rows'] += 1
        why = why_left_out(row)
        if why:
            stats['left_out'][why] += 1
            continue
        name = re.sub(r'\s+', ' ', row['Course Name']).strip()
        field = re.sub(r'^\d+\s*-\s*', '', row.get('Field of Education 1 Broad Field', '')).strip()
        rec = {
            'code': row['CRICOS Course Code'].strip().upper(),
            'name': name,
            'level': LEVELS[row['Course Level']],
            'weeks': whole(row.get('Duration (Weeks)')),
            'tuition': money(row.get('Tuition Fee')),
            'nonTuition': money(row.get('Non Tuition Fee')),
            'field': field or None,
            'places': [list(p) for p in locs.get((row['CRICOS Provider Code'], row['CRICOS Course Code']), [])],
        }
        if BACHELOR_WORD.search(name) and MASTER_WORD.search(name):
            rec['combined'] = True
        docs[slug]['courses'].append(rec)
        stats['kept'] += 1
    for d in docs.values():
        d['courses'].sort(key=lambda c: (c['level'], c['name'].lower(), c['code']))
    return docs, stats


def dump(doc):
    """One course per line, so a git diff shows what changed."""
    head = {k: v for k, v in doc.items() if k != 'courses'}
    lines = ['{']
    for k, v in head.items():
        lines.append(f'"{k}": {json.dumps(v, ensure_ascii=False)},')
    lines.append('"courses": [')
    lines.append(',\n'.join(json.dumps(c, ensure_ascii=False) for c in doc['courses']))
    lines.append(']')
    lines.append('}')
    return '\n'.join(lines) + '\n'


class Register:
    """The registered Bachelor's and Master's courses of one university."""

    def __init__(self, doc):
        self.slug = doc.get('slug', '')
        self.by_code = {c['code']: c for c in doc.get('courses', [])}
        self.by_name = defaultdict(set)
        for c in self.by_code.values():
            self.by_name[name_key(c['name'])].add(c['code'])

    @classmethod
    def load(cls, slug, folder=DEFAULT_DIR):
        p = Path(folder) / f'{slug}.json'
        if not p.is_file():
            return None
        try:
            return cls(json.loads(p.read_text(encoding='utf-8')))
        except (OSError, ValueError):
            return None

    def get(self, code):
        return self.by_code.get((code or '').strip().upper())

    def candidates(self, name, degree=''):
        """Ways the register may write what a page calls `name` (the degree, when the page's heading leaves it out)."""
        names = [name]
        if degree and name_key(degree) not in name_key(name):
            names += [f'{degree} {name}', f'{degree} ({name})', f'{degree} in {name}']
            if name_key(degree).endswith(' ' + name_key(name)):       # heading "Data Science", degree "Master of Data Science"
                names.append(degree)
        return names

    def match(self, name, degree=''):
        found = set()
        for n in self.candidates(name, degree):
            found |= self.by_name.get(name_key(n), set())
        return sorted(found)

    def unique(self, name, degree=''):
        """The code when exactly one registered course has this name at this university, else ''.
        Two registered courses with one name (a different campus or variant) cannot be told apart from the page: no code."""
        found = self.match(name, degree)
        return found[0] if len(found) == 1 else ''


def years_from_weeks(weeks, level):
    """Official length as the site writes it ('1.5 years'), or None when it falls outside what a Bachelor's or Master's takes."""
    if not weeks:
        return None
    y = round(weeks / 52 * 4) / 4          # quarters of a year: 78 weeks = 1.5, 156 = 3
    lo, hi = (2.5, 6.5) if level == 'Bachelor' else (0.5, 3.5)
    if not lo <= y <= hi:
        return None
    return {'display': f"{y:g} {'year' if y == 1 else 'years'}", 'years': y, 'context': f'Government register (CRICOS): {weeks} weeks'}


def site_block(c):
    """What the course page needs from a registered course."""
    return {'code': c['code'], 'weeks': c.get('weeks'), 'tuition': c.get('tuition'), 'nonTuition': c.get('nonTuition'), 'currency': 'AUD',
            'places': c.get('places') or [], 'field': c.get('field')}


def source_credit(folder=DEFAULT_DIR):
    """The credit the licence asks for, as saved with the register files."""
    try:
        return json.loads((Path(folder) / 'providers.json').read_text(encoding='utf-8')).get('source')
    except (OSError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build', help='turn the four CRICOS CSV files into data/cricos/<university>.json')
    b.add_argument('--csv-dir', required=True)
    b.add_argument('--out', default=str(DEFAULT_DIR))
    a = ap.parse_args()
    out = Path(a.out)
    prov = json.loads((out / 'providers.json').read_text(encoding='utf-8'))
    docs, stats = build(a.csv_dir, prov['providers'])
    for slug, d in docs.items():
        d['source'] = prov['source']
        (out / f'{slug}.json').write_text(dump({k: d[k] for k in ('slug', 'providers', 'source', 'courses')}), encoding='utf-8')
    print(f"{stats['rows']} register rows for {len(docs)} universities, {stats['kept']} kept")
    for k, v in sorted(stats['left_out'].items(), key=lambda kv: -kv[1]):
        print(f'  left out ({k}): {v}')
    empty = [s for s, d in docs.items() if not d['courses']]
    if empty:
        print('  no registered courses found for:', ', '.join(empty))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
