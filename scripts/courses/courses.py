"""Turn one course page into a course record, or say why it is not one. No AI: structure, headings and patterns only.

A record is kept only if the page itself shows all three of these:
  - a Bachelor's or Master's degree (not a PhD, diploma, certificate, foundation or pathway course)
  - full-time study on campus (not online, not distance, not part-time only)
  - that international students can take it (an international fee, a CRICOS code, or an international admissions sentence)
Everything else is counted in the run report with the reason, and is not published.
"""
import hashlib
import json
import re

import extract as X  # scripts/scholarships/extract.py (path is set by the caller)
import textutil as T
import levels as L
import facts as F

LD = re.compile(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.I | re.S)
SEG_SKIP = re.compile(r"\b(?:university|college|institute|polytechnic|school of|home|study at|courses?|programmes?|programs?)\b", re.I)
LISTING_LINKS = 8      # a page that links to this many programmes is a list, not one programme
SHORT_LINE = 90


def sentences_with_labels(text):
    """Sentences of the page, plus each short label joined to the line after it ("Study mode." + "Full-time.")."""
    base = T.sentences(text)
    out = []
    for i, s in enumerate(base):
        if len(s) <= 30 and not re.search(r'\d', s) and i + 1 < len(base) and len(base[i + 1]) <= 200:
            out.append(f'{s} {base[i + 1]}')
        out.append(s)
        if len(out) > 420:
            break
    return out


def jsonld(html):
    """schema.org Course / EducationalOccupationalProgram blocks. Read before Page() removes the scripts."""
    found = []
    for m in LD.finditer(html or ''):
        try:
            data = json.loads(m.group(1).strip())
        except ValueError:
            continue
        stack = [data]
        while stack:
            d = stack.pop()
            if isinstance(d, list):
                stack.extend(d)
            elif isinstance(d, dict):
                if '@graph' in d:
                    stack.extend(d['@graph'] if isinstance(d['@graph'], list) else [d['@graph']])
                t = d.get('@type')
                t = ' '.join(t) if isinstance(t, list) else (t or '')
                if re.search(r'Course|EducationalOccupationalProgram|Program', str(t)):
                    found.append(d)
    return found


def markup_facts(nodes):
    out = {'mode': '', 'years': None, 'starts': []}
    for d in nodes:
        inst = d.get('hasCourseInstance')
        inst = inst if isinstance(inst, list) else ([inst] if inst else [])
        for i in inst:
            if not isinstance(i, dict):
                continue
            cm = i.get('courseMode')
            cm = ' '.join(cm) if isinstance(cm, list) else (cm or '')
            if cm and not out['mode']:
                out['mode'] = cm
            sd = str(i.get('startDate') or '')
            m = re.match(r'(\d{4})-(\d{2})', sd)
            if m and int(m.group(2)) in F.SHORT and F.SHORT[int(m.group(2))] not in out['starts']:
                out['starts'].append(F.SHORT[int(m.group(2))])
        tr = str(d.get('timeRequired') or d.get('duration') or '')
        m = re.match(r'P(?:(\d+)Y)?(?:(\d+)M)?$', tr)
        if m and (m.group(1) or m.group(2)) and out['years'] is None:
            out['years'] = int(m.group(1) or 0) + int(m.group(2) or 0) / 12
        cm = d.get('courseMode') or d.get('educationalProgramMode')
        if cm and not out['mode']:
            out['mode'] = ' '.join(cm) if isinstance(cm, list) else str(cm)
    return out


def segments(title):
    parts = [p for p in T.TITLE_SEP.split(T.clean(title)) if p]
    return [p for p in parts if L.BACHELOR_TITLE.search(p) or L.MASTER_TITLE.search(p) or not SEG_SKIP.search(p)]


GENERIC_H1 = re.compile(r"^(?:(?:undergraduate|postgraduate|graduate)\s+)?(?:study|courses?|programmes?|programs?)(?: and courses?)?(?:\s+\d{4})?$|^(?:overview|degree overview|home|undergraduate|postgraduate|search|results?|admissions?)$", re.I)


def programme_name(page):
    cands = [page.h1] + segments(page.og_title) + segments(page.title_tag)
    for c in cands:
        c = T.clean(c)
        if 3 <= len(c) <= 160 and not GENERIC_H1.match(c):
            return c
    return ''


def identify(page):
    """Return (level, degree, flags, out_reason). The programme's own title decides; the lines under it may add the degree."""
    heads = [page.h1] + segments(page.og_title) + segments(page.title_tag)
    heads = [h for h in heads if h]
    for h in heads:
        level, degree, flags, reason = L.classify_title(h)
        if level:
            return level, degree, flags, ''
        if reason and reason not in ('no-title', 'no-degree-designation'):
            return None, '', {}, reason
    # the title is the subject ("Computer Science") and the degree sits on the next line ("BSc (Hons)")
    if count_course_links(page) >= 3:
        return None, '', {}, 'no-degree-designation'   # a list of programmes: its lines are other programmes' names
    link_texts = {T.clean(t) for _h, t in page.links}
    for line in page.lines[:8]:
        if len(line) <= SHORT_LINE and line not in link_texts:
            level, degree, flags, reason = L.classify_title(line)
            if level:
                return level, degree, flags, ''
    return None, '', {}, 'no-degree-designation'


def count_course_links(page):
    n = 0
    seen = set()
    for href, text in page.links:
        if text and len(text) <= 140 and href not in seen and (L.BACHELOR_TITLE.search(text) or L.MASTER_TITLE.search(text)):
            seen.add(href)
            n += 1
    return n


def _hash(rec):
    keys = ('name', 'degree', 'level', 'studyMode', 'international', 'fee', 'duration', 'intakes', 'ielts', 'cricos', 'field')
    return hashlib.sha1(json.dumps({k: rec.get(k) for k in keys}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]


def course_id(uni_slug, name, url):
    return f"{uni_slug}:{T.slugify(name, 60)}:{hashlib.sha1(url.encode()).hexdigest()[:6]}"


def read_course(page, html, uni, today, uni_intl=None, strict_international=False, register=None):
    """Return (record, reason). `record` is None when the page is not an eligible course; `reason` says why.

    `uni_intl` is {'url', 'evidence'} when the university's own admissions pages show it takes international students.
    `register` (cricos.Register) is the government list of this university's courses for international students (Australia only).
    A page whose programme name matches exactly one registered course is open to international students even when the page does not
    say so; the code is saved with how="cricos" and `cricosMatch: "name"`, so it is clear the page itself did not quote it.
    """
    level, degree, flags, out = identify(page)
    if not level:
        return None, ('not-a-course-page' if out == 'no-degree-designation' else out)
    url_out = L.classify_url(page.url)
    if url_out:
        return None, url_out
    not_prog = L.not_programme_url(page.url, uni.get('country', ''))
    if not_prog:
        return None, not_prog
    if count_course_links(page) >= LISTING_LINKS:
        return None, 'listing-page'
    name = programme_name(page)
    if len(name) < 3:
        return None, 'no-name'
    if L.not_programme_name(name):
        return None, 'not-a-programme-name'
    sents = sentences_with_labels(page.text)
    nodes = jsonld(html)
    mk = markup_facts(nodes)

    mode, mode_ev = L.study_mode(sents, name, page.url, mk['mode'])
    if mode == 'no':
        return None, 'online-or-part-time'
    cricos = ''
    m = L.CRICOS.search(page.text)
    if m:
        cricos = m.group(1).upper()
    intl, how, intl_ev = L.international(sents, cricos)
    if intl == 'no':
        return None, 'domestic-only'
    matched = ''
    if register and not cricos:
        matched = register.unique(name, degree)
        if matched:
            cricos = matched
            if intl == 'unclear':
                intl, how = 'yes', 'cricos'
                intl_ev = (f'CRICOS course code {matched}. The programme name matches one course on the government register of courses for '
                           f'international students; the page itself does not show the code.')
    if intl == 'unclear' and uni_intl and not strict_international:
        intl, how, intl_ev = 'yes', 'university', f"The university's admissions page says it takes international students: {uni_intl['evidence']}"
    if mode != 'yes':
        return None, 'study-mode-unclear'
    if intl != 'yes':
        return None, 'international-unclear'

    fee = F.find_fee(sents, uni.get('country'))
    dur = F.find_duration(sents, level)
    if not dur and mk['years'] and ((level == 'Bachelor' and 2.5 <= mk['years'] <= 6.5) or (level == 'Master' and 0.5 <= mk['years'] <= 3.5)):
        dur = {'display': f"{mk['years']:g} years", 'years': round(mk['years'], 2), 'context': 'Page markup (schema.org Course)'}
    ints = F.find_intakes(sents)
    if not ints and mk['starts']:
        ints = {'months': mk['starts'][:5], 'context': 'Page markup (schema.org Course)'}
    ielts = F.find_ielts(sents)

    rec = {
        'id': course_id(uni['slug'], name, page.url),
        'university': uni['slug'],
        'name': name,
        'degree': degree,
        'level': level,
        'field': F.find_field(name),
        'url': page.url,
        'studyMode': {'verdict': 'full-time on campus', 'evidence': mode_ev},
        'international': {'how': how, 'evidence': intl_ev},
        'fee': fee,
        'duration': dur,
        'intakes': ints,
        'ielts': ielts,
        'cricos': cricos or None,
        'cricosMatch': 'name' if matched else None,
        'flags': sorted(flags) or None,
        'firstSeen': today,
        'lastVerified': today,
        'lastChanged': today,
    }
    rec['hash'] = _hash(rec)
    return rec, ''
