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
SEED_SCORE = 100        # pages checked by hand are read first
SEED_HUB = 1000         # ...and always win the "hub page" choice over a page we only guessed
LISTING_LINKS = 60      # links followed from a listing page (was 25)
SITEMAP_PICKS = 80      # best sitemap candidates queued (was 40)
GUESS_PATHS = ('/scholarships/', '/study/scholarships/', '/international/scholarships/', '/international-students/scholarships/',
               '/admissions/scholarships/', '/fees-and-funding/', '/study/fees-and-scholarships/', '/scholarships')
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


def crawl_university(uni, fx, today, max_pages=60, seeds=None, extra=None):
    """Read one university. `seeds` are scholarship pages checked by hand: they are read first, they may sit on another
    domain, and they replace the hub page we would otherwise guess. `extra` are scholarship pages named by the university's own
    finder feed (feeds.py): they are read as international scholarship pages but are never taken for the hub page."""
    seeds = [X.canon(u) for u in (seeds or []) if u]
    extra = [X.canon(u) for u in (extra or []) if u]
    out = {'slug': uni['slug'], 'status': 'ok', 'records': [], 'hub': None, 'pages': 0, 'reasons': Counter(), 'note': '',
           'seeds': {}, 'robotsReason': ''}
    base = uni.get('web')
    if not base:
        out['status'] = 'no-website'
        return out
    p0 = urllib.parse.urlsplit(base)
    scheme, host = (p0.scheme or 'https'), p0.netloc
    regs = {reg_domain(host)}
    for u in seeds:
        regs.add(reg_domain(urllib.parse.urlsplit(u).netloc))
    same = lambda u: reg_domain(urllib.parse.urlsplit(u).netloc) in regs

    home = fx.get(base)
    home_ok = home.ok and not home.robots_blocked
    if not home_ok:
        if home.robots_blocked:
            out['status'] = 'robots'
            out['robotsReason'] = home.robots_reason
            out['note'] = {'disallow': 'robots.txt disallows the home page',
                           'forbidden': 'robots.txt answered 401/403 and strict mode is on',
                           'unreachable': fx.robots_note(base)}.get(home.robots_reason, 'robots.txt does not allow us')
        else:
            out['status'], out['note'] = 'unreachable', home.error or 'no response'
        if not seeds:
            return out
        out['homeFailed'] = out['status']
        out['status'], out['note'] = 'ok', out['note'] + '; read the supplied pages only'
    else:
        fp = urllib.parse.urlsplit(home.final_url)
        regs.add(reg_domain(fp.netloc))
        scheme, host = fp.scheme, fp.netloc

    heap, queued, visited = [], set(), set()
    seq = 0
    seed_set = set(seeds)

    def push(url, score, depth, intl=False):
        nonlocal seq
        c = X.canon(url)
        if c in queued or score <= 0 or not same(c):
            return
        queued.add(c)
        seq += 1
        heapq.heappush(heap, (-score, seq, c, depth, intl))

    # 0. pages checked by hand
    for u in seeds:
        push(u, SEED_SCORE, 1, True)  # a page the owner supplied as the international scholarships page
    for u in extra:
        push(u, SEED_SCORE - 1, 2, True)  # listed by the finder as open to overseas students

    if home_ok:
        # 1. sitemap candidates
        try:
            sm = read_sitemaps(fx, scheme, host, same)
        except Exception as e:  # a bad sitemap must never stop the run
            sm = []
            out['note'] = f'sitemap error: {e}'
        scored = sorted(((url_score(u), -len(u), u) for u in sm), reverse=True)
        for sc, _, u in [x for x in scored if x[0] > 0][:SITEMAP_PICKS]:
            push(u, sc, 1)

        # 2. links on the home page
        hp = X.Page(home.final_url, home.text, uni['country'], uni['name'])
        for href, text in hp.all_links:
            sc = url_score(href, text)
            if sc == 0 and re.search(r'international|study-?abroad|fees|funding|financial', urllib.parse.urlsplit(href).path, re.I):
                sc = 1
            push(href, sc, 1)
        visited.add(X.canon(home.final_url))

        # 3. nothing promising so far: try the usual places a university keeps its scholarships (a few requests, 404s are cheap)
        if not seeds and not any(-h[0] >= 3 for h in heap):
            for path in GUESS_PATHS:
                push(f'{scheme}://{host}{path}', 2, 1)
            out['reasons']['guessed-paths'] += 1

    hub_best = (0, None, None)  # (score, url, title)
    hub_seed = False
    seen_ids = {}
    out['trace'] = []   # the first pages visited and what became of each (printed only with run.py --diagnose)

    def trace(url, what):
        if len(out['trace']) < 30:
            out['trace'].append(f'{url}  ->  {what}')
    while heap and out['pages'] < max_pages:
        negsc, _, url, depth, intl_ctx = heapq.heappop(heap)
        if url in visited:
            continue
        visited.add(url)
        is_seed = url in seed_set
        res = fx.get(url)
        out['pages'] += 1
        if res.robots_blocked:
            trace(url, 'blocked by robots.txt')
            out['reasons']['robots-blocked-page'] += 1
            if is_seed:
                out['seeds'][url] = f'robots-{res.robots_reason}'
            continue
        if not res.ok:
            trace(url, f'not opened: {res.error or res.status}')
            out['reasons']['fetch-failed'] += 1
            if is_seed:
                out['seeds'][url] = f'failed: {res.error}'
            if fx.host_dead(urllib.parse.urlsplit(url).netloc) and urllib.parse.urlsplit(url).netloc == host:
                break
            continue
        if 'html' not in (res.ctype or '').lower() and res.ctype:
            out['reasons']['not-html'] += 1
            if is_seed:
                out['seeds'][url] = 'not a web page'
            continue
        try:
            page = X.Page(res.final_url, res.text, uni['country'], uni['name'])
        except Exception as e:
            out['reasons']['parse-error'] += 1
            if is_seed:
                out['seeds'][url] = 'could not parse'
            continue
        visited.add(X.canon(res.final_url))
        if len(page.text) < 200:
            trace(url, f'almost no text ({len(page.text)} characters): built by scripts or a bot check')
            out['reasons']['js-only-or-empty'] += 1
            if is_seed:
                # the page loads but builds its list with scripts: we cannot read it, but the link is still worth showing
                out['seeds'][url] = 'loads, but the list is built by scripts'
                hub_best = max(hub_best, (SEED_HUB, X.canon(res.final_url), page.name or uni['name']), key=lambda t: t[0])
                hub_seed = True
            continue
        is_listing, links = X.looks_like_listing(page, same)
        about = bool(re.search(r'\bschol|bursar|fellowship|funding|financial aid', page.text[:4000], re.I))
        if is_seed:
            out['seeds'][url] = 'ok' if about else 'loads, but does not mention scholarships'
            if about:
                hub_best = max(hub_best, (SEED_HUB + len(links), X.canon(res.final_url), page.name), key=lambda t: t[0])
                hub_seed = True
        # does this page speak to international students? Its scholarships inherit that.
        here_intl = bool(intl_ctx or URL_INTL.search(url) or re.search(r'international|overseas', page.name, re.I))
        recs = X.table_records(page, uni, today, intl_hint=here_intl)
        if recs:
            for r in recs:
                seen_ids.setdefault(r['id'], r)
        trace(url, ('table of %d' % len(recs)) if recs else ('listing page, %d links' % len(links)) if is_listing else 'page')
        if is_listing:
            sc = len(links) + (3 if URL_INTL.search(url) else 0) + (2 if URL_STRONG.search(url) else 0)
            if sc > hub_best[0]:
                hub_best = (sc, X.canon(res.final_url), page.name)
        elif not recs:
            rec, reason = X.detail_record(page, uni, today, intl_hint=intl_ctx)
            if rec:
                seen_ids.setdefault(rec['id'], rec)
                trace(url, f"record: {rec['name']}")
            else:
                trace(url, f"kept out: {reason} ({page.name[:60]!r})")
                out['reasons'][reason] += 1
                # a page that is about scholarships but is not a detail page can still be the best "hub"
                if reason in ('no-details', 'international-not-stated') and re.search(r'\bscholarships?\b', page.name, re.I):
                    sc = 1 + (3 if URL_INTL.search(url) else 0)
                    if sc > hub_best[0]:
                        hub_best = (sc, X.canon(res.final_url), page.name)
        if (is_listing or is_seed) and depth < 3:
            for h, t in links[:LISTING_LINKS]:
                push(h, max(url_score(h, t), 1), depth + 1, here_intl)

    # one record per scholarship name inside a university: keep the one with the most fields
    by_name = {}
    for r in seen_ids.values():
        k = re.sub(r'[^a-z0-9]+', ' ', r['name'].lower()).strip()
        fill = sum(bool(r.get(f)) for f in ('value', 'deadline', 'eligibility', 'description', 'applyUrl'))
        if k not in by_name or fill > by_name[k][0]:
            by_name[k] = (fill, r)
    out['records'] = [v[1] for v in by_name.values()]
    if hub_best[1]:
        out['hub'] = {'url': hub_best[1], 'title': hub_best[2], 'supplied': hub_seed}
    if not out['records'] and not out['hub']:
        out['status'] = 'no-scholarship-pages'
    if out.get('homeFailed'):
        # only the supplied pages could be read: what we saw is partial, so it must not count against records we did not reach
        out['partial'] = True
        if not out['records'] and not out['hub']:
            out['status'] = out['homeFailed']
    return out
