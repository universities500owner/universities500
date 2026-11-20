// Run with: npm test   (node --test)
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { normaliseGmail } from '../src/lib/account/gmail.js';
import { COUNTRIES, SUBJECT_GROUPS, STAGES, cleanSection, cleanStudent, sectionDone, plansDone, SECTION_IDS } from '../src/lib/account/schema.js';

const read = (p) => JSON.parse(fs.readFileSync(new URL(p, import.meta.url), 'utf8'));
const NOW = Date.UTC(2026, 10, 20);

// ---- Gmail -----------------------------------------------------------------------------------------------------

test('Gmail addresses are reduced to one canonical form', () => {
  for (const [typed, want] of [
    ['Jo.Smith@Gmail.com', 'josmith@gmail.com'],
    ['  josmith+uni.2027@gmail.com ', 'josmith@gmail.com'],
    ['j.o.s.m.i.t.h@googlemail.com', 'josmith@gmail.com'],
    ['JOSMITH@GMAIL.COM', 'josmith@gmail.com'],
    ['raja.2026@gmail.com', 'raja2026@gmail.com'],
  ]) assert.deepEqual(normaliseGmail(typed), { ok: true, email: want }, typed);
});

test('only valid Gmail addresses are accepted', () => {
  const code = (s) => normaliseGmail(s).error;
  assert.equal(code(''), 'empty');
  assert.equal(code(undefined), 'empty');
  assert.equal(code('someone@yahoo.com'), 'not_gmail');
  assert.equal(code('someone@gmail.co.in'), 'not_gmail');
  assert.equal(code('someone@mail.gmail.com'), 'not_gmail');
  assert.equal(code('someone@gmail.com.evil.com'), 'not_gmail');
  for (const bad of ['a@gmail.com', 'abc.d@gmail.com', '.josmith@gmail.com', 'josmith.@gmail.com', 'jo..smith@gmail.com', 'jo_smith@gmail.com',
    'jo smith@gmail.com', 'josmith@@gmail.com', 'jo@smith@gmail.com', '+tag@gmail.com', 'josmith@gmail.com,other@gmail.com', '"jo"@gmail.com',
    'a'.repeat(31) + '@gmail.com', '<josmith>@gmail.com']) {
    assert.equal(normaliseGmail(bad).ok, false, bad);
  }
});

// ---- the lists match the rest of the site ----------------------------------------------------------------------

test('destinations match the guides', () => {
  const guides = read('../src/data/guides.json').map((g) => g.slug).sort();
  assert.deepEqual(COUNTRIES.map((c) => c[0]).sort(), guides);
});

test('subject groups match the course search', () => {
  const groups = read('../src/data/subjects.json').groups;
  assert.deepEqual(SUBJECT_GROUPS.map((g) => [g[0], g[1]]), groups.map((g) => [g.id, g.name]));
});

// ---- sections --------------------------------------------------------------------------------------------------

test('about you: trims, requires the basics and keeps adults only', () => {
  const ok = cleanSection('profile', { full_name: '  Asha   Rao ', birth_year: '2001', nationality: 'Indian', city: '', extra: 'dropped' }, NOW);
  assert.deepEqual(ok, { value: { full_name: 'Asha Rao', birth_year: 2001, nationality: 'Indian' }, errors: {} });
  const bad = cleanSection('profile', { birth_year: 2012 }, NOW).errors;
  assert.ok(bad.full_name && bad.nationality);
  assert.match(bad.birth_year, /18 or older/);
  assert.match(cleanSection('profile', { full_name: 'A', nationality: 'x', birth_year: 2009 }, NOW).errors.birth_year, /18 or older/);
  assert.deepEqual(cleanSection('profile', { full_name: 'A', nationality: 'x', birth_year: 2008 }, NOW).errors, {});
});

test('text fields lose control characters and keep to their length', () => {
  const r = cleanSection('profile', { full_name: 'Asha\u0000\nRao ', birth_year: 2000, nationality: 'x'.repeat(61) }, NOW);
  assert.equal(r.value.full_name, 'Asha Rao');
  assert.match(r.errors.nationality, /under 60/);
});

test('academic history: entries are checked one by one', () => {
  const good = { level: 'bachelors', institution: 'Anna University', status: 'completed', start_year: 2018, end_year: 2022, grade_type: 'cgpa10', grade: '8.1', backlogs: 0 };
  const r = cleanSection('academic', { items: [good] }, NOW);
  assert.deepEqual(r.errors, {});
  assert.equal(r.value.items[0].grade, 8.1);
  const bad = cleanSection('academic', { items: [good, { ...good, end_year: 2017, grade: 11 }, { level: 'x' }] }, NOW).errors;
  assert.match(bad['items.1.end_year'], /before the start/);
  assert.match(bad['items.1.grade'], /more than 10/);
  assert.ok(bad['items.2.level'] && bad['items.2.institution'] && bad['items.2.status']);
  assert.equal(cleanSection('academic', { items: Array(7).fill(good) }, NOW).errors.items, 'Add up to 6 entries.');
});

test('academic history: backlogs only apply to diplomas and degrees, and a grade needs its grading', () => {
  const r = cleanSection('academic', { items: [{ level: 'class12', institution: 'S', status: 'completed', backlogs: 3, grade: 90 }] }, NOW);
  assert.equal('backlogs' in r.value.items[0], false);
  assert.equal('grade' in r.value.items[0], false);
});

test('English test: scores are checked against the test', () => {
  const base = { test: 'ielts', status: 'taken', overall: 6.5, listening: 7, reading: 6, writing: 6, speaking: 6.5 };
  assert.deepEqual(cleanSection('english', base, NOW).errors, {});
  assert.match(cleanSection('english', { ...base, overall: 6.3 }, NOW).errors.overall, /steps of 0.5/);
  assert.match(cleanSection('english', { ...base, listening: 10 }, NOW).errors.listening, /0 to 9/);
  assert.deepEqual(cleanSection('english', { test: 'toefl', status: 'taken', overall: 98, listening: 25, reading: 24, writing: 22, speaking: 27 }, NOW).errors, {});
  assert.match(cleanSection('english', { test: 'toefl', status: 'taken', overall: 130 }, NOW).errors.overall, /0 to 120/);
  assert.match(cleanSection('english', { test: 'pte', status: 'taken', overall: 5 }, NOW).errors.overall, /10 to 90/);
  const duo = cleanSection('english', { test: 'duolingo', status: 'taken', overall: 120, listening: 5 }, NOW);
  assert.deepEqual(duo.errors, {});
  assert.equal('listening' in duo.value, false);
  assert.match(cleanSection('english', { test: 'duolingo', status: 'taken', overall: 122 }, NOW).errors.overall, /steps of 5/);
});

test('English test: scores are dropped until the test is taken, and "no test yet" needs nothing else', () => {
  const planned = cleanSection('english', { test: 'ielts', status: 'planned', date: '2027-02', overall: 7 }, NOW);
  assert.deepEqual(planned, { value: { test: 'ielts', status: 'planned', date: '2027-02' }, errors: {} });
  assert.deepEqual(cleanSection('english', { test: 'none', status: 'taken', overall: 7 }, NOW), { value: { test: 'none' }, errors: {} });
  assert.ok(cleanSection('english', { test: 'other', status: 'planned' }, NOW).errors.other_name);
  assert.ok(cleanSection('english', { test: 'ielts' }, NOW).errors.status);
  assert.ok(cleanSection('english', { test: 'ielts', status: 'taken' }, NOW).errors.overall);
});

test('work experience: "none" clears the list, otherwise dates must make sense', () => {
  assert.deepEqual(cleanSection('work', { none: true, items: [{ employer: 'x' }] }, NOW), { value: { none: true }, errors: {} });
  const job = { employer: 'Zoho', title: 'Engineer', type: 'full_time', start: '2022-07', end: '2024-03' };
  assert.deepEqual(cleanSection('work', { items: [job, { ...job, end: '' }] }, NOW).errors, {});
  assert.match(cleanSection('work', { items: [{ ...job, end: '2021-01' }] }, NOW).errors['items.0.end'], /before the start/);
  assert.match(cleanSection('work', { items: [{ ...job, start: '2022-13' }] }, NOW).errors['items.0.start'], /month and year/);
  assert.ok(cleanSection('work', { items: [{}] }, NOW).errors['items.0.employer']);
});

test('immigration history: optional answers, entries only when there is something to add', () => {
  assert.deepEqual(cleanSection('immigration', { history: 'prefer_not', travel: 'UAE', items: [{ country: 'x' }] }, NOW), { value: { history: 'prefer_not' }, errors: {} });
  assert.deepEqual(cleanSection('immigration', { history: 'none', travel: 'Singapore, UAE' }, NOW), { value: { history: 'none', travel: 'Singapore, UAE' }, errors: {} });
  const some = cleanSection('immigration', { history: 'some', items: [{ country: 'Canada', year: 2024, kind: 'visit', outcome: 'refused' }] }, NOW);
  assert.deepEqual(some.errors, {});
  assert.equal(some.value.items[0].outcome, 'refused');
  assert.ok(cleanSection('immigration', { history: 'some', items: [{ country: 'Canada' }] }, NOW).errors['items.0.year']);
  assert.ok(cleanSection('immigration', {}, NOW).errors.history);
});

test('unknown sections and non-object data are rejected safely', () => {
  assert.ok(cleanSection('passport', {}, NOW).errors._);
  for (const junk of [null, 'text', 5, [], undefined]) assert.ok(Object.keys(cleanSection('profile', junk, NOW).errors).length > 0);
});

// ---- the plans part --------------------------------------------------------------------------------------------

test('plans: only known destinations, groups and stages', () => {
  const ok = cleanStudent({ display_name: ' Asha ', countries: ['uk', 'canada', 'uk'], level: 'masters', subject_groups: ['computing'], subjects: ['data-science'], stage: 'applying' });
  assert.deepEqual(ok, { value: { display_name: 'Asha', countries: ['uk', 'canada'], level: 'masters', subject_groups: ['computing'], subjects: ['data-science'], stage: 'applying' }, errors: {} });
  assert.ok(cleanStudent({ countries: ['mars'] }).errors.countries);
  assert.ok(cleanStudent({ countries: 'uk' }).errors.countries);
  assert.ok(cleanStudent({ level: 'wizard' }).errors.level);
  assert.ok(cleanStudent({ stage: 'done' }).errors.stage);
  assert.ok(cleanStudent({ subjects: ['x y'] }).errors.subjects);
  assert.equal(cleanStudent({ level: '' }).value.level, null);
});

test('plans: protected fields are never accepted', () => {
  const r = cleanStudent({ email: 'x@gmail.com', consent_at: '2000-01-01', id: 'abc', onboarded_at: '2000-01-01', stage: 'visa' });
  assert.deepEqual(r.value, { stage: 'visa' });
});

test('progress helpers', () => {
  assert.equal(STAGES.length, 5);
  assert.equal(plansDone({ countries: ['uk'], level: 'masters', subject_groups: ['arts'], stage: 'offer' }), true);
  assert.equal(plansDone({ countries: [], level: 'masters', subject_groups: ['arts'], stage: 'offer' }), false);
  assert.equal(sectionDone('academic', { items: [] }), false);
  assert.equal(sectionDone('work', { none: true }), true);
  assert.equal(sectionDone('english', { test: 'none' }), true);
  assert.equal(sectionDone('english', { test: 'ielts' }), false);
  assert.deepEqual(SECTION_IDS, ['profile', 'academic', 'english', 'work', 'immigration', 'visa_au']);
});
