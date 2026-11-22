import test from 'node:test';
import assert from 'node:assert/strict';
import { guard } from '../src/lib/courseGuard.js';

const course = (o) => ({ name: 'Test MSc', level: 'Master', fee: null, duration: null, ...o });

test('a deposit, a scholarship or a per-credit price is not the fee', () => {
  assert.equal(guard(course({ fee: { display: 'GBP 2,000', context: "Deposit. We'll ask you to pay £2,000 of your tuition fees in advance." } })).fee, null);
  assert.equal(guard(course({ fee: { display: 'GBP 6,000', context: "Postgraduate International Excellence Award: £6,000 scholarship towards your fees." } })).fee, null);
  assert.equal(guard(course({ fee: { display: 'GBP 22,700', context: 'Overseas fees. £22,700.' } })).fee.display, 'GBP 22,700');
});

test('a part-time or "first years" sentence does not give the length', () => {
  assert.equal(guard(course({ duration: { display: '3 years', years: 3, context: 'Duration. 3 years part-time.' } })).duration, null);
  assert.equal(guard(course({ duration: { display: '3 years', years: 3, context: 'Your first three years follow a broad curriculum.' } })).duration, null);
  assert.equal(guard(course({ duration: { display: '2 years', years: 2, context: '1 year full-time, 2 years part-time (September start).' } })).duration, null);
  assert.equal(guard(course({ duration: { display: '1 year', years: 1, context: '1 year full-time, 2 years part-time (September start).' } })).duration.display, '1 year');
  assert.equal(guard(course({ duration: { display: '1 year', years: 1, context: 'Duration. 1 year.' } })).duration.display, '1 year');
});

test('a Scottish MA (Honours) is a four-year first degree, not a Master\'s', () => {
  const g = guard(course({ name: 'Spanish MA (Honours) 2027 entry', duration: { display: '2 years', years: 2, context: 'In the first two years, students take modules.' } }));
  assert.equal(g.level, 'Bachelor');
  assert.equal(g.duration, null);
  assert.equal(guard(course({ name: 'Global Public Health MA', level: 'Master' })).level, 'Master');
});

test('the guard never changes the input and never adds a value', () => {
  const i = course({ fee: { display: 'GBP 1', context: 'deposit' }, duration: { display: '1 year', years: 1, context: 'part-time' } });
  const before = JSON.stringify(i);
  guard(i);
  assert.equal(JSON.stringify(i), before);
  assert.equal(guard(course({})).fee, null);
});
