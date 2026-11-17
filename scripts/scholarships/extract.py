"""Turn one HTML page into scholarship records. No AI: structure, headings and patterns only.

Every field is copied from the page. If a field cannot be read with confidence it stays empty,
and the site shows 'Check the official page' for it."""
import hashlib
import json
import re
import urllib.parse

from bs4 import BeautifulSoup

import details as Det
import quality as Q
import textutil as T

DROP_TAGS = ['script', 'style', 'noscript', 'nav', 'header', 'footer', 'aside', 'form', 'svg', 'iframe', 'template', 'button', 'select', 'dialog']
DROP_ROLES = ['navigation', 'banner', 'contentinfo', 'search', 'complementary']
DROP_CLASS = re.compile(r'(?:^|[\s_-])(?:cookie|consent|breadcrumb|skip|sidebar|share|social|related|newsletter|megamenu|mega-menu|site-nav|main-nav|footer|header-nav|menu)(?:$|[\s_-])', re.I)
LABELS = re.compile(r'^(?:application )?(?:deadlines?|closing dates?|closes?|opens?|opening dates?|value|amount|worth|funding|award|awards|eligibility|who can apply|how much|key dates?|dates?)$', re.I)
ELIG_HEAD = re.compile(
    r"^(?:am i eligible|are you eligible|eligibility(?: criteria| requirements)?|who (?:can|may|is eligible to) apply|who is eligible|"
    r"selection criteria|criteria|requirements|entry requirements|to be eligible|eligible (?:applicants|students)|what (?:you need|are the criteria))\b", re.I)
APPLY_TEXT = re.compile(r'^(?:apply(?: now| online| here| today| for this scholarship)?|how to apply|application (?:form|portal|process)|start (?:your )?application|apply for (?:the |this )?(?:scholarship|award|bursary))\b', re.I)
SCH_HINT = re.compile(r'schol|bursar|fellow|studentship|waiver|award|grant|funding|financial-aid|tuition-discount|stipend', re.I)
JUNK_PATH = re.compile(r'/(?:news|blog|events?|stories|story|press|articles?|alumni|staff|jobs|careers|people|tag|category|feed|login|search|cart|shop|gallery|video|podcast)(?:/|$)|\.(?:pdf|docx?|xlsx?|pptx?|zip|jpe?g|png|gif|mp4)$|/page/\d+|[?&](?:page|p|sort|filter)=', re.I)
TRACKING = re.compile(r'^(?:utm_|fbclid|gclid|mc_|_ga|ref$|source$)', re.I)


def canon(url):
    p = urllib.parse.urlsplit(url)
    q = [(k, v) for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True) if not TRACKING.match(k)]
    path = re.sub(r'/index\.(?:html?|php|aspx?)$', '/', p.path)
    return urllib.parse.urlunsplit((p.scheme.lower(), p.netloc.lower(), path or '/', urllib.parse.urlencode(q), ''))


def soup_of(html):
    try:
        return BeautifulSoup(html, 'lxml')
    except Exception:
        return BeautifulSoup(html, 'html.parser')


def meta(soup, *names):
    for n in names:
        el = soup.find('meta', attrs={'name': n}) or soup.find('meta', attrs={'property': n})
        if el and el.get('content'):
            c = T.clean(el['content'])
            if c:
                return c
    return ''


def _gone(el):
    """True for an element that went with a parent we already removed (bs4 empties its attributes, so any later .get() fails)."""
    return el.attrs is None or getattr(el, 'decomposed', False)


# Page chrome that can also be a wrapper around the whole page: many older sites put <form runat="server"> around the body,
# and a markup slip can leave a <nav> or <header> open so that the rest of the page ends up inside it.
WRAPPER_TAGS = ('form', 'nav', 'header', 'footer', 'aside')


def _holds_the_page(el):
    if el.find(['main', 'article']) or el.find(attrs={'role': 'main'}):
        return True
    # a form that holds the page's own heading and a lot of text is the page, not a search box
    return el.name == 'form' and bool(el.find('h1')) and len(el.get_text(' ', strip=True)) > 1500


def main_node(soup):
    for t in soup(DROP_TAGS):
        if _gone(t):
            continue
        if t.name in WRAPPER_TAGS and _holds_the_page(t):
            t.unwrap()    # keep what is inside; the real menus and search boxes inside it are dropped below or by their own tags
        else:
            t.decompose()
    for el in soup.find_all(attrs={'role': True}):
        if not _gone(el) and el.get('role') in DROP_ROLES:
            el.decompose()
    for el in soup.find_all(class_=DROP_CLASS):
        # only drop small chrome blocks, never a wrapper that holds the article
        if not _gone(el) and len(el.get_text(' ', strip=True)) < 1500 and el.name not in ('body', 'html', 'main', 'article'):
            el.decompose()
    for sel in ('main', '[role=main]', 'article', '#main-content', '#content', '#main', '.main-content', '.content'):
        node = soup.select_one(sel)
        if node and len(node.get_text(' ', strip=True)) > 200:
            return node
    return soup.body or soup


def lines_of(node):
    raw = [T.clean(x) for x in node.get_text('\n').split('\n')]
    raw = [x for x in raw if x]
    out, i = [], 0
    while i < len(raw):
        line = raw[i]
        if i + 1 < len(raw) and len(line) <= 32 and LABELS.match(line.rstrip(':')):
            out.append(line.rstrip(':') + ': ' + raw[i + 1])
            i += 2
            continue
        out.append(line)
        i += 1
    return out


def flat_text(lines):
    parts = []
    for l in lines:
        parts.append(l if re.search(r'[.!?:;]$', l) else l + '.')
    return ' '.join(parts)


def _generic(name):
    return not (name or '').strip() or Q.is_generic(name)


class Page:
    """What we learned from one HTML page."""

    def __init__(self, url, html, country=None, site_name=None):
        self.url = url
        soup = soup_of(html)
        # every link on the page, taken before we strip menus and footers (needed to find scholarship menus on home pages)
        self.all_links = []
        for a in soup.find_all('a', href=True):
            href = a['href'].strip()
            if href.startswith(('mailto:', 'tel:', 'javascript:', '#')):
                continue
            self.all_links.append((urllib.parse.urljoin(url, href), T.clean(a.get_text(' '))))
        self.title_tag = T.clean(soup.title.get_text()) if soup.title else ''
        self.og_title = meta(soup, 'og:title')
        self.meta_desc = meta(soup, 'description', 'og:description')
        self.canonical = ''
        c = soup.find('link', rel='canonical')
        if c and c.get('href'):
            self.canonical = urllib.parse.urljoin(url, c['href'])
        self.robots_meta = meta(soup, 'robots').lower()
        self.lang = (soup.html.get('lang') if soup.html else '') or ''
        h1 = soup.find('h1')
        self.h1 = T.clean(h1.get_text(' ')) if h1 else ''
        self.main = main_node(soup)
        self.lines = lines_of(self.main)
        self.text = flat_text(self.lines)[:40000]
        self.country = country
        self.site_name = site_name
        self.links = []
        for a in self.main.find_all('a', href=True):
            href = a['href'].strip()
            if href.startswith(('mailto:', 'tel:', 'javascript:', '#')):
                continue
            self.links.append((urllib.parse.urljoin(url, href), T.clean(a.get_text(' '))))
        self.soup = soup

    @property
    def name(self):
        """The scholarship's name. The first heading is not always it: some sites put the section name ("Scholarships",
        "Scholarship details") in the h1 and the scholarship's own name in the page title or a second heading."""
        first = T.clean_title(self.h1 or self.og_title or self.title_tag, self.site_name)
        if not _generic(first):
            return first
        heads = [T.clean(h.get_text(' ')) for h in self.main.find_all(['h2', 'h3'])[:4]]
        for c in (self.og_title, self.title_tag, *heads):
            n = T.clean_title(c, self.site_name) if c else ''
            if n and T.NAME_WORDS.search(n) and not _generic(n) and len(n) <= 140:
                return n
        return first

    def scholarship_links(self, same_domain):
        out = []
        for href, text in self.links:
            path = urllib.parse.urlsplit(href).path
            if not same_domain(href) or JUNK_PATH.search(href):
                continue
            if SCH_HINT.search(path) or (T.NAME_WORDS.search(text) and len(text) > 8):
                out.append((canon(href), text))
        seen, uniq = set(), []
        for h, t in out:
            if h not in seen:
                seen.add(h)
                uniq.append((h, t))
        return uniq


def find_eligibility(page):
    items = []
    soup = page.main
    heads = soup.find_all(['h2', 'h3', 'h4', 'h5', 'h6', 'dt', 'summary', 'strong', 'b', 'th'])
    for h in heads:
        txt = T.clean(h.get_text(' '))
        if len(txt) > 70 or not ELIG_HEAD.search(txt.rstrip(':')):
            continue
        if h.name in ('th', 'dt'):
            sib = h.find_next_sibling(['td', 'dd'])
            if sib:
                lis = [T.clean(li.get_text(' ')) for li in sib.find_all('li')]
                items = lis or [T.clean(sib.get_text(' '))]
        elif h.name == 'summary' and h.parent is not None:
            lis = [T.clean(li.get_text(' ')) for li in h.parent.find_all('li')]
            items = lis or [T.clean(p.get_text(' ')) for p in h.parent.find_all('p')]
        else:
            level = int(h.name[1]) if re.fullmatch(r'h[2-6]', h.name) else 9
            lis, ps = [], []
            for el in h.find_all_next(True):
                if re.fullmatch(r'h[1-6]', el.name) and (int(el.name[1]) <= min(level, 6)):
                    break
                if el.name == 'li' and el.parent is not None and el.parent.name in ('ul', 'ol'):
                    t = T.clean(el.get_text(' '))
                    if t:
                        lis.append(t)
                elif el.name == 'p':
                    t = T.clean(el.get_text(' '))
                    if len(t) > 25:
                        ps.append(t)
                if len(lis) >= 12 or len(ps) >= 6:
                    break
            items = lis or ps
        items = [i for i in items if i and len(i) > 8]
        if items:
            break
    out, total = [], 0
    for i in items[:10]:
        i = i[:300]
        if total + len(i) > 1400:
            break
        out.append(i)
        total += len(i)
    return out


def find_description(page):
    d = page.meta_desc
    if d and 50 <= len(d) <= 400 and not re.search(r'cookie|javascript|home page|welcome to', d, re.I):
        return d[:320]
    h1 = page.soup.find('h1')
    node = h1 if h1 else page.main
    for p in node.find_all_next('p', limit=8):
        t = T.clean(p.get_text(' '))
        if len(t) >= 70 and not re.search(r'cookie|©|all rights reserved', t, re.I):
            return t[:320].rsplit(' ', 1)[0] + ('…' if len(t) > 320 else '')
    return None


def find_apply_url(page):
    best = None
    for a in page.main.find_all('a', href=True):
        t = T.clean(a.get_text(' '))
        href = a['href'].strip()
        if href.startswith(('mailto:', 'tel:', 'javascript:', '#')) or not t:
            continue
        if APPLY_TEXT.search(t):
            return canon(urllib.parse.urljoin(page.url, href))
    return best


def _hash(rec):
    keys = ('name', 'value', 'deadline', 'deadlineText', 'opens', 'rolling', 'eligibility', 'description', 'applyUrl', 'levels',
            'awards', 'duration', 'covers', 'applyMode', 'india')
    return hashlib.sha1(json.dumps({k: rec.get(k) for k in keys}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]


def make_record(*, name, provider, provider_slug, provider_type, country, url, text, today, origin,
                apply_url=None, description=None, eligibility=None, levels=None, intl=None, row_dates=None, row_value=None,
                lines=None, detail_text=None):
    dates = T.find_dates(text)
    if row_dates:
        dates['deadlines'] = row_dates.get('deadlines', []) + dates['deadlines']
        dates['partial'] = row_dates.get('partial', []) + dates['partial']
    dl = T.choose_deadline(dates['deadlines'], today)
    op = T.choose_open(dates['opens'], dl['iso'] if dl else None, today)
    value = row_value or T.find_value(text, country)
    deadline_text = None
    if dl:
        deadline_text = dl['ctx']
    elif dates['partial']:
        deadline_text = dates['partial'][0]['text']
    rec = {
        'name': name,
        'provider': provider,
        'providerSlug': provider_slug,
        'providerType': provider_type,
        'country': country,
        'levels': levels or [],
        'value': value,
        'deadline': dl['iso'] if dl else None,
        'deadlineText': deadline_text,
        'deadlinePartial': (dates['partial'][0]['text'] if (not dl and dates['partial']) else None),
        'opens': op,
        'rolling': bool(dates['rolling']),
        'eligibility': eligibility or [],
        'description': description,
        'url': canon(url),
        'applyUrl': apply_url,
        'origin': origin,
        'intl': intl,
    }
    rec.update(Det.extra(text if detail_text is None else detail_text, lines, apply_url))
    miss = Det.missed(text, not (dl or dates['partial'] or dates['rolling']), not value)
    if miss:
        rec['_miss'] = miss  # for the run log only; run.py removes it before saving
    rec['hash'] = _hash(rec)
    rec['id'] = hashlib.sha1(f"{provider_slug or provider}|{rec['url']}|{name.lower()}".encode()).hexdigest()[:12]
    return rec


def detail_record(page, uni, today, same_domain=None, intl_hint=False):
    """One scholarship from one page, or (None, reason)."""
    name = page.name
    if not name or len(name) < 6 or len(name) > 140:
        return None, 'no-name'
    if not T.NAME_WORDS.search(name):
        return None, 'name-not-a-scholarship'
    why = Q.name_problem(name, today) or Q.url_problem(page.url)
    if why:
        return None, why
    if 'noindex' in page.robots_meta and False:
        return None, 'noindex'
    text = page.text
    if T.ONLINE_ONLY.search(name):
        return None, 'online-only'
    levels, phd = T.detect_levels(text)
    if not levels:
        return None, 'phd-only' if phd else 'no-level'
    intl = T.detect_international(text)
    path = urllib.parse.urlsplit(page.url).path.lower()
    if intl == 'unclear' and (intl_hint or re.search(r'international|overseas|global|non-?eu|abroad|worldwide', path)):
        intl = 'yes'  # the page sits under an international section, or was linked from one. A page that says "home students only" still counts as no
    if intl == 'no':
        return None, 'domestic-only'
    if intl != 'yes':
        return None, 'international-not-stated'
    rec = make_record(
        name=name, provider=uni['name'], provider_slug=uni['slug'], provider_type='university', country=uni['country'],
        url=page.url, text=text, today=today, origin='page', apply_url=find_apply_url(page),
        description=find_description(page), eligibility=find_eligibility(page), levels=levels, intl=intl,
        lines=page.lines)
    if not (rec['value'] or rec['deadline'] or rec['deadlinePartial'] or rec['rolling'] or rec['eligibility']):
        return None, 'no-details'
    return rec, 'ok'


HEAD_NAME = re.compile(r'scholarship|award|bursary|name|programme|program|title|fellowship|grant', re.I)
HEAD_VAL = re.compile(r'amount|value|worth|funding|benefit|covers|reward', re.I)
HEAD_DL = re.compile(r'deadline|closing|closes|close|due|apply by|application date', re.I)
HEAD_EL = re.compile(r'eligib|criteria|who|requirement', re.I)


def table_records(page, uni, today, intl_hint=False):
    """Scholarships listed as rows of a table on one page."""
    out = []
    page_levels, page_phd = T.detect_levels(page.text)
    page_intl = T.detect_international(page.text)
    if page_intl == 'unclear' and intl_hint:
        page_intl = 'yes'
    for table in page.main.find_all('table'):
        rows = table.find_all('tr')
        if len(rows) < 2:
            continue
        head = [T.clean(c.get_text(' ')) for c in rows[0].find_all(['th', 'td'])]
        if not head:
            continue
        ni = next((i for i, h in enumerate(head) if HEAD_NAME.search(h)), None)
        vi = next((i for i, h in enumerate(head) if HEAD_VAL.search(h)), None)
        di = next((i for i, h in enumerate(head) if HEAD_DL.search(h)), None)
        ei = next((i for i, h in enumerate(head) if HEAD_EL.search(h)), None)
        if ni is None or (vi is None and di is None):
            continue
        for tr in rows[1:60]:
            cells = tr.find_all(['td', 'th'])
            if len(cells) <= ni:
                continue
            name = T.clean(cells[ni].get_text(' '))
            if len(name) < 5 or len(name) > 140:
                continue
            row_text = ' '.join(T.clean(c.get_text(' ')) for c in cells)
            levels, phd = T.detect_levels(row_text)
            levels = levels or page_levels
            if not levels:
                continue
            intl = T.detect_international(row_text)
            if intl == 'unclear':
                intl = page_intl
            if intl != 'yes':
                continue
            a = cells[ni].find('a', href=True) or tr.find('a', href=True)
            link = urllib.parse.urljoin(page.url, a['href']) if a else page.url
            if Q.name_problem(name, today) or Q.url_problem(link, page.url):
                continue
            val = None
            if vi is not None and vi < len(cells):
                vtxt = T.clean(cells[vi].get_text(' '))
                val = T.find_value(vtxt + '.', uni['country']) or ({'display': vtxt[:80], 'context': vtxt[:200]} if vtxt and len(vtxt) <= 80 else None)
            row_dates = None
            if di is not None and di < len(cells):
                dtxt = 'Deadline: ' + T.clean(cells[di].get_text(' '))
                dd = T.find_dates(dtxt)
                row_dates = {'deadlines': dd['deadlines'], 'partial': dd['partial']}
            elig = []
            if ei is not None and ei < len(cells):
                e = T.clean(cells[ei].get_text(' '))
                if len(e) > 8:
                    elig = [e[:300]]
            rec = make_record(
                name=name, provider=uni['name'], provider_slug=uni['slug'], provider_type='university', country=uni['country'],
                url=link, text='', today=today, origin='table', eligibility=elig, levels=levels, intl=intl,
                row_dates=row_dates, row_value=val, detail_text=row_text)
            if not (rec['value'] or rec['deadline'] or rec['deadlinePartial'] or rec['eligibility']):
                continue
            rec['sourcePage'] = canon(page.url)
            out.append(rec)
    return out


def looks_like_listing(page, same_domain):
    links = page.scholarship_links(same_domain)
    name = page.name
    plural = bool(re.search(r'\b(?:scholarships|bursaries|awards|fellowships|grants|studentships)\b', name, re.I))
    generic = bool(re.search(r'\b(?:funding|financial (?:aid|support)|fees|search|finder|overview|all|list|directory|options|opportunities)\b', name, re.I))
    n = len(links)
    return (n >= 12) or (plural and n >= 6) or (generic and n >= 4), links
