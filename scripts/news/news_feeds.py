"""Read the official lists of news: RSS and Atom feeds, the US Federal Register's own JSON, and (when a body has no feed) its HTML news list.
Each reader returns plain dicts: title, url, published (ISO date or None), summary (official text, may be HTML)."""
import json
import re
import urllib.parse

from bs4 import BeautifulSoup

import extract as X  # scripts/scholarships/extract.py (path is set by the caller)
import textutil as T
import news_rules as R


def _local(tag):
    return (tag.name or '').split(':')[-1].lower()


def parse_feed(body, base=''):
    """RSS 2.0, RSS 1.0 (RDF) and Atom. Returns a list of items, newest first as the feed gives them."""
    try:
        soup = BeautifulSoup(body, 'xml')
    except Exception:
        soup = BeautifulSoup(body, 'html.parser')
    items = []
    for it in soup.find_all(['item', 'entry']):
        f = {}
        link = ''
        for ch in it.find_all(True, recursive=False):
            name = _local(ch)
            if name == 'link':
                href = ch.get('href')
                if href:
                    rel = ch.get('rel')
                    rel = ' '.join(rel) if isinstance(rel, list) else (rel or 'alternate')
                    if rel.lower() == 'alternate':
                        link = link or href
                elif ch.get_text(strip=True):
                    link = link or ch.get_text(strip=True)
            elif name in ('title', 'pubdate', 'published', 'updated', 'date', 'issued', 'description', 'summary', 'encoded', 'content', 'guid'):
                f.setdefault(name, ch.get_text(' '))   # the text of a CDATA or escaped description is its HTML; excerpt() strips the tags
        if not link and f.get('guid', '').startswith('http'):
            link = f['guid'].strip()
        url = urllib.parse.urljoin(base, link.strip()) if link else ''
        pub = None
        for k in ('pubdate', 'published', 'issued', 'date', 'updated'):
            pub = pub or R.parse_date(f.get(k))
        summary = f.get('description') or f.get('summary') or ''
        if len(R._text(summary)) < 40:
            summary = f.get('encoded') or f.get('content') or summary
        items.append({'title': T.clean(BeautifulSoup(f.get('title', ''), 'html.parser').get_text(' ')), 'url': url, 'published': pub, 'summary': summary})
    return [i for i in items if i['title'] and i['url']]


def discover_feeds(html, base):
    """Feed addresses a page advertises with <link rel="alternate" type="application/rss+xml">."""
    soup = X.soup_of(html)
    out = []
    for l in soup.find_all('link', href=True):
        rel = ' '.join(l.get('rel') or []).lower() if isinstance(l.get('rel'), list) else str(l.get('rel') or '').lower()
        typ = (l.get('type') or '').lower()
        if 'alternate' in rel and ('rss' in typ or 'atom' in typ):
            u = urllib.parse.urljoin(base, l['href'].strip())
            if u not in out:
                out.append(u)
    return out


def looks_like_feed(body):
    head = body[:600].lower()
    return b'<rss' in head or b'<feed' in head or b'<rdf:rdf' in head or (b'<?xml' in head and (b'<channel' in body[:3000].lower() or b'<entry' in body[:3000].lower()))


FR_API = 'https://www.federalregister.gov/api/v1/documents.json'


def federal_register_url(term, per_page=100, since=None):
    q = [('per_page', per_page), ('order', 'newest'), ('conditions[term]', term)]
    if since:
        q.append(('conditions[publication_date][gte]', since))
    q += [('fields[]', f) for f in ('title', 'abstract', 'html_url', 'publication_date', 'type', 'agency_names')]
    return FR_API + '?' + urllib.parse.urlencode(q)


GOVUK_API = 'https://www.gov.uk/api/search.json'


def govuk_url(org, q, since, count=100):
    """GOV.UK's own search API: one organisation, one query, newest first, from a date."""
    p = [('filter_organisations', org), ('order', '-public_timestamp'), ('count', count), ('filter_public_timestamp', f'from:{since}')]
    if q:
        p.append(('q', q))
    p += [('fields', f) for f in ('title', 'description', 'public_timestamp', 'link', 'format')]
    return GOVUK_API + '?' + urllib.parse.urlencode(p)


def parse_govuk(body):
    try:
        data = json.loads(body)
    except ValueError:
        return []
    out = []
    for r in data.get('results', []) if isinstance(data, dict) else []:
        link = r.get('link') or ''
        if r.get('title') and link:
            out.append({'title': T.clean(r['title']), 'url': urllib.parse.urljoin('https://www.gov.uk', link),
                        'published': R.parse_date(r.get('public_timestamp')), 'summary': r.get('description') or '',
                        'detail': (r.get('format') or '').replace('_', ' ')})
    return out


def wp_url(base, q, page, since, per_page=100):
    """The WordPress REST API that many news sites switch on: posts that match a word, newest first, from a date."""
    p = [('search', q), ('per_page', per_page), ('page', page), ('orderby', 'date'), ('order', 'desc'), ('after', f'{since}T00:00:00')]
    p += [('_fields', 'date,link,title,excerpt')]
    return base.rstrip('/') + '/wp-json/wp/v2/posts?' + urllib.parse.urlencode(p)


def parse_wp(body):
    try:
        data = json.loads(body)
    except ValueError:
        return []
    out = []
    for r in data if isinstance(data, list) else []:
        title = T.clean(BeautifulSoup((r.get('title') or {}).get('rendered', ''), 'html.parser').get_text(' '))
        if title and r.get('link'):
            out.append({'title': title, 'url': r['link'], 'published': R.parse_date(r.get('date')),
                        'summary': (r.get('excerpt') or {}).get('rendered', ''), 'detail': ''})
    return out


def parse_federal_register(body):
    """The Federal Register is the US government's official gazette. Each notice has its own official abstract."""
    try:
        data = json.loads(body)
    except ValueError:
        return []
    out = []
    for r in data.get('results', []) if isinstance(data, dict) else []:
        if r.get('title') and r.get('html_url'):
            out.append({'title': T.clean(r['title']), 'url': r['html_url'], 'published': R.parse_date(r.get('publication_date')),
                        'summary': r.get('abstract') or '', 'detail': ', '.join(r.get('agency_names') or [])[:120]})
    return out


LISTISH = re.compile(r'news|item|teaser|card|result|row|post|article|update|release|story|list', re.I)


def parse_listing(html, base):
    """A news list page with no feed. Takes blocks that hold one link, one date and (optionally) a short teaser.
    A block with no readable date is skipped: we do not guess dates."""
    soup = X.soup_of(html)
    items, seen = [], set()
    blocks = soup.find_all(['article', 'li', 'tr', 'div'])
    for b in blocks:
        if b.name == 'div' and not LISTISH.search(' '.join(b.get('class') or [])):
            continue
        txt = T.clean(b.get_text(' '))
        if not (30 <= len(txt) <= 1400):
            continue
        links = [a for a in b.find_all('a', href=True) if 20 <= len(T.clean(a.get_text(' '))) <= 240 and not a['href'].startswith(('#', 'mailto:', 'javascript:'))]
        if not links or len({a['href'] for a in links}) > 3:
            continue   # a menu or a wrapper around many items
        head = b.find(['h2', 'h3', 'h4'])
        a = next((x for x in links if head and x in head.find_all('a')), None) or links[0]
        url = urllib.parse.urljoin(base, a['href'].strip())
        if url in seen or url.rstrip('/') == base.rstrip('/'):
            continue
        t = b.find('time')
        pub = R.parse_date(t.get('datetime') or t.get_text(' ')) if t else None
        if not pub:
            dates = T.parse_full_dates(txt)
            pub = dates[0] if dates else None
        if not pub:
            continue
        title = T.clean(a.get_text(' '))
        teaser = ''
        for p in b.find_all('p'):
            pt = T.clean(p.get_text(' '))
            if len(pt) >= 40 and pt.lower() != title.lower() and not T.parse_full_dates(pt) == [pt]:
                teaser = pt
                break
        seen.add(url)
        items.append({'title': title, 'url': url, 'published': pub, 'summary': teaser})
    return items


def parse_dated_links(html, base, pattern):
    """For a list whose headlines carry no date but whose addresses do (University World News: ...story=20261114092909696).
    `pattern` has one group of eight digits, YYYYMMDD. A link whose address has no such date is skipped."""
    rx = re.compile(pattern)
    soup = X.soup_of(html)
    items, seen = [], set()
    for a in soup.find_all('a', href=True):
        title = T.clean(a.get_text(' '))
        if not 25 <= len(title) <= 240:
            continue
        url = urllib.parse.urljoin(base, a['href'].strip())
        m = rx.search(url)
        if not m or url in seen:
            continue
        d = m.group(1)
        pub = R.parse_date(f'{d[:4]}-{d[4:6]}-{d[6:8]}')
        if not pub:
            continue
        seen.add(url)
        items.append({'title': title, 'url': url, 'published': pub, 'summary': ''})
    return items


# ---- finding a site's news pages from its home page, and describing a page we could not read ----
NEWS_TEXT = re.compile(r"\b(?:news|press|media(?:[- ]?(?:centre|center|releases?|room))?|latest|announcements?|updates?|newsroom|notices?|bulletins?)\b", re.I)
NEWS_PATH = re.compile(r"/(?:news|press|media|latest|newsroom|announcements?|notices?|updates?|press-releases?|media-releases?)(?:[-_/.]|$)", re.I)
NOT_A_PAGE = re.compile(r"\.(?:pdf|docx?|xlsx?|zip|jpe?g|png|gif|svg|mp4)$", re.I)


def discover_sections(html, base, domains, limit=3):
    """Links on a home page that lead to the body's news or press pages: link text or address says news, press, media, latest, notices.
    Only addresses on the body's own domains. Shallow list pages come before single articles."""
    soup = X.soup_of(html)
    found = {}
    for a in soup.find_all('a', href=True):
        href = a['href'].strip()
        if not href or href.startswith(('#', 'mailto:', 'tel:', 'javascript:')):
            continue
        url = urllib.parse.urljoin(base, href).split('#')[0]
        if url.rstrip('/') == base.rstrip('/') or not R.allowed(url, domains):
            continue
        path = urllib.parse.urlparse(url).path
        if NOT_A_PAGE.search(path):
            continue
        segs = [x for x in path.split('/') if x]
        if segs and len(segs[-1]) > 45:
            continue      # a long slug is an article, not a list
        text = T.clean(a.get_text(' '))
        score = (2 if NEWS_TEXT.search(text) and len(text) <= 40 else 0) + (2 if NEWS_PATH.search(path) else 0)
        if score:
            old = found.get(url)
            if not old or score > old[0]:
                found[url] = (score, len(segs))
    ranked = sorted(found.items(), key=lambda kv: (-kv[1][0], kv[1][1], kv[0]))
    return [u for u, _ in ranked[:limit]]


DATE_HINT = re.compile(r"\b\d{1,2}[ /.-](?:\d{1,2}|[A-Z][a-z]{2,8})[ /.-]\d{4}\b|\b[A-Z][a-z]{2,8}\.? \d{1,2},? \d{4}\b")
API_HINT = re.compile(r"""["'](https?://[^"'\s<>]+|/[^"'\s<>]+)["']""")


def profile(html, base):
    """A few plain facts about a page that gave no items, so the report can say why (script-loaded, no dates, a menu only, ...)."""
    soup = X.soup_of(html)
    title = T.clean(soup.title.get_text(' ')) if soup.title else ''
    text = T.clean(soup.get_text(' '))
    anchors = soup.find_all('a', href=True)
    long_links = []
    for a in anchors:
        t = T.clean(a.get_text(' '))
        if len(t) >= 30:
            long_links.append(f"{t[:60]} -> {urllib.parse.urljoin(base, a['href'])[:100]}")
        if len(long_links) >= 6:
            break
    # where a date sits in the visible text, and any data addresses named in the page's scripts: enough to see why no headline was read
    ctx = [T.clean(text[max(0, m.start() - 90):m.end() + 90]) for m in list(DATE_HINT.finditer(text))[:2]]
    raw = html or ''
    hm = DATE_HINT.search(raw)
    date_html = re.sub(r'\s+', ' ', raw[max(0, hm.start() - 260):hm.end() + 120]) if hm else ''
    ends = []
    for e in API_HINT.findall(html or ''):
        if re.search(r'api|\.json|ajax|feed|search|graphql|odata|_vti|services?/', e, re.I) and not re.search(r'\.(?:js|css|png|jpe?g|svg|gif|woff2?|ico)(?:\?|$)', e, re.I) and e not in ends:
            ends.append(e[:420])
        if len(ends) >= 5:
            break
    return {'title': title[:90], 'chars': len(text), 'links': len(anchors), 'timeTags': len(soup.find_all('time')),
            'dates': len(T.parse_full_dates(text)), 'scripts': len(soup.find_all('script')), 'sample': long_links,
            'dateContext': ctx, 'dateHtml': date_html, 'endpoints': ends}
