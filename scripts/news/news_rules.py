"""Plain rules for the industry-news reader. No AI. Every word shown on the site is copied from the official page.

- relevant():  does an official item concern international students? (words in the headline and the official summary)
- english():   is the text English? (we never translate)
- excerpt():   the first few sentences of the official summary, cut at a sentence end, never reworded
- allowed():   is the link on the official body's own website?
- parse_date(): one date format at a time, never a guess
"""
import email.utils
import re
import urllib.parse
from datetime import date, datetime

from bs4 import BeautifulSoup

import textutil as T  # scripts/scholarships/textutil.py (path is set by the caller)

# words that say an item is about people who study (broad words such as "education" or "academic" are left out on purpose:
# a department of education publishes much that has nothing to do with international students)
STUDENT = re.compile(
    r"\b(?:students?|study|studying|studies|universit(?:y|ies)|colleges?|graduates?|post-study|scholarships?|tuition|higher education|"
    r"enrol(?:l)?ment|enrol(?:l)?ed|PGWP|OPT|CPT|SEVP|SEVIS|F-1|M-1|J-1|ESOS|CRICOS)\b", re.I)
# words that say the item is about people coming from abroad, or about visas and immigration
INTL = re.compile(
    r"\b(?:international|overseas|foreign|non-(?:EU|EEA|UK)|abroad|visas?|permits?|immigration|migrants?|sponsor(?:s|ship)?|work rights|"
    r"post-study|graduate route|CAS|passport|nationals?)\b", re.I)
# words that settle it: the item is about studying abroad
STRONG = re.compile(
    r"\b(?:international students?|overseas students?|foreign students?|student visas?|study visas?|study permits?|student route|student permission|"
    r"student pass|post-study|graduate route|graduate visa|PGWP|OPT|STEM OPT|SEVP|SEVIS|F-1|ESOS|CRICOS|genuine student|subclass 500|subclass 485|temporary graduate)\b", re.I)
# items about something else, unless a strong word is also there
BLOCK = re.compile(
    r"\b(?:asylum|refugees?|deportations?|border (?:force|security)|illegal migration|citizenship ceremony|sanctions?|extradition|"
    r"passport office|vacanc(?:y|ies)|tenders?|procurement|seizure)\b", re.I)
# items that are enforcement or crime news: never about guidance for students, even if a student is named (checked in the headline)
HARD_BLOCK = re.compile(
    r"\b(?:arrest(?:ed|s)?|detainers?|illegal aliens?|murder\w*|kill(?:ed|ing|s)|charged|convicted|sentenced|indicted|pleads? guilty|fugitives?|"
    r"traffick\w*|smuggl\w*|terror\w*|deport\w*|removal operation)\b", re.I)
STOP = re.compile(r"\b(?:the|and|of|to|in|for|is|are|on|with|that|a|an|from|will|be|new)\b", re.I)
BOILERPLATE = re.compile(
    r"(?:The post .{0,200}? appeared first on .{0,100}?\.?$|Read more\.?|Continue reading\.?|\[\s*(?:…|\.\.\.)\s*\]|Share this page\.?|Last updated:? [^.]{0,40}\.?|"
    r"Published:? [^.]{0,40}\.?|Posted on:? [^.]{0,40}\.?|Skip to (?:main )?content\.?|Print this page\.?|Cookie[s]? (?:settings|policy)[^.]*\.?)", re.I)


def relevant(title, summary='', mode='student', immigration=False):
    """Return (True, '') or (False, reason).
    mode 'all' is for sources that only publish student news (Study in the States).
    immigration=True is for an immigration authority, where every item already concerns visas: a student word alone is then enough.
    Otherwise an item needs a strong word (student visa, study permit, ...), or a student word together with a word about coming from abroad."""
    if mode == 'all':
        return True, ''
    both = f'{title} {summary}'
    if HARD_BLOCK.search(title):
        return False, 'about-something-else'
    strong = bool(STRONG.search(both))
    if BLOCK.search(title) and not strong:
        return False, 'about-something-else'
    if strong:
        return True, ''
    if STUDENT.search(both) and (immigration or INTL.search(both)):
        return True, ''
    return False, 'not-about-students'


def english(text):
    """True when the text reads as English. Short strings are not judged."""
    letters = [c for c in text if c.isalpha()]
    if len(letters) < 25:
        return True
    if sum(1 for c in letters if c.isascii()) / len(letters) < 0.93:
        return False
    words = len(text.split())
    return words < 8 or len(STOP.findall(text)) >= max(2, words // 25)


def _text(html):
    if not html:
        return ''
    if '<' in html:
        html = BeautifulSoup(html, 'html.parser').get_text(' ')
    return T.clean(html)


def excerpt(html, title='', max_chars=360):
    """The first sentences of the official summary, as plain text, ending at a sentence end where possible. '' when there is nothing useful."""
    txt = _text(html)
    txt = T.clean(BOILERPLATE.sub(' ', txt))
    if title and txt.lower().startswith(T.clean(title).lower()):
        txt = T.clean(txt[len(T.clean(title)):]).lstrip('.:–- ')
    if len(txt) < 40 or txt.lower() == T.clean(title).lower():
        return ''
    out, size = [], 0
    for s in re.split(r'(?<=[.!?])\s+(?=[A-Z0-9“"\'£€$])', txt):
        if size + len(s) + (1 if out else 0) > max_chars:
            break
        out.append(s)
        size += len(s) + (1 if len(out) > 1 else 0)
    if out:
        return ' '.join(out)
    cut = txt[:max_chars].rsplit(' ', 1)[0].rstrip(' ,;:–-')
    return cut + '…'


def allowed(url, domains):
    """True when the link is on one of the official body's own domains (the domain itself or any sub-domain of it)."""
    host = urllib.parse.urlsplit(url).hostname or ''
    host = host.lower()
    return bool(host) and any(host == d.lower() or host.endswith('.' + d.lower()) for d in domains)


def parse_date(s, today=None):
    """A date string from a feed or a page, as an ISO date; None when it cannot be read with certainty."""
    s = (s or '').strip()
    if not s:
        return None
    try:
        d = email.utils.parsedate_to_datetime(s)
        if d:
            return d.date().isoformat()
    except (TypeError, ValueError, IndexError):
        pass
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            return None
    found = T.parse_full_dates(s)
    return found[0] if found else None


def age_days(iso, today):
    try:
        return (datetime.fromisoformat(today).date() - datetime.fromisoformat(iso).date()).days
    except (TypeError, ValueError):
        return None
