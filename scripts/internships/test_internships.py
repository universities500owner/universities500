#!/usr/bin/env python3
"""Offline tests: stub job-board feeds on localhost, no internet, no AI.
Run: python3 scripts/internships/test_internships.py"""
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import places as P  # noqa: E402
import run as R  # noqa: E402
import sources as S  # noqa: E402
import titles as T  # noqa: E402
from fetcher import Fetcher  # noqa: E402

PORT = {}
STATE = {'lever_down': False}


def feeds():
    return {
        '/v1/boards/acme/jobs': {'jobs': [
            {'title': 'Software Engineer Intern', 'location': {'name': 'Sydney, Australia'}, 'absolute_url': 'https://boards.example/acme/1', 'first_published': '2026-11-10T01:00:00Z'},
            {'title': 'Internal Auditor', 'location': {'name': 'London, United Kingdom'}, 'absolute_url': 'https://boards.example/acme/2'},
            {'title': 'Marketing Intern', 'location': {'name': 'Remote - US'}, 'absolute_url': 'https://boards.example/acme/3'},
            {'title': 'Data Science Intern', 'location': {'name': 'London or New York'}, 'absolute_url': 'https://boards.example/acme/4'},
            {'title': 'Research Intern (PhD)', 'location': {'name': 'Dublin, Ireland'}, 'absolute_url': 'https://boards.example/acme/5'},
            {'title': 'Design Intern', 'location': {'name': 'Narnia'}, 'absolute_url': 'https://boards.example/acme/6'},
        ]},
        '/v0/postings/leverco': [
            {'text': 'Product Design Co-op', 'categories': {'location': 'Toronto, ON', 'allLocations': ['Toronto, ON']}, 'hostedUrl': 'https://jobs.example/leverco/a', 'createdAt': 1762732800000},
            {'text': 'Analyst', 'categories': {'location': 'Singapore', 'commitment': 'Intern'}, 'hostedUrl': 'https://jobs.example/leverco/b', 'createdAt': 1762732800000},
            {'text': 'Senior Analyst', 'categories': {'location': 'Singapore', 'commitment': 'Full-time'}, 'hostedUrl': 'https://jobs.example/leverco/c'},
        ],
        '/posting-api/job-board/ashbyco': {'jobs': [
            {'title': 'Associate', 'location': 'Berlin', 'employmentType': 'Intern', 'jobUrl': 'https://ashby.example/ashbyco/1', 'publishedAt': '2026-11-01T00:00:00Z'},
            {'title': 'Praktikum Finance', 'location': 'Munich, Germany', 'secondaryLocations': [{'location': 'Vienna, Austria'}], 'jobUrl': 'https://ashby.example/ashbyco/2'},
            {'title': 'Intern, Hidden', 'location': 'Paris', 'isListed': False, 'jobUrl': 'https://ashby.example/ashbyco/3'},
        ]},
        '/v1/companies/srco/postings': {'totalFound': 2, 'content': [
            {'id': '111', 'name': 'Finance Intern', 'location': {'city': 'Melbourne', 'country': 'au'}, 'company': {'identifier': 'SrCo'}, 'releasedDate': '2026-11-02T00:00:00Z'},
            {'id': '222', 'name': 'Trainee', 'location': {'city': 'Kuala Lumpur', 'country': 'my'}, 'company': {'identifier': 'SrCo'}, 'experienceLevel': {'id': 'internship', 'label': 'Internship'}},
        ]},
        '/api/v1/widget/accounts/wkco': {'name': 'WkCo', 'jobs': [
            {'title': 'Summer Intern', 'city': 'Dubai', 'country': 'United Arab Emirates', 'url': 'https://apply.example/wkco/x', 'published_on': '2026-11-05'},
            {'title': 'Engineer', 'city': 'Dubai', 'country': 'United Arab Emirates', 'url': 'https://apply.example/wkco/y'},
        ]},
        '/search': {'hits': [
            {'id': 'j1', 'headline': 'Praktikant ekonomi', 'employer': {'name': 'Svensk AB'}, 'workplace_address': {'municipality': 'Stockholm', 'country': 'Sverige'}, 'webpage_url': 'https://arbetsformedlingen.example/ad/j1', 'publication_date': '2026-11-09T00:00:00'},
            {'id': 'j2', 'headline': 'Sjuksköterska', 'employer': {'name': 'Vård AB'}, 'workplace_address': {'municipality': 'Lund', 'country': 'Sverige'}, 'webpage_url': 'https://arbetsformedlingen.example/ad/j2'},
        ]},
    }


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def reply(self, code, body=None, ctype='application/json'):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.end_headers()
        if body is not None:
            self.wfile.write(body if isinstance(body, bytes) else json.dumps(body).encode())

    def do_GET(self):
        path = self.path.split('?')[0]
        if path == '/robots.txt':
            return self.reply(200, b'User-agent: *\nDisallow: /posting-api/job-board/blockedco\n', 'text/plain')
        if path == '/api/job-board-api':
            page = int(self.path.split('page=')[1].split('&')[0]) if 'page=' in self.path else 1
            data = {1: [{'title': 'Werkstudent Marketing', 'company_name': 'Berliner GmbH', 'location': 'Berlin', 'url': 'https://www.arbeitnow.example/jobs/1', 'job_types': [], 'created_at': 1762732800},
                        {'title': 'Senior Developer', 'company_name': 'Berliner GmbH', 'location': 'Berlin', 'url': 'https://www.arbeitnow.example/jobs/2', 'job_types': []}],
                    2: [{'title': 'Business Analyst', 'company_name': 'Hamburg AG', 'location': 'Hamburg', 'url': 'https://www.arbeitnow.example/jobs/3', 'job_types': ['Internship']}]}.get(page, [])
            return self.reply(200, {'data': data, 'links': {'next': 'x' if page == 1 else None}})
        if path.startswith('/v0/postings/') and STATE['lever_down']:
            return self.reply(500, b'oops')
        if path.startswith('/v0/postings/leverco'):
            return self.reply(200, feeds()[path])
        f = feeds()
        if path in f:
            return self.reply(200, f[path])
        self.reply(404, b'{}')


def setUpModule():
    os.environ.pop('GITHUB_STEP_SUMMARY', None)  # test reports must not land in a real run's summary page
    srv = HTTPServer(('127.0.0.1', 0), H)
    PORT['srv'] = srv
    base = f'http://127.0.0.1:{srv.server_address[1]}'
    PORT['base'] = base
    for k in S.BASES:
        S.BASES[k] = base
    threading.Thread(target=srv.serve_forever, daemon=True).start()


def tearDownModule():
    PORT['srv'].shutdown()


def fx():
    return Fetcher('TestBot/1.0', delay=0.0, allow_http_local=True)


class TitleTests(unittest.TestCase):
    def test_matches(self):
        for t, kind in [('Software Engineering Intern', 'Internship'), ('Co-op Software Developer', 'Co-op'), ('Industrial Placement Student', 'Placement'),
                        ('Werkstudent Marketing', 'Working student'), ('Praktikum Data Science', 'Internship'), ('Sommarpraktik Ekonomi', 'Internship')]:
            self.assertEqual(T.classify(t), kind, t)

    def test_rejects(self):
        for t in ['Internal Auditor', 'International Sales Manager', 'Internship Program Manager', 'Placement Coordinator', 'Summer 2027 Intern - ML (PhD)',
                  'Staging Engineer', 'High School Intern', 'Senior Data Analyst']:
            self.assertIsNone(T.classify(t), t)

    def test_pupils_apprentices_and_student_workers_are_not_ours(self):
        self.assertIsNone(T.classify('Schülerpraktikant (m/w/d)'))
        self.assertEqual(T.classify('Pflichtpraktikum / Schülerpraktikum Social Media'), 'Internship')
        self.assertIsNone(T.classify('Product Manager Apprentice', 'france', True))  # the employer's flag does not rescue an apprenticeship
        self.assertEqual(T.classify('Brand Design Intern or Apprentice'), 'Internship')
        self.assertIsNone(T.classify('Contract Student Worker: Analyst'))

    def test_swedish_intern_means_internal(self):
        for t in ['Kommunikatör - intern kommunikation', 'Intern tekniker till Bilbolaget i Kiruna', 'Veterinär blandad praktik',
                  'Tandhygienist till liten och trivsam praktik', 'Samordnare för praktik och arbetsplats lärande']:
            self.assertIsNone(T.classify(t, 'sweden'), t)
        for t in ['HR Intern', 'Internship in Human Resources', 'Praktikant inom IT', 'Praktik inom försäljning på Aventi!']:
            self.assertEqual(T.classify(t, 'sweden'), 'Internship', t)

    def test_stage_only_in_france_and_netherlands(self):
        self.assertEqual(T.classify('Stage - Marketing', 'france'), 'Internship')
        self.assertIsNone(T.classify('Stage - Marketing', 'usa'))
        self.assertIsNone(T.classify('Stage Manager', 'france'))

    def test_structured_flag(self):
        self.assertIsNone(T.classify('Associate'))
        self.assertEqual(T.classify('Associate', None, T.structured_intern('Intern')), 'Internship')
        self.assertFalse(T.structured_intern('Full-time'))


class PlaceTests(unittest.TestCase):
    def test_california_and_dc(self):
        self.assertEqual(P.resolve('Foster City, CA'), [('Foster City', 'usa')])
        self.assertEqual(P.resolve('Toronto, CA'), [('Toronto', 'canada')])
        self.assertEqual(P.resolve('Washington, D.C.'), [('Washington, D.C.', 'usa')])
        self.assertEqual(P.resolve('Norderstedt'), [('Norderstedt', 'germany')])

    def test_city_noise_is_cut_to_the_known_city(self):
        self.assertEqual(P.resolve('9th arrondissement of Paris'), [('Paris', 'france')])
        self.assertEqual(P.resolve('The Italian Shot Maxvorstadt München'), [('München', 'germany')])
        self.assertEqual(P.tidy_city('Stuttgart &'), 'Stuttgart')
        self.assertEqual(P.tidy_city('Bad Salzungen'), 'Bad Salzungen')

    def test_resolve(self):
        cases = {
            'Sydney, Australia': [('Sydney', 'australia')], 'London, ON': [('London', 'canada')], 'San Francisco, CA': [('San Francisco', 'usa')],
            'Perth, WA': [('Perth', 'australia')], 'Seattle, WA': [('Seattle', 'usa')], 'Berlin': [('Berlin', 'germany')],
            'Amsterdam, NL': [('Amsterdam', 'netherlands')], 'Düsseldorf': [('Düsseldorf', 'germany')], 'Singapore': [(None, 'singapore')],
            'Belfast, Northern Ireland': [('Belfast', 'uk')], 'London or New York': [('London', 'uk'), ('New York', 'usa')],
            'Sydney NSW': [('Sydney', 'australia')],
        }
        for text, want in cases.items():
            self.assertEqual(P.resolve(text), want, text)

    def test_never_guesses(self):
        for text in ['Remote', 'Remote - US', 'Remote, Germany', 'Cambridge', 'Wilmington, DE', "St. John's, NL", 'Narnia', '']:
            self.assertEqual(P.resolve(text), [], text)
        # two countries named in one place: skip it
        self.assertEqual(P.resolve('Toronto, Canada / Boston, US'), [('Toronto', 'canada'), ('Boston', 'usa')])
        self.assertEqual(P.resolve('Canada United States'), [])


class SourceTests(unittest.TestCase):
    def test_greenhouse(self):
        st, rows = S.greenhouse(fx(), 'acme')
        self.assertEqual(st, 'ok')
        self.assertEqual(len(rows), 6)
        self.assertEqual(rows[0]['posted'], '2026-11-10')

    def test_missing_and_blocked(self):
        self.assertEqual(S.greenhouse(fx(), 'ghost')[0], 'missing')
        self.assertEqual(S.ashby(fx(), 'blockedco')[0], 'blocked')

    def test_each_reader_returns_rows(self):
        self.assertEqual(S.lever(fx(), 'leverco')[0], 'ok')
        st, rows = S.ashby(fx(), 'ashbyco')
        self.assertEqual((st, len(rows)), ('ok', 2))  # the unlisted one is dropped
        self.assertEqual(S.smartrecruiters(fx(), 'srco')[0], 'ok')
        self.assertEqual(S.workable(fx(), 'wkco')[0], 'ok')
        st, rows = S.jobtech(fx(), terms=('praktik',))
        self.assertEqual((st, len(rows)), ('ok', 2))
        st, rows = S.arbeitnow(fx())
        self.assertEqual((st, len(rows)), ('ok', 3))  # followed the next-page link


def sources_file(tmp, extra_employers=()):
    emp = [{'name': 'Acme', 'ats': 'greenhouse', 'slug': 'acme'}, {'name': 'Lever Co', 'ats': 'lever', 'slug': 'leverco'},
           {'name': 'Ashby Co', 'ats': 'ashby', 'slug': 'ashbyco'}, {'name': 'SR Co', 'ats': 'smartrecruiters', 'slug': 'srco'},
           {'name': 'Wk Co', 'ats': 'workable', 'slug': 'wkco'}, {'name': 'Ghost', 'ats': 'greenhouse', 'slug': 'ghost'}, *extra_employers]
    p = Path(tmp) / 'sources.json'
    p.write_text(json.dumps({'employers': emp, 'openFeeds': {'jobtech': {'enabled': True}, 'arbeitnow': {'enabled': True}},
                             'portals': [{'id': 'p1', 'title': 'Portal', 'url': PORT['base'] + '/portal', 'countries': ['uk']}]}))
    return p


def run(tmp, *extra):
    argv = ['run.py', '--sources', str(sources_file(tmp)), '--prev', str(Path(tmp) / 'prev.json'), '--out', str(Path(tmp) / 'out.json'),
            '--report', str(Path(tmp) / 'rep'), '--delay', '0', '--today', '2026-11-14', *extra]
    old = sys.argv
    sys.argv = argv
    try:
        return R.main()
    finally:
        sys.argv = old


class RecheckTests(unittest.TestCase):
    def test_saved_postings_are_checked_again(self):
        old = [{'title': 'Software Intern', 'country': 'usa', 'kind': 'Internship', 'city': 'Austin', 'org': 'A'},
               {'title': 'Contract Student Worker', 'country': 'usa', 'kind': 'Working student', 'city': 'Boston', 'org': 'Zoox'},
               {'title': 'Product Manager Apprentice', 'country': 'france', 'kind': 'Internship', 'city': '9th arrondissement of Paris', 'org': 'Artefactjobs'},
               {'title': 'Data Analyst', 'country': 'usa', 'kind': 'Internship', 'city': 'Austin', 'org': 'B'}]  # kept: saved as an internship by the employer's flag
        R.ORG_ALIAS['artefactjobs'] = 'Artefact'
        kept, removed = R.recheck(old)
        self.assertEqual([k['title'] for k in kept], ['Software Intern', 'Data Analyst'])
        self.assertEqual(removed, 2)


class PipelineTests(unittest.TestCase):
    def test_full_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(run(tmp), 0)
            d = json.loads((Path(tmp) / 'out.json').read_text())
            titles = {(i['title'], i['country'], i['city']) for i in d['items']}
            # kept
            for want in [('Software Engineer Intern', 'australia', 'Sydney'), ('Data Science Intern', 'uk', 'London'), ('Data Science Intern', 'usa', 'New York'),
                         ('Product Design Co-op', 'canada', 'Toronto'), ('Analyst', 'singapore', ''), ('Associate', 'germany', 'Berlin'),
                         ('Praktikum Finance', 'germany', 'Munich'), ('Finance Intern', 'australia', 'Melbourne'), ('Trainee', 'malaysia', 'Kuala Lumpur'),
                         ('Summer Intern', 'uae', 'Dubai'), ('Praktikant ekonomi', 'sweden', 'Stockholm'), ('Werkstudent Marketing', 'germany', 'Berlin'),
                         ('Business Analyst', 'germany', 'Hamburg')]:
                self.assertIn(want, titles)
            # not kept: staff-like, remote, PhD, unplaced, unlisted, other-country (Vienna), non-internship
            names = {i['title'] for i in d['items']}
            for bad in ['Internal Auditor', 'Marketing Intern', 'Research Intern (PhD)', 'Design Intern', 'Intern, Hidden', 'Senior Analyst', 'Engineer', 'Senior Developer', 'Sjuksköterska']:
                self.assertNotIn(bad, names)
            self.assertFalse([i for i in d['items'] if i['url'].startswith('javascript')])
            self.assertEqual(d['stats']['boardsRead'], 8)
            self.assertEqual(d['stats']['boardsOk'], 7)  # the ghost board does not exist
            rep = (Path(tmp) / 'rep' / 'internship_report.md').read_text()
            self.assertIn('greenhouse:ghost', rep)
            self.assertIn('Narnia', rep)
            self.assertTrue(d['portals'][0]['ok'] in (True, False))

    def test_merge_misses_and_carry_forward(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(run(tmp), 0)
            out = Path(tmp) / 'out.json'
            d = json.loads(out.read_text())
            n = len(d['items'])
            # add a stale item from a board that is read fine (acme) and one from a board that will be down (leverco is up; use ghost-like 'lever:down')
            stale = {'id': 'zz1', 'title': 'Old Intern', 'org': 'Acme', 'city': 'Sydney', 'country': 'australia', 'kind': 'Internship', 'url': 'https://boards.example/acme/old',
                     'source': 'greenhouse', 'board': 'acme', 'posted': '', 'firstSeen': '2026-11-01'}
            held = dict(stale, id='zz2', title='Held Intern', url='https://x.example/held', source='lever', board='leverco')
            d['items'] += [stale, held]
            (Path(tmp) / 'prev.json').write_text(json.dumps(d))
            STATE['lever_down'] = True
            try:
                self.assertEqual(run(tmp), 0)
            finally:
                STATE['lever_down'] = False
            d2 = json.loads(out.read_text())
            by = {i['id']: i for i in d2['items']}
            self.assertEqual(by['zz1']['misses'], 1)  # acme was read, the posting was not there: one miss
            self.assertIn('zz2', by)  # leverco was down: carried forward untouched
            self.assertNotIn('misses', by['zz2'])
            (Path(tmp) / 'prev.json').write_text(json.dumps(d2))
            self.assertEqual(run(tmp), 0)
            d3 = json.loads(out.read_text())
            self.assertNotIn('zz1', {i['id'] for i in d3['items']})  # second miss: dropped
            old = {i['id']: i['firstSeen'] for i in d['items']}
            for i in d3['items']:
                if i['id'] in old:
                    self.assertEqual(i['firstSeen'], old[i['id']])  # first-seen dates are kept
            self.assertGreaterEqual(len(d3['items']), n - 1)

    def test_gate_stops_collapse(self):
        with tempfile.TemporaryDirectory() as tmp:
            filler = [{'id': f'f{i}', 'title': f'Filler Intern {i}', 'org': 'X', 'city': 'Paris', 'country': 'france', 'kind': 'Internship', 'url': f'https://x.example/{i}',
                       'source': 'greenhouse', 'board': 'acme', 'posted': '', 'firstSeen': '2026-11-01', 'misses': 1} for i in range(300)]
            (Path(tmp) / 'prev.json').write_text(json.dumps({'items': filler, 'generatedAt': '2026-11-01T00:00:00Z'}))
            before = (Path(tmp) / 'prev.json').read_text()
            self.assertEqual(run(tmp), 3)
            self.assertFalse((Path(tmp) / 'out.json').exists())
            self.assertIn('STOPPED', (Path(tmp) / 'rep' / 'internship_report.md').read_text())
            self.assertEqual((Path(tmp) / 'prev.json').read_text(), before)
            self.assertEqual(run(tmp, '--allow-drop'), 0)
            self.assertTrue((Path(tmp) / 'out.json').exists())

    def test_cadence_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            from datetime import datetime, timezone
            (Path(tmp) / 'prev.json').write_text(json.dumps({'items': [], 'generatedAt': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}))
            self.assertEqual(run(tmp, '--if-older-than-hours', '20'), 0)
            self.assertFalse((Path(tmp) / 'out.json').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
