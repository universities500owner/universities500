"""Open data feeds behind a university's own scholarship finder.

Why this exists: some finders are built with scripts, so the page itself holds no list. Behind the finder sits a
plain data file that the page loads. Where that file is public and the university's robots.txt allows it, reading
it is the same as reading a list page: we take only the addresses of the scholarship pages. The usual reader then
opens each of those pages and applies the usual rules (international students, undergraduate or master's level,
a real scholarship name, no prizes). Nothing in the feed is shown on the site without that page check.

Rules this file follows:
  - same polite fetcher as everything else: identified bot, robots.txt, 3 s between requests
  - one request for the feed, no guessing of other addresses
  - if the feed is missing or changes shape, nothing is returned and the normal reader carries on without it

Feeds read today:
  - UCL: https://www.ucl.ac.uk/scholarships/scholarships-finder loads its list from
    https://www.ucl.ac.uk/digital-presence-services/scholarships/www/scholarships.json.php?year=YYYY
    (robots.txt allowed it on 17 Nov 2026). Each entry says whether it is open to overseas students (os_status),
    to undergraduates (ug), taught postgraduates (pgt) or research students (pgr), and gives the scholarship page.
"""
import json
import os
import re

UCL_FEED = os.environ.get('UCL_FEED_BASE', 'https://www.ucl.ac.uk') + '/digital-presence-services/scholarships/www/scholarships.json.php'
UCL_SHARED = 'https://www.ucl.ac.uk/scholarships/fee-partnerships'  # one page shared by many partner schemes: not a scholarship page


def parse_ucl(text):
    """The feed is a script line `var schol_json_current = [ ... ];`. Returns the list of entries, or [] when the shape differs."""
    i = text.find('=')
    j = text.find('[', i if i >= 0 else 0)
    if j < 0:
        return []
    try:
        data, _ = json.JSONDecoder().raw_decode(text, j)
    except ValueError:
        return []
    return [e for e in data if isinstance(e, dict)] if isinstance(data, list) else []


def ucl_pages(entries):
    """Addresses of scholarship pages open to overseas students at bachelor's or taught-master's level, for prospective students.
    Returns (urls, counts)."""
    counts = {'entries': len(entries), 'overseas': 0, 'level': 0, 'shared': 0, 'kept': 0}
    urls, seen = [], set()
    for e in entries:
        if e.get('os_status') != 'Y':
            continue
        counts['overseas'] += 1
        if e.get('prospective') == 'N' or not (e.get('ug') == 'Y' or e.get('pgt') == 'Y'):
            continue
        counts['level'] += 1
        u = re.sub(r'\s+', '', str(e.get('scholURL') or ''))
        if not u.startswith('https://www.ucl.ac.uk/'):
            continue
        if u.rstrip('/') == UCL_SHARED:
            counts['shared'] += 1
            continue
        if u in seen:
            continue
        seen.add(u)
        urls.append(u)
    counts['kept'] = len(urls)
    return urls, counts


def ucl(fx, today):
    """Returns (urls, report). Tries next year's feed first (the finder shows the coming intake), then this year's."""
    report = {'feed': 'ucl', 'ok': False}
    this_year = int(str(today)[:4])
    for year in (this_year + 1, this_year):
        res = fx.get(f'{UCL_FEED}?year={year}')
        if res.robots_blocked:
            report['note'] = 'robots.txt does not allow the feed'
            return [], report
        if not res.ok:
            report['note'] = res.error or f'HTTP {res.status}'
            continue
        entries = parse_ucl(res.text)
        if not entries:
            report['note'] = f'no entries in the {year} feed'
            continue
        urls, counts = ucl_pages(entries)
        report.update(counts, ok=True, year=year)
        return urls, report
    return [], report


FEEDS = {'ucl': ucl}


def pages_for(uni, fx, today):
    """Extra scholarship pages for a university from its finder's feed. Never raises: a broken feed must not stop a run."""
    fn = FEEDS.get(uni['slug'])
    if not fn:
        return [], None
    try:
        return fn(fx, today)
    except Exception as e:
        return [], {'feed': uni['slug'], 'ok': False, 'note': f'{type(e).__name__}: {e}'}
