// Run with: npm test   (node --test)
import test from 'node:test';
import assert from 'node:assert/strict';
import { withThe, cleanSop, nextStep, standing, validUntil, factsFor, buildDraft, checks, draftText, wordCount, questions, answered, storyDone, answersDone, courseChosen, ARCS, QIDS } from '../src/lib/sop/model.js';

const NOW = Date.parse('2026-11-23T00:00:00Z');
const card = (over = {}) => ({ course: { duration: '2 years', months: ['Feb', 'Jul'], ielts: 6.5, src: 'https://www.sample.edu/courses/msc/', on: '2026-11-12', ...over } });
const eng = { test: 'ielts', status: 'taken', overall: 7 };
const answers = () => ({
  dest: 'australia', uni: 'sample-university', uni_name: 'Sample University', course_id: 'crs:sample-university/msc-x', course_name: 'MSc Data Science', group: 'computing',
  picks: { q1: ['project'], q2: ['team'], q3: ['none'], q4: ['taught', 'psw'], q5: ['r_analyst', 'w_dest'], q6: ['team'] },
  notes: { q1: 'In my final year I cleaned a clinic\'s appointment records by hand', q2: 'I built a placement dashboard used by 40 students' },
  tone: 'plain', arc: 0,
});
const ctx = { destName: 'Australia', courseName: 'MSc Data Science', uniName: 'Sample University', group: 'computing', profileChips: [] };

test('good answers are kept and unknown keys are dropped', () => {
  const r = cleanSop({ ...answers(), passport: '123', picks: { ...answers().picks, q9: ['x'] } });
  assert.deepEqual(r.errors, {});
  assert.equal(r.value.passport, undefined);
  assert.equal(r.value.picks.q9, undefined);
  assert.equal(r.value.dest, 'australia');
});

test('a pick that is not one of the options, too many picks, or "nothing to explain" with another are refused', () => {
  assert.ok(cleanSop({ picks: { q1: ['not-a-chip'] } }).errors['picks.q1']);
  assert.ok(cleanSop({ picks: { q1: ['project', 'job', 'family'] } }).errors['picks.q1']);
  assert.ok(cleanSop({ picks: { q3: ['none', 'workgap'] } }).errors['picks.q3']);
  assert.equal(cleanSop({ picks: { q3: ['workgap', 'studygap'] } }).errors['picks.q3'], undefined);
});

test('profile chips are only accepted for question 2', () => {
  assert.equal(cleanSop({ picks: { q2: ['p:My work as Analyst at Acme'] } }).errors['picks.q2'], undefined);
  assert.ok(cleanSop({ picks: { q1: ['p:My work as Analyst at Acme'] } }).errors['picks.q1']);
});

test('notes are limited, a destination must be one of ours, and the edited text keeps line breaks', () => {
  assert.ok(cleanSop({ notes: { q1: 'x'.repeat(301) } }).errors['notes.q1']);
  assert.ok(cleanSop({ dest: 'mars' }).errors.dest);
  assert.ok(cleanSop({ uni: '../etc' }).errors.uni);
  assert.ok(cleanSop({ tone: 'angry' }).errors.tone);
  assert.ok(cleanSop({ arc: 5 }).errors.arc);
  assert.equal(cleanSop({ edited: 'One.\r\n\r\n\r\n\r\nTwo.\u0000' }).value.edited, 'One.\n\nTwo.');
  assert.ok(cleanSop({ edited: 'x'.repeat(9001) }).errors.edited);
});

test('the next step follows the profile, then the course, then the story and voice', () => {
  const all = { profile: true, academic: true, english: true, work: true };
  assert.equal(nextStep({ ...all, work: false }, {}), 'home');
  assert.equal(nextStep(all, {}), 'start');
  assert.equal(nextStep(all, { dest: 'uk', uni: 'x-university', course_name: 'MSc' }), 'story');
  assert.equal(nextStep(all, answers()), 'draft');
  const a = answers();
  assert.equal(courseChosen(a) && storyDone(a) && answersDone(a), true);
  assert.equal(answered(a), 7);
  delete a.tone;
  assert.equal(answered(a), 6);
  assert.equal(nextStep(all, a), 'story');
});

test('a source is used for a year, marked "re-check soon" in the last 30 days, and not used after that', () => {
  assert.equal(standing('2026-11-12', NOW), 'verified');
  assert.equal(standing('2025-11-30', NOW), 'recheck');
  assert.equal(standing('2025-11-01', NOW), 'old');
  assert.equal(standing('', NOW), 'old');
  assert.equal(validUntil('2026-11-12'), '12 Nov 2027');
});

test('an old fact is left out, and the student\'s own score is marked as theirs', () => {
  const f = factsFor(card({ on: '2025-01-01' }), { english: eng }, NOW);
  assert.deepEqual(f.map((x) => x.id), ['P1']);
  const g = factsFor(card(), { english: eng }, NOW);
  assert.deepEqual(g.map((x) => x.id), ['F1', 'F2', 'F3', 'P1']);
  assert.equal(g.find((x) => x.id === 'P1').chip, 'Your data');
  assert.equal(g.find((x) => x.id === 'F1').chip, 'Verified');
  assert.equal(factsFor(card({ duration: null, months: [], ielts: null }), { english: { test: 'ielts', status: 'planned' } }, NOW).length, 0);
});

test('the draft holds only the student\'s words, checked facts and gaps', () => {
  const facts = factsFor(card(), { english: eng }, NOW);
  const paras = buildDraft(answers(), ctx, facts);
  const text = draftText(paras);
  assert.match(text, /clinic's appointment records by hand\./);
  assert.match(text, /Sample University's MSc Data Science takes 2 years, with intakes in Feb and Jul\./);
  assert.match(text, /IELTS overall score of 7 meets the course requirement of 6.5\./);
  // every number in the draft comes from an answer or a fact
  const allowed = new Set(['2', '7', '6.5', '40']);
  for (const n of text.match(/\d+(?:\.\d+)?/g) || []) assert.ok(allowed.has(n), `unexpected number ${n}`);
  // every fact sentence names facts that exist
  for (const s of paras.flatMap((p) => p.items)) for (const id of s.f) assert.ok(facts.some((f) => f.id === id), id);
});

test('where the student wrote nothing, the draft shows a gap and does not make something up', () => {
  const a = answers();
  a.notes = {};
  a.picks.q3 = ['studygap'];
  const paras = buildDraft(a, ctx, []);
  const gaps = paras.flatMap((p) => p.items).filter((s) => s.k === 'g');
  assert.ok(gaps.length >= 4, 'moment, proud work, record, why');
  assert.ok(gaps.every((g) => /^\[.*\]$/.test(g.t)));
  assert.equal(checks(paras, []).gaps, gaps.length);
  assert.equal(wordCount(draftText(paras)) > 0, true);
  assert.doesNotMatch(draftText(paras), /takes \d/, 'no course length without a fact');
});

test('a score below the requirement, or a different test, is not mentioned', () => {
  const below = factsFor(card({ ielts: 7.5 }), { english: eng }, NOW);
  assert.doesNotMatch(draftText(buildDraft(answers(), ctx, below)), /meets the course requirement/);
  const other = factsFor(card(), { english: { test: 'pte', status: 'taken', overall: 70 } }, NOW);
  assert.doesNotMatch(draftText(buildDraft(answers(), ctx, other)), /meets the course requirement/);
});

test('the three openings differ, and the same answers always give the same draft', () => {
  const facts = factsFor(card(), { english: eng }, NOW);
  const t = ARCS.map((_, i) => draftText(buildDraft({ ...answers(), arc: i }, ctx, facts)));
  assert.equal(new Set(t).size, 3);
  assert.equal(draftText(buildDraft(answers(), ctx, facts)), draftText(buildDraft(answers(), ctx, facts)));
});

test('questions use the destination and the subject area, and profile chips come first on question 2', () => {
  const qs = questions({ destName: 'Canada', group: 'health', profileChips: ['My work as Nurse at City Hospital'] });
  assert.equal(qs.length, QIDS.length);
  assert.match(qs[3].title, /Canada/);
  assert.ok(qs[4].chips.some((c) => c.text === 'Public health or policy'));
  assert.ok(qs[4].chips.some((c) => c.text === 'Work in Canada first'));
  assert.equal(qs[1].chips[0].own, true);
  assert.ok(questions({ group: 'unknown' })[4].chips.length > 0, 'an unknown area still gets roles');
});

test('destinations that take an article get one in a sentence', () => {
  assert.equal(withThe('usa', 'United States'), 'the United States');
  assert.equal(withThe('uk', 'United Kingdom'), 'the United Kingdom');
  assert.equal(withThe('australia', 'Australia'), 'Australia');
  assert.match(questions({ destName: withThe('usa', 'United States') })[3].title, /Why the United States and/);
});
