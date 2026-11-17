"""Read one official source and return the items that pass every rule, plus a plain account of what happened (for the run report)."""
import urllib.parse
from collections import Counter
from datetime import datetime, timedelta

import extract as X  # scripts/scholarships/extract.py (path is set by the caller)
import textutil as T
import news_feeds as NF
import news_rules as R

MAX_ARTICLE_FETCHES = 4      # per source per run: only to find an official summary when the list has none
SUMMARY_MIN = 40


def _fetch(fx, url, info, accept=None):
    res = fx.get(url, accept=accept)
    entry = {'url': url, 'status': res.status}
    if res.robots_blocked:
        entry['error'] = f'blocked by robots.txt ({res.robots_reason})'
        info['robotsBlocked'] += 1
    elif res.error:
        entry['error'] = res.error
    info['tried'].append(entry)
    return res if res.ok else None


MAX_FETCHES = 12             # per source per run, before the article pages (a source may set maxFetches)
RECENT_DAYS = 21             # after the first run a source only needs its recent items: older ones are already stored


def _as_list(v):
    return [v] if isinstance(v, str) else list(v or [])


def _candidates(src, fx, info, since):
    """Items from every endpoint that gives any, in this order, de-duplicated by address:
    explicit feeds, the Federal Register, feeds the home page advertises, the listed news pages, and (only when nothing came yet)
    the news pages the home page links to."""
    acc, seen = [], set()
    FEED_ACCEPT = 'application/rss+xml,application/atom+xml,application/xml,text/xml,*/*;q=0.5'

    def take(its, via):
        new = [i for i in its if i['url'] not in seen]
        for i in new:
            seen.add(i['url'])
        if new:
            acc.extend(new)
            info['via'] = f"{info['via']}; {via}" if info['via'] else via
        return bool(new)

    def fetch(u, **kw):
        if len(info['tried']) >= int(src.get('maxFetches', MAX_FETCHES)):
            return None
        return _fetch(fx, u, info, **kw)

    def feeds_on(res, label):
        got = False
        for u in NF.discover_feeds(res.text, res.final_url)[:3]:
            r = fetch(u, accept=FEED_ACCEPT)
            if r and NF.looks_like_feed(r.body):
                got = take(NF.parse_feed(r.body, r.final_url), f'feed ({label}) {u}') or got
        return got

    def list_page(res, u):
        its = NF.parse_dated_links(res.text, res.final_url, src['urlDate']) if src.get('urlDate') else NF.parse_listing(res.text, res.final_url)
        if its:
            return take(its, f'list page {u}')
        info['profiles'].append({'url': u, **NF.profile(res.text, res.final_url)})
        return False

    for u in _as_list(src.get('feeds')):
        res = fetch(u, accept=FEED_ACCEPT)
        if res and NF.looks_like_feed(res.body):
            take(NF.parse_feed(res.body, res.final_url), f'feed {u}')
    for term in _as_list(src.get('fr')):
        res = fetch(NF.federal_register_url(term, since=since), accept='application/json')
        if res:
            its = NF.parse_federal_register(res.body)
            if its:
                info.setdefault('frTerms', []).append(term)
                take(its, 'federal-register')
    gu = src.get('govuk') or {}
    for q in _as_list(gu.get('q')) or ['']:
        for org in _as_list(gu.get('orgs')):
            res = fetch(NF.govuk_url(org, q, since), accept='application/json')
            if res:
                take(NF.parse_govuk(res.body), 'govuk-search')
    wp = src.get('wp') or {}
    for q in _as_list(wp.get('queries')):
        for page in range(1, int(wp.get('pages', 2)) + 1):
            res = fetch(NF.wp_url(wp['base'], q, page, since), accept='application/json')
            if not res:
                break
            its = NF.parse_wp(res.body)
            take(its, f"wordpress-api {wp['base']}")
            if len(its) < 100:
                break
    home = fetch(src['home']) if src.get('home') else None
    if home:
        feeds_on(home, 'found on the home page')
    for u in _as_list(src.get('list')):
        res = home if (home and u == src.get('home')) else fetch(u)
        if res:
            if not list_page(res, u):
                feeds_on(res, 'found on the news page')
    if not acc and home:
        for u in NF.discover_sections(home.text, home.final_url, src['domains']):
            info.setdefault('sections', []).append(u)
            res = fetch(u)
            if res and not list_page(res, u):
                feeds_on(res, 'found on a news page')
            if acc:
                break
    return acc


def _article_summary(fx, url, info):
    res = _fetch(fx, url, info)
    if not res:
        return '', None
    try:
        pg = X.Page(X.canon(res.final_url), res.text)
    except Exception:
        return '', None
    s = pg.meta_desc or ''
    if len(R._text(s)) < SUMMARY_MIN:
        s = next((ln for ln in pg.lines if len(ln) >= 80 and ln.lower() != pg.name.lower()), '')
    return s, None


def read_source(src, fx, today, keep_days=120, known=None, backfill=False):
    """Returns (items, info). `known` maps url -> a stored item, so pages we already summarised are not fetched again."""
    known = known or {}
    info = {'id': src['id'], 'country': src['country'], 'body': src['body'], 'via': '', 'tried': [], 'robotsBlocked': 0,
            'found': 0, 'drops': Counter(), 'kept': 0, 'samples': [], 'rejected': [], 'error': '', 'profiles': []}
    have = any(i.get('sourceId') == src['id'] for i in known.values())
    since = (datetime.fromisoformat(today) - timedelta(days=RECENT_DAYS if (have and not backfill) else keep_days)).date().isoformat()
    try:
        cands = _candidates(src, fx, info, since)
    except Exception as e:  # one broken source must never stop the others
        info['error'] = f'{type(e).__name__}: {e}'
        return [], info
    info['found'] = len(cands)
    if not cands and not info['error']:
        info['error'] = 'no items found' + (' (blocked by robots.txt)' if info['robotsBlocked'] else '')
    out, seen, fetched = [], set(), 0
    for c in cands:
        title, url = c['title'], c['url']
        if url in seen:
            continue
        seen.add(url)
        if not R.allowed(url, src['domains']):
            info['drops']['link-not-on-official-site'] += 1
            continue
        pub = c.get('published')
        if not pub:
            info['drops']['no-date'] += 1
            continue
        age = R.age_days(pub, today)
        if age is None or age > keep_days:
            info['drops']['too-old'] += 1
            continue
        if age < -1:
            info['drops']['date-in-the-future'] += 1
            continue
        old = known.get(url)
        media = src.get('kind') == 'media'
        summary = '' if media else R.excerpt(c.get('summary', ''), title)     # trade-press text is never kept: headline, date and link only
        if not summary and not media and old and old.get('summary'):
            summary = old['summary']
        if not summary and not media and fetched < MAX_ARTICLE_FETCHES and src.get('filter') != 'skip-article':
            fetched += 1
            s, _ = _article_summary(fx, url, info)
            summary = R.excerpt(s, title)
        if not R.english(f'{title}. {summary}'):
            info['drops']['not-english'] += 1
            continue
        ok, why = R.relevant(title, summary, src.get('filter', 'student'), src.get('context') in ('immigration', 'international'))
        if not ok:
            info['drops'][why] += 1
            if len(info['rejected']) < 4:
                info['rejected'].append(f'{title[:90]} [{why}]')
            continue
        if src.get('tag'):        # trade press covers many countries: the country is the one named in the headline
            where = R.countries_in(title)
            if not where:
                info['drops']['no-country'] += 1
                continue
        else:
            where = [src['country']]
        for cc in where:
            out.append({'country': cc, 'sourceId': src['id'], 'body': src['body'], 'kind': src.get('kind', 'government'),
                        'detail': c.get('detail', ''), 'title': title, 'url': url, 'published': pub, 'summary': summary})
    info['kept'] = len(out)
    info['samples'] = [f"{i['published']} {i['title'][:90]}" for i in out[:3]]
    return out, info
