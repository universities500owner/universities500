#!/usr/bin/env python3
"""Offline tests: a stub university website on localhost, no internet, no AI.
Run: python3 scripts/courses/test_courses.py"""
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
sys.path.insert(0, str(HERE.parent / 'scholarships'))
import build_site_data as B  # noqa: E402
import checks as Q  # noqa: E402
import courses as C  # noqa: E402
import detail as D  # noqa: E402
import detail_run as DR  # noqa: E402
import cricos as K  # noqa: E402
import crawl  # noqa: E402
import extract as X  # noqa: E402
import facts as F  # noqa: E402
import levels as L  # noqa: E402
import textutil as T  # noqa: E402
from fetcher import Fetcher  # noqa: E402

PORT = {}
HITS = []
EXTRA = {}          # path -> (content type, body[, status]); a test adds pages here and clears them afterwards


def page(title, body, head=''):
    return (f'<!doctype html><html lang="en"><head><title>{title} | Test University</title>{head}</head><body><header><nav><a href="/">Home</a></nav></header>'
            f'<main><h1>{title}</h1>{body}</main><footer>footer text</footer></body></html>')


def course(title, body, head=''):
    return ('text/html', page(title, body + '<p>Filler sentence so that the page is long enough to be read as a page of content.</p>' * 3, head))


def pages():
    p = PORT['p']
    base = f'http://127.0.0.1:{p}'
    list1 = ''.join(f'<li><a href="{u}">{t}</a></li>' for u, t in [
        ('/courses/bsc-computer-science/', 'Computer Science BSc (Hons)'),
        ('/courses/msc-data-science/', 'MSc Data Science'),
        ('/courses/bsc-business-online/', 'BSc Business Management (Online)'),
        ('/courses/msc-finance-distance/', 'MSc Finance'),
        ('/courses/phd-physics/', 'PhD Physics'),
        ('/courses/graduate-certificate-business/', 'Graduate Certificate in Business'),
        ('/courses/foundation-engineering/', 'International Foundation Year in Engineering'),
        ('/courses/ba-history-domestic/', 'Bachelor of Arts in History'),
        ('/courses/mba-part-time/', 'Master of Business Administration'),
        ('/courses/beng-civil/', 'Bachelor of Engineering (Civil)'),
        ('/courses/ma-media/', 'Master of Arts in Media'),
        ('/courses/bs-physics/', 'Bachelor of Science in Physics'),
        ('/courses/beng-mechanical/', 'Mechanical Engineering BEng'),
        ('/private/mba/', 'Master of Business Administration (private)')])
    return {
        '/robots.txt': ('text/plain', f'User-agent: *\nDisallow: /private/\nSitemap: {base}/sitemap.xml\n'),
        '/sitemap.xml': ('application/xml', '<?xml version="1.0"?><urlset>' + ''.join(f'<url><loc>{base}{u}</loc></url>' for u in [
            '/courses/bsc-computer-science/', '/courses/msc-ai/', '/news/new-building/', '/de/studium/bachelor-informatik/', '/private/mba/', '/about/']) + '</urlset>'),
        '/': ('text/html', page('Test University', '<p>Welcome to Test University, a place to study.</p>' * 10).replace(
            '<nav><a href="/">Home</a></nav>', '<nav><a href="/">Home</a><a href="/courses/">Courses</a><a href="/international/">International students</a></nav>')),
        '/international/': ('text/html', page('International students', '<p>International students can apply online from October. Entry requirements for international students include IELTS 6.5 and a student visa.</p>' * 3)),
        '/courses/': ('text/html', page('Courses', f'<p>Find your course at Test University.</p><ul>{list1}</ul><a href="/courses/?page=2">Next page</a>' + '<p>Long enough text. </p>' * 12)),
        '/courses/?page=2': ('text/html', page('Courses, page 2', '<ul><li><a href="/courses/msc-ai/">MSc Artificial Intelligence</a></li></ul>' + '<p>Long enough text. </p>' * 12)),
        '/courses/msc-ai/': course('MSc Artificial Intelligence', '<p>Study mode: Full-time. Duration: 12 months. International fee: £26,000 per year. Starts in September.</p>'),
        '/courses/bachelor-degrees/': ('text/html', page('Bachelor degrees', ''.join(f'<p><a href="/courses/x{i}/">Bachelor of Science in Subject {i}</a></p>' for i in range(10)) + '<p>Long enough text. </p>' * 12)),
        '/courses/bsc-computer-science/': course('Computer Science BSc (Hons)', '''
            <p>Study mode: Full-time on campus.</p><p>Duration: 3 years full-time.</p>
            <p>International students: tuition fee £21,500 per year. UK students: £9,250 per year.</p>
            <p>Start dates: September 2027 and January 2028.</p><p>English language: IELTS 6.5 overall with no band below 6.0.</p>'''),
        '/courses/msc-data-science/': course('MSc Data Science', '<p>Full-time, 1 year. International fee: £24,000 per year. You may start in September.</p>'),
        '/courses/bsc-business-online/': course('BSc Business Management (Online)', '<p>Full-time study. International fee: £15,000 per year.</p>'),
        '/courses/msc-finance-distance/': course('MSc Finance', '<p>This course is delivered fully online. International fee: £18,000 per year.</p>'),
        '/courses/phd-physics/': course('PhD Physics', '<p>Full-time on campus. International fee: £20,000 per year.</p>'),
        '/courses/graduate-certificate-business/': course('Graduate Certificate in Business', '<p>Full-time on campus. International fee: £9,000 per year.</p>'),
        '/courses/foundation-engineering/': course('International Foundation Year in Engineering', '<p>Full-time on campus. International fee: £14,000 per year. Leads to a Bachelor of Engineering.</p>'),
        '/courses/ba-history-domestic/': course('Bachelor of Arts in History', '<p>Full-time on campus. This course is available to domestic students only.</p>'),
        '/courses/mba-part-time/': course('Master of Business Administration', '<p>Available part-time only. International fee: £30,000 per year.</p>'),
        '/courses/beng-civil/': course('Bachelor of Engineering (Civil)', '<p>Study mode: On-campus. CRICOS course code: 012345A. Duration: 4 years full-time.</p>'),
        '/courses/ma-media/': course('Master of Arts in Media', '<p>International fee: £17,000 per year. Learn how stories are made.</p>'),
        '/courses/bs-physics/': course('Bachelor of Science in Physics', '<p>This is a full-time course taught on campus. You will study mechanics and waves.</p>'),
        '/courses/beng-mechanical/': course('Mechanical Engineering BEng', '<p>International students pay £22,000 per year in tuition.</p>', '''<script type="application/ld+json">
            {"@context":"https://schema.org","@type":"Course","name":"Mechanical Engineering BEng","timeRequired":"P4Y",
             "hasCourseInstance":{"@type":"CourseInstance","courseMode":"onsite","startDate":"2027-09-01"}}</script>'''),
        '/private/mba/': course('Master of Business Administration', '<p>Full-time on campus. International fee: £30,000 per year.</p>'),
    }


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        HITS.append(self.path)
        pg = EXTRA.get(self.path) or pages().get(self.path)
        if not pg:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(pg[2] if len(pg) > 2 else 200)
        if len(pg) > 3:
            self.send_header('Location', pg[3])
        self.send_header('Content-Type', pg[0] + '; charset=utf-8')
        self.end_headers()
        self.wfile.write(pg[1].encode())


def setUpModule():
    os.environ.pop('GITHUB_STEP_SUMMARY', None)
    srv = HTTPServer(('127.0.0.1', 0), H)
    PORT['p'] = srv.server_address[1]
    PORT['srv'] = srv
    threading.Thread(target=srv.serve_forever, daemon=True).start()


def tearDownModule():
    PORT['srv'].shutdown()


def uni(country='uk'):
    return {'slug': 'test-university', 'name': 'Test University', 'country': country, 'web': f'http://127.0.0.1:{PORT["p"]}/'}


class Levels(unittest.TestCase):
    def test_in_scope(self):
        for title, level in [('Bachelor of Science in Nursing', 'Bachelor'), ('BSc (Hons) Computer Science', 'Bachelor'), ('Computer Science BA', 'Bachelor'),
                             ('BACHELOR OF ARTS', 'Bachelor'), ('LLB Law', 'Bachelor'), ('Master of Science in Online Marketing', 'Master'),
                             ('MSc Data Science', 'Master'), ('MA in History', 'Master'), ('MS in Computer Science', 'Master'), ('MBA', 'Master'),
                             ('Master of Business Administration (MBA)', 'Master'), ('MEng Mechanical Engineering (Hons)', 'Master')]:
            self.assertEqual(L.classify_title(title)[0], level, title)

    def test_out_of_scope(self):
        for title, reason in [('PhD in Physics', 'research-degree'), ('Doctor of Philosophy', 'research-degree'), ('MPhil Economics', 'research-degree'),
                              ('Master of Philosophy', 'research-degree'), ('Graduate Certificate in Business', 'diploma-or-certificate'),
                              ('Postgraduate Diploma in Law', 'diploma-or-certificate'), ('Executive MBA', 'diploma-or-certificate'),
                              ('Pathway to Master of Business', 'foundation-or-pathway'), ('International Foundation Year', 'foundation-or-pathway'),
                              ('Associate of Arts', 'foundation-or-pathway'), ('Master of Data Science (Online)', 'online-or-distance'),
                              ('Online Master of Science in Nursing', 'online-or-distance'), ('Bachelor of Business - Distance Education', 'online-or-distance'),
                              ('Master of Science (Part-time only)', 'part-time-only')]:
            level, _d, _f, out = L.classify_title(title)
            self.assertIsNone(level, title)
            self.assertEqual(out, reason, title)

    def test_words_that_look_like_degrees(self):
        # "ma" and "bs" inside ordinary words, and subjects without a degree, are not degrees
        for title in ['Computer Science', 'Foundations of Biology', 'Mastering Excel', 'Management and Marketing']:
            self.assertIsNone(L.classify_title(title)[0], title)
        self.assertEqual(L.classify_title('Master of Science (Full-time/Part-time)')[0], 'Master')
        self.assertEqual(L.classify_title('MEng Civil Engineering')[2], {'integrated': True})
        self.assertEqual(L.classify_title('Bachelor of Arts/Master of Teaching')[2], {'combined': True})

    def test_online_urls(self):
        self.assertEqual(L.classify_url('https://u.edu/online/courses/mba/'), 'online-or-distance')
        self.assertEqual(L.classify_url('https://u.edu/courses/msc-finance-online/'), 'online-or-distance')
        self.assertEqual(L.classify_url('https://u.edu/courses/pathway-business/'), 'foundation-or-pathway')
        self.assertEqual(L.classify_url('https://u.edu/courses/foundations-of-biology/'), '')
        self.assertEqual(L.classify_url('https://u.edu/pathways/business/'), 'foundation-or-pathway')
        self.assertEqual(L.classify_url('https://u.edu/courses/computer-science/'), '')

    def test_domestic_version_of_a_course_page(self):
        self.assertEqual(L.classify_url('https://adelaide.edu.au/study/degrees/2027/master-of-nursing/dom/'), 'domestic-only')
        self.assertEqual(L.classify_url('https://u.edu/study/domestic/bachelor-of-arts/'), 'domestic-only')
        self.assertEqual(L.classify_url('https://adelaide.edu.au/study/degrees/2027/master-of-nursing/int/'), '')
        self.assertEqual(L.classify_url('https://u.edu/courses/domestic-policy-bachelor/'), '')   # a word inside a name is not a section

    def test_study_mode(self):
        self.assertEqual(L.study_mode(['Study mode: Full-time on campus.'])[0], 'yes')
        self.assertEqual(L.study_mode(['This course is delivered fully online.'])[0], 'no')
        self.assertEqual(L.study_mode(['Available part-time only.'])[0], 'no')
        self.assertEqual(L.study_mode(['Learn about waves.'])[0], 'unclear')
        self.assertEqual(L.study_mode(['You can work full-time during the holidays.'])[0], 'unclear')       # a visa rule, not the course
        self.assertEqual(L.study_mode(['Live on campus in our university halls.'])[0], 'unclear')            # housing, not the course
        self.assertEqual(L.study_mode(['Join our in-person open day.'])[0], 'unclear')
        self.assertEqual(L.study_mode(['Mode of study: Full-time.'])[0], 'yes')
        self.assertEqual(L.study_mode(['Full-time on campus.', 'Also 100% online.'])[0], 'unclear')   # the page says both: a person must look
        self.assertEqual(L.study_mode(['It is not available full-time.'])[0], 'unclear')
        self.assertEqual(L.study_mode([], markup_mode='online')[0], 'no')
        self.assertEqual(L.study_mode([], markup_mode='onsite')[0], 'yes')
        self.assertEqual(L.study_mode(['Full-time.'], url='https://u.edu/online/x/')[0], 'unclear')

    def test_international(self):
        self.assertEqual(L.international(['International students: tuition fee £21,500 per year.'])[:2], ('yes', 'fee'))
        self.assertEqual(L.international(['Learn waves.'], '012345A')[:2], ('yes', 'cricos'))
        self.assertEqual(L.international(['International students can apply online.'])[:2], ('yes', 'page'))
        self.assertEqual(L.international(['This course is only available for international students.'])[:2], ('yes', 'page'))
        self.assertEqual(L.international(['International students. £34,400.'])[:2], ('yes', 'fee'))
        self.assertEqual(L.international(['This course is available to domestic students only.', 'International fee £1,000 a year.'])[0], 'no')
        self.assertEqual(L.international(['Learn waves.'])[0], 'unclear')


class Admissions(unittest.TestCase):
    def test_hub_check(self):
        good = 'International students apply through our online application and must meet the entry requirements below.'
        self.assertTrue(L.hub_check([good], 'https://u.edu/international/admissions/', 'International admissions')[0])
        for sent, url in [('Located in the Student Centre, the International Services Office is a dedicated team that provide a wide range of support.', 'https://u.edu/international/'),
                          ('Events. We coordinate events that are open to all international and domestic students, staff and families.', 'https://u.edu/international/'),
                          (good, 'https://u.edu/international/student-visas/'), (good, 'https://u.edu/news/international-students-apply/'),
                          ('Student visas. To study in Australia, you will need to hold an appropriate visa that permits study.', 'https://u.edu/international/')]:
            self.assertFalse(L.hub_check([sent], url, 'International')[0], sent)

    def test_page_evidence(self):
        self.assertEqual(L.international(['International students can apply for this course.'])[:2], ('yes', 'page'))
        for s in ('English language requirements.', 'IELTS overall 6.5.', 'Master & International Admissions.', 'You need a student visa.'):
            self.assertEqual(L.international([s])[0], 'unclear', s)
        self.assertEqual(L.international(['International students. Tuition.'])[0], 'unclear')      # no amount: not a fee

    def test_not_programme_names_and_addresses(self):
        for n in ('General FAQ', 'Applying to MSBTAI', 'Accountancy Curriculum', "Bachelor's programmes", 'Bachelor education', 'Aboriginal Studies Master Class'):
            self.assertTrue(L.not_programme_name(n), n)
        for n in ("Bachelor's language requirements and exemptions (2026/27)", 'Curriculum & Courses', 'Bachelor of Accounting application',
                  'International students Enrolment in a Higher Semester', 'Desautels Faculty of Management Undergraduate Office',
                  'Beyond AI: Creating Value with AI Amplifiers Presentation Event', "Accelerated master's stream"):
            self.assertTrue(L.not_programme_name(n), n)
        for n in ('Bachelor of Education', 'Master of Strategy and Security', 'Biology, MS', 'MSc Data Science', 'Master of Computer Applications',
                  'MSc Requirements Engineering', 'Bachelor of International Studies', 'BSc Technology and Innovation with Study Abroad'):
            self.assertFalse(L.not_programme_name(n), n)
        self.assertEqual(L.not_programme_url('https://u.edu/x/ms/admissions/requirements-deadlines'), 'programme-subpage')
        self.assertEqual(L.not_programme_url('https://u.edu/study/courses/arch-6006/'), 'course-unit-page')
        self.assertEqual(L.not_programme_url('https://u.edu/malaysia/study/bba', 'uk'), 'other-country-campus')
        self.assertEqual(L.not_programme_url('https://u.edu/malaysia/study/bba', 'malaysia'), '')
        self.assertEqual(L.not_programme_url('https://u.edu/course/706AA/9/2026'), '')


class Facts(unittest.TestCase):
    def sents(self, text):
        return C.sentences_with_labels(T.clean(text))

    def test_fee(self):
        f = F.find_fee(self.sents('International students: tuition fee £21,500 per year. UK students: £9,250 per year.'), 'uk')
        self.assertEqual(f['display'], 'GBP 21,500 a year')
        self.assertIn('21,500', f['context'])
        self.assertIsNone(F.find_fee(self.sents('Tuition fee £9,250 per year for UK students.'), 'uk'))
        self.assertIsNone(F.find_fee(self.sents('International students pay £350 per credit.'), 'uk'))
        self.assertIsNone(F.find_fee(self.sents('International students need £1,334 a month for living costs and a student visa.'), 'uk'))
        # a table row: label in one cell, amount in the next
        f = F.find_fee(self.sents('International students. £18,400 per year.'), 'uk')
        self.assertEqual(f['display'], 'GBP 18,400 a year')
        f = F.find_fee(self.sents('Domestic fee A$9,000 a year, international fee A$38,000 a year.'), 'australia')
        self.assertEqual(f['display'], 'AUD 38,000 a year')

    def test_fee_as_real_pages_write_it(self):
        # a table: "Tuition fees" heading, then one row per fee status, label and amount in separate cells
        table = 'Tuition fees (2026/27). UK students. £9,535. International students. £34,400. Additional costs. There are no additional costs.'
        self.assertEqual(F.find_fee(self.sents(table), 'uk')['display'], 'GBP 34,400')
        self.assertEqual(F.find_fee(self.sents('Tuition fees. UK: £9,535. Overseas: £43,500.'), 'uk')['display'], 'GBP 43,500')
        # a price for the whole course is not a yearly fee
        self.assertIsNone(F.find_fee(self.sents('International tuition, whole course. A$173,188.'), 'australia'))
        f = F.find_fee(self.sents('International tuition, whole course: A$173,188, about A$57,729 a year.'), 'australia')
        self.assertEqual(f['display'], 'AUD 57,729 a year')
        self.assertIsNone(F.find_fee(self.sents('International fee: A$800 per credit point.'), 'australia'))
        # a number with no fee talk on the page is not a fee
        self.assertIsNone(F.find_fee(self.sents('International students. 12,000 students from 140 countries.'), 'uk'))

    def test_duration(self):
        self.assertEqual(F.find_duration(self.sents('Duration: 3 years full-time.'), 'Bachelor')['years'], 3)
        self.assertEqual(F.find_duration(self.sents('Duration: 18 months.'), 'Master')['years'], 1.5)
        self.assertEqual(F.find_duration(self.sents('Length of study: two years.'), 'Master')['display'], '2 years')
        self.assertIsNone(F.find_duration(self.sents('Graduate visa: stay for 2 years after you finish.'), 'Master'))
        self.assertIsNone(F.find_duration(self.sents('Duration: 10 years.'), 'Bachelor'))
        self.assertEqual(F.find_duration(self.sents('Full-time: 3 years. Part-time: 6 years.'), 'Bachelor')['years'], 3)
        self.assertEqual(F.find_duration(self.sents('Full Time (3 Years)'), 'Bachelor')['years'], 3)
        self.assertEqual(F.find_duration(self.sents('Duration 36 months'), 'Bachelor')['years'], 3)

    def test_intakes(self):
        self.assertEqual(F.find_intakes(self.sents('Start dates: September 2027 and January 2028.'))['months'], ['Sep', 'Jan'])
        self.assertIsNone(F.find_intakes(self.sents('Applications close on 30 June for the September start.')))
        self.assertIsNone(F.find_intakes(self.sents('You may start when you are ready.')))     # the verb "may" is not the month
        self.assertEqual(F.find_intakes(self.sents('Intakes: February, July.'))['months'], ['Feb', 'Jul'])

    def test_ielts(self):
        self.assertEqual(F.find_ielts(self.sents('IELTS 6.5 overall with no band below 6.0.'))['overall'], 6.5)
        self.assertEqual(F.find_ielts(self.sents('IELTS (Academic): overall 7.0, no less than 6.5 in any band.'))['overall'], 7.0)
        self.assertEqual(F.find_ielts(self.sents('IELTS 6.5.'))['overall'], 6.5)
        r = F.find_ielts(self.sents('IELTS 6.0 in writing and 6.5 in speaking.'))
        self.assertIsNone(r['overall'])           # ambiguous: keep the sentence, no number
        self.assertIn('IELTS', r['context'])
        self.assertIsNone(F.find_ielts(self.sents('Learn about waves.')))

    def test_field_law_before_engineering(self):
        self.assertEqual(F.find_field('Bachelor in Civil Law'), 'Law')
        self.assertEqual(F.find_field('Civil Engineering BEng'), 'Engineering')

    def test_total_fee(self):
        self.assertIsNone(F.find_fee(['International: £33,900 (Total).'], 'uk'))

    def test_field(self):
        self.assertEqual(F.find_field('Computer Science BSc (Hons)'), 'Computer science and IT')
        self.assertEqual(F.find_field('Master of Science in Data Science'), 'Data science and AI')
        self.assertEqual(F.find_field('Bachelor of Nursing'), 'Medicine and health')
        self.assertIsNone(F.find_field('Bachelor of Science'))


class Reader(unittest.TestCase):
    def read(self, path, **kw):
        fx = Fetcher('Universities500Bot/1.0 (test)', delay=0, timeout=5)
        res = fx.get(f'http://127.0.0.1:{PORT["p"]}{path}')
        pg = X.Page(X.canon(res.final_url), res.text, 'uk', 'Test University')
        return C.read_course(pg, res.text, uni(), '2026-11-16', kw.get('uni_intl'), kw.get('strict', False), kw.get('register'))

    def test_eligible_course(self):
        r, why = self.read('/courses/bsc-computer-science/')
        self.assertEqual(why, '')
        self.assertEqual((r['level'], r['degree'], r['field']), ('Bachelor', 'BSc (Hons)', 'Computer science and IT'))
        self.assertEqual(r['fee']['display'], 'GBP 21,500 a year')
        self.assertEqual(r['duration']['years'], 3)
        self.assertEqual(r['intakes']['months'], ['Sep', 'Jan'])
        self.assertEqual(r['ielts']['overall'], 6.5)
        self.assertEqual(r['international']['how'], 'fee')
        self.assertIn('Full-time on campus', r['studyMode']['evidence'])
        self.assertEqual(r['firstSeen'], '2026-11-16')
        self.assertEqual(Q.problem(r), '')

    def test_master_with_missing_facts_stays_empty(self):
        r, why = self.read('/courses/msc-data-science/')
        self.assertEqual(why, '')
        self.assertEqual(r['level'], 'Master')
        self.assertEqual(r['fee']['display'], 'GBP 24,000 a year')
        self.assertEqual(r['duration']['display'], '1 year')
        self.assertEqual(r['intakes']['months'], ['Sep'])
        self.assertIsNone(r['ielts'])
        self.assertIsNone(r['cricos'])

    def test_what_is_left_out(self):
        for path, reason in [('/courses/bsc-business-online/', 'online-or-distance'), ('/courses/msc-finance-distance/', 'online-or-part-time'),
                             ('/courses/phd-physics/', 'research-degree'), ('/courses/graduate-certificate-business/', 'diploma-or-certificate'),
                             ('/courses/foundation-engineering/', 'foundation-or-pathway'), ('/courses/ba-history-domestic/', 'domestic-only'),
                             ('/courses/mba-part-time/', 'online-or-part-time'), ('/courses/ma-media/', 'study-mode-unclear'),
                             ('/courses/bachelor-degrees/', 'listing-page'), ('/courses/', 'not-a-course-page')]:
            r, why = self.read(path)
            self.assertIsNone(r, path)
            self.assertEqual(why, reason, path)

    def test_cricos_and_markup(self):
        r, why = self.read('/courses/beng-civil/')
        self.assertEqual(why, '')
        self.assertEqual((r['cricos'], r['international']['how']), ('012345A', 'cricos'))
        r, why = self.read('/courses/beng-mechanical/')
        self.assertEqual(why, '')
        self.assertEqual(r['duration']['years'], 4)
        self.assertEqual(r['intakes']['months'], ['Sep'])
        self.assertIn('onsite', r['studyMode']['evidence'])

    def test_university_wide_international_evidence(self):
        ev = {'url': 'http://x/international/', 'evidence': 'International students can apply online from October.'}
        r, why = self.read('/courses/bs-physics/')
        self.assertEqual(why, 'international-unclear')
        r, why = self.read('/courses/bs-physics/', uni_intl=ev)
        self.assertEqual(why, '')
        self.assertEqual(r['international']['how'], 'university')
        r, why = self.read('/courses/bs-physics/', uni_intl=ev, strict=True)
        self.assertEqual(why, 'international-unclear')
        # a page that says "domestic only" is never rescued by the university-wide statement
        r, why = self.read('/courses/ba-history-domestic/', uni_intl=ev)
        self.assertEqual(why, 'domestic-only')

    def test_pages_about_a_programme_are_not_the_programme(self):
        ok = '<p>Full-time on campus. International fee: £22,000 a year. Duration: 1 year full-time.</p>'
        EXTRA.update({
            '/courses/msc-data-science/faq/': course('MSc Data Science', ok),                       # a sub-page: FAQ
            '/study/courses/indg-5011/': course('Master Class in Aboriginal Studies', ok),           # one unit inside a degree
            '/dubai/study/bba/': course('BBA (Hons) Bachelor of Business Administration', ok),       # a branch campus in another country
            '/courses/msc-apply/': course('Applying to MSc Data Science', ok),                       # a "how to apply" page
            '/courses/msc-general/': course('General FAQ', ok, '<meta property="og:title" content="Master programmes FAQ">'),
        })
        try:
            for path, why in [('/courses/msc-data-science/faq/', 'programme-subpage'), ('/study/courses/indg-5011/', 'course-unit-page'),
                              ('/dubai/study/bba/', 'other-country-campus'), ('/courses/msc-apply/', 'not-a-programme-name')]:
                r, got = self.read(path)
                self.assertIsNone(r, path)
                self.assertEqual(got, why, path)
        finally:
            EXTRA.clear()

    def test_mixed_delivery_is_held_for_a_look(self):
        EXTRA['/courses/msc-blended/'] = course('MSc Data Science Blended', '<p>Full-time. Your studies will be on-campus, and may include some online delivery. International fee: £22,000 a year.</p>')
        EXTRA['/courses/msc-blend2/'] = course('MSc Data Science Mixed', '<p>This full-time programme blends on-campus teaching with online coursework. International fee: £22,000 a year.</p>')
        try:
            for path in ('/courses/msc-blended/', '/courses/msc-blend2/'):
                r, why = self.read(path)
                self.assertIsNone(r, path)
                self.assertEqual(why, 'study-mode-unclear', path)
        finally:
            EXTRA.clear()

    def test_total_price_is_not_a_yearly_fee(self):
        EXTRA['/courses/msc-total/'] = course('MSc Data Science Total', '<p>Full-time on campus.</p><p>International: £33,900 (Total).</p><p>Duration: 1 year full-time.</p>')
        try:
            r, why = self.read('/courses/msc-total/')
            self.assertEqual(why, '')                 # an international price shows international students are taken ...
            self.assertIsNone(r['fee'])               # ... but a price tagged "total" is never shown as a yearly fee
        finally:
            EXTRA.clear()

    def test_english_test_and_visa_lines_are_not_proof_of_international_places(self):
        EXTRA['/courses/msc-ielts/'] = course('MSc Data Science IELTS', '<p>Full-time on campus.</p><p>English language requirements.</p><p>IELTS overall 6.5. You may need a student visa.</p>')
        try:
            r, why = self.read('/courses/msc-ielts/')
            self.assertEqual(why, 'international-unclear')
        finally:
            EXTRA.clear()

    def test_nested_menu_blocks_do_not_crash_the_page_reader(self):
        nav = '<div role="navigation" class="menu"><div role="search" class="menu"><span class="menu">x</span></div></div>'
        EXTRA['/courses/msc-nested/'] = course('MSc Data Science Nested', nav + '<p>Full-time on campus. International fee: £22,000 a year.</p>')
        try:
            r, why = self.read('/courses/msc-nested/')
            self.assertEqual(why, '')
            self.assertEqual(r['fee']['display'], 'GBP 22,000 a year')
        finally:
            EXTRA.clear()

    def test_programme_name_skips_a_generic_heading(self):
        EXTRA['/study/courses/bachelor-of-commerce/'] = course('Study', '<p>Full-time on campus. International fee: £22,000 a year.</p>',
                                                               '<meta property="og:title" content="Bachelor of Commerce">')
        try:
            r, why = self.read('/study/courses/bachelor-of-commerce/')
            self.assertEqual(why, '')
            self.assertEqual(r['name'], 'Bachelor of Commerce')
        finally:
            EXTRA.clear()


def reg_course(code, name, level='Bachelor', weeks=156, tuition=105700, **kw):
    c = {'code': code, 'name': name, 'level': level, 'weeks': weeks, 'tuition': tuition, 'nonTuition': 2172, 'field': 'Science', 'places': [['Perth', 'WA']]}
    c.update(kw)
    return c


def register(*courses):
    return K.Register({'slug': 'test-university', 'courses': list(courses)})


class Register(unittest.TestCase):
    """The government register of courses for international students (CRICOS): what it adds, and what it must never do."""

    def test_register_files_from_the_four_csvs(self):
        head = 'CRICOS Provider Code,Institution Name,CRICOS Course Code,Course Name,VET National Code,Dual Qualification,Field of Education 1 Broad Field,Course Level,Duration (Weeks),Tuition Fee,Non Tuition Fee,Expired\n'
        rows = [
            '00001A,Test University,111111A,Bachelor of Science,,No,01 - Natural and Physical Sciences,Bachelor Degree,156,"$105,700.00",$150.00,No',
            '00001A,Test University,222222B,Master of Data Science,,No,02 - Information Technology,Masters Degree (Coursework),104,$0.00,,No',
            '00001A,Test University,333333C,Doctor of Philosophy,,No,01 - Natural and Physical Sciences,Doctoral Degree,156,"$40,000.00",,No',
            '00001A,Test University,444444D,Doctor of Medicine,,No,06 - Health,Masters Degree (Extended),208,"$300,000.00",,No',
            '00001A,Test University,555555E,Master of Law,,No,09 - Society and Culture,Masters Degree (Coursework),52,"$40,000.00",,Yes',
            '00001A,Test University,666666F,Bachelor of Arts and Diploma of Languages,,No,09 - Society and Culture,Bachelor Degree,156,"$90,000.00",,No',
            '00001A,Test University,777777G,Bachelor of Arts / Master of Teaching,,No,07 - Education,Masters Degree (Coursework),260,"$150,000.00",,No',
            '00002B,Another University,888888H,Bachelor of Science,,No,01 - Natural and Physical Sciences,Bachelor Degree,156,"$100,000.00",,No']
        locs = ('CRICOS Provider Code,Institution Name,CRICOS Course Code,Location Name,Location City,Location State\n'
                '00001A,Test University,111111A,Main campus,PERTH,WA\n00001A,Test University,111111A,City campus,PERTH,WA\n00001A,Test University,111111A,North campus,Joondalup,WA\n')
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'CRICOS_Courses.csv').write_text('\ufeff' + head + '\n'.join(rows) + '\n', encoding='utf-8')
            (Path(d) / 'CRICOS_Course_Locations.csv').write_text('\ufeff' + locs, encoding='utf-8')
            docs, stats = K.build(d, {'test-university': ['00001A']})
        got = {c['code']: c for c in docs['test-university']['courses']}
        self.assertEqual(sorted(got), ['111111A', '222222B', '777777G'])        # doctorate, "Doctor of ...", expired and a bundled diploma are left out
        self.assertEqual(dict(stats['left_out']), {'level': 1, 'doctor-titled': 1, 'expired': 1, 'diploma-or-certificate-in-name': 1})
        a = got['111111A']
        self.assertEqual((a['level'], a['weeks'], a['tuition'], a['nonTuition'], a['field']), ('Bachelor', 156, 105700, 150, 'Natural and Physical Sciences'))
        self.assertEqual(a['places'], [['Perth', 'WA'], ['Joondalup', 'WA']])      # one entry per place, capitals tidied
        self.assertIsNone(got['222222B']['tuition'])                                # $0 means "not published", never a free course
        self.assertTrue(got['777777G'].get('combined'))
        self.assertTrue(K.dump(docs['test-university']).count('\n{"code"') == 3)
        json.loads(K.dump(docs['test-university']))

    def test_unique_name_match(self):
        r = register(reg_course('000111A', 'Bachelor of Science in Physics'), reg_course('000222B', 'Master of Data Science', 'Master', 104),
                     reg_course('000333C', 'Master of Teaching'), reg_course('000444D', 'Master of Teaching', 'Master', 78))
        self.assertEqual(r.unique('Bachelor of Science in Physics'), '000111A')
        self.assertEqual(r.unique('bachelor  of science in PHYSICS'), '000111A')           # case and spacing do not matter
        self.assertEqual(r.unique('Data Science', 'Bachelor of Data Science'), '')        # another degree in the same subject is another course
        self.assertEqual(r.unique('Data Science', 'Master of Data Science'), '000222B')   # the heading leaves the degree out
        self.assertEqual(r.unique('Master of Teaching'), '')                              # two registered courses: cannot tell which
        self.assertEqual(r.unique('Bachelor of Science'), '')
        self.assertEqual(r.get('000111a')['name'], 'Bachelor of Science in Physics')

    def test_years_from_weeks(self):
        self.assertEqual(K.years_from_weeks(156, 'Bachelor')['display'], '3 years')
        self.assertEqual(K.years_from_weeks(78, 'Master')['display'], '1.5 years')
        self.assertEqual(K.years_from_weeks(52, 'Master')['display'], '1 year')
        self.assertIsNone(K.years_from_weeks(416, 'Bachelor'))                            # eight years: not a normal Bachelor's, left for the page
        self.assertIsNone(K.years_from_weeks(None, 'Master'))
        self.assertTrue(K.years_from_weeks(104, 'Master')['context'].startswith('Government register'))

    def read(self, path, reg):
        fx = Fetcher('Universities500Bot/1.0 (test)', delay=0, timeout=5)
        res = fx.get(f'http://127.0.0.1:{PORT["p"]}{path}')
        pg = X.Page(X.canon(res.final_url), res.text, 'australia', 'Test University')
        return C.read_course(pg, res.text, uni('australia'), '2026-11-17', None, False, reg)

    def test_a_registered_name_makes_a_course_open_to_international_students(self):
        # this page never says international students can apply, so without the register it is held back
        r, why = self.read('/courses/bs-physics/', None)
        self.assertEqual(why, 'international-unclear')
        r, why = self.read('/courses/bs-physics/', register(reg_course('000111A', 'Bachelor of Science in Physics')))
        self.assertEqual(why, '')
        self.assertEqual((r['cricos'], r['cricosMatch'], r['international']['how']), ('000111A', 'name', 'cricos'))
        self.assertIn('does not show the code', r['international']['evidence'])
        self.assertEqual(Q.problem(r), '')

    def test_two_registered_courses_with_one_name_are_not_guessed(self):
        reg = register(reg_course('000111A', 'Bachelor of Science in Physics'), reg_course('000222B', 'Bachelor of Science in Physics', weeks=208))
        r, why = self.read('/courses/bs-physics/', reg)
        self.assertEqual((r, why), (None, 'international-unclear'))

    def test_a_code_on_the_page_comes_first(self):
        r, why = self.read('/courses/beng-civil/', register(reg_course('999999Z', 'Bachelor of Engineering (Civil)')))
        self.assertEqual(why, '')
        self.assertEqual((r['cricos'], r['cricosMatch']), ('012345A', None))

    def test_register_never_replaces_what_the_page_says_about_international_students(self):
        # the page shows an international fee: that sentence stays the evidence, the register only adds the code
        r, why = self.read('/courses/msc-data-science/', register(reg_course('000222B', 'MSc Data Science', 'Master', 52)))
        self.assertEqual(why, '')
        self.assertEqual((r['international']['how'], r['cricos'], r['cricosMatch']), ('fee', '000222B', 'name'))
        # a page that says "domestic only" is never rescued by a name match
        r, why = self.read('/courses/ba-history-domestic/', register(reg_course('000333C', 'Bachelor of Arts in History')))
        self.assertEqual(why, 'domestic-only')

    def test_site_record_adds_the_register_entry_and_never_the_fee(self):
        base = SiteData.rec(None, 'Bachelor of Science in Physics', 'https://u.edu/p/', degree='Bachelor of Science', level='Bachelor', duration=None, fee=None)
        reg = register(reg_course('000111A', 'Bachelor of Science in Physics'))
        it = B.site_record(base, 'test-university', reg)
        self.assertEqual((it['cricos'], it['cricosMatch']), ('000111A', 'name'))
        self.assertEqual((it['reg']['weeks'], it['reg']['tuition'], it['reg']['currency']), (156, 105700, 'AUD'))
        self.assertIsNone(it['fee'])                                                  # the older whole-course figure is not the fee
        self.assertEqual(it['duration']['display'], '3 years')                        # length is filled only because the page gave none
        self.assertTrue(it['duration']['context'].startswith('Government register'))
        # a length the page gave is kept
        page_len = {'display': '4 years', 'years': 4, 'context': 'Duration: 4 years.'}
        it = B.site_record(dict(base, duration=page_len), 'test-university', reg)
        self.assertEqual(it['duration'], page_len)
        # a different level is not the same course, unless the name shows a combined degree
        it = B.site_record(dict(base, level='Master', degree='MSc'), 'test-university', reg)
        self.assertNotIn('reg', it)
        # no register, no entry
        self.assertNotIn('reg', B.site_record(base, 'test-university', None))

    def test_site_build_reads_register_files_and_credits_them(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as k:
            rec = SiteData.rec(None, 'Bachelor of Science in Physics', 'https://u.edu/p/', degree='Bachelor of Science', level='Bachelor', duration=None, fee=None)
            (Path(d) / 'u.json').write_text(json.dumps({'slug': 'u', 'status': 'ok', 'generatedAt': '2026-11-17T10:00:00Z', 'courses': [rec]}))
            (Path(k) / 'u.json').write_text(K.dump({'slug': 'u', 'providers': ['00001A'], 'courses': [reg_course('000111A', 'Bachelor of Science in Physics')]}))
            (Path(k) / 'providers.json').write_text(json.dumps({'source': {'name': 'CRICOS', 'by': 'Department of Education', 'licence': 'CC BY 2.5 AU', 'url': 'https://data.gov.au/data/dataset/cricos', 'downloaded': '2026-11-17'}}))
            doc, stats = B.build(d, k)
            self.assertEqual(doc['items'][0]['reg']['code'], '000111A')
            self.assertEqual(doc['register']['licence'], 'CC BY 2.5 AU')
            doc, stats = B.build(d, Path(d) / 'nowhere')                              # a university without register files still builds
            self.assertNotIn('reg', doc['items'][0])


class Crawl(unittest.TestCase):
    def run_crawl(self, **kw):
        del HITS[:]
        fx = Fetcher('Universities500Bot/1.0 (test)', delay=0, timeout=5)
        return crawl.crawl_university(uni(), fx, '2026-11-16', max_pages=kw.pop('max_pages', 60), **kw)

    def test_crawl_finds_the_right_courses(self):
        r = self.run_crawl()
        names = sorted(rec['name'] for rec in r['records'].values())
        self.assertEqual(names, ['Bachelor of Engineering (Civil)', 'Bachelor of Science in Physics', 'Computer Science BSc (Hons)', 'MSc Artificial Intelligence',
                                 'MSc Data Science', 'Mechanical Engineering BEng'])
        self.assertTrue(r['intlOpen']['url'].endswith('/international/'))
        phys = next(x for x in r['records'].values() if x['name'].endswith('Physics'))
        self.assertEqual(phys['international']['how'], 'university')
        self.assertFalse(any(h.startswith('/private/') for h in HITS), 'must not request disallowed paths')
        self.assertFalse(any(h.startswith('/de/') or h.startswith('/news/') for h in HITS), 'must not fetch other-language or news pages')
        self.assertIn('/courses/?page=2', HITS)        # pages of a list are followed
        for reason in ('skipped-by-address:online-or-distance', 'skipped-by-address:research-degree', 'skipped-by-address:foundation-or-pathway',
                       'diploma-or-certificate', 'domestic-only', 'online-or-part-time', 'study-mode-unclear', 'robots-blocked-page'):
            self.assertIn(reason, r['reasons'], reason)
        self.assertTrue(r['samples']['domestic-only'][0].endswith('/courses/ba-history-domestic/'))

    def test_strict_international(self):
        r = self.run_crawl(strict_international=True)
        self.assertNotIn('Bachelor of Science in Physics', [x['name'] for x in r['records'].values()])
        self.assertIn('international-unclear', r['reasons'])

    def test_page_budget(self):
        r = self.run_crawl(max_pages=5)
        self.assertEqual(r['pages'], 5)
        self.assertEqual(len(HITS) - sum(1 for h in HITS if h in ('/robots.txt', '/sitemap.xml', '/')), 5)

    def test_known_pages_are_refreshed_first(self):
        first = self.run_crawl()
        prev = {'courses': list(first['records'].values()), 'seen': first['seen'], 'intlOpen': first['intlOpen']}
        # everything read 20 days ago: due again; pages never read are fetched with what is left
        for rec in prev['courses']:
            rec['lastVerified'] = '2026-10-27'
        prev['seen'] = {u: ['2026-10-27', e[1]] for u, e in prev['seen'].items()}
        r = self.run_crawl(prev=prev, max_pages=10)
        self.assertGreaterEqual(r['knownRead'], 6)
        self.assertLessEqual(r['knownRead'], 6)          # 60% of 10
        # pages read three days ago are not due: not asked again
        prev['seen'] = {u: ['2026-11-13', e[1]] for u, e in first['seen'].items()}
        r = self.run_crawl(prev=prev, max_pages=60)
        asked = {u for u in r['results']}
        self.assertFalse(any(u.endswith('/courses/msc-data-science/') for u in asked))

    def test_robots_blocked_and_unreachable(self):
        fx = Fetcher('Universities500Bot/1.0 (test)', delay=0, timeout=5)
        u = dict(uni(), web=f'http://127.0.0.1:{PORT["p"]}/private/home/')
        r = crawl.crawl_university(u, fx, '2026-11-16', max_pages=5)
        self.assertEqual((r['status'], r['robotsReason']), ('robots', 'disallow'))
        u = dict(uni(), web='http://127.0.0.1:1/')
        r = crawl.crawl_university(u, fx, '2026-11-16', max_pages=5)
        self.assertEqual(r['status'], 'unreachable')


class Robust(unittest.TestCase):
    def fx(self):
        return Fetcher('Universities500Bot/1.0 (test)', delay=0, timeout=5)

    def test_robots_txt_that_moves_is_followed(self):
        EXTRA['/robots.txt'] = ('text/plain', '', 301, '/real-robots.txt')
        EXTRA['/real-robots.txt'] = ('text/plain', 'User-agent: *\nDisallow: /private/\n')
        try:
            fx = self.fx()
            base = f'http://127.0.0.1:{PORT["p"]}'
            self.assertTrue(fx.allowed(f'{base}/courses/'))
            self.assertFalse(fx.allowed(f'{base}/private/x'))      # the rules came through the move
            self.assertEqual(fx.robots_status[f'127.0.0.1:{PORT["p"]}'], 200)
        finally:
            EXTRA.clear()

    def test_unreadable_robots_says_why(self):
        import urllib.robotparser
        fx = self.fx()
        host = f'127.0.0.1:{PORT["p"]}'
        fx._robots[('http', host)] = (urllib.robotparser.RobotFileParser(), 'deny')
        fx.robots_detail[host] = 'HTTP 502'
        self.assertEqual(fx.robots_note(f'http://{host}/'), 'robots.txt could not be read (HTTP 502)')

    def test_odd_addresses_are_cleaned(self):
        from fetcher import clean_url
        self.assertEqual(clean_url('https://x.ac.uk/agri-fut\nure/a b/'), 'https://x.ac.uk/agri-future/a%20b/')
        self.assertEqual(clean_url('https://x.de/studium/Über uns'), 'https://x.de/studium/%C3%9Cber%20uns')
        self.assertEqual(clean_url('https://münchen.de/a'), 'https://xn--mnchen-3ya.de/a')
        self.assertEqual(clean_url('https://x.org/a%20b/'), 'https://x.org/a%20b/')       # already encoded: left alone
        EXTRA['/courses/msc x/'] = course('MSc Data Science Space', '<p>Full-time on campus.</p>')
        EXTRA['/courses/msc%20x/'] = EXTRA['/courses/msc x/']
        try:
            res = self.fx().get(f'http://127.0.0.1:{PORT["p"]}/courses/msc x/')
            self.assertTrue(res.ok, res.error)
        finally:
            EXTRA.clear()

    def test_one_bad_page_does_not_stop_the_university(self):
        from unittest import mock
        real = C.read_course

        def flaky(page, html, uni_, today, *a, **k):
            if 'msc-data-science' in page.url:
                raise RuntimeError('boom')
            return real(page, html, uni_, today, *a, **k)

        with mock.patch.object(crawl.C, 'read_course', flaky):
            out = crawl.crawl_university(uni(), Fetcher('Universities500Bot/1.0 (test)', delay=0, timeout=5), '2026-11-16', max_pages=40)
        self.assertEqual(out['status'], 'ok')
        self.assertTrue(any(v == 'page-error' for v in out['results'].values()))
        self.assertTrue(out['pageErrors'] and 'boom' in out['pageErrors'][0])
        self.assertTrue(any(r['name'].startswith('Computer Science') for r in out['records'].values()))   # the other courses were still read


class Runner(unittest.TestCase):
    def run_main(self, tmp, today, *extra):
        env = {k: v for k, v in os.environ.items() if k != 'GITHUB_STEP_SUMMARY'}
        unis = Path(tmp) / 'universities.json'
        if not unis.exists():
            unis.write_text(json.dumps([
                uni(),
                dict(uni(), slug='blocked-university', name='Blocked University', web=f'http://127.0.0.1:{PORT["p"]}/private/home/'),
                dict(uni(), slug='down-university', name='Down University', web='http://127.0.0.1:1/')]))
        cmd = [sys.executable, str(HERE / 'run.py'), '--universities', str(unis), '--out-dir', str(Path(tmp) / 'courses'), '--report', str(Path(tmp) / 'out'),
               '--delay', '0', '--workers', '3', '--max-pages', '60', '--today', today, '--refresh-days', '0', '--held-days', '0', *extra]
        return subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=120)

    def doc(self, tmp, slug='test-university'):
        return json.loads((Path(tmp) / 'courses' / f'{slug}.json').read_text())

    def test_runs_merge_and_drop(self):
        EXTRA.clear()
        with tempfile.TemporaryDirectory() as tmp:
            p = self.run_main(tmp, '2026-11-16')
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            d = self.doc(tmp)
            self.assertEqual(d['counts']['eligible'], 6)
            self.assertEqual(d['status'], 'ok')
            self.assertIn('domestic-only', d['counts']['held'])
            ds = next(c for c in d['courses'] if c['name'] == 'MSc Data Science')
            self.assertEqual((ds['firstSeen'], ds['lastVerified'], ds['lastChanged']), ('2026-11-16',) * 3)
            self.assertEqual(self.doc(tmp, 'blocked-university')['status'], 'robots')
            self.assertEqual(self.doc(tmp, 'down-university')['status'], 'unreachable')
            csv_text = (Path(tmp) / 'out' / 'universities.csv').read_text()
            self.assertIn('test-university,uk,ok', csv_text)
            self.assertIn('robots', csv_text)
            self.assertIn('Eligible courses now: **6**', (Path(tmp) / 'out' / 'course_report.md').read_text())

            # run 2: one page changed, one page gone
            EXTRA['/courses/msc-data-science/'] = course('MSc Data Science', '<p>Full-time, 1 year. International fee: £25,500 per year.</p>')
            EXTRA['/courses/msc-ai/'] = ('text/html', '', 404)
            p = self.run_main(tmp, '2026-12-01', '--only', 'test-university,blocked-university')
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            d = self.doc(tmp)
            ds = next(c for c in d['courses'] if c['name'] == 'MSc Data Science')
            self.assertEqual((ds['firstSeen'], ds['lastVerified'], ds['lastChanged']), ('2026-11-16', '2026-12-01', '2026-12-01'))
            self.assertEqual(ds['fee']['display'], 'GBP 25,500 a year')
            cs = next(c for c in d['courses'] if c['name'].startswith('Computer Science'))
            self.assertEqual((cs['lastVerified'], cs['lastChanged']), ('2026-12-01', '2026-11-16'))     # read again, nothing changed
            ai = next(c for c in d['courses'] if c['name'] == 'MSc Artificial Intelligence')
            self.assertEqual(ai['misses'], 1)                  # kept for now, a page can be down for a day
            # the website that could not be read keeps its old state
            self.assertEqual(self.doc(tmp, 'blocked-university')['courses'], [])
            self.run_main(tmp, '2026-12-15', '--only', 'test-university,blocked-university')
            p = self.run_main(tmp, '2027-01-01', '--only', 'test-university,blocked-university')
            names = [c['name'] for c in self.doc(tmp)['courses']]
            self.assertNotIn('MSc Artificial Intelligence', names)      # gone for three runs in a row
            self.assertEqual(len(names), 5)
        EXTRA.clear()

    def test_shard_and_only(self):
        EXTRA.clear()
        with tempfile.TemporaryDirectory() as tmp:
            p = self.run_main(tmp, '2026-11-16', '--shard', '1/3')
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            files = sorted(x.name for x in (Path(tmp) / 'courses').glob('*.json'))
            self.assertEqual(files, ['blocked-university.json'])      # slugs sorted: blocked, down, test; shard 1 of 3 = the first
            p = self.run_main(tmp, '2026-11-16', '--only', 'test-university')
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertTrue((Path(tmp) / 'courses' / 'test-university.json').exists())

    def test_site_trouble_counts_no_misses(self):
        EXTRA.clear()
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(Path(tmp) / 'courses')
            fake = {'slug': 'test-university', 'courses': [
                dict(name=f'Fake {i} BSc', degree='BSc', level='Bachelor', url=f'http://127.0.0.1:{PORT["p"]}/gone/{i}/', university='test-university', lastVerified='2026-10-01',
                     studyMode={'verdict': 'full-time on campus'}, international={'how': 'fee', 'evidence': 'International students: GBP 24,000 a year.'}, hash='x', firstSeen='2026-10-01', lastChanged='2026-10-01', misses=2)
                for i in range(120)], 'seen': {}}
            (Path(tmp) / 'courses' / 'test-university.json').write_text(json.dumps(fake))
            # every known page answers 404 at once: the website probably changed its addresses, so no course is marked as missing
            p = self.run_main(tmp, '2026-11-16', '--only', 'test-university', '--max-pages', '300')
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            d = self.doc(tmp)
            self.assertEqual(d['counts']['eligible'], 126)
            self.assertTrue(all(c.get('misses', 0) == 2 for c in d['courses'] if c['name'].startswith('Fake')))

    def test_safety_gate(self):
        EXTRA.clear()
        for i in range(120):
            EXTRA[f'/fake/{i}/'] = ('text/html', page('About the department', '<p>We are a friendly department with many staff and students.</p>' * 8))
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(Path(tmp) / 'courses')
            fake = {'slug': 'test-university', 'courses': [
                dict(name=f'Fake {i} BSc', degree='BSc', level='Bachelor', url=f'http://127.0.0.1:{PORT["p"]}/fake/{i}/', university='test-university', lastVerified='2026-10-01',
                     studyMode={'verdict': 'full-time on campus'}, international={'how': 'fee', 'evidence': 'International students: GBP 24,000 a year.'}, hash='x', firstSeen='2026-10-01', lastChanged='2026-10-01', misses=2)
                for i in range(120)], 'seen': {}}
            path = Path(tmp) / 'courses' / 'test-university.json'
            path.write_text(json.dumps(fake))
            before = path.read_text()
            # the pages load, but none of them is a course any more, for the third run in a row: 120 courses would vanish at once
            p = self.run_main(tmp, '2026-11-16', '--only', 'test-university', '--max-pages', '300')
            self.assertEqual(p.returncode, 3, p.stdout + p.stderr)
            self.assertEqual(path.read_text(), before, 'nothing may be written when the gate stops the run')
            self.assertIn('Stopped', (Path(tmp) / 'out' / 'course_report.md').read_text())
            p = self.run_main(tmp, '2026-11-16', '--only', 'test-university', '--max-pages', '300', '--allow-drop')
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertEqual(self.doc(tmp)['counts']['eligible'], 6)
        EXTRA.clear()


class Merge(unittest.TestCase):
    def rec(self, url, name='MSc Data Science'):
        return dict(id='x', university='u', name=name, degree='MSc', level='Master', url=url, studyMode={'verdict': 'full-time on campus'},
                    international={'how': 'fee', 'evidence': 'International students: GBP 24,000 a year.'}, firstSeen='2026-10-01', lastVerified='2026-10-01', lastChanged='2026-10-01', hash='h1')

    def test_redirected_address_keeps_one_record(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('course_run', HERE / 'run.py')   # 'run' alone would be the scholarship runner
        run = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(run)
        u = {'slug': 'u', 'name': 'U', 'country': 'uk'}
        prev = {'courses': [self.rec('https://u.edu/old/')], 'seen': {}}
        new = dict(self.rec('https://u.edu/new/'), firstSeen='2026-11-16', lastVerified='2026-11-16', lastChanged='2026-11-16')
        out = {'status': 'ok', 'note': '', 'pages': 1, 'results': {'https://u.edu/old/': 'ok'}, 'records': {'https://u.edu/old/': new}, 'seen': {},
               'reasons': {}, 'samples': {}, 'knownRead': 1, 'knownFailed': 0}
        doc, st = run.merge(u, prev, out, '2026-11-16', '2026-11-16T00:00:00Z')
        self.assertEqual([c['url'] for c in doc['courses']], ['https://u.edu/new/'])
        self.assertEqual(doc['courses'][0]['firstSeen'], '2026-10-01')      # the history of the course is kept

    def test_same_programme_under_several_years_is_kept_once(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('course_run2', HERE / 'run.py')
        run = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(run)
        recs = {u: dict(self.rec(u, 'Bachelor of Business Informatics'), name='Bachelor of Business Informatics', level='Bachelor')
                for u in ('https://u.edu/course/706AA/9/2026', 'https://u.edu/course/706AA/9/2027', 'https://u.edu/course/706AA/8/2023')}
        recs['https://u.edu/course/706AA/9/2027']['fee'] = {'display': 'AUD 30,000 a year'}
        drop = run.duplicates(recs)
        self.assertEqual(sorted(drop), ['https://u.edu/course/706AA/8/2023', 'https://u.edu/course/706AA/9/2026'])    # the one with a fee stays
        other = {'https://u.edu/a/': self.rec('https://u.edu/a/', 'MSc A'), 'https://u.edu/b/': self.rec('https://u.edu/b/', 'MSc B')}
        self.assertEqual(run.duplicates(other), [])


class Quality(unittest.TestCase):
    def good(self):
        return dict(name='MSc Data Science', degree='MSc', level='Master', url='https://u.edu/c/', lastVerified='2026-11-16',
                    studyMode={'verdict': 'full-time on campus'}, international={'how': 'fee', 'evidence': 'International students: GBP 24,000 a year.'}, duration={'years': 1}, fee={'display': 'GBP 24,000 a year'})

    def test_problem(self):
        self.assertEqual(Q.problem(self.good()), '')
        for change, why in [({'url': ''}, 'no-source-url'), ({'level': 'PhD'}, 'bad-level'), ({'name': 'Courses'}, 'bad-name'),
                            ({'studyMode': {'verdict': 'unclear'}}, 'not-full-time-on-campus'), ({'international': {}}, 'no-international-evidence'),
                            ({'duration': {'years': 9}}, 'duration-out-of-range'), ({'fee': {'display': 'GBP'}}, 'fee-without-number'),
                            ({'name': 'PhD Data Science', 'degree': ''}, 'research-degree'), ({'name': 'General FAQ'}, 'not-a-programme-name'),
                            ({'url': 'https://u.edu/study/courses/arch-6006/'}, 'course-unit-page'),
                            ({'international': {'how': 'page', 'evidence': 'English language requirements.'}}, 'weak-international-evidence'),
                            ({'international': {'how': 'fee', 'evidence': 'International students. Tuition.'}}, 'weak-international-evidence'),
                            ({'studyMode': {'verdict': 'full-time on campus', 'evidence': 'On-campus, and may include some online delivery.'}}, 'mixed-delivery')]:
            r = self.good()
            r.update(change)
            self.assertEqual(Q.problem(r), why, change)
        r = self.good()
        r['fee'] = {'display': 'GBP 33,900 a year', 'context': 'International: £33,900 (Total).'}
        self.assertEqual(Q.problem(r), '')
        self.assertIsNone(r['fee'])        # a record saved with a total price as its fee loses the fee, not the course


class SiteData(unittest.TestCase):
    """The file the website reads: only checked records, with the sentence each fact came from, one stable page address per course."""

    def rec(self, name, url, **kw):
        r = dict(id=f'u:{T.slugify(name, 60)}:abc123', university='u', name=name, degree='MSc', level='Master', field=None, url=url, lastVerified='2026-11-16',
                 firstSeen='2026-11-01', lastChanged='2026-11-16', studyMode={'verdict': 'full-time on campus', 'evidence': 'Full-time, on campus.'},
                 international={'how': 'fee', 'evidence': 'International students: GBP 24,000 a year.'}, duration={'display': '1 year', 'years': 1, 'context': 'Duration: 1 year.'},
                 fee={'display': 'GBP 24,000 a year', 'context': 'International students: GBP 24,000 a year.'}, ielts=None, intakes=None, cricos=None, flags=None, hash='x')
        r.update(kw)
        return r

    def build(self, courses):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'u.json').write_text(json.dumps({'slug': 'u', 'status': 'ok', 'generatedAt': '2026-11-16T10:00:00Z', 'courses': courses, 'seen': {'x': 1}}))
            return B.build(d)

    def test_kept_and_dropped(self):
        doc, stats = self.build([self.rec('MSc Data Science', 'https://u.edu/ds/'), self.rec('General FAQ', 'https://u.edu/faq-page/'),
                                 self.rec('MSc Law', 'https://u.edu/law/', studyMode={'verdict': 'unclear', 'evidence': ''})])
        self.assertEqual([i['name'] for i in doc['items']], ['MSc Data Science'])
        self.assertEqual(stats['read'], 3)
        self.assertEqual(stats['checks'], {'not-a-programme-name': 1, 'not-full-time-on-campus': 1})
        it = doc['items'][0]
        self.assertEqual(it['slug'], 'msc-data-science-abc123')
        self.assertEqual(it['uni'], 'u')
        self.assertEqual(it['studyMode'], 'Full-time, on campus.')          # the sentence, not the verdict
        self.assertEqual(it['fee']['context'], 'International students: GBP 24,000 a year.')
        self.assertNotIn('hash', it)
        self.assertNotIn('seen', doc)
        self.assertEqual((doc['total'], doc['generatedAt'], doc['universities']['u']['n']), (1, '2026-11-16', 1))

    def test_same_programme_under_two_addresses_is_kept_once(self):
        doc, stats = self.build([self.rec('MSc Data Science', 'https://u.edu/ds/2026'), self.rec('MSc Data Science', 'https://u.edu/ds/2027', fee=None)])
        self.assertEqual(len(doc['items']), 1)
        self.assertEqual(stats['duplicates'], 1)
        self.assertIsNotNone(doc['items'][0]['fee'])                         # the record with more facts stays

    def test_page_addresses_never_clash(self):
        # the same name and the same address code at two levels: only one can have the page address
        a = self.rec('Mathematics', 'https://u.edu/a/', degree='MSc', level='Master')
        b = self.rec('Mathematics', 'https://u.edu/b/', degree='BSc', level='Bachelor', duration={'display': '3 years', 'years': 3, 'context': 'Three years.'})
        doc, stats = self.build([a, b])
        self.assertEqual((len(doc['items']), stats['slug-clash']), (1, 1))

    def test_dump_is_valid_json_one_course_per_line(self):
        doc, _ = self.build([self.rec('MSc Data Science', 'https://u.edu/ds/'), self.rec('MSc Physics', 'https://u.edu/ph/')])
        text = B.dump(doc)
        self.assertEqual(json.loads(text)['total'], 2)
        self.assertEqual(sum(1 for ln in text.splitlines() if ln.startswith('{"slug"')), 2)
        empty = B.dump({'generatedAt': None, 'total': 0, 'universities': {}, 'items': []})
        self.assertEqual(json.loads(empty)['items'], [])


# A made-up page shaped like a UK university course page (test only, never published).
DETAIL_HTML = """<html><head><title>MSc Finance</title></head><body>
<nav><a href="/">Home</a><a href="/study">Study</a></nav>
<main>
<h1>MSc Finance</h1>
<p>Learn how financial markets work and how firms decide where to invest. This course suits graduates who want a career in banking.</p>
<h2>Key information</h2>
<ul><li>Duration: 1 year full-time</li><li>Start date: September 2027</li><li>Location: Egham campus</li></ul>
<h2>Entry requirements</h2>
<p>A 2:1 degree or equivalent in a quantitative subject.</p>
<h3>English language requirements</h3>
<p>IELTS 6.5 overall with no less than 6.0 in each subscore. TOEFL iBT 92 is also accepted.</p>
<h2>Fees</h2>
<table><tr><td>UK students</td><td>&pound;14,500</td></tr><tr><td>International students</td><td>&pound;28,100</td></tr></table>
<h2>Course content</h2>
<h3>Core modules</h3><ul><li>Corporate Finance</li><li>Asset Pricing</li></ul>
<h3>Optional modules</h3><ul><li>Financial Econometrics</li></ul>
<h2>Careers</h2>
<p>Our graduates work at Barclays and Deloitte, or continue to a PhD.</p>
<h2>Contact us</h2><p>Phone 01784 000000</p>
</main>
<footer>Cookie policy</footer></body></html>"""

GOOD_ANSWER = {
    'sections': [{'id': 0, 'type': 'overview'}, {'id': 1, 'type': 'key_facts'}, {'id': 2, 'type': 'entry_requirements'}, {'id': 3, 'type': 'english_requirements'},
                 {'id': 4, 'type': 'fees'}, {'id': 6, 'type': 'modules'}, {'id': 7, 'type': 'modules'}, {'id': 8, 'type': 'careers'}, {'id': 9, 'type': 'other'}],
    'duration': {'text': '1 year full-time', 'quote': 'Duration: 1 year full-time'},
    'study_mode': {'text': 'full-time', 'quote': 'Duration: 1 year full-time'},
    'campus': {'text': 'Egham campus', 'quote': 'Location: Egham campus'},
    'starts': [{'text': 'September 2027', 'quote': 'Start date: September 2027'}],
    'fees': [{'audience': 'international', 'amount': 28100, 'currency': 'GBP', 'period': 'year', 'year_label': None, 'quote': 'International students £28,100'},
             {'audience': 'home', 'amount': 14500, 'currency': 'GBP', 'period': 'year', 'year_label': None, 'quote': 'UK students £14,500'}],
    'ielts': {'overall': 6.5, 'min_band': 6.0, 'quote': 'IELTS 6.5 overall with no less than 6.0 in each subscore'},
    'other_english_tests': [{'test': 'TOEFL iBT', 'score_text': '92', 'quote': 'TOEFL iBT 92 is also accepted'}],
    'academic_entry': {'text': 'A 2:1 degree or equivalent in a quantitative subject', 'quote': 'A 2:1 degree or equivalent in a quantitative subject'},
    'core_modules': ['Corporate Finance', 'Asset Pricing'], 'optional_modules': ['Financial Econometrics'],
    'employers': ['Barclays', 'Deloitte'],
}


class DetailTests(unittest.TestCase):
    def secs(self):
        return D.sections_of(DETAIL_HTML, 'https://u.edu/msc-finance')

    def test_page_is_cut_at_headings_and_chrome_is_dropped(self):
        secs = self.secs()
        heads = [s['heading'] for s in secs]
        self.assertIn('Entry requirements', heads)
        self.assertIn('Core modules', heads)
        text = D.page_text(secs)
        self.assertNotIn('Cookie policy', text)
        self.assertIn('IELTS 6.5 overall', text)

    def test_good_answer_is_kept_and_text_is_copied_from_the_page(self):
        secs = self.secs()
        detail, rejected = D.verify(GOOD_ANSWER, secs)
        f = detail['facts']
        self.assertEqual(rejected, [])
        self.assertEqual(f['duration']['text'], '1 year full-time')
        self.assertEqual(f['ielts']['overall'], 6.5)
        self.assertEqual([x['audience'] for x in f['fees']], ['international', 'home'])
        self.assertEqual(f['coreModules'], ['Corporate Finance', 'Asset Pricing'])
        self.assertEqual(f['employers'], ['Barclays', 'Deloitte'])
        sec = detail['sections']
        self.assertEqual([b['heading'] for b in sec['modules']], ['Core modules', 'Optional modules'])   # several blocks of one type, in page order
        self.assertIn('Corporate Finance', sec['modules'][0]['text'])
        self.assertEqual(sec['entry_requirements'][0]['text'], secs[2]['text'])   # copied by code, character for character
        self.assertNotIn('other', sec)

    def test_a_fact_that_is_not_on_the_page_is_thrown_away(self):
        bad = dict(GOOD_ANSWER)
        bad['ielts'] = {'overall': 7.0, 'min_band': 6.5, 'quote': 'IELTS 7.0 overall'}                      # the page says 6.5
        bad['starts'] = [{'text': 'January 2027', 'quote': 'Start date: January 2027'}]                       # not on the page
        bad['core_modules'] = ['Corporate Finance', 'Quantum Cooking']                                       # second one invented
        bad['employers'] = ['Goldman Sachs']
        detail, rejected = D.verify(bad, self.secs())
        f = detail['facts']
        self.assertIsNone(f['ielts'])
        self.assertEqual(f['starts'], [])
        self.assertEqual(f['coreModules'], ['Corporate Finance'])
        self.assertEqual(f['employers'], [])
        self.assertEqual(len(rejected), 4)

    def test_fee_must_match_its_quote_and_international_needs_the_word(self):
        ans = {'sections': [], 'fees': [
            {'audience': 'international', 'amount': 2810, 'currency': 'GBP', 'period': 'year', 'quote': 'International students £28,100'},   # 2810 is not 28,100
            {'audience': 'international', 'amount': 14500, 'currency': 'GBP', 'period': 'year', 'quote': 'UK students £14,500'},          # quote does not say international
            {'audience': 'international', 'amount': 100, 'currency': 'GBP', 'period': 'year', 'quote': 'International students £28,100'}]}  # 100 is not a number in the quote
        detail, rejected = D.verify(ans, self.secs())
        fees = detail['facts']['fees']
        self.assertEqual([(x['audience'], x['amount']) for x in fees], [('other', 14500)])               # kept, but never shown as the international fee
        self.assertEqual(sorted(w for _, w in rejected), ['amount-not-in-quote', 'amount-not-in-quote', 'international-not-in-quote'])

    def test_reworded_text_falls_back_to_the_short_quote(self):
        ans = {'sections': [], 'duration': {'text': '12 months', 'quote': 'Duration: 1 year full-time'}}
        detail, _ = D.verify(ans, self.secs())
        self.assertEqual(detail['facts']['duration']['text'], 'Duration: 1 year full-time')             # not "12 months": that is not on the page

    def test_bad_section_ids_and_types_are_ignored(self):
        ans = {'sections': [{'id': 99, 'type': 'fees'}, {'id': 2, 'type': 'astrology'}, {'id': 'x', 'type': 'fees'}]}
        detail, _ = D.verify(ans, self.secs())
        self.assertEqual(detail['sections'], {})
        self.assertFalse(D.has_content(detail))

    def test_request_is_a_batch_request_with_a_forced_tool(self):
        r = D.request_of('c1', self.secs(), 'https://u.edu/x')
        self.assertEqual(r['custom_id'], 'c1')
        self.assertEqual(r['params']['model'], 'claude-haiku-5-5')
        self.assertEqual(r['params']['tool_choice'], {'type': 'tool', 'name': 'record_course_detail'})
        self.assertIn('[S0]', r['params']['messages'][0]['content'])
        self.assertLess(len(r['params']['messages'][0]['content']), D.MAX_PROMPT_CHARS + 500)

    def test_parse_tool_input_reads_dicts_and_objects(self):
        self.assertEqual(D.parse_tool_input([{'type': 'text', 'text': 'hi'}, {'type': 'tool_use', 'name': 'record_course_detail', 'input': {'a': 1}}]), {'a': 1})

        class Blk:
            type, name, input = 'tool_use', 'record_course_detail', {'b': 2}
        self.assertEqual(D.parse_tool_input([Blk()]), {'b': 2})
        self.assertIsNone(D.parse_tool_input([]))

    def test_dump_is_valid_json_one_page_per_line(self):
        detail, _ = D.verify(GOOD_ANSWER, self.secs())
        text = D.dump({'slug': 'u', 'pages': {'https://u.edu/b': detail, 'https://u.edu/a': detail}})
        doc = json.loads(text)
        self.assertEqual(list(doc['pages']), ['https://u.edu/a', 'https://u.edu/b'])
        self.assertEqual(sum(1 for ln in text.splitlines() if ln.startswith('"https://')), 2)


class AddressRuleTests(unittest.TestCase):
    """Pages found by vetting a real run of the Australian universities: events, blogs, domestic pages, rules pages, research degrees, compare links."""
    def test_event_blog_and_rules_pages_are_not_programmes(self):
        for u in ['https://www.sydney.edu.au/business/study/mba/mba-events/mba-webinar-26-aug-2026.html',
                  'https://www.unisq.edu.au/study/why-unisq/unisq-stories/blogs/what-is-a-masters-degree-and-5-reasons-to-study-one',
                  'https://students.flinders.edu.au/my-course/course-rules-2020/undergrad/bnursing/bngp',
                  'https://www.rmit.edu.au/study-with-us/levels-of-study/undergraduate-study/bachelor-degrees/bachelor-of-music-industry-bp047/further-study',
                  'https://www.rmit.edu.au/study-with-us/applying-to-rmit/local-student-applications/entry-requirements/inherent-requirements/master-of-social-work']:
            self.assertTrue(L.not_programme_url(u) or L.classify_url(u), u)

    def test_domestic_and_research_paths(self):
        self.assertEqual(L.classify_url('https://www.rmit.edu.au/study-with-us/applying-to-rmit/local-student-applications/entry-requirements/x'), 'domestic-only')
        self.assertEqual(L.classify_url('https://www.rmit.edu.au/study-with-us/levels-of-study/research-programs/phd/x'), 'research-degree')

    def test_real_course_pages_still_pass(self):
        for u in ['https://www.unsw.edu.au/study/postgraduate/master-of-engineering-science-robotics',
                  'https://www.uts.edu.au/courses/master-of-physiotherapy',
                  'https://www.rmit.edu.au/study-with-us/levels-of-study/postgraduate-study/masters-by-coursework/master-of-landscape-architecture-mc172',
                  'https://www.curtin.edu.au/study/offering/course-ug-bachelor-of-laws--b-laws/',
                  'https://www.swinburne.edu.au/course/undergraduate/bachelor-of-animation/handbook/',   # Swinburne's course pages are its handbook pages
                  'https://www.westernsydney.edu.au/future/study/courses/postgraduate/master-of-chinese-medicine',
                  'https://www.ecu.edu.au/degrees/courses/master-of-management-information-systems']:
            self.assertEqual(L.not_programme_url(u), '', u)
            self.assertEqual(L.classify_url(u), '', u)

    def test_names_that_are_events_blogs_or_sections(self):
        for n in ['MBA Webinar 26 August 2026', 'What is a Masters degree and 5 reasons to study one', 'Further study after the Bachelor of Music Industry', 'Study with us']:
            self.assertEqual(L.not_programme_name(n), 'not-a-programme-name', n)
        self.assertEqual(L.not_programme_name('Master of Business Administration'), '')

    def test_compare_links_do_not_make_new_addresses(self):
        base = 'https://www.uow.edu.au/study/courses/bachelor-of-arts/'
        for q in ('?addCourse=410100', '?removeCourse=410100', '?addCourse=361537&utm_source=x'):
            self.assertEqual(X.canon(base + q), base)
        self.assertEqual(X.canon('https://www.curtin.edu.au/study/offering/x/?segment=int'), 'https://www.curtin.edu.au/study/offering/x/?segment=int')   # a real choice of page stays


class FakeFetch:
    def __init__(self, html):
        self.html, self.got = html, []

    def get(self, url):
        self.got.append(url)

        class R:
            ok, final_url = True, url
            text = self.html
        return R()


class FakeBatches:
    def __init__(self, answers):
        self.answers, self.created = answers, []

    def create(self, requests):
        self.created.append(requests)
        return type('B', (), {'id': 'batch_1'})()

    def retrieve(self, i):
        return type('B', (), {'processing_status': 'ended'})()

    def results(self, i):
        for req in self.created[0]:
            cid = req['custom_id']
            ans = self.answers.get(cid)
            if ans is None:
                yield type('E', (), {'custom_id': cid, 'result': type('R', (), {'type': 'errored'})()})()
                continue
            msg = type('M', (), {'content': [{'type': 'tool_use', 'name': 'record_course_detail', 'input': ans}],
                                 'usage': type('U', (), {'input_tokens': 6000, 'output_tokens': 1500})()})()
            yield type('E', (), {'custom_id': cid, 'result': type('R', (), {'type': 'succeeded', 'message': msg})()})()


class DetailRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        DR.OUT, DR.DETAIL_DIR = self.tmp / 'out', self.tmp / 'detail'
        self.items = self.tmp / 'courses.json'
        self.items.write_text(json.dumps({'items': [
            {'uni': 'u1', 'url': 'https://u.edu/a', 'slug': 'a'}, {'uni': 'u1', 'url': 'https://u.edu/b', 'slug': 'b'},
            {'uni': 'u1', 'url': 'https://u.edu/c', 'slug': 'c'}, {'uni': 'u2', 'url': 'https://v.edu/a', 'slug': 'a'}]}))
        self.args = type('A', (), dict(courses_file=str(self.items), only='', per_uni=2, limit_unis=0, force=False, model=D.MODEL, delay=0, max_minutes=1, contact=''))()

    def test_prepare_picks_a_spread_and_skips_unchanged_pages(self):
        fx = FakeFetch(DETAIL_HTML)
        reqs, pages = DR.prepare(self.args, fx)
        self.assertEqual(len(reqs), 3)                                         # u1: 2 of 3, u2: 1
        self.assertEqual(len(fx.got), 3)
        # a second run with the stored hashes: nothing changed, nothing sent
        first = next(iter(pages.values()))
        (DR.DETAIL_DIR).mkdir(parents=True)
        (DR.DETAIL_DIR / 'u1.json').write_text(D.dump({'slug': 'u1', 'pages': {first['url']: {'hash': first['hash']}}}))
        reqs2, _ = DR.prepare(self.args, FakeFetch(DETAIL_HTML))
        self.assertEqual(len(reqs2), 2 if first['uni'] == 'u1' else 3)

    def test_page_with_nothing_readable_is_not_sent(self):
        reqs, _ = DR.prepare(self.args, FakeFetch('<html><body><div id="app"></div><script>boot()</script></body></html>'))
        self.assertEqual(reqs, [])

    def test_collect_checks_answers_and_writes_one_file_per_university(self):
        reqs, pages = DR.prepare(self.args, FakeFetch(DETAIL_HTML))
        bad = dict(GOOD_ANSWER, employers=['Goldman Sachs'])
        ids = list(pages)
        client = type('C', (), {'messages': type('M', (), {'batches': FakeBatches({ids[0]: GOOD_ANSWER, ids[1]: bad})})()})()
        DR.submit(client, reqs)
        rep = DR.collect(client, ['batch_1'], pages, '2026-11-17')
        self.assertEqual((rep['ok'], rep['failed']), (2, 1))                   # the third had no answer
        self.assertEqual(rep['rejected']['employers: name-not-on-page'], 1)
        self.assertEqual((rep['in'], rep['out']), (12000, 3000))
        self.assertGreater(rep['cost_usd'], 0)
        written = json.loads((DR.DETAIL_DIR / 'u1.json').read_text())
        d = next(iter(written['pages'].values()))
        self.assertEqual((d['readOn'], d['model']), ('2026-11-17', D.MODEL))
        self.assertTrue(d['hash'])


if __name__ == '__main__':
    unittest.main(verbosity=1)
