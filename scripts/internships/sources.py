"""Readers for each place we get postings from. Each returns (status, rows):
status is 'ok', 'missing' (the board does not exist), 'blocked' (robots.txt says no) or 'error'.
A row is {title, locations: [text or (city, country)], url, posted, structured}.
Only public, documented feeds. Nothing is scraped from a web page."""
import json
import re
import urllib.parse

import places as P
from titles import structured_intern

BASES = {
    'greenhouse': 'https://boards-api.greenhouse.io',
    'lever': 'https://api.lever.co',
    'ashby': 'https://api.ashbyhq.com',
    'smartrecruiters': 'https://api.smartrecruiters.com',
    'workable': 'https://apply.workable.com',
    'jobtech': 'https://jobsearch.api.jobtechdev.se',
    'arbeitnow': 'https://www.arbeitnow.com',
}
JSON = 'application/json'


def _get_json(fx, url):
    res = fx.get(url, accept=JSON)
    if res.robots_blocked:
        return 'blocked', None
    if res.status in (404, 410):
        return 'missing', None
    if not res.ok:
        return 'error', None
    try:
        return 'ok', json.loads(res.text)
    except ValueError:
        return 'error', None


def _date(v):
    """ISO date (YYYY-MM-DD) from a string or epoch milliseconds/seconds, or ''."""
    if v in (None, ''):
        return ''
    if isinstance(v, (int, float)):
        import datetime
        sec = v / 1000 if v > 10_000_000_000 else v
        try:
            return datetime.datetime.fromtimestamp(sec, datetime.timezone.utc).date().isoformat()
        except (OverflowError, OSError, ValueError):
            return ''
    s = str(v)
    return s[:10] if len(s) >= 10 and s[4] == '-' and s[7] == '-' else ''


_INTERVAL = (('hour', 'hour'), ('day', 'day'), ('week', 'week'), ('month', 'month'), ('year', 'year'), ('annual', 'year'))


def interval_of(text):
    """'per-hour-wage' -> 'hour'. '' when the feed does not say (we never guess)."""
    t = str(text or '').lower()
    if re.search(r'bi-?week|fortnight|semi-?month', t):
        return ''
    for key, name in _INTERVAL:
        if key in t:
            return name
    return ''


def _amount(v, per):
    v = float(v)
    if per in ('year', '') and v >= 10000:  # 62500 -> 62.5k, 60000 -> 60k
        k = round(v / 1000, 1)
        return f"{int(k) if k == int(k) else k}k"
    if v == int(v):
        return f"{int(v):,}"
    return f"{v:,.2f}"


def fmt_pay(currency, lo, hi, per=''):
    """Pay exactly as the feed states it: 'USD 45-55 / hour'. Nothing is converted, estimated or guessed."""
    try:
        lo = float(lo) if lo not in (None, '') else None
        hi = float(hi) if hi not in (None, '') else None
    except (TypeError, ValueError):
        return ''
    if not lo and not hi:
        return ''
    lo, hi = lo or hi, hi or lo
    if lo > hi:
        lo, hi = hi, lo
    cur = str(currency or '').strip().upper()[:3]
    amt = _amount(lo, per) if lo == hi else f"{_amount(lo, per)}\u2013{_amount(hi, per)}"
    return ' '.join(x for x in (cur, amt) if x) + (f" / {per}" if per else '')


MODES = {'onsite': 'On-site', 'on-site': 'On-site', 'hybrid': 'Hybrid', 'remote': 'Remote'}


def greenhouse(fx, slug):
    st, d = _get_json(fx, f"{BASES['greenhouse']}/v1/boards/{urllib.parse.quote(slug)}/jobs")
    if st != 'ok':
        return st, []
    rows = []
    for j in (d.get('jobs') if isinstance(d, dict) else None) or []:
        loc = (j.get('location') or {}).get('name') if isinstance(j.get('location'), dict) else j.get('location')
        rows.append({'title': j.get('title'), 'locations': [loc] if loc else [], 'url': j.get('absolute_url'),
                     'posted': _date(j.get('first_published')), 'structured': False, 'ref': str(j.get('id') or '')})
    return 'ok', rows


def greenhouse_job(fx, slug, ref):
    """One Greenhouse posting's own page of data: department and, where the employer publishes it, the pay range.
    Returns (status, {'team':..., 'pay':...}). Only what the feed states."""
    st, d = _get_json(fx, f"{BASES['greenhouse']}/v1/boards/{urllib.parse.quote(slug)}/jobs/{urllib.parse.quote(str(ref))}?pay_transparency=true")
    if st != 'ok' or not isinstance(d, dict):
        return st, {}
    out = {}
    deps = [x.get('name') for x in (d.get('departments') or []) if isinstance(x, dict) and x.get('name')]
    if deps:
        out['team'] = deps[0].strip()[:60]
    rngs = [r for r in (d.get('pay_input_ranges') or []) if isinstance(r, dict) and (r.get('min_cents') or r.get('max_cents'))]
    cur = {str(r.get('currency_type') or '').upper() for r in rngs}
    if rngs and len(cur) == 1:
        per = {interval_of(f"{r.get('title') or ''} {r.get('blurb') or ''}") for r in rngs}
        per = per.pop() if len(per) == 1 else ''
        lo = min((r.get('min_cents') or r.get('max_cents')) for r in rngs) / 100
        hi = max((r.get('max_cents') or r.get('min_cents')) for r in rngs) / 100
        pay = fmt_pay(cur.pop(), lo, hi, per)
        if pay:
            out['pay'] = pay
    return 'ok', out


def lever(fx, slug):
    rows, skip, page = [], 0, 100
    while True:
        st, d = _get_json(fx, f"{BASES['lever']}/v0/postings/{urllib.parse.quote(slug)}?mode=json&limit={page}&skip={skip}")
        if st != 'ok':
            return (st if skip == 0 else 'error'), ([] if skip == 0 else rows)
        if not isinstance(d, list):
            return 'error', rows
        for j in d:
            cat = j.get('categories') or {}
            locs = cat.get('allLocations') or ([cat['location']] if cat.get('location') else [])
            sr = j.get('salaryRange') if isinstance(j.get('salaryRange'), dict) else {}
            rows.append({'title': j.get('text'), 'locations': locs, 'url': j.get('hostedUrl'),
                         'posted': _date(j.get('createdAt')), 'structured': structured_intern(cat.get('commitment')),
                         'team': (cat.get('team') or cat.get('department') or '').strip()[:60],
                         'mode': MODES.get(str(j.get('workplaceType') or '').lower(), ''),
                         'pay': fmt_pay(sr.get('currency'), sr.get('min'), sr.get('max'), interval_of(sr.get('interval')))})
        if len(d) < page or skip >= 2000:
            return 'ok', rows
        skip += page


def ashby(fx, slug):
    st, d = _get_json(fx, f"{BASES['ashby']}/posting-api/job-board/{urllib.parse.quote(slug)}")
    if st != 'ok':
        return st, []
    rows = []
    for j in (d.get('jobs') if isinstance(d, dict) else None) or []:
        if j.get('isListed') is False:
            continue
        locs = [j.get('location')] if j.get('location') else []
        locs += [s.get('location') for s in (j.get('secondaryLocations') or []) if isinstance(s, dict) and s.get('location')]
        rows.append({'title': j.get('title'), 'locations': locs, 'url': j.get('jobUrl') or j.get('applyUrl'),
                     'posted': _date(j.get('publishedAt')), 'structured': structured_intern(j.get('employmentType'))})
    return 'ok', rows


def smartrecruiters(fx, slug):
    rows, offset, page = [], 0, 100
    while True:
        url = f"{BASES['smartrecruiters']}/v1/companies/{urllib.parse.quote(slug)}/postings?limit={page}&offset={offset}&q=intern"
        st, d = _get_json(fx, url)
        if st != 'ok':
            return (st if offset == 0 else 'error'), ([] if offset == 0 else rows)
        content = (d.get('content') if isinstance(d, dict) else None) or []
        for j in content:
            loc = j.get('location') or {}
            country = P.from_iso2(loc.get('country'))
            city = (loc.get('city') or '').strip()
            if loc.get('remote') and not city:
                locs = []
            elif country:
                locs = [(city or None, country)]
            else:
                locs = [', '.join(x for x in (city, loc.get('region'), loc.get('country')) if x)]
            cid = (j.get('company') or {}).get('identifier') or slug
            exp = j.get('experienceLevel') or {}
            rows.append({'title': j.get('name'), 'locations': locs, 'url': f"https://jobs.smartrecruiters.com/{cid}/{j.get('id')}",
                         'posted': _date(j.get('releasedDate')),
                         'structured': structured_intern(exp) or structured_intern(j.get('typeOfEmployment'))})
        total = (d.get('totalFound') if isinstance(d, dict) else 0) or 0
        offset += page
        if not content or offset >= total or offset >= 1000:
            return 'ok', rows


def workable(fx, slug):
    st, d = _get_json(fx, f"{BASES['workable']}/api/v1/widget/accounts/{urllib.parse.quote(slug)}")
    if st != 'ok':
        return st, []
    rows = []
    for j in (d.get('jobs') if isinstance(d, dict) else None) or []:
        loc = ', '.join(x for x in (j.get('city'), j.get('state'), j.get('country')) if x)
        rows.append({'title': j.get('title'), 'locations': [loc] if loc else [], 'url': j.get('url') or j.get('shortlink') or j.get('application_url'),
                     'posted': _date(j.get('published_on') or j.get('created_at')), 'structured': structured_intern(j.get('employment_type')),
                     'team': str(j.get('department') or '').strip()[:60], 'mode': 'Remote' if j.get('telecommuting') is True else ''})
    return 'ok', rows


ATS = {'greenhouse': greenhouse, 'lever': lever, 'ashby': ashby, 'smartrecruiters': smartrecruiters, 'workable': workable}


def jobtech(fx, terms=('praktik', 'praktikant', 'internship', 'intern')):
    """Sweden's public employment service (Platsbanken), open data, CC0. Returns one row per distinct ad."""
    seen, rows, any_ok = set(), [], False
    for term in terms:
        offset = 0
        while offset <= 1900:
            st, d = _get_json(fx, f"{BASES['jobtech']}/search?q={urllib.parse.quote(term)}&limit=100&offset={offset}")
            if st != 'ok':
                break
            any_ok = True
            hits = (d.get('hits') if isinstance(d, dict) else None) or []
            for h in hits:
                if h.get('id') in seen:
                    continue
                seen.add(h.get('id'))
                wa = h.get('workplace_address') or {}
                city = wa.get('municipality') or wa.get('city') or None
                rows.append({'title': h.get('headline'), 'org': (h.get('employer') or {}).get('name'),
                             'locations': [(city, 'sweden')] if wa.get('country') in (None, '', 'Sverige', 'Sweden') else [],
                             'url': h.get('webpage_url'), 'posted': _date(h.get('publication_date')), 'structured': False,
                             'deadline': _date(h.get('application_deadline'))})
            if len(hits) < 100:
                break
            offset += 100
    return ('ok' if any_ok else 'error'), rows


def arbeitnow(fx, max_pages=40):
    """Arbeitnow's free job board API (Germany and Europe). It asks for a link back, which the site gives."""
    rows, page = [], 1
    while page <= max_pages:
        st, d = _get_json(fx, f"{BASES['arbeitnow']}/api/job-board-api?page={page}")
        if st != 'ok':
            return ('ok' if page > 1 else st), rows
        data = (d.get('data') if isinstance(d, dict) else None) or []
        if not data:
            break
        for j in data:
            types = j.get('job_types') or []
            struct = any('intern' in str(t).lower() or 'praktik' in str(t).lower() for t in types)
            rows.append({'title': j.get('title'), 'org': j.get('company_name'), 'locations': [j.get('location')] if j.get('location') else [],
                         'url': j.get('url'), 'posted': _date(j.get('created_at')), 'structured': struct,
                         'team': str((j.get('tags') or [''])[0] or '').strip()[:60], 'mode': 'Remote' if j.get('remote') is True else ''})
        if not ((d.get('links') or {}).get('next')):
            break
        page += 1
    return 'ok', rows
