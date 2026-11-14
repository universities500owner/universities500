// Run: node --test scripts/external-links.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { rewrite, isExternal } from './external-links.mjs';

test('outside links open in a new tab, own links do not', () => {
  const { html, changed } = rewrite('<a href="https://example.org/x">Out</a> <a href="/study-in/uk/">In</a> <a href="https://universities500.com/bot/">Own</a> <a href="https://www.universities500.com/">Own www</a> <a href="mailto:a@b.c">Mail</a>');
  assert.equal(changed, 1);
  assert.match(html, /<a rel="noopener" target="_blank" href="https:\/\/example\.org\/x">Out<span class="sr-only"> \(opens in a new tab\)<\/span><\/a>/);
  assert.match(html, /<a href="\/study-in\/uk\/">In<\/a>/);
  assert.match(html, /<a href="https:\/\/universities500\.com\/bot\/">Own<\/a>/);
  assert.match(html, /<a href="mailto:a@b\.c">Mail<\/a>/);
});

test('existing rel and aria-label are kept and extended; running twice changes nothing more', () => {
  const once = rewrite('<a class="btn" href="https://jobs.example/1" rel="noopener nofollow" aria-label="Apply for X"><b>Go</b></a>').html;
  assert.match(once, /rel="noopener nofollow"/);
  assert.match(once, /aria-label="Apply for X \(opens in a new tab\)"/);
  assert.equal((once.match(/target="_blank"/g) || []).length, 1);
  assert.equal(rewrite(once).html, once);
});

test('an existing target is replaced, and protocol-relative links count as outside', () => {
  assert.equal(isExternal('//cdn.example.org/a'), true);
  assert.equal(isExternal('#top'), false);
  assert.match(rewrite('<a target="_self" href="http://a.example/">x</a>').html, /target="_blank"/);
  assert.doesNotMatch(rewrite('<a target="_self" href="http://a.example/">x</a>').html, /_self/);
});
