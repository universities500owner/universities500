import test from 'node:test';
import assert from 'node:assert/strict';
import { assessAu, moneyNeeded, REQUIRED, BAND_LABEL } from '../src/lib/visa/au-check.js';
import { MONEY, WEIGHTS, ENGLISH, CHECKED } from '../src/lib/visa/au-rules.js';
import { cleanSection, sectionDone, SECTION_IDS, PROFILE_SECTION_IDS } from '../src/lib/account/schema.js';

const NOW = Date.UTC(2026, 10, 21);

// A strong, complete set of answers. Each test changes one thing.
const strong = () => ({
  english: { test: 'ielts', status: 'taken', overall: 7 },
  immigration: { history: 'none' },
  visa_au: {
    tuition: 30000, funds: 80000, funds_status: 'ready', funds_trail: 'documented', partner: false, children: 0,
    course_link: 'related', reasons: 'clear', gap: 'none', ties_family: true, ties_assets: true, ties_career: true, docs: 'ready',
  },
});
const withV = (patch, rest = {}) => { const s = strong(); Object.assign(s.visa_au, patch); return Object.assign(s, rest); };

test('weights add up to 100 and every part has a factor', () => {
  assert.equal(Object.values(WEIGHTS).reduce((a, b) => a + b, 0), 100);
  const r = assessAu(strong(), NOW);
  assert.deepEqual(r.factors.map((f) => f.id), ['funds', 'fit', 'english', 'history', 'evidence']);
  for (const f of r.factors) assert.equal(f.max, WEIGHTS[f.id]);
});

test('a strong, complete case is Green with 100 points and nothing holding it down', () => {
  const r = assessAu(strong(), NOW);
  assert.equal(r.complete, true);
  assert.equal(r.score, 100);
  assert.equal(r.band, 'green');
  assert.equal(r.held, false);
  assert.deepEqual(r.flags, []);
});

test('missing answers give no band, and name what is missing', () => {
  const r = assessAu({ visa_au: { tuition: 30000 } }, NOW);
  assert.equal(r.complete, false);
  assert.equal(r.band, undefined);
  assert.equal(r.score, undefined);
  assert.ok(r.missing.includes('funds') && !r.missing.includes('tuition'));
  assert.deepEqual(assessAu(undefined, NOW).missing, REQUIRED);
  // 0 is an answer, not a blank
  assert.equal(assessAu(withV({ funds: 0 }), NOW).complete, true);
});

test('money needed: tuition + living, with a partner, children and school costs', () => {
  assert.equal(moneyNeeded({ tuition: 30000 }).total, 30000 + MONEY.living);
  assert.equal(moneyNeeded({ tuition: 0, partner: true }).total, MONEY.living + MONEY.partner);
  assert.equal(moneyNeeded({ tuition: 10000, children: 2, school_children: 1 }).total, 10000 + MONEY.living + 2 * MONEY.child + MONEY.school);
  // school children can never exceed children, whatever is passed in
  assert.equal(moneyNeeded({ tuition: 0, children: 1, school_children: 5 }).schooling, MONEY.school);
  assert.equal(moneyNeeded({ tuition: 0, children: -2 }).total, MONEY.living);
});

test('funds: below the money counted holds the result at Red whatever the rest', () => {
  const need = 30000 + MONEY.living;
  const r = assessAu(withV({ funds: need - 1 }), NOW);
  assert.equal(r.factors[0].score, 0);
  assert.equal(r.band, 'red');
  assert.equal(r.held, true);
  assert.ok(r.flags.some((f) => f.id === 'funds_short'));
  assert.equal(r.actions[0].must, true); // the first thing to fix is the shortfall
  assert.match(r.actions[0].text, /AUD 1/); // names the shortfall
});

test('funds: spare money steps the points up at 100%, 110% and 125%', () => {
  const need = 30000 + MONEY.living;
  const pts = (funds, status = 'ready') => assessAu(withV({ funds: Math.ceil(need * funds), funds_status: status }), NOW).factors[0].score;
  assert.equal(pts(1.0), 12);
  assert.equal(pts(1.1), 22);
  assert.equal(pts(1.25), 30);
  assert.ok(pts(1.25, 'partial') < pts(1.25, 'ready'));
  assert.ok(pts(1.25, 'planned') < pts(1.25, 'partial'));
});

test('English: score against the visa score, with the pathway score as a floor', () => {
  const at = (test, overall, status = 'taken') => assessAu({ ...strong(), english: { test, status, overall } }, NOW);
  assert.equal(at('ielts', 6.5).factors[2].score, 15);
  assert.equal(at('ielts', 6).factors[2].score, 11);
  assert.equal(at('ielts', 5.5).factors[2].score, 6);
  assert.equal(at('ielts', 5).factors[2].score, 2);
  assert.equal(at('pte', 58).factors[2].score, 15);
  assert.equal(at('pte', 50).factors[2].score, 11);
  assert.equal(at('pte', 42).factors[2].score, 6);
  assert.equal(at('toefl', 79).factors[2].score, 15);
  assert.equal(at('toefl', 64).factors[2].score, 11);
  assert.equal(at('toefl', 46).factors[2].score, 6);
  // the numbers come from the rules file, not from this test
  assert.equal(ENGLISH.ielts.standard, 6);
  // meeting the visa score does not hold anything down; being below it caps at Amber
  assert.deepEqual(at('ielts', 6).flags, []);
  const low = at('ielts', 5.5);
  assert.equal(low.band, 'amber');
  assert.ok(low.flags.some((f) => f.id === 'english_below'));
});

test('English: no test, a planned test, an unknown test and nothing added', () => {
  const eng = (e) => assessAu({ ...strong(), english: e }, NOW).factors[2];
  assert.equal(eng({ test: 'none' }).score, 3);
  assert.equal(eng({ test: 'ielts', status: 'planned' }).score, 6);
  assert.equal(eng({ test: 'ielts', status: 'booked' }).score, 6);
  assert.equal(eng({ test: 'duolingo', status: 'taken', overall: 130 }).score, 6);
  assert.equal(eng({ test: 'other', other_name: 'X', status: 'taken', overall: 7 }).score, 6);
  assert.equal(eng(undefined).score, 3);
  assert.match(eng({ test: 'duolingo', status: 'taken', overall: 130 }).notes.join(' '), /cannot compare/);
});

test('visa history: none, not said, and not answered', () => {
  const h = (imm) => assessAu({ ...strong(), immigration: imm }, NOW).factors[3];
  assert.equal(h({ history: 'none' }).score, 15);
  assert.equal(h({ history: 'prefer_not' }).score, 10);
  assert.equal(h(undefined).score, 10);
  assert.equal(h({}).score, 10);
  // choosing not to say is never a flag
  assert.deepEqual(assessAu({ ...strong(), immigration: { history: 'prefer_not' } }, NOW).flags, []);
});

test('visa history: a recent study refusal holds the result at Amber at best', () => {
  const imm = { history: 'some', items: [{ country: 'Canada', year: 2025, kind: 'study', outcome: 'refused' }] };
  const r = assessAu({ ...strong(), immigration: imm }, NOW);
  assert.equal(r.factors[3].score, 6);
  assert.ok(r.flags.some((f) => f.id === 'recent_refusal'));
  assert.equal(r.scoreBand, 'green'); // the points alone would still be Green
  assert.equal(r.band, 'amber');
  assert.equal(r.held, true);
  // the action to take is first
  assert.equal(r.actions[0].must, true);
});

test('visa history: an old or a visit refusal costs points but does not hold the band', () => {
  const run = (items) => assessAu({ ...strong(), immigration: { history: 'some', items } }, NOW);
  const old = run([{ country: 'UK', year: 2015, kind: 'study', outcome: 'refused' }]);
  assert.equal(old.factors[3].score, 13);
  assert.deepEqual(old.flags, []);
  const visit = run([{ country: 'USA', year: 2024, kind: 'visit', outcome: 'refused' }]);
  assert.equal(visit.factors[3].score, 10);
  assert.deepEqual(visit.flags, []);
  // a granted visa costs nothing; withdrawn costs a little; points never go below 0
  assert.equal(run([{ country: 'UK', year: 2022, kind: 'study', outcome: 'granted' }]).factors[3].score, 15);
  assert.equal(run([{ country: 'UK', year: 2022, kind: 'study', outcome: 'withdrawn' }]).factors[3].score, 14);
  const many = run(Array.from({ length: 5 }, () => ({ country: 'X', year: 2024, kind: 'visit', outcome: 'refused' })));
  assert.equal(many.factors[3].score, 0);
});

test('visa history: a cancelled visa holds the result at Amber', () => {
  const r = assessAu({ ...strong(), immigration: { history: 'some', items: [{ country: 'USA', year: 2020, kind: 'visit', outcome: 'cancelled' }] } }, NOW);
  assert.ok(r.flags.some((f) => f.id === 'cancelled'));
  assert.equal(r.band, 'amber');
});

test('two flags: the harder one wins, and a flag can never raise a band', () => {
  const s = withV({ funds: 1000 }, { immigration: { history: 'some', items: [{ country: 'UK', year: 2025, kind: 'study', outcome: 'refused' }] } });
  assert.equal(assessAu(s, NOW).band, 'red');
  const weak = withV({ funds: 1000 });
  weak.visa_au.course_link = 'unrelated'; weak.visa_au.reasons = 'not_yet'; weak.visa_au.gap = 'unexplained';
  assert.equal(assessAu(weak, NOW).band, 'red');
});

test('bands change at 75 and 50, using the points alone', () => {
  // build cases by lowering the fit and evidence answers with funds and English kept strong
  const mk = (patch) => assessAu(withV(patch), NOW);
  const a = mk({ course_link: 'partly', reasons: 'general', gap: 'explained', ties_career: false, docs: 'some', funds_trail: 'some' });
  assert.equal(a.score, 30 + (7 + 4 + 4) + 15 + 15 + (4 + 2 + 2));
  assert.equal(a.band, a.score >= 75 ? 'green' : a.score >= 50 ? 'amber' : 'red');
  const b = mk({ course_link: 'unrelated', reasons: 'not_yet', gap: 'unexplained', ties_family: false, ties_assets: false, ties_career: false, docs: 'not_started', funds_trail: 'no', funds_status: 'planned' });
  assert.ok(b.score < 50 && b.band === 'red');
  assert.equal(BAND_LABEL[b.band], 'Red');
});

test('actions: at most five, must-do first, then the biggest gain', () => {
  const r = assessAu(withV({ funds: 1000, course_link: 'unrelated', reasons: 'not_yet', gap: 'unexplained', docs: 'not_started', funds_trail: 'no', ties_family: false }), NOW);
  assert.ok(r.actions.length <= 5);
  assert.equal(r.actions[0].must, true);
  const gains = r.actions.filter((a) => !a.must).map((a) => a.gain);
  assert.deepEqual(gains, [...gains].sort((x, y) => y - x));
  assert.deepEqual(assessAu(strong(), NOW).actions, []);
});

test('the result carries its date and sources so the page can show them', () => {
  const r = assessAu(strong(), NOW);
  assert.equal(r.checked, CHECKED);
  assert.ok(r.sources.length >= 3 && r.sources.every((s) => /^https:\/\//.test(s.url)));
});

test('the result never says how likely a visa is', () => {
  const text = JSON.stringify(assessAu(strong(), NOW)) + JSON.stringify(assessAu(withV({ funds: 1 }), NOW));
  assert.doesNotMatch(text, /probab|chance|likel|guarantee|approv/i);
});

// ---- the stored section ---------------------------------------------------------------------------------------------

test('visa_au is stored but is not a profile page section', () => {
  assert.ok(SECTION_IDS.includes('visa_au'));
  assert.ok(!PROFILE_SECTION_IDS.includes('visa_au'));
  assert.deepEqual(PROFILE_SECTION_IDS.filter((x) => !SECTION_IDS.includes(x)), []);
});

test('visa_au: checks, cleans and drops what does not belong', () => {
  const ok = cleanSection('visa_au', { ...strong().visa_au, funds: '80000', evil: '<script>', children: 2, school_children: 1 }, NOW);
  assert.deepEqual(ok.errors, {});
  assert.equal(ok.value.funds, 80000);
  assert.equal(ok.value.evil, undefined);
  assert.equal(ok.value.ties_career, true);
  assert.equal(ok.value.partner, undefined); // an unticked box is not stored
  const bad = cleanSection('visa_au', { tuition: -5, funds: 1.5, funds_status: 'rich', course_link: 'x', children: 1, school_children: 3 }, NOW);
  for (const k of ['tuition', 'funds', 'funds_status', 'course_link', 'school_children', 'funds_trail', 'reasons', 'gap', 'docs']) assert.ok(bad.errors[k], k);
  // school children is only asked when there are children
  assert.equal(cleanSection('visa_au', { ...strong().visa_au, school_children: 2 }, NOW).value.school_children, undefined);
});

test('visa_au: done means every required answer is there', () => {
  assert.equal(sectionDone('visa_au', strong().visa_au), true);
  assert.equal(sectionDone('visa_au', { tuition: 1 }), false);
  assert.equal(sectionDone('visa_au', undefined), false);
});

test('what the form saves can be scored, and gives the same result as the raw answers', () => {
  const saved = cleanSection('visa_au', strong().visa_au, NOW).value;
  assert.equal(assessAu({ ...strong(), visa_au: saved }, NOW).score, 100);
});
