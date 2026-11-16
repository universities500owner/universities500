"""Read one official source and return the items that pass every rule, plus a plain account of what happened (for the run report)."""
import urllib.parse
from collections import Counter

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


def _candidates(src, fx, info):
    """Items from the best endpoint that gives any: explicit feeds, then feeds the home page advertises, then the Federal Register, then the HTML list."""
    for u in src.get('feeds', []):
        res = _fetch(fx, u, info, accept='application/rss+xml,application/atom+xml,application/xml,text/xml,*/*;q=0.5')
        if res and NF.looks_like_feed(res.body):
            its = NF.parse_feed(res.body, res.final_url)
            if its:
                info['via'] = f'feed {u}'
                return its
    for term in src.get('fr', []):
        u = NF.federal_register_url(term)
        res = _fetch(fx, u, info, accept='application/json')
        if res:
            its = NF.parse_federal_register(res.body)
            if its:
                info.setdefault('frTerms', []).append(term)
                info['via'] = 'federal-register'
                info.setdefault('acc', []).extend(its)
    if info.get('acc'):
        seen, out = set(), []
        for i in info.pop('acc'):
            if i['url'] not in seen:
                seen.add(i['url'])
                out.append(i)
        return out
    page_url = src.get('list') or src.get('home')
    home = None
    if src.get('home'):
        home = _fetch(fx, src['home'], info)
        if home:
            for u in NF.discover_feeds(home.text, home.final_url)[:3]:
                res = _fetch(fx, u, info, accept='application/rss+xml,application/atom+xml,application/xml,text/xml,*/*;q=0.5')
                if res and NF.looks_like_feed(res.body):
                    its = NF.parse_feed(res.body, res.final_url)
                    if its:
                        info['via'] = f'feed (found on the home page) {u}'
                        return its
    if page_url:
        res = home if (home and page_url == src.get('home')) else _fetch(fx, page_url, info)
        if res:
            its = NF.parse_listing(res.text, res.final_url)
            if its:
                info['via'] = f'list page {page_url}'
                return its
    return []


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


def read_source(src, fx, today, keep_days=120, known=None):
    """Returns (items, info). `known` maps url -> a stored item, so pages we already summarised are not fetched again."""
    known = known or {}
    info = {'id': src['id'], 'country': src['country'], 'body': src['body'], 'via': '', 'tried': [], 'robotsBlocked': 0,
            'found': 0, 'drops': Counter(), 'kept': 0, 'samples': [], 'rejected': [], 'error': ''}
    try:
        cands = _candidates(src, fx, info)
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
        summary = R.excerpt(c.get('summary', ''), title)
        if not summary and old and old.get('summary'):
            summary = old['summary']
        if not summary and fetched < MAX_ARTICLE_FETCHES and src.get('filter') != 'skip-article':
            fetched += 1
            s, _ = _article_summary(fx, url, info)
            summary = R.excerpt(s, title)
        if not R.english(f'{title}. {summary}'):
            info['drops']['not-english'] += 1
            continue
        ok, why = R.relevant(title, summary, src.get('filter', 'student'))
        if not ok:
            info['drops'][why] += 1
            if len(info['rejected']) < 4:
                info['rejected'].append(f'{title[:90]} [{why}]')
            continue
        out.append({'country': src['country'], 'sourceId': src['id'], 'body': src['body'], 'kind': src.get('kind', 'government'),
                    'detail': c.get('detail', ''), 'title': title, 'url': url, 'published': pub, 'summary': summary})
    info['kept'] = len(out)
    info['samples'] = [f"{i['published']} {i['title'][:90]}" for i in out[:3]]
    return out, info
