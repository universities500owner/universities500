// The sign-in email lives in supabase/email-templates and is pasted into Supabase by hand, so these checks stop a bad edit
// (a missing code, a stray script, a link to another site) from reaching real students.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';

const dir = new URL('../supabase/email-templates/', import.meta.url);
const files = readdirSync(dir).filter((f) => f.endsWith('.html'));

test('there is at least one email template', () => { assert.ok(files.length >= 1); });

for (const f of files) {
  const html = readFileSync(new URL(f, dir), 'utf8');

  test(`${f}: only the variables Supabase fills in`, () => {
    const vars = [...html.matchAll(/\{\{\s*([^}]*?)\s*\}\}/g)].map((m) => m[1]);
    for (const v of vars) assert.ok(['.Token', '.Email'].includes(v), `unexpected variable {{ ${v} }}`);
    assert.ok(vars.includes('.Token'), 'the code (.Token) must be in the email');
  });

  test(`${f}: no scripts, forms, remote styles or fonts`, () => {
    assert.ok(!/<script|<form|<iframe|<link\b|@import|@font-face/i.test(html));
  });

  test(`${f}: every link and image is https on universities500.com`, () => {
    const urls = [...html.matchAll(/(?:href|src)="([^"]+)"/g)].map((m) => m[1]);
    assert.ok(urls.length > 0);
    for (const u of urls) assert.match(u, /^https:\/\/universities500\.com\//, `unexpected address ${u}`);
  });

  test(`${f}: images have alt text, and nothing names an employer`, () => {
    for (const tag of html.match(/<img\b[^>]*>/gi) || []) assert.match(tag, /\balt="[^"]+"/);
    assert.ok(!/\bIDP\b/.test(html));
  });
}
