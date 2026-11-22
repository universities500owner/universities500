"""Offline tests for publish.py: only checked values reach the site file."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import publish as P  # noqa: E402

THUMB = 'https://thumb.wikimedia.org/wikipedia/commons/thumb/4/45/A.jpg/960px-A.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo'


def photo(n=1):
    return {'title': f'File:A{n}.jpg', 'thumb': THUMB.replace('A.jpg', f'A{n}.jpg'), 'thumbWidth': 960, 'width': 4000, 'height': 3000, 'author': 'Jo Bloggs', 'licence': 'CC BY-SA 4.0',
            'licenceUrl': 'https://creativecommons.org/licenses/by-sa/4.0', 'page': f'https://commons.wikimedia.org/wiki/File:A{n}.jpg', 'year': 2022}


def rec():
    return {
        'slug': 'stub', 'name': 'Stub University', 'generated': '2026-11-22',
        'brief': {'text': 'Stub University is a public university.', 'status': 'verified', 'src': 'university pages and Wikipedia lead'},
        'founded': {'v': 1958, 'status': 'official', 'src': 'https://stub.test/about', 'source_text': 'Source: stub.test', 'present_form': {'v': 2018}},
        'students': {'v': 30000, 'asof': 2023, 'status': 'official', 'src': 'https://stub.test/facts', 'source_text': 'Source: stub.test, 2023'},
        'campuses': [{'name': 'North Campus', 'maps': 'https://www.google.com/maps/search/?api=1&query=North', 'from': 'university page', 'quote': 'North Campus is in the city', 'photo': photo(9)},
                     {'name': 'Moon Campus', 'maps': 'https://www.google.com/maps/search/?api=1&query=Moon', 'from': 'university page', 'quote': 'A Moon Campus is planned for 2030', 'photo': None},
                     {'name': 'East Campus', 'maps': 'https://www.google.com/maps/search/?api=1&query=East', 'from': 'university page', 'quote': 'East Campus is by the river', 'photo': None}],
        'faculties': [{'name': 'Schools & Colleges', 'url': ''}, {'name': 'Faculty of Law', 'url': 'https://law.stub.test'}, {'name': 'Faculty of Law', 'url': ''},
                      {'name': 'Majors & Programs', 'url': ''}, {'name': 'Graduate Programs', 'url': ''}, {'name': 'Faculty of Arts', 'url': ''}, {'name': 'Stub University North', 'url': ''}, {'name': 'Stub University School of Music', 'url': ''}],
        'links': {'admissions': {'url': 'https://stub.test/apply', 'final': 'https://stub.test/apply/', 'grade': 'verified'}, 'courses': {'url': 'https://stub.test/courses', 'grade': 'weak'},
                  'scholarships': {'url': 'https://stub.test/funding', 'grade': 'verified'}, 'partners': {'url': 'https://stub.test/industry', 'grade': 'external'}},
        'social': {'instagram': {'url': 'https://www.instagram.com/stub/', 'status': 'verified'}, 'linkedin': {'url': 'https://www.linkedin.com/school/stub/', 'status': 'check'},
                   'youtube': {'url': 'https://www.youtube.com/@stub', 'status': 'wikidata-only'}},
        'partners': {'names': [{'name': 'Acme Corp'}, {'name': 'Initech'}], 'page': 'https://stub.test/industry'},
        'gallery': {'photos': [photo(i) for i in range(1, 11)]},
        'publish': {'brief': True, 'founded': True, 'students': True, 'gallery': True},
    }


class Tests(unittest.TestCase):
    def test_everything_that_passed_is_in(self):
        o = P.one(rec())
        self.assertEqual(o['brief'], 'Stub University is a public university.')
        self.assertEqual(o['established'], {'v': 1958, 'note': 'Present form 2018', 'source': 'Source: stub.test', 'src': 'https://stub.test/about'})
        self.assertEqual((o['students']['v'], o['students']['asof'], o['students']['source']), (30000, 2023, 'Source: stub.test, 2023'))
        self.assertEqual(len(o['gallery']), 8)                                                      # capped
        self.assertEqual(o['partners'], ['Acme Corp', 'Initech'])

    def test_what_did_not_pass_is_out(self):
        r = rec()
        r['publish'] = {'brief': False, 'founded': False, 'students': False, 'gallery': False}
        o = P.one(r)
        for k in ('brief', 'established', 'students', 'gallery'):
            self.assertNotIn(k, o)
        self.assertTrue(o['campuses'] and o['faculties'])                                           # the university stays listed with the rest

    def test_wikidata_city_is_a_place_not_a_campus(self):
        r = rec()
        r['campuses'] = [{'name': 'Berkeley', 'maps': 'https://m', 'from': 'wikidata', 'photo': None}]
        o = P.one(r)
        self.assertNotIn('campuses', o)
        self.assertEqual(o['place']['name'], 'Berkeley')
        self.assertIn('Stub+University', o['place']['maps'])                                        # the map searches for the university, not for the city
        r['campuses'] = [{'name': 'Queensland', 'maps': 'https://m', 'from': 'wikidata', 'photo': None}]
        self.assertNotIn('place', P.one(r))                                                         # a region is not somewhere to put a pin

    def test_menu_labels_and_buildings_are_not_campuses(self):
        r = rec()
        r['campuses'] = [{'name': n, 'maps': 'https://m', 'from': src, 'quote': 'x', 'photo': None} for n, src in
                         (('Campus Bus Routes', 'site'), ('Campus Buildings', 'university page'), ('Hammersmith Hospital', 'university page'), ('Faculty of Medicine campus', 'university page'),
                          ('Water sports center (Pleinfeld)', 'university page'), ('Main Campus', 'site'), ('Bentley Campus', 'university page'))]
        self.assertEqual([c['name'] for c in P.one(r)['campuses']], ['Bentley Campus'])

    def test_one_or_two_faculties_are_not_shown(self):
        r = rec()
        r['faculties'] = [{'name': 'Faculty of Law', 'url': ''}, {'name': 'Faculty of Arts', 'url': ''}, {'name': 'University Libraries', 'url': ''}]
        self.assertNotIn('faculties', P.one(r))

    def test_wide_copy_only_when_the_original_is_big_enough(self):
        r = rec()
        r['gallery']['photos'][0]['width'] = 1000
        g = P.one(r)['gallery']
        self.assertNotIn('u2', g[0])
        self.assertIn('/1280px-', g[1]['u2'])
        self.assertEqual(g[1]['o'], 4000)

    def test_only_verified_links_go_live(self):
        self.assertEqual(P.one(rec())['links'], {'admissions': 'https://stub.test/apply/', 'scholarships': 'https://stub.test/funding'})

    def test_social_needs_a_verified_or_official_page(self):
        self.assertEqual(sorted(P.one(rec())['social']), ['instagram', 'youtube'])                  # the LinkedIn page is in doubt

    def test_menu_labels_and_duplicates_are_not_faculties(self):
        self.assertEqual([f['name'] for f in P.one(rec())['faculties']], ['Faculty of Law', 'Faculty of Arts', 'Stub University School of Music'])
        self.assertEqual(P.one(rec())['faculties'][0]['url'], 'https://law.stub.test')

    def test_planned_campuses_are_left_out_and_photos_are_credited(self):
        c = P.one(rec())['campuses']
        self.assertEqual([x['name'] for x in c], ['North Campus', 'East Campus'])
        ph = c[0]['photo']
        self.assertIn('/500px-', ph['u'])                                                           # a standard thumbnail size, no tracking query
        self.assertNotIn('?', ph['u'])
        self.assertEqual((ph['by'], ph['lic'], ph['y']), ('Jo Bloggs', 'CC BY-SA 4.0', 2022))
        self.assertEqual((ph['w'], ph['h']), (500, 375))                                            # 4:3 kept, so the page can reserve the space
        self.assertTrue(ph['page'].startswith('https://commons.wikimedia.org/wiki/File:'))
        self.assertIsNone(c[1]['photo'])

    def test_gallery_keeps_960_px_and_credits(self):
        g = P.one(rec())['gallery']
        self.assertIn('/960px-', g[0]['u'])
        self.assertTrue(all(p['by'] and p['licUrl'] and p['page'] for p in g))

    def test_a_bare_record_is_fine(self):
        o = P.one({'slug': 's', 'name': 'S', 'publish': {}})
        self.assertEqual(o, {'name': 'S', 'generated': ''})

    def test_input_is_not_changed(self):
        r = rec()
        before = copy.deepcopy(r)
        P.one(r)
        self.assertEqual(r, before)


if __name__ == '__main__':
    unittest.main()
