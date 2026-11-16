#!/usr/bin/env python3
"""Offline tests: a stub university website on localhost, no internet, no AI.
Run: python3 scripts/scholarships/test_scholarships.py"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import details as D  # noqa: E402
import official as O  # noqa: E402
import extract as X  # noqa: E402
import quality as Q  # noqa: E402
import textutil as T  # noqa: E402
from fetcher import Fetcher  # noqa: E402

PORT = {}
HITS = []
EXTRA = {}          # path -> (content type, body[, status]); a test adds pages here and clears them afterwards
ROBOTS = {'status': None}   # when set, /robots.txt answers with this status code and no rules


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
        if self.path == '/robots.txt' and ROBOTS['status']:
            self.send_response(ROBOTS['status'])
            if ROBOTS['status'] == 503:
                self.send_header('Retry-After', '120')
            self.end_headers()
            return
        pg = EXTRA.get(self.path) or pages().get(self.path)
        if not pg:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(pg[2] if len(pg) > 2 else 200)
        if len(pg) > 2 and pg[2] == 503:
            self.send_header('Retry-After', '120')   # the reader gives up on the host at once instead of waiting and retrying
        self.send_header('Content-Type', pg[0] + '; charset=utf-8')
        self.end_headers()
        self.wfile.write(pg[1].encode())


def setUpModule():
    # The tests run the reader on purpose with bad data. Keep their reports out of the real run's summary page.
    os.environ.pop('GITHUB_STEP_SUMMARY', None)
    srv = HTTPServer(('127.0.0.1', 0), H)
    PORT['p'] = srv.server_address[1]
    PORT['srv'] = srv
    threading.Thread(target=srv.serve_forever, daemon=True).start()


def tearDownModule():
    PORT['srv'].shutdown()


class QualityTests(unittest.TestCase):
    def bad(self, name):
        return Q.name_problem(name, '2026-11-14')

    def test_headings_and_cells_are_not_names(self):
        for n in ['Find a scholarship', 'Scholarships', 'Fees and scholarships', 'International scholarships', 'All programs',
                  '£12,600', '$2,000 (non-renewable)', 'January', 'Applying for scholarships', 'Scholarship eligibility']:
            self.assertIsNotNone(self.bad(n), n)

    def test_real_names_pass(self):
        for n in ['Chevening Scholarships', 'International Merit Scholarship', 'Global Leaders Scholarship', "Dean's Award",
                  'Adelaide Partner Award (10%)', 'Study in Canada Scholarships', 'UM NL Global Studies Scholarship']:
            self.assertIsNone(self.bad(n), n)

    def test_wrong_kind_of_record(self):
        for n in ['PhD Scholarships', 'Staff Scholarships', 'Alex Rodgers Travel Grant', 'New Colombo Plan Scholarship',
                  'Bruce Liley Prize', 'Eiffel Scholarship 2024 call for applications is launched!', 'Undergraduate Home Excellence Scholarship']:
            self.assertIsNotNone(self.bad(n), n)

    def test_old_year_but_not_current(self):
        self.assertEqual(self.bad('Eiffel Excellence scholarship 2025'), 'old-year')
        self.assertIsNone(self.bad('Eiffel Excellence scholarship 2027'))

    def test_pages_for_enrolled_or_outbound(self):
        self.assertIsNotNone(Q.url_problem('https://x.edu/scholarships/domestic/bachelors-honours/study-overseas.html'))
        self.assertIsNotNone(Q.url_problem('https://x.edu/scholarships/dom/some-bursary/'))
        self.assertIsNone(Q.url_problem('https://x.edu/international/students-from-abroad/scholarships/study-in-canada'))

    def test_review_list_wins(self):
        self.assertEqual(Q.url_problem('https://www.purdue.edu/niso/scholarship/additional/international.html'), 'excluded-by-review')

    def test_old_records_are_cleaned(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / 's.json'
            f.write_text(json.dumps({'stats': {'items': 2}, 'universities': {'a': {'count': 2}}, 'items': [
                {'name': 'Find a scholarship', 'origin': 'page', 'providerSlug': 'a', 'url': 'https://x.edu/a'},
                {'name': 'Chevening Scholarships', 'origin': 'official', 'providerSlug': None, 'url': 'https://chevening.org/'}]}))
            kept, dropped = Q.clean_file(f, '2026-11-14')
            self.assertEqual([k['name'] for k in kept], ['Chevening Scholarships'])
            doc = json.loads(f.read_text())
            self.assertEqual((doc['stats']['items'], doc['universities']['a']['count']), (1, 0))


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
            old = [{'id': f'x{i}', 'slug': f's{i}', 'name': f'Example Excellence Scholarship {i}', 'provider': 'P', 'providerSlug': 'test-university', 'country': 'uk',
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


SEED_PATH = '/hidden/overseas-funding/'


def seed_pages():
    """A funding page that nothing on the site links to, a detail page that never says "international" itself,
    and a home-students-only page that must stay out even when the seed page links to it."""
    return {
        SEED_PATH: ('text/html', page('Funding for overseas students', '''
            <p>Funding for overseas students starting an undergraduate or master course at Test University.</p>
            <table><tr><th>Award</th><th>Amount</th><th>Deadline</th></tr>
            <tr><td>Zeta Overseas Bursary</td><td>£1,500</td><td>20 May 2027</td></tr></table>
            <ul><li><a href="/hidden/awards/kappa-scholarship/">Kappa Scholarship</a></li>
            <li><a href="/scholarships/home-students-bursary/">Home Students Bursary</a></li></ul>''' + '<p>More text so the page is long enough to read. </p>' * 8)),
        '/hidden/awards/kappa-scholarship/': ('text/html', page('Kappa Scholarship', '''
            <p>The Kappa Scholarship is worth £3,000 and is awarded for undergraduate study. Applications close on 1 June 2027.</p>
            <p>Apply online before the closing date to be considered for the scholarship.</p>''' + '<p>Further notes for applicants. </p>' * 6)),
    }


class Coverage(unittest.TestCase):
    """What the reader does to reach more universities: pages checked by hand, guessed paths, robots.txt answers."""

    def setUp(self):
        EXTRA.clear()
        ROBOTS['status'] = None
        del HITS[:]

    def tearDown(self):
        EXTRA.clear()
        ROBOTS['status'] = None

    def uni(self):
        return {'slug': 'test-university', 'name': 'Test University', 'country': 'uk', 'web': f'http://127.0.0.1:{PORT["p"]}/'}

    def fx(self, **kw):
        return Fetcher('Universities500Bot/1.0 (test)', delay=0, timeout=5, **kw)

    def crawl(self, seeds=None, **kw):
        import discover
        return discover.crawl_university(self.uni(), self.fx(**kw), '2026-11-14', max_pages=40, seeds=seeds)

    def seed_url(self):
        return f'http://127.0.0.1:{PORT["p"]}{SEED_PATH}'

    def test_seed_page_becomes_the_hub_and_its_links_inherit_international(self):
        EXTRA.update(seed_pages())
        r = self.crawl(seeds=[self.seed_url()])
        names = sorted(x['name'] for x in r['records'])
        self.assertIn('Zeta Overseas Bursary', names)
        self.assertIn('Kappa Scholarship', names)           # never says "international", but it is linked from the overseas page
        self.assertNotIn('Home Students Bursary', names)    # an explicit "home students only" still wins
        self.assertEqual(r['hub']['url'], self.seed_url())
        self.assertTrue(r['hub']['supplied'])
        self.assertEqual(r['seeds'][self.seed_url()], 'ok')

    def test_without_the_seed_the_hidden_page_is_never_found(self):
        EXTRA.update(seed_pages())
        r = self.crawl()
        self.assertNotIn('Kappa Scholarship', [x['name'] for x in r['records']])
        self.assertFalse(r['hub'].get('supplied'))

    def test_seed_that_fails_is_reported_not_hidden(self):
        r = self.crawl(seeds=[f'http://127.0.0.1:{PORT["p"]}/gone/'])
        self.assertTrue(r['seeds'][f'http://127.0.0.1:{PORT["p"]}/gone/'].startswith('failed'), r['seeds'])
        self.assertTrue(r['records'], 'the rest of the site is still read')

    def test_seed_that_does_not_mention_scholarships_is_not_a_hub(self):
        EXTRA['/hidden/about-us/'] = ('text/html', page('About us', '<p>We are a university with a long history of teaching and research.</p>' * 10))
        u = f'http://127.0.0.1:{PORT["p"]}/hidden/about-us/'
        r = self.crawl(seeds=[u])
        self.assertEqual(r['seeds'][u], 'loads, but does not mention scholarships')
        self.assertNotEqual(r['hub']['url'], u)

    def test_a_seed_still_obeys_robots(self):
        u = f'http://127.0.0.1:{PORT["p"]}/private/secret-scholarship/'
        r = self.crawl(seeds=[u])
        self.assertEqual(r['seeds'][u], 'robots-disallow')
        self.assertFalse(any(h.startswith('/private/') for h in HITS))

    def test_usual_paths_are_tried_when_the_site_gives_no_clue(self):
        EXTRA['/'] = ('text/html', page('Test University', '<p>Welcome to Test University, a place to study.</p>' * 10))
        EXTRA['/sitemap.xml'] = ('application/xml', '<?xml version="1.0"?><urlset></urlset>')
        r = self.crawl()
        self.assertEqual(r['reasons']['guessed-paths'], 1)
        self.assertTrue(r['hub']['url'].endswith('/scholarships/'), r['hub'])
        self.assertIn('/scholarships/', HITS)

    def test_robots_403_is_not_a_ban_unless_strict(self):
        ROBOTS['status'] = 403
        r = self.crawl()
        self.assertEqual(r['status'], 'ok')
        self.assertTrue(r['records'])
        r = self.crawl(strict_forbidden=True)
        self.assertEqual((r['status'], r['robotsReason']), ('robots', 'forbidden'))

    def test_robots_404_means_no_rules(self):
        ROBOTS['status'] = 404
        self.assertEqual(self.crawl()['status'], 'ok')

    def test_robots_server_error_is_treated_as_closed(self):
        ROBOTS['status'] = 503
        r = self.crawl()
        self.assertEqual((r['status'], r['robotsReason']), ('robots', 'unreachable'))
        self.assertEqual(r['records'], [])

    def test_explicit_disallow_is_reported_as_such(self):
        EXTRA['/robots.txt'] = ('text/plain', 'User-agent: *\nDisallow: /\n')
        r = self.crawl()
        self.assertEqual((r['status'], r['robotsReason']), ('robots', 'disallow'))
        self.assertFalse(any(h not in ('/robots.txt',) for h in HITS), 'nothing but robots.txt may be requested')

    def test_explicit_disallow_also_stops_the_supplied_pages(self):
        EXTRA['/robots.txt'] = ('text/plain', 'User-agent: *\nDisallow: /\n')
        EXTRA.update(seed_pages())
        r = self.crawl(seeds=[self.seed_url()])
        self.assertEqual(r['records'], [])
        self.assertEqual(r['seeds'][self.seed_url()], 'robots-disallow')
        self.assertEqual(r['status'], 'robots')

    def test_home_page_down_but_supplied_page_readable(self):
        EXTRA['/'] = ('text/html', 'not found', 404)
        EXTRA.update(seed_pages())
        r = self.crawl(seeds=[self.seed_url()])
        self.assertEqual(r['status'], 'ok')
        self.assertTrue(r.get('partial'), 'what we read is partial, so it must not remove records we did not reach')
        self.assertIn('Zeta Overseas Bursary', [x['name'] for x in r['records']])

    def test_run_writes_supplied_hub_and_reports_the_seed(self):
        EXTRA.update(seed_pages())
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / 'unis.json').write_text(json.dumps([self.uni()]))
            (d / 'src.json').write_text(json.dumps({}))
            (d / 'seeds.json').write_text(json.dumps({'checked': '2026-11-15', 'seeds': {'test-university': {'name': 'Test University', 'urls': [self.seed_url()]}}}))
            cmd = [sys.executable, str(HERE / 'run.py'), '--universities', str(d / 'unis.json'), '--sources', str(d / 'src.json'), '--seeds', str(d / 'seeds.json'),
                   '--prev', str(d / 's.json'), '--out', str(d / 's.json'), '--report', str(d / 'rep'), '--delay', '0', '--workers', '2', '--today', '2026-11-14']
            r = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            doc = json.loads((d / 's.json').read_text())
            u = doc['universities']['test-university']
            self.assertEqual((u['hubUrl'], u['hubSource']), (self.seed_url(), 'supplied'))
            self.assertIn('Kappa Scholarship', [i['name'] for i in doc['items']])
            rep = (d / 'rep' / 'scholarship_report.md').read_text()
            self.assertIn('Pages checked by hand', rep)
            self.assertIn(SEED_PATH, rep)
            self.assertIn('robots_reason', (d / 'rep' / 'universities.csv').read_text().splitlines()[0])


class India(unittest.TestCase):
    """The page's own sentence, copied. Never a label, and never a guess from a different meaning of "Indian"."""

    def test_sentences_that_name_india(self):
        for s in ['Students from India, Nepal and Sri Lanka are eligible to apply for this scholarship.',
                  'This award is open to Indian students who hold an offer for a full-time course.',
                  'Applicants from India must also submit a verified English test score.']:
            self.assertEqual(D.find_india(s), s)

    def test_not_india(self):
        for s in ['Funding for American Indian students living on reservations is available from the state.',
                  'The Indian Ocean research scholarship is awarded to marine biology students.',
                  'There is a long history of Indian Affairs policy in this department of the university.',
                  'India is a large country and we like to talk about it on this page of the website.',
                  'The Indian Act is studied in the law school and appears in the second year of the course.']:
            self.assertIsNone(D.find_india(s), s)

    def test_nothing_without_the_word(self):
        self.assertIsNone(D.find_india('International students are eligible to apply.'))
        self.assertIsNone(D.find_india(''))
        self.assertIsNone(D.find_india(None))

    def test_prefers_the_sentence_about_who_can_apply(self):
        t = 'Our campus has a famous India Society and a cricket ground. Students from India are eligible to apply for this scholarship.'
        self.assertEqual(D.find_india(t), 'Students from India are eligible to apply for this scholarship.')

    def test_long_sentences_are_trimmed_around_the_word(self):
        countries = ', '.join(f'Country{i}' for i in range(60))
        t = f'Applicants who are citizens of any of the following countries are eligible to apply: {countries}, India, Nepal, {countries}.'
        got = D.find_india(t)
        self.assertIn('India', got)
        self.assertLessEqual(len(got), 330)
        self.assertTrue(got.startswith('Applicants who are citizens'))

    def test_record_carries_it_and_the_hash_notices_a_change(self):
        kw = dict(name='Example Excellence Scholarship', provider='P', provider_slug='p', provider_type='university', country='uk',
                  url='https://example.edu/s/', today='2026-11-14', origin='page')
        a = X.make_record(text='Students from India are eligible to apply for this scholarship. Apply online before 1 May 2027.', **kw)
        self.assertEqual(a['india'], 'Students from India are eligible to apply for this scholarship.')
        b = X.make_record(text='Apply online before 1 May 2027.', **kw)
        self.assertNotIn('india', b)
        self.assertNotEqual(a['hash'], b['hash'])


class Details(unittest.TestCase):
    """The extra facts come only from sentences on the page. Anything unclear stays empty."""

    def test_awards(self):
        self.assertEqual(D.find_awards('Up to 10 scholarships are available each year for international students.'), {'n': 10, 'upTo': True})
        self.assertEqual(D.find_awards('We offer five awards annually.'), {'n': 5, 'upTo': False})
        self.assertIsNone(D.find_awards('The 2026 Awards ceremony takes place in May.'))
        self.assertIsNone(D.find_awards('A $5,000 scholarship is available each year.'))

    def test_duration(self):
        self.assertEqual(D.find_duration('The scholarship is awarded for the duration of the degree programme.'), 'Full length of the course')
        self.assertEqual(D.find_duration('The scholarship is for up to 4 years of undergraduate study.'), 'Up to 4 years')
        self.assertEqual(D.find_duration('This is a one-year scholarship for master\'s students.'), '1 year')
        self.assertIsNone(D.find_duration('The course runs for 3 years.'))

    def test_covers_skips_negations(self):
        self.assertEqual(D.find_covers('The award covers tuition fees, a living allowance and return airfare. It does not cover visa fees.'),
                         ['Tuition', 'Living costs', 'Travel'])
        self.assertEqual(D.find_covers('The scholarship does not cover living costs.'), [])

    def test_covers_from_a_list(self):
        lines = ['What it covers', 'Full tuition fees', 'A monthly living stipend', 'Health insurance', 'Apply now']
        self.assertEqual(D.find_covers('', lines), ['Tuition', 'Living costs', 'Health insurance'])

    def test_apply_mode(self):
        self.assertEqual(D.find_apply_mode('Students are automatically considered for this scholarship when they apply for admission.'), 'automatic')
        self.assertEqual(D.find_apply_mode('Apply online before 31 March 2027 to be considered for the scholarship.'), 'application')
        self.assertIsNone(D.find_apply_mode('A scholarship for students.'))

    def test_record_carries_the_new_fields_and_hash(self):
        text = 'Up to 3 scholarships are available each year. The award covers tuition fees. Apply online before 31 March 2027.'
        kw = dict(name='Example Excellence Scholarship', provider='P', provider_slug='p', provider_type='university', country='uk',
                  url='https://example.edu/s/', today='2026-11-14', origin='page')
        a = X.make_record(text=text, **kw)
        self.assertEqual(a['awards'], {'n': 3, 'upTo': True})
        self.assertEqual(a['covers'], ['Tuition'])
        self.assertEqual(a['applyMode'], 'application')
        b = X.make_record(text=text.replace('Up to 3', 'Up to 4'), **kw)
        self.assertNotEqual(a['hash'], b['hash'], 'a change in the new fields must count as a change')

    def test_missed_sentences_are_only_for_the_log(self):
        m = D.missed('Applications close on 5 June each year. Awards of $4,000 are made.', True, True)
        self.assertIn('deadline', m)
        self.assertIn('value', m)
        self.assertEqual(D.missed('Nothing here.', True, True), {})
        self.assertEqual(D.missed('Applications close on 5 June each year.', False, False), {})

    def test_programme_options(self):
        """A programme can list several accepted names, carry a university slug, and gets the new fields."""
        class Res:
            ok = True
            ctype = 'text/html'
            final_url = 'https://example.org/p/'
            error = None
            status = 200
            text = ('<html><head><title>NL Scholarship | Example</title></head><body><main><h1>NL Scholarship</h1>'
                    '<p>The scholarship covers tuition fees and a living allowance. It is awarded for the first year only.</p>'
                    '<p>Apply online before 1 May 2027.</p></main></body></html>')

        class Fx:
            def get(self, url):
                return Res()
        src = {'programmes': [{'id': 'x', 'name': 'Example Programme', 'provider': 'Example University', 'providerSlug': 'example-university',
                               'providerType': 'university', 'country': 'canada', 'levels': ['Bachelor'], 'urls': ['https://example.org/p/'],
                               'expect': ['holland scholarship', 'nl scholarship']}]}
        recs, report = O.read_programmes(src, Fx(), '2026-11-14')
        self.assertEqual(len(recs), 1, report)
        r = recs[0]
        self.assertEqual((r['providerSlug'], r['providerType'], r['origin']), ('example-university', 'university', 'official'))
        self.assertEqual(r['covers'], ['Tuition', 'Living costs'])
        self.assertEqual(r['duration'], 'First year only')
        src['programmes'][0]['expect'] = 'something else'
        recs, report = O.read_programmes(src, Fx(), '2026-11-14')
        self.assertEqual(recs, [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
