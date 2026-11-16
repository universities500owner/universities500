"""Find and read the course pages of one university. Polite by construction: a hard cap on pages per run,
robots.txt obeyed (RFC 9309), one request at a time per website, 3 seconds between requests.

Order of work, highest priority first:
  1. the university's international admissions page (so we know whether it takes international students)
  2. course pages we already know and that are due for a re-check, stalest first (at most 60% of the budget)
  3. list pages (a list page is how new courses are found, so it is read every run)
  4. new course pages found in the sitemap, on the home page and on list pages
"""
import gzip
import heapq
import re
import time
import urllib.parse
from collections import Counter
from datetime import date

import extract as X  # scripts/scholarships/extract.py (path is set by the caller)
import textutil as T
from fetcher import reg_domain

import courses as C
import levels as L

HUB_SCORE = 30
KNOWN_SCORE = 25
LIST_SCORE = 20
KNOWN_SHARE = 0.6
SITEMAP_PICKS = 600
LINKS_PER_PAGE = 400
GUESS_INTL = ('/international/', '/international-students/', '/study/international/', '/admissions/international/',
              '/international-admissions/', '/apply/international/', '/study/international-students/', '/international')
LOC = re.compile(r'<loc>\s*(?:<!\[CDATA\[)?\s*([^<\s]+?)\s*(?:\]\]>)?\s*</loc>', re.I)

COURSE_PATH = re.compile(r'/(?:courses?|programmes?|programs?|degrees?|undergraduate|postgraduate|graduate|masters?|bachelors?|majors?|study|subjects?|academics|study-areas?|areas-of-study|course-finder|find-a-course)(?:/|-|$)', re.I)
DEGREE_SLUG = re.compile(r'bachelor|master|(?:^|[-/_])(?:bsc|msc|beng|meng|mba|llb|llm|bba|bcom|mres)(?:[-/_.]|$)|(?:^|[-/_])(?:ba|ma|bs|ms)-|-(?:ba|ma|bs|ms)(?:[-/_.]|$)|honours|-hons', re.I)
JUNK = re.compile(r'/(?:news|blog|events?|stories|story|press|articles?|alumni|staff|jobs|careers|people|tag|category|feed|login|search|cart|shop|gallery|video|podcast|contact|privacy|terms|cookies?|accessibility|sitemap)(?:/|$)|\.(?:pdf|docx?|xlsx?|pptx?|zip|jpe?g|png|gif|mp4|svg|css|js)$|[?&](?:sort|filter|q|query|search|s)=', re.I)
OTHER_LANG = re.compile(r'^/(?:de|fr|es|it|nl|sv|se|no|nb|da|fi|pt|ar|zh|zh-cn|zh-tw|ja|ko|ru|pl|tr|cs|hu|ro|el|he|th|vi|id|ms|hi)(?:/|$)', re.I)
INTL_PATH = re.compile(r'international|overseas|global-students|study-abroad', re.I)
INTL_PAGE = re.compile(r'admission|apply|application|entry|requirement|fees|visa|english|IELTS|TOEFL', re.I)
SEEN_CAP = 3000

DAY = 86400


def url_score(url, text=''):
    """How likely a URL (and its link text) is to be a course page or a list of courses. 0 = do not fetch."""
    sp = urllib.parse.urlsplit(url)
    path = sp.path or '/'
    if JUNK.search(url) or OTHER_LANG.search(path) or L.classify_url(url):
        return 0
    if re.search(r'[?&]page=(\d+)', sp.query) and not COURSE_PATH.search(path):
        return 0
    s = 0
    if COURSE_PATH.search(path):
        s += 2
    if DEGREE_SLUG.search(path):
        s += 4
    if text and (L.BACHELOR_TITLE.search(text) or L.MASTER_TITLE.search(text)) and len(text) <= 140:
        s += 5
    depth = len([p for p in path.split('/') if p])
    if s and 2 <= depth <= 6:
        s += 1
    return s


def read_sitemaps(fx, scheme, host, same, limit=8):
    queue = list(fx.sitemaps(scheme, host)[:4]) or [f'{scheme}://{host}/sitemap.xml']
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
            try:
                body = gzip.decompress(body)
            except OSError:
                continue
        txt = body.decode('utf-8', errors='replace')[:8_000_000]
        locs = LOC.findall(txt)
        if '<sitemapindex' in txt[:2000].lower():
            ranked = sorted(locs, key=lambda u: (0 if re.search(r'course|programme|program|degree|study|undergrad|postgrad|page|content', u, re.I) else 1))
            queue.extend(ranked[:5])
        else:
            urls.extend(u for u in locs if same(u))
    return urls


def _age_days(d, today):
    try:
        return max((date.fromisoformat(today) - date.fromisoformat(d)).days, 0)
    except (TypeError, ValueError):
        return 9999


def due(entry, today, refresh_days, held_days):
    """Is a page we have already read due for another look? entry = [date, reason]."""
    d, reason = entry[0], entry[1]
    if reason == 'listing-page':
        return True  # list pages are how new courses are found
    age = _age_days(d, today)
    return age >= (refresh_days if reason == 'ok' else held_days)


def crawl_university(uni, fx, today, max_pages=150, prev=None, seeds=None, refresh_days=14, held_days=45, strict_international=False):
    """Read one university. `prev` is its file from the last run (courses, seen, intlOpen). `seeds` are course list pages
    checked by hand: they are read first and may sit on another domain."""
    prev = prev or {}
    seeds = [X.canon(u) for u in (seeds or []) if u]
    out = {'slug': uni['slug'], 'status': 'ok', 'note': '', 'robotsReason': '', 'pages': 0,
           'results': {},            # url asked for -> 'ok' or the reason it is not an eligible course; 'gone' for 404/410
           'records': {},            # url asked for -> record
           'seen': {},               # url -> [date, reason] for every page read this run
           'reasons': Counter(), 'samples': {}, 'urlSkipped': Counter(), 'partial': False,
           'intlOpen': prev.get('intlOpen'), 'knownRead': 0, 'knownFailed': 0}
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
        if home.robots_blocked and home.robots_reason == 'unreachable':
            out['status'], out['note'] = 'unreachable', 'robots.txt could not be read (server error or no answer)'
        elif home.robots_blocked:
            out['status'] = 'robots'
            out['robotsReason'] = home.robots_reason
            out['note'] = {'disallow': 'robots.txt disallows the home page',
                           'forbidden': 'robots.txt answered 401/403 and strict mode is on',
                           'unreachable': 'robots.txt could not be read (server error or no answer)'}.get(home.robots_reason, 'robots.txt does not allow us')
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
    prev_seen = {u: e for u, e in (prev.get('seen') or {}).items() if isinstance(e, list) and len(e) == 2}
    prev_courses = {c['url']: c for c in prev.get('courses', []) if c.get('url')}
    for u in prev_courses:
        prev_seen.setdefault(u, [prev_courses[u].get('lastVerified', today), 'ok'])
    known_cap = max(int(max_pages * KNOWN_SHARE), 1)

    def note(reason, url):
        out['reasons'][reason] += 1
        s = out['samples'].setdefault(reason, [])
        if len(s) < 5:
            s.append(url)

    skipped = set()

    def push(url, score, depth, kind='new'):
        nonlocal seq
        c = X.canon(url)
        if c in queued or score <= 0 or not same(c):
            if score <= 0 and c not in skipped and same(c) and c not in queued:
                why = L.classify_url(c)
                if why and (COURSE_PATH.search(urllib.parse.urlsplit(c).path) or DEGREE_SLUG.search(urllib.parse.urlsplit(c).path)):
                    skipped.add(c)
                    note(f'skipped-by-address:{why}', c)   # an online, pathway or doctoral address on a course path: counted, never requested
            return
        entry = prev_seen.get(c)
        if entry and kind == 'new':
            return  # known pages are queued below with their own priority, or are not due yet
        queued.add(c)
        seq += 1
        heapq.heappush(heap, (-score, seq, c, depth, kind))

    def consider(href, text, depth, bonus=0, floor=1, kind='new'):
        """Score a link and queue it. An online, pathway or doctoral address on a course path is counted and never requested."""
        sc = url_score(href, text)
        if sc == 0:
            push(href, 0, depth, kind)   # push() only counts it
            return
        if sc >= floor:
            push(href, sc + bonus, depth, kind)

    # 0. known pages that are due, stalest first
    for u, e in prev_seen.items():
        if not same(u) or e[1] == 'hub':
            continue
        if due(e, today, refresh_days, held_days):
            age = _age_days(e[0], today)
            if e[1] == 'listing-page':
                push_score, kind = LIST_SCORE, 'list'
            else:
                push_score, kind = KNOWN_SCORE + min(age, 400) / 100, 'known'
            c = X.canon(u)
            if c not in queued:
                queued.add(c)
                seq += 1
                heapq.heappush(heap, (-push_score, seq, c, 1, kind))
    # 0b. seeds: list pages checked by hand
    for u in seeds:
        if X.canon(u) not in queued:
            queued.add(X.canon(u))
            seq += 1
            heapq.heappush(heap, (-(LIST_SCORE + 5), seq, X.canon(u), 1, 'list'))

    if home_ok:
        # 1. international admissions pages: home page links, sitemap, then the usual places
        hp = X.Page(home.final_url, home.text, uni['country'], uni['name'])
        for href, text in hp.all_links:
            if INTL_PATH.search(urllib.parse.urlsplit(href).path) and not JUNK.search(href) and not OTHER_LANG.search(urllib.parse.urlsplit(href).path):
                push(href, HUB_SCORE - 1, 1, 'hub')
        try:
            sm = read_sitemaps(fx, scheme, host, same)
        except Exception as e:  # a bad sitemap must never stop the run
            sm = []
            out['note'] = f'sitemap error: {e}'
        for u in sm:
            path = urllib.parse.urlsplit(u).path
            if INTL_PATH.search(path) and INTL_PAGE.search(path) and len([p for p in path.split('/') if p]) <= 3 and not OTHER_LANG.search(path):
                push(u, HUB_SCORE - 2, 1, 'hub')
        if not any(-h[0] >= HUB_SCORE - 2 for h in heap):
            for i, path in enumerate(GUESS_INTL[:5]):
                push(f'{scheme}://{host}{path}', HUB_SCORE - 5 - i, 1, 'hub')
        # 2. course candidates
        scored = sorted(((url_score(u), -len(u), u) for u in sm), reverse=True)
        for sc, _, u in [x for x in scored if x[0] > 0][:SITEMAP_PICKS]:
            push(u, sc, 1)
        for u in sm:
            if url_score(u) == 0:
                push(u, 0, 1)
        for href, text in hp.all_links:
            consider(href, text, 1)
        visited.add(X.canon(home.final_url))
        # nothing found yet: try the usual course list addresses (a few cheap requests)
        if not any(0 < -h[0] < HUB_SCORE - 5 for h in heap if h[4] == 'new') and not any(h[4] in ('known', 'list') for h in heap):
            for path in ('/courses/', '/programmes/', '/programs/', '/study/', '/degrees/', '/undergraduate/', '/postgraduate/', '/study/courses/'):
                u = X.canon(f'{scheme}://{host}{path}')
                if u not in queued:
                    queued.add(u)
                    seq += 1
                    heapq.heappush(heap, (-3, seq, u, 1, 'list-guess'))
            out['reasons']['guessed-paths'] += 1

    while heap and out['pages'] < max_pages:
        if fx.deadline and time.monotonic() > fx.deadline:
            out['partial'] = True
            break
        negsc, _, url, depth, kind = heapq.heappop(heap)
        if url in visited:
            continue
        if kind == 'known' and out['knownRead'] >= known_cap:
            continue  # the rest of the known pages wait for the next run; they are the stalest, so they come first then
        visited.add(url)
        res = fx.get(url)
        out['pages'] += 1
        if kind == 'known':
            out['knownRead'] += 1
        if res.robots_blocked:
            out['pages'] -= 1   # no request was made, so it does not use the page budget
            note('robots-blocked-page', url)
            out['results'][url] = 'robots-blocked-page'
            continue
        if not res.ok:
            gone = res.status in (404, 410)
            note('gone' if gone else 'fetch-failed', url)
            out['results'][url] = 'gone' if gone else 'fetch-failed'
            if kind == 'known':
                out['knownFailed'] += 1
            if fx.host_dead(urllib.parse.urlsplit(url).netloc) and urllib.parse.urlsplit(url).netloc == host:
                break
            continue
        if res.ctype and 'html' not in res.ctype.lower():
            note('not-html', url)
            out['results'][url] = 'not-html'
            continue
        try:
            page = X.Page(X.canon(res.final_url), res.text, uni['country'], uni['name'])
        except Exception:
            note('parse-error', url)
            out['results'][url] = 'parse-error'
            continue
        visited.add(X.canon(res.final_url))
        if len(page.text) < 200:
            note('js-only-or-empty', url)
            out['results'][url] = 'js-only-or-empty'
            out['seen'][url] = [today, 'js-only-or-empty']
            continue

        # international admissions page?
        if kind == 'hub':
            sents = C.sentences_with_labels(page.text)
            intl, how, ev = L.international(sents)
            if intl == 'yes' and re.search(r'international|overseas', page.name + ' ' + url, re.I):
                out['intlOpen'] = {'url': page.url, 'evidence': ev, 'verified': today}
            out['results'][url] = 'hub'
            out['seen'][url] = [today, 'hub']
            # an admissions page can also be a way into course lists
            for href, text in page.links[:LINKS_PER_PAGE]:
                consider(href, text, depth + 1)
            continue

        rec, reason = C.read_course(page, res.text, uni, today, out['intlOpen'], strict_international)
        # links: from list pages and from pages that are not themselves a course, follow what looks like a course
        # (a course page's own links are mostly menus and "related courses", which are read at lower priority)
        n_links = C.count_course_links(page)
        is_list = reason == 'listing-page' or n_links >= 3 or (reason == 'not-a-course-page' and url_score(url) >= 2)
        if rec:
            out['records'][url] = rec
            out['results'][url] = 'ok'
            out['seen'][url] = [today, 'ok']
            note('eligible', url)
        else:
            out['results'][url] = reason
            # a page we followed links from is read again every run: it is how new courses are found
            out['seen'][url] = [today, 'listing-page' if is_list else reason]
            note(reason, url)
        if depth < 4 and (is_list or not rec):
            for href, text in page.links[:LINKS_PER_PAGE]:
                consider(href, text, depth + 1, bonus=2 if is_list else 0)
        elif depth < 4 and rec:
            for href, text in page.links[:60]:
                consider(href, text, depth + 1, floor=6)
    out['samples'] = {k: v for k, v in out['samples'].items()}
    return out
