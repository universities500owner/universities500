#!/usr/bin/env python3
"""Offline tests for the industry-news reader: a stub 'official website' on localhost, no internet, no AI.
Run: python3 scripts/news/test_news.py"""
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
sys.path.insert(0, str(HERE.parent / 'scholarships'))
from fetcher import Fetcher  # noqa: E402
import news_feeds as NF  # noqa: E402
import news_read as NR  # noqa: E402
import news_rules as R  # noqa: E402
import news_run as RUN  # noqa: E402

PORT = {}
EXTRA = {}
TODAY = '2026-11-16'


def rss(items):
    body = ''.join(f'<item><title>{t}</title><link>{l}</link><pubDate>{d}</pubDate><description><![CDATA[{s}]]></description></item>' for t, l, d, s in items)
    return ('application/rss+xml', f'<?xml version="1.0"?><rss version="2.0"><channel><title>News</title>{body}</channel></rss>')


def article(title, desc=''):
    meta = f'<meta name="description" content="{desc}">' if desc else ''
    return ('text/html', f'<!doctype html><html><head><title>{title}</title>{meta}</head><body><main><h1>{title}</h1>'
            f'<p>This is the full notice with enough words to be read as a page of its own for the tests.</p></main></body></html>')


def pages():
    b = f'http://127.0.0.1:{PORT["p"]}'
    return {
        '/robots.txt': ('text/plain', 'User-agent: *\nDisallow: /private/\n'),
        '/feed.xml': rss([
            ('Changes to the Student route for international students', f'{b}/n/student-route', 'Mon, 09 Nov 2026 09:00:00 GMT',
             '<p>The government has changed the Student route. From 1 January 2027 students need a new document. Check the guidance before you apply.</p>'),
            ('New asylum processing centre opens', f'{b}/n/asylum', 'Tue, 10 Nov 2026 09:00:00 GMT', '<p>A new centre opens for asylum claims across the region this winter.</p>'),
            ('Old study visa fee notice', f'{b}/n/old', 'Mon, 01 Jun 2026 09:00:00 GMT', '<p>Fees for the study visa changed earlier this year and applicants were informed.</p>'),
            ('Study visa news on another website', 'https://example.org/elsewhere', 'Mon, 09 Nov 2026 09:00:00 GMT', '<p>This item points to a website that is not the official body.</p>'),
            ('Étudiants internationaux : nouvelles règles pour le visa étudiant', f'{b}/n/fr', 'Mon, 09 Nov 2026 09:00:00 GMT', '<p>Les étudiants internationaux doivent déposer une demande en ligne avant le départ.</p>'),
            ('Student visa processing times updated', f'{b}/n/times', 'Wed, 11 Nov 2026 09:00:00 GMT', ''),
        ]),
        '/n/times': article('Student visa processing times updated', 'Processing times for student visas were updated on 11 November. Most applications are decided within four weeks.'),
        '/atom.xml': ('application/atom+xml', f'''<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><title>Atom news</title>
            <entry><title>Graduate route guidance for students</title><link rel="alternate" href="{b}/n/graduate"/><link rel="self" href="{b}/atom.xml"/>
            <updated>2026-11-12T10:00:00Z</updated><summary>Updated guidance explains how graduates can stay after their studies. It lists the documents needed.</summary></entry></feed>'''),
        '/home': ('text/html', f'<html><head><link rel="alternate" type="application/rss+xml" href="{b}/feed.xml"></head><body><p>Home</p></body></html>'),
        '/list': ('text/html', f'''<html><body><main><ul>
            <li class="news-item"><h3><a href="{b}/n/a1">Scholarship round opens for international students</a></h3><time datetime="2026-11-10">10 November 2026</time>
              <p>The scholarship round for international students opens on 1 December and closes in February.</p></li>
            <li class="news-item"><h3><a href="{b}/n/a2">Student pass changes explained for new arrivals</a></h3><span>Published 5 November 2026</span></li>
            <li class="news-item"><h3><a href="{b}/n/a3">Undated notice about student places for next year</a></h3><p>This item has no date anywhere so it must be skipped by the reader.</p></li>
            </ul></main></body></html>'''),
        '/private/feed.xml': rss([('Student visa update', f'{b}/n/x', 'Mon, 09 Nov 2026 09:00:00 GMT', 'Student visa text long enough to be read as a summary of the notice.')]),
        '/n/a1': article('a1'),
        '/n/a2': article('Student pass changes explained for new arrivals', 'New arrivals on a student pass must register within two weeks and keep their documents with them.'),
    }


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        path = self.path.split('?')[0]
        pg = EXTRA.get(path) or pages().get(path)
        if not pg:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(pg[2] if len(pg) > 2 else 200)
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


def fx():
    return Fetcher('Universities500Bot/1.0 (test)', delay=0, timeout=5)


def src(**kw):
    b = f'http://127.0.0.1:{PORT["p"]}'
    base = {'id': 'test-body', 'country': 'uk', 'body': 'Test Immigration Department', 'kind': 'government', 'domains': ['127.0.0.1'], 'filter': 'student', 'feeds': [f'{b}/feed.xml']}
    base.update(kw)
    return base


class Rules(unittest.TestCase):
    def test_relevance(self):
        self.assertEqual(R.relevant('Changes to the Student route', ''), (True, ''))
        self.assertEqual(R.relevant('Visa fees rise', 'The fee for a study permit rises.')[0], True)
        self.assertEqual(R.relevant('New asylum processing centre', 'A new centre for asylum claims.'), (False, 'about-something-else'))
        self.assertEqual(R.relevant('Minister visits the border', 'A speech about trade.'), (False, 'not-about-students'))
        self.assertEqual(R.relevant('Anything at all', '', 'all'), (True, ''))

    def test_relevance_is_not_loose(self):
        # a department of education publishes much that is not about international students
        self.assertEqual(R.relevant('Guidance: EHE and CME data collection: guide and validation', 'Elective home education and children missing education: how councils report numbers of pupils and students.')[0], False)
        self.assertEqual(R.relevant('New college funding guide', 'Funding for colleges and universities in England.')[0], False)
        # ...but a student word with an international or visa word counts
        self.assertEqual(R.relevant('Register of licensed sponsors: students', 'Organisations that sponsor students from overseas.')[0], True)
        self.assertEqual(R.relevant('Scholarship round opens', 'Scholarships for foreign nationals who plan to study.')[0], True)
        # an immigration authority needs only a student word
        self.assertEqual(R.relevant('Update for students', 'Changes to the online form.')[0], False)
        self.assertEqual(R.relevant('Update for students', 'Changes to the online form.', 'student', True)[0], True)
        # enforcement and crime news is never guidance, even when a student is named
        self.assertEqual(R.relevant('ICE issues immigration detainer against illegal alien', 'The man, an F-1 student, was charged.'), (False, 'about-something-else'))
        self.assertEqual(R.relevant('Man arrested after student visa fraud', 'An international student was named.')[0], False)

    def test_statement_of_changes_counts_for_an_immigration_authority_only(self):
        title = 'Statement of changes to the Immigration Rules: HC 1333'
        self.assertEqual(R.relevant(title, '', 'student', True), (True, ''))
        self.assertEqual(R.relevant(title, '', 'student', False)[0], False)

    def test_policy_words_cover_permission_court_and_budget(self):
        for h in ['Budget 2026: targeted two-year Graduate permission announced', 'Federal Court Rules in Favor of Coalition Challenging Rule', 'NAFSA joins lawsuit over internship changes']:
            self.assertEqual(R.relevant(h, '', 'policy'), (True, ''), h)
        self.assertEqual(R.relevant('International students contributed $39.9 billion to the US economy', '', 'policy')[0], False)

    def test_english(self):
        self.assertTrue(R.english('International students can now apply for the new graduate visa online from next week.'))
        self.assertFalse(R.english('Les étudiants internationaux peuvent demander un visa pour la France en ligne dès maintenant'))
        self.assertFalse(R.english('Internationale Studierende können ab sofort ein Visum für Deutschland online beantragen und müssen'))
        # headlines with no small words are English too; short foreign headlines are not
        self.assertTrue(R.english('Australia caps student visa numbers amid migration concerns'))
        self.assertTrue(R.english('Canada cuts study permit cap again for international students next year'))
        self.assertFalse(R.english('Chili-Colombie : la tournée Campus France 2026 confirme l’attractivité des études en France'))
        self.assertFalse(R.english('Neue Regeln für das Studentenvisum in Deutschland und was sich ändert'))

    def test_excerpt(self):
        t = R.excerpt('<p>Published: 3 Nov 2026.</p><p>The government has changed the Graduate route. From 1 January 2027 the route lasts 18 months. ' + 'More detail follows. ' * 30 + '</p>', 'x')
        self.assertTrue(t.startswith('The government has changed the Graduate route.'))
        self.assertLessEqual(len(t), 361)
        self.assertTrue(t.endswith('.'))                       # cut at a sentence end
        self.assertEqual(R.excerpt('Too short', 'x'), '')       # no summary rather than a made-up one
        self.assertEqual(R.excerpt('Same as the title text here', 'Same as the title text here'), '')
        self.assertTrue(R.excerpt('A' * 500, 'x').endswith('…'))

    def test_dates_and_domains(self):
        self.assertEqual(R.parse_date('Mon, 16 Nov 2026 10:00:00 GMT'), '2026-11-16')
        self.assertEqual(R.parse_date('2026-11-16T10:00:00Z'), '2026-11-16')
        self.assertEqual(R.parse_date('16 November 2026'), '2026-11-16')
        self.assertIsNone(R.parse_date('03/04/2026'))          # day or month first? we do not guess
        self.assertTrue(R.allowed('https://www.gov.uk/x', ['gov.uk']))
        self.assertFalse(R.allowed('https://gov.uk.evil.com/x', ['gov.uk']))
        self.assertFalse(R.allowed('https://evilgov.uk/x', ['gov.uk']))


class Readers(unittest.TestCase):
    def test_rss_and_atom(self):
        b = f'http://127.0.0.1:{PORT["p"]}'
        its = NF.parse_feed(fx().get(f'{b}/feed.xml').body, b)
        self.assertEqual(len(its), 6)
        self.assertEqual(its[0]['published'], '2026-11-09')
        at = NF.parse_feed(fx().get(f'{b}/atom.xml').body, b)
        self.assertEqual([(i['title'], i['published'], i['url']) for i in at], [('Graduate route guidance for students', '2026-11-12', f'{b}/n/graduate')])

    def test_feed_discovery_and_feed_detection(self):
        b = f'http://127.0.0.1:{PORT["p"]}'
        self.assertEqual(NF.discover_feeds(fx().get(f'{b}/home').text, f'{b}/home'), [f'{b}/feed.xml'])
        self.assertTrue(NF.looks_like_feed(fx().get(f'{b}/feed.xml').body))
        self.assertFalse(NF.looks_like_feed(fx().get(f'{b}/home').body))

    def test_list_page_needs_a_date(self):
        b = f'http://127.0.0.1:{PORT["p"]}'
        its = NF.parse_listing(fx().get(f'{b}/list').text, f'{b}/list')
        self.assertEqual([i['title'] for i in its], ['Scholarship round opens for international students', 'Student pass changes explained for new arrivals'])
        self.assertEqual([i['published'] for i in its], ['2026-11-10', '2026-11-05'])
        self.assertTrue(its[0]['summary'].startswith('The scholarship round'))

    def test_federal_register(self):
        body = json.dumps({'results': [{'title': 'SEVP fee notice', 'abstract': 'The agency sets a fee for students.', 'html_url': 'https://www.federalregister.gov/d/2026-1', 'publication_date': '2026-11-10', 'agency_names': ['Immigration and Customs Enforcement']}, {'title': 'No link'}]})
        its = NF.parse_federal_register(body)
        self.assertEqual(len(its), 1)
        self.assertEqual((its[0]['published'], its[0]['detail']), ('2026-11-10', 'Immigration and Customs Enforcement'))
        self.assertIn('conditions%5Bterm%5D=SEVP', NF.federal_register_url('SEVP'))


class ReadSource(unittest.TestCase):
    def test_what_is_kept_and_why_the_rest_is_dropped(self):
        items, info = NR.read_source(src(), fx(), TODAY)
        titles = [i['title'] for i in items]
        self.assertEqual(sorted(titles), ['Changes to the Student route for international students', 'Student visa processing times updated'])
        self.assertEqual(info['found'], 6)
        d = info['drops']
        self.assertEqual((d['about-something-else'], d['too-old'], d['link-not-on-official-site'], d['not-english']), (1, 1, 1, 1))
        first = next(i for i in items if i['title'].startswith('Changes'))
        self.assertTrue(first['summary'].startswith('The government has changed the Student route.'))
        self.assertEqual((first['published'], first['country'], first['body']), ('2026-11-09', 'uk', 'Test Immigration Department'))
        self.assertTrue(first['url'].startswith('http://127.0.0.1'))

    def test_summary_is_taken_from_the_official_page_when_the_feed_has_none(self):
        items, _ = NR.read_source(src(), fx(), TODAY)
        t = next(i for i in items if i['title'].startswith('Student visa processing'))
        self.assertTrue(t['summary'].startswith('Processing times for student visas were updated'))

    def test_home_page_feed_discovery(self):
        b = f'http://127.0.0.1:{PORT["p"]}'
        items, info = NR.read_source(src(feeds=[], home=f'{b}/home'), fx(), TODAY)
        self.assertEqual(len(items), 2)
        self.assertIn('found on the home page', info['via'])

    def test_list_page_fallback(self):
        b = f'http://127.0.0.1:{PORT["p"]}'
        items, info = NR.read_source(src(feeds=[], list=f'{b}/list'), fx(), TODAY)
        self.assertEqual(len(items), 2)
        self.assertTrue(info['via'].startswith('list page'))
        self.assertEqual(next(i for i in items if 'Student pass' in i['title'])['summary'][:20], 'New arrivals on a st')

    def test_news_section_found_from_the_home_page(self):
        b = f'http://127.0.0.1:{PORT["p"]}'
        EXTRA['/site'] = ('text/html', f'<html><body><nav><a href="{b}/about">About us</a> <a href="{b}/list">Latest news</a> <a href="https://example.org/news">Other news</a></nav></body></html>')
        try:
            self.assertEqual(NF.discover_sections(fx().get(f'{b}/site').text, f'{b}/site', ['127.0.0.1']), [f'{b}/list'])
            items, info = NR.read_source(src(feeds=[], home=f'{b}/site'), fx(), TODAY)      # no feed, no list address: the home page leads to it
            self.assertEqual(len(items), 2)
            self.assertEqual(info['sections'], [f'{b}/list'])
        finally:
            EXTRA.clear()

    def test_page_with_no_items_is_described(self):
        b = f'http://127.0.0.1:{PORT["p"]}'
        EXTRA['/spa'] = ('text/html', '<html><head><title>News</title><script src="a.js"></script></head><body><div id="app"></div></body></html>')
        try:
            items, info = NR.read_source(src(feeds=[], list=f'{b}/spa'), fx(), TODAY)
            self.assertEqual(items, [])
            pr = info['profiles'][0]
            self.assertEqual((pr['title'], pr['scripts'], pr['links']), ('News', 1, 0))
        finally:
            EXTRA.clear()

    def test_feed_and_list_are_merged(self):
        b = f'http://127.0.0.1:{PORT["p"]}'
        items, info = NR.read_source(src(list=f'{b}/list'), fx(), TODAY)
        self.assertEqual(len(items), 4)      # 2 from the feed + 2 from the list page
        self.assertTrue(info['via'].startswith('feed') and 'list page' in info['via'])

    def test_robots_and_failures_are_reported_not_hidden(self):
        b = f'http://127.0.0.1:{PORT["p"]}'
        items, info = NR.read_source(src(feeds=[f'{b}/private/feed.xml']), fx(), TODAY)
        self.assertEqual(items, [])
        self.assertIn('robots', info['error'])
        items, info = NR.read_source(src(feeds=[f'{b}/missing.xml']), fx(), TODAY)
        self.assertEqual((items, info['error']), ([], 'no items found'))

    def test_a_student_only_source_keeps_everything_official(self):
        b = f'http://127.0.0.1:{PORT["p"]}'
        EXTRA['/all.xml'] = rss([('Portal maintenance this weekend', f'{b}/n/m', 'Mon, 09 Nov 2026 09:00:00 GMT', 'The portal will be unavailable on Saturday while the team makes an upgrade.')])
        try:
            items, _ = NR.read_source(src(feeds=[f'{b}/all.xml'], filter='all'), fx(), TODAY)
            self.assertEqual(len(items), 1)
            items, _ = NR.read_source(src(feeds=[f'{b}/all.xml']), fx(), TODAY)
            self.assertEqual(len(items), 0)
        finally:
            EXTRA.clear()


class Store(unittest.TestCase):
    def it(self, n, c='uk', pub='2026-11-01', title=None, summary='Official text here that is long enough.'):
        return {'country': c, 'sourceId': 's', 'body': 'B', 'kind': 'government', 'detail': '', 'title': title or f'Item {n}', 'url': f'https://x.gov/{n}', 'published': pub, 'summary': summary}

    def test_merge_keeps_ages_out_and_orders(self):
        prev = [dict(self.it(1), id='a', firstSeen='2026-10-01', lastSeen='2026-11-10'), dict(self.it(2, pub='2025-06-01'), id='b', firstSeen='2026-06-02', lastSeen='2026-06-02')]
        out = RUN.merge(prev, [self.it(3, pub='2026-11-12')], TODAY)
        self.assertEqual([i['url'] for i in out], ['https://x.gov/3', 'https://x.gov/1'])      # newest first, the 17-month-old item is gone
        self.assertEqual(next(i for i in out if i['url'].endswith('/1'))['firstSeen'], '2026-10-01')   # missing from today's feed: kept
        self.assertEqual(next(i for i in out if i['url'].endswith('/3'))['firstSeen'], TODAY)

    def test_changed_text_is_marked_updated(self):
        prev = [dict(self.it(1), id='a', firstSeen='2026-10-01', lastSeen='2026-11-10')]
        out = RUN.merge(prev, [self.it(1, summary='New official wording that is long enough to count.')], TODAY)
        self.assertEqual(out[0]['updated'], TODAY)
        self.assertEqual(out[0]['summary'], 'New official wording that is long enough to count.')

    def test_per_country_cap(self):
        out = RUN.merge([], [self.it(n, pub='2026-11-%02d' % (1 + n % 14)) for n in range(40)], TODAY, per_country=30)
        self.assertEqual(len(out), 30)

    def test_recheck_removes_a_page_that_is_gone(self):
        b = f'http://127.0.0.1:{PORT["p"]}'
        items = [dict(self.it(1), url=f'{b}/n/a2', lastSeen='2026-11-01'), dict(self.it(2), url=f'{b}/n/does-not-exist', lastSeen='2026-11-01')]
        out, gone = RUN.recheck(items, fx(), TODAY)
        self.assertEqual((len(out), gone), (1, 1))
        self.assertEqual(out[0]['lastSeen'], TODAY)


def wp_json(posts):
    return ('application/json', json.dumps([{'date': d, 'link': l, 'title': {'rendered': t}, 'excerpt': {'rendered': '<p>Trade press text that must never be kept.</p>'}} for t, l, d in posts]))


class Backfill(unittest.TestCase):
    def test_since_is_21_days_for_a_known_source_unless_backfill(self):
        seen = []
        orig = NR._candidates
        NR._candidates = lambda src, fx, info, since: seen.append(since) or []
        try:
            known = {'x': {'sourceId': 's1'}}
            src = {'id': 's1', 'country': 'uk', 'body': 'b', 'domains': ['example.org']}
            NR.read_source(src, None, '2026-11-17', 365, known)
            NR.read_source(src, None, '2026-11-17', 365, known, backfill=True)
            NR.read_source(src, None, '2026-11-17', 365, {})
        finally:
            NR._candidates = orig
        self.assertEqual(seen, ['2026-10-27', '2025-11-17', '2025-11-17'])


class DatedLinks(unittest.TestCase):
    def test_date_taken_from_the_address(self):
        html = '<a href="/post.php?story=20261114092909696">Foreign universities struggle to attract Indian students</a><a href="/about">About this newspaper and who runs it</a><a href="/post.php?story=20261113104312394">Short</a>'
        its = NF.parse_dated_links(html, 'https://example.org/list', r'story=(\d{8})')
        self.assertEqual([(i['published'], i['title']) for i in its], [('2026-11-14', 'Foreign universities struggle to attract Indian students')])


class TwelveMonths(unittest.TestCase):
    def test_parsers(self):
        gu = NF.parse_govuk(json.dumps({'results': [{'title': 'Student sponsor guidance', 'description': 'How to sponsor a student.', 'public_timestamp': '2026-11-06T10:00:00Z', 'link': '/guidance/student-sponsor', 'format': 'guidance'}, {'title': 'No link'}]}))
        self.assertEqual([(i['url'], i['published'], i['detail']) for i in gu], [('https://www.gov.uk/guidance/student-sponsor', '2026-11-06', 'guidance')])
        wp = NF.parse_wp(json.dumps([{'date': '2026-11-05T08:00:00', 'link': 'https://x.org/a', 'title': {'rendered': 'Canada&#8217;s new cap &amp; visa rules'}, 'excerpt': {'rendered': '<p>x</p>'}}]))
        self.assertEqual((wp[0]['title'], wp[0]['published']), ('Canada\u2019s new cap & visa rules', '2026-11-05'))
        self.assertIn('after=2025-11-16T00%3A00%3A00', NF.wp_url('https://x.org/', 'visa', 1, '2025-11-16'))
        self.assertIn('filter_public_timestamp=from%3A2025-11-16', NF.govuk_url('home-office', 'student', '2025-11-16'))
        self.assertIn('conditions%5Bpublication_date%5D%5Bgte%5D=2025-11-16', NF.federal_register_url('SEVP', since='2025-11-16'))

    def test_trade_press_headline_date_link_only(self):
        b = f'http://127.0.0.1:{PORT["p"]}'
        EXTRA['/wp-json/wp/v2/posts'] = wp_json([
            ('Canada cuts study permit cap again', f'{b}/p/1', '2026-11-05T08:00:00'),
            ('UK and Australia tighten student visa rules', f'{b}/p/2', '2026-10-20T08:00:00'),
            ('Top source markets for the fall intake', f'{b}/p/3', '2026-10-01T08:00:00'),
            ('A new campus opens in Canada', f'{b}/p/4', '2026-09-01T08:00:00'),
            ('Visa changes for students worldwide', f'{b}/p/5', '2026-08-01T08:00:00'),
            ('Canada cap decision from 2024', f'{b}/p/6', '2025-02-01T08:00:00')])
        try:
            press = {'id': 'press', 'country': '*', 'tag': True, 'body': 'Trade Press', 'kind': 'media', 'filter': 'policy', 'domains': ['127.0.0.1'],
                     'wp': {'base': b, 'queries': ['visa'], 'pages': 2}}
            items, info = NR.read_source(press, fx(), TODAY, 365, {})
            got = sorted((i['country'], i['title']) for i in items)
            self.assertEqual(got, [('australia', 'UK and Australia tighten student visa rules'), ('canada', 'Canada cuts study permit cap again'), ('uk', 'UK and Australia tighten student visa rules')])
            self.assertTrue(all(i['summary'] == '' and i['kind'] == 'media' for i in items))      # the publisher's text is never kept
            d = info['drops']
            self.assertEqual((d['not-about-policy'], d['no-country'], d['too-old']), (2, 1, 1))
            self.assertIn('after=2025-11-16', info['tried'][0]['url'])                       # first run: the whole 12 months
            _, info2 = NR.read_source(press, fx(), TODAY, 365, {'u': {'sourceId': 'press'}})
            self.assertIn('after=2026-10-26', info2['tried'][0]['url'])                      # later runs: the last 21 days
        finally:
            EXTRA.clear()

    def test_merge_one_article_under_two_countries_and_caps_kept_apart(self):
        a = {'country': 'uk', 'sourceId': 'p', 'body': 'P', 'kind': 'media', 'detail': '', 'title': 'T', 'url': 'https://p/1', 'published': '2026-11-01', 'summary': ''}
        b = dict(a, country='australia')
        off = [{'country': 'uk', 'sourceId': 's', 'body': 'B', 'kind': 'government', 'detail': '', 'title': f'O{n}', 'url': f'https://g/{n}', 'published': '2026-10-%02d' % (1 + n % 28), 'summary': 'x'} for n in range(70)]
        out = RUN.merge([], [a, b] + off, TODAY)
        self.assertEqual(len([i for i in out if i['kind'] == 'media']), 2)
        self.assertEqual(len([i for i in out if i['country'] == 'uk' and i['kind'] == 'government']), 60)
        self.assertEqual(len({i['id'] for i in out}), len(out))


class Runner(unittest.TestCase):
    def run_main(self, tmp, sources, *extra):
        b = f'http://127.0.0.1:{PORT["p"]}'
        sp = Path(tmp) / 'sources.json'
        sp.write_text(json.dumps({'keepDays': 120, 'sources': sources}))
        return RUN.main(['--sources', str(sp), '--data', str(Path(tmp) / 'news.json'), '--report', str(Path(tmp) / 'rep'), '--today', TODAY, '--delay', '0', *extra])

    def test_daily_run_writes_and_probe_does_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ.pop('GITHUB_STEP_SUMMARY', None)
            self.assertEqual(self.run_main(tmp, [src()], '--probe'), 0)
            self.assertFalse((Path(tmp) / 'news.json').exists())
            self.assertTrue((Path(tmp) / 'rep' / 'news_report.md').exists())
            self.assertEqual(self.run_main(tmp, [src()]), 0)
            doc = json.loads((Path(tmp) / 'news.json').read_text())
            self.assertEqual(len(doc['items']), 2)
            self.assertEqual(doc['sources']['test-body']['status'], 'ok')
            self.assertEqual(doc['sources']['test-body']['checked'], TODAY)
            self.assertTrue(all(i['url'] and i['published'] and i['body'] and i['firstSeen'] for i in doc['items']))

    def test_one_broken_source_does_not_stop_the_others(self):
        b = f'http://127.0.0.1:{PORT["p"]}'
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self.run_main(tmp, [src(id='broken', country='canada', feeds=[f'{b}/missing.xml']), src()]), 0)
            doc = json.loads((Path(tmp) / 'news.json').read_text())
            self.assertEqual(doc['sources']['broken']['status'], 'failed')
            self.assertEqual(len(doc['items']), 2)

    def test_nothing_answers_leaves_the_file_alone(self):
        b = f'http://127.0.0.1:{PORT["p"]}'
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self.run_main(tmp, [src()]), 0)
            before = (Path(tmp) / 'news.json').read_text()
            self.assertEqual(self.run_main(tmp, [src(feeds=[f'{b}/missing.xml'])]), 3)
            self.assertEqual((Path(tmp) / 'news.json').read_text(), before)

    def test_why_a_source_was_empty(self):
        b = f'http://127.0.0.1:{PORT["p"]}'
        EXTRA['/forbidden'] = ('text/plain', 'no', 403)
        EXTRA['/blank'] = ('text/html', '<html><body><p>Nothing here</p></body></html>')
        try:
            with tempfile.TemporaryDirectory() as tmp:
                self.assertEqual(self.run_main(tmp, [src(), src(id='a', feeds=[], list=f'{b}/forbidden'), src(id='b', feeds=[], list=f'{b}/blank'), src(id='c', feeds=[f'{b}/missing.xml']),
                                                      src(id='d', feeds=[f'{b}/private/feed.xml'])]), 0)
                st = json.loads((Path(tmp) / 'news.json').read_text())['sources']
                self.assertEqual([st[k]['status'] for k in 'abcd'], ['blocked', 'unreadable', 'failed', 'blocked'])
        finally:
            EXTRA.clear()

    def test_only_one_country(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self.run_main(tmp, [src(), src(id='other', country='canada')], '--only', 'canada'), 0)
            doc = json.loads((Path(tmp) / 'news.json').read_text())
            self.assertEqual({i['country'] for i in doc['items']}, {'canada'})


class SourceList(unittest.TestCase):
    def test_every_country_has_a_source_and_every_source_is_complete(self):
        cfg = json.loads((HERE.parent.parent / 'data' / 'news_sources.json').read_text())
        by = {}
        for s in cfg['sources']:
            by.setdefault(s['country'], []).append(s)
            self.assertTrue(s['id'] and s['body'] and s['domains'], s.get('id'))
            self.assertIn(s['kind'], ('government', 'agency', 'media') if s['country'] != '*' else ('media',), s['id'])
            if s['kind'] == 'media':
                self.assertEqual(s['filter'], 'policy', s['id'])      # sector bodies and trade press: policy headlines only
            self.assertTrue(s.get('feeds') or s.get('fr') or s.get('list') or s.get('home'), s['id'])
            lst = s.get('list') or []
            for u in (s.get('feeds') or []) + ([lst] if isinstance(lst, str) else lst) + [s.get('home') or '']:
                if u:
                    self.assertTrue(u.startswith('https://'), (s['id'], u))
                    if 'federalregister.gov' not in u:
                        self.assertTrue(R.allowed(u, s['domains']), (s['id'], u))      # the address is on the body's own website
        self.assertEqual(set(by) - {'*'}, set(RUN.COUNTRIES))
        for s in by.get('*', []):
            self.assertTrue(s.get('tag') and s['kind'] == 'media' and s['filter'] == 'policy', s['id'])      # trade press: country from the headline, policy headlines only
        self.assertEqual(len({s['id'] for s in cfg['sources']}), len(cfg['sources']))


if __name__ == '__main__':
    unittest.main(verbosity=1)
