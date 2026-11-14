"""A polite fetcher: identifies itself, obeys robots.txt, waits between requests to the same site,
follows redirects by hand so every hop is checked, and gives up quickly on slow or unhappy sites."""
import gzip
import io
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from collections import Counter, defaultdict

BOT_TOKEN = 'Universities500Bot'
MAX_CRAWL_DELAY = 20


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


class Result:
    __slots__ = ('url', 'final_url', 'status', 'ctype', 'body', 'error', 'robots_blocked', 'truncated')

    def __init__(self, url):
        self.url = url
        self.final_url = url
        self.status = 0
        self.ctype = ''
        self.body = b''
        self.error = None
        self.robots_blocked = False
        self.truncated = False

    @property
    def ok(self):
        return self.status == 200 and not self.error

    @property
    def text(self):
        if not self.body:
            return ''
        enc = 'utf-8'
        ct = self.ctype.lower()
        if 'charset=' in ct:
            enc = ct.split('charset=')[1].split(';')[0].strip() or 'utf-8'
        try:
            return self.body.decode(enc, errors='replace')
        except LookupError:
            return self.body.decode('utf-8', errors='replace')


def reg_domain(host):
    """Rough registrable domain: ox.ac.uk, unimelb.edu.au, mit.edu. Good enough to keep a crawl on one institution."""
    host = host.lower().split(':')[0]
    if host.replace('.', '').isdigit() or host == 'localhost':
        return host
    labels = host.split('.')
    if len(labels) >= 3 and len(labels[-1]) == 2 and labels[-2] in ('ac', 'co', 'edu', 'gov', 'org', 'com', 'net', 'sch'):
        return '.'.join(labels[-3:])
    return '.'.join(labels[-2:])


class Fetcher:
    def __init__(self, user_agent, delay=3.0, timeout=25, max_bytes=2_500_000, deadline=None, allow_http_local=False):
        self.ua = user_agent
        self.delay = delay
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.deadline = deadline  # time.monotonic() value after which we stop asking
        self.opener = urllib.request.build_opener(NoRedirect)
        self._locks = defaultdict(threading.Lock)
        self._next_ok = defaultdict(float)
        self._robots = {}
        self._robots_lock = threading.Lock()
        self._host_delay = {}
        self._dead_hosts = {}  # host -> reason, for this run
        self.stats = Counter()
        self.robots_blocked = []  # (host, path)
        self.errors = []  # (url, reason)
        self.gone = set()  # URLs that answered 404 or 410
        self.robots_text = {}  # host -> robots.txt body, for the report
        self.slock = threading.Lock()

    # ---------- robots ----------
    def _robots_for(self, scheme, host):
        key = (scheme, host)
        with self._robots_lock:
            if key in self._robots:
                return self._robots[key]
        rp = urllib.robotparser.RobotFileParser()
        status, body, _ct, _loc = self._raw(f'{scheme}://{host}/robots.txt')
        verdict = 'rules'
        if status == 200:
            txt = body.decode('utf-8', errors='replace')
            rp.parse(txt.splitlines())
            self.robots_text[host] = txt[:4000]
        elif status in (401, 403):
            verdict = 'deny'  # RFC 9309: forbidden means the crawler should assume complete disallow
        elif 400 <= status < 500:
            verdict = 'allow'  # no robots.txt
        else:
            verdict = 'deny'  # unreachable or erroring: do not crawl this run
        entry = (rp, verdict)
        with self._robots_lock:
            self._robots[key] = entry
        return entry

    def allowed(self, url):
        p = urllib.parse.urlsplit(url)
        rp, verdict = self._robots_for(p.scheme, p.netloc)
        if verdict == 'deny':
            return False
        if verdict == 'allow':
            return True
        return rp.can_fetch(BOT_TOKEN, url)

    def crawl_delay(self, url):
        p = urllib.parse.urlsplit(url)
        rp, verdict = self._robots_for(p.scheme, p.netloc)
        if verdict != 'rules':
            return self.delay
        cd = rp.crawl_delay(BOT_TOKEN)
        rr = rp.request_rate(BOT_TOKEN)
        if rr and rr.requests:
            cd = max(cd or 0, rr.seconds / rr.requests)
        return max(self.delay, float(cd)) if cd else self.delay

    def sitemaps(self, scheme, host):
        rp, verdict = self._robots_for(scheme, host)
        if verdict != 'rules':
            return []
        return list(rp.site_maps() or [])

    # ---------- low level ----------
    def _wait(self, host, delay):
        with self._locks[host]:
            now = time.monotonic()
            wait = self._next_ok[host] - now
            if wait > 0:
                time.sleep(wait)
            self._next_ok[host] = time.monotonic() + delay

    def _raw(self, url, accept=None):
        """One request, no redirects. Returns (status, body, content_type, location). Status 0 means a network error."""
        p = urllib.parse.urlsplit(url)
        host = p.netloc
        if host in self._dead_hosts:
            return 0, b'', '', ''
        if self.deadline and time.monotonic() > self.deadline:
            return 0, b'', '', ''
        delay = self._host_delay.get(host, self.delay)
        self._wait(host, delay)
        req = urllib.request.Request(url, headers={
            'User-Agent': self.ua,
            'Accept': accept or 'text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.5',
            'Accept-Language': 'en',
            'Accept-Encoding': 'gzip',
        })
        for attempt in range(3):
            try:
                with self.opener.open(req, timeout=self.timeout) as r:
                    data = r.read(self.max_bytes + 1)
                    enc = r.headers.get('Content-Encoding', '')
                    if 'gzip' in enc:
                        try:
                            data = gzip.GzipFile(fileobj=io.BytesIO(data)).read(self.max_bytes + 1)
                        except OSError:
                            pass
                    with self.slock:
                        self.stats['requests'] += 1
                        self.stats['bytes'] += len(data)
                    return r.status, data, r.headers.get('Content-Type', ''), r.headers.get('Location', '')
            except urllib.error.HTTPError as e:
                code = e.code
                ctype = e.headers.get('Content-Type', '') if e.headers else ''
                loc = e.headers.get('Location', '') if e.headers else ''
                with self.slock:
                    self.stats['requests'] += 1
                if code in (301, 302, 303, 307, 308):
                    return code, b'', ctype, loc
                if code == 429 or code == 503:
                    ra = e.headers.get('Retry-After', '') if e.headers else ''
                    secs = int(ra) if ra.isdigit() else 10 * (attempt + 1)
                    if secs > 60:
                        self._dead_hosts[host] = f'asked us to wait {secs}s'
                        return code, b'', ctype, loc
                    time.sleep(secs)
                    continue
                if 500 <= code < 600 and attempt < 2:
                    time.sleep(3 * (attempt + 1))
                    continue
                return code, b'', ctype, loc
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                if attempt < 2:
                    time.sleep(3 * (attempt + 1))
                    continue
                with self.slock:
                    self.stats['network_errors'] += 1
                self._dead_hosts[host] = f'network error: {getattr(e, "reason", e)}'
                return 0, b'', '', ''
        return 0, b'', '', ''

    # ---------- public ----------
    def get(self, url, accept=None):
        res = Result(url)
        cur = url
        for _hop in range(6):
            p = urllib.parse.urlsplit(cur)
            if p.scheme not in ('http', 'https') or not p.netloc:
                res.error = 'unsupported url'
                return res
            if not self.allowed(cur):
                res.robots_blocked = True
                res.error = 'blocked by robots.txt'
                with self.slock:
                    self.stats['robots_blocked'] += 1
                    self.robots_blocked.append((p.netloc, p.path or '/'))
                return res
            # honour Crawl-delay for this host
            cd = self.crawl_delay(cur)
            if cd > MAX_CRAWL_DELAY:
                res.error = f'robots.txt asks for a {cd:.0f}s Crawl-delay'
                self._dead_hosts[p.netloc] = res.error
                return res
            self._host_delay[p.netloc] = cd
            status, body, ctype, loc = self._raw(cur, accept=accept)
            if status in (301, 302, 303, 307, 308) and loc:
                cur = urllib.parse.urljoin(cur, loc)
                continue
            res.final_url = cur
            res.status = status
            res.ctype = ctype
            res.body = body[:self.max_bytes]
            res.truncated = len(body) > self.max_bytes
            if status in (404, 410):
                with self.slock:
                    self.gone.add(url)
            if status == 0:
                res.error = self._dead_hosts.get(p.netloc) or 'no response'
            elif status >= 400:
                res.error = f'HTTP {status}'
            if res.error:
                with self.slock:
                    self.errors.append((url, res.error))
            return res
        res.error = 'too many redirects'
        return res

    def host_dead(self, host):
        return self._dead_hosts.get(host)
