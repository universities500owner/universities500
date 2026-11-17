"""Study Australia scholarship list (Australian Government, Austrade): https://search.studyaustralia.gov.au/scholarships

Why this exists: some university sites turn our reader away (Cloudflare bot checks) or build their scholarship
finder with scripts, so the reader finds nothing there. Study Australia is the government's own site for
international students. Its list is plain HTML, robots.txt allows crawling (checked 17 Nov 2026), and each
scholarship names the university that offers it. We read that list, keep only the entries run by universities
on this site, and link back to the university when Study Australia gives its page.

Rules this file follows:
  - same polite fetcher as everything else: identified bot, robots.txt, 3 s between requests
  - nothing is guessed: value, closing date, level, description and eligibility are copied from the page
  - the page we read is the source (`url`); the university's own page, when listed, is `applyUrl`
  - same name and level rules as every other record (quality.py), so prizes, research and school
    scholarships stay out
  - if the page layout changes and no cards are found, nothing is returned and the old records stay as they were
"""
import hashlib
import html as htmllib
import os
import re
import urllib.parse

import details as Det
import extract as X
import quality as Q
import textutil as T

BASE = os.environ.get('STUDYAUSTRALIA_BASE', 'https://search.studyaustralia.gov.au')  # the variable is only for the offline tests
LIST_URL = BASE + '/scholarships'
ORIGIN = 'studyaustralia'
VIA = 'Study Australia'
MAX_LIST_PAGES = 140      # the list had 117 pages (1,164 scholarships) on 17 Nov 2026
DETAIL_CAP = 700          # detail pages read in one run
REUSE_DAYS = 7            # a record whose card did not change is not fetched again for this long

# Names Study Australia may use for a university, as they come out of norm(). Only needed where the name differs from ours.
ALIASES = {
    'unsw sydney': 'the-university-of-new-south-wales',
    'unsw': 'the-university-of-new-south-wales',
    'uts': 'university-of-technology-sydney',
    'unisq': 'university-of-southern-queensland',
    'cquniversity australia': 'central-queensland-university-australia',
    'cquniversity': 'central-queensland-university-australia',
    'cqu': 'central-queensland-university-australia',
    'ecu': 'edith-cowan-university',
    'jcu': 'james-cook-university',
    'uwa': 'the-university-of-western-australia',
    'uow': 'university-of-wollongong',
    'anu': 'australian-national-university',
    'rmit': 'rmit-university',
    'qut': 'queensland-university-of-technology',
    'uq': 'the-university-of-queensland',
}

LABEL = re.compile(r'^(Award value|Level of study|Closing date)\s*[-–:]\s*(.+)$', re.I)
OPEN_ENDED = re.compile(r'^(?:ongoing|open|rolling|all year|year[- ]round|no closing date|continuous(?:ly)?|always open)\b', re.I)
NO_VALUE = re.compile(r'^(?:varies|various|not (?:stated|specified|applicable)|n/?a|tbc|tba|-)\.?$', re.I)


def norm(s):
    s = htmllib.unescape(s or '').lower().replace('&', ' and ')
    s = re.sub(r"[^a-z0-9 ]+", ' ', s.replace("'", '').replace('’', ''))
    s = re.sub(r'\b(?:the|of)\b', ' ', s)
    return ' '.join(s.split())


def provider_index(unis):
    """normalised university name -> slug, for the universities this run is allowed to fill."""
    idx = {norm(u['name']): u['slug'] for u in unis}
    for alias, slug in ALIASES.items():
        if slug in {u['slug'] for u in unis}:
            idx[alias] = slug
    return idx


def match_provider(name, provider_url, idx):
    for cand in (norm(name), norm(urllib.parse.unquote((urllib.parse.urlsplit(provider_url or '').path.split('/') + ['', '', ''])[2]).replace('-', ' '))):
        if cand and cand in idx:
            return idx[cand]
    return None


def _txt(el):
    return T.clean(el.get_text(' ')) if el is not None else ''


def parse_listing(html, base=BASE):
    """(total scholarships the site says it has, [card, ...]). A card is what the list shows: name, page, provider, value, level, closing date."""
    soup = X.soup_of(html)
    total = None
    m = re.search(r'Showing\s+([\d,]+)\s+scholarships', soup.get_text(' '))
    if m:
        total = int(m.group(1).replace(',', ''))
    cards = []
    for div in soup.select('div.scholarship-list-card'):
        a = div.select_one('h3 a[href*="/scholarship/"]') or div.select_one('a[href*="/scholarship/"]')
        if not a:
            continue
        prov = div.select_one('a[href*="/provider/"][aria-label]') or div.select_one('strong a[href*="/provider/"]')
        card = {
            'name': _txt(a), 'url': X.canon(urllib.parse.urljoin(base, a['href'])),
            'provider': _txt(prov), 'providerUrl': urllib.parse.urljoin(base, prov['href']) if prov else None,
            'value': None, 'level': None, 'closing': None,
        }
        for p in div.find_all('p'):
            lm = LABEL.match(_txt(p))
            if lm:
                card[{'award value': 'value', 'level of study': 'level', 'closing date': 'closing'}[lm.group(1).lower()]] = lm.group(2).strip()
        if card['name']:
            cards.append(card)
    return total, cards


def parse_detail(html, base=BASE):
    """What the scholarship's own page adds: description paragraphs, eligibility lines, and the university's page ('Visit website')."""
    soup = X.soup_of(html)
    out = {'description': [], 'eligibility': [], 'visit': None}
    for a in soup.find_all('a', href=True):
        if re.match(r'^(?:visit website|visit site|apply(?: now| online)?)$', _txt(a), re.I):
            href = urllib.parse.urljoin(base, a['href'].strip())
            if href.startswith('http') and urllib.parse.urlsplit(href).netloc != urllib.parse.urlsplit(base).netloc:
                out['visit'] = X.canon(href)
                break
    head = next((h for h in soup.find_all(['h2', 'h3']) if _txt(h).lower().startswith('scholarship information')), None)
    if head is not None:
        for sib in head.find_next_siblings():
            if sib.name != 'p':
                continue
            t = _txt(sib)
            if not t or LABEL.match(t.replace(':', ' -', 1)) or t.lower().startswith('level of study'):
                continue
            out['description'].append(t)
    btn = next((b for b in soup.find_all('button') if 'eligibility' in _txt(b).lower()), None)
    if btn is not None:
        box = btn.find_parent('div', class_=re.compile(r'\bw-100\b')) or btn.parent
        items = [_txt(li) for li in box.find_all('li')]
        if not items:
            items = [_txt(p) for p in box.find_all('p')]
        if not items:  # the answer may sit in the next block, outside the button's box
            nxt = box.find_next_sibling()
            if nxt is not None and not nxt.find('button'):
                items = [_txt(li) for li in nxt.find_all('li')] or [_txt(p) for p in nxt.find_all('p')]
        out['eligibility'] = [i for i in items if i and 'eligibility requirements' != i.lower()][:8]
    return out


def levels_from(level_text):
    """Study Australia's own level labels -> our two levels. Research and school levels are not ours."""
    lv, phd = [], False
    for part in re.split(r'[,/]', level_text or ''):
        p = part.lower()
        if re.search(r'undergraduate|bachelor', p) and 'Bachelor' not in lv:  # "Undergraduate / VET" is one label: the VET half alone is not ours
            lv.append('Bachelor')
        if re.search(r'postgraduate|masters?\b|graduate (?:diploma|certificate|coursework)', p) and 'research' not in p and 'Master' not in lv:
            lv.append('Master')
        if re.search(r'research|doctor|ph\.?d|higher degree', p):
            phd = True
    return [l for l in ('Bachelor', 'Master') if l in lv], phd


def trim(text, limit=480):
    if len(text) <= limit:
        return text
    out = ''
    for s in T.sentences(text):
        if len(out) + len(s) + 1 > limit:
            break
        out = (out + ' ' + s).strip()
    return out or text[:limit].rsplit(' ', 1)[0] + '…'


def signature(card):
    return hashlib.sha1('|'.join(str(card.get(k)) for k in ('name', 'provider', 'value', 'level', 'closing')).encode()).hexdigest()[:10]


def card_problem(card, today):
    """Why the list card alone rules a scholarship out (so its page need not be read), or None."""
    name = card['name']
    why = Q.name_problem(name, today)
    if why == 'generic-heading':
        why = None   # that rule catches page headings like "Fees and scholarships"; a title on a list card is a name
    why = why or Q.url_problem(card['url'])
    if why:
        return why
    if T.ONLINE_ONLY.search(name):
        return 'online-only'
    levels, phd = levels_from(card.get('level'))
    if not levels:
        return 'phd-only' if phd else 'level-not-ours'
    return None


def make(card, detail, slug, uni, today):
    """One record, or (None, reason)."""
    why = card_problem(card, today)
    if why:
        return None, why
    name = card['name']
    levels, _phd = levels_from(card.get('level'))
    desc = trim(' '.join(detail.get('description') or []))
    elig = [trim(e, 220) for e in (detail.get('eligibility') or [])]
    closing = (card.get('closing') or '').strip()
    value = (card.get('value') or '').strip()
    bits = []
    if value and not NO_VALUE.match(value):
        bits.append(f'Award value - {value}.')
    if closing:
        bits.append(f'Closing date - {closing}.' if not OPEN_ENDED.match(closing) else 'Applications are accepted on a rolling basis.')
    text = ' '.join(bits + [desc] + elig)
    if T.detect_international(text) == 'no':
        return None, 'domestic-only'
    rec = X.make_record(
        name=name, provider=uni['name'], provider_slug=slug, provider_type='university', country=uni['country'],
        url=card['url'], text=text, today=today, origin=ORIGIN, apply_url=detail.get('visit'),
        description=desc or None, eligibility=elig, levels=levels, intl='yes')
    rec['via'] = VIA
    rec['saSig'] = signature(card)
    rec['saLevel'] = card.get('level')
    if not (rec['value'] or rec['deadline'] or rec['deadlinePartial'] or rec['rolling'] or rec['eligibility'] or rec['description']):
        return None, 'no-details'
    return rec, 'ok'


def read(fx, unis, today, prev_items=None, log=print):
    """Read the list and the detail pages of matched scholarships.
    Returns (records, report). report['complete'] is True only if every list page was read, so the caller knows
    whether a record that is missing now has really gone."""
    idx = provider_index(unis)
    by_slug = {u['slug']: u for u in unis}
    prev_by_url = {i['url']: i for i in (prev_items or {}).values() if i.get('origin') == ORIGIN}
    rep = {'complete': False, 'status': 'not-run', 'listed': 0, 'total': None, 'pages': 0, 'matched': 0, 'records': 0,
           'reused': 0, 'detailsRead': 0, 'reasons': {}, 'unmatched': {}, 'levels': {}, 'perUniversity': {}, 'noVisitLink': 0}
    if not idx:
        rep['status'] = 'no-australian-universities'
        return [], rep
    if not fx.allowed(LIST_URL):
        rep['status'] = 'robots'
        return [], rep

    cards, total, n_pages, ok_all = [], None, None, True
    page = 1
    while page <= MAX_LIST_PAGES:
        url = LIST_URL if page == 1 else f'{LIST_URL}?page={page}'
        res = fx.get(url)
        if not res.ok:
            ok_all = False
            rep['status'] = f'list page {page}: {res.error or res.status}'
            if page == 1:
                return [], rep
            break
        t, got = parse_listing(res.text, res.final_url)
        if page == 1:
            total = t
            if not got:
                rep['status'] = 'layout-changed'  # no cards where there used to be some
                return [], rep
            n_pages = -(-total // len(got)) if total else None
            log(f'studyaustralia: {total} scholarships on the site, {len(got)} per page, about {n_pages} pages')
        rep['pages'] += 1
        if not got:
            break
        cards.extend(got)
        if n_pages and page >= n_pages:
            break
        page += 1
    rep['total'], rep['listed'] = total, len(cards)
    rep['complete'] = bool(ok_all and total and len(cards) >= total * 0.97)
    if not rep['complete'] and ok_all:
        rep['status'] = f'read {len(cards)} of {total}'

    seen, mine = set(), []
    for c in cards:
        if c['url'] in seen:
            continue
        seen.add(c['url'])
        slug = match_provider(c['provider'], c['providerUrl'], idx)
        if not slug:
            rep['unmatched'][c['provider']] = rep['unmatched'].get(c['provider'], 0) + 1
            continue
        c['slug'] = slug
        mine.append(c)
    rep['matched'] = len(mine)

    records, details_left = [], DETAIL_CAP
    for c in mine:
        slug, uni = c['slug'], by_slug[c['slug']]
        rep['levels'][c.get('level') or '(none)'] = rep['levels'].get(c.get('level') or '(none)', 0) + 1
        why = card_problem(c, today)
        if why:   # the card already says no: do not visit its page
            rep['reasons'][why] = rep['reasons'].get(why, 0) + 1
            continue
        old = prev_by_url.get(c['url'])
        fresh_enough = old and old.get('saSig') == signature(c) and old.get('lastVerified', '') >= _days_ago(today, REUSE_DAYS)
        if fresh_enough:
            detail = {'description': [old.get('description')] if old.get('description') else [], 'eligibility': old.get('eligibility') or [], 'visit': old.get('applyUrl')}
            rep['reused'] += 1
        elif details_left > 0:
            res = fx.get(c['url'])
            details_left -= 1
            detail = parse_detail(res.text, res.final_url) if res.ok else {'description': [], 'eligibility': [], 'visit': None}
            rep['detailsRead'] += 1
            if not res.ok and old:   # keep what we knew
                detail = {'description': [old.get('description')] if old.get('description') else [], 'eligibility': old.get('eligibility') or [], 'visit': old.get('applyUrl')}
        else:
            detail = {'description': [], 'eligibility': [], 'visit': None}
        if not detail.get('visit'):
            rep['noVisitLink'] += 1
        rec, why = make(c, detail, slug, uni, today)
        if rec:
            records.append(rec)
            rep['perUniversity'][slug] = rep['perUniversity'].get(slug, 0) + 1
        else:
            rep['reasons'][why] = rep['reasons'].get(why, 0) + 1
    rep['records'] = len(records)
    if rep['status'] == 'not-run':
        rep['status'] = 'ok'
    return records, rep


def _days_ago(today, n):
    from datetime import date, timedelta
    return (date.fromisoformat(today) - timedelta(days=n)).isoformat()


def print_report(rep, unis, log=print):
    log(f"\nStudy Australia: {rep['status']}. {rep['listed']} of {rep['total']} listed ({rep['pages']} pages), "
        f"{rep['matched']} are from the universities on this site, {rep['records']} kept "
        f"({rep['detailsRead']} detail pages read, {rep['reused']} reused, {rep['noVisitLink']} without a university link)")
    if rep['reasons']:
        log('  not kept: ' + ', '.join(f'{k} {v}' for k, v in sorted(rep['reasons'].items(), key=lambda kv: -kv[1])))
    if rep['levels']:
        log('  level labels on matched entries: ' + ', '.join(f'{k!r} {v}' for k, v in sorted(rep['levels'].items(), key=lambda kv: -kv[1])))
    names = {u['slug']: u['name'] for u in unis}
    for s in sorted(names):
        log(f"  {rep['perUniversity'].get(s, 0):3}  {names[s]}")
    near = [(p, n) for p, n in rep['unmatched'].items() if re.search(r'universit|institute of tech|college', p, re.I)]
    if near:
        log('  providers that look like universities but did not match one on this site (add to ALIASES if one is ours):')
        for p, n in sorted(near, key=lambda kv: -kv[1])[:40]:
            log(f'    {n:3}  {p}')
