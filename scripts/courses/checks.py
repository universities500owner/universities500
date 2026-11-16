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
    if L.not_programme_name(name):
        return 'not-a-programme-name'
    if L.not_programme_url(rec['url']) in ('programme-subpage', 'course-unit-page'):
        return L.not_programme_url(rec['url'])
    if rec.get('level') not in ('Bachelor', 'Master'):
        return 'bad-level'
    level, _deg, _fl, out = L.classify_title(f"{rec.get('degree') or ''} {name}")
    if out and out not in ('no-title', 'no-degree-designation'):
        return out
    if (rec.get('studyMode') or {}).get('verdict') != 'full-time on campus':
        return 'not-full-time-on-campus'
    intl = rec.get('international') or {}
    if intl.get('how') not in ('fee', 'cricos', 'page', 'university'):
        return 'no-international-evidence'
    ev = intl.get('evidence') or ''
    if intl['how'] == 'page' and (not L.INTL_APPLY.search(ev) or L.INTL_PAGE_BAD.search(ev)):
        return 'weak-international-evidence'        # saved before English-test and visa sentences stopped counting
    if intl['how'] == 'fee' and not re.search(r'\d{3}', ev):
        return 'weak-international-evidence'
    if intl['how'] == 'university' and not L.hub_check([ev.split(': ', 1)[-1]], 'https://x/international/', '')[0]:
        return 'weak-international-evidence'
    if L.MIXED_MODE.search((rec.get('studyMode') or {}).get('evidence') or ''):
        return 'mixed-delivery'
    dur = rec.get('duration')
    if dur:
        y = dur.get('years') or 0
        lo, hi = (2.5, 6.5) if rec['level'] == 'Bachelor' else (0.5, 3.5)
        if not lo <= y <= hi:
            return 'duration-out-of-range'
    fee = rec.get('fee')
    if fee and not re.search(r'\d', fee.get('display', '')):
        return 'fee-without-number'
    if fee and re.search(r'\btotal\b', fee.get('context', ''), re.I):
        rec['fee'] = None          # a total for the whole course was shown as a yearly fee: drop the fee, keep the course
    return ''
