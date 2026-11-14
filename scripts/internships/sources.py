"""Readers for each place we get postings from. Each returns (status, rows):
status is 'ok', 'missing' (the board does not exist), 'blocked' (robots.txt says no) or 'error'.
A row is {title, locations: [text or (city, country)], url, posted, structured}.
Only public, documented feeds. Nothing is scraped from a web page."""
import json
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


def greenhouse(fx, slug):
    st, d = _get_json(fx, f"{BASES['greenhouse']}/v1/boards/{urllib.parse.quote(slug)}/jobs")
    if st != 'ok':
        return st, []
    rows = []
    for j in (d.get('jobs') if isinstance(d, dict) else None) or []:
        loc = (j.get('location') or {}).get('name') if isinstance(j.get('location'), dict) else j.get('location')
        rows.append({'title': j.get('title'), 'locations': [loc] if loc else [], 'url': j.get('absolute_url'),
                     'posted': _date(j.get('first_published')), 'structured': False})
    return 'ok', rows


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
            rows.append({'title': j.get('text'), 'locations': locs, 'url': j.get('hostedUrl'),
                         'posted': _date(j.get('createdAt')), 'structured': structured_intern(cat.get('commitment'))})
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
                     'posted': _date(j.get('published_on') or j.get('created_at')), 'structured': structured_intern(j.get('employment_type'))})
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
                             'url': h.get('webpage_url'), 'posted': _date(h.get('publication_date')), 'structured': False})
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
                         'url': j.get('url'), 'posted': _date(j.get('created_at')), 'structured': struct})
        if not ((d.get('links') or {}).get('next')):
            break
        page += 1
    return 'ok', rows
