"""Read the plain facts of a course page: international fee, length, start months, English score, field.

Every value is copied from a sentence on the page and the sentence is kept next to it, so the site can show
"the page says: ..." and anyone can check it. If a value cannot be read with confidence it stays empty
and the site says 'Check the official page'. No AI.
"""
import re

import textutil as T  # scripts/scholarships/textutil.py (path is set by the caller)
import levels as L

# ---------------- international tuition fee ----------------
FEE_CUE = re.compile(r"\b(?:fees?|tuition|cost|per (?:year|annum|semester|term|credit)|a year|annual(?:ly)?|yearly)\b", re.I)
DOMESTIC_CUE = re.compile(r"\b(?:domestic|home|UK|EU|Australian|Canadian|in[- ]state|resident|local|citizens?|Commonwealth|New Zealand)\b", re.I)
NOT_TUITION = re.compile(r"\b(?:application fee|admission fee|deposit|visa|insurance|health cover|OSHC|living|accommodation|rent|flight|accommodation|student services|SSAF|amenities|laptop|books?|scholarship|bursary|discount|waiver|stipend|salary|earn|income|loan|per credit hour)\b", re.I)
PER_CREDIT = re.compile(r"per (?:\d+\s+)?(?:credit|unit|module|point)s?", re.I)
TOTAL_CUE = re.compile(r"\b(?:whole course|entire (?:course|programme|program|degree)|full (?:course|programme|program|degree)|total (?:tuition|cost|fees?|price)|course total|total for the (?:course|degree|programme|program))\b", re.I)
TABLE_ROW = 90   # a short "International students. £34,400." line is a table row: the fee word sits in the table heading


def _num(txt):
    m = re.search(r"\d[\d,]*(?:\.\d+)?", txt)
    try:
        return float(m.group(0).replace(',', '')) if m else 0
    except ValueError:
        return 0


def find_fee(sentences_, country=None):
    """Return {display, context} for the international tuition fee, or None.

    The sentence (or the sentence before it, for table rows) must name international students and carry an amount, and the
    page must talk about fees somewhere. Amounts in sentences about home or domestic students alone are skipped, and so are
    prices for the whole course or per credit: we do not turn those into a yearly fee by guessing.
    """
    best, best_score = None, 0
    page_has_fees = any(re.search(r"\b(?:tuition|fees?)\b", x, re.I) for x in sentences_[:400])
    prev = ''
    for i, s in enumerate(sentences_[:400]):
        window_prev, prev = prev, s
        if len(s) > 360:
            continue
        amts = [t for t in (T._amount_text(m, country) for m in T.AMOUNT.finditer(s)) if t]
        if not amts:
            continue
        has_intl_here = bool(L.INTL_FEE.search(s))
        has_intl_prev = bool(window_prev) and len(window_prev) < 160 and bool(L.INTL_FEE.search(window_prev))
        if not (has_intl_here or has_intl_prev):
            continue
        if NOT_TUITION.search(s) and not re.search(r"\btuition\b", s, re.I):
            continue
        if PER_CREDIT.search(s):
            continue  # a price per credit cannot be turned into a yearly fee without guessing the credits
        if TOTAL_CUE.search(s) or (has_intl_prev and TOTAL_CUE.search(window_prev)):
            amts = [t for t in amts if re.search(r"\ba (?:year|month|semester|term)\b", t)]   # keep only amounts that say per year
            if not amts:
                continue
        row = has_intl_here and len(s) <= TABLE_ROW and page_has_fees and any(_num(t) >= 1000 for t in amts)
        if not (FEE_CUE.search(s) or (has_intl_prev and FEE_CUE.search(window_prev)) or row):
            continue
        # "Domestic £9,250, international £21,000": keep only the amount that follows the international word
        if DOMESTIC_CUE.search(s) and has_intl_here:
            after = s[L.INTL_FEE.search(s).start():]
            amts2 = [t for t in (T._amount_text(m, country) for m in T.AMOUNT.finditer(after)) if t]
            if amts2:
                amts = amts2
        elif DOMESTIC_CUE.search(s) and not has_intl_here:
            continue
        score = 3 + (2 if has_intl_here else 0) + (1 if re.search(r"\btuition\b", s, re.I) else 0) + (1 if re.search(r"per (?:year|annum)|a year|annual", s, re.I) else 0)
        if score > best_score:
            ctx = (window_prev + ' ' + s).strip() if (has_intl_prev and not has_intl_here) else s
            best, best_score = {'display': '; '.join(dict.fromkeys(amts[:2])), 'context': ctx[:300]}, score
    return best


# ---------------- length of the course ----------------
DUR_CUE = re.compile(r"\b(?:duration|length|years?|months?|full[- ]time|course length|length of (?:study|course|programme|program)|takes|typically|lasts?)\b", re.I)
DUR = re.compile(r"\b(\d{1,2}(?:\.\d)?|one|two|three|four|five|six)(?:\s?[-–]\s?(?:\d{1,2}(?:\.\d)?|one|two|three|four))?\s*(years?|yrs?|months?|semesters?)\b", re.I)
WORDNUM = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6}
NOT_DUR = re.compile(r"\b(?:work experience|experience|visa|post[- ]study|graduate route|after graduation|since|founded|ago|alumni|part[- ]time|per week|a week|hours|credit|scholarship|deadline|apply (?:at least|within|before)|within \d)\b", re.I)


FT_DUR = re.compile(r"full[- ]?time\W{0,8}(?:\w+\W+){0,2}?(\d{1,2}(?:\.\d)?|one|two|three|four|five|six)\s*(years?|yrs?|months?)", re.I)


def find_duration(sentences_, level):
    for s in sentences_[:400]:
        if len(s) > 220:
            continue
        text = s
        if re.search(r"part[- ]?time", s, re.I):
            m = FT_DUR.search(s)       # "Full-time: 1 year, Part-time: 2 years" - the full-time length is the one we want
            if m:
                text = f"Full-time {m.group(1)} {m.group(2)}"
        if not DUR_CUE.search(text):
            continue
        if NOT_DUR.search(text) and not re.search(r"\b(?:duration|length)\b", text, re.I):
            continue
        for m in DUR.finditer(text):
            n = m.group(1).lower()
            n = WORDNUM.get(n) or float(n)
            unit = m.group(2).lower()
            years = n if unit.startswith(('year', 'yr')) else (n / 12 if unit.startswith('month') else n / 2)
            lo, hi = (2.5, 6.5) if level == 'Bachelor' else (0.5, 3.5)
            if not (lo <= years <= hi):
                continue
            word = 'year' if unit.startswith(('year', 'yr')) and n == 1 else ('years' if unit.startswith(('year', 'yr')) else ('months' if unit.startswith('month') else 'semesters'))
            return {'display': f"{int(n) if float(n) == int(n) else n} {word}", 'years': round(years, 2), 'context': s[:240]}
    return None


# ---------------- start months ----------------
START_CUE = re.compile(r"\b(?:intakes?|start(?:s|ing)?(?: date| month| in)?|commenc\w+|begins?|entry (?:point|date)|semester \d|study period|enrol(?:ment)? periods?)\b", re.I)
MONTH_WORD = re.compile(T._MON, re.I)
SHORT = {1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun', 7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'}
NOT_START = re.compile(r"\b(?:deadline|close[sd]?|closing|apply by|applications? (?:open|due)|scholarship|results?|offer|decision|census|exam|orientation|graduat|visa)\b", re.I)


def find_intakes(sentences_):
    for s in sentences_[:400]:
        if len(s) > 240 or not START_CUE.search(s) or NOT_START.search(s):
            continue
        months = []
        for m in MONTH_WORD.finditer(s):
            if m.group(0) == 'may':
                continue  # the verb ("you may start"), not the month
            n = T.MONTHS.get(m.group(0).lower().rstrip('.'))
            if n and SHORT[n] not in months:
                months.append(SHORT[n])
        if 1 <= len(months) <= 5:
            return {'months': months, 'context': s[:240]}
    return None


# ---------------- English test score ----------------
IELTS_S = re.compile(r"\bIELTS\b", re.I)
SCORE = r"([4-9](?:\.[05])?)"
IELTS_OVERALL = [
    re.compile(rf"\b{SCORE}\s*(?:or higher\s*)?(?:overall|in total|total)\b", re.I),
    re.compile(rf"\boverall(?: band| score)?(?: of)?(?: at least| minimum| a minimum of)?\s*:?\s*{SCORE}\b", re.I),
]


def find_ielts(sentences_):
    for s in sentences_[:400]:
        if len(s) > 320 or not IELTS_S.search(s):
            continue
        n = None
        for rx in IELTS_OVERALL:
            m = rx.search(s)
            if m:
                n = float(m.group(1))
                break
        if n is None:
            nums = {float(x) for x in re.findall(rf"(?<![\d.]){SCORE}(?![\d])", s)}
            if len(nums) == 1:
                n = nums.pop()
        return {'overall': n, 'context': s[:240]}
    return None


# ---------------- field of study, from the programme title ----------------
FIELDS = [
    ('Data science and AI', r"data science|artificial intelligence|machine learning|\bAI\b|data analytics|analytics|big data"),
    ('Computer science and IT', r"computer|computing|software|informatics|information (?:technology|systems)|cyber|web development|\bgames?\b"),
    ('Biotechnology and life sciences', r"biotech|bioscience|biolog|biochem|genetic|microbiolog|molecular|life science|neuroscience|zoology|botany|ecology|marine"),
    ('Medicine and health', r"medicine|medical|health|nursing|midwif|dentist|pharmac|physiotherap|public health|clinical|biomedical|paramedic|radiograph|nutrition|veterinar"),
    ('Engineering', r"engineering|mechatronic|aerospace|robotic|\bEEE\b|civil|mechanical|electrical|electronic|chemical eng|materials"),
    ('Architecture and design', r"architect|urban plan|interior|industrial design|graphic design|fashion|design"),
    ('Business and management', r"business|management|marketing|\bMBA\b|entrepreneur|supply chain|human resource|commerce|administration|hospitality|tourism|event"),
    ('Finance and economics', r"financ|accounting|economics|banking|actuarial|econometric|investment"),
    ('Law', r"\blaw\b|legal|\bLLB\b|\bLLM\b|jurisprudence"),
    ('Education', r"education|teaching|teacher|pedagog"),
    ('Psychology and social sciences', r"psycholog|sociolog|anthropolog|criminolog|politic|international relations|social (?:work|science)|geograph|development studies|public policy"),
    ('Natural sciences and maths', r"physics|chemistry|mathemat|statistic|geolog|earth science|astronom|environmental|sustainab|climate|science"),
    ('Media and communication', r"media|communicat|journalism|film|television|publishing|advertising|public relations"),
    ('Arts and humanities', r"\barts?\b|history|philosoph|literature|english|language|linguistic|music|theatre|drama|archaeolog|religio|classics|creative writing|humanities|liberal"),
]
FIELD_RX = [(name, re.compile(rx, re.I)) for name, rx in FIELDS]


def find_field(name):
    """Field label chosen by keywords in the programme name. This is our label, not the university's: the site says so."""
    t = re.sub(r"^(?:Bachelor|Master)s?(?:['’]s)? of (?:Science|Arts|Engineering|Business|Technology|Commerce|Laws|Education|Fine Arts|Applied Science)\b", '', name, flags=re.I)
    for label, rx in FIELD_RX:
        if rx.search(t):
            return label
    return None
