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
    # the domestic version of a course page (Adelaide: /study/degrees/2027/<course>/dom/); the site is for international students
    ('domestic-only', re.compile(r"/(?:dom|domestic|home-students?|local-students?)(?:/|$)", re.I)),
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


# A course that "may include some online delivery" or "blends on-campus with online coursework" is not the plain on-campus
# full-time course the person asked for. We hold it for a human look instead of listing it.
MIXED_MODE = re.compile(
    r"\b(?:blended (?:learning|delivery|programme|program|course|degree|mode)|hybrid (?:programme|program|course|degree|delivery|learning|mode)|"
    r"some online (?:delivery|learning|study|classes|content|components?)|(?:may|can|will) include (?:some )?online|partly online|part[- ]online|"
    r"online (?:and|or) (?:on[- ]campus|face[- ]to[- ]face|in[- ]person)|(?:on[- ]campus|face[- ]to[- ]face|in[- ]person) (?:and|or) online|"
    r"or (?:studying )?on-?line|virtual options|blends?\b[^.]{0,60}\bonline|online (?:option|options|delivery option|component))\b", re.I)


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
    pos, online, part, mixed = '', '', '', ''
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
        if not mixed and MIXED_MODE.search(s) and not NOT_ABOUT_STUDY.search(s):
            mixed = s
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
    if mixed and not online:
        return 'unclear', f'Mixed delivery: {mixed[:200]}'
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
    r"\b(?:international (?:students?|applicants?) (?:can|may|are (?:welcome|able|eligible|invited|required|accepted)|should|will|need|must|apply|who)|"
    r"(?:available|open|offered|designed|suitable|intended) (?:only )?(?:to|for) international (?:students?|applicants?)|"
    r"(?:we )?welcome (?:applications? from )?international|apply as an international|how to apply (?:as|for) international|"
    r"open to (?:all )?international|international (?:entry requirements?|applicants?)|entry requirements? for international|"
    r"(?:accepts?|admits?|enrols?|enrolls?) international (?:students?|applicants?))\b", re.I)
# Not enough on their own: English-test scores, visas and "international admissions" menu labels also appear on pages for home students,
# on FAQ pages and in footers. They used to count as proof; they no longer do.
INTL_NO = re.compile(
    r"\b(?:(?:this|the) (?:course|programme|program|degree)(?: is)? (?:is )?(?:only )?(?:available|open|offered) (?:only )?(?:to|for) (?:domestic|home|local|[A-Z][a-z]+ (?:citizens|residents)|citizens?|residents?)|"
    r"(?:domestic|home|local) (?:students?|applicants?) only|citizens? (?:and|or) permanent residents? only|"
    r"not (?:available|open|offered|eligible)(?: to| for)? international|international students? (?:are|is) not (?:eligible|able|accepted|admitted)|"
    r"closed to international|unable to accept international|cannot accept international)\b", re.I)


# A sentence that mentions international students while talking about work rights, insurance, scholarships or visas is not about
# being admitted to the course.
INTL_PAGE_BAD = re.compile(r"\b(?:CPT|OPT|practical training|insurance|health (?:plan|cover)|scholarships?|bursar\w*|visas?|work(?:ing)?|employ\w*|permitted|housing|orientation|"
                           r"full-time status|purchase|stipends?|assistantships?)\b", re.I)


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
        if INTL_FEE.search(s) and re.search(r"\d[\d,. ]{2,}", s) and re.search(r"[£€$]|\b(?:fees?|tuition|cost|USD|GBP|EUR|AUD|CAD|NZD|per year|a year|annual)\b", s, re.I):
            return 'yes', 'fee', s[:240]
    for s in sentences_[:400]:
        if 25 <= len(s) <= 320 and INTL_APPLY.search(s) and not INTL_PAGE_BAD.search(s):
            return 'yes', 'page', s[:240]
    return 'unclear', '', ''


# ---------------- the university's own international admissions page ----------------
HUB_URL_NO = re.compile(
    r"/(?:news|events?|stories|story|blog|press|visas?|student-visas?|immigration|services?|support|orientation|arrivals?|welcome|housing|accommodation|"
    r"life|clubs?|societ\w+|exchange|study-abroad|incoming|outgoing|summer|short[- ]?(?:courses?|programs?|programmes?)|pathways?|foundation|"
    r"english-(?:language-)?(?:courses?|programs?|programmes?)|language-(?:courses?|programs?)|research|hdr|phd|doctoral|alumni|contact|faq|faqs)(?:/|-|\.|$)", re.I)
HUB_SENTENCE = re.compile(
    r"\binternational (?:students?|applicants?|undergraduate|graduate|postgraduate|admissions?|entry)\b|\boverseas (?:students?|applicants?)\b|"
    r"\bapplicants? from (?:outside|overseas|abroad|other countries)\b|\bstudents? from (?:outside|overseas|abroad|other countries)\b", re.I)
HUB_ACTION = re.compile(r"\b(?:appl(?:y|ication|ications|ying)|admission|admissions|admitted|entry|requirements?|eligib\w+|deadlines?|tuition|fees?|enrol\w*|welcome|accept\w*)\b", re.I)
HUB_BAD = re.compile(r"\b(?:events?|webinar|fair|tour|visa|immigration|housing|accommodation|clubs?|societ\w+|warning|scam|fraud|exchange|summer|pathway|foundation|phd|doctoral|research degree|HDR|mitgeteilt|Es wird)\b", re.I)


def hub_check(sentences_, url='', name=''):
    """Is this the university's international admissions page for degree study? Returns (ok, evidence).

    The address must not be a visa, news, event, service, exchange, summer-school, pathway or research page, and a sentence must be about
    international students AND about applying, entry, fees or admission. The first such sentence is the evidence."""
    path = re.sub(r'^https?://[^/]+', '', url)
    if HUB_URL_NO.search(path) or HUB_BAD.search(name or ''):
        return False, ''
    strong = re.compile(r"\b(?:appl(?:y|ication|ications|ying)|admission|admissions|admitted|entry|requirements?|eligib\w+|deadlines?)\b", re.I)
    weak = []
    for s in sentences_[:300]:
        if not (40 <= len(s) <= 320):
            continue
        if HUB_SENTENCE.search(s) and HUB_ACTION.search(s) and not HUB_BAD.search(s):
            if strong.search(s):
                return True, s[:240]          # best evidence: it is about applying or entering
            weak.append(s)                    # fees, tuition, welcome: good enough if nothing better is on the page
    return (True, weak[0][:240]) if weak else (False, '')


# ---------------- pages that are about a programme but are not the programme ----------------
# the last part of the address: FAQ, how to apply, curriculum, fees ... (a sub-page of a programme)
SUBPAGE_LEAF = re.compile(
    r"^(?:faqs?|frequently-asked-questions|how-to-apply|apply(?:ing)?(?:-now|-online)?|applications?|admissions?|admission-requirements|"
    r"entry-requirements|requirements|requirements-deadlines|deadlines|curriculum|academics|careers?|career-outcomes|contact(?:-us)?|"
    r"fees?|fees-and-funding|tuition|funding|scholarships?|news|events?|people|faculty|staff|alumni|financial-aid|costs?|visit|open-days?|"
    r"stay-touch|ask-admissions[\w-]*|after-your-admission[\w-]*|how-do-i-apply|international-applicants?)(?:\.html?|\.php|\.aspx)?$", re.I)
# a single course unit inside a degree: .../courses/indg-5011/
UNIT_URL = re.compile(r"/(?:courses?|units?|subjects?|modules?)/[a-z]{2,6}[-_ ]?\d{3,5}[a-z]?/?$", re.I)
# a branch campus in another country, as the first part of the address: /dubai/study/..., /malaysia/study/...
BRANCH_CAMPUS = {'dubai': 'uae', 'abu-dhabi': 'uae', 'malaysia': 'malaysia', 'singapore': 'singapore', 'qatar': 'qatar', 'china': 'china',
                 'ningbo': 'china', 'suzhou': 'china', 'mauritius': 'mauritius', 'bangalore': 'india', 'india': 'india', 'kazakhstan': 'kazakhstan'}
# names that are pages about studying, not programmes
NOT_PROGRAMME_NAME = re.compile(
    r"^(?:general )?faqs?\b|\bfrequently asked\b|\bhow to apply\b|^apply(?:ing)?\b|\bapplication and admission\b|^admissions?\b|\badmissions? (?:office|overview|requirements?|and tuition)\b|"
    r"\brequirements?(?: (?:&|and) deadlines)?$|\bcurriculum$|^academics$|^contact\b|\bcontact (?:the|us)\b|\bopen days?\b|\bscholarships?$|^scholarships?\b|\bloans?$|"
    r"^funding\b|\bgraduate calendar\b|^regulations? for\b|\bassessment procedure\b|^average salary$|^careers?\b|\bcareer experience\b|^levels and degrees$|\bflexible degree options\b|"
    r"\bafter your admission\b|^ask admissions\b|^programs? and courses$|^study$|^(?:undergraduate|postgraduate|graduate) study\b|^beginner|\bmasterful\b|\bmaster class\b|\bmasters? project \d\b|"
    r"^[A-Z]{3,5}\s?\d{4}\b|"
    r"\b(?:language|inherent|entry|admission) requirements\b|\brequirements (?:and|&) (?:exemptions|procedures?)\b|\bcurriculum (?:&|and) courses\b|\benrol(?:l)?ment in\b|"
    r"\bpresentation event\b|\boffice$|^international students\b|\bapplication$|^accelerated (?:bachelor|master)\S* (?:stream|pathway|option)$", re.I)
GENERIC_NAME = re.compile(
    r"^(?:overview )?(?:the )?(?:undergraduate |postgraduate |graduate )?(?:bachelor|master)(?:['’]?s)?(?: (?:degree|degrees|programmes?|programs?|education|studies|overview|open days?))*$", re.I)


def not_programme_url(url, country=''):
    """Reason a web address cannot be a single programme page, or ''."""
    sp = re.sub(r'^https?://[^/]+', '', url).split('?')[0].split('#')[0]
    segs = [x for x in sp.split('/') if x]
    if segs and SUBPAGE_LEAF.match(segs[-1]):
        return 'programme-subpage'
    if UNIT_URL.search(sp):
        return 'course-unit-page'
    if segs:
        home = BRANCH_CAMPUS.get(segs[0].lower())
        if home and home != country:
            return 'other-country-campus'
    return ''


def not_programme_name(name):
    n = (name or '').strip()
    if NOT_PROGRAMME_NAME.search(n) or GENERIC_NAME.match(n):
        return 'not-a-programme-name'
    return ''
