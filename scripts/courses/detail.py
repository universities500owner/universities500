#!/usr/bin/env python3
"""Course detail: what a student reads on the university's own course page, kept in sections and facts.

The reader (run.py) decides WHICH pages are courses. This module reads WHAT is on each course page, so the site can show overview,
fees, entry requirements, modules, teaching, careers and deadlines the way the university's page does, instead of four facts.

A model does only two small jobs, and code does the rest:
  1. LABEL the page's sections ("this heading is entry requirements") and pick out short facts, each with the exact sentence it came from.
  2. Nothing else. The text of a section is COPIED by code from the page, never written by the model.
Then code CHECKS every sentence and every name the model returned against the page text. Anything that is not on the page is thrown
away, so a wrong or invented value cannot reach the site. A fact the model could not support stays empty.

The page text comes from the same reader as everywhere else (robots.txt obeyed, polite, identified). The model never browses.

    python3 scripts/courses/detail_run.py prepare|submit|collect ...      (see that file)
"""
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'scholarships'))
import extract as X  # noqa: E402

MODEL = 'claude-haiku-5-5'
SCHEMA_VERSION = 2

# What a section can be labelled. "other" is anything the course page does not need (contact box, related links, news).
SECTION_TYPES = ['overview', 'key_facts', 'fees', 'entry_requirements', 'english_requirements', 'modules', 'teaching_assessment',
                 'careers', 'accreditation', 'scholarships', 'how_to_apply', 'deadlines', 'objectives', 'industry_placements', 'other']
# Sections whose own words are shown on the page (copied by code, in page order; a type may have several blocks). The rest are used for facts only.
SHOWN_SECTIONS = ['overview', 'entry_requirements', 'english_requirements', 'modules', 'teaching_assessment', 'careers', 'accreditation', 'scholarships', 'how_to_apply', 'deadlines',
                  'objectives', 'industry_placements']
MAX_SECTION_CHARS = 6000          # what one section may keep
MAX_PROMPT_SECTION = 3500         # how much of one section the model is shown
MAX_PROMPT_CHARS = 40000          # about 10,000 tokens: a page's fees and requirements often sit low on it

HEADING = re.compile(r'^h([1-6])$')
MARK = '§H'


# ---------------- the page as sections ----------------
def sections_of(html, url='', max_chars=MAX_SECTION_CHARS):
    """[{'id', 'level', 'heading', 'text'}]: the page's main content cut at its headings. Text is what the reader keeps (menus, footers and forms dropped)."""
    soup = X.soup_of(html)
    main = X.main_node(soup)
    for h in main.find_all(HEADING):
        if X._gone(h):
            continue
        n = HEADING.match(h.name).group(1)
        txt = re.sub(r'\s+', ' ', h.get_text(' ', strip=True))
        h.clear()
        h.append(f'{MARK}{n}§ {txt}')
    raw = [re.sub(r'\s+', ' ', x).strip() for x in main.get_text('\n').split('\n')]
    out, cur, last = [], {'level': 0, 'heading': '', 'lines': []}, None
    for line in raw:
        if not line:
            continue
        m = re.match(rf'^{MARK}([1-6])§\s*(.*)$', line)
        if m:
            if cur['lines'] or cur['heading']:
                out.append(cur)
            cur = {'level': int(m.group(1)), 'heading': m.group(2), 'lines': []}
            last = None
            continue
        if line == last:
            continue
        cur['lines'].append(line)
        last = line
    if cur['lines'] or cur['heading']:
        out.append(cur)
    secs = []
    for s in out:
        text = '\n'.join(s['lines'])
        if not text and not s['heading']:
            continue
        secs.append({'id': len(secs), 'level': s['level'], 'heading': s['heading'], 'text': text[:max_chars]})
    return secs


def title_of(html):
    """The page's <title> text, which names the course on most pages. It is part of the text a quote may be found in."""
    t = X.soup_of(html).find('title')
    return re.sub(r'\s+', ' ', t.get_text(' ', strip=True)) if t else ''


def page_text(secs):
    """The text a quote must be found in: every heading and line of every section."""
    return '\n'.join(f"{s['heading']}\n{s['text']}" for s in secs)


def page_hash(secs):
    return hashlib.sha1(page_text(secs).encode('utf-8')).hexdigest()[:16]


def norm(text):
    """Lower case, one kind of quote and dash, no spaces or markup: so a quote matches however the page spaced it.
    Soft hyphens and zero-width characters (pages use them to break long words, as "Archi\u00adtec\u00adtural") are not part of the text."""
    t = re.sub('[\u00ad\u200b-\u200d\u2060\ufeff]', '', text or '').lower().replace('\u00a0', ' ')
    t = re.sub(r'[\u2018\u2019\u201a\u2032]', "'", t)
    t = re.sub(r'[\u201c\u201d\u201e\u2033]', '"', t)
    t = re.sub(r'[\u2010-\u2015\u2212]', '-', t)
    t = re.sub(r'[*_`]+', '', t)
    return re.sub(r'\s+', ' ', t).strip()


def present(snippet, haystack_norm):
    s = norm(snippet)
    return len(s) >= 3 and s in haystack_norm


# ---------------- what the model is asked ----------------
SYSTEM = (
    "You read one university course page that has been cut into numbered sections. Your job is to label the sections and copy out short facts. "
    "You never write, summarise or rephrase: every fact you return must come with a QUOTE, copied exactly from the page, that shows it. "
    "If the page does not state a fact, leave it out (null or empty). Never guess a start month, a fee, a score or a date. "
    "Every 'text' you give is copied exactly as the page writes it (for example '1 year full-time', 'September 2027'), never reworded or converted. "
    "The page may be for a home-students version of a course: only call a fee 'international' if the page says international, overseas or non-EU/non-UK. "
    "Section types: overview (what the course is, who it suits), key_facts (a box of duration, mode, campus, code), fees, entry_requirements (academic), "
    "english_requirements, modules (core and optional units), teaching_assessment (how it is taught and assessed), careers (outcomes, employers, further study), "
    "accreditation (professional bodies), scholarships (funding for this course), how_to_apply, deadlines, "
    "objectives (aims, what the course sets out to do, learning outcomes), industry_placements (industry links, partner companies, internships, work placements, co-op), "
    "other (contact boxes, news, related courses, anything else). "
    "Also say what the page is: 'level' is bachelor, master, doctorate, other_award (diploma, certificate, short course, foundation) or not_a_degree_page (news, event, department, listing, anything that is not one course). "
    "'delivery' is on_campus, online (online or distance learning), blended or unclear: say on_campus only when the page says the course is taught on campus or in person, and online when the page says online or distance. "
    "'international' is open when the page says international students can apply or lists international entry requirements or fees, restricted when it says they cannot, otherwise unstated. "
    "Each of these needs a quote. If the page is not one course, still fill 'level' and leave the rest empty. "
    "Give one entry per section that is not 'other'. Call the record_course_detail tool."
)

LEVELS = ['bachelor', 'master', 'doctorate', 'other_award', 'not_a_degree_page']
DELIVERIES = ['on_campus', 'online', 'blended', 'unclear']
INTERNATIONALS = ['open', 'restricted', 'unstated']
REQUIREMENT_KINDS = ['test', 'portfolio', 'interview', 'work_experience', 'documents', 'prerequisites', 'other']

TOOL = {
    'name': 'record_course_detail',
    'description': 'Record the section labels and the facts found on the course page, each fact with an exact quote from the page.',
    'input_schema': {
        'type': 'object',
        'properties': {
            'sections': {'type': 'array', 'items': {'type': 'object', 'properties': {
                'id': {'type': 'integer'}, 'type': {'type': 'string', 'enum': SECTION_TYPES}}, 'required': ['id', 'type']}},
            'duration': {'type': ['object', 'null'], 'properties': {'text': {'type': 'string'}, 'quote': {'type': 'string'}}},
            'study_mode': {'type': ['object', 'null'], 'properties': {'text': {'type': 'string'}, 'quote': {'type': 'string'}}},
            'campus': {'type': ['object', 'null'], 'properties': {'text': {'type': 'string'}, 'quote': {'type': 'string'}}},
            'starts': {'type': 'array', 'items': {'type': 'object', 'properties': {'text': {'type': 'string'}, 'quote': {'type': 'string'}}, 'required': ['text', 'quote']}},
            'fees': {'type': 'array', 'items': {'type': 'object', 'properties': {
                'audience': {'type': 'string', 'enum': ['international', 'home', 'eu', 'other']},
                'amount': {'type': 'number'}, 'currency': {'type': 'string'},
                'period': {'type': 'string', 'enum': ['year', 'total', 'term', 'credit', 'unknown']},
                'year_label': {'type': ['string', 'null']}, 'quote': {'type': 'string'}},
                'required': ['audience', 'amount', 'currency', 'period', 'quote']}},
            'deadlines': {'type': 'array', 'items': {'type': 'object', 'properties': {
                'label': {'type': 'string'}, 'date_text': {'type': 'string'}, 'quote': {'type': 'string'}}, 'required': ['label', 'date_text', 'quote']}},
            'ielts': {'type': ['object', 'null'], 'properties': {'overall': {'type': 'number'}, 'min_band': {'type': ['number', 'null']}, 'quote': {'type': 'string'}}},
            'other_english_tests': {'type': 'array', 'items': {'type': 'object', 'properties': {
                'test': {'type': 'string'}, 'score_text': {'type': 'string'}, 'quote': {'type': 'string'}}, 'required': ['test', 'score_text', 'quote']}},
            'academic_entry': {'type': ['object', 'null'], 'properties': {'text': {'type': 'string'}, 'quote': {'type': 'string'}}},
            'core_modules': {'type': 'array', 'items': {'type': 'string'}},
            'optional_modules': {'type': 'array', 'items': {'type': 'string'}},
            'employers': {'type': 'array', 'items': {'type': 'string'}},
            'accreditations': {'type': 'array', 'items': {'type': 'string'}},
            'course_name': {'type': ['object', 'null'], 'properties': {'text': {'type': 'string'}, 'quote': {'type': 'string'}}},
            'faculty': {'type': ['object', 'null'], 'properties': {'text': {'type': 'string'}, 'quote': {'type': 'string'}}},
            'level': {'type': ['object', 'null'], 'properties': {'value': {'type': 'string', 'enum': LEVELS}, 'quote': {'type': 'string'}}},
            'delivery': {'type': ['object', 'null'], 'properties': {'value': {'type': 'string', 'enum': DELIVERIES}, 'quote': {'type': 'string'}}},
            'international': {'type': ['object', 'null'], 'properties': {'value': {'type': 'string', 'enum': INTERNATIONALS}, 'quote': {'type': 'string'}}},
            'scholarship_items': {'type': 'array', 'items': {'type': 'object', 'properties': {
                'name': {'type': 'string'}, 'amount_text': {'type': ['string', 'null']}, 'quote': {'type': 'string'}}, 'required': ['name', 'quote']}},
            'additional_requirements': {'type': 'array', 'items': {'type': 'object', 'properties': {
                'kind': {'type': 'string', 'enum': REQUIREMENT_KINDS}, 'text': {'type': 'string'}, 'quote': {'type': 'string'}}, 'required': ['kind', 'text', 'quote']}},
            'industry_links': {'type': 'array', 'items': {'type': 'object', 'properties': {'text': {'type': 'string'}, 'quote': {'type': 'string'}}, 'required': ['text', 'quote']}},
            'internships': {'type': 'array', 'items': {'type': 'object', 'properties': {'text': {'type': 'string'}, 'quote': {'type': 'string'}}, 'required': ['text', 'quote']}},
        },
        'required': ['sections'],
    },
}


def prompt_of(secs, url='', title=''):
    parts, used = [f'Course page: {url}'] if url else [], 0
    if title:
        parts.append(f'Page title: {title}')
    for s in secs:
        body = s['text'][:MAX_PROMPT_SECTION]
        block = f"[S{s['id']}] {'#' * max(1, s['level'])} {s['heading'] or '(no heading)'}\n{body}"
        if used + len(block) > MAX_PROMPT_CHARS:
            break
        parts.append(block)
        used += len(block)
    return '\n\n'.join(parts)


def request_of(custom_id, secs, url='', model=MODEL, title=''):
    """One Batch API request (a line of the batch)."""
    return {'custom_id': custom_id, 'params': {
        'model': model, 'max_tokens': 4500, 'system': SYSTEM,
        'tools': [TOOL], 'tool_choice': {'type': 'tool', 'name': 'record_course_detail'},
        'messages': [{'role': 'user', 'content': prompt_of(secs, url, title)}]}}


# ---------------- checking what came back ----------------
def _quoted(item, hay, key='quote'):
    return isinstance(item, dict) and bool(item.get(key)) and present(item[key], hay)


def _digits(s):
    return re.sub(r'\D', '', str(s))


NUMBER = re.compile(r'\d[\d,]*(?:\.\d+)?')
INTL = re.compile(r'international|overseas|non[- ]?(?:uk|eu)|outside (?:of )?the (?:uk|eu)|worldwide', re.I)


def _amount_in(quote, amount):
    """The amount is one of the numbers written in the quote ('28,100' for 28100). '100' is not found in '1,000'."""
    for m in NUMBER.findall(quote or ''):
        try:
            if abs(float(m.replace(',', '')) - float(amount)) < 0.005:
                return True
        except ValueError:
            pass
    return False


def shown_text(item, key, hay):
    """The short text to show for a fact: the model's own words if they are on the page, otherwise the quote itself when it is short, otherwise nothing."""
    t, q = (item.get(key) or '').strip(), (item.get('quote') or '').strip()
    if t and present(t, hay):
        return t
    return q if 0 < len(q) <= 140 else ''


def verify(tool_input, secs, title=''):
    """Return (detail, rejected). `detail` holds only what the page supports; `rejected` lists what was thrown away and why."""
    hay = norm(page_text(secs) + '\n' + (title or ''))
    rejected = []
    ti = tool_input or {}

    def one(name):
        v = ti.get(name)
        if not v:
            return None
        if _quoted(v, hay):
            t = shown_text(v, 'text', hay)
            if t:
                return {'text': t, 'quote': v['quote'].strip()}
        rejected.append((name, 'quote-not-on-page'))
        return None

    def many(name):
        out = []
        for v in ti.get(name) or []:
            if _quoted(v, hay):
                out.append(v)
            else:
                rejected.append((name, 'quote-not-on-page'))
        return out

    facts = {
        'duration': one('duration'), 'studyMode': one('study_mode'), 'campus': one('campus'), 'academicEntry': one('academic_entry'),
        'starts': [{'text': shown_text(v, 'text', hay), 'quote': v['quote'].strip()} for v in many('starts') if shown_text(v, 'text', hay)],
        'deadlines': [{'label': v['label'].strip(), 'date': shown_text(v, 'date_text', hay), 'quote': v['quote'].strip()} for v in many('deadlines')
                      if (v.get('label') or '').strip() and shown_text(v, 'date_text', hay)],
        'otherEnglish': [{'test': v['test'].strip(), 'score': shown_text(v, 'score_text', hay), 'quote': v['quote'].strip()} for v in many('other_english_tests')
                         if (v.get('test') or '').strip() and shown_text(v, 'score_text', hay)],
        'fees': [], 'ielts': None,
    }
    for v in many('fees'):
        try:
            amount = float(v['amount'])
        except (TypeError, ValueError, KeyError):
            rejected.append(('fees', 'no-amount'))
            continue
        if amount <= 0 or not _amount_in(v['quote'], amount):
            rejected.append(('fees', 'amount-not-in-quote'))
            continue
        audience = v['audience']
        if audience == 'international' and not INTL.search(v['quote']):
            audience = 'other'                      # the page's own words do not say international: never present it as the international fee
            rejected.append(('fees', 'international-not-in-quote'))
        facts['fees'].append({'audience': audience, 'amount': int(amount) if amount.is_integer() else amount, 'currency': (v.get('currency') or '').strip().upper()[:3],
                              'period': v['period'], 'year': (v.get('year_label') or None), 'quote': v['quote'].strip()})
    ie = ti.get('ielts')
    if ie:
        if _quoted(ie, hay) and isinstance(ie.get('overall'), (int, float)) and 4 <= ie['overall'] <= 9 and re.search(re.escape(f"{ie['overall']:g}"), ie['quote']):
            facts['ielts'] = {'overall': ie['overall'], 'minBand': ie.get('min_band') if isinstance(ie.get('min_band'), (int, float)) else None, 'quote': ie['quote'].strip()}
        else:
            rejected.append(('ielts', 'score-or-quote-not-on-page'))
    for key, name in (('coreModules', 'core_modules'), ('optionalModules', 'optional_modules'), ('employers', 'employers'), ('accreditations', 'accreditations')):
        got = []
        for n in ti.get(name) or []:
            if isinstance(n, str) and present(n, hay) and n.strip() not in got:
                got.append(n.strip())
            else:
                rejected.append((name, 'name-not-on-page'))
        facts[key] = got

    # what the page is, and the fields added for the pilot: each needs a quote that is on the page
    def pick(name, allowed):
        v = ti.get(name)
        if not v:
            return None
        if _quoted(v, hay) and v.get('value') in allowed:
            return {'value': v['value'], 'quote': v['quote'].strip()}
        rejected.append((name, 'value-or-quote-not-on-page'))
        return None

    facts['level'] = pick('level', LEVELS)
    facts['delivery'] = pick('delivery', DELIVERIES)
    facts['international'] = pick('international', INTERNATIONALS)
    facts['faculty'] = one('faculty')
    name = one('course_name')
    if not name:
        h1 = next((s['heading'] for s in secs if s['level'] == 1 and s['heading']), '')       # the page's own main heading, taken by code
        name = {'text': h1, 'quote': h1} if h1 else None
    facts['courseName'] = name
    facts['scholarships'] = [{'name': shown_text(v, 'name', hay), 'amount': (v.get('amount_text') or '').strip() if present(v.get('amount_text') or '', hay) else '', 'quote': v['quote'].strip()}
                             for v in many('scholarship_items') if shown_text(v, 'name', hay)]
    facts['additionalRequirements'] = [{'kind': v['kind'] if v.get('kind') in REQUIREMENT_KINDS else 'other', 'text': shown_text(v, 'text', hay), 'quote': v['quote'].strip()}
                                       for v in many('additional_requirements') if shown_text(v, 'text', hay)]
    for key, name_ in (('industryLinks', 'industry_links'), ('internships', 'internships')):
        facts[key] = [{'text': shown_text(v, 'text', hay), 'quote': v['quote'].strip()} for v in many(name_) if shown_text(v, 'text', hay)]

    labels = {}
    for s in ti.get('sections') or []:
        if isinstance(s, dict) and isinstance(s.get('id'), int) and 0 <= s['id'] < len(secs) and s.get('type') in SECTION_TYPES:
            labels.setdefault(s['id'], s['type'])
    shown = {}
    for sid, typ in sorted(labels.items()):
        sec = secs[sid]
        if typ in SHOWN_SECTIONS and (sec['text'].strip()):
            blocks = shown.setdefault(typ, [])
            if sum(len(b['text']) for b in blocks) + len(sec['text']) <= 2 * MAX_SECTION_CHARS:
                blocks.append({'heading': sec['heading'], 'text': sec['text']})       # copied by code, never by the model
    return {'v': SCHEMA_VERSION, 'facts': facts, 'sections': shown}, rejected



def eligibility(detail):
    """The reader's own rule for what the site lists, applied to what the model found: 'yes' (a bachelor's or master's, on campus, and the page does not say
    international students cannot apply), 'maybe' (the same, but the page does not say whether it is taught on campus or open to international students,
    and says nothing about online study), or 'no'. Each reason is a word from the page's own quote, never the model's opinion."""
    f = (detail or {}).get('facts') or {}
    level, delivery, intl = (f.get(k) or {} for k in ('level', 'delivery', 'international'))
    if level.get('value') not in ('bachelor', 'master'):
        return 'no'
    if delivery.get('value') in ('online', 'blended') or intl.get('value') == 'restricted':
        return 'no'
    if delivery.get('value') == 'on_campus' and intl.get('value') == 'open':
        return 'yes'
    return 'maybe'


# The fields a student wants from a course page, and where each one lives in a checked detail record.
# (University name and the course's web address are known to code, so they are not listed.)
FIELDS = [
    ('Course name', lambda f, s: f.get('courseName')),
    ('Overview', lambda f, s: s.get('overview')),
    ('Faculty or school', lambda f, s: f.get('faculty')),
    ('Tuition fee (international, per year)', lambda f, s: any(x.get('audience') == 'international' and x.get('period') == 'year' for x in f.get('fees') or [])),
    ('Tuition fee (any)', lambda f, s: f.get('fees')),
    ('Scholarships', lambda f, s: f.get('scholarships') or s.get('scholarships')),
    ('Admission requirement', lambda f, s: f.get('academicEntry') or s.get('entry_requirements')),
    ('English test requirement', lambda f, s: f.get('ielts') or f.get('otherEnglish') or s.get('english_requirements')),
    ('Additional tests or requirements', lambda f, s: f.get('additionalRequirements')),
    ('Programme objectives', lambda f, s: s.get('objectives')),
    ('Career outcomes', lambda f, s: s.get('careers') or f.get('employers')),
    ('Industry connections', lambda f, s: f.get('industryLinks') or s.get('industry_placements')),
    ('Internships or placements', lambda f, s: f.get('internships')),
]


def fields_present(detail):
    """The names of the fields this page filled, after checking."""
    f, s = (detail or {}).get('facts') or {}, (detail or {}).get('sections') or {}
    return [name for name, has in FIELDS if has(f, s)]


def empty_detail():
    return {'v': SCHEMA_VERSION, 'facts': {}, 'sections': {}}


def has_content(detail):
    f = (detail or {}).get('facts') or {}
    return bool((detail or {}).get('sections')) or any(f.get(k) for k in f if k != 'courseName')       # a page title alone is not content


def parse_tool_input(message_content):
    """The record_course_detail input from a response's content blocks (dicts or SDK objects), or None."""
    for block in message_content or []:
        if isinstance(block, dict):
            typ, name, inp = block.get('type'), block.get('name'), block.get('input')
        else:
            typ, name, inp = getattr(block, 'type', None), getattr(block, 'name', None), getattr(block, 'input', None)
        if typ == 'tool_use' and name == 'record_course_detail':
            return inp if isinstance(inp, dict) else None
    return None


def dump(doc):
    """One page per line, so a git diff shows what changed."""
    head = {k: v for k, v in doc.items() if k != 'pages'}
    lines = ['{']
    for k, v in head.items():
        lines.append(f'"{k}": {json.dumps(v, ensure_ascii=False)},')
    lines.append('"pages": {')
    lines.append(',\n'.join(f'{json.dumps(u, ensure_ascii=False)}: {json.dumps(d, ensure_ascii=False)}' for u, d in sorted(doc['pages'].items())))
    lines.append('}')
    lines.append('}')
    return '\n'.join(lines) + '\n'
