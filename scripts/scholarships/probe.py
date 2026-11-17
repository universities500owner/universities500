#!/usr/bin/env python3
"""Find out WHY a university gives no scholarships, before changing any reader code. Writes nothing to the data files.

For each university it asks, with the same polite fetcher the reader uses (identified, robots.txt obeyed, 3 s between requests):
  1. robots.txt: what answered, and whether the answer looks like a security wall (a challenge page, "access denied") or a real rule.
  2. each scholarship page we know (the hand-checked seeds, then the home page): did it load, how many links look like scholarships,
     and does the page look built by scripts (few links, a data blob, a search vendor, an address a script would call).
  3. the sitemap: how many addresses mention scholarships, with samples.
It then prints one verdict per university. Nothing here goes around a block: a university that does not answer is reported as such.

    python3 scripts/scholarships/probe.py --only monash-university,rmit-university
    python3 scripts/scholarships/probe.py --country australia
    python3 scripts/scholarships/probe.py --url https://search.studyaustralia.gov.au/scholarships --url https://example.edu/scholarships/
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
from fetcher import Fetcher  # noqa: E402

SCH_WORD = re.compile(r"scholarship|bursar|grant\b|award|fellowship|stipend|funding|financial aid", re.I)
SCRIPT_SRC = re.compile(r'<script[^>]+src=["\']([^"\']+)["\']', re.I)
LINK = re.compile(r'<a\b[^>]*href=["\']([^"\'#][^"\']*)["\'][^>]*>(.*?)</a>', re.I | re.S)
TAGS = re.compile(r'<[^>]+>')
# vendors that build a searchable list with scripts, and the words a page uses to hand its data to a script
VENDORS = ('algolia', 'coveo', 'funnelback', 'searchspring', 'swiftype', 'elastic', 'typesense', 'meilisearch', 'sitecore', 'contentful',
           'sanity.io', 'prismic', 'storyblok', 'salesforce', 'force.com', 'siteimprove', 'bloomreach', 'yext', 'cludo', 'gatsby', 'next', 'nuxt')
BLOBS = (('__NEXT_DATA__', 'next-data'), ('__NUXT__', 'nuxt'), ('__INITIAL_STATE__', 'initial-state'), ('__APOLLO_STATE__', 'apollo'),
         ('window.__data', 'window-data'), ('application/ld+json', 'ld-json'))
API_PATH = re.compile(r'["\'](/(?:[\w\-]+/){0,4}(?:api|graphql|search|query|_next/data|wp-json|umbraco/api|jss)[\w\-/.?=&%]*)["\']', re.I)
WALL = re.compile(r'access denied|request blocked|just a moment|attention required|incapsula|akamai|reference #|captcha|pardon our interruption|bot|unusual traffic', re.I)


def raw_robots(host, ua):
    """robots.txt is a file every site invites us to read, so asking for it directly is always fine. Report exactly what came back."""
    url = f'https://{host}/robots.txt'
    req = urllib.request.Request(url, headers={'User-Agent': ua, 'Accept': 'text/plain,*/*;q=0.5', 'Accept-Encoding': 'identity'})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            body = r.read(4000).decode('utf-8', errors='replace')
            return {'status': r.status, 'server': r.headers.get('Server', ''), 'ctype': r.headers.get('Content-Type', ''), 'body': body,
                    'flags': [h for h in ('cf-mitigated', 'x-datadome', 'x-sucuri-id', 'x-amzn-waf-action', 'x-iinfo') if r.headers.get(h)]}
    except urllib.error.HTTPError as e:
        body = ''
        try:
            body = e.read(600).decode('utf-8', errors='replace')
        except OSError:
            pass
        return {'status': e.code, 'server': e.headers.get('Server', '') if e.headers else '', 'ctype': e.headers.get('Content-Type', '') if e.headers else '',
                'body': body, 'flags': [h for h in ('cf-mitigated', 'x-datadome', 'x-sucuri-id', 'x-amzn-waf-action', 'x-iinfo') if e.headers and e.headers.get(h)]}
    except Exception as e:  # noqa: BLE001  (a diagnostic: report whatever happened)
        return {'status': 0, 'server': '', 'ctype': '', 'body': '', 'flags': [], 'error': f'{type(e).__name__}: {str(e)[:160]}'}


def page_signals(html, base):
    """What a page tells us about how its scholarship list is made. Pure text work on the HTML we were given."""
    links = []
    for href, inner in LINK.findall(html):
        text = re.sub(r'\s+', ' ', TAGS.sub(' ', inner)).strip()
        full = urllib.parse.urljoin(base, href)
        if SCH_WORD.search(text) or SCH_WORD.search(urllib.parse.urlsplit(full).path):
            links.append((full, text[:80]))
    uniq = list(dict.fromkeys(links))
    host = urllib.parse.urlsplit(base).netloc
    scripts = SCRIPT_SRC.findall(html)
    vend = sorted({v for s in scripts for v in VENDORS if v in s.lower()} | {v for v in VENDORS if f'"{v}' in html.lower()[:200000] and v in ('algolia', 'coveo', 'funnelback')})
    blobs = [name for key, name in BLOBS if key in html]
    apis = list(dict.fromkeys(API_PATH.findall(html)))[:6]
    body_text = re.sub(r'\s+', ' ', TAGS.sub(' ', re.sub(r'<(script|style)\b.*?</\1>', ' ', html, flags=re.S | re.I)))
    return {'links': uniq, 'scripts': len(scripts), 'vendors': vend, 'blobs': blobs, 'apis': apis, 'text_len': len(body_text.strip()),
            'noscript': bool(re.search(r'<noscript', html, re.I)), 'foreign_scripts': sorted({urllib.parse.urlsplit(s).netloc for s in scripts if urllib.parse.urlsplit(s).netloc and urllib.parse.urlsplit(s).netloc != host})[:4]}


def verdict(robots, pages, sm_hits):
    if robots.get('status') == 0 or (robots.get('status', 0) >= 500):
        wall = WALL.search(robots.get('body', '') or '') or robots.get('flags')
        return 'NO ANSWER: robots.txt did not load from the runner' + (' (looks like a security wall)' if wall else '') + '. The reader must stop; nothing to fix in code.'
    loaded = [p for p in pages if p['ok']]
    if not loaded:
        return 'PAGES DID NOT LOAD: ' + '; '.join(f"{p['url'][-50:]} {p['err']}" for p in pages[:3])
    best = max(loaded, key=lambda p: len(p['sig']['links']))
    n = len(best['sig']['links'])
    if n >= 8:
        return f'STATIC LINKS: {n} scholarship-like links on the page; the reader should have found pages. Check the quality filters.'
    if best['sig']['vendors'] or best['sig']['blobs'] or best['sig']['apis'] or best['sig']['text_len'] < 1500:
        extra = 'sitemap lists %d scholarship pages' % sm_hits if sm_hits else 'sitemap has none'
        return f"SCRIPT-BUILT LIST: only {n} links, text {best['sig']['text_len']} chars, hints {best['sig']['vendors'] + best['sig']['blobs']}; {extra}."
    return f'FEW LINKS: {n} scholarship-like links; the list may sit on other pages. Sitemap lists {sm_hits}.'


def probe_urls(a):
    """Look at addresses that are not a university's own: an official listing site, say. Same polite fetcher, same report."""
    ua = f"Universities500Bot/1.0 (+https://universities500.com/bot/{'; ' + a.contact if a.contact else ''})"
    fx = Fetcher(ua, delay=a.delay, deadline=time.monotonic() + 1500)
    print('User-Agent:', ua)
    seen = set()
    for url in a.url:
        host = urllib.parse.urlsplit(url).netloc
        if host not in seen:
            seen.add(host)
            rb = raw_robots(host, ua)
            print(f"\n=== robots.txt of {host}: HTTP {rb['status']} {rb.get('error', '')} server={rb['server']!r}")
            print('  ', re.sub(r'\s+', ' ', rb['body'])[:700])
        res = fx.get(url)
        print(f"--- {url}\n  {'HTTP %s, %d bytes' % (res.status, len(res.body)) if res.ok else 'FAILED: ' + (res.error or '')}")
        if not res.ok:
            continue
        html = res.text
        sig = page_signals(html, res.final_url)
        print(f"  text {sig['text_len']} chars, scripts {sig['scripts']}, vendors {sig['vendors']}, blobs {sig['blobs']}")
        same = [(urllib.parse.urljoin(res.final_url, h), re.sub(r'\s+', ' ', TAGS.sub(' ', t)).strip()[:70]) for h, t in LINK.findall(html)]
        same = [(h, t) for h, t in same if urllib.parse.urlsplit(h).netloc == host and t]
        print(f'  {len(same)} links on the same site; first 12:')
        for h, t in list(dict.fromkeys(same))[:12]:
            print(f'    {t!r} -> {h[:120]}')
        text = re.sub(r'\s+', ' ', TAGS.sub(' ', re.sub(r'<(script|style)\b.*?</\1>', ' ', html, flags=re.S | re.I)))
        print('  visible text starts:', text[:1500])
        try:  # why does the reader see little or no text on a page a browser shows in full?
            import extract as X
            def body_len(sp):
                return len(sp.body.get_text(' ', strip=True)) if sp.body else -1
            full = X.soup_of(html)
            print(f"  reader: body text {body_len(full)} chars as parsed; page.text {len(X.Page(res.final_url, html, 'x', 'x').text)} chars after cleaning")
            for tag in X.DROP_TAGS:
                sp = X.soup_of(html)
                n = len(sp(tag))
                for t in sp(tag):
                    t.decompose()
                if n:
                    print(f"    dropping <{tag}> ({n}): body text {body_len(sp)}")
            sp = X.soup_of(html)
            for el in sp.find_all(attrs={'role': True}):
                if el.get('role') in X.DROP_ROLES and not X._gone(el):
                    el.decompose()
            print(f"    dropping role=navigation/banner/search/...: body text {body_len(sp)}")
            kinds = {}
            for el in X.soup_of(html).find_all(['form', 'nav', 'header', 'footer', 'aside']):
                kinds[el.name] = max(kinds.get(el.name, 0), len(el.get_text(' ', strip=True)))
            print('    largest text inside each chrome tag:', kinds)
            print('    first tags under <body>:', [(c.name, (c.get('id') or '') + '.' + '.'.join(c.get('class') or [])) for c in (full.body.find_all(True, recursive=False)[:8] if full.body else [])])
        except Exception as e:
            print('  reader check failed:', repr(e)[:200])
        for key in ('Award value', 'Closing date', 'Level of study', 'Visit website', 'Eligibility', 'Showing', 'class="card', 'rel="next"'):
            i = html.find(key)
            if i >= 0:
                print(f'  html around {key!r}: ' + re.sub(r'\s+', ' ', html[max(0, i - 160):i + 260]))
        bare = re.sub(r'\s+', ' ', re.sub(r'<svg\b.*?</svg>|<!--.*?-->', '', html, flags=re.S))
        for key, size in (('scholarship-list-card', 3500), ('Scholarship Information', 6000)):
            i = bare.find(key)
            if i >= 0:
                print(f'  MARKUP from {key!r} ({size} chars, svg and comments removed): ' + bare[i:i + size])
        m = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)', html, re.I)
        print('  canonical:', m.group(1) if m else None, '| meta robots:', re.findall(r'<meta[^>]+name=["\']robots["\'][^>]*>', html, re.I)[:1])
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default='')
    ap.add_argument('--country', default='')
    ap.add_argument('--url', action='append', default=[], help='probe these addresses on their own (robots.txt answer, page, links); repeatable')
    ap.add_argument('--delay', type=float, default=3.0)
    ap.add_argument('--contact', default=os.environ.get('CONTACT_EMAIL', ''))
    a = ap.parse_args()
    if a.url:
        return probe_urls(a)
    unis = json.loads((ROOT / 'src/data/universities.json').read_text(encoding='utf-8'))
    seeds = (json.loads((ROOT / 'data/scholarship_seeds.json').read_text(encoding='utf-8')).get('seeds') or {})
    prev = json.loads((ROOT / 'src/data/scholarships.json').read_text(encoding='utf-8')).get('universities', {})
    want = set(filter(None, a.only.split(',')))
    pick = [u for u in unis if u.get('web') and ((u['slug'] in want) if want else (u['country'] == a.country))]
    ua = f"Universities500Bot/1.0 (+https://universities500.com/bot/{'; ' + a.contact if a.contact else ''})"
    fx = Fetcher(ua, delay=a.delay, deadline=time.monotonic() + 3000)
    print('User-Agent:', ua)
    summary = []
    for u in pick:
        host = urllib.parse.urlsplit(u['web']).netloc
        print(f"\n=== {u['name']} ({u['slug']}) {u['web']}   last run: {prev.get(u['slug'], {}).get('status')}")
        rb = raw_robots(host, ua)
        print(f"robots.txt direct: HTTP {rb['status']} {rb.get('error', '')} server={rb['server']!r} flags={rb['flags']} type={rb['ctype'][:40]!r}")
        if rb['status'] != 200 and rb['body']:
            print('  body starts:', re.sub(r'\s+', ' ', rb['body'])[:200])
        if rb['status'] == 200:
            dis = [ln.strip() for ln in rb['body'].splitlines() if re.match(r'(?i)\s*(disallow|crawl-delay|user-agent)\s*:', ln)][:8]
            print('  rules:', ' | '.join(dis))
        urls = list(dict.fromkeys((seeds.get(u['slug']) or {}).get('urls', []) + [u['web']]))
        pages = []
        for url in urls[:3]:
            res = fx.get(url)
            rec = {'url': url, 'ok': res.ok, 'err': res.error or '', 'sig': None}
            if res.ok:
                rec['sig'] = page_signals(res.text, res.final_url)
                s = rec['sig']
                print(f"page {url}\n  HTTP {res.status}, {len(res.body)} bytes, text {s['text_len']} chars, {s['scripts']} scripts, noscript={s['noscript']}")
                print(f"  scholarship-like links: {len(s['links'])}; vendors={s['vendors']} blobs={s['blobs']} foreign={s['foreign_scripts']}")
                for link, text in s['links'][:5]:
                    print(f'    {text[:60]!r} -> {link[:110]}')
                if s['apis']:
                    print('  addresses a script may call:', s['apis'])
            else:
                print(f"page {url}\n  FAILED: {rec['err']}  (robots: {fx.robots_status.get(urllib.parse.urlsplit(url).netloc)} {fx.robots_detail.get(urllib.parse.urlsplit(url).netloc, '')})")
            pages.append(rec)
        sm_hits, samples = 0, []
        try:
            import discover
            scheme, h = 'https', host
            sm = discover.read_sitemaps(fx, scheme, h, lambda x: True) if fx.robots_status.get(h) not in (0, None) else []
            hits = [x for x in sm if SCH_WORD.search(urllib.parse.urlsplit(x).path)]
            sm_hits, samples = len(hits), hits[:5]
            print(f'sitemap: {len(sm)} addresses, {sm_hits} mention scholarships/funding' + (': ' + ' | '.join(s[:90] for s in samples) if samples else ''))
        except Exception as e:  # noqa: BLE001
            print('sitemap: error', type(e).__name__, str(e)[:100])
        v = verdict(rb, pages, sm_hits)
        print('VERDICT:', v)
        summary.append((u['name'], v))
    print('\n==== SUMMARY ====')
    for n, v in summary:
        print(f'{n[:38]:38} {v[:150]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
