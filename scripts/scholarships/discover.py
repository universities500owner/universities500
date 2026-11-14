"""Find and read the scholarship pages of one university. Polite by construction:
a hard cap on pages, robots.txt obeyed, one request at a time per site."""
import heapq
import re
import urllib.parse
from collections import Counter

import extract as X
import textutil as T
from fetcher import reg_domain

URL_STRONG = re.compile(r'schol|bursar|fellowship|studentship|waiver', re.I)
URL_WEAK = re.compile(r'award|grant|funding|financial-?aid|fees-?and-?funding|tuition-?discount|stipend', re.I)
URL_INTL = re.compile(r'international|overseas|global|non-?eu|abroad|worldwide|out-of-state', re.I)
LOC = re.compile(r'<loc>\s*(?:<!\[CDATA\[)?\s*([^<\s]+?)\s*(?:\]\]>)?\s*</loc>', re.I)


def url_score(url, text=''):
    path = urllib.parse.urlsplit(url).path.lower()
    if X.JUNK_PATH.search(url):
        return 0
    s = 0
    if URL_STRONG.search(path):
        s += 3
    if URL_WEAK.search(path):
        s += 1
    if s and URL_INTL.search(path):
        s += 2
    if text and T.NAME_WORDS.search(text):
        s += 2 if s else 1
    return s


def read_sitemaps(fx, scheme, host, same, limit=5):
    """Collect URLs from sitemaps named in robots.txt, or /sitemap.xml. At most `limit` sitemap files."""
    queue = list(fx.sitemaps(scheme, host)[:3]) or [f'{scheme}://{host}/sitemap.xml']
    seen, urls, fetched = set(), [], 0
    while queue and fetched < limit:
        sm = queue.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        res = fx.get(sm, accept='application/xml,text/xml,*/*;q=0.5')
        fetched += 1
        if not res.ok:
            continue
        body = res.body
        if body[:2] == b'\x1f\x8b':
            import gzip
            try:
                body = gzip.decompress(body)
            except OSError:
                continue
        txt = body.decode('utf-8', errors='replace')[:5_000_000]
        locs = LOC.findall(txt)
        if '<sitemapindex' in txt[:2000].lower():
            ranked = sorted(locs, key=lambda u: (0 if re.search(r'page|content|schol|post|general', u, re.I) else 1))
            queue.extend(ranked[:3])
        else:
            urls.extend(u for u in locs if same(u))
    return urls


def crawl_university(uni, fx, today, max_pages=30):
    out = {'slug': uni['slug'], 'status': 'ok', 'records': [], 'hub': None, 'pages': 0, 'reasons': Counter(), 'note': ''}
    base = uni.get('web')
    if not base:
        out['status'] = 'no-website'
        return out
    p0 = urllib.parse.urlsplit(base)
    scheme, host = (p0.scheme or 'https'), p0.netloc
    regs = {reg_domain(host)}
    same = lambda u: reg_domain(urllib.parse.urlsplit(u).netloc) in regs

    home = fx.get(base)
    if home.robots_blocked:
        out['status'], out['note'] = 'robots', 'robots.txt does not allow us'
        return out
    if not home.ok:
        out['status'], out['note'] = 'unreachable', home.error or 'no response'
        return out
    fp = urllib.parse.urlsplit(home.final_url)
    regs.add(reg_domain(fp.netloc))
    scheme, host = fp.scheme, fp.netloc

    heap, queued, visited = [], set(), set()
    seq = 0

    def push(url, score, depth):
        nonlocal seq
        c = X.canon(url)
        if c in queued or score <= 0 or not same(c):
            return
        queued.add(c)
        seq += 1
        heapq.heappush(heap, (-score, seq, c, depth))

    # 1. sitemap candidates (best 40)
    try:
        sm = read_sitemaps(fx, scheme, host, same)
    except Exception as e:  # a bad sitemap must never stop the run
        sm = []
        out['note'] = f'sitemap error: {e}'
    scored = sorted(((url_score(u), -len(u), u) for u in sm), reverse=True)
    for sc, _, u in [x for x in scored if x[0] > 0][:40]:
        push(u, sc, 1)

    # 2. links on the home page
    hp = X.Page(home.final_url, home.text, uni['country'], uni['name'])
    for href, text in hp.all_links:
        sc = url_score(href, text)
        if sc == 0 and re.search(r'international|study-?abroad|fees|funding|financial', urllib.parse.urlsplit(href).path, re.I):
            sc = 1
        push(href, sc, 1)
    visited.add(X.canon(home.final_url))

    hub_best = (0, None, None)  # (score, url, title)
    seen_ids = {}
    while heap and out['pages'] < max_pages:
        negsc, _, url, depth = heapq.heappop(heap)
        if url in visited:
            continue
        visited.add(url)
        res = fx.get(url)
        out['pages'] += 1
        if res.robots_blocked:
            out['reasons']['robots-blocked-page'] += 1
            continue
        if not res.ok:
            out['reasons']['fetch-failed'] += 1
            if fx.host_dead(urllib.parse.urlsplit(url).netloc):
                break
            continue
        if 'html' not in (res.ctype or '').lower() and res.ctype:
            out['reasons']['not-html'] += 1
            continue
        try:
            page = X.Page(res.final_url, res.text, uni['country'], uni['name'])
        except Exception as e:
            out['reasons']['parse-error'] += 1
            continue
        visited.add(X.canon(res.final_url))
        if len(page.text) < 200:
            out['reasons']['js-only-or-empty'] += 1
            continue
        is_listing, links = X.looks_like_listing(page, same)
        recs = X.table_records(page, uni, today)
        if recs:
            for r in recs:
                seen_ids.setdefault(r['id'], r)
        if is_listing:
            sc = len(links) + (3 if URL_INTL.search(url) else 0) + (2 if URL_STRONG.search(url) else 0)
            if sc > hub_best[0]:
                hub_best = (sc, X.canon(res.final_url), page.name)
            if depth < 3:
                for h, t in links[:25]:
                    push(h, max(url_score(h, t), 1), depth + 1)
        elif not recs:
            rec, reason = X.detail_record(page, uni, today)
            if rec:
                seen_ids.setdefault(rec['id'], rec)
            else:
                out['reasons'][reason] += 1
                # a page that is about scholarships but is not a detail page can still be the best "hub"
                if reason in ('no-details', 'international-not-stated') and re.search(r'\bscholarships?\b', page.name, re.I):
                    sc = 1 + (3 if URL_INTL.search(url) else 0)
                    if sc > hub_best[0]:
                        hub_best = (sc, X.canon(res.final_url), page.name)

    # one record per scholarship name inside a university: keep the one with the most fields
    by_name = {}
    for r in seen_ids.values():
        k = re.sub(r'[^a-z0-9]+', ' ', r['name'].lower()).strip()
        fill = sum(bool(r.get(f)) for f in ('value', 'deadline', 'eligibility', 'description', 'applyUrl'))
        if k not in by_name or fill > by_name[k][0]:
            by_name[k] = (fill, r)
    out['records'] = [v[1] for v in by_name.values()]
    if hub_best[1]:
        out['hub'] = {'url': hub_best[1], 'title': hub_best[2]}
    if not out['records'] and not out['hub']:
        out['status'] = 'no-scholarship-pages'
    return out
