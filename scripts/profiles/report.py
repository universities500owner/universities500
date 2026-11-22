"""The pilot report: how many of the universities got each field, at what level of evidence, and what failed.
Plain markdown, written to out/report.md and the Actions job summary."""
import collections
import datetime

LINK_ROLES = ['admissions', 'courses', 'scholarships', 'faculties', 'partners', 'campuses', 'facts']
MARK = {'verified': 'V', 'weak': 'w', 'external': 'x', 'failed': '-', None: '-'}


def pct(n, total):
    return f'{n}/{total}'


def grade(rec, role):
    return ((rec.get('links') or {}).get(role) or {}).get('grade') or 'failed'


def build(recs, meta=None):
    meta = meta or {}
    n = len(recs)
    L = [f'# Profile pilot report', '',
         f'{n} universities, run {datetime.date.today().isoformat()}. '
         f'{meta.get("requests_site", "?")} website requests, {meta.get("requests_api", "?")} Wikimedia requests, {meta.get("seconds", "?")} s.', '']

    # ---- field table
    L += ['## Fill rate by field', '', 'Ready = could be shown today. Review = found, but a person should look first.', '',
          '| Field | Ready | Review | Missing | What counts as ready |', '|---|---|---|---|---|']

    def row(label, ready, review, rule):
        L.append(f'| {label} | {ready} | {review} | {n - ready - review} | {rule} |')

    c = collections.Counter(r.get('founded', {}).get('status') for r in recs)
    row('Year established', c['ok'], c['conflict'], 'one year on Wikidata, no conflict')
    c = collections.Counter(r.get('students', {}).get('status') for r in recs)
    row('Students + as-on year', c['verified'], c['single-source'] + c['site-only'] + c['missing-year'],
        'Wikidata number with a year, and the university site says about the same')
    ok = sum(1 for r in recs if (r.get('website') or {}).get('status') == 200)
    row('Official site readable', ok, 0, 'home page loaded and robots.txt allowed it')
    for role in ('admissions', 'courses', 'scholarships'):
        g = collections.Counter(grade(r, role) for r in recs)
        row(f'{role.capitalize()} link', g['verified'], g['weak'] + g['external'], 'page loads on the university domain and its title names the topic')
    g = collections.Counter(grade(r, 'partners') for r in recs)
    row('Partnerships page', g['verified'], g['weak'] + g['external'], 'same test; the names on it still need reading')
    ready = sum(1 for r in recs if len(r.get('faculties') or []) >= 3)
    linked = sum(1 for r in recs if len([f for f in (r.get('faculties') or []) if f.get('url')]) >= 3)
    row('Faculties (3 or more)', linked, ready - linked, 'three or more names, each with a link')
    for kind in ('instagram', 'linkedin', 'youtube'):
        g = collections.Counter(((r.get('social') or {}).get(kind) or {}).get('status', 'missing') for r in recs)
        row(f'{kind.capitalize()} account', g['verified'], g['check'] + g['wikidata-only'], 'link found in the site footer or its page data, and Wikidata does not disagree')
    g4 = sum(1 for r in recs if len((r.get('gallery') or {}).get('photos') or []) >= 4)
    g1 = sum(1 for r in recs if 1 <= len((r.get('gallery') or {}).get('photos') or []) < 4)
    row('Gallery (4+ photos)', g4, g1, 'four or more licensed, large, landscape photos with a credit')
    cp = sum(1 for r in recs if any(c.get('photo') for c in r.get('campuses') or []))
    row('A campus thumbnail', cp, 0, 'at least one campus has a matching licensed photo')
    short = sum(1 for r in recs if 200 <= len((r.get('brief') or {}).get('text') or '') <= 600)
    row('Brief of 4-5 lines', 0, short, 'needs the AI step; the Wikipedia lead exists for these (review = right length already)')
    L.append('')

    # ---- university matrix
    L += ['## Per university', '',
          'Links: a=admissions c=courses s=scholarships p=partners; V verified, w weak, x other domain, - none. '
          'Social: i=instagram l=linkedin y=youtube.', '',
          '| University | Country | Est. | Students (as on) | Status | Site | a c s p | i l y | Fac. | Photos | Campus pic |', '|---|---|---|---|---|---|---|---|---|---|---|']
    for r in recs:
        st = r.get('students') or {}
        stu = f"{st['v']:,} ({st['asof'] or 'no year'})" if st.get('v') else '-'
        links = ' '.join(MARK[grade(r, x)] for x in ('admissions', 'courses', 'scholarships', 'partners'))
        soc = ' '.join('V' if ((r.get('social') or {}).get(k) or {}).get('status') == 'verified' else ('?' if (r.get('social') or {}).get(k) else '-')
                       for k in ('instagram', 'linkedin', 'youtube'))
        w = r.get('website') or {}
        site = 'ok' if w.get('status') == 200 else ('robots' if w.get('robots') else (w.get('error') or 'fail')[:18])
        L.append(f"| {r['name'][:34]} | {r['country'][:12]} | {(r.get('founded') or {}).get('v') or '-'} | {stu} | {st.get('status', '-')} | {site} | {links} | {soc} | "
                 f"{len(r.get('faculties') or [])} | {len((r.get('gallery') or {}).get('photos') or [])} | {sum(1 for c in r.get('campuses') or [] if c.get('photo'))}/{len(r.get('campuses') or [])} |")
    L.append('')

    # ---- photos
    drops = collections.Counter()
    for r in recs:
        for k, v in ((r.get('gallery') or {}).get('counts') or {}).items():
            if isinstance(v, int):
                drops[k] += v
    years = [p['year'] for r in recs for p in (r.get('gallery') or {}).get('photos') or [] if p.get('year')]
    this = datetime.date.today().year
    L += ['## Photos', '',
          f"Files scanned: {drops.get('scanned', 0)}; usable: {drops.get('usable', 0)}. Dropped for: "
          + ', '.join(f'{k} {v}' for k, v in drops.most_common() if k not in ('scanned', 'usable')) + '.']
    if years:
        L.append(f"Chosen photos: {len(years)}; taken in the last 10 years: {sum(1 for y in years if y >= this - 10)}; oldest year: {min(years)}.")
    L.append('')

    # ---- students
    L += ['## Student totals: Wikidata against the university site', '', '| University | Wikidata | Year | Site says | Status |', '|---|---|---|---|---|']
    for r in recs:
        st = r.get('students') or {}
        sec = st.get('second') or {}
        L.append(f"| {r['name'][:34]} | {st.get('v') or '-'} | {st.get('asof') or '-'} | {sec.get('v') or (st.get('candidates') or [{}])[0].get('v') or '-'} | {st.get('status', '-')} |")
    L.append('')

    # ---- problems
    L += ['## What went wrong', '']
    bad = [r for r in recs if (r.get('website') or {}).get('status') != 200 or r.get('errors')]
    if not bad:
        L.append('Nothing failed.')
    for r in bad:
        w = r.get('website') or {}
        bits = []
        if w.get('status') != 200:
            bits.append(f"site: {w.get('error') or 'no answer'}")
        bits += r.get('errors') or []
        L.append(f"- **{r['name']}**: " + '; '.join(bits)[:400])
    if meta.get('robots_blocked'):
        L += ['', 'Blocked by robots.txt (not fetched): ' + ', '.join(sorted({f'{h}{p}' for h, p in meta['robots_blocked']}))[:600]]
    return '\n'.join(L) + '\n'
