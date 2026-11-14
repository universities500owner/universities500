#!/usr/bin/env python3
"""Turn a destination article pack (.docx) into one JSON file per article in src/data/articles/.

    python3 scripts/articles/import_docx.py pack1.docx pack2.docx [--out src/data/articles] [--report out/articles_report.md]

What it keeps: headline, introduction, quick answer, the numbered sections (with tables, lists and call-outs),
the FAQs and the official sources.
What it leaves out: the editors' notes (editorial standards, SEO and publishing metadata, product and GEO build
briefs, accuracy notes, pre-publication checklists, appendices). The SEO title, meta description and URL slug
are read from those notes and stored as fields, never shown as article text.

Needs pandoc (apt install pandoc). No AI: the packs have a regular layout and this reads it by pattern.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

PREFIX = {'AUS': 'australia', 'USA': 'usa', 'UK': 'uk', 'CAN': 'canada', 'IRE': 'ireland', 'NZ': 'new-zealand', 'SGP': 'singapore',
          'NLD': 'netherlands', 'MYS': 'malaysia', 'NOR': 'norway', 'SWE': 'sweden', 'UAE': 'uae', 'FRA': 'france', 'GER': 'germany', 'GLB': 'global'}
TOPICS = {  # the pack's category -> (slug, label shown to students)
    'cost & budgeting': ('cost-and-budgeting', 'Costs and budgeting'),
    'visa & compliance': ('visas', 'Visas and paperwork'),
    'post-study & pr': ('after-study', 'Work after study'),
    'admissions & tests': ('admissions', 'Admissions and tests'),
    'universities & courses': ('universities-and-courses', 'Universities and courses'),
    'student life & work': ('student-life', 'Student life and work'),
    'finance & scholarships': ('scholarships-and-funding', 'Scholarships and funding'),
    'career & roi': ('careers', 'Careers and jobs'),
}
ID_RE = re.compile(r'^([A-Z]{2,4})-(\d{2})\s*\|\s*(.+)$')
META_RE = re.compile(r'^(Priority|Primary keyword|Secondary keywords?|Search intent|Proposed GEO|GEO\s*/|Workbook|Audience|Research cut-off)\b', re.I)
# sections that are notes for editors or builders, never for students
INTERNAL = re.compile(r'(\bSEO\b|metadata|publishing|publication|pre-publication|accuracy notes|editorial|research and legal|keyword clusters|^contents$|workbook)', re.I)
SOURCES_HEAD = re.compile(r'^(official sources?|primary sources?|sources?|further reading|source register|official source register)(?!\s+of\b)', re.I)
# a heading that starts the editors' back matter: everything after it, up to the FAQs or sources, is left out
TAIL = re.compile(
    r'(build brief|product brief|recommended tool|\bbrief$|interactive .*(brief|calculator)|suggested interactive|recommended (database|inputs|outputs|implementation|structured)|database fields|'
    r'data model|search-intent coverage|answer-first passages|suggested (internal links|images)|alt text|governance rules|seo (title|metadata|and)|metadata|'
    r'publishing (checklist|package)|pre-publication|publication (checklist|cautions)|corrections and|accuracy notes|editorial|appendix|research notes|'
    r'keyword|workbook|roadmap|structured content|geo and structured|geo implementation|geo, faqs|\(\d+ articles\)|faqs? (and|&) structured)', re.I)
EDITOR_ANY = re.compile(r'(a calculator should|do not publish|avoid publishing|should not publish)', re.I)
ARTICLE_MARK = re.compile(r'^article( draft| text| body| content)?$', re.I)
# sentences written for the editors or the page builders; dropped from the student-facing text and listed in the report
EDITOR_SENT = re.compile(
    r"(source (workbook|blueprint)|workbook|^for publication|student-facing calculator|^build a calculator|recommended interactive|proposed (interactive|city)|interactive element|"
    r"^verification note|before (the article goes live|publishing|publication)|immediately before publication|\bpublication\b.*\b(check|refresh)|^index only|reusable student tool|"
    r"should let (the )?students?|keep source dates visible|allow users to edit|^a calculator should|should be refreshed|must be rechecked|hard-code|evergreen content|"
    r"populate this comparison|do not invent a representative|^show the estimated|^record the source|refresh the statistics canada|"
    r"^show a clear warning|do not publish|avoid publishing|^a transparent earnings-offset|^show the official source url|do not rank cities as universally|do not mix ranking years|treat the current .* page as|this (pack|brief|working edition)|working edition|re-open each source)", re.I)
FAQ_HEAD = re.compile(r'^(frequently asked questions|faqs?)$', re.I)
QUICK_HEAD = re.compile(r'^quick answer$', re.I)
URL_RE = re.compile(r'https?://[^\s)>\]]+')


# ---------------- pandoc AST -> small block model ----------------
def runs_of(inlines, st=None):
    st = st or {}
    out = []
    for i in inlines:
        t = i['t']
        if t == 'Str':
            out.append({'t': i['c'], **st})
        elif t in ('Space', 'SoftBreak'):
            out.append({'t': ' ', **st})
        elif t == 'LineBreak':
            out.append({'br': 1})
        elif t == 'Strong':
            out += runs_of(i['c'], {**st, 'b': 1})
        elif t == 'Emph':
            out += runs_of(i['c'], {**st, 'i': 1})
        elif t == 'Link':
            href = i['c'][2][0]
            out += runs_of(i['c'][1], {**st, 'href': href})
        elif t == 'Quoted':
            q = '“”' if i['c'][0]['t'] == 'DoubleQuote' else '‘’'
            out += [{'t': q[0], **st}] + runs_of(i['c'][1], st) + [{'t': q[1], **st}]
        elif t in ('Underline', 'Span', 'SmallCaps', 'Superscript', 'Subscript', 'Strikeout'):
            out += runs_of(i['c'] if t != 'Span' else i['c'][1], st)
        elif t == 'Code':
            out.append({'t': i['c'][1], **st})
    return autolink(merge(out))


def autolink(runs):
    """A web address typed as plain text becomes a link."""
    out = []
    for r in runs:
        if 't' not in r or r.get('href') or not re.search(r'https?://', r['t']):
            out.append(r)
            continue
        pos = 0
        for m in URL_RE.finditer(r['t']):
            url = m.group(0).rstrip('.,;:)')
            end = m.start() + len(url)
            if m.start() > pos:
                out.append({**r, 't': r['t'][pos:m.start()]})
            out.append({**r, 't': url, 'href': url})
            pos = end
        if pos < len(r['t']):
            out.append({**r, 't': r['t'][pos:]})
    return out


def merge(runs):
    out = []
    for r in runs:
        if out and 't' in r and 't' in out[-1] and {k: v for k, v in r.items() if k != 't'} == {k: v for k, v in out[-1].items() if k != 't'}:
            out[-1]['t'] += r['t']
        else:
            out.append(dict(r))
    return out


def plain(runs):
    return ''.join(r.get('t', ' ') if 't' in r else ' ' for r in runs).strip()


def trim(runs):
    runs = [dict(r) for r in runs]
    while runs and 't' in runs[0] and not runs[0]['t'].strip():
        runs.pop(0)
    while runs and 't' in runs[-1] and not runs[-1]['t'].strip():
        runs.pop()
    if runs and 't' in runs[0]:
        runs[0]['t'] = runs[0]['t'].lstrip()
    if runs and 't' in runs[-1]:
        runs[-1]['t'] = runs[-1]['t'].rstrip()
    return runs


def list_items(items, ordered=False):
    out, checks = [], 0
    for blocks in items:
        first = next((b for b in blocks if b['t'] in ('Plain', 'Para')), None)
        rs = trim(runs_of(first['c'])) if first else []
        if rs and 't' in rs[0] and rs[0]['t'][:1] in '☐☑':
            checks += 1
            rs[0]['t'] = rs[0]['t'][1:].lstrip()
        it = {}
        # a bold lead-in at the start of the item, kept separate so it can be styled
        if rs and rs[0].get('b') and len(rs) > 1 and not all(r.get('b') for r in rs):
            lead = [dict(r) for r in rs if r.get('b')][:1]
            it['lead'] = [{k: v for k, v in lead[0].items() if k != 'b'}]
            rest = rs[1:]
            if rest and 't' in rest[0]:
                rest[0] = dict(rest[0])
                rest[0]['t'] = re.sub(r'^\s*[—–:-]\s*', ' ', rest[0]['t']) if re.match(r'^\s*[—–:-]\s', rest[0]['t']) else rest[0]['t']
            it['runs'] = trim(rest) if rest else []
            if rest and 't' in rest[0] and not rest[0]['t'].startswith(' ') and not re.match(r'^[.,;:]', rest[0]['t']):
                it['runs'][0]['t'] = ' ' + it['runs'][0]['t']
        else:
            it['runs'] = rs
        for b in blocks:
            if b['t'] == 'BulletList':
                it['sub'] = list_items(b['c'])['items']
            elif b['t'] == 'OrderedList':
                it['sub'] = list_items(b['c'][1])['items']
            elif b['t'] in ('Plain', 'Para') and b is not first:
                it['runs'] = it['runs'] + [{'t': ' '}] + trim(runs_of(b['c']))
        out.append(it)
    res = {'t': 'ol' if ordered else 'ul', 'items': out}
    if out and checks == len(out):
        res['check'] = 1
    return res


def cell_runs(cell):
    blocks = cell[4]
    rs = []
    for b in blocks:
        if b['t'] in ('Plain', 'Para'):
            if rs:
                rs.append({'br': 1})
            rs += runs_of(b['c'])
        elif b['t'] in ('BulletList', 'OrderedList'):
            items = b['c'] if b['t'] == 'BulletList' else b['c'][1]
            for it in items:
                if rs:
                    rs.append({'br': 1})
                rs.append({'t': '• '})
                rs += runs_of(it[0]['c']) if it and it[0]['t'] in ('Plain', 'Para') else []
    return trim(merge(rs))


def table_block(b):
    c = b['c']
    head_rows = c[3][1]
    body_rows = []
    for body in c[4]:
        body_rows += body[2] + body[3]
    ncols = len(c[2])
    rows = [[cell_runs(cell) for cell in row[1]] for row in head_rows + body_rows]
    # a one-cell table is a call-out box in these documents
    if ncols == 1 and len(rows) <= 2:
        cells = [cl for row in (head_rows + body_rows) for cl in row[1]]
        blocks = []
        for cl in cells:
            for bb in cl[4]:
                blocks.append(bb)
        return callout_from(blocks)
    head = rows[0] if head_rows else None
    body = rows[1:] if head_rows else rows
    if head and not any(plain(h) for h in head):
        head = None
    return {'t': 'table', 'head': head, 'rows': body}


def callout_from(blocks):
    title, body = None, []
    for n, bb in enumerate(blocks):
        if bb['t'] in ('Plain', 'Para'):
            rs = trim(runs_of(bb['c']))
            if n == 0 and rs and rs[0].get('b'):
                title = plain([rs[0]]).rstrip(':.— ')
                rest = trim(rs[1:])
                if rest:
                    body.append({'t': 'p', 'runs': rest})
                continue
            body.append({'t': 'p', 'runs': rs})
        elif bb['t'] == 'BulletList':
            body.append(list_items(bb['c']))
        elif bb['t'] == 'OrderedList':
            body.append(list_items(bb['c'][1], True))
    return {'t': 'callout', 'title': title, 'blocks': body}


def convert(b):
    """One pandoc block -> our block (or None)."""
    t = b['t']
    if t in ('Para', 'Plain'):
        rs = trim(runs_of(b['c']))
        return {'t': 'p', 'runs': rs} if rs else None
    if t == 'Header':
        return {'t': 'h', 'level': b['c'][0], 'text': plain(runs_of(b['c'][2]))}
    if t == 'BulletList':
        return list_items(b['c'])
    if t == 'OrderedList':
        return list_items(b['c'][1], True)
    if t == 'Table':
        return table_block(b)
    if t == 'BlockQuote':
        inner = [convert(x) for x in b['c']]
        return {'t': 'quote', 'blocks': [x for x in inner if x]}
    return None


# ---------------- reading a pack ----------------
def pandoc_ast(path):
    r = subprocess.run(['pandoc', '-f', 'docx', '-t', 'json', str(path)], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f'pandoc failed on {path}: {r.stderr[:300]}')
    return json.loads(r.stdout)['blocks']


def btext(b):
    t = b['t']
    if t == 'Header':
        return plain(runs_of(b['c'][2]))
    if t in ('Para', 'Plain'):
        return plain(runs_of(b['c']))
    return ''


def parse_id(text):
    m = ID_RE.match(text.strip())
    if not m:
        return None
    parts = [p.strip() for p in m.group(3).split('|')]
    cat = pri = None
    for p in parts:
        if re.search(r'priority', p, re.I) or p.lower() in ('high', 'medium', 'low'):
            pri = re.sub(r'(?i)priority:?|\s*priority', '', p).strip() or None
        elif not re.match(r'(?i)workbook|search intent', p) and cat is None:
            cat = p
    return m.group(1), m.group(2), cat, pri


def find_articles(blocks):
    """[(index, id, category, priority)] for the first real occurrence of each article id."""
    seen, out = set(), []
    for n, b in enumerate(blocks):
        if b['t'] not in ('Para', 'Header', 'Plain'):
            continue
        p = parse_id(btext(b))
        if not p:
            continue
        aid = f'{p[0]}-{p[1]}'
        if aid in seen:
            continue
        seen.add(aid)
        out.append((n, aid, p[2], p[3]))
    return out


def label_value(text):
    m = re.match(r'^(SEO title|Meta description|Suggested URL slug|Suggested URL|Proposed URL slug|Proposed SEO title|Proposed meta description|URL slug|Primary keyword|Secondary keywords?|Search intent|'
                 r'Workbook primary keyword|Workbook secondary keywords?|Proposed GEO / interactive element|GEO / interactive element)\s*:\s*(.+)$', text.strip(), re.I)
    return (m.group(1).lower(), m.group(2).strip()) if m else (None, None)


def seo_from_rows(rows, into):
    for row in rows:
        if len(row) >= 2:
            k = plain(row[0]).lower()
            v = plain(row[1])
            if re.search(r'seo title', k):
                into.setdefault('seoTitle', v)
            elif re.search(r'meta description', k):
                into.setdefault('metaDescription', v)
            elif re.search(r'(suggested|proposed)? ?url|slug', k):
                into.setdefault('slug', v)
            elif re.search(r'primary keyword', k):
                into.setdefault('primaryKeyword', v)
            elif re.search(r'internal links', k):
                into.setdefault('internalLinks', v)


def appendix_seo(blocks):
    """Pack-level tables whose first column is the article id: SEO title, meta description, slug."""
    out = {}
    for b in blocks:
        if b['t'] != 'Table':
            continue
        tb = table_block(b)
        if tb['t'] != 'table' or not tb['head']:
            continue
        heads = [plain(h).lower() for h in tb['head']]
        if not heads or 'id' not in heads[0]:
            continue
        for row in tb['rows']:
            aid = plain(row[0]).strip()
            if not re.match(r'^[A-Z]{2,4}-\d\d$', aid):
                continue
            d = out.setdefault(aid, {})
            for h, cell in zip(heads, row):
                v = plain(cell)
                if 'seo title' in h:
                    d['seoTitle'] = v
                elif 'meta' in h:
                    d['metaDescription'] = v
                elif 'slug' in h or 'url' in h:
                    d['slug'] = v
    return out


def source_entries(blocks):
    """Sources: a bold title, then a short note and a web address (as one paragraph, a bullet, or a quoted block)."""
    out = []

    def one(rs, title_hint=''):
        text = plain(rs)
        urls = [r['href'] for r in rs if r.get('href')] or URL_RE.findall(text)
        if not urls:
            return
        url = urls[0].rstrip('.,;')
        bold = ''.join(r.get('t', '') for r in rs if r.get('b')).strip(' —–-:') or title_hint
        linked = ''.join(r.get('t', '') for r in rs if r.get('href')).strip()
        title = bold or (linked if linked and not linked.startswith('http') else '')
        note = URL_RE.sub('', text)
        if bold:
            note = note.replace(bold, '', 1)
        if linked and not linked.startswith('http'):
            note = note.replace(linked, '', 1)
        note = re.sub(r'^[\s—–:|-]+|[\s—–:|-]+$', '', note.strip())
        if not title:
            title = re.sub(r'https?://(www\.)?', '', url).split('/')[0]
        out.append({'title': title, 'url': url, 'note': note})

    pending = ''
    for b in blocks:
        t = b['t']
        if t in ('Para', 'Plain'):
            rs = runs_of(b['c'])
            has_url = any(r.get('href') for r in rs) or URL_RE.search(plain(rs))
            if not has_url:
                bold = ''.join(r.get('t', '') for r in rs if r.get('b')).strip(' —–-:')
                pending = bold or plain(rs)
                continue
            one(rs, pending)
            pending = ''
        elif t == 'BlockQuote':
            rs = []
            for x in b['c']:
                if x['t'] in ('Para', 'Plain'):
                    if rs:
                        rs.append({'t': ' '})
                    rs += runs_of(x['c'])
            one(merge(rs), pending)
            pending = ''
        elif t == 'BulletList':
            for it in b['c']:
                if it and it[0]['t'] in ('Plain', 'Para'):
                    one(runs_of(it[0]['c']))
    seen, uniq = set(), []
    for s_ in out:
        if s_['url'] not in seen:
            seen.add(s_['url'])
            uniq.append(s_)
    return uniq


def split_faq(blocks):
    """FAQ blocks -> [{'q': text, 'a': [blocks]}]. A question is a heading, or a short paragraph ending in '?'."""
    faqs, cur = [], None
    for b in blocks:
        t = b['t']
        txt = btext(b)
        is_q = (t == 'Header' and b['c'][0] >= 3) or (t in ('Para', 'Plain') and txt.endswith('?') and len(txt) < 220)
        if is_q:
            cur = {'q': txt, 'a': []}
            faqs.append(cur)
        elif cur is not None:
            if t == 'BlockQuote':
                for x in b['c']:
                    c = convert(x)
                    if c:
                        cur['a'].append(c)
            else:
                c = convert(b)
                if c:
                    cur['a'].append(c)
    return [f for f in faqs if f['a']]


def slice_runs(runs, lo, hi):
    """The part of a list of runs between two character positions."""
    out, pos = [], 0
    for r in runs:
        if 't' not in r:
            if lo <= pos < hi:
                out.append(r)
            continue
        t = r['t']
        a, b = max(lo, pos), min(hi, pos + len(t))
        if a < b:
            out.append({**r, 't': t[a - pos:b - pos]})
        pos += len(t)
    return trim(out)


def clean_runs(runs, dropped):
    """Remove the sentences meant for editors. Returns the runs that remain."""
    text = ''.join(r.get('t', ' ') if 't' in r else ' ' for r in runs)
    if not EDITOR_SENT.search(text.replace('. ', '.\n').replace('? ', '?\n').replace('! ', '!\n')) and not EDITOR_ANY.search(text):
        return runs
    cuts = [0] + [m.end() for m in re.finditer(r'(?<=[.!?])\s+(?=[A-Z“"(\[])', text)] + [len(text)]
    keep = []
    for lo, hi in zip(cuts, cuts[1:]):
        sent = text[lo:hi].strip()
        if not sent:
            continue
        if EDITOR_SENT.search(sent):
            dropped.append(sent[:140])
        else:
            keep.append((lo, hi))
    out = []
    for lo, hi in keep:
        part = slice_runs(runs, lo, hi)
        if out and part:
            out.append({'t': ' '})
        out += part
    return merge(out)


def clean_blocks(blocks, dropped):
    out = []
    for b in blocks:
        t = b['t']
        if t == 'p':
            rs = clean_runs(b['runs'], dropped)
            if plain(rs):
                out.append({**b, 'runs': rs})
        elif t in ('ul', 'ol'):
            items = []
            for it in b['items']:
                rs = clean_runs(it['runs'], dropped)
                lead = it.get('lead')
                if not plain(rs) and not lead:
                    continue
                ni = {**it, 'runs': rs}
                if it.get('sub'):
                    ni['sub'] = [{**x, 'runs': clean_runs(x['runs'], dropped)} for x in it['sub']]
                items.append(ni)
            if items:
                out.append({**b, 'items': items})
        elif t in ('callout', 'quote'):
            inner = clean_blocks(b['blocks'], dropped)
            if inner:
                out.append({**b, 'blocks': inner})
        elif t == 'table':
            rows = [[clean_runs(c, dropped) for c in r] for r in b['rows']]
            out.append({**b, 'rows': rows})
        else:
            out.append(b)
    return out


def build_article(blocks, start, end, aid, cat, pri, pack_seo, pack_sources, dest_hint, report):
    seg = blocks[start:end]
    art = {'id': aid, 'category': cat, 'priority': pri}
    n = 1
    title = None
    while n < len(seg) and n < 8:
        b = seg[n]
        txt = btext(b)
        pm = re.match(r'^Priority:?\s*(High|Medium|Low)', txt, re.I)
        if pm and not art.get('priority'):
            art['priority'] = pm.group(1).capitalize()
        if b['t'] == 'Header' and b['c'][0] == 1:
            title = txt
            n += 1
            break
        if b['t'] in ('Para', 'Plain') and txt and not META_RE.match(txt) and label_value(txt)[0] is None and len(txt) < 170 \
                and not re.match(r'^(Priority|Workbook|Search intent)', txt, re.I):
            title = txt
            n += 1
            break
        n += 1
    if not title:
        report.append(f'{aid}: no title found')
        return None
    art['title'] = title
    meta, seo = {}, {}
    intro, quick, sections, faq_blocks, source_blocks = [], [], [], [], []
    mode, cur = 'meta', None
    tail = False

    def flush():
        nonlocal cur
        if cur and cur['blocks']:
            sections.append(cur)
        cur = None

    def add(c):
        nonlocal cur
        if c is None:
            return
        if cur is None:
            cur = {'title': None, 'blocks': []}
        cur['blocks'].append(c)

    for b in seg[n:]:
        t = b['t']
        txt = btext(b)
        if t == 'Header':
            lvl = b['c'][0]
            plainhead = re.sub(r'^\d+\.\s*', '', txt).strip()
            if QUICK_HEAD.match(plainhead):
                flush(); mode = 'quick'; continue
            if FAQ_HEAD.match(plainhead) or re.match(r'(?i)^(faqs?|frequently asked questions)\b', plainhead) and lvl <= 2:
                flush(); mode = 'faq'; tail = False; continue
            if mode == 'faq' and lvl >= 3 and not TAIL.search(plainhead):
                faq_blocks.append(b); continue
            if SOURCES_HEAD.match(plainhead):
                flush(); mode = 'sources'; tail = False; continue
            if ARTICLE_MARK.match(plainhead):
                flush(); mode = 'sections-pre'; continue
            if re.match(r'(?i)^(SEO|recommended SEO)', plainhead) or 'metadata' in plainhead.lower():
                flush(); mode = 'seo'; continue
            if TAIL.search(plainhead):
                flush(); mode = 'skip'; tail = True; continue
            if INTERNAL.search(plainhead):
                flush(); mode = 'skip'; continue
            if tail:
                flush(); mode = 'skip'; continue
            flush()
            mode = 'sections'
            cur = {'title': re.sub(r'\s*\((GEO element)\)\s*$', '', plainhead, flags=re.I), 'blocks': []}
            continue
        if mode == 'skip':
            continue
        if mode == 'meta':
            k, v = label_value(txt) if t in ('Para', 'Plain') else (None, None)
            if k:
                meta[k] = v
                continue
            if t in ('Para', 'Plain') and (META_RE.match(txt) or re.match(r'^Priority', txt)):
                m = re.match(r'^Priority:?\s*(High|Medium|Low)', txt, re.I)
                if m and not art.get('priority'):
                    art['priority'] = m.group(1).capitalize()
                continue
            if t == 'Table':
                tb = table_block(b)
                if tb['t'] == 'callout' and re.match(r'(?i)^quick answer', tb['title'] or ''):
                    quick = tb['blocks']
                    mode = 'sections-pre'
                    continue
                if tb['t'] == 'callout':
                    intro.append(tb)  # a notice such as a date change: shown as a box under the opening paragraph
                    continue
                add(tb); mode = 'sections-pre'; continue
            c = convert(b)
            if c and t in ('Para', 'Plain'):
                m = re.match(r'^Quick answer\s*[:—-]\s*(.+)$', txt, re.I | re.S)
                if m:
                    qr = list(c['runs'])
                    while qr and ('t' not in qr[0] or not qr[0]['t'].strip() or re.match(r'^\s*Quick answer\s*[:—-]?\s*$', qr[0]['t'], re.I)):
                        qr.pop(0)
                    if qr and 't' in qr[0]:
                        qr[0] = {**qr[0], 't': re.sub(r'^\s*Quick answer\s*[:—-]\s*', '', qr[0]['t'], flags=re.I)}
                    if qr and 't' in qr[0]:
                        qr[0] = {**qr[0], 't': qr[0]['t'][:1].upper() + qr[0]['t'][1:]}
                    quick = [{'t': 'p', 'runs': trim(qr)}]
                    mode = 'sections-pre'
                    continue
                intro.append(c)
            elif c:
                intro.append(c)
            continue
        if mode == 'quick':
            if t == 'Table':
                tb = table_block(b)
                quick += tb['blocks'] if tb['t'] == 'callout' else [tb]
            else:
                c = convert(b)
                if c:
                    quick.append(c)
            continue
        if mode in ('sections-pre', 'sections'):
            add(convert(b))
            continue
        if mode == 'faq':
            faq_blocks.append(b)
            continue
        if mode == 'sources':
            source_blocks.append(b)
            continue
        if mode == 'seo':
            k, v = label_value(txt) if t in ('Para', 'Plain') else (None, None)
            if k:
                if 'seo title' in k or 'proposed seo' in k:
                    seo['seoTitle'] = v
                elif 'meta' in k:
                    seo['metaDescription'] = v
                elif 'url' in k or 'slug' in k:
                    seo['slug'] = v
            elif re.match(r'^Suggested internal links', txt, re.I):
                seo['internalLinks'] = txt.split(':', 1)[-1].strip()
            if t == 'Table':
                tb = table_block(b)
                if tb['t'] == 'table':
                    seo_from_rows(tb['rows'], seo)
            continue
    flush()
    # paragraphs before the first heading (or after "Article draft") are the introduction
    if sections and sections[0]['title'] is None:
        intro += sections.pop(0)['blocks']
    dropped = []
    art['intro'] = clean_blocks(intro, dropped)
    art['quick'] = clean_blocks(quick, dropped)
    art['sections'] = [{'title': s['title'], 'blocks': clean_blocks(s['blocks'], dropped)} for s in sections]
    art['sections'] = [s for s in art['sections'] if s['blocks']]
    art['faq'] = [{'q': f['q'], 'a': clean_blocks(f['a'], dropped)} for f in split_faq(faq_blocks)]
    art['faq'] = [f for f in art['faq'] if f['a']]
    for d in dropped:
        report.append(f'{aid}: editor sentence dropped: {d}')
    art['sourcesOwn'] = source_entries(source_blocks)
    art['primaryKeyword'] = meta.get('primary keyword') or meta.get('workbook primary keyword') or pack_seo.get(aid, {}).get('primaryKeyword')
    sk = meta.get('secondary keywords') or meta.get('secondary keyword') or meta.get('workbook secondary keywords')
    art['secondaryKeywords'] = [x.strip() for x in re.split(r'[;,]\s*', sk)] if sk else []
    art['intent'] = meta.get('search intent')
    for k in ('seoTitle', 'metaDescription', 'slug', 'internalLinks'):
        v = seo.get(k) or pack_seo.get(aid, {}).get(k)
        if v:
            art[k] = v
    return art



def flat_text(art):
    parts = [art['title']]

    def walk(bs):
        for b in bs:
            t = b['t']
            if t == 'p':
                parts.append(plain(b['runs']))
            elif t in ('ul', 'ol'):
                for it in b['items']:
                    parts.append(plain(it.get('lead', [])) + ' ' + plain(it['runs']))
            elif t == 'table':
                for r in ([b['head']] if b['head'] else []) + b['rows']:
                    parts.append(' | '.join(plain(c) for c in r))
            elif t in ('callout', 'quote'):
                walk(b['blocks'])
    walk(art['intro']); walk(art['quick'])
    for s_ in art['sections']:
        walk(s_['blocks'])
    for f in art['faq']:
        parts.append(f['q']); walk(f['a'])
    return '\n'.join(parts)


RANK_NUM = re.compile(r'(\b(QS|THE|Times Higher Education|US News)\b[^.|]{0,60}\b\d{1,3}\b|\b[Rr]ank(ed|ing)?\s*(No\.?|#|number)\s*\d+|#\s?\d{1,3}\b|[Hh]ighest[- ]ranked|[Tt]op[- ]ranked|[Tt]op[- ]?\d+\s+(universit|institution|school|college))')
OUTCOME = re.compile(r'(guarantee[sd]?|assured|100\s?%|will (get|receive|obtain) (a )?(PR|visa|permanent)|easy (PR|visa)|sure(ly)? (get|receive))', re.I)
NEG = re.compile(r"\b(not|no|never|nor|cannot|can't|doesn't|does|do|avoid|without|isn't|aren't|unless|whether|if|any|every|rely|assum\w+|promises?)\b|\?", re.I)


def apply_overrides(art, ov, report):
    o = ov.get(art['id'])
    if not o:
        return art
    if o.get('title'):
        report.append(f"{art['id']}: title changed from '{art['title']}' to '{o['title']}' ({o.get('why', '')})")
        art['title'] = o['title']
    for key in ('seoTitle', 'metaDescription', 'slug'):
        if o.get(key):
            art[key] = o[key]
    for frag in o.get('dropSections', []):
        n0 = len(art['sections'])
        art['sections'] = [s_ for s_ in art['sections'] if frag.lower() not in (s_['title'] or '').lower()]
        report.append(f"{art['id']}: removed {n0 - len(art['sections'])} section(s) matching '{frag}' ({o.get('why', '')})")
    for frag in o.get('dropFaq', []):
        n0 = len(art['faq'])
        art['faq'] = [f for f in art['faq'] if frag.lower() not in f['q'].lower()]
        report.append(f"{art['id']}: removed {n0 - len(art['faq'])} FAQ(s) matching '{frag}' ({o.get('why', '')})")
    if o.get('hold'):
        art['hold'] = True
        report.append(f"{art['id']}: HELD, not published ({o.get('why', '')})")
    return art


def scan(art, report):
    text = flat_text(art)
    for line in text.split('\n'):
        if RANK_NUM.search(line):
            report.append(f"{art['id']}: RANKING wording, check against the no-rankings rule: {line.strip()[:150]}")
        if OUTCOME.search(line) and not NEG.search(line):
            report.append(f"{art['id']}: OUTCOME wording, check: {line.strip()[:150]}")
    words = len(text.split())
    art['words'] = words
    art['readMinutes'] = max(2, round(words / 220))


def reviewed_date(blocks):
    for b in blocks[:40]:
        m = re.search(r'(?:cut-off|edition|reviewed)[^0-9]{0,20}(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d\d)', btext(b), re.I)
        if m:
            mo = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december'].index(m.group(2).lower()) + 1
            return f'{m.group(3)}-{mo:02d}-{int(m.group(1)):02d}'
    return None


def pack_sources_of(blocks, arts_start):
    """Sources listed once for the whole pack (a register after the last article)."""
    out = []
    for n, b in enumerate(blocks):
        if b['t'] == 'Header' and re.match(r'(?i)^(appendix [a-z]\.\s*)?(official )?source register', re.sub(r'^\d+\.\s*', '', btext(b))) and n > arts_start:
            end = len(blocks)
            for m in range(n + 1, len(blocks)):
                if blocks[m]['t'] == 'Header' and blocks[m]['c'][0] <= blocks[n]['c'][0]:
                    end = m
                    break
            out += source_entries(blocks[n + 1:end])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('docx', nargs='+')
    ap.add_argument('--out', default='src/data/articles')
    ap.add_argument('--report', default='')
    ap.add_argument('--reviewed', default='')
    ap.add_argument('--overrides', default=str(Path(__file__).with_name('overrides.json')))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report, written = [], 0
    ov = json.loads(Path(args.overrides).read_text(encoding='utf-8')) if Path(args.overrides).exists() else {}
    for path in args.docx:
        blocks = pandoc_ast(path)
        starts = find_articles(blocks)
        reviewed = args.reviewed or reviewed_date(blocks)
        pack_seo = appendix_seo(blocks)
        # the back matter after the last article is not part of it; each article ends at the next article or at its own notes
        last_end = len(blocks)
        register = pack_sources_of(blocks, starts[0][0] if starts else 0)
        for k, (start, aid, cat, pri) in enumerate(starts):
            end = starts[k + 1][0] if k + 1 < len(starts) else last_end
            local = []
            art = build_article(blocks, start, end, aid, cat, pri, pack_seo, register, None, local)
            if not art:
                report += local
                continue
            words = sum(len(plain(b.get('runs', []) or [])) for s in art['sections'] for b in s['blocks'] if b['t'] == 'p')
            if len(art['sections']) < 2 and not art['quick']:
                report.append(f'{aid}: skipped, no body found ({Path(path).name})')
                continue
            report += local
            pre = aid.split('-')[0]
            art['destination'] = PREFIX.get(pre, pre.lower())
            slug_topic, label = TOPICS.get((cat or '').lower(), (re.sub(r'[^a-z]+', '-', (cat or 'general').lower()).strip('-'), cat or 'General'))
            art['topic'] = slug_topic
            art['topicLabel'] = label
            art['reviewed'] = reviewed
            art['sources'] = art['sourcesOwn'] or register
            art['sourcesScope'] = 'article' if art['sourcesOwn'] else 'destination'
            del art['sourcesOwn']
            art['sourceFile'] = Path(path).name
            art = apply_overrides(art, ov, report)
            scan(art, report)
            (out / f'{aid}.json').write_text(json.dumps(art, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
            written += 1
            report.append(f'{aid}: {art["title"][:80]} | sections {len(art["sections"])}, faq {len(art["faq"])}, sources {len(art["sources"])} ({art["sourcesScope"]}), quick {"yes" if art["quick"] else "NO"}, slug {art.get("slug", "-")}')
    text = '\n'.join(report)
    print(text)
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(text + '\n', encoding='utf-8')
    print(f'\nwrote {written} articles to {out}')


if __name__ == '__main__':
    main()
