"""Decides whether a job title is an internship, and what kind. Whole-word matching only, so
"Internal Auditor" and "International Sales" never match. No AI: plain patterns."""
import html
import re

R = lambda p: re.compile(p, re.I)

COOP = R(r"\bco[- ]?op\b")
PLACEMENT = R(r"\b(industrial placement|placement year|year in industry|sandwich (?:placement|year)|placement student|summer placement|(?:12|twelve|6|six)[- ]month placement)\b")
WORKING_STUDENT = R(r"\b(werkstudent(?:in)?|working student|student worker)\b")
INTERN = R(r"\b(interns?|internships?|summer (?:analyst|associate|student)|praktikum|praktikant(?:in)?|pflichtpraktikum|stagiaires?|stagiair|afstudeerstage|(?:sommar)?praktik(?:ant(?:er)?|plats(?:er)?)?)\b")
# 'stage' is a French and Dutch word for internship, and an English word for much else. Only trusted in France and the Netherlands.
STAGE = R(r"\bstage\b")
STAGE_ENGLISH = R(r"\b(stage (?:manager|hand|crew|director|design\w*|production|lighting|gate|lead)|(?:late|early|growth|seed|pre[- ]seed|mid|series [a-z]) stage|stage[- ]gate|stage[- ]\d)\b")

# Staff who run internship programmes are not internships.
STAFF = R(r"\b(interns?|internships?)\s+(?:program(?:me)?\s+)?(coordinator|manager|lead|recruiter|director|specialist|partner|administrator|advisor|adviser|supervisor|mentor)\b|\b(recruiter|coordinator|manager)\b.*\b(interns?|internships?)\b")
# This site is for Bachelor's and Master's students.
NOT_OUR_LEVEL = R(r"\b(ph\.?d\.?|doctoral|doctorate|high[- ]school|secondary school|k-12|school leaver)\b")


def clean_title(t):
    t = html.unescape(t or '')
    t = re.sub(r'\s+', ' ', t).strip(' -–|,;')
    return t[:140]


def classify(title, country=None, structured=None):
    """Returns 'Co-op', 'Placement', 'Working student', 'Internship' or None.
    structured: a flag from the employer's own system (such as employment type "Intern"), which counts as a match."""
    t = clean_title(title)
    if not t or NOT_OUR_LEVEL.search(t) or STAFF.search(t):
        return None
    if COOP.search(t):
        return 'Co-op'
    if PLACEMENT.search(t):
        return 'Placement'
    if WORKING_STUDENT.search(t):
        return 'Working student'
    if INTERN.search(t):
        return 'Internship'
    if country in ('france', 'netherlands') and STAGE.search(t) and not STAGE_ENGLISH.search(t):
        return 'Internship'
    if structured:
        return 'Internship'
    return None


def structured_intern(value):
    """True for the employer's own 'Intern' labels (employment type, commitment, experience level)."""
    v = (value or '')
    if isinstance(v, dict):
        v = v.get('label') or v.get('id') or ''
    v = str(v).strip().lower()
    return v in ('intern', 'interns', 'internship', 'internships', 'intern / co-op', 'stage', 'praktikum')
