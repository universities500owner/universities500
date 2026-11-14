"""Turns the free-text location an employer typed into one of our 14 destinations. Never guesses:
if the text is vague, remote-only, or could be two countries, the posting is skipped."""
import re
import unicodedata

COUNTRY_NAMES = {
    'australia': 'Australia', 'canada': 'Canada', 'france': 'France', 'germany': 'Germany', 'ireland': 'Ireland',
    'malaysia': 'Malaysia', 'netherlands': 'Netherlands', 'new-zealand': 'New Zealand', 'norway': 'Norway',
    'singapore': 'Singapore', 'sweden': 'Sweden', 'uae': 'United Arab Emirates', 'uk': 'United Kingdom', 'usa': 'United States',
}

# Words that name a country outright. Checked first, longest first.
ALIASES = {
    'northern ireland': 'uk', 'united kingdom': 'uk', 'great britain': 'uk', 'england': 'uk', 'scotland': 'uk', 'wales': 'uk',
    'united arab emirates': 'uae', 'u.a.e': 'uae', 'uae': 'uae',
    'united states of america': 'usa', 'united states': 'usa', 'u.s.a': 'usa', 'u.s': 'usa', 'usa': 'usa',
    'new zealand': 'new-zealand', 'aotearoa': 'new-zealand',
    'the netherlands': 'netherlands', 'netherlands': 'netherlands', 'nederland': 'netherlands', 'holland': 'netherlands',
    'republic of ireland': 'ireland', 'ireland': 'ireland',
    'deutschland': 'germany', 'germany': 'germany', 'australia': 'australia', 'canada': 'canada', 'france': 'france',
    'malaysia': 'malaysia', 'norway': 'norway', 'norge': 'norway', 'singapore': 'singapore', 'sweden': 'sweden', 'sverige': 'sweden',
    'uk': 'uk', 'gb': 'uk', 'nz': 'new-zealand', 'us': 'usa',
    # regions that only exist in one country
    'new south wales': 'australia', 'queensland': 'australia', 'western australia': 'australia', 'south australia': 'australia', 'tasmania': 'australia',
    'ontario': 'canada', 'quebec': 'canada', 'british columbia': 'canada', 'alberta': 'canada', 'manitoba': 'canada', 'nova scotia': 'canada',
    'new brunswick': 'canada', 'saskatchewan': 'canada',
    'california': 'usa', 'new york': 'usa', 'texas': 'usa', 'massachusetts': 'usa', 'washington dc': 'usa', 'illinois': 'usa', 'colorado': 'usa',
    'florida': 'usa', 'north carolina': 'usa', 'pennsylvania': 'usa', 'oregon': 'usa', 'ohio': 'usa', 'virginia': 'usa', 'michigan': 'usa',
    'minnesota': 'usa', 'new jersey': 'usa', 'utah': 'usa', 'arizona': 'usa',
}

# Two-letter codes that are safe on their own after a comma ("Singapore, SG").
ISO = {'AU': 'australia', 'FR': 'france', 'IE': 'ireland', 'MY': 'malaysia', 'NZ': 'new-zealand', 'SG': 'singapore', 'SE': 'sweden',
       'AE': 'uae', 'GB': 'uk', 'UK': 'uk', 'US': 'usa', 'NO': 'norway'}
US_STATES = set('AL AK AZ AR CO CT FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WV WI WY DC'.split())
CA_PROVINCES = set('AB BC MB NB NS NT NU ON PE QC SK YT'.split())
AU_STATES = {'NSW', 'VIC', 'QLD', 'TAS', 'ACT'}
# CA, DE, NL, WA, SA, NT, WA mean different countries or states; the city decides.

CITIES = {
    'australia': 'sydney melbourne brisbane perth adelaide canberra gold coast hobart darwin wollongong geelong parramatta north sydney',
    'canada': 'toronto vancouver montreal ottawa calgary edmonton waterloo kitchener mississauga winnipeg halifax quebec city saskatoon regina markham burnaby kelowna',
    'france': "paris lyon marseille toulouse nantes bordeaux lille nice strasbourg montpellier rennes grenoble sophia antipolis boulogne-billancourt issy-les-moulineaux la defense courbevoie puteaux levallois-perret nanterre rueil-malmaison clichy villeneuve-d'ascq",
    'germany': 'berlin munich munchen hamburg frankfurt cologne koln dusseldorf stuttgart leipzig dresden hannover hanover nuremberg nurnberg bremen karlsruhe mannheim heidelberg aachen bonn essen dortmund darmstadt potsdam walldorf ingolstadt wolfsburg jena freiburg mainz regensburg augsburg munster kiel rostock ulm erlangen braunschweig paderborn',
    'ireland': 'dublin cork galway limerick waterford kilkenny drogheda dundalk sligo athlone maynooth letterkenny',
    'malaysia': 'kuala lumpur penang george town petaling jaya cyberjaya johor bahru shah alam selangor putrajaya subang jaya kota kinabalu kuching iskandar puteri ipoh melaka malacca bangsar',
    'netherlands': "amsterdam rotterdam the hague den haag utrecht eindhoven delft groningen leiden haarlem breda tilburg nijmegen maastricht almere amersfoort enschede arnhem hilversum zwolle schiphol hoofddorp 's-hertogenbosch",
    'new-zealand': 'auckland wellington christchurch dunedin tauranga queenstown napier palmerston north nelson lower hutt',
    'norway': 'oslo bergen trondheim stavanger tromso kristiansand drammen fredrikstad sandvika lysaker fornebu',
    'singapore': 'singapore',
    'sweden': 'stockholm gothenburg goteborg malmo uppsala lund linkoping vasteras orebro umea jonkoping norrkoping helsingborg kista solna sundbyberg lulea karlstad',
    'uae': 'dubai abu dhabi sharjah ajman ras al khaimah fujairah al ain umm al quwain masdar',
    'uk': 'london manchester birmingham edinburgh glasgow bristol leeds liverpool sheffield cardiff belfast nottingham newcastle upon tyne oxford reading leicester southampton brighton aberdeen cheltenham milton keynes slough guildford bath exeter york coventry swansea dundee norwich plymouth derby ipswich portsmouth canary wharf harwell',
    'usa': 'new york nyc san francisco los angeles seattle boston chicago austin denver atlanta dallas houston san diego san jose mountain view palo alto sunnyvale menlo park redwood city santa clara cupertino irvine miami philadelphia pittsburgh minneapolis raleigh durham salt lake city phoenix detroit nashville charlotte san mateo oakland boulder brooklyn bellevue redmond kirkland plano irving cleveland st louis tampa orlando las vegas indianapolis baltimore ann arbor princeton stamford hoboken jersey city',
}
# multi-word cities are written above separated by single spaces; list them explicitly so we can split correctly
MULTI = {
    'australia': ['gold coast', 'north sydney'],
    'canada': ['quebec city'],
    'france': ['sophia antipolis', 'la defense'],
    'malaysia': ['kuala lumpur', 'george town', 'petaling jaya', 'johor bahru', 'shah alam', 'subang jaya', 'kota kinabalu', 'iskandar puteri'],
    'netherlands': ['the hague', 'den haag'],
    'new-zealand': ['palmerston north', 'lower hutt'],
    'uae': ['abu dhabi', 'ras al khaimah', 'al ain', 'umm al quwain'],
    'uk': ['newcastle upon tyne', 'milton keynes', 'canary wharf'],
    'usa': ['new york', 'san francisco', 'los angeles', 'san diego', 'san jose', 'mountain view', 'palo alto', 'menlo park', 'redwood city', 'santa clara', 'salt lake city', 'san mateo', 'ann arbor', 'jersey city', 'las vegas', 'st louis'],
}


def fold(s):
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(ch for ch in s if not unicodedata.combining(ch))
    return s.lower()


def _build_cities():
    out = {}
    for c, text in CITIES.items():
        names = set(MULTI.get(c, []))
        rest = text
        for m in sorted(MULTI.get(c, []), key=len, reverse=True):
            rest = rest.replace(m, ' ')
        names.update(w for w in rest.split() if w)
        for n in names:
            out[n] = c
    return out


CITY = _build_cities()
CITY_RE = re.compile(r"(?<![a-z])(" + '|'.join(re.escape(n) for n in sorted(CITY, key=len, reverse=True)) + r")(?![a-z])")
ALIAS_RE = re.compile(r"(?<![a-z])(" + '|'.join(re.escape(n) for n in sorted(ALIASES, key=len, reverse=True)) + r")(?![a-z])")
SPLIT = re.compile(r'\s*(?:;|\||\n|\s/\s|\sor\s|\sand\s)\s*', re.I)
NOISE = re.compile(r'\((?:[^)]*)\)|\b(hybrid|on-?site|onsite|remote|office|hq|headquarters|flexible|NSW|VIC|QLD|TAS|ACT)\b', re.I)


def _display_city(piece, country_hit):
    first = re.split(r',|\s-\s|\s–\s', piece)[0]
    first = NOISE.sub(' ', first)
    first = re.sub(r'\s+', ' ', first).strip(' -–.')
    f = fold(first)
    names = {n.lower() for n in COUNTRY_NAMES.values()}
    if not first or f in names or (f in ALIASES and f not in CITY) or f in ('remote', 'multiple locations', 'multiple', 'various', 'anywhere'):
        return None
    if f in CITY:
        return first
    return first if len(first) <= 40 and re.search(r'[A-Za-z]', first) else None


def resolve_piece(piece):
    """One location string -> (city, country) or None."""
    raw = piece.strip()
    if not raw:
        return None
    f = fold(raw)
    # 1. a country (or a region that exists in only one country) is named outright
    named = {ALIASES[m.group(1)] for m in ALIAS_RE.finditer(f)}
    # a US state name inside "Washington DC" etc is fine; but two different countries means we cannot tell
    if len(named) > 1:
        return None
    if len(named) == 1:
        c = named.pop()
        city = _display_city(raw, c)
        if city is None and re.search(r'\bremote\b', f):
            return None  # remote-only: no place to be
        return (city, c)
    # 2. a safe country code or a state / province code after a comma
    parts = [p.strip() for p in raw.split(',')]
    code = parts[-1].upper() if len(parts) > 1 else ''
    if code in ISO:
        return (_display_city(raw, ISO[code]), ISO[code])
    if code in CA_PROVINCES:
        return (_display_city(raw, 'canada'), 'canada')
    if code in US_STATES:
        return (_display_city(raw, 'usa'), 'usa')
    if code in AU_STATES:
        return (_display_city(raw, 'australia'), 'australia')
    m = re.search(r'\b(NSW|VIC|QLD|TAS|ACT)\b', raw)
    if m:
        return (_display_city(raw, 'australia'), 'australia')
    # 3. a city we know
    hits = {CITY[m.group(1)] for m in CITY_RE.finditer(f)}
    if len(hits) == 1:
        c = hits.pop()
        return (_display_city(raw, c), c)
    return None


def resolve(text):
    """Free text -> list of unique (city, country). Empty when unsure."""
    if not text:
        return []
    out, seen = [], set()
    for piece in SPLIT.split(str(text)):
        r = resolve_piece(piece)
        if r and (r[0], r[1]) not in seen:
            seen.add((r[0], r[1]))
            out.append(r)
    return out


def from_iso2(code):
    return ISO.get((code or '').upper()) or {'CA': 'canada', 'DE': 'germany', 'NL': 'netherlands'}.get((code or '').upper())
