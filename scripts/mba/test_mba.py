#!/usr/bin/env python3
"""Offline tests for the MBA reader: sentences copied from real school pages, a stub school website on localhost, no internet, no AI.
Run: python3 scripts/mba/test_mba.py"""
import importlib.util
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
ROOT = HERE.resolve().parents[1]
for p in (HERE, HERE.parent / 'courses', HERE.parent / 'scholarships'):
    sys.path.insert(0, str(p))
import mbafacts as M  # noqa: E402
import textutil as T  # noqa: E402


def load_by_path(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


B = load_by_path('mba_build_site_data', HERE / 'build_site_data.py')


def S(text):
    return T.sentences(text)


PAGE = """<html><head><title>Oxford MBA</title></head><body>
<header><nav><a href="/about">About</a><a href="/careers/employment-report-2025.pdf">Oxford MBA Employment Report</a></nav></header>
<main><h1>Oxford MBA</h1>
<p>The Oxford MBA is a one-year, full-time programme. The course fee for the 2027-28 programme will be £94,120.</p>
<p>Applicants need at least two years of full-time work experience. The class average is five years of work experience.</p>
<p>All applicants are required to have completed a recognised undergraduate degree.</p>
<p>You must submit a GMAT or GRE score report. We accept IELTS 7.5 overall for English.</p>
<p>The programme starts in September 2027. Round One Deadline: September 15, 2026.</p>
</main></body></html>"""


class Facts(unittest.TestCase):
    def test_experience_minimum(self):
        f = M.find_experience(S('Applicants need at least two years of full-time work experience.'))
        self.assertEqual((f['min'], f['max']), (2, None))

    def test_experience_range(self):
        f = M.find_experience(S('Most students have 3 to 5 years of work experience before they apply.'))
        self.assertEqual((f['min'], f['max']), (3, 5))

    def test_experience_class_average_is_not_a_requirement(self):
        self.assertIsNone(M.find_experience(S('The average class has five years of work experience.')))

    def test_experience_executive(self):
        f = M.find_experience(S('Candidates should have a minimum of 10 years of professional experience.'))
        self.assertEqual(f['min'], 10)

    def test_fee_international_wins(self):
        f = M.find_fee(S('Tuition for international students is £48,500 a year. Home students pay £12,000 a year.'), 'uk')
        self.assertEqual((f['cur'], f['amount']), ('GBP', 48500))

    def test_fee_single_fee_is_labelled(self):
        f = M.find_fee(S('The course fee for the 2027-28 programme will be £94,120.'), 'uk')
        self.assertEqual(f['amount'], 94120)
        self.assertEqual(f['t'], '£94,120 (2027-28)')
        self.assertIn('does not list a separate international fee', f['note'])

    def test_fee_mixed_page_is_left_alone(self):
        self.assertIsNone(M.find_fee(S('Home students pay £9,250. The course fee is £30,000.'), 'uk'))

    def test_fee_small_amount_is_not_tuition(self):
        self.assertIsNone(M.find_fee(S('The application fee is £150.'), 'uk'))

    def test_test_found_and_waived(self):
        self.assertEqual(M.find_test(S('You must submit a GMAT or GRE score report.'))['t'], 'GMAT or GRE')
        self.assertIsNone(M.find_test(S('The GMAT is waived for applicants with a master\'s degree.')))

    def test_english(self):
        self.assertEqual(M.find_english(S('You need IELTS 7.5 overall with no less than 7.0 in each part.'))['ielts'], 7.5)

    def test_start_and_length(self):
        self.assertEqual(M.find_start(S('The programme starts in September 2027.'))['months'], ['Sep'])
        self.assertEqual(M.find_length(S('The programme lasts 12 months, full-time.'))['months'], 12)

    def test_deadlines_keep_the_sentence(self):
        f = M.find_deadlines(S('Round One Deadline: September 15, 2026. Round Two Deadline: January 5, 2027.'))
        self.assertIn('September 15, 2026', f['t'])

    def test_verify_drops_a_value_that_is_not_in_its_sentence(self):
        bad = {'amount': 99999, 'q': 'The fee is £94,120.'}
        self.assertTrue(M.verify('fee', bad))
        self.assertEqual(M.verify('fee', {'amount': 94120, 'q': 'The fee is £94,120.'}), '')
        self.assertTrue(M.verify('exp', {'min': 3, 'q': 'at least two years of work experience'}))
        self.assertTrue(M.verify('english', {'ielts': 7.0, 'q': 'IELTS 7.5 overall'}))
        self.assertEqual(M.verify('english', {'ielts': 7.0, 'q': 'IELTS 7.0 overall'}), '')
        self.assertTrue(M.verify('fee', {'amount': 9412, 'q': 'The fee is £94,120.'}))   # a prefix of the real number is not a match
        self.assertTrue(M.verify('start', {'months': ['Jan'], 'q': 'starts in September'}))

    def test_read_page_end_to_end(self):
        facts, rejected = M.read_page(PAGE, 'https://example.edu/oxford-mba', 'uk')
        self.assertEqual(rejected, [])
        self.assertEqual(facts['fee']['amount'], 94120)
        self.assertEqual(facts['exp']['min'], 2)
        self.assertEqual(facts['test']['t'], 'GMAT or GRE')
        self.assertEqual(facts['english']['ielts'], 7.5)
        self.assertEqual(facts['start']['months'], ['Sep'])
        self.assertTrue(facts['employment']['u'].endswith('employment-report-2025.pdf'))
        for k, f in facts.items():
            if k != 'employment':            # the employment fact's address is the report's own, not this page
                self.assertEqual(f['u'], 'https://example.edu/oxford-mba', k)

    def test_merge_first_page_wins(self):
        a = ({'fee': {'amount': 1, 'u': 'a'}}, [])
        b = ({'fee': {'amount': 2, 'u': 'b'}, 'test': {'t': 'GRE', 'u': 'b'}}, [('x', 'y')])
        facts, rej = M.merge([a, b])
        self.assertEqual((facts['fee']['u'], facts['test']['u']), ('a', 'b'))
        self.assertEqual(rej, [('x', 'y')])


class Build(unittest.TestCase):
    BASE = {'id': 'x', 'readOn': '2026-11-01', 'how': 'hand', 'name': 'X MBA', 'url': 'https://e.edu/x',
            'fee': {'t': '£1', 'amount': 1, 'note': 'From the tuition table on the page'}, 'exp': {'t': 'At least 2 years', 'min': 2},
            'test': None, 'employment': None}

    def test_reader_replaces_only_what_it_finds(self):
        read = {'readOn': '2026-11-18', 'facts': {'fee': {'t': '£2', 'amount': 2, 'u': 'https://e.edu/fees'}, 'test': {'t': 'GMAT', 'u': 'https://e.edu/apply'}}}
        r = B.build_record(self.BASE, read)
        self.assertEqual(r['fee']['amount'], 2)
        self.assertEqual(r['fee']['note'], 'From the tuition table on the page')   # the note about how the fee is listed stays
        self.assertEqual(r['feeUrl'], 'https://e.edu/fees')
        self.assertEqual(r['exp']['min'], 2)                                       # not found by the program: stays as read by hand
        self.assertEqual(r['provenance']['exp'], {'by': 'hand', 'on': '2026-11-01'})
        self.assertEqual(r['provenance']['fee'], {'by': 'program', 'on': '2026-11-18'})
        self.assertEqual(r['provenance']['test'], {'by': 'program', 'on': '2026-11-18'})
        self.assertEqual((r['how'], r['readOn']), ('both', '2026-11-18'))

    def test_no_reader_output_leaves_the_hand_record(self):
        r = B.build_record(self.BASE, {})
        self.assertEqual(r['how'], 'hand')
        self.assertEqual(r['fee']['amount'], 1)
        self.assertEqual(r['readOn'], '2026-11-01')

    def test_a_fact_without_a_source_page_is_ignored(self):
        r = B.build_record(self.BASE, {'readOn': '2026-11-18', 'facts': {'fee': {'t': '£9', 'amount': 9}}})
        self.assertEqual(r['fee']['amount'], 1)

    def test_site_data_has_sources_and_no_ranking(self):
        # the site data is what build_site_data makes from the hand-read base (plus any reader output committed under data/mba/read)
        doc = json.loads((ROOT / 'src' / 'data' / 'mba.json').read_text(encoding='utf-8'))
        self.assertTrue(doc['items'])
        for m in doc['items']:
            self.assertTrue(m['url'].startswith('https://'), m['id'])
            self.assertTrue(m['readOn'], m['id'])
            for k in ('length', 'fee', 'exp', 'degree', 'test', 'english', 'start', 'deadlines', 'employment'):
                f = m.get(k)
                if f and k not in ('length', 'start'):
                    self.assertTrue(f.get('u'), f'{m["id"]} {k} has no source page')
        self.assertNotIn('rank', json.dumps(doc).lower().replace('frank', ''))


class Register(unittest.TestCase):
    reg = json.loads((ROOT / 'data' / 'mba_sources.json').read_text(encoding='utf-8'))
    pilot = {r['id']: r for r in json.loads((HERE / 'pilot.json').read_text(encoding='utf-8'))['items']}

    def test_every_destination_is_in_a_wave_once(self):
        flat = [c for w in self.reg['waves'].values() for c in w]
        self.assertEqual(len(flat), len(set(flat)))
        self.assertEqual(len(flat), 14)

    def test_programmes_match_the_hand_read_base(self):
        ids = {p['id'] for p in self.reg['programmes']}
        self.assertEqual(ids, set(self.pilot))
        for p in self.reg['programmes']:
            for u in p['pages']:
                self.assertTrue(u.startswith('https://'), u)
            if not p['pages']:
                self.assertTrue(p.get('note'), f"{p['id']} has no pages and no reason")

    def test_candidates_are_proposals_with_a_domain_and_no_rank(self):
        self.assertTrue(self.reg['candidates'])
        waves = self.reg['waves']
        for c in self.reg['candidates']:
            self.assertTrue(c['domain'] and c['school'], c)
            self.assertIn(c['country'], waves[str(c['wave'])], c)
        self.assertNotIn('rank', json.dumps(self.reg).lower().replace('ranking is stored', ''))


# ---------------- a stub school website ----------------
PAGES = {
    '/robots.txt': (200, 'text/plain', 'User-agent: *\nDisallow: /private/\n'),
    '/mba': (200, 'text/html', PAGE),
    '/mba/fees': (200, 'text/html', '<html><body><main><p>Tuition for international students is £48,500 a year.</p></main></body></html>'),
    '/mba/blocked': (403, 'text/html', '<html><body>Access denied</body></html>'),
    '/private/page': (200, 'text/html', '<html><body><main><p>You must submit a GMAT score.</p></main></body></html>'),
}
HITS = []


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        HITS.append(self.path)
        status, ctype, body = PAGES.get(self.path, (404, 'text/html', 'not found'))
        b = body.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', ctype + '; charset=utf-8')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, *a):
        pass


class Runner(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(('127.0.0.1', 0), H)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def run_reader(self, tmp, pages, force=False, pilot=None):
        base = f'http://127.0.0.1:{self.port}'
        reg = Path(tmp) / 'reg.json'
        reg.write_text(json.dumps({'programmes': [{'id': 'stub-mba', 'pages': [base + p for p in pages]}]}))
        pil = Path(tmp) / 'pilot.json'
        pil.write_text(json.dumps(pilot or {'items': [{'id': 'stub-mba', 'country': 'uk', 'fee': {'t': '£94,120', 'amount': 94120}, 'exp': {'t': 'At least 3 years', 'min': 3}}]}))
        cmd = [sys.executable, str(HERE / 'read.py'), '--register', str(reg), '--pilot', str(pil), '--out', str(Path(tmp) / 'out'), '--delay', '0', '--allow-http-local']
        if force:
            cmd.append('--force')
        env = dict(os.environ)
        env.pop('GITHUB_STEP_SUMMARY', None)
        return subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=120)

    def test_reads_skips_unchanged_and_never_goes_around_a_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self.run_reader(tmp, ['/mba', '/mba/fees', '/mba/blocked', '/private/page'])
            self.assertEqual(r.returncode, 0, r.stderr)
            doc = json.loads((Path(tmp) / 'out' / 'stub-mba.json').read_text(encoding='utf-8'))
            status = {p['url'].rsplit(':', 1)[1].split('/', 1)[1]: p['status'] for p in doc['pages']}
            self.assertEqual(status['mba'], 'ok')
            self.assertTrue(status['mba/blocked'].startswith('refused (HTTP 403)'))
            self.assertTrue(status['private/page'].startswith('robots-blocked'))
            self.assertEqual(doc['facts']['exp']['min'], 2)
            self.assertEqual(doc['facts']['fee']['amount'], 94120)          # the first page wins; the second page's fee does not override it
            self.assertNotIn('test', {k for k in doc['facts'] if doc['facts'][k]['u'].endswith('/private/page')})
            self.assertEqual(doc['diff']['fee'], 'same')
            self.assertEqual(doc['diff']['exp'], 'differs')                 # the hand base says 3, the page says 2: the report must show it
            self.assertEqual(doc['diff']['test'], 'only read by program')
            self.assertIn('/mba/blocked', HITS)                             # asked once ...
            self.assertEqual(HITS.count('/mba/blocked'), 1)                 # ... and not asked again by another route
            self.assertNotIn('/private/page', HITS)                         # robots.txt said no, so it was never requested
            before = (Path(tmp) / 'out' / 'stub-mba.json').read_text(encoding='utf-8')
            r2 = self.run_reader(tmp, ['/mba', '/mba/fees', '/mba/blocked', '/private/page'])
            self.assertIn('unchanged', r2.stdout)
            self.assertEqual(before, (Path(tmp) / 'out' / 'stub-mba.json').read_text(encoding='utf-8'))
            r3 = self.run_reader(tmp, ['/mba', '/mba/fees', '/mba/blocked', '/private/page'], force=True)
            self.assertIn('| read |', r3.stdout)

    def test_unreachable_programme_keeps_what_we_had(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.run_reader(tmp, ['/mba'])
            keep = (Path(tmp) / 'out' / 'stub-mba.json').read_text(encoding='utf-8')
            r = self.run_reader(tmp, ['/mba/blocked'])
            self.assertIn('not read', r.stdout)
            self.assertEqual(keep, (Path(tmp) / 'out' / 'stub-mba.json').read_text(encoding='utf-8'))

    def test_reader_has_no_ai(self):
        for f in HERE.glob('*.py'):
            if f.name == 'test_mba.py':
                continue
            text = f.read_text(encoding='utf-8').lower()
            for bad in ('anthropic', 'api_key', 'openai', 'claude-'):
                self.assertNotIn(bad, text.replace('no ai and no api key', ''), f'{f.name} mentions {bad}')


if __name__ == '__main__':
    unittest.main(verbosity=1)
