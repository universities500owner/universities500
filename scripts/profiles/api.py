"""A small, polite client for the Wikimedia APIs (Wikidata, Commons, the Wikidata query service).

Wikimedia asks API users to identify themselves with a contact address, to send one request at a time and to back off
when told to. robots.txt is for crawlers; the API policy is what applies here. Standard library only."""
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

WIKIDATA = 'https://www.wikidata.org/w/api.php'
COMMONS = 'https://commons.wikimedia.org/w/api.php'
SPARQL = 'https://query.wikidata.org/sparql'


class ApiError(Exception):
    pass


class Api:
    def __init__(self, mailto='', delay=1.0, timeout=60):
        contact = f"; {mailto}" if mailto else ""
        self.ua = f'Universities500Bot/1.0 (+https://universities500.com/bot/{contact})'
        self.delay = delay
        self.timeout = timeout
        self.requests = 0
        self._next = 0.0
        self._lock = threading.Lock()

    def get_json(self, base, params, tries=4):
        url = base + ('&' if '?' in base else '?') + urllib.parse.urlencode(params)
        last = None
        for attempt in range(tries):
            with self._lock:
                wait = self._next - time.monotonic()
                if wait > 0:
                    time.sleep(wait)
                self._next = time.monotonic() + self.delay
            req = urllib.request.Request(url, headers={'User-Agent': self.ua, 'Accept': 'application/json'})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    self.requests += 1
                    return json.load(r)
            except urllib.error.HTTPError as e:
                last = f'HTTP {e.code}'
                if e.code in (429, 500, 502, 503, 504):
                    ra = e.headers.get('Retry-After', '') if e.headers else ''
                    time.sleep(min(int(ra) if ra.isdigit() else 5 * (attempt + 1), 60))
                    continue
                raise ApiError(f'{last} for {base}') from e
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
                last = str(getattr(e, 'reason', e))
                time.sleep(3 * (attempt + 1))
        raise ApiError(f'{last} for {base}')
