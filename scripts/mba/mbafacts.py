"""Read the plain facts of an MBA programme page: length, tuition, work experience, test, English, start, deadlines, degree, employment report.

No AI. Every value is copied from a sentence on the page, and the sentence is kept next to it as `q`, so the site can show
"The page says: ..." and anyone can check it. A value whose digits or names are not in its own sentence is dropped (see `verify`).
A fact that cannot be read with confidence stays empty and the site says "Not stated".
"""
import re
import urllib.parse

import textutil as T   # scripts/scholarships/textutil.py (the caller puts it on the path)
import facts as CF     # scripts/courses/facts.py

NUMW = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'twelve': 12, 'fifteen': 15}
NUM = r"(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|twelve|fifteen)"
QMAX = 240
FULL_MONTH = {'Jan': 'January', 'Feb': 'February', 'Mar': 'March', 'Apr': 'April', 'May': 'May', 'Jun': 'June', 'Jul': 'July', 'Aug': 'August', 'Sep': 'September', 'Oct': 'October', 'Nov': 'November', 'Dec': 'December'}


def _n(tok):
    tok = tok.lower()
    return NUMW.get(tok) if tok in NUMW else int(tok)


# ---------------- work experience ----------------
EXP_WORD = re.compile(r"\b(?:work|professional|managerial|management|business|full[- ]time|post[- ]graduat\w+|employment)\b[^.]{0,40}\bexperience\b|\bexperience\b[^.]{0,30}\byears?\b|\byears?\b[^.]{0,30}\bexperience\b", re.I)
EXP_MIN = [
    re.compile(rf"\b(?:minimum|at least|a minimum of|minimum of|no less than|not less than)\s+(?:of\s+)?(?:{NUM}|\w+\s+\({NUM}\))\s*(?:\(\d+\)\s*)?years?", re.I),
    re.compile(rf"\bminimum\s+{NUM}\s+years?", re.I),
    re.compile(rf"\b{NUM}\s*\+\s*years?", re.I),
    re.compile(rf"\b{NUM}\s+or more years?", re.I),
    re.compile(rf"\bmin\.?\s+{NUM}\s+years?", re.I),
]
EXP_RANGE = re.compile(rf"\b{NUM}\s*(?:to|-|–)\s*{NUM}\s*years?", re.I)
EXP_NOT = re.compile(r"\b(?:visa|post[- ]study|graduate route|alumni|average|median|class profile|on average|typical(?:ly)? (?:class|student)|ago)\b", re.I)


def find_experience(sentences_):
    """{min, max, t, q} from a sentence about years of work experience, or None. Averages of a class are not requirements, so they are skipped."""
    for s in sentences_[:500]:
        if len(s) > 320 or not EXP_WORD.search(s) or EXP_NOT.search(s):
            continue
        r = EXP_RANGE.search(s)
        if r and 'experience' in s.lower():
            lo, hi = _n(r.group(1)), _n(r.group(2))
            if 0 <= lo < hi <= 20:
                return {'min': lo, 'max': hi, 't': f'{lo} to {hi} years', 'q': s[:QMAX]}
        for rx in EXP_MIN:
            m = rx.search(s)
            if m:
                tok = next((g for g in m.groups() if g), None)
                if tok is None:
                    continue
                n = _n(tok)
                if 0 < n <= 20:
                    return {'min': n, 'max': None, 't': f'At least {n} year{"s" if n != 1 else ""}', 'q': s[:QMAX]}
    return None


# ---------------- tuition ----------------
AMT_YEAR = re.compile(r"\b(20\d\d)\s*[-–/]\s*(\d\d)\b|\b(?:for|in|from)\s+(20\d\d)\b|\b(20\d\d)\s+(?:academic year|entry|intake|fees?)\b|\b(?:September|January|August|October)\s+(20\d\d)\b", re.I)
SPLIT_CUE = re.compile(r"\b(?:domestic|home|international|overseas|non-EU|EU students?|resident|citizens?)\b", re.I)
FEE_SENT = re.compile(r"\b(?:course fees?|programme fees?|program fees?|tuition(?: fees?)?|fees? for|fees? (?:are|is|will be))\b", re.I)
NOT_FEE = re.compile(r"\b(?:application fee|deposit|reservation|instal?lments?|alumni|discount|scholarship|bursary|living|accommodation|insurance|visa|laptop|books?|per credit|per module|per subject|waiver|loan|stipend|salary|earn)\b", re.I)
AMOUNT_PARTS = re.compile(r"^(?:Up to )?(?P<cur>[A-Za-z]{3}|[£€$])\s?(?P<num>[\d,]+(?:\.\d+)?)")


def _parse_amount(display):
    m = AMOUNT_PARTS.match(display or '')
    if not m:
        return None, None
    cur = {'£': 'GBP', '€': 'EUR'}.get(m.group('cur'), m.group('cur').upper())
    try:
        return float(m.group('num').replace(',', '')), cur
    except ValueError:
        return None, None


def _year_of(s):
    m = AMT_YEAR.search(s)
    if not m:
        return ''
    if m.group(1):
        return f'{m.group(1)}-{m.group(2)}'
    return next(g for g in m.groups()[2:] if g)


def find_fee(sentences_, country=None):
    """{t, amount, cur, per, q, note} or None.

    Step 1: the fee for international students, by the course reader's own rule. Step 2: a page that gives one fee for everybody and never
    mentions home or international students in a sentence with an amount (many MBA pages do this). A page that mixes the two is left alone."""
    hit = CF.find_fee(sentences_, country)
    note = ''
    if hit:
        display, ctx = hit['display'].split('; ')[0], hit['context']
    else:
        split = any(SPLIT_CUE.search(s) and any(T._amount_text(m, country) for m in T.AMOUNT.finditer(s)) for s in sentences_[:400])
        if split:
            return None
        display = ctx = None
        for s in sentences_[:400]:
            if len(s) > 300 or NOT_FEE.search(s) or not FEE_SENT.search(s):
                continue
            amts = [t for t in (T._amount_text(m, country) for m in T.AMOUNT.finditer(s)) if t]
            if amts and _parse_amount(amts[0])[0] and _parse_amount(amts[0])[0] >= 5000:
                display, ctx = amts[0], s
                note = 'The page gives one fee and does not list a separate international fee.'
                break
        if not display:
            return None
    amount, cur = _parse_amount(display)
    if not amount:
        return None
    yr = _year_of(ctx)
    per = 'year' if re.search(r"\ba year\b|per (?:year|annum)|annual", display + ' ' + ctx, re.I) else ('programme' if re.search(r"\b(?:whole|entire|total|full)\b", ctx, re.I) else 'unknown')
    sym = {'GBP': '£', 'EUR': '€', 'USD': 'US$'}.get(cur)
    num = f'{int(amount):,}' if amount == int(amount) else f'{amount:,.2f}'
    shown = f'{sym}{num}' if sym else f'{cur} {num}'
    return {'t': shown + (f' ({yr})' if yr else ''), 'amount': amount, 'cur': cur, 'per': per, 'q': ctx[:QMAX], 'note': note or None}


# ---------------- GMAT / GRE ----------------
TEST_RX = [('GMAT', re.compile(r"\bGMAT\b")), ('GRE', re.compile(r"\bGRE\b")), ('Executive Assessment', re.compile(r"\bExecutive Assessment\b|\bEA\b"))]
TEST_CUE = re.compile(r"\b(?:require[sd]?|accept\w*|submit|provide|need|must|complete|take|score report|valid)\b", re.I)
TEST_NEG = re.compile(r"\b(?:not required|waive[rd]?s?|no longer|optional|exempt\w*|not (?:need|necessary)|without a)\b", re.I)


def find_test(sentences_):
    for s in sentences_[:500]:
        if len(s) > 300 or not TEST_CUE.search(s):
            continue
        found = [name for name, rx in TEST_RX if rx.search(s)]
        if not any(n in ('GMAT', 'GRE') for n in found) or TEST_NEG.search(s):
            continue
        return {'t': ' or '.join(found), 'q': s[:QMAX]}
    return None


# ---------------- English ----------------
def find_english(sentences_):
    hit = CF.find_ielts(sentences_)
    if hit and hit.get('overall'):
        o = hit['overall']
        return {'t': f"IELTS {o:g} overall", 'ielts': o, 'q': hit['context'][:QMAX]}
    return None


# ---------------- length, start, deadlines, degree ----------------
def find_length(sentences_):
    hit = CF.find_duration(sentences_, 'Master')
    if not hit:
        return None
    q = hit['context']
    return {'t': hit['display'] + (', full-time' if re.search(r"full[- ]time", q, re.I) else ''), 'months': round(hit['years'] * 12), 'q': q[:QMAX]}


def find_start(sentences_):
    hit = CF.find_intakes(sentences_)
    if not hit:
        return None
    months, q = hit['months'], hit['context']
    year = re.findall(r"\b(20\d\d)\b", q)
    names = ', '.join(FULL_MONTH[m] for m in months)
    return {'t': names + (f' {year[0]}' if len(months) == 1 and len(set(year)) == 1 else ''), 'months': months, 'q': q[:QMAX]}


DEADLINE = re.compile(r"\bdeadlines?\b|\bapply by\b|\bclos(?:es|ing)\b|\bround (?:one|two|three|four|\d)\b", re.I)


def find_deadlines(sentences_):
    out = []
    for s in sentences_[:500]:
        if len(s) > 260 or not DEADLINE.search(s) or not re.search(rf"\b{T._MON}\b", s) or not re.search(r"\b20\d\d\b", s):
            continue
        if s not in out:
            out.append(s)
        if len(out) == 3:
            break
    return {'t': ' '.join(out)[:420], 'q': out[0][:QMAX]} if out else None


DEGREE = re.compile(r"\b(?:undergraduate|bachelor'?s?|honours|first degree|university degree)\b", re.I)
DEGREE_CUE = re.compile(r"\b(?:require[sd]?|must|need|hold|complete[d]?|equivalent|accept|degree in any)\b|\b2[.:]1\b", re.I)


def find_degree(sentences_):
    for s in sentences_[:500]:
        if 20 < len(s) <= 200 and re.search(r"\bdegree\b", s, re.I) and DEGREE.search(s) and DEGREE_CUE.search(s):
            return {'t': s, 'q': s[:QMAX]}
    return None


# ---------------- employment report (a link, not numbers) ----------------
EMP_LINK = re.compile(r"\b(?:employment|careers?|placement|graduate)\s+(?:report|outcomes?|statistics|destinations)\b|\bemployment\s+(?:report|statistics)\b", re.I)


def find_employment(soup, page_url):
    for a in soup.find_all('a', href=True):
        label = T.clean(a.get_text(' '))
        if 4 <= len(label) <= 70 and EMP_LINK.search(label):
            u = urllib.parse.urljoin(page_url, a['href'].strip())
            if urllib.parse.urlsplit(u).scheme in ('http', 'https'):
                return {'t': label, 'u': u.split('#')[0]}
    return None


# ---------------- one page ----------------
FACTS = ('length', 'fee', 'exp', 'degree', 'test', 'english', 'start', 'deadlines')
FINDERS = {'length': find_length, 'exp': find_experience, 'degree': find_degree, 'test': find_test, 'english': find_english, 'start': find_start, 'deadlines': find_deadlines}


def verify(name, f):
    """A fact is kept only if what it says is in its own sentence. Returns an error text, or '' when it checks out."""
    q = re.sub(r"[\s ]+", ' ', f.get('q') or '')
    flat = q.replace(',', '')
    if name == 'fee':
        n = f['amount']
        digits = f'{n:.2f}'.rstrip('0').rstrip('.')
        return '' if re.search(rf"(?<![\d.]){re.escape(digits)}(?!\.?\d)", flat) else 'fee amount not in its sentence'
    if name == 'exp':
        n = f['min']
        words = [w for w, v in NUMW.items() if v == n]
        return '' if re.search(rf"(?<![\d.]){n}(?!\.?\d)", q) or any(re.search(rf"\b{w}\b", q, re.I) for w in words) else 'years not in its sentence'
    if name == 'english':
        score = f'{f["ielts"]:g}'
        return '' if re.search(rf"(?<![\d.]){re.escape(score)}(?:\.0)?(?!\.?\d)", q) else 'score not in its sentence'
    if name == 'start':
        bad = [m for m in f['months'] if not re.search(rf"\b{FULL_MONTH[m][:3]}", q, re.I)]
        return 'month not in its sentence' if bad else ''
    if name == 'test':
        return '' if all(re.search(rf"\b{re.escape(n.split()[0])}\b", q) for n in f['t'].split(' or ')) else 'test not in its sentence'
    return ''


def read_page(html, url, country=None):
    """{fact name: fact} from one page, plus 'employment'. Each fact has t (what the site shows), q (the sentence), u (this page)."""
    import extract as X  # scripts/scholarships/extract.py
    soup = X.soup_of(html)
    emp = find_employment(soup, url)          # before the page chrome is cut away: the link is often in a footer or a side box
    node = X.main_node(soup)
    sents = T.sentences(X.flat_text(X.lines_of(node)))
    out, rejected = {}, []
    found = {name: fn(sents) for name, fn in FINDERS.items()}
    found['fee'] = find_fee(sents, country)
    for name in FACTS:
        f = found.get(name)
        if not f:
            continue
        err = verify(name, f)
        if err:
            rejected.append((name, err))
            continue
        f['u'] = url
        out[name] = f
    if emp:
        out['employment'] = emp
    return out, rejected


def merge(per_page):
    """First page in the register's order wins for each fact. per_page: [(facts dict, rejected list)]."""
    out, rej = {}, []
    for facts_, rejected in per_page:
        rej += rejected
        for k, v in facts_.items():
            out.setdefault(k, v)
    return out, rej
