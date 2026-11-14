"""Extra facts about one scholarship, found with patterns in the page text. No AI.
Each fact comes from a sentence on the page. If the page does not say it clearly, the field stays empty
and the site shows nothing for it. Nothing is worked out beyond what the sentence says."""
import re

import textutil as T

WORD_N = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
          'twelve': 12, 'fifteen': 15, 'twenty': 20, 'thirty': 30, 'fifty': 50}
NUM = r'(\d{1,4}|' + '|'.join(WORD_N) + r')'
THING = r'(?:scholarships?|awards?|bursar(?:y|ies)|fellowships?|grants?|places|waivers?)'
SCH = re.compile(r'\b(?:scholar\w*|award(?:s|ed)?|bursar\w*|fellowships?|grants?|funding|waivers?|stipends?)\b', re.I)


def _n(tok):
    tok = tok.lower()
    return WORD_N.get(tok) if tok in WORD_N else int(tok)


# ---------- how many awards ----------
AWARDS_A = re.compile(
    rf'(?<![\d,.$£€])\b(up to |a maximum of |maximum of |a total of |approximately |around |about )?{NUM}\s+'
    rf'(?:(?:full|partial|new|annual|international|merit|tuition|fee|excellence|prestigious|competitive)\s+){{0,2}}{THING}\b'
    r'(?=[^.]{0,70}\b(?:available|offered|awarded|each year|per (?:year|intake|round|cohort)|annually|every year|are given|are granted|are provided|to be (?:awarded|offered)|will be (?:awarded|offered|given)))',
    re.I)
AWARDS_B = re.compile(rf'\b(?:number of (?:awards|scholarships|places|recipients)|(?:awards|scholarships|places) available|recipients? (?:per|each) year)\s*[:\-–]?\s*(up to )?{NUM}\b', re.I)


def find_awards(text):
    """{'n': 10, 'upTo': True} from a sentence like 'Up to 10 scholarships are available each year', else None."""
    for s in T.sentences(text):
        for rx in (AWARDS_A, AWARDS_B):
            m = rx.search(s)
            if not m:
                continue
            groups = m.groups()
            up_to, tok = (groups[0], groups[1]) if rx is AWARDS_A else (groups[0], groups[1])
            try:
                n = _n(tok)
            except (KeyError, ValueError):
                continue
            if n < 1 or n > 2000 or 1900 <= n <= 2100:
                continue
            return {'n': n, 'upTo': bool(up_to and re.search(r'up to|maximum|approx|around|about', up_to, re.I))}
    return None


# ---------- how long it lasts ----------
UNIT = r'(year|semester|term)s?'
DUR_FULL = re.compile(r'\b(?:for|over|throughout|during) (?:the )?(?:full |entire |whole |normal |standard |minimum )?(?:duration|length|period) of (?:the |your |their |a )?(?:\w+[- ]){0,2}(?:programme|program|degree|course|study|studies|undergraduate|postgraduate|masters?|bachelor)', re.I)
DUR_FOR = re.compile(rf'\b(?:for|over) (up to |a maximum of |maximum of |a period of )?(?:the )?(?:first )?{NUM}[- ](?:academic )?{UNIT}\b', re.I)
DUR_ADJ = re.compile(rf'\b{NUM}[- ]year (?:scholarship|award|bursary|grant|fellowship|funding)\b', re.I)
DUR_FIRST = re.compile(r'\b(?:first[- ]year (?:only|tuition|fees?)|for the first year\b|in (?:the |your )first year only)', re.I)


def find_duration(text):
    """'Full length of the course', '1 year', 'Up to 4 years', 'First year only'. Only from a sentence about the award itself."""
    for s in T.sentences(text):
        if not SCH.search(s):
            continue
        if DUR_FULL.search(s):
            return 'Full length of the course'
        m = DUR_FOR.search(s) or DUR_ADJ.search(s)
        if m:
            g = m.groups()
            up, tok, unit = (g[0], g[1], g[2]) if m.re is DUR_FOR else (None, g[0], 'year')
            try:
                n = _n(tok)
            except (KeyError, ValueError):
                continue
            if not 1 <= n <= 8:
                continue
            first = bool(re.search(r'\bfirst ' + re.escape(tok), s, re.I))
            if first and n == 1:
                return 'First year only'
            label = f"{n} {unit}{'s' if n > 1 else ''}"
            return ('Up to ' + label) if up and re.search(r'up to|maximum', up, re.I) else label
        if DUR_FIRST.search(s):
            return 'First year only'
    return None


# ---------- what it covers ----------
COVERS = [
    ('Tuition', re.compile(r'\btuition\b|\b(?:course|programme|program|study) fees?\b|\bfee (?:waivers?|reductions?|discounts?|remission)\b|\bfees? (?:waived|paid|covered)\b', re.I)),
    ('Living costs', re.compile(r'\bliving (?:allowance|costs?|expenses?|stipend)\b|\bstipend\b|\bmaintenance (?:grant|allowance)\b|\bmonthly (?:allowance|payments?)\b|\bcost of living\b|\bsubsistence\b', re.I)),
    ('Travel', re.compile(r'\bair ?fares?\b|\bflights?\b|\btravel (?:allowance|costs?|grant|expenses)\b|\breturn travel\b', re.I)),
    ('Health insurance', re.compile(r'\b(?:health|medical) (?:insurance|cover)\b|\bOSHC\b|\bOVHC\b', re.I)),
    ('Accommodation', re.compile(r'\baccommodation\b|\bhousing\b|\broom and board\b', re.I)),
    ('Books and materials', re.compile(r'\btextbooks?\b|\bstudy materials\b|\bbooks\b|\blaptop\b|\bequipment allowance\b', re.I)),
]
COVER_VERB = re.compile(r'\b(?:cover(?:s|ed|ing)?|includ(?:e|es|ed|ing)|provid(?:e|es|ed|ing)|pays?|paid|fund(?:s|ed|ing)?|allowance|stipend|entitle[sd]?|benefits?|received?|receive)\b', re.I)
NEGATION = re.compile(r"\b(?:not|no|n't|exclud\w+|except|cannot|without|unable|does not|do not)\b", re.I)
COVER_HEAD = re.compile(r"^(?:what (?:does|is) (?:it|the (?:scholarship|award)) (?:cover|include)|what(?:'s| is) (?:covered|included)|(?:the )?(?:scholarship|award) (?:covers|includes|provides)|benefits?(?: of the (?:scholarship|award))?|what you(?:'ll| will) (?:get|receive)|funding (?:covers|includes)|what (?:it|the (?:scholarship|award)) (?:covers|includes|provides)|what(?:'s| is) (?:covered|included)|what is funded)\b[:?]?$", re.I)


def find_covers(text, lines=None):
    """Ordered list of what the award says it pays for, from sentences about the award and from a 'What it covers' list."""
    found = set()
    for s in T.sentences(text):
        if len(s) > 400 or not COVER_VERB.search(s) or NEGATION.search(s):
            continue
        if not (SCH.search(s) or re.search(r'\btuition\b', s, re.I)):
            continue
        for label, rx in COVERS:
            if rx.search(s):
                found.add(label)
    if lines:
        for i, line in enumerate(lines):
            if len(line) <= 60 and COVER_HEAD.match(line.rstrip(':? ')):
                for item in lines[i + 1:i + 9]:
                    if len(item) > 160 or NEGATION.search(item):
                        continue
                    for label, rx in COVERS:
                        if rx.search(item):
                            found.add(label)
    return [label for label, _ in COVERS if label in found]


# ---------- do you have to apply? ----------
AUTO = re.compile(r"\bautomatically (?:considered|assessed|awarded|eligible|selected|reviewed|evaluated|given|granted)\b|\bno (?:separate |additional |extra )?application (?:is |will be )?(?:required|needed|necessary)\b|\b(?:do not|don't|does not|doesn't) (?:need|have) to (?:apply|submit)\b|\bno need to apply\b", re.I)
MUST = re.compile(r"\b(?:apply (?:online|by|before|through|via)|submit (?:an|your|a) (?:online )?application|application form|complete (?:an|the) application|applications? (?:must|should) be (?:submitted|made|received))\b", re.I)


def find_apply_mode(text, apply_url=None):
    """'automatic' if the page says there is nothing to fill in, 'application' if it asks you to apply, else None."""
    auto = any(AUTO.search(s) and SCH.search(s) for s in T.sentences(text))
    if auto:
        return 'automatic'
    if apply_url or MUST.search(text):
        return 'application'
    return None


def extra(text, lines=None, apply_url=None):
    """All of the above as record fields. Empty ones are left out."""
    out = {}
    aw = find_awards(text)
    if aw:
        out['awards'] = aw
    d = find_duration(text)
    if d:
        out['duration'] = d
    c = find_covers(text, lines)
    if c:
        out['covers'] = c
    m = find_apply_mode(text, apply_url)
    if m:
        out['applyMode'] = m
    return out


# ---------- what the page says about missed fields (for the run log only) ----------
DL_HINT = re.compile(r'\b(?:deadline|clos(?:e|es|ed|ing)|apply (?:by|before)|due|applications? (?:open|close)|submit(?:ted)? by|no later than)\b', re.I)
DATE_HINT = re.compile(r'\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?[A-Za-z]{3,9}|[A-Za-z]{3,9}\.?\s+\d{1,2}|\d{1,2}[/.]\d{1,2}[/.]\d{2,4}|\b20\d\d\b')
VAL_HINT = re.compile(r'[£€$₹]\s?\d|\b\d[\d,]*\s?(?:USD|GBP|EUR|AUD|CAD|NZD|SGD|AED|MYR|SEK|NOK|CHF|INR)\b|\b\d{1,3}\s?%')


def missed(text, want_deadline, want_value, limit=3):
    """Sentences that look like they hold a deadline or a value the reader did not take. The run log prints a sample,
    so the patterns can be improved from real pages."""
    out = {}
    for key, need, cue in (('deadline', want_deadline, DL_HINT), ('value', want_value, VAL_HINT)):
        if not need:
            continue
        lines = []
        for s in T.sentences(text):
            if cue.search(s) and (key == 'value' or DATE_HINT.search(s)):
                lines.append(s[:220])
            if len(lines) >= limit:
                break
        if lines:
            out[key] = lines
    return out
