"""Decide what kind of programme a page describes. No AI: patterns on the programme title and on sentences of the page.

Three questions, each answered from words on the page:
  1. level      - Bachelor or Master (anything else is left out)
  2. study mode - full-time on campus, yes / no / unclear, with the sentence that says so
  3. international - open to international students, yes / no / unclear, with the sentence or code that says so
"""
import re

import textutil as T  # scripts/scholarships/textutil.py (path is set by the caller)

# ---------------- level, from the title ----------------
# Letters like BA, MA, MS and BS are matched in capitals only, so "ma" or "bs" inside ordinary words never count.
BACHELOR_TITLE = re.compile(
    r"(?:(?i:\bBachelor(?:s|['’]s)?(?:\s+degree)?\b)|\bBBA\b|\bBSc\b|\bB\.Sc\b|\bBEng\b|\bB\.Eng\b|\bBCom\b|\bBComm\b|\bBEd\b|\bBTech\b|\bB\.Tech\b|\bBFA\b|\bBArch\b|"
    r"\bBMus\b|\bBDes\b|\bBSW\b|\bBN\b|\bLLB\b|\bMBBS\b|\bMBChB\b|\bBA\b|\bB\.A\.|\bBS\b|\bB\.S\.|\bBBus\b|\bBPharm\b|\bBPsych\b)")
MASTER_TITLE = re.compile(
    r"(?:(?i:\bMaster(?:s|['’]s)?(?:\s+degree)?\b)|\bMBA\b|\bMSc\b|\bM\.Sc\b|\bMEng\b|\bM\.Eng\b|\bMRes\b|\bMEd\b|\bMFA\b|\bMPA\b|\bMPH\b|\bMArch\b|\bMMus\b|\bMSW\b|"
    r"\bMCom\b|\bMComm\b|\bMIM\b|\bMFin\b|\bMAcc\b|\bMBus\b|\bMPP\b|\bMDes\b|\bLLM\b|\bMPharm\b|\bMPsych\b|\bMSci\b|\bMChem\b|\bMPhys\b|\bMMath\b|\bMComp\b|\bMBiol\b|\bMGeol\b|"
    r"\bMA\b|\bM\.A\.|\bMS\b|\bM\.S\.|\bMTech\b|\bM\.Tech\b)")
# four-year UK "integrated master's" start at undergraduate level: still a Master's, flagged so the site can say so
INTEGRATED = re.compile(r"\b(?:MEng|MSci|MChem|MPhys|MMath|MComp|MBiol|MGeol|MPharm|MArch)\b")
# degrees that are written as "Bachelor of X" but are really something else
SECOND_FIRST = re.compile(r"\b(?:Bachelor|Master)(?:s|['’]s)? of (?:Philosophy|Research)\b", re.I)

# anything in the title that makes the programme something other than a Bachelor's or Master's
OUT_TITLE = [
    ('research-degree', re.compile(r"\b(?:Ph\.?D|DPhil|Doctor(?:ate|al)?|MPhil|Master(?:s|['’]s)? of Philosophy|Higher Degree by Research|EdD|DBA|DProf)\b", re.I)),
    ('foundation-or-pathway', re.compile(r"\b(?:foundation|pathway|pre[- ]?master'?s?|pre[- ]?sessional|bridging|access (?:course|programme|program)|preparatory|prep (?:year|programme|program)|diploma of higher education|HND|HNC|associate (?:degree|of)|FdA|FdSc|FdEng|transfer (?:pathway|programme|program))\b", re.I)),
    ('diploma-or-certificate', re.compile(r"\b(?:diploma|certificate|PGCert|PGDip|PgDip|PgCert|graduate cert|postgraduate cert|micro-?credential|badge|short course|summer (?:school|course|programme|program)|executive education|executive MBA|EMBA|professional development|CPD|apprenticeship|licen[cs]ure|endorsement)\b", re.I)),
    ('online-or-distance', re.compile(r"\b(?:online|distance(?: learning| education)?|off[- ]campus|external mode|remote(?:ly)? delivered|e-?learning|open learning|correspondence|virtual)\b", re.I)),
    ('part-time-only', re.compile(r"\b(?:part[- ]time(?: only)?|evening (?:programme|program|degree)|weekend (?:programme|program|degree))\b", re.I)),
]
# the same words in a URL path (hyphenated)
OUT_PATH = [
    ('online-or-distance', re.compile(r"/(?:online|distance|distance-learning|e-?learning|off-campus|external)(?:/|-|$)|[-/]online(?:[-/]|$)", re.I)),
    ('foundation-or-pathway', re.compile(r"/(?:foundation|pathway|pathways|pre-masters?|diploma|certificate|short-courses?|executive-education)(?:/|-|$)", re.I)),
    ('research-degree', re.compile(r"/(?:phd|doctoral|doctorate|research-degrees?|mphil)(?:/|-|$)", re.I)),
]


def classify_title(title):
    """Return (level, degree_text, flags, reason). `reason` is set when the title says the programme is out of scope."""
    t = T.clean(title)
    if not t:
        return None, '', {}, 'no-title'
    # a PhD or a certificate named in the title is out even if "Master" also appears ("Certificate in Master Data Management")
    for reason, rx in OUT_TITLE:
        m = rx.search(t)
        if m:
            # "Master of Science in Online Marketing" is a campus Master's; only treat "online" as out when it stands as a label
            if reason == 'part-time-only' and re.search(r"full[- ]?time", t, re.I):
                continue
            if reason == 'online-or-distance' and not re.search(r"\((?:[^)]*\b(?:online|distance|remote|virtual|off[- ]campus)\b[^)]*)\)|[-–:|]\s*(?:online|distance|remote)\b|\bonline\s*$|^online\b|\bfully online\b", t, re.I):
                continue
            return None, '', {}, reason
    b, mm = BACHELOR_TITLE.search(t), MASTER_TITLE.search(t)
    if SECOND_FIRST.search(t):
        return None, '', {}, 'research-degree'
    if not b and not mm:
        return None, '', {}, 'no-degree-designation'
    flags = {}
    if b and mm:
        flags['combined'] = True
        first = b if b.start() < mm.start() else mm
    else:
        first = b or mm
    level = 'Bachelor' if first is b else 'Master'
    degree = first.group(0).strip()
    # "Bachelor of Science in Nursing" - keep the whole designation, "Bachelor of Science (Honours)" etc.
    m = re.search(r"\b(?:Bachelor|Master)(?:s|['’]s)? of [A-Za-z][A-Za-z&,\- ]{2,60}?(?= in | \(|\s*[-–:|/]|$)", t, re.I)
    if m and m.start() == first.start():
        degree = T.clean(m.group(0))
    else:
        h = re.match(r"\s*\((Hons|Honours)\)", t[first.end():], re.I)
        if h:
            degree = f"{degree} ({h.group(1)})"
    if level == 'Master' and INTEGRATED.search(t):
        flags['integrated'] = True
    return level, degree, flags, ''


def classify_url(url):
    path = re.sub(r'^https?://[^/]+', '', url)
    for reason, rx in OUT_PATH:
        if rx.search(path):
            return reason
    return ''


# ---------------- study mode, from sentences ----------------
ON_CAMPUS = re.compile(
    r"\b(?:on[- ]campus|campus[- ]based|face[- ]to[- ]face|in[- ]person|on-site|onsite|attend(?:ing)? (?:classes|lectures) on campus|"
    r"study mode:?\s*(?:full[- ]time|on[- ]campus|internal)|mode of (?:study|attendance|delivery):?\s*(?:full[- ]time|on[- ]campus|internal|face)|"
    r"attendance:?\s*(?:full[- ]time|on[- ]campus)|study (?:load|type):?\s*full[- ]time)\b", re.I)
FULL_TIME = re.compile(r"\b(?:full[- ]?time|fulltime)\b", re.I)
ONLINE_ONLY = re.compile(
    r"\b(?:(?:100\s?%|fully|entirely|completely|wholly|totally|purely)\s+(?:online|distance)|online[- ]only|only (?:available )?online|"
    r"delivered (?:fully |entirely |100% |completely )?online|study mode:?\s*(?:online|distance|external|remote)|"
    r"(?:distance|online) learning (?:programme|program|degree|course)|this is an online (?:programme|program|degree|course)|no (?:campus )?attendance|"
    r"studied (?:entirely |fully )?(?:online|at a distance|by distance)|fully remote)\b", re.I)
PART_TIME_ONLY = re.compile(r"\b(?:part[- ]time (?:only|study only)|only (?:available )?part[- ]time|available part[- ]time only|part[- ]time (?:mode )?only)\b", re.I)
NEGATED = re.compile(r"\b(?:not|isn['’]t|aren['’]t|no longer|cannot|can['’]t|unable to)\b[^.]{0,40}\b(?:full[- ]time|on[- ]campus)\b", re.I)


# "full-time" and "on campus" also turn up in sentences about jobs, visas, housing and open days. Those do not describe the course.
NOT_ABOUT_STUDY = re.compile(
    r"\b(?:work(?:ing)?|jobs?|employ\w*|vacations?|holidays?|breaks?|career\w*|salary|wages?|placements?|internships?|accommodation|housing|halls?|residences?|living|dining|parking|"
    r"open days?|events?|tours?|visits?|webinars?|fairs?|facilit\w+|library|clubs?|societ\w+|gym|visa|hours (?:a|per) week|apply in person|bring|pay)\b", re.I)
MODE_LABEL = re.compile(
    r"\b(?:study mode|mode of (?:study|attendance|delivery)|attendance|study (?:load|type)|delivery|course type)\b[^.]{0,30}?\b(?:full[- ]?time|on[- ]campus|internal|face[- ]to[- ]face|in[- ]person)\b", re.I)


def _says_full_time_on_campus(s):
    if MODE_LABEL.search(s):
        return True
    if NOT_ABOUT_STUDY.search(s):
        return False
    return bool(ON_CAMPUS.search(s) or FULL_TIME.search(s))


def study_mode(sentences_, title='', url='', markup_mode=''):
    """Return (verdict, evidence). verdict is 'yes' (full-time, on campus), 'no' or 'unclear'.

    'yes' needs a sentence that says full-time or on-campus about the course, and nothing on the page that says it is online only.
    A page that says both is 'unclear': a person should look.
    """
    pos, online, part = '', '', ''
    out = classify_url(url)
    if out == 'online-or-distance':
        online = f'The address of the page is an online or distance page: {url}'
    for s in sentences_[:400]:
        if len(s) > 320:
            continue
        if not online and ONLINE_ONLY.search(s):
            online = s
        if not part and PART_TIME_ONLY.search(s):
            part = s
        if not pos and _says_full_time_on_campus(s) and not NEGATED.search(s) and not PART_TIME_ONLY.search(s):
            pos = s
    mm = (markup_mode or '').lower()
    if mm:
        if re.search(r'\bonline\b|distance|remote', mm) and not re.search(r'onsite|on-site|campus|blended', mm):
            online = online or f'The page marks the course mode as "{markup_mode}".'
        elif re.search(r'onsite|on-site|campus|face', mm):
            pos = pos or f'The page marks the course mode as "{markup_mode}".'
    if online and pos:
        return 'unclear', f'Conflicting: {pos[:140]} | {online[:140]}'
    if online:
        return 'no', online[:240]
    if part and not pos:
        return 'no', part[:240]
    if pos:
        return 'yes', pos[:240]
    return 'unclear', ''


# ---------------- international students ----------------
CRICOS = re.compile(r"\bCRICOS(?:\s+(?:provider|course))?(?:\s+(?:code|number|no\.?))?\s*:?\s*(\d{6}[A-Z])\b", re.I)
INTL_FEE = re.compile(
    r"\b(?:international(?:\s+(?:students?|student fee|tuition|fees?|applicants?|undergraduate|postgraduate))?|overseas(?:\s+(?:students?|fees?))?|"
    r"non[- ]?(?:EU|EEA|UK|US|U\.S\.|Australian|Canadian|domestic|resident)(?:\s+(?:students?|fees?))?|out[- ]of[- ]state|"
    r"outside (?:the )?(?:EU|EEA|UK|US|Australia|Canada|New Zealand))\b", re.I)
INTL_APPLY = re.compile(
    r"\b(?:international (?:students?|applicants?) (?:can|may|are (?:welcome|able|eligible|invited)|should|will|need|must|apply)|"
    r"(?:available|open|offered|designed|suitable|intended) (?:only )?(?:to|for) international (?:students?|applicants?)|"
    r"(?:we )?welcome (?:applications? from )?international|apply as an international|how to apply (?:as|for) international|"
    r"open to (?:all )?international|international (?:admissions?|entry requirements?|applications?)|"
    r"entry requirements? for international|english language requirements?|visa|student visa|IELTS|TOEFL|Duolingo|PTE)\b", re.I)
INTL_NO = re.compile(
    r"\b(?:(?:this|the) (?:course|programme|program|degree)(?: is)? (?:is )?(?:only )?(?:available|open|offered) (?:only )?(?:to|for) (?:domestic|home|local|[A-Z][a-z]+ (?:citizens|residents)|citizens?|residents?)|"
    r"(?:domestic|home|local) (?:students?|applicants?) only|citizens? (?:and|or) permanent residents? only|"
    r"not (?:available|open|offered|eligible)(?: to| for)? international|international students? (?:are|is) not (?:eligible|able|accepted|admitted)|"
    r"closed to international|unable to accept international|cannot accept international)\b", re.I)


def international(sentences_, cricos_code=''):
    """Return (verdict, how, evidence). how is 'cricos', 'fee' or 'page'."""
    for s in sentences_[:400]:
        if len(s) <= 320 and INTL_NO.search(s):
            return 'no', 'page', s[:240]
    if cricos_code:
        return 'yes', 'cricos', f'CRICOS course code {cricos_code}. A CRICOS code means the course is registered for international students.'
    for i, s in enumerate(sentences_[:400]):
        if len(s) > 320:
            continue
        if INTL_FEE.search(s) and re.search(r"[£€$]|\b(?:fees?|tuition|cost|USD|GBP|EUR|AUD|CAD|NZD|per year|a year|annual)\b", s, re.I):
            return 'yes', 'fee', s[:240]
    for s in sentences_[:400]:
        if len(s) <= 320 and INTL_APPLY.search(s) and re.search(r"international|overseas|non-?EU|visa|IELTS|TOEFL|English language", s, re.I):
            return 'yes', 'page', s[:240]
    return 'unclear', '', ''
