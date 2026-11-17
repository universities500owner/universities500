"""Quality gate for scholarship records.

A record is kept only if its name looks like the name of one scholarship, and the
page it came from is about students coming in to study a Bachelor's or Master's.
Everything here is plain pattern matching. When a rule is unsure, the record is
left out: a missing scholarship costs a student a click, a wrong one costs trust.

Run on its own to clean a data file that was written before these rules existed:
    python3 scripts/scholarships/quality.py src/data/scholarships.json
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

NAME_WORDS = re.compile(r'\b(?:scholar(?:ship)?s?|bursar(?:y|ies)|fellowships?|awards?|grants?|waivers?|studentships?|stipends?|exhibitions?)\b', re.I)

# Words that only describe a kind of page. A name made of nothing else ("Fees and scholarships",
# "Find a scholarship", "All programs") is a heading, not one scholarship.
GENERIC = set('''
international intl student students undergraduate undergraduates postgraduate graduate masters master master's master’s
bachelor bachelors bachelor's bachelor’s scholarship scholarships scholar bursary bursaries award awards grant grants
funding fund funds fees fee tuition costs cost and or for to of the a an in on at with study studying abroad applying apply
find finance financial aid support eligibility policy general external prestigious available other incoming new first year
years entrance admission program programs programme programmes opportunities information overseas global english our your
how what about all prior current future specific details detail overview page information info summary search results list listing view home
'''.split())

REASONS = [
    ('value-or-date-not-name', re.compile(r'^(?:up to\s+)?[£$€¥]|[£$€]\s?\d{1,3}(?:,\d{3})|^(?!20\d\d\s+[A-Za-z])\d')),   # "2027 Global Scholarship" is a name
    ('news-or-notice', re.compile(
        r'\b(?:launch(?:es|ed)?|announc\w+|celebrat\w+|call for|appel|to host|to fund|provide stipends|frequently asked|faqs?|'
        r'terms and conditions|friends,? food|workshop|webinar|symposium|conference|festival|welcome)\b', re.I)),
    ('wrong-level', re.compile(
        r'\b(?:ph\.?d|doctoral|doctorate|post-?doctoral|postdoc\w*|studentships?|staff|faculty fellowship|visiting fellowship|'
        r'research (?:scholarships?|students?|degree|training|fellowships?)|higher degree by research|hdr)\b', re.I)),
    ('for-people-already-enrolled', re.compile(r'\b(?:student leadership|completion|in-course|continuing students?)\b', re.I)),
    ('home-students-only', re.compile(r'\b(?:home|domestic|access)\b', re.I)),
    ('page-heading', re.compile(
        r'\b(?:opportunities|finder|directory|financial aid|beyond)\b|tuition fees?\b|'
        r'\bfees,? (?:and|&) scholarships?\b|\bscholarships?,? (?:and|&) (?:funding|bursaries|fees|awards|financial)\b', re.I)),
    ('outbound-or-exchange', re.compile(
        r'\b(?:travel(?:l?ing)?|exchanges?|mobility|study abroad|field trip|outbound|outgoing|internship|new colombo plan|ncp|'
        r'overseas\s+(?:scholarships?|study|research|training|travel|field|professional)|(?:yale|harvard)\b)', re.I)),
    ('prize-not-scholarship', re.compile(r'\b(?:prizes?|medals?|competitions?|3mt|essay)\b', re.I)),
]
# URL parts that mean the page is for students already enrolled, or going abroad from here.
PATH = re.compile(r'/(?:domestic|dom|outgoing|outbound|study-overseas|study-abroad|go-abroad|exchange[\w-]*|prizes?|studentships?)(?:/|\.|$)', re.I)

_EXCLUDE = None


def _exclusions():
    global _EXCLUDE
    if _EXCLUDE is None:
        p = ROOT / 'data' / 'scholarship_exclude.json'
        _EXCLUDE = json.loads(p.read_text(encoding='utf-8')).get('urlPrefixes', []) if p.exists() else []
    return _EXCLUDE


PAGE_WORDS = set('details detail overview page information info summary search results list listing view home'.split())
ONE_AWARD = re.compile(r'\b(?:scholarship|bursary|award|grant|fellowship|waiver|studentship)\b', re.I)   # singular: one award, not a page of them


def is_generic(name):
    """True for a heading made only of page-describing words ("International scholarships", "Scholarship details").
    A year plus a singular noun ("2026 International Masters Scholarship") is one named award of that year, not a heading."""
    n = (name or '').strip()
    toks = re.findall(r"[a-zà-ÿ'’]+", n.lower())
    if not toks or not all(t in GENERIC for t in toks):
        return False
    if re.search(r'\b20\d\d\b', n) and ONE_AWARD.search(n) and not any(t in PAGE_WORDS for t in toks):
        return False
    return True


def name_problem(name, today=None):
    """Why this text is not a scholarship name, or None."""
    n = (name or '').strip()
    if not NAME_WORDS.search(n):
        return 'no-scholarship-word'
    for code, rx in REASONS:
        if rx.search(n):
            return code
    if is_generic(n):
        return 'generic-heading'
    year = int((today or date.today().isoformat())[:4])
    years = [int(y) for y in re.findall(r'\b(20\d\d)\b', n)]
    if years and max(years) < year:
        return 'old-year'
    return None


def url_problem(*urls):
    for u in urls:
        if not u:
            continue
        if PATH.search(re.sub(r'^https?://[^/]+', '', u)):
            return 'page-for-enrolled-or-outbound'
        for ex in _exclusions():
            if u.startswith(ex['prefix']):
                return 'excluded-by-review'
    return None


def problem(rec, today=None):
    if rec.get('origin') == 'official':
        return None
    why = name_problem(rec.get('name'), today)
    if why == 'generic-heading' and rec.get('origin') == 'studyaustralia':
        why = None   # a title on Study Australia's list is a name, not a page heading
    return why or url_problem(rec.get('url'), rec.get('sourcePage'))


def clean_file(path, today=None, write=True):
    p = Path(path)
    doc = json.loads(p.read_text(encoding='utf-8'))
    keep, dropped = [], []
    for it in doc['items']:
        why = problem(it, today)
        (dropped if why else keep).append((it, why))
    if write:
        doc['items'] = [i for i, _ in keep]
        doc['stats']['items'] = len(doc['items'])
        for slug, u in doc.get('universities', {}).items():
            u['count'] = sum(1 for i in doc['items'] if i.get('providerSlug') == slug)
        p.write_text(json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    return [i for i, _ in keep], dropped


if __name__ == '__main__':
    kept, dropped = clean_file(sys.argv[1], write='--dry' not in sys.argv)
    from collections import Counter
    print(f'kept {len(kept)}, removed {len(dropped)}')
    for k, v in Counter(w for _, w in dropped).most_common():
        print(f'  {k}: {v}')
