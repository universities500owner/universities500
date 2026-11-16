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


def federal_register_url(term, per_page=25):
    q = [('per_page', per_page), ('order', 'newest'), ('conditions[term]', term)]
    q += [('fields[]', f) for f in ('title', 'abstract', 'html_url', 'publication_date', 'type', 'agency_names')]
    return FR_API + '?' + urllib.parse.urlencode(q)


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
