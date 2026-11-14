"""Tests for the article importer. Builds a small Word file with pandoc, then reads it back.

    python3 scripts/articles/test_import.py
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import import_docx as I  # noqa: E402

PACK = '''# Research cut-off: 14 November 2026

# UK-01 \\| Cost & Budgeting

Priority: High \\| Workbook status: Not Started

# Cost of Studying in the UK

Primary keyword: cost of studying UK

Secondary keywords: uk fees; ihs

GEO / interactive element: Cost Calculator

The opening paragraph explains why costs are more than tuition.

Quick answer: add tuition, living costs and the health surcharge. Check GOV.UK.

## 1. Tuition

Tuition depends on the course. The proposed interactive element is a calculator. It should let the student enter fees.

- **Check the CAS.** Fees are on it.
- **Check the funds.** Keep them for 28 days.

| Cost | Amount |
|------|--------|
| Rent | £1,000 |
| Food | £300 |

## 2. Product brief for the calculator

Build a calculator with these inputs.

## 3. Something after the brief

This text comes after a build brief and must not appear.

## Frequently asked questions

### Is the fee fixed?

No. Check the university.

### Can I work?

Yes, within limits. See https://www.gov.uk/student-visa/work for the rules.

## Sources

**GOV.UK – Student visa**

> Current fees and rules.
>
> [https://www.gov.uk/student-visa](https://www.gov.uk/student-visa)

## SEO and page metadata

| Element | Recommendation |
|---|---|
| SEO title | UK Study Costs |
| Meta description | What it costs to study in the UK. |
| Suggested URL | /uk-study-costs/ |

# UK-02 \\| Visa & Compliance

Priority: Medium

# Short Second Article

A paragraph.

## 1. Only section

Text.

## 2. Another section

More text.

## Frequently asked questions

### Q one?

Answer one.
'''


class Import(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        d = Path(cls.tmp.name)
        (d / 'pack.md').write_text(PACK, encoding='utf-8')
        subprocess.run(['pandoc', str(d / 'pack.md'), '-o', str(d / 'UK_pack.docx')], check=True)
        cls.out = d / 'out'
        subprocess.run([sys.executable, str(HERE / 'import_docx.py'), str(d / 'UK_pack.docx'), '--out', str(cls.out),
                        '--overrides', str(d / 'none.json')], check=True, capture_output=True)
        cls.a = json.loads((cls.out / 'UK-01.json').read_text(encoding='utf-8'))
        cls.b = json.loads((cls.out / 'UK-02.json').read_text(encoding='utf-8'))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def text(self, blocks):
        return ' '.join(I.plain(b['runs']) for b in blocks if b['t'] == 'p')

    def test_two_articles_found(self):
        self.assertEqual((self.a['id'], self.b['id']), ('UK-01', 'UK-02'))
        self.assertEqual(self.a['destination'], 'uk')
        self.assertEqual(self.a['topic'], 'cost-and-budgeting')

    def test_title_and_fields(self):
        self.assertEqual(self.a['title'], 'Cost of Studying in the UK')
        self.assertEqual(self.a['primaryKeyword'], 'cost of studying UK')
        self.assertEqual(self.a['seoTitle'], 'UK Study Costs')
        self.assertEqual(self.a['slug'], '/uk-study-costs/')
        self.assertEqual(self.a['priority'], 'High')
        self.assertEqual(self.a['reviewed'], '2026-11-14')

    def test_intro_and_quick_answer(self):
        self.assertIn('opening paragraph', self.text(self.a['intro']))
        q = self.text(self.a['quick'])
        self.assertTrue(q.startswith('Add tuition'), q)  # label removed, first letter capital
        self.assertNotIn('Quick answer', q)

    def test_sections_keep_lists_and_tables(self):
        sec = self.a['sections'][0]
        self.assertEqual(sec['title'], 'Tuition')
        kinds = [b['t'] for b in sec['blocks']]
        self.assertIn('ul', kinds)
        self.assertIn('table', kinds)
        ul = next(b for b in sec['blocks'] if b['t'] == 'ul')
        self.assertEqual(I.plain(ul['items'][0]['lead']), 'Check the CAS.')

    def test_editor_sentences_dropped(self):
        body = self.text(self.a['sections'][0]['blocks'])
        self.assertIn('Tuition depends on the course.', body)
        self.assertNotIn('interactive element', body)
        self.assertNotIn('should let the student', body)

    def test_editor_sections_dropped(self):
        titles = [s['title'] for s in self.a['sections']]
        self.assertEqual(titles, ['Tuition'])

    def test_faq_and_links(self):
        self.assertEqual([f['q'] for f in self.a['faq']], ['Is the fee fixed?', 'Can I work?'])
        ans = self.a['faq'][1]['a'][0]['runs']
        self.assertTrue(any(r.get('href') == 'https://www.gov.uk/student-visa/work' for r in ans))

    def test_sources(self):
        self.assertEqual(self.a['sources'][0]['title'], 'GOV.UK – Student visa')
        self.assertEqual(self.a['sources'][0]['url'], 'https://www.gov.uk/student-visa')
        self.assertEqual(self.a['sources'][0]['note'], 'Current fees and rules.')

    def test_article_without_quick_answer(self):
        self.assertEqual(self.b['quick'], [])
        self.assertEqual(len(self.b['sections']), 2)
        self.assertEqual(len(self.b['faq']), 1)


class Overrides(unittest.TestCase):
    def test_override_changes_title_and_drops_section(self):
        art = {'id': 'X-01', 'title': 'Old', 'sections': [{'title': 'Keep', 'blocks': [1]}, {'title': 'QS Rankings table', 'blocks': [1]}],
               'faq': [{'q': 'Which is top-ranked?', 'a': [1]}, {'q': 'Other?', 'a': [1]}]}
        out = I.apply_overrides(art, {'X-01': {'title': 'New', 'dropSections': ['rankings'], 'dropFaq': ['ranked']}}, [])
        self.assertEqual(out['title'], 'New')
        self.assertEqual([s['title'] for s in out['sections']], ['Keep'])
        self.assertEqual([f['q'] for f in out['faq']], ['Other?'])


class Scan(unittest.TestCase):
    def test_flags_rank_numbers_but_not_negated_guarantees(self):
        rep = []
        art = {'id': 'X-01', 'title': 'T', 'intro': [], 'quick': [], 'faq': [],
               'sections': [{'title': 'S', 'blocks': [
                   {'t': 'p', 'runs': [{'t': 'The university is ranked No. 5 in the world.'}]},
                   {'t': 'p', 'runs': [{'t': 'A degree does not guarantee a visa.'}]},
                   {'t': 'p', 'runs': [{'t': 'We guarantee your visa.'}]}]}]}
        I.scan(art, rep)
        self.assertEqual(sum('RANKING' in r for r in rep), 1)
        self.assertEqual(sum('OUTCOME' in r for r in rep), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
