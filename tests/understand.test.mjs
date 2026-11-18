import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { compile } from '../src/lib/subjects.js';
import { buildLexicon, understand, distance } from '../src/lib/understand.js';

const def = JSON.parse(fs.readFileSync(new URL('../src/data/subjects.json', import.meta.url), 'utf8'));
const countries = [['uk', 'United Kingdom'], ['usa', 'United States'], ['canada', 'Canada'], ['australia', 'Australia'], ['new-zealand', 'New Zealand'], ['ireland', 'Ireland'], ['germany', 'Germany'], ['france', 'France'], ['uae', 'United Arab Emirates']]
  .map(([code, name]) => ({ code, name }));
const lex = buildLexicon({ countries, subjects: compile(def) });
const U = (q, ignore) => understand(q, lex, ignore ? new Set(ignore) : undefined);

test('the question from the screenshot is understood', () => {
  const u = U('Masters in engineering in Australia');
  assert.equal(u.level, 'master');
  assert.deepEqual(u.countries, ['australia']);
  assert.equal(u.subject.id, 'engineering');
  assert.deepEqual(u.rest, []);
});

test('level words', () => {
  assert.equal(U('undergrad nursing').level, 'bachelor');
  assert.equal(U('postgraduate law uk').level, 'master');
  assert.equal(U('msc data science').level, 'master');
  assert.equal(U('bachelor or master in law').level, null, 'both levels means no level');
});

test('countries by name, by short name and several at once', () => {
  assert.deepEqual(U('law in the UK or Canada').countries, ['uk', 'canada']);
  assert.deepEqual(U('nursing new zealand').countries, ['new-zealand']);
  assert.deepEqual(U('study in britain').countries, ['uk']);
  assert.deepEqual(U('best universities in the US').countries, ['usa']);
  assert.deepEqual(U('tell us about law').countries, [], '"us" in lower case is a pronoun');
  assert.deepEqual(U('dubai business').countries, ['uae']);
});

test('subjects by the short names a student types', () => {
  assert.equal(U('data science').subject.id, 'data-science');
  assert.equal(U('cs masters').subject.id, 'computer-science');
  assert.equal(U('public health canada').subject.id, 'public-health');
  assert.equal(U('nursing').subject.id, 'nursing');
});

test('a fee limit needs a currency, or one destination to take it from', () => {
  assert.deepEqual(U('data science under 25000 aud').budget, { amount: 25000, currency: 'AUD' });
  assert.deepEqual(U('law in uk under £20,000').budget, { amount: 20000, currency: 'GBP' });
  assert.deepEqual(U('nursing canada below 15k').budget, { amount: 15000, currency: 'CAD' });
  const none = U('nursing under 20000');
  assert.equal(none.budget.currency, null);
  assert.ok(none.notes.length > 0, 'it says why it cannot use the number');
  assert.equal(U('business in 2027').budget, null, 'a year is not money');
  assert.equal(U('law ielts 6.5').budget, null, 'an IELTS score is not money');
  assert.equal(U('under 20 lakhs mba').budget.currency, 'INR');
});

test('IELTS and start month', () => {
  assert.equal(U('business uk ielts 6.5').ielts, 6.5);
  assert.equal(U('business uk 6 ielts').ielts, 6);
  assert.equal(U('law canada september intake').month, 'Sep');
  assert.equal(U('law canada in may').month, 'May');
  assert.equal(U('you may like law').month, null, '"may" is a month only after a word like "in"');
});

test('topics are kept as topics', () => {
  assert.ok(U('scholarships for engineering in germany').topics.includes('scholarship'));
  assert.ok(U('student visa canada').topics.includes('visa'));
  const g = U('graduate route visa uk');
  assert.equal(g.level, null, '"graduate route" is a visa, not a Master\'s');
  assert.ok(g.topics.includes('work'));
  assert.ok(U('mba in uk').topics.includes('mba'));
  assert.equal(U('mba in uk').subject, null, 'MBA goes to the MBA Explorer, not the business subject');
});

test('flags: ranking and universities words', () => {
  const u = U('best universities for law');
  assert.equal(u.flags.ranking, true);
  assert.equal(u.flags.universities, true);
});

test('spelling is repaired, and shown', () => {
  const u = U('nusing masters canada');
  assert.equal(u.subject.id, 'nursing');
  assert.deepEqual(u.fixes, [['nusing', 'nursing']]);
  assert.equal(U('enginering australia').subject.id, 'engineering');
  assert.deepEqual(U('leeds').fixes, [], 'a place name is left alone');
  assert.deepEqual(U('oxford').rest, ['oxford']);
  assert.equal(distance('nusing', 'nursing'), 1);
  assert.equal(distance('nursign', 'nursing'), 1, 'two letters swapped is one change');
});

test('chips the visitor removed are not applied', () => {
  const u = U('masters in nursing in canada', ['level', 'country:canada']);
  assert.equal(u.level, null);
  assert.deepEqual(u.countries, []);
  assert.equal(u.subject.id, 'nursing');
  assert.deepEqual(u.rest, [], 'a removed word does not turn into a text search');
});

test('chips come in a steady order', () => {
  const u = U('canada nursing masters ielts 6 september');
  assert.deepEqual(u.chips.map((c) => c.kind.split(':')[0]), ['level', 'subject', 'country', 'month', 'ielts']);
});

test('words that name nothing stay as plain words', () => {
  const u = U('hello world');
  assert.deepEqual(u.rest, ['hello', 'world']);
  assert.equal(u.subject, null);
  assert.deepEqual(U('').chips, []);
});
