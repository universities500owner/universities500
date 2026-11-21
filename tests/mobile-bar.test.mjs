// Run with: npm test   (node --test)
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { LINES, VISA_SELF_CHECK_COUNTRIES, lineFor } from '../src/lib/mobile-bar.js';
import { MENU, TABS, TAB_IDS } from '../src/lib/student-menu.js';

test('the shortlist line is the default on every ordinary page', () => {
  for (const p of ['/', '/courses/', '/courses/rmit-university/bachelor-of-applied-science-aviation-60ac81/', '/universities/', '/scholarships/', '/internships/uk/', '/search/', '/study-in/canada/', '/study-in/', '/budget/']) {
    assert.equal(lineFor(p), 'shortlist', p);
  }
});

test('application prep, English tests and exams get the prep line', () => {
  for (const p of ['/application-prep/', '/english-test/', '/exams/', '/exams/ielts/']) assert.equal(lineFor(p), 'prep', p);
});

test('the visa line shows on the visa hub and on destinations that have a self-check', () => {
  assert.equal(lineFor('/visa-readiness/'), 'visa');
  assert.equal(lineFor('/study-in/australia/'), 'visa');
  assert.equal(lineFor('/study-in/canada/'), 'shortlist', 'no self-check for Canada yet');
  assert.equal(lineFor('/study-in/canada/', [...VISA_SELF_CHECK_COUNTRIES, 'canada']), 'visa', 'adding a country to the list is enough');
});

test('a path with no trailing slash, a query or a hash is read the same way', () => {
  assert.equal(lineFor('/study-in/australia'), 'visa');
  assert.equal(lineFor('/application-prep?x=1'), 'prep');
  assert.equal(lineFor('/visa-readiness/#nz'), 'visa');
});

test('every line is short enough to stay on one line in the bar', () => {
  for (const [k, text] of Object.entries(LINES)) assert.ok(text.length <= 23, `${k}: "${text}" is ${text.length} characters`);
  assert.deepEqual(Object.keys(LINES).sort(), ['prep', 'shortlist', 'visa']);
});

test('the lines say only what is true today', () => {
  for (const text of Object.values(LINES)) assert.doesNotMatch(text, /odds|chance|guarantee|approved|assessment/i, text);
});

test('the phone tabs are real dashboard pages with short labels', () => {
  const ids = MENU.map(([id]) => id);
  for (const [id, label] of TABS) {
    assert.ok(ids.includes(id), id);
    assert.ok(label.length <= 10, `${label} must fit under an icon`);
  }
  assert.equal(TAB_IDS.length, 4);
});

test('every built dashboard menu link has a page', () => {
  for (const [id, , href] of MENU) {
    if (!href) continue;
    const rel = href === '/student/' ? 'index' : href.replace(/^\/student\/|\/$/g, '');
    assert.ok(fs.existsSync(new URL(`../src/pages/student/${rel}.astro`, import.meta.url)), `${id} -> ${href}`);
  }
});
