"""Plain-text helpers for the scholarship reader. No AI, no network: regular expressions only."""
import re
import unicodedata
from datetime import date

MONTHS = {
    'jan': 1, 'january': 1, 'feb': 2, 'february': 2, 'mar': 3, 'march': 3, 'apr': 4, 'april': 4,
    'may': 5, 'jun': 6, 'june': 6, 'jul': 7, 'july': 7, 'aug': 8, 'august': 8,
    'sep': 9, 'sept': 9, 'september': 9, 'oct': 10, 'october': 10, 'nov': 11, 'november': 11,
    'dec': 12, 'december': 12,
}
_MON = r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
_ORD = r'(?:st|nd|rd|th)?'

D_DMY = re.compile(rf'\b(\d{{1,2}}){_ORD}\s+(?:of\s+)?({_MON})\.?,?\s+(\d{{4}})\b', re.I)
D_MDY = re.compile(rf'\b({_MON})\.?\s+(\d{{1,2}}){_ORD},?\s+(\d{{4}})\b', re.I)
D_ISO = re.compile(r'\b(\d{4})-(\d{2})-(\d{2})\b')
D_NUM = re.compile(r'\b(\d{1,2})[/.](\d{1,2})[/.](\d{4})\b')
# A day and month with no year. We keep these as text and never turn them into a date.
D_PART_DM = re.compile(rf'\b(\d{{1,2}}){_ORD}\s+(?:of\s+)?({_MON})\b(?!\.?,?\s+\d{{4}})', re.I)
D_PART_MD = re.compile(rf'\b({_MON})\.?\s+(\d{{1,2}}){_ORD}\b(?!,?\s+\d{{4}})', re.I)

DEADLINE_WORDS = re.compile(
    r'\b(?:deadlines?|closing date|closes?|closed|close on|applications? (?:close|closes|due)|apply by|apply before|'
    r'submit(?:ted)? by|last date|due (?:by|on|date)|must be (?:received|submitted)|no later than|until)\b', re.I)
OPEN_WORDS = re.compile(
    r'\b(?:opens?|opening|open from|opens on|applications? (?:open|opens|start|starts|begin|begins)|'
    r'call opens|available from|accepting applications from)\b', re.I)
NOT_APPLICATION_DATE = re.compile(
    r'\b(?:notif(?:y|ied|ication)|announce|results?|decisions?|outcomes?|interviews?|'
    r'(?:programme|program|course|semester|term|intake|academic year) (?:starts?|begins?|commences?)|'
    r'start(?:s|ing)? (?:of|in|on) (?:the )?(?:programme|program|course|semester|term)|'
    r'commenc\w+|published|updated|posted|last reviewed)\b', re.I)
ROLLING = re.compile(
    r'\b(?:rolling basis|rolling applications?|open all year|year[- ]round|no (?:fixed |set |specific )?deadline|'
    r'always open|applications? (?:are )?(?:accepted|considered) (?:throughout|all) (?:the )?year)\b', re.I)


def clean(s):
    if not s:
        return ''
    s = unicodedata.normalize('NFKC', s)
    s = re.sub(r'[​-‏⁠﻿]', '', s)
    return re.sub(r'\s+', ' ', s).strip()


def sentences(text):
    text = clean(text)
    # split on sentence ends and on line-like separators that survived get_text(separator='\n')
    parts = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9£€$])', text)
    out = []
    for p in parts:
        p = p.strip()
        while len(p) > 400:  # very long run-on: cut at a semicolon or bullet if any
            cut = max(p.rfind('; ', 0, 400), p.rfind(' • ', 0, 400))
            if cut < 100:
                break
            out.append(p[:cut + 1])
            p = p[cut + 2:]
        if p:
            out.append(p)
    return out


def _mk(y, m, d):
    try:
        if 2000 <= y <= 2100:
            return date(y, m, d).isoformat()
    except ValueError:
        return None
    return None


def parse_full_dates(text):
    """Every full date (with a year) in the text, as ISO strings, in order."""
    found = []
    for m in D_DMY.finditer(text):
        iso = _mk(int(m.group(3)), MONTHS[m.group(2).lower().rstrip('.')], int(m.group(1)))
        if iso:
            found.append((m.start(), iso))
    for m in D_MDY.finditer(text):
        iso = _mk(int(m.group(3)), MONTHS[m.group(1).lower().rstrip('.')], int(m.group(2)))
        if iso:
            found.append((m.start(), iso))
    for m in D_ISO.finditer(text):
        iso = _mk(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if iso:
            found.append((m.start(), iso))
    for m in D_NUM.finditer(text):
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if a > 12 and b <= 12:
            iso = _mk(y, b, a)
        elif b > 12 and a <= 12:
            iso = _mk(y, a, b)
        else:
            iso = None  # 03/04/2027 could be either: skip rather than guess
        if iso:
            found.append((m.start(), iso))
    found.sort()
    seen, out = set(), []
    for _, iso in found:
        if iso not in seen:
            seen.add(iso)
            out.append(iso)
    return out


def parse_partial_dates(text):
    out = []
    for m in D_PART_DM.finditer(text):
        out.append(f"{int(m.group(1))} {m.group(2).capitalize()}")
    for m in D_PART_MD.finditer(text):
        out.append(f"{int(m.group(2))} {m.group(1).capitalize()}")
    return out


def find_dates(text):
    """Look at each sentence. Returns {deadlines, opens, partial, rolling}.

    A deadline is a full date in a sentence that talks about closing or applying by.
    An opening date is a full date in a sentence about applications opening.
    Dates in sentences about results, interviews or course starts are ignored.
    """
    deadlines, opens, partial, rolling = [], [], [], False
    for s in sentences(text):
        if len(s) > 420:
            s = s[:420]
        has_dl = bool(DEADLINE_WORDS.search(s))
        has_op = bool(OPEN_WORDS.search(s))
        if ROLLING.search(s) and re.search(r'scholar|bursar|award|grant|fellowship|appl', s, re.I) and not re.search(r'admission', s, re.I):
            rolling = True
        if not (has_dl or has_op):
            continue
        if NOT_APPLICATION_DATE.search(s) and not re.search(r'deadline|closing date|apply by|close', s, re.I):
            continue
        full = parse_full_dates(s)
        if full:
            # In "opens 1 Oct 2026 and closes 15 Jan 2027" keep order: first is open, last is close.
            if has_dl and has_op and len(full) >= 2:
                opens.append({'iso': full[0], 'ctx': s})
                deadlines.append({'iso': full[-1], 'ctx': s})
            elif has_dl:
                for iso in full:
                    deadlines.append({'iso': iso, 'ctx': s})
            else:
                for iso in full:
                    opens.append({'iso': iso, 'ctx': s})
        elif has_dl:
            for p in parse_partial_dates(s)[:2]:
                partial.append({'text': p, 'ctx': s})
    return {'deadlines': deadlines, 'opens': opens, 'partial': partial, 'rolling': rolling}


def choose_deadline(deadlines, today_iso):
    """Next upcoming deadline if there is one, otherwise the latest one that has passed."""
    if not deadlines:
        return None
    isos = sorted({d['iso'] for d in deadlines})
    upcoming = [i for i in isos if i >= today_iso]
    pick = upcoming[0] if upcoming else isos[-1]
    ctx = next(d['ctx'] for d in deadlines if d['iso'] == pick)
    return {'iso': pick, 'ctx': ctx[:240]}


def choose_open(opens, deadline_iso, today_iso):
    if not opens:
        return None
    isos = sorted({o['iso'] for o in opens})
    if deadline_iso:
        before = [i for i in isos if i < deadline_iso]
        if not before:
            return None
        isos = before
    # nearest opening not after the deadline, preferring one that is still in the future
    future = [i for i in isos if i > today_iso]
    return future[0] if future else isos[-1]


# ---------------- values ----------------
CUR_WORDS = r'USD|GBP|EUR|AUD|CAD|NZD|SGD|AED|MYR|SEK|NOK|CHF|INR|CNY|DKK'
CUR_SYM = r'(?:US|AU|A|CA|C|NZ|S|HK)?\$|£|€|RM|Rs\.?|₹'
NUM = r'\d{1,3}(?:[,  ]\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?'
AMOUNT = re.compile(
    rf'(?P<pre>\b(?:up to|upto|maximum of|worth|valued at|of|at|from)\s+)?'
    rf'(?:(?P<cur1>{CUR_WORDS})\s?(?P<n1>{NUM})|(?P<cur2>{CUR_SYM})\s?(?P<n2>{NUM})|(?P<n3>{NUM})\s?(?P<cur3>{CUR_WORDS}))'
    r'(?P<mult>\s?(?:k|K|m|M|million)\b)?'
    r'(?P<per>\s*(?:per|a|each|/)\s*(?:year|annum|month|semester|term|academic year)|\s*(?:annually|yearly|monthly))?',
    re.I)
COVERAGE = re.compile(
    r'\b(?:full(?:y)?[- ](?:tuition[- ])?(?:fee[- ])?(?:waiver|scholarship|funding|funded|ride)|fully[- ]funded|'
    r'full tuition(?: fees?)?|tuition[- ](?:fee[- ])?waiver|100\s?% (?:of )?(?:tuition|fees?)|'
    r'(?:\d{1,3}|half|partial)\s?%?[- ](?:of )?(?:tuition|fees?)(?: (?:waiver|discount|reduction))?|'
    r'\d{1,3}\s?% (?:tuition )?(?:discount|reduction|waiver)|living (?:allowance|stipend)|monthly stipend|stipend)\b', re.I)
VALUE_CUE = re.compile(r'\b(?:worth|value[ds]?|award(?:s|ed)? of|amount|up to|receive|covers?|provides?|offers?|funding|includes?|benefits?)\b', re.I)
NOT_VALUE = re.compile(
    r'\b(?:application fees?|admission fees?|deposit|visa fees?|cost of living|tuition fees? (?:are|is|for|of)|'
    r'per credit|processing fee|fee of|insurance|rent|flight|ielts|toefl|salary)\b', re.I)
DOLLAR_BY_COUNTRY = {'australia': 'AUD', 'canada': 'CAD', 'new-zealand': 'NZD', 'singapore': 'SGD', 'usa': 'USD'}
SYM_CODE = {'£': 'GBP', '€': 'EUR', '₹': 'INR', 'RM': 'MYR', 'US$': 'USD', 'A$': 'AUD', 'AU$': 'AUD', 'C$': 'CAD', 'CA$': 'CAD', 'NZ$': 'NZD', 'S$': 'SGD', 'HK$': 'HKD'}
PERIOD = {'year': 'a year', 'annum': 'a year', 'academic year': 'a year', 'annually': 'a year', 'yearly': 'a year', 'month': 'a month', 'monthly': 'a month', 'semester': 'a semester', 'term': 'a term'}


def _amount_text(m, country):
    cur = m.group('cur1') or m.group('cur2') or m.group('cur3') or ''
    num = m.group('n1') or m.group('n2') or m.group('n3') or ''
    num = re.sub(r'[\s ]', ',', num.strip())
    if cur.upper() in SYM_CODE:
        cur = SYM_CODE[cur.upper()]
    elif cur == '$':
        cur = DOLLAR_BY_COUNTRY.get(country, '$')
    elif cur.lower().startswith('rs'):
        cur = 'INR'
    cur = cur.upper() if cur.isalpha() else cur
    try:
        val = float(num.replace(',', ''))
    except ValueError:
        return None
    mult = (m.group('mult') or '').strip().lower()
    if mult == 'k':
        val *= 1000
    elif mult in ('m', 'million'):
        val *= 1_000_000
    if val < 100 and not mult:  # "$50" is a fee or a prize, not a scholarship value
        return None
    if val > 5_000_000:
        return None
    shown = f"{int(val):,}" if val == int(val) else f"{val:,.2f}"
    per = (m.group('per') or '').strip().lower()
    per = re.sub(r'^(?:per\s+|each\s+|a\s+|/\s*)', '', per)  # not r'^a': it ate the 'a' of 'annually'
    txt = f"{cur} {shown}" if cur.isalpha() else f"{cur}{shown}"
    if per in PERIOD:
        txt += f" {PERIOD[per]}"
    pre = (m.group('pre') or '').strip().lower()
    if pre in ('up to', 'upto', 'maximum of'):
        txt = 'Up to ' + txt
    return txt


def find_value(text, country=None):
    """Best statement of what the scholarship is worth. Returns {display, context} or None.

    The display text is built only from numbers and phrases found in the sentence.
    """
    best, best_score = None, 0
    for i, s in enumerate(sentences(text)[:60]):
        if len(s) > 420 or NOT_VALUE.search(s):
            continue
        amts = [t for t in (_amount_text(m, country) for m in AMOUNT.finditer(s)) if t]
        cov = [clean(c.group(0)).capitalize() for c in COVERAGE.finditer(s)]
        if not amts and not cov:
            continue
        score = 3 + (2 if VALUE_CUE.search(s) else 0) + (1 if i < 12 else 0) + (1 if amts else 0)
        if score > best_score:
            shown = []
            for t in amts[:2] + cov[:1]:
                if t.lower() not in [x.lower() for x in shown]:
                    shown.append(t)
            best, best_score = {'display': '; '.join(shown[:3]), 'context': s[:240]}, score
    return best


# ---------------- levels, international, name ----------------
BACHELOR = re.compile(r"\b(?:undergraduates?|bachelor(?:s|['’]s)?|b\.?sc|first[- ]degree|first[- ]year undergraduate)\b", re.I)
MASTER = re.compile(r"\b(?:postgraduates?(?: taught)?|master(?:s|['’]s)?|m\.?sc|mba|llm|taught postgraduate|graduate (?:students?|programmes?|programs?|degrees?|studies)|pgt)\b", re.I)
PHD = re.compile(r"\b(?:ph\.?d|doctoral|doctorates?|dphil|research degrees?|higher degree by research|hdr)\b", re.I)
ONLINE_ONLY = re.compile(r'\b(?:online (?:only|programmes?|degrees?)|distance learning|mooc)\b', re.I)

INTL_YES = re.compile(
    r"\b(?:international (?:students?|applicants?|undergraduates?|postgraduates?|fee)|overseas (?:students?|applicants?)|"
    r"non[- ]?(?:EU|UK|EEA|US|U\.S\.|Australian|Canadian|domestic|resident)|"
    r"(?:students?|applicants?) (?:from|who live) (?:outside|overseas|abroad|any country|all countries|around the world)|"
    r"all nationalit(?:y|ies)|any nationality|(?:from )?(?:any|all) countr(?:y|ies)|worldwide|students? from around the world)\b", re.I)
INTL_NO = re.compile(
    r"\b(?:(?:only )?(?:for|available to|open to|restricted to) (?:domestic|home|local|australian|new zealand|canadian|uk|eu|us|u\.s\.|american|german|french|dutch|swedish|norwegian|irish|singaporean|malaysian|emirati) "
    r"(?:students?|citizens?|residents?|applicants?|nationals?)(?: only)?|"
    r"(?:domestic|home|local) (?:students?|applicants?) only|citizens? (?:and|or) permanent residents? only|"
    r"not (?:available|open|eligible)(?: to| for)? international)\b", re.I)


def detect_levels(text):
    lv = []
    if BACHELOR.search(text):
        lv.append('Bachelor')
    if MASTER.search(text):
        lv.append('Master')
    return lv, bool(PHD.search(text))


def detect_international(text):
    yes, no = bool(INTL_YES.search(text)), bool(INTL_NO.search(text))
    if yes and not no:
        return 'yes'
    if yes and no:
        return 'unclear'
    if no:
        return 'no'
    return 'unclear'


NAME_WORDS = re.compile(r'\b(?:scholar(?:ship)?s?|bursar(?:y|ies)|fellowships?|awards?|grants?|waivers?|studentships?|stipends?|exhibitions?)\b', re.I)
TITLE_SEP = re.compile(r'\s+(?:\||–|—|-|::|·|•|»|«)\s+')


def clean_title(title, site_name=None):
    """Pick the part of a page title that names the scholarship, dropping the site name."""
    title = clean(title)
    parts = [p for p in TITLE_SEP.split(title) if p]
    if not parts:
        return title
    named = [p for p in parts if NAME_WORDS.search(p)]
    pick = (named or parts)[0]
    if site_name and len(parts) > 1:
        rest = [p for p in (named or parts) if site_name.lower() not in p.lower()]
        if rest:
            pick = rest[0]
    return pick.strip(' .:-')


def slugify(s, maxlen=70):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    s = re.sub(r'[^a-zA-Z0-9]+', '-', s).strip('-').lower()
    return s[:maxlen].strip('-') or 'scholarship'
