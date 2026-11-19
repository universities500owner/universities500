import test from 'node:test';
import assert from 'node:assert/strict';
import { handleContact } from '../src/lib/contact-handler.js';

const URL_ = 'https://universities500.com/api/contact';
const ENV = { RESEND_API_KEY: 're_test', CONTACT_TO: 'owner@example.com' };
const NOW = Date.parse('2026-11-19T10:30:00Z');
const GOOD = { name: 'Asha K', email: 'asha@example.com', subject: 'Wrong fee on a page', message: 'The fee on the Nursing course page looks old.' };

function req(fields, headers = {}) {
  const form = new FormData();
  for (const [k, v] of Object.entries(fields)) form.set(k, v);
  return new Request(URL_, { method: 'POST', body: form, headers: { accept: 'application/json', origin: 'https://universities500.com', ...headers } });
}
function spy(status = 200) {
  const calls = [];
  const fn = async (url, init) => { calls.push({ url, init, body: JSON.parse(init.body) }); return new Response('{}', { status }); };
  return { fn, calls };
}

test('sends a valid message to the address from settings, with reply-to the visitor', async () => {
  const { fn, calls } = spy();
  const res = await handleContact(req(GOOD), ENV, fn, NOW);
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), { ok: true });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, 'https://api.resend.com/emails');
  assert.equal(calls[0].init.headers.authorization, 'Bearer re_test');
  assert.deepEqual(calls[0].body.to, ['owner@example.com']);
  assert.equal(calls[0].body.reply_to, 'asha@example.com');
  assert.match(calls[0].body.subject, /Wrong fee on a page/);
  assert.match(calls[0].body.text, /Nursing course page/);
});

test('the destination address is never returned to the browser', async () => {
  const { fn } = spy();
  const res = await handleContact(req(GOOD), ENV, fn, NOW);
  assert.ok(!(await res.text()).includes('owner@example.com'));
});

test('uses CONTACT_FROM when set, the Resend test sender otherwise', async () => {
  let s = spy(); await handleContact(req(GOOD), ENV, s.fn, NOW);
  assert.match(s.calls[0].body.from, /onboarding@resend\.dev/);
  s = spy(); await handleContact(req(GOOD), { ...ENV, CONTACT_FROM: 'Universities500 <contact@universities500.com>' }, s.fn, NOW);
  assert.equal(s.calls[0].body.from, 'Universities500 <contact@universities500.com>');
});

test('rejects missing and malformed fields without sending', async () => {
  const { fn, calls } = spy();
  const res = await handleContact(req({ name: '', email: 'not-an-email', subject: '', message: 'hi' }), ENV, fn, NOW);
  assert.equal(res.status, 422);
  const body = await res.json();
  assert.deepEqual(Object.keys(body.errors).sort(), ['email', 'message', 'name', 'subject']);
  assert.equal(calls.length, 0);
});

test('rejects over-long fields', async () => {
  const { fn, calls } = spy();
  const res = await handleContact(req({ ...GOOD, message: 'x'.repeat(4001) }), ENV, fn, NOW);
  assert.equal(res.status, 422);
  assert.ok((await res.json()).errors.message);
  assert.equal(calls.length, 0);
});

test('line breaks in name, email and subject cannot add headers', async () => {
  const { fn, calls } = spy();
  const res = await handleContact(req({ ...GOOD, subject: 'Hello\r\nBcc: spam@example.com', name: 'A\nB' }), ENV, fn, NOW);
  assert.equal(res.status, 200);
  assert.ok(!/[\r\n]/.test(calls[0].body.subject));
  assert.ok(!/Bcc: spam@example.com\n/.test(calls[0].body.subject));
});

test('a line break inside the email value is not accepted as an address', async () => {
  const { fn, calls } = spy();
  const res = await handleContact(req({ ...GOOD, email: 'a@example.com Bcc: x@example.com' }), ENV, fn, NOW);
  assert.equal(res.status, 422);
  assert.equal(calls.length, 0);
});

test('a filled hidden field looks like success but sends nothing', async () => {
  const { fn, calls } = spy();
  const res = await handleContact(req({ ...GOOD, website: 'http://spam.example' }), ENV, fn, NOW);
  assert.equal(res.status, 200);
  assert.equal(calls.length, 0);
});

test('a form sent within a moment of loading looks like success but sends nothing', async () => {
  const { fn, calls } = spy();
  const res = await handleContact(req({ ...GOOD, t: String(NOW - 500) }), ENV, fn, NOW);
  assert.equal(res.status, 200);
  assert.equal(calls.length, 0);
  const slow = await handleContact(req({ ...GOOD, t: String(NOW - 20000) }), ENV, spy().fn, NOW);
  assert.equal(slow.status, 200);
});

test('refuses a post from another site', async () => {
  const { fn, calls } = spy();
  const res = await handleContact(req(GOOD, { origin: 'https://evil.example' }), ENV, fn, NOW);
  assert.equal(res.status, 403);
  assert.equal(calls.length, 0);
});

test('reports a clear failure when settings are missing, without naming them to the visitor', async () => {
  const res = await handleContact(req(GOOD), {}, spy().fn, NOW);
  assert.equal(res.status, 500);
  const text = await res.text();
  assert.ok(!/RESEND|CONTACT_TO/.test(text));
});

test('reports a failure when Resend refuses or is unreachable', async () => {
  let res = await handleContact(req(GOOD), ENV, spy(403).fn, NOW);
  assert.equal(res.status, 502);
  res = await handleContact(req(GOOD), ENV, async () => { throw new Error('down'); }, NOW);
  assert.equal(res.status, 502);
});

test('visitors without JavaScript get a readable page, not JSON', async () => {
  const { fn } = spy();
  const res = await handleContact(req(GOOD, { accept: 'text/html' }), ENV, fn, NOW);
  assert.equal(res.status, 200);
  assert.match(res.headers.get('content-type'), /text\/html/);
  assert.match(await res.text(), /Message sent/);
});

test('only POST is accepted', async () => {
  const res = await handleContact(new Request(URL_, { method: 'GET' }), ENV, spy().fn, NOW);
  assert.equal(res.status, 405);
});
