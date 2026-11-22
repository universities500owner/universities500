// Run with: npm test   (node --test)
import test from 'node:test';
import assert from 'node:assert/strict';
import { NOTE_MAX, WORDS, WORDS_DEFAULT, wordsTarget, withThe, cleanSop, nextStep, standing, validUntil, factsFor, buildDraft, checks, draftText, wordCount, questions, answered, storyDone, answersDone, courseChosen, ARCS, QIDS } from '../src/lib/sop/model.js';

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
  assert.ok(cleanSop({ notes: { q1: 'x'.repeat(NOTE_MAX + 1) } }).errors['notes.q1']);
  assert.equal(cleanSop({ notes: { q1: 'x'.repeat(NOTE_MAX) } }).errors['notes.q1'], undefined);
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
  assert.match(text, /I am applying for the MSc Data Science at Sample University\./);
  assert.match(text, /The course takes 2 years, and has intakes in Feb and Jul\./);
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

// ---- the story: six paragraphs, with the profile as the backbone ----------------------------------------------------

const academic = [
  { level: 'masters', institution: 'Anna University', field: 'Computer Science', status: 'ongoing', end_year: 2027, grade_type: 'cgpa10', grade: 8.2 },
  { level: 'bachelors', institution: 'SRM University', field: 'Information Technology', status: 'completed', end_year: 2025, grade_type: 'percentage', grade: 78 },
  { level: 'class12', institution: 'Don Bosco School', field: 'Science', status: 'completed', end_year: 2021, grade_type: 'percentage', grade: 91 },
];
const work = [ // latest first, as the profile keeps them
  { employer: 'Zed Labs', title: 'Analyst', type: 'full_time', start: '2025-07' },
  { employer: 'Acme Analytics', title: 'Data intern', type: 'internship', start: '2024-06', end: '2024-08' },
];
const storyCtx = { ...ctx, academic, work, profileChips: ['My work as Data intern at Acme Analytics'] };
const paraText = (paras) => paras.map((p) => p.items.map((x) => x.t).join(' '));

test('the draft is a story in six paragraphs, in the order the guides describe', () => {
  const a = { ...answers(), picks: { ...answers().picks, q2: ['p:My work as Data intern at Acme Analytics'] }, notes: { ...answers().notes, q5: 'I want to work on health data.', q6: 'I have led a team of six.' } };
  const paras = paraText(buildDraft(a, storyCtx, factsFor(card(), { english: eng }, NOW)));
  assert.equal(paras.length, 6);
  assert.match(paras[0], /clinic's appointment records/);                       // where the interest began
  assert.match(paras[1], /Class 12|Bachelor|Master/);                           // the education behind it
  assert.match(paras[2], /Zed Labs|Acme Analytics/);                            // the work
  assert.match(paras[3], /I am applying for the MSc Data Science at Sample University\./); // why this course and university
  assert.match(paras[4], /After the course I am looking at these paths/);       // what comes after
  assert.match(paras[5], /On campus I will bring teamwork\.[\s\S]*It began with a project at college, and I want to take it further at Sample University\./); // back to the start
});

test('education comes from the profile: the two highest qualifications, oldest first, and a result only in words we understand', () => {
  const [, edu] = paraText(buildDraft(answers(), storyCtx, []));
  assert.ok(edu.indexOf('SRM University') < edu.indexOf('Anna University'), 'oldest first');
  assert.match(edu, /I completed my Bachelor's degree in Information Technology at SRM University in 2025, with 78%\./);
  assert.match(edu, /I am studying my Master's degree in Computer Science at Anna University, due to finish in 2027\. My result so far is a CGPA of 8\.2 out of 10\./);
  assert.doesNotMatch(edu, /Don Bosco/, 'only the two highest qualifications');
  const other = paraText(buildDraft(answers(), { ...ctx, academic: [{ level: 'bachelors', institution: 'X College', status: 'completed', grade_type: 'other', grade: 640 }] }, []))[1];
  assert.match(other, /I completed my Bachelor's degree at X College\./);
  assert.doesNotMatch(other, /640/, 'another grading system is not worded');
  assert.match(paraText(buildDraft(answers(), { ...ctx, academic: [{ level: 'class12', institution: 'Don Bosco School', field: 'Science', status: 'completed', end_year: 2021 }] }, []))[1], /I completed Class 12 in Science at Don Bosco School in 2021\./);
});

test('without an education in the profile the draft asks for it, it does not guess', () => {
  const edu = buildDraft(answers(), ctx, [])[1].items;
  assert.equal(edu[0].k, 'g');
  assert.match(edu[0].t, /Add where you studied/);
});

test('work comes from the profile with its dates, and a job named as proudest work is not said twice', () => {
  const plain = paraText(buildDraft(answers(), storyCtx, []))[2];
  assert.match(plain, /I did an internship as Data intern at Acme Analytics, from Jun 2024 to Aug 2024\./);
  assert.match(plain, /I worked as Analyst at Zed Labs, since Jul 2025\./);
  assert.ok(plain.indexOf('Acme Analytics') < plain.indexOf('Zed Labs'), 'oldest first');
  const a = { ...answers(), picks: { ...answers().picks, q2: ['p:My work as Data intern at Acme Analytics'] } };
  const exp = paraText(buildDraft(a, storyCtx, []))[2];
  assert.equal(exp.match(/Acme Analytics/g).length, 1);
  assert.match(exp, /The work I am proudest of is my work as Data intern at Acme Analytics \(Jun 2024 to Aug 2024\)\./);
  // no work in the profile: the paragraph is just what the student chose and wrote
  assert.doesNotMatch(paraText(buildDraft(answers(), { ...storyCtx, work: [] }, []))[2], /I worked|internship as/);
});

test('every number in a story draft comes from the answers, the profile or a checked fact', () => {
  const facts = factsFor(card(), { english: eng }, NOW);
  const text = draftText(buildDraft(answers(), storyCtx, facts));
  const allowed = new Set(['2', '7', '6.5', '40', '78', '8.2', '10', '2025', '2027', '2024', '06', '08']);
  for (const n of text.match(/\d+(?:\.\d+)?/g) || []) assert.ok(allowed.has(n), `unexpected number ${n}`);
});

test('an opening on the goal says the goal once, and the profile makes the draft longer than answers alone', () => {
  const t = draftText(buildDraft({ ...answers(), arc: 2 }, storyCtx, []));
  assert.equal(t.match(/After the course I am looking at these paths/g).length, 1);
  assert.ok(wordCount(draftText(buildDraft(answers(), storyCtx, []))) > wordCount(draftText(buildDraft(answers(), ctx, []))) + 25);
});

test('the length the student wants, and a limit the university sets, are checked', () => {
  assert.deepEqual(WORDS, [400, 600, 800]);
  assert.equal(wordsTarget({}), WORDS_DEFAULT);
  assert.equal(wordsTarget({ words: 800 }), 800);
  assert.equal(wordsTarget({ words: 123 }), WORDS_DEFAULT);
  assert.equal(cleanSop({ words: 800 }).value.words, 800);
  assert.ok(cleanSop({ words: 1234 }).errors.words);
  assert.equal(cleanSop({ limit: 500 }).value.limit, 500);
  assert.equal(cleanSop({ limit: '' }).value.limit, undefined);
  for (const bad of [5, 99999, 450.5, 'many']) assert.ok(cleanSop({ limit: bad }).errors.limit, String(bad));
});
