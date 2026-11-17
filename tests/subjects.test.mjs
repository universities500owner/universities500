// Run with: npm test   (node --test)
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { compile, subjectsOf, exactSubject, suggestSubjects, hintFromUrl, norm } from '../src/lib/subjects.js';

const def = JSON.parse(fs.readFileSync(new URL('../src/data/subjects.json', import.meta.url), 'utf8'));
const c = compile(def);
const ids = (name, degree = '', url = '', uni = '') => subjectsOf(c, { name, degree, url }, uni);

test('every subject has a name, a group that exists, and words to match', () => {
  const groups = new Set(def.groups.map((g) => g.id));
  const seen = new Set();
  for (const s of def.subjects) {
    assert.ok(s.name && s.id, `subject needs id and name: ${JSON.stringify(s)}`);
    assert.ok(!seen.has(s.id), `duplicate id ${s.id}`);
    seen.add(s.id);
    assert.ok(groups.has(s.group), `${s.id}: unknown group ${s.group}`);
    assert.ok((s.any && s.any.length) || (s.includes && s.includes.length), `${s.id}: nothing to match`);
    for (const inc of s.includes || []) assert.ok(def.subjects.some((x) => x.id === inc), `${s.id}: includes unknown ${inc}`);
  }
});

test('the plain cases a student would try', () => {
  assert.ok(ids('Nursing').includes('nursing'));
  assert.ok(ids('Master of Nursing (Graduate Entry)').includes('nursing'));
  assert.ok(ids('Midwifery').includes('nursing'));
  assert.ok(ids('Computer Science', 'BSc (Hons)').includes('computer-science'));
  assert.ok(ids('Artificial Intelligence').includes('ai'));
  assert.ok(ids('Data Science and Analytics').includes('data-science'));
  assert.ok(ids('Master of Laws', 'LLM').includes('law'));
  assert.ok(ids('Clinical Psychology').includes('psychology'));
  assert.ok(ids('Pharmacy').includes('pharmacy'));
});

test('a word must start the match, so a different word that contains it does not count', () => {
  assert.ok(!ids('Lawn Care Management').includes('law'));
  assert.ok(!ids('Medicinal Chemistry').includes('medicine'));
  assert.ok(ids('Medicinal Chemistry').includes('pharmacy'));
  assert.ok(!ids('Transport Studies').includes('sport'));
});

test('exclusions keep a course out of a subject it only looks like', () => {
  assert.ok(!ids('Veterinary Medicine').includes('medicine'));
  assert.ok(ids('Veterinary Medicine').includes('veterinary'));
  assert.ok(!ids('Biomedical Engineering').includes('biomedical-science'));
  assert.ok(ids('Biomedical Engineering').includes('biomedical-eng'));
  assert.ok(!ids('Environmental Sciences (B.Sc.) taught in English').includes('english'));
  assert.ok(!ids('Information Security').includes('criminology'));
});

test('a broad subject covers the narrow ones it includes', () => {
  const civil = ids('Civil Engineering', 'BEng (Hons)');
  assert.ok(civil.includes('civil-eng') && civil.includes('engineering'));
  const mkt = ids('Digital Marketing');
  assert.ok(mkt.includes('marketing') && mkt.includes('business'));
  assert.ok(!ids('Accounting and Finance').includes('business'), 'accounting and finance have their own subjects');
});

test('a course can sit in more than one subject', () => {
  const x = ids('Computer Science with Artificial Intelligence');
  assert.ok(x.includes('computer-science') && x.includes('ai'));
});

test('an abbreviation degree alone does not decide the subject, a long degree title does', () => {
  assert.deepEqual(ids('Class Profile', 'MBA'), []);
  assert.ok(ids('Programme overview', 'Master of Public Health').includes('public-health'));
});

test('a page saved under the university name is read from its address', () => {
  const url = 'https://www.kcl.ac.uk/study/undergraduate/courses/accounting-finance-bsc';
  assert.equal(hintFromUrl(url), 'accounting finance bsc');
  assert.ok(subjectsOf(c, { name: "King's College London", degree: 'BSc', url }, "King's College London").includes('accounting'));
  // a real name is never overridden by the address
  assert.deepEqual(subjectsOf(c, { name: 'Welcome', degree: 'BSc', url }, "King's College London"), []);
  // a dated intake page falls back to the course folder
  assert.equal(hintFromUrl('https://www.aston.ac.uk/study/courses/mba-full-time-mba/january-2027'), 'mba full time mba');
});

test('typed words find a subject', () => {
  assert.equal(exactSubject(c, 'nursing and midwifery').id, 'nursing');
  assert.equal(exactSubject(c, 'IT').id, 'it');
  assert.equal(exactSubject(c, 'cs').id, 'computer-science');
  assert.equal(exactSubject(c, 'nonsense words'), null);
  assert.equal(suggestSubjects(c, 'nurs')[0].id, 'nursing');
  assert.ok(suggestSubjects(c, 'data').map((s) => s.id).includes('data-science'));
  assert.deepEqual(suggestSubjects(c, ''), []);
});

test('no two subjects answer to the same typed word', () => {
  const owner = new Map();
  for (const s of c.subjects) {
    for (const a of s.alias) {
      assert.ok(!owner.has(a) || owner.get(a) === s.id, `"${a}" names both ${owner.get(a)} and ${s.id}`);
      owner.set(a, s.id);
    }
  }
});

test('the short names a student would type find the right subject', () => {
  const want = { nursing: 'nursing', 'data science': 'data-science', 'computer science': 'computer-science', business: 'business', law: 'law',
    engineering: 'engineering', finance: 'finance', psychology: 'psychology', 'public health': 'public-health', architecture: 'architecture', education: 'education', medicine: 'medicine' };
  for (const [typed, id] of Object.entries(want)) assert.equal((exactSubject(c, typed) || {}).id, id, typed);
});

test('norm drops accents, apostrophes and punctuation', () => {
  assert.equal(norm("King’s College — Café & Bar"), 'kings college cafe and bar');
});

test('the real course list: most courses get a subject and nursing is found', () => {
  const data = JSON.parse(fs.readFileSync(new URL('../src/data/courses.json', import.meta.url), 'utf8'));
  const unis = new Map(JSON.parse(fs.readFileSync(new URL('../src/data/universities.json', import.meta.url), 'utf8')).map((u) => [u.slug, u.name]));
  let hit = 0; let nursing = 0;
  for (const i of data.items) {
    const s = subjectsOf(c, i, unis.get(i.uni));
    if (s.length) hit += 1;
    if (s.includes('nursing')) nursing += 1;
  }
  assert.ok(hit / data.items.length > 0.9, `only ${hit} of ${data.items.length} have a subject`);
  assert.ok(nursing >= 20, `only ${nursing} nursing courses`);
});
