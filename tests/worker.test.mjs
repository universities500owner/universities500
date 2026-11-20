import test from 'node:test';
import assert from 'node:assert/strict';
import worker, { ROUTES } from '../src/worker.js';

const SITE = 'https://universities500.com';
const assets = (calls) => ({ fetch: (req) => { calls.push(new URL(req.url).pathname); return new Response('<html>page</html>', { status: 200 }); } });

test('every API address in the site code has a route', () => {
  assert.deepEqual(Object.keys(ROUTES).sort(), [
    '/api/auth/config', '/api/auth/logout', '/api/auth/request', '/api/auth/verify', '/api/contact', '/api/me', '/api/me/export', '/api/me/saved',
  ]);
});

test('/api/auth/config answers from the Worker, as JSON, even before settings exist', async () => {
  const calls = [];
  const r = await worker.fetch(new Request(`${SITE}/api/auth/config`), { ASSETS: assets(calls) });
  assert.equal(r.status, 200);
  const j = await r.json();
  assert.equal(j.configured, false);
  assert.deepEqual(calls, []);
});

test('a trailing slash still reaches the route', async () => {
  const r = await worker.fetch(new Request(`${SITE}/api/auth/config/`), { ASSETS: assets([]) });
  assert.equal(r.status, 200);
});

test('contact address answers 405 to a plain visit', async () => {
  const r = await worker.fetch(new Request(`${SITE}/api/contact`), { ASSETS: assets([]) });
  assert.equal(r.status, 405);
  assert.equal(r.headers.get('allow'), 'POST');
});

test('unknown /api/ addresses get a JSON 404', async () => {
  const calls = [];
  const r = await worker.fetch(new Request(`${SITE}/api/nope`), { ASSETS: assets(calls) });
  assert.equal(r.status, 404);
  assert.equal((await r.json()).error, 'not_found');
  assert.deepEqual(calls, []);
});

test('everything else goes to the static site', async () => {
  const calls = [];
  const r = await worker.fetch(new Request(`${SITE}/sign-in/`), { ASSETS: assets(calls) });
  assert.equal(await r.text(), '<html>page</html>');
  assert.deepEqual(calls, ['/sign-in/']);
});
