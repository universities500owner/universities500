"""Read a university's own website for the links and social accounts a profile needs.

No AI. The home page is read once; its links are scored by what they say and where they point, per role (admissions,
courses, scholarships, faculties, partners, campuses, facts). Each chosen link is then opened and graded:
  verified  the page loads, stays on the university's domain and its title or heading names the role
  weak      loads on the university's domain but the title does not name the role
  external  loads on another domain (for example a national application service)
  failed    does not load, or robots.txt says no
Only verified links go live. Weak and external ones go to a person for a look."""
import json
import re
import urllib.parse

from bs4 import BeautifulSoup

from fetcher import reg_domain

ROLES = {
    'admissions': (
        r'admission|apply|application|enrol|zulassung|bewerb|candidature|inscription|toelating|inschrijv|aanmeld|antagning|ans[oö]kan|opptak|s[oø]knad|kemasukan|permohonan|pendaftaran',
        r'scholar|bursar|stipend|bourse|staff|job|career|vacanc|alumni|phd|doctoral|research degree|graduate research'),
    'courses': (
        r'courses?\b|programmes?\b|programs?\b|degrees?\b|study options|find a course|course finder|studieng[aä]nge|studienangebot|formations?\b|offre de formation|opleidingen|utbildning|studieprogram|sarjana|kursus|undergraduate|postgraduate',
        r'short course|online course|news|alumni|continuing|executive|apprentice|summer|events?\b'),
    'scholarships': (
        r'scholar|bursar|fellowship|financial aid|funding|stipend|studentship|bourses?\b|beurzen|stipendi|beasiswa|biasiswa|fees and funding',
        r'news|alumni|staff|research funding|grants? for researchers'),
    'faculties': (
        r'faculties|faculty\b|schools\b|colleges\b|departments|academic units|fakult[aä]ten|fachbereiche|facult[eé]s|composantes|faculteiten|fakulteter|institutioner|fakultas|fakulti',
        r'news|alumni|staff|careers|jobs|events'),
    'partners': (
        r'industry|partnerships?|partners\b|collaborat|corporate|employers?|business engagement|industry engagement|kooperation|partenariat|entreprises|samenwerking|n[aä]ringsliv|samarbeid|industri',
        r'news|alumni|staff|careers|jobs|events|research funding'),
    'campuses': (
        r'campus|campuses|locations|standorte|campussen|campuser',
        r'virtual tour|open day|events?\b|news|jobs|parking|map of|safety'),
    'facts': (
        r'facts and figures|facts & figures|key facts|quick facts|at a glance|statistics|university in numbers|in numbers|zahlen und fakten|zahlen|chiffres cl[eé]s|chiffres|cijfers|siffror|tall og fakta|fakta om',
        r'news|alumni|jobs|careers|contact|events|merger|proposal|claims|employment|graduate outcomes|insertion'),
}
ROLES = {k: (re.compile(p, re.I), re.compile(n, re.I)) for k, (p, n) in ROLES.items()}
GUESS = {
    'admissions': ['/admissions/', '/apply/', '/study/apply/', '/international/admissions/'],
    'courses': ['/courses/', '/programmes/', '/programs/', '/study/', '/degrees/'],
    'scholarships': ['/scholarships/', '/fees-and-funding/', '/funding/', '/study/scholarships/'],
    'faculties': ['/faculties/', '/schools/', '/academics/', '/about/faculties/'],
    'partners': ['/industry/', '/partnerships/', '/business/', '/industry-partnerships/'],
    'campuses': ['/campuses/', '/about/campuses/', '/our-campuses/', '/campus/'],
    'facts': ['/about/facts-and-figures/', '/about/facts/', '/facts-and-figures/', '/about/key-facts/'],
}
JUNK_PATH = re.compile(
    r'/(?:news|blog|events?|stories|story|press|articles?|alumni|staff|jobs|careers|people|tag|category|feed|login|search|cart|shop|gallery|video|podcast|privacy|terms|cookies?|sitemap)(?:/|$)|'
    r'\.(?:pdf|docx?|xlsx?|pptx?|zip|jpe?g|png|gif|mp4|svg)$', re.I)
TRACKING = re.compile(r'^(?:utm_|fbclid|gclid|mc_|_ga|ref$|source$)', re.I)
FACULTY_WORD = re.compile(
    r'\b(faculty|faculties|school|college|department|institute|facult[eé]|fakult[aä]t|facultad|fakulteit|fakultet|fakulti|fachbereich)\b', re.I)
FACULTY_BAD = re.compile(r'\b(all|view|find|explore|our|about|contact|news|staff|apply|visit|home|events?|search|portal|login|map|jobs)\b', re.I)

SOCIAL = {
    'instagram': re.compile(r'^https?://(?:www\.)?instagram\.com/([A-Za-z0-9_.]{2,30})/?(?:[?#].*)?$', re.I),
    'linkedin': re.compile(r'^https?://(?:[a-z]{2,3}\.)?linkedin\.com/(school|company|edu)/([^/?#]+)/?', re.I),
    'youtube': re.compile(r'^https?://(?:www\.|m\.)?youtube\.com/(@[\w.\-]+|channel/[\w\-]+|user/[\w\-]+|c/[\w\-]+)/?', re.I),
}
INSTAGRAM_SKIP = {'p', 'reel', 'reels', 'explore', 'accounts', 'share', 'stories', 'tv', 'about', 'legal', 'developer'}

NUM = r'(\d{1,3}(?:[,.   ]\d{3})+|\d{4,6})'
STUDENTS = re.compile(
    NUM + r'\s*\+?\s*(?:total\s+|enrolled\s+|full[- ]time\s+|current\s+)?(?:(international|overseas|foreign|internationale|ausl[aä]ndische)\s+)?'
    r'(?:students|learners|[eé]tudiants|[eé]tudiantes|studierende|studenten|studenter|studenti|pelajar|mahasiswa)\b', re.I)


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


def page_info(html, base_url):
    """title, first heading, every link (with whether it sits in the footer), JSON-LD sameAs links, and the visible text."""
    soup = soup_of(html)
    title = soup.title.get_text(' ', strip=True) if soup.title else ''
    h1 = soup.find('h1')
    h1 = h1.get_text(' ', strip=True) if h1 else ''
    links = []
    for a in soup.find_all('a', href=True):
        href = (a['href'] or '').strip()
        if not href or href.startswith(('#', 'mailto:', 'tel:', 'javascript:')):
            continue
        url = urllib.parse.urljoin(base_url, href)
        if not url.startswith(('http://', 'https://')):
            continue
        text = a.get_text(' ', strip=True) or a.get('aria-label') or a.get('title') or ''
        foot = a.find_parent('footer') is not None or a.find_parent(attrs={'role': 'contentinfo'}) is not None
        links.append({'url': canon(url), 'text': re.sub(r'\s+', ' ', text)[:140], 'footer': foot})
    same_as = []
    for s in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(s.string or '')
        except ValueError:
            continue
        stack = [data]
        while stack:
            d = stack.pop()
            if isinstance(d, list):
                stack += d
            elif isinstance(d, dict):
                v = d.get('sameAs')
                same_as += [v] if isinstance(v, str) else [x for x in (v or []) if isinstance(x, str)]
                stack += [x for x in d.values() if isinstance(x, (dict, list))]
    lang = ((soup.html.get('lang') if soup.html else '') or '').lower()
    english = ''
    for l in soup.find_all('link', attrs={'rel': 'alternate', 'hreflang': True}):
        if re.match(r'^en(?:[-_]|$)', (l.get('hreflang') or '').lower()) and l.get('href'):
            english = canon(urllib.parse.urljoin(base_url, l['href']))
            break
    for t in soup(['script', 'style', 'noscript', 'svg', 'template']):
        t.decompose()
    text = re.sub(r'\s+', ' ', soup.get_text(' ', strip=True))
    return {'title': title, 'h1': h1, 'links': links, 'same_as': same_as, 'text': text, 'lang': lang, 'english': english}


def role_candidates(role, links, home_reg, limit=3):
    """Best links for a role: [{'url','text','score'}], highest score first."""
    pos, neg = ROLES[role]
    best = {}
    for l in links:
        path = urllib.parse.unquote(urllib.parse.urlsplit(l['url']).path).lower().replace('-', ' ').replace('_', ' ')
        text = l['text'].lower() if len(l['text']) <= 60 else ''
        s = 0.0
        if pos.search(text):
            s += 3
        if pos.search(path):
            s += 2
        if s == 0:
            continue
        if neg.search(text) or neg.search(path):
            s -= 4
        if JUNK_PATH.search(l['url']):
            s -= 5
        s -= 0.25 * max(0, path.strip('/').count('/') - 1)
        same = reg_domain(urllib.parse.urlsplit(l['url']).netloc) == home_reg
        s += 1 if same else -1
        if l['footer']:
            s += 0.5
        if s <= 1.5:
            continue
        if l['url'] not in best or s > best[l['url']]['score']:
            best[l['url']] = {'url': l['url'], 'text': l['text'], 'score': round(s, 2)}
    return sorted(best.values(), key=lambda x: -x['score'])[:limit]


def same_account(kind, wd, handle):
    """True/False when Wikidata and the site give the same kind of identifier (both a channel id, both a name); None when they
    are different kinds (a YouTube channel id against an @name, a LinkedIn number against a slug) and so cannot be compared."""
    if not wd:
        return None
    wd, handle = wd.lower(), handle.lower()
    if kind == 'youtube':
        def form(x):
            return 'id' if re.match(r'^(?:channel/)?uc[\w-]{20,}$', x, re.I) else 'name'
        a, b = re.sub(r'^(?:channel|user|c)/', '', wd), re.sub(r'^(?:channel|user|c)/', '', handle)
        return (a == b) if form(a) == form(b) else None
    if kind == 'linkedin':
        return (wd == handle) if wd.isdigit() == handle.isdigit() else None
    return wd == handle


def socials(links, same_as, wikidata):
    """Official social accounts. Order of trust: footer link, JSON-LD sameAs, other link. `agree` says whether Wikidata gives
    the same account. Facebook/X are not collected (not asked for)."""
    found = {k: [] for k in SOCIAL}
    pool = [(l['url'], 'footer' if l['footer'] else 'page') for l in links] + [(u, 'jsonld') for u in same_as]
    for url, src in pool:
        for kind, rx in SOCIAL.items():
            m = rx.match(url)
            if not m:
                continue
            if kind == 'instagram':
                handle = m.group(1)
                if handle.lower() in INSTAGRAM_SKIP:
                    continue
                canon_url = f'https://www.instagram.com/{handle}/'
            elif kind == 'linkedin':
                handle = m.group(2)
                canon_url = f'https://www.linkedin.com/{m.group(1)}/{handle}/'
            else:
                handle = m.group(1)
                canon_url = f'https://www.youtube.com/{handle}'
            found[kind].append({'url': canon_url, 'handle': handle.lower().lstrip('@'), 'from': src})
    out = {}
    rank = {'footer': 0, 'jsonld': 1, 'page': 2}
    for kind, rows in found.items():
        if not rows:
            continue
        counts = {}
        for r in rows:
            counts[r['handle']] = counts.get(r['handle'], 0) + 1
        rows.sort(key=lambda r: (rank[r['from']], -counts[r['handle']]))
        top = rows[0]
        distinct = sorted({r['handle'] for r in rows})
        wd = (wikidata.get(kind) or '').lower().lstrip('@')
        top = dict(top, others=[h for h in distinct if h != top['handle']][:4], agree=same_account(kind, wd, top['handle']))
        out[kind] = top
    return out


def student_numbers(text):
    """Student counts a page states in words: [{'v','asof','intl','snippet'}]. Only a second opinion for the Wikidata figure."""
    out = []
    for m in STUDENTS.finditer(text):
        try:
            v = int(re.sub(r'\D', '', m.group(1)))
        except ValueError:
            continue
        if not 500 <= v <= 500000:
            continue
        a, b = max(0, m.start() - 90), min(len(text), m.end() + 90)
        near = text[a:b]
        years = [int(y) for y in re.findall(r'\b(20[12]\d)\b', near)]
        out.append({'v': v, 'asof': max(years) if years else None, 'intl': bool(m.group(2)), 'snippet': near.strip()})
    return out[:12]


CAMPUS_NAME = re.compile(
    r"^(?!(?i:our|all|view|find|explore|virtual|visit|other|global|online|the|campus)\b)"
    r"[A-Z\u00C0-\u00DE][\w'’.&-]*(?: [A-Z\u00C0-\u00DE&][\w'’.&-]*){0,3} [Cc]ampus$|^[Cc]ampus (?:de |du |d'|di |van )?[A-Z\u00C0-\u00DE][\w'’-]+(?: [A-Z\u00C0-\u00DE][\w'’-]+)?$")


def names_from_links(links, rx, home_reg, cap=40):
    """Faculty or campus names taken from the link text of a hub page: [{'name','url'}]."""
    seen = {}
    for l in links:
        t = l['text'].strip()
        if not 4 <= len(t) <= 70 or not rx.search(t) or FACULTY_BAD.search(t) and not re.search(r'faculty|school|college|department', t, re.I):
            continue
        if rx.pattern == CAMPUS_NAME.pattern and not CAMPUS_NAME.match(t):
            continue
        if JUNK_PATH.search(l['url']) or t.lower() in seen:
            continue
        seen[t.lower()] = {'name': t, 'url': l['url'], 'sameSite': reg_domain(urllib.parse.urlsplit(l['url']).netloc) == home_reg}
    return list(seen.values())[:cap]


def grade(res, role, home_reg):
    """verified / weak / external / failed for a fetched page."""
    if not res.ok:
        return 'failed', ''
    info = page_info(res.text, res.final_url) if res.text else {'title': '', 'h1': ''}
    name_ok = bool(ROLES[role][0].search(f"{info['title']} {info['h1']}"))
    same = reg_domain(urllib.parse.urlsplit(res.final_url).netloc) == home_reg
    if not same:
        return 'external', info['title']
    return ('verified' if name_ok else 'weak'), info['title']


def crawl(fetcher, home_url, cap_text=9000):
    """Everything the site gives us for one university. Never raises; failures are recorded in the result."""
    out = {'home': {'url': home_url}, 'links': {}, 'social': {}, 'faculties': [], 'campuses': [], 'students2': [], 'cache': {}}
    res = fetcher.get(home_url)
    out['home'].update(final=res.final_url, status=res.status, error=res.error or '', robots=res.robots_blocked)
    if not res.ok or not res.text:
        return out
    home_reg = reg_domain(urllib.parse.urlsplit(res.final_url).netloc)
    out['home']['reg'] = home_reg
    home = page_info(res.text, res.final_url)
    extra_links, extra_same_as = [], []
    if home['lang'] and not home['lang'].startswith('en'):
        # a home page in another language: use its English version when it names one on the same domain,
        # and keep the original page's links too (social links often sit only on the national-language page)
        eng = home['english'] or next((l['url'] for l in home['links'] if l['text'].strip().lower() in ('english', 'en', 'in english')), '')
        if eng and reg_domain(urllib.parse.urlsplit(eng).netloc) == home_reg and eng != res.final_url:
            r2 = fetcher.get(eng)
            if r2.ok and r2.text:
                extra_links, extra_same_as = home['links'], home['same_as']
                res, home = r2, page_info(r2.text, r2.final_url)
                out['home']['english'] = r2.final_url
    out['home']['title'] = home['title']
    out['cache']['home'] = home['text'][:cap_text]
    out['social_links'] = home['links'] + extra_links
    out['_same_as'] = home['same_as'] + extra_same_as
    base = urllib.parse.urlsplit(res.final_url)
    root = f'{base.scheme}://{base.netloc}'

    for role in ROLES:
        cands = [dict(c, source='homepage') for c in role_candidates(role, home['links'], home_reg)]
        if not cands:
            cands = [{'url': root + g, 'text': '', 'score': 0, 'source': 'guess'} for g in GUESS[role][:3]]
        chosen = None
        tried = []
        for c in cands[:3]:
            r = fetcher.get(c['url'])
            g, title = grade(r, role, home_reg)
            tried.append({'url': c['url'], 'grade': g, 'status': r.status, 'error': r.error or ''})
            if g in ('verified', 'weak', 'external'):
                chosen = dict(c, grade=g, status=r.status, title=title[:140], final=r.final_url)
                if g == 'verified':
                    pg = page_info(r.text, r.final_url)
                    if role in ('facts', 'partners', 'campuses', 'faculties', 'scholarships', 'admissions', 'courses'):
                        out['cache'][role] = pg['text'][:cap_text]
                    if role == 'faculties':
                        out['faculties'] = names_from_links(pg['links'], FACULTY_WORD, home_reg)
                    if role == 'campuses':
                        out['campuses'] = names_from_links(pg['links'], CAMPUS_NAME, home_reg, 12)
                    if role == 'facts':
                        out['students2'] += student_numbers(pg['text'])
                break
        out['links'][role] = chosen or {'grade': 'failed', 'tried': tried}
        if chosen:
            out['links'][role]['tried'] = tried
    out['students2'] += student_numbers(home['text'])
    return out
