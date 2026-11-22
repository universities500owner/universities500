"""Campus photos from Wikimedia Commons, with the credit the licence asks for.

Only files under a licence that allows reuse with credit (CC BY, CC BY-SA, CC0, public domain) are kept. Every photo
carries its author, licence name and the Commons page, so the site can print a small credit under it.
A photo must also be big and landscape, and its file name must not look like a logo, map, plan or a posed portrait."""
import datetime
import html
import re

from api import COMMONS

LICENCE_OK = re.compile(r'^(?:CC[ -]BY(?:[ -]SA)?(?:[ -]\d(?:\.\d)?)?(?:[ -][A-Za-z]{2,3})?|CC0(?:[ -]1\.0)?|Public domain|PD[\w -]*)$', re.I)
NAME_BAD = re.compile(
    r'logo|seal\b|crest|coat[ _]of|\barms\b|flag\b|\bmap\b|\bplan\b|diagram|poster|banner|brochure|portrait|signature|sticker|icon|'
    r'emblem|graduat|ceremony|protest|demonstration|\bbus\b|\btram\b|\btrain\b|plaque|statue of|bust of|\bprofessor\b|\bdr\.? |'
    r'screenshot|infographic|chart|\bgraph\b|engraving|etching|drawing|painting|lithograph|woodcut|illustration|atlas|gravure|estampe|\.svg$|\.pdf$|\.tif|protest|demolition|encampment|\bcamp\b|rally|vigil|memorial|'
    r'\bfire\b|flood|accident|riot|strike|construction|\bcrane\b|vehicle|\bcars?\b|truck|cushman|\.thumb\.|\binterior|\bsalle\b|banner', re.I)
CATS_BAD = re.compile(
    r'protest|demonstration|encampment|construction|vehicle|\bcars?\b|portrait|graduat|ceremon|events?\b|sport|concert|exhibition|logos?\b|'
    r'murals?|artworks?|statues?|people|interiors?|food|conference|lectures?\b|stock|plaques?|signs?\b|demolition|disaster|crime|'
    r'\bmaps?\b|atlas|prints?\b|engravings?|etchings?|paintings?|drawings?|illustrations?|lithograph|woodcut|postcards?|stamps?|manuscripts?|books?\b|'
    r'historic(?:al)? (?:images?|photographs?|views?)|meetings?|visits?\b|delegations?|groups?\b', re.I)
SUBCAT_KEEP = re.compile(r'campus|building|library|quad|hall\b|tower|gate\b|entrance|architecture|exterior|aerial|lecture|laborator|student cent|main', re.I)
SUBCAT_SKIP = re.compile(r'people|alumni|portrait|sport|event|logo|coat|map|history|\d{2}th|stub|document|publication|persons|staff|students? ', re.I)
HINT_WORDS = re.compile(r'campus|aerial|library|quad|entrance|exterior|building|tower|hall|facade|main|gate|courtyard', re.I)
GENERIC = {'the', 'of', 'and', 'campus', 'main', 'university', 'universität', 'universite', 'université', 'city', 'centre', 'center',
           'college', 'institute', 'school', 'de', 'la', 'le', 'du', 'des', 'van', 'der', 'den', 'von', 'zu', 'for'}
CREDIT_BAD = re.compile(r'please|thank you|credit line|unknown|no machine-readable|assumed|this image was|see source|own work by|anonymous', re.I)
MIN_W, MIN_H = 1600, 900


def strip_html(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s or ''))).strip()


def meta(info, key):
    return strip_html(((info.get('extmetadata') or {}).get(key) or {}).get('value', ''))


def photo_year(info):
    # only DateTimeOriginal is a capture date; 'DateTime' is when the file was last saved, which is how a scanned engraving
    # ends up looking recent
    m = re.search(r'\b(19|20)\d\d\b', meta(info, 'DateTimeOriginal'))
    if m:
        return int(m.group(0)), 'taken'
    m = re.match(r'^(\d{4})-', info.get('timestamp') or '')
    return (int(m.group(1)), 'uploaded') if m else (None, '')


def gate(page):
    """(ok, reason) for one imageinfo page. The reason is what the report counts."""
    ii = (page.get('imageinfo') or [None])[0]
    if not ii:
        return False, 'no info'
    title = page.get('title', '')
    if NAME_BAD.search(title):
        return False, 'name'
    if ii.get('mime') != 'image/jpeg':
        return False, 'type'
    w, h = ii.get('width') or 0, ii.get('height') or 0
    if w < MIN_W or h < MIN_H:
        return False, 'small'
    if not 1.25 <= w / max(h, 1) <= 2.4:
        return False, 'shape'
    lic = meta(ii, 'LicenseShortName')
    if not LICENCE_OK.match(lic):
        return False, 'licence'
    if meta(ii, 'Restrictions'):
        return False, 'restricted'
    if CATS_BAD.search(meta(ii, 'Categories')):
        return False, 'topic'
    who = meta(ii, 'Artist') or meta(ii, 'Credit')
    if not who:
        return False, 'no author'
    if len(who) > 70 or CREDIT_BAD.search(who):     # an instruction or a sentence is not a name we can print under a photo
        return False, 'author text'
    return True, ''


def to_photo(page, thumb_width):
    ii = page['imageinfo'][0]
    year, how = photo_year(ii)
    author = meta(ii, 'Artist') or meta(ii, 'Credit')
    return {
        'title': page['title'],
        'thumb': ii.get('thumburl') or ii.get('url'),
        'thumbWidth': ii.get('thumbwidth') or thumb_width,
        'width': ii.get('width'), 'height': ii.get('height'),
        'author': author[:90],
        'licence': meta(ii, 'LicenseShortName'),
        'licenceUrl': meta(ii, 'LicenseUrl'),
        'page': ii.get('descriptionurl') or '',
        'year': year, 'yearFrom': how,
        'categories': meta(ii, 'Categories'),
        'description': meta(ii, 'ImageDescription')[:160],
    }


def info(api, titles, thumb_width=960):
    """Image info for file titles, 40 at a time -> list of pages (those with info)."""
    out = []
    for i in range(0, len(titles), 40):
        data = api.get_json(COMMONS, {
            'action': 'query', 'format': 'json', 'formatversion': '2', 'titles': '|'.join(titles[i:i + 40]),
            'prop': 'imageinfo', 'iiprop': 'url|size|mime|extmetadata|timestamp', 'iiurlwidth': thumb_width,
        })
        out += [p for p in (data.get('query') or {}).get('pages', []) if p.get('imageinfo')]
    return out


def members(api, category, kind, limit):
    data = api.get_json(COMMONS, {
        'action': 'query', 'format': 'json', 'formatversion': '2', 'list': 'categorymembers',
        'cmtitle': category if category.startswith('Category:') else f'Category:{category}',
        'cmtype': kind, 'cmlimit': min(limit, 500),
    })
    return [m['title'] for m in (data.get('query') or {}).get('categorymembers', [])]


def search(api, query, limit=20):
    data = api.get_json(COMMONS, {
        'action': 'query', 'format': 'json', 'formatversion': '2', 'list': 'search', 'srnamespace': 6,
        'srsearch': f'{query} filetype:bitmap', 'srlimit': limit,
    })
    return [m['title'] for m in (data.get('query') or {}).get('search', [])]


def score(photo, this_year):
    y = photo.get('year') or this_year - 30
    s = max(0, 30 - (this_year - y)) * 2
    s += min(photo['width'] or 0, 6000) / 400
    if HINT_WORDS.search(photo['title'] + ' ' + photo.get('categories', '')):
        s += 8
    return s


def gallery(api, category, this_year=None, want=8, scan=260):
    """Up to `want` good, recent photos from a Commons category and its building/campus sub-categories.
    Returns (photos, counts) where counts says how many files were scanned and why others were dropped."""
    this_year = this_year or datetime.date.today().year
    counts = {'scanned': 0}
    titles = members(api, category, 'file', scan)
    for sub in [s for s in members(api, category, 'subcat', 120) if SUBCAT_KEEP.search(s) and not SUBCAT_SKIP.search(s)][:6]:
        titles += members(api, sub, 'file', 80)
    titles = list(dict.fromkeys(t for t in titles if not NAME_BAD.search(t)))[:scan + 400]
    pages = info(api, titles)
    counts['scanned'] = len(pages)
    good = []
    for p in pages:
        ok, why = gate(p)
        if ok:
            ph = to_photo(p, 960)
            if ph['yearFrom'] != 'taken':           # no camera date: cannot say it is recent, and may not be a photograph
                counts['no date'] = counts.get('no date', 0) + 1
                continue
            good.append(ph)
        else:
            counts[why] = counts.get(why, 0) + 1
    # a campus gallery shows buildings and grounds: use photos whose title or categories say so, when there are enough
    scenic = [p for p in good if HINT_WORDS.search(p['title'] + ' ' + p.get('categories', ''))]
    pool = scenic if len(scenic) >= want // 2 else good
    pool.sort(key=lambda x: -score(x, this_year))
    picked, per_author = [], {}
    for ph in pool:
        a = ph['author'].lower()
        if per_author.get(a, 0) >= 2:
            continue
        per_author[a] = per_author.get(a, 0) + 1
        picked.append(ph)
        if len(picked) == want:
            break
    counts['usable'] = len(good)
    return picked, counts


def _tokens(s):
    return [t for t in re.findall(r'[a-zà-ÿ]{3,}', s.lower()) if t not in GENERIC]


def campus_photo(api, campus, uni_name, this_year=None):
    """One photo for a named campus: a search on Commons, then the same checks. The photo's title or categories must
    mention both the campus and the university, so a 'Melbourne' search cannot return any random Melbourne street."""
    this_year = this_year or datetime.date.today().year
    ctoks, utoks = _tokens(campus), _tokens(uni_name)
    if not utoks:
        return None
    titles = search(api, f'{campus} {uni_name} campus')
    best = None
    for p in info(api, titles[:20]):
        ok, _ = gate(p)
        if not ok:
            continue
        ph = to_photo(p, 480)
        if ph['yearFrom'] != 'taken':
            continue
        hay = (ph['title'] + ' ' + ph['categories']).lower()
        if not HINT_WORDS.search(hay):               # a campus thumbnail must show buildings or grounds
            continue
        if ctoks and not any(t in hay for t in ctoks):
            continue
        if not any(t in hay for t in utoks[:2]):
            continue
        if best is None or score(ph, this_year) > score(best, this_year):
            best = ph
    return best
