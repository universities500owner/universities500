#!/usr/bin/env python3
"""Offline tests: a stub university website on localhost and a stub Wikimedia API. No internet, no AI.
Run: python3 scripts/profiles/test_profiles.py"""
import datetime
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'scholarships'))
import collect as C  # noqa: E402
import commons as CM  # noqa: E402
import report as R  # noqa: E402
import review as RV  # noqa: E402
import sitereader as S  # noqa: E402
import wikidata as WD  # noqa: E402
from fetcher import Fetcher  # noqa: E402

PORT = {}
PAGES = {}


def page(title, body, head=''):
    return f'<html><head><title>{title}</title>{head}</head><body>{body}</body></html>'


def home():
    ld = '<script type="application/ld+json">{"@type":"CollegeOrUniversity","sameAs":["https://www.instagram.com/stubuni/","https://www.youtube.com/@stubuni"]}</script>'
    nav = ('<nav><a href="/admissions/">Admissions</a><a href="/study/courses/">Courses</a><a href="/scholarships/">Scholarships</a>'
           '<a href="/faculties/">Faculties</a><a href="/industry/">Industry partnerships</a><a href="/campuses/">Our campuses</a>'
           '<a href="/about/facts/">Facts and figures</a><a href="/news/new-scholarship-announced-for-engineering-students-this-year">'
           'New scholarship announced for engineering students this year</a></nav>')
    foot = ('<footer><a href="https://www.instagram.com/stubuni/">Instagram</a><a href="https://www.linkedin.com/school/stub-university/">LinkedIn</a>'
            '<a href="https://www.youtube.com/@stubuni">YouTube</a><a href="https://www.instagram.com/stubuni_sports/">Sports</a></footer>')
    return page('Stub University', nav + '<h1>Stub University</h1>' + foot, ld)


def pages():
    return {
        '/': home(),
        '/admissions/': page('Admissions | Stub University', '<h1>How to apply</h1>'),
        '/study/courses/': page('Find a course | Stub University', '<h1>Courses</h1>'),
        '/scholarships/': page('Scholarships and funding', '<h1>Scholarships</h1>'),
        '/faculties/': page('Faculties | Stub University', '<h1>Our faculties</h1><a href="/arts/">Faculty of Arts</a><a href="/sci/">Faculty of Science</a>'
                            '<a href="/eng/">School of Engineering</a><a href="/all/">View all schools</a>'),
        '/industry/': page('Industry partnerships', '<h1>Industry</h1>'),
        '/campuses/': page('Campuses', '<h1>Campuses</h1><a href="/north/">North campus</a><a href="/south/">South campus</a>'),
        '/about/facts/': page('Facts and figures', '<h1>Facts</h1><p>Over 31,000 students in 2023, including 5,200 international students.</p>'),
    }


class H(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        p = self.path.split('?')[0]
        body = PAGES.get(p)
        if p == '/robots.txt' or body is None:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, *a):
        pass


def photo(title, w, h, lic='CC BY-SA 4.0', artist='<a href="x">Jane Doe</a>', date='2021-05-01', mime='image/jpeg', cats='Stub University'):
    meta = {'LicenseShortName': {'value': lic}, 'Artist': {'value': artist}, 'DateTimeOriginal': {'value': date},
            'Categories': {'value': cats}, 'ImageDescription': {'value': 'A view'}}
    return {'title': title, 'imageinfo': [{'url': f'https://u/{title}', 'thumburl': f'https://t/{title}', 'thumbwidth': 960, 'width': w, 'height': h, 'mime': mime,
                                           'descriptionurl': f'https://commons/{title}', 'timestamp': '2022-01-01T00:00:00Z', 'extmetadata': meta}]}


FILES = {p['title']: p for p in [
    photo('File:Stub University library 2021.jpg', 4000, 2500),
    photo('File:Stub University aerial 2019.jpg', 5000, 3000, lic='CC BY 2.0', date='2019-03-02'),
    photo('File:Stub University logo.png', 4000, 2500),
    photo('File:Small view.jpg', 800, 600),
    photo('File:Tall view.jpg', 1000, 3000),
    photo('File:NC photo.jpg', 4000, 2500, lic='CC BY-NC 4.0'),
    photo('File:No author.jpg', 4000, 2500, artist=''),
    photo('File:North campus Stub University 2022.jpg', 4000, 2500, date='2022-06-01', cats='North campus|Stub University'),
    photo('File:Random street.jpg', 4000, 2500, cats='Streets'),
]}


class FakeApi:
    requests = 0

    def get_json(self, base, params):
        if base.endswith('sparql'):
            def b(n, site=None):
                d = {'fLabel': {'value': n}}
                if site:
                    d['site'] = {'value': site}
                return d
            return {'results': {'bindings': [b('Faculty of Law', 'https://law.stub.test/'), b('Stub University Library'), b('Q12345'), b('School of Music')]}}
        q = params
        if q.get('list') == 'categorymembers':
            if q['cmtype'] == 'subcat':
                return {'query': {'categorymembers': [{'title': 'Category:Buildings of Stub University'}, {'title': 'Category:People of Stub University'}]}}
            if 'Buildings' in q['cmtitle']:
                return {'query': {'categorymembers': [{'title': 'File:Stub University aerial 2019.jpg'}]}}
            return {'query': {'categorymembers': [{'title': t} for t in FILES if 'campus' not in t and 'street' not in t]}}
        if q.get('list') == 'search':
            return {'query': {'search': [{'title': 'File:Random street.jpg'}, {'title': 'File:North campus Stub University 2022.jpg'}]}}
        if q.get('prop') == 'imageinfo':
            return {'query': {'pages': [FILES[t] for t in q['titles'].split('|') if t in FILES]}}
        raise AssertionError(f'unexpected call {base} {params}')


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        PAGES.update(pages())
        cls.srv = HTTPServer(('127.0.0.1', 0), H)
        PORT['p'] = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    # ---------- Wikidata ----------
    def test_wikidata_facts(self):
        def snak(v, t='wikibase-item'):
            return {'snaktype': 'value', 'datavalue': {'value': v, 'type': t}}
        ent = {'id': 'Q1', 'claims': {
            'P571': [{'rank': 'normal', 'mainsnak': snak({'time': '+1958-01-01T00:00:00Z', 'precision': 9})}],
            'P2196': [
                {'rank': 'normal', 'mainsnak': snak({'amount': '+50000'}), 'qualifiers': {'P585': [snak({'time': '+2019-00-00T00:00:00Z', 'precision': 9})]}},
                {'rank': 'normal', 'mainsnak': snak({'amount': '+55000'}), 'qualifiers': {'P585': [snak({'time': '+2022-01-01T00:00:00Z', 'precision': 11})]}},
                {'rank': 'deprecated', 'mainsnak': snak({'amount': '+99999'}), 'qualifiers': {'P585': [snak({'time': '+2024-01-01T00:00:00Z', 'precision': 9})]}}],
            'P625': [{'rank': 'normal', 'mainsnak': snak({'latitude': -37.9105, 'longitude': 145.1362})}],
            'P856': [{'rank': 'normal', 'mainsnak': snak('https://www.stub.test/', 'string')}],
            'P373': [{'rank': 'normal', 'mainsnak': snak('Stub University', 'string')}],
            'P2003': [{'rank': 'normal', 'mainsnak': snak('stubuni', 'string')}]},
            'sitelinks': {'enwiki': {'title': 'Stub University'}}}
        f = WD.parse(ent)
        self.assertEqual(f['founded'], {'v': 1958, 'all': [1958], 'conflict': False})
        self.assertEqual((f['students']['v'], f['students']['asof']), (55000, 2022))   # latest dated, deprecated ignored
        self.assertEqual(f['commons'], 'Stub University')
        self.assertEqual(f['coords']['lat'], -37.9105)
        self.assertEqual(f['enwiki'], 'Stub University')
        self.assertEqual(WD.social_url('instagram', 'stubuni'), 'https://www.instagram.com/stubuni/')

    def test_wikidata_year_needs_precision_and_conflict_flagged(self):
        def snak(v):
            return {'snaktype': 'value', 'datavalue': {'value': v}}
        ent = {'id': 'Q2', 'claims': {'P571': [
            {'rank': 'normal', 'mainsnak': snak({'time': '+1900-00-00T00:00:00Z', 'precision': 7})},       # a century: not a year
            {'rank': 'normal', 'mainsnak': snak({'time': '+1965-01-01T00:00:00Z', 'precision': 9})},
            {'rank': 'normal', 'mainsnak': snak({'time': '+1970-01-01T00:00:00Z', 'precision': 9})}]}}
        f = WD.parse(ent)
        self.assertTrue(f['founded']['conflict'])
        self.assertEqual(f['founded']['all'], [1965, 1970])

    def test_faculties_filter(self):
        names = [f['name'] for f in WD.faculties(FakeApi(), 'Q1')]
        self.assertEqual(names, ['Faculty of Law', 'School of Music'])        # not the library, not a bare Q id

    # ---------- site reader ----------
    def test_role_links_and_news_is_ignored(self):
        info = S.page_info(home(), 'https://www.stub.test/')
        reg = 'stub.test'
        self.assertEqual(S.role_candidates('scholarships', info['links'], reg)[0]['url'], 'https://www.stub.test/scholarships/')
        self.assertEqual(S.role_candidates('admissions', info['links'], reg)[0]['url'], 'https://www.stub.test/admissions/')
        self.assertTrue(all('/news/' not in c['url'] for r in S.ROLES for c in S.role_candidates(r, info['links'], reg)))

    def test_socials_prefer_footer_and_flag_disagreement(self):
        info = S.page_info(home(), 'https://www.stub.test/')
        out = S.socials(info['links'], info['same_as'], {'instagram': 'stubuni', 'youtube': 'someoneelse'})
        self.assertEqual(out['instagram']['url'], 'https://www.instagram.com/stubuni/')
        self.assertEqual(out['instagram']['others'], ['stubuni_sports'])
        self.assertTrue(out['instagram']['agree'])
        self.assertFalse(out['youtube']['agree'])
        self.assertEqual(out['linkedin']['url'], 'https://www.linkedin.com/school/stub-university/')

    def test_student_numbers(self):
        t = ('Over 31,000 students in 2023. 5,200 international students. 55 000 étudiants (2022). 41.000 Studierende. '
             'We have 120 students in this lab. 900000 students worldwide.')
        got = S.student_numbers(t)
        vals = [(g['v'], g['intl']) for g in got]
        self.assertIn((31000, False), vals)
        self.assertIn((5200, True), vals)
        self.assertIn((55000, False), vals)
        self.assertIn((41000, False), vals)
        self.assertFalse(any(v in (120, 900000) for v, _ in vals))
        self.assertEqual(next(g['asof'] for g in got if g['v'] == 31000), 2023)

    # ---------- Commons ----------
    def test_gate_reasons(self):
        why = {t: CM.gate(p)[1] for t, p in FILES.items()}
        self.assertEqual(why['File:Stub University library 2021.jpg'], '')
        self.assertEqual(why['File:Stub University logo.png'], 'name')
        self.assertEqual(why['File:Small view.jpg'], 'small')
        self.assertEqual(why['File:Tall view.jpg'], 'small')
        self.assertEqual(why['File:NC photo.jpg'], 'licence')
        self.assertEqual(why['File:No author.jpg'], 'no author')

    def test_gallery_picks_recent_licensed_photos_with_credit(self):
        photos, counts = CM.gallery(FakeApi(), 'Stub University', 2026)
        titles = [p['title'] for p in photos]
        self.assertIn('File:Stub University library 2021.jpg', titles)
        self.assertIn('File:Stub University aerial 2019.jpg', titles)     # found through a building sub-category
        self.assertFalse(any('logo' in t or 'NC' in t or 'Small' in t for t in titles))
        self.assertEqual(titles[0], 'File:Stub University library 2021.jpg')   # newer first
        p = photos[0]
        self.assertEqual((p['author'], p['licence']), ('Jane Doe', 'CC BY-SA 4.0'))   # HTML stripped
        self.assertTrue(p['page'].startswith('https://commons/'))
        self.assertGreaterEqual(counts['usable'], 2)

    def test_campus_photo_must_name_campus_and_university(self):
        ph = CM.campus_photo(FakeApi(), 'North', 'Stub University', 2026)
        self.assertEqual(ph['title'], 'File:North campus Stub University 2022.jpg')   # not the 'Random street' result
        self.assertIsNone(CM.campus_photo(FakeApi(), 'Harbour', 'Stub University', 2026))

    # ---------- fixes found by the first real run ----------
    def test_social_compares_only_like_with_like(self):
        self.assertIsNone(S.same_account('youtube', 'UCO3krgSinpAjqXE1DU47-cA', 'sorbonneuniversite'))   # channel id vs name: cannot compare
        self.assertFalse(S.same_account('youtube', 'someone', 'sorbonneuniversite'))
        self.assertTrue(S.same_account('youtube', 'UCO3krgSinpAjqXE1DU47-cA', 'channel/UCO3krgSinpAjqXE1DU47-cA'))
        self.assertIsNone(S.same_account('linkedin', 'monash-university', '8788'))
        self.assertTrue(S.same_account('instagram', 'monash_uni', 'monash_uni'))
        self.assertIsNone(S.same_account('instagram', '', 'monash_uni'))

    def test_campus_names_must_look_like_campuses(self):
        good = ['North campus', 'Clayton Campus', 'Campus de Jussieu', 'Main campus']
        bad = ['Cross-campus pathways', 'Campus locations', 'Campus maps', 'Vie des campus', 'Our campuses', 'View all campuses', 'Virtual campus']
        for t in good:
            self.assertTrue(S.CAMPUS_NAME.match(t), t)
        for t in bad:
            self.assertFalse(S.CAMPUS_NAME.match(t), t)

    def test_facts_role_ignores_a_page_that_only_says_facts_in_passing(self):
        links = [{'url': 'https://www.stub.test/about/merger-proposal/', 'text': 'About the merger proposal: claims and facts', 'footer': False},
                 {'url': 'https://www.stub.test/about/facts-and-figures/', 'text': 'Facts and figures', 'footer': False}]
        top = S.role_candidates('facts', links, 'stub.test')
        self.assertEqual(top[0]['url'], 'https://www.stub.test/about/facts-and-figures/')
        self.assertEqual(len(top), 1)

    def test_english_page_is_used_and_social_links_from_both_pages_are_kept(self):
        PAGES['/en-home/'] = page('Stub University', '<nav><a href="/admissions/">Admissions</a></nav><h1>Welcome</h1>').replace('<html>', '<html lang="en">')
        PAGES['/no-home/'] = ('<html lang="no"><head><title>Stub</title><link rel="alternate" hreflang="en" href="/en-home/"></head><body>'
                              '<footer><a href="https://www.instagram.com/stubuni/">Instagram</a></footer></body></html>')
        fx = Fetcher('Universities500Bot/1.0 (test)', delay=0, timeout=5)
        out = S.crawl(fx, f'http://127.0.0.1:{PORT["p"]}/no-home/')
        self.assertTrue(out['home'].get('english', '').endswith('/en-home/'))
        self.assertEqual(out['links']['admissions']['grade'], 'verified')
        soc = S.socials(out['social_links'], out['_same_as'], {})
        self.assertEqual(soc['instagram']['url'], 'https://www.instagram.com/stubuni/')   # from the original page's footer

    def test_wikidata_faculties_are_tidied(self):
        self.assertEqual(WD.tidy_faculty('UiO Faculty of Dentistry', 'University of Oslo'), 'Faculty of Dentistry')
        self.assertEqual(WD.tidy_faculty('Faculty of Law, University of Oslo', 'University of Oslo'), 'Faculty of Law')
        self.assertEqual(WD.tidy_faculty('University of Oslo Faculty of Theology', 'University of Oslo'), 'Faculty of Theology')

    def test_gallery_drops_protests_and_prefers_buildings(self):
        bad = photo('File:Pro-palestine protest at Stub.jpg', 4000, 2500)
        self.assertEqual(CM.gate(bad)[1], 'name')
        cat = photo('File:Stub quad.jpg', 4000, 2500, cats='Protests at Stub University')
        self.assertEqual(CM.gate(cat)[1], 'topic')
        ok = photo('File:Stub quad.jpg', 4000, 2500, cats='Buildings of Stub University')
        self.assertTrue(CM.gate(ok)[0])

    def test_engravings_and_undated_files_are_not_gallery_photos(self):
        eng = photo('File:Stub University view.jpg', 4000, 2500, cats='Engravings of Stub University')
        self.assertEqual(CM.gate(eng)[1], 'topic')
        saved = photo('File:Stub University scan.jpg', 4000, 2500, date='')          # no capture date, only a saved-on date
        saved['imageinfo'][0]['extmetadata']['DateTime'] = {'value': '2024-02-02'}
        self.assertEqual(CM.photo_year(saved['imageinfo'][0])[1], 'uploaded')          # not 'taken'
        self.assertEqual(CM.photo_year(FILES['File:Stub University library 2021.jpg']['imageinfo'][0]), (2021, 'taken'))

    def test_gallery_prefers_photos_from_the_last_15_years(self):
        class Api2(FakeApi):
            def get_json(self, base, params):
                if params.get('list') == 'categorymembers' and params['cmtype'] == 'file':
                    return {'query': {'categorymembers': [{'title': f'File:Stub campus {i}.jpg'} for i in range(8)]}}
                if params.get('list') == 'categorymembers':
                    return {'query': {'categorymembers': []}}
                if params.get('prop') == 'imageinfo':
                    pages = []
                    for t in params['titles'].split('|'):
                        i = int(t.split()[-1].split('.')[0])
                        pages.append(photo(t, 4000, 2500, date=f'{1908 if i == 0 else 2020 + i % 5}-05-01', artist=f'Author {i}'))
                    return {'query': {'pages': pages}}
                raise AssertionError(params)
        photos, _ = CM.gallery(Api2(), 'Stub University', 2026, want=6)
        self.assertEqual(len(photos), 6)
        self.assertTrue(all(p['year'] >= 2011 for p in photos))

    def test_credit_must_be_a_name_not_an_instruction(self):
        for who in ('Thank you to indicate this credit line next to the image in case of reuse: Credit Sorbonne',
                    'Unknown author Unknown author', 'No machine-readable author provided. Donaldytong assumed', 'x' * 80):
            self.assertEqual(CM.gate(photo('File:Stub aerial.jpg', 4000, 2500, artist=who))[1], 'author text', who[:30])
        self.assertTrue(CM.gate(photo('File:Stub aerial.jpg', 4000, 2500, artist='Maksim Sokolov (Maxergon)'))[0])

    def test_campus_noise_words_are_dropped(self):
        links = [{'url': f'https://www.stub.test/{i}/', 'text': t, 'footer': False} for i, t in
                 enumerate(['North Campus', 'Campus Life', 'Campus Tours', 'Smoke-free campus', 'Accessible Campus', 'Loyola Campus'])]
        names = [n['name'] for n in S.names_from_links(links, S.CAMPUS_NAME, 'stub.test', 12)]
        self.assertEqual(names, ['North Campus', 'Loyola Campus'])

    def test_founded_year_is_checked_against_the_lead(self):
        wd = {'src': 'x', 'founded': {'v': 2018, 'all': [2018], 'conflict': False}}
        self.assertEqual(C.founded_block(wd, 'It was founded in 1257 and merged in 2018.')['status'], 'check')
        self.assertEqual(C.founded_block(wd, 'It was established in 2018.')['status'], 'confirmed')
        self.assertEqual(C.founded_block(wd, 'A public university.')['status'], 'ok')
        self.assertEqual(C.founded_block({'src': 'x'}, '')['status'], 'missing')


    # ---------- the whole record ----------
    def test_process_builds_a_record(self):
        base = f'http://127.0.0.1:{PORT["p"]}/'
        fx = Fetcher('Universities500Bot/1.0 (test)', delay=0, timeout=5)
        uni = {'slug': 'stub', 'name': 'Stub University', 'countryName': 'Australia', 'qid': 'Q1', 'web': base,
               'campuses': [{'n': 'North', 'w': 'campus'}], 'overview': 'Stub University is a public university.', 'overviewSrc': 'https://en.wikipedia.org/wiki/Stub'}
        wd = {'qid': 'Q1', 'src': 'https://www.wikidata.org/wiki/Q1', 'founded': {'v': 1958, 'all': [1958], 'conflict': False},
              'students': {'v': 31200, 'asof': 2023, 'all': [{'v': 31200, 'asof': 2023, 'preferred': False}]}, 'commons': 'Stub University', 'instagram': 'stubuni'}
        rec, cache = C.process(uni, wd, FakeApi(), fx, datetime.date(2026, 11, 22))
        self.assertEqual(rec['errors'], [])
        self.assertEqual(rec['students']['status'], 'verified')                 # the site says 31,000: within 15%
        self.assertEqual(rec['students']['second']['v'], 31000)
        for role in ('admissions', 'courses', 'scholarships', 'partners'):
            self.assertEqual(rec['links'][role]['grade'], 'verified', role)
        self.assertEqual([f['name'] for f in rec['faculties']][:2], ['Faculty of Arts', 'Faculty of Law'])
        self.assertEqual(rec['social']['instagram']['status'], 'verified')
        self.assertEqual(rec['social']['linkedin']['status'], 'verified')
        self.assertEqual(rec['campuses'][0]['name'], 'North')
        self.assertTrue(rec['campuses'][0]['maps'].startswith('https://www.google.com/maps/search/?api=1&query=North'))
        self.assertTrue(rec['campuses'][0]['photo'])
        self.assertGreaterEqual(len(rec['gallery']['photos']), 2)
        self.assertIn('facts', cache)
        text = R.build([rec], {})
        self.assertIn('Fill rate by field', text)
        self.assertIn('Stub University', text)

    def test_review_page_builds_offline(self):
        base = f'http://127.0.0.1:{PORT["p"]}/'
        fx = Fetcher('Universities500Bot/1.0 (test)', delay=0, timeout=5)
        uni = {'slug': 'stub', 'name': 'Stub <University>', 'countryName': 'Australia', 'qid': 'Q1', 'web': base, 'campuses': [{'n': 'North', 'w': 'campus'}]}
        wd = {'qid': 'Q1', 'src': 'https://www.wikidata.org/wiki/Q1', 'founded': {'v': 1958, 'all': [1958], 'conflict': False}, 'commons': 'Stub University'}
        rec, _ = C.process(uni, wd, FakeApi(), fx, datetime.date(2026, 11, 22))
        page_html = RV.build([rec], thumb=lambda u: 'data:image/jpeg;base64,AAAA')
        self.assertIn('Stub &lt;University&gt;', page_html)                      # names are escaped
        self.assertIn('https://www.google.com/maps/search/?api=1&amp;query=North', page_html)
        self.assertIn('data:image/jpeg;base64,AAAA', page_html)
        self.assertIn('Jane Doe', page_html)                                      # the credit line is printed
        self.assertEqual(RV.small('https://upload.wikimedia.org/x/960px-A.jpg'), 'https://upload.wikimedia.org/x/330px-A.jpg')

    def test_a_site_that_will_not_answer_is_reported_not_fatal(self):
        fx = Fetcher('Universities500Bot/1.0 (test)', delay=0, timeout=2)
        uni = {'slug': 'x', 'name': 'X University', 'countryName': 'Nowhere', 'qid': 'Q9', 'web': 'http://127.0.0.1:1/', 'campuses': []}
        rec, _ = C.process(uni, {'qid': 'Q9', 'src': 'https://www.wikidata.org/wiki/Q9'}, FakeApi(), fx, datetime.date(2026, 11, 22))
        self.assertNotEqual(rec['website']['status'], 200)
        self.assertEqual(rec['students']['status'], 'missing')
        self.assertEqual(rec['campuses'][0]['name'], 'Main campus')
        self.assertIn('site', R.build([rec], {}).lower())


if __name__ == '__main__':
    unittest.main(verbosity=1)
