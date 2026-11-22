"""Facts from Wikidata (CC0): year founded, student total with its year, coordinates, website, social accounts,
the Commons category and the faculties. Every value keeps the Wikidata page it came from, so a reader can check it.

A value is only returned when its statement is not deprecated. When Wikidata holds several different values we keep
them all and say so ('conflict'), because a conflict is a reason to look at the source, not to pick one quietly."""
import re

from api import WIKIDATA, SPARQL

P = {
    'inception': 'P571', 'students': 'P2196', 'coords': 'P625', 'website': 'P856', 'commons': 'P373',
    'image': 'P18', 'instagram': 'P2003', 'youtube': 'P2397', 'linkedin': 'P4264',
}
POINT_IN_TIME = 'P585'
FACULTY_WORD = re.compile(
    r'\b(faculty|faculties|school|college|department|institute|faculté|fakultät|facultad|fakulteit|fakultet|fakulti|fachbereich)\b', re.I)
FACULTY_SKIP = re.compile(
    r'hospital|library|press\b|museum|club\b|union\b|foundation|alumni|association|sports?\b|orchestra|choir|society|'
    r'high school|secondary school|primary school|nursery|kindergarten|research (centre|center|group)|laboratory|observatory|'
    r'students[\'’]? ', re.I)


def wd_url(qid):
    return f'https://www.wikidata.org/wiki/{qid}'


def entities(api, qids):
    """qid -> entity JSON, fetched 50 at a time."""
    out = {}
    qids = list(qids)
    for i in range(0, len(qids), 50):
        chunk = qids[i:i + 50]
        data = api.get_json(WIKIDATA, {
            'action': 'wbgetentities', 'ids': '|'.join(chunk), 'props': 'claims|sitelinks|labels',
            'languages': 'en', 'format': 'json', 'formatversion': '2',
        })
        for qid, ent in (data.get('entities') or {}).items():
            if 'missing' not in ent:
                out[qid] = ent
    return out


def _statements(ent, prop):
    """Statements for a property, preferred first, deprecated dropped."""
    rows = (ent.get('claims') or {}).get(prop) or []
    rows = [r for r in rows if r.get('rank') != 'deprecated' and (r.get('mainsnak') or {}).get('snaktype') == 'value']
    return sorted(rows, key=lambda r: 0 if r.get('rank') == 'preferred' else 1)


def _value(st):
    return ((st.get('mainsnak') or {}).get('datavalue') or {}).get('value')


def _year(time_value):
    """'+1958-01-01T00:00:00Z' -> 1958, only when the date is precise to the year or better (precision 9+)."""
    if not isinstance(time_value, dict) or (time_value.get('precision') or 0) < 9:
        return None
    m = re.match(r'^([+-])(\d{1,6})-', time_value.get('time') or '')
    return int(m.group(2)) * (1 if m.group(1) == '+' else -1) if m else None


def _qualifier_year(st):
    for q in (st.get('qualifiers') or {}).get(POINT_IN_TIME, []):
        y = _year((q.get('datavalue') or {}).get('value'))
        if y:
            return y
    return None


def parse(ent):
    """One entity -> the facts we use. Missing facts are simply absent."""
    qid = ent.get('id', '')
    out = {'qid': qid, 'src': wd_url(qid)}

    inc = [y for y in (_year(_value(s)) for s in _statements(ent, P['inception'])) if y]
    if inc:
        out['founded'] = {'v': inc[0], 'all': sorted(set(inc)), 'conflict': len(set(inc)) > 1}

    stu = []
    for s in _statements(ent, P['students']):
        v = _value(s)
        try:
            n = int(round(float((v or {}).get('amount'))))
        except (TypeError, ValueError):
            continue
        if n > 0:
            stu.append({'v': n, 'asof': _qualifier_year(s), 'preferred': s.get('rank') == 'preferred'})
    if stu:
        # latest dated figure first; undated figures only if nothing is dated
        dated = [x for x in stu if x['asof']]
        pool = sorted(dated, key=lambda x: (-x['asof'], not x['preferred'])) if dated else stu
        out['students'] = {'v': pool[0]['v'], 'asof': pool[0]['asof'], 'all': stu}

    co = [_value(s) for s in _statements(ent, P['coords'])]
    if co and isinstance(co[0], dict) and 'latitude' in co[0]:
        out['coords'] = {'lat': round(co[0]['latitude'], 5), 'lon': round(co[0]['longitude'], 5)}

    for key in ('website', 'commons', 'image', 'instagram', 'youtube', 'linkedin'):
        vals = [v for v in (_value(s) for s in _statements(ent, P[key])) if isinstance(v, str) and v.strip()]
        if vals:
            out[key] = vals[0].strip()

    sl = (ent.get('sitelinks') or {}).get('enwiki')
    if sl:
        out['enwiki'] = sl.get('title') if isinstance(sl, dict) else None
    return out


def social_url(kind, handle):
    h = (handle or '').strip().lstrip('@')
    if not h:
        return ''
    if kind == 'instagram':
        return f'https://www.instagram.com/{h}/'
    if kind == 'youtube':
        return f'https://www.youtube.com/channel/{h}' if re.match(r'^UC[\w-]{20,}$', h) else f'https://www.youtube.com/@{h}'
    if kind == 'linkedin':
        return f'https://www.linkedin.com/school/{h}/'
    return ''


def faculties(api, qid):
    """Units that name the university as their parent: [{'name', 'url'}] (url may be empty). Needs the query service."""
    q = (f'SELECT ?f ?fLabel ?site WHERE {{ {{ ?f wdt:P749 wd:{qid} }} UNION {{ ?f wdt:P361 wd:{qid} }} '
         f'OPTIONAL {{ ?f wdt:P856 ?site }} SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }} }} LIMIT 400')
    data = api.get_json(SPARQL, {'query': q, 'format': 'json'})
    seen = {}
    for b in (data.get('results') or {}).get('bindings', []):
        name = (b.get('fLabel') or {}).get('value', '').strip()
        if not name or re.match(r'^Q\d+$', name) or not FACULTY_WORD.search(name) or FACULTY_SKIP.search(name):
            continue
        url = (b.get('site') or {}).get('value', '')
        if name not in seen or (url and not seen[name]['url']):
            seen[name] = {'name': name, 'url': url, 'src': wd_url(qid)}
    return sorted(seen.values(), key=lambda x: x['name'])
