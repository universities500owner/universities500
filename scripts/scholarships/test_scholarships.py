#!/usr/bin/env python3
"""Offline tests: a stub university website on localhost, no internet, no AI.
Run: python3 scripts/scholarships/test_scholarships.py"""
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import extract as X  # noqa: E402
import textutil as T  # noqa: E402
from fetcher import Fetcher  # noqa: E402

PORT = {}
HITS = []


def page(title, body, extra=''):
    return f'<!doctype html><html lang="en"><head><title>{title} | Test University</title>{extra}</head><body><header><nav><a href="/">Home</a></nav></header><main><h1>{title}</h1>{body}</main><footer>footer text</footer></body></html>'


def pages():
    p = PORT['p']
    base = f'http://127.0.0.1:{p}'
    links = ''.join(f'<li><a href="/scholarships/filler-{i}/">Filler Scholarship {i}</a></li>' for i in range(14))
    return {
        '/robots.txt': ('text/plain', f'User-agent: *\nDisallow: /private/\nSitemap: {base}/sitemap.xml\n'),
        '/sitemap.xml': ('application/xml', '<?xml version="1.0"?><urlset>' + ''.join(f'<url><loc>{base}{u}</loc></url>' for u in [
            '/scholarships/', '/international/scholarships/global-excellence-scholarship/', '/scholarships/home-students-bursary/',
            '/scholarships/doctoral-award/', '/scholarships/table/', '/private/secret-scholarship/', '/news/scholarship-news/', '/about/']) + '</urlset>'),
        '/': ('text/html', page('Test University', '<p>Welcome to Test University, a place to study.</p>' * 10, '') .replace('<nav><a href="/">Home</a></nav>', '<nav><a href="/">Home</a><a href="/scholarships/">Scholarships</a></nav>')),
        '/scholarships/': ('text/html', page('Scholarships', f'<p>Funding for students at Test University. Browse every award below.</p><ul>{links}</ul>' + '<p>Long enough text for the page. </p>' * 12)),
        '/international/scholarships/global-excellence-scholarship/': ('text/html', page('Global Excellence Scholarship', '''
            <p>The Global Excellence Scholarship rewards outstanding international undergraduate and postgraduate taught applicants.</p>
            <p>The scholarship is worth up to £5,000 per year. Applications open on 1 October 2026 and close on 15 January 2027. Results will be announced on 1 March 2027.</p>
            <h2>Eligibility</h2><ul><li>You must be an international student paying overseas fees</li><li>You must hold an offer for a full-time on-campus course</li></ul>
            <p><a href="/apply/global/">Apply now</a></p>''', '<meta name="description" content="A merit scholarship for international students starting a bachelor or master programme at Test University.">')),
        '/scholarships/home-students-bursary/': ('text/html', page('Home Students Bursary', '<p>This bursary is for home students only. Worth £1,000. Deadline: 1 June 2027. Undergraduate courses.</p>' * 3)),
        '/scholarships/doctoral-award/': ('text/html', page('Doctoral Research Award', '<p>An award for international PhD students. Worth £20,000 per year. Deadline 3 March 2027.</p>' * 3)),
        '/scholarships/table/': ('text/html', page('International Awards Table', '''
            <p>Awards for international students on undergraduate and master courses.</p>
            <table><tr><th>Award</th><th>Amount</th><th>Deadline</th></tr>
            <tr><td><a href="/awards/alpha/">Alpha Excellence Award</a></td><td>£2,500</td><td>30 April 2027</td></tr>
            <tr><td>Beta Merit Award</td><td>50% tuition fee waiver</td><td>1 May 2027</td></tr></table>''' + '<p>filler text to make the page long enough. </p>' * 12)),
        '/private/secret-scholarship/': ('text/html', page('Secret Scholarship', '<p>International students, £9,000, deadline 1 May 2027, undergraduate.</p>')),
    }


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        HITS.append(self.path)
        pg = pages().get(self.path)
        if not pg:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header('Content-Type', pg[0] + '; charset=utf-8')
        self.end_headers()
        self.wfile.write(pg[1].encode())


def setUpModule():
    srv = HTTPServer(('127.0.0.1', 0), H)
    PORT['p'] = srv.server_address[1]
    PORT['srv'] = srv
    threading.Thread(target=srv.serve_forever, daemon=True).start()


def tearDownModule():
    PORT['srv'].shutdown()


class TextTests(unittest.TestCase):
    def test_dates(self):
        d = T.find_dates('Applications open on 1 October 2026 and close on 15 January 2027. Results will be announced on 1 March 2027.')
        self.assertEqual([x['iso'] for x in d['deadlines']], ['2027-01-15'])
        self.assertEqual([x['iso'] for x in d['opens']], ['2026-10-01'])

    def test_no_year_stays_text(self):
        d = T.find_dates('Deadline: 15 March.')
        self.assertEqual(d['deadlines'], [])
        self.assertEqual(d['partial'][0]['text'], '15 March')

    def test_ambiguous_numeric_date_skipped(self):
        self.assertEqual(T.parse_full_dates('Deadline 03/04/2027'), [])
        self.assertEqual(T.parse_full_dates('Deadline 25/04/2027'), ['2027-04-25'])

    def test_choose_deadline(self):
        ds = [{'iso': '2026-01-10', 'ctx': 'a'}, {'iso': '2027-02-01', 'ctx': 'b'}]
        self.assertEqual(T.choose_deadline(ds, '2026-11-14')['iso'], '2027-02-01')
        self.assertEqual(T.choose_deadline(ds, '2027-06-01')['iso'], '2027-02-01')

    def test_value(self):
        v = T.find_value('The scholarship is worth up to £10,000 per year. Application fee of $100.', 'uk')
        self.assertEqual(v['display'], 'Up to GBP 10,000 a year')
        self.assertIsNone(T.find_value('Pay an application fee of $120 online.', 'usa'))

    def test_levels_and_intl(self):
        self.assertEqual(T.detect_levels('for undergraduate and master’s students')[0], ['Bachelor', 'Master'])
        self.assertEqual(T.detect_levels('PhD students only'), ([], True))
        self.assertEqual(T.detect_international('open to international students'), 'yes')
        self.assertEqual(T.detect_international('for home students only'), 'no')


class PipelineTests(unittest.TestCase):
    def uni(self):
        return {'slug': 'test-university', 'name': 'Test University', 'country': 'uk', 'web': f'http://127.0.0.1:{PORT["p"]}/'}

    def test_crawl(self):
        import discover
        del HITS[:]
        fx = Fetcher('Universities500Bot/1.0 (test)', delay=0, timeout=5)
        r = discover.crawl_university(self.uni(), fx, '2026-11-14', max_pages=30)
        names = sorted(x['name'] for x in r['records'])
        self.assertIn('Global Excellence Scholarship', names)
        self.assertIn('Alpha Excellence Award', names)
        self.assertIn('Beta Merit Award', names)
        self.assertNotIn('Home Students Bursary', names)      # domestic only
        self.assertNotIn('Doctoral Research Award', names)    # PhD only
        self.assertNotIn('Secret Scholarship', names)         # robots.txt disallows it
        self.assertFalse(any(h.startswith('/private/') for h in HITS), 'must not request disallowed paths')
        g = next(x for x in r['records'] if x['name'] == 'Global Excellence Scholarship')
        self.assertEqual(g['deadline'], '2027-01-15')
        self.assertEqual(g['opens'], '2026-10-01')
        self.assertEqual(g['value']['display'], 'Up to GBP 5,000 a year')
        self.assertEqual(g['levels'], ['Bachelor', 'Master'])
        self.assertTrue(g['applyUrl'].endswith('/apply/global/'))
        self.assertTrue(any('international' in e.lower() for e in g['eligibility']))
        self.assertIn('merit scholarship', g['description'])
        beta = next(x for x in r['records'] if x['name'] == 'Beta Merit Award')
        self.assertEqual(beta['deadline'], '2027-05-01')
        self.assertTrue(r['hub']['url'].endswith('/scholarships/'))
        self.assertLessEqual(r['pages'], 30)

    def test_run_merge_and_gate(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / 'unis.json').write_text(json.dumps([self.uni()]))
            (d / 'src.json').write_text(json.dumps({'programmes': [], 'directories': [], 'thirdParty': []}))
            cmd = [sys.executable, str(HERE / 'run.py'), '--universities', str(d / 'unis.json'), '--sources', str(d / 'src.json'),
                   '--prev', str(d / 's.json'), '--out', str(d / 's.json'), '--report', str(d / 'rep'), '--delay', '0', '--workers', '2', '--today', '2026-11-14']
            r = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            doc = json.loads((d / 's.json').read_text())
            self.assertGreaterEqual(len(doc['items']), 3)
            slugs = [i['slug'] for i in doc['items']]
            self.assertEqual(len(slugs), len(set(slugs)))
            self.assertEqual(doc['universities']['test-university']['status'], 'ok')
            self.assertTrue((d / 'rep' / 'scholarship_report.md').exists())
            # second run keeps slugs stable and marks nothing as new
            first = {i['id']: i['slug'] for i in doc['items']}
            r2 = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
            doc2 = json.loads((d / 's.json').read_text())
            self.assertEqual({i['id']: i['slug'] for i in doc2['items']}, first)
            self.assertEqual(doc2['stats']['added'], 0)
            # a university that is down must not wipe its records
            bad = dict(self.uni(), web='http://127.0.0.1:9/')
            (d / 'unis.json').write_text(json.dumps([bad]))
            r3 = subprocess.run(cmd, capture_output=True, text=True)
            doc3 = json.loads((d / 's.json').read_text()) if r3.returncode == 0 else None
            self.assertTrue(r3.returncode in (0, 3))
            if doc3:
                self.assertEqual(len(doc3['items']), len(doc['items']))
                self.assertEqual(doc3['items'][0]['misses'], 0)

    def test_gate_stops_collapse(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            # 40 old records, each already missed twice. The university is readable and none of them exists any more,
            # so this run would remove all 40. The gate must refuse to write.
            old = [{'id': f'x{i}', 'slug': f's{i}', 'name': f'N{i}', 'provider': 'P', 'providerSlug': 'test-university', 'country': 'uk',
                    'url': f'http://127.0.0.1:{PORT["p"]}/old{i}/', 'origin': 'page', 'hash': 'h', 'misses': 2,
                    'firstSeen': '2026-01-01', 'lastVerified': '2026-01-01', 'lastChanged': '2026-01-01'} for i in range(40)]
            before = json.dumps({'items': old, 'generatedAt': '2026-01-01T00:00:00Z'})
            (d / 's.json').write_text(before)
            (d / 'unis.json').write_text(json.dumps([self.uni()]))
            (d / 'src.json').write_text(json.dumps({}))
            cmd = [sys.executable, str(HERE / 'run.py'), '--universities', str(d / 'unis.json'), '--sources', str(d / 'src.json'),
                   '--prev', str(d / 's.json'), '--out', str(d / 's.json'), '--report', str(d / 'rep'), '--delay', '0', '--today', '2026-11-14']
            r = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
            self.assertEqual((d / 's.json').read_text(), before, 'the data file must be left untouched')
            self.assertIn('Stopped by the sanity check', (d / 'rep' / 'scholarship_report.md').read_text())
            r2 = subprocess.run(cmd + ['--allow-drop'], capture_output=True, text=True)
            self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
