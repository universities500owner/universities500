"""Checks on a saved course record. Records saved before a rule existed are checked again on every run,
so an old mistake does not linger. Returns a short reason when a record should not be kept."""
import re

import levels as L

SKIP_NAME = re.compile(r"^(?:courses?|programmes?|programs?|undergraduate|postgraduate|search|all courses|find a course|home|study)\b", re.I)


def problem(rec):
    if not rec.get('url', '').startswith(('http://', 'https://')):
        return 'no-source-url'
    if not rec.get('lastVerified'):
        return 'no-verified-date'
    name = rec.get('name') or ''
    if not (3 <= len(name) <= 160) or SKIP_NAME.match(name):
        return 'bad-name'
    if rec.get('level') not in ('Bachelor', 'Master'):
        return 'bad-level'
    level, _deg, _fl, out = L.classify_title(f"{rec.get('degree') or ''} {name}")
    if out and out not in ('no-title', 'no-degree-designation'):
        return out
    if (rec.get('studyMode') or {}).get('verdict') != 'full-time on campus':
        return 'not-full-time-on-campus'
    if (rec.get('international') or {}).get('how') not in ('fee', 'cricos', 'page', 'university'):
        return 'no-international-evidence'
    dur = rec.get('duration')
    if dur:
        y = dur.get('years') or 0
        lo, hi = (2.5, 6.5) if rec['level'] == 'Bachelor' else (0.5, 3.5)
        if not lo <= y <= hi:
            return 'duration-out-of-range'
    fee = rec.get('fee')
    if fee and not re.search(r'\d', fee.get('display', '')):
        return 'fee-without-number'
    return ''
