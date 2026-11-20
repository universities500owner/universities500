// "My shortlist" API, against the in-memory Supabase (tests/fake-supabase.mjs).
import test from 'node:test';
import assert from 'node:assert/strict';
import { handleRequestCode, handleVerify, handleSaved, handleExport, handleMe } from '../src/lib/account/handlers.js';
import { cleanItem, cleanChange, STATUSES } from '../src/lib/account/saved.js';
import { createFakeSupabase, post, cookieJar, cookieHeader } from './fake-supabase.mjs';

const SITE = 'https://universities500.com';
const CRS = 'crs:arizona-state-university/asus-first-three-year-bachelor-of-education-degrees-9a20f8';

async function setup() {
  const fake = createFakeSupabase();
  const env = fake.env;
  const T = () => fake.clock.t;
  const signIn = async (email) => {
    const a = await handleRequestCode(post(`${SITE}/api/auth/request`, { email, adult: true, terms: true }), env, fake.fetch, T());
    assert.equal(a.status, 200);
    fake.clock.t += 61000;
    const v = await handleVerify(post(`${SITE}/api/auth/verify`, { email, code: fake.outbox.at(-1).code }), env, fake.fetch, T());
    assert.equal(v.status, 200);
    return cookieJar(v);
  };
  const call = (jar, method, body) => {
    const headers = { cookie: cookieHeader(jar) };
    const req = method === 'GET'
      ? new Request(`${SITE}/api/me/saved`, { headers })
      : new Request(`${SITE}/api/me/saved`, { method, headers: { ...headers, origin: SITE, 'content-type': 'application/json' }, body: JSON.stringify(body) });
    return handleSaved(req, env, fake.fetch, T());
  };
  return { fake, env, signIn, call, jar: await signIn('asha.rao@gmail.com') };
}

test('validation: ids, titles, links and statuses', () => {
  assert.equal(cleanItem({ id: 'nope' }).error, 'Unknown item.');
  assert.equal(cleanItem({ id: 'crs:a b' }).error, 'Unknown item.');
  const c = cleanItem({ id: CRS, title: '  Bachelor\nof   Education ', sub: 'ASU', url: '/courses/arizona-state-university/x/' }).value;
  assert.equal(c.title, 'Bachelor of Education');
  assert.equal(c.status, 'shortlisted');
  assert.equal(c.kind, 'crs');
  assert.equal(cleanItem({ id: 'sch:abc', title: 'S', url: 'javascript:alert(1)' }).value.url, '');
  assert.equal(cleanItem({ id: 'sch:abc', title: 'S', url: '//evil.example/x' }).value.url, '');
  assert.equal(cleanItem({ id: 'int:c90688991ac0', title: 'T', url: 'https://jobs.example.com/a?b=1' }).value.url, 'https://jobs.example.com/a?b=1');
  assert.equal(cleanItem({ id: 'int:c90688991ac0', title: 'T', url: 'http://jobs.example.com/a' }).value.url, '');
  assert.equal(cleanItem({ id: 'mba:warwick-msc-management' }).value.title, 'warwick msc management', 'a missing title falls back to the id');
  assert.equal(cleanItem({ id: 'sch:abc' }).value.status, 'saved');
  assert.equal(cleanChange({ id: CRS, status: 'awarded' }).error, 'Choose one of the listed statuses.');
  assert.equal(cleanChange({ id: 'sch:abc', status: 'awarded' }).value.status, 'awarded');
  assert.equal(cleanChange({ id: CRS, note: 'x'.repeat(501) }).error, 'Keep the note under 500 characters.');
  assert.equal(cleanChange({ id: CRS }).error, 'Nothing to change.');
  for (const k of Object.keys(STATUSES)) assert.ok(STATUSES[k].length >= 5);
});

test('a signed-out visitor gets 401; wrong origin is refused', async () => {
  const { call, fake, env } = await setup();
  assert.equal((await call({}, 'GET')).status, 401);
  const r = await handleSaved(new Request(`${SITE}/api/me/saved`, { method: 'POST', headers: { origin: 'https://evil.example', 'content-type': 'application/json' }, body: '{}' }), env, fake.fetch);
  assert.equal(r.status, 403);
});

test('save, list, change status and note, remove', async () => {
  const { call, jar, fake } = await setup();
  assert.deepEqual((await (await call(jar, 'GET')).json()).items, []);
  const add = await (await call(jar, 'POST', { items: [{ id: CRS, title: 'B.Ed three-year', sub: 'Arizona State University', url: '/courses/arizona-state-university/x/' }, { id: 'sch:abc-grant', title: 'ABC Grant' }] })).json();
  assert.equal(add.ok, true);
  assert.equal(add.added, 2);
  assert.equal(add.items.length, 2);
  assert.equal(add.items.find((i) => i.item_id === CRS).status, 'shortlisted');
  assert.equal(add.items.find((i) => i.item_id === 'sch:abc-grant').status, 'saved');

  assert.equal((await call(jar, 'PATCH', { id: CRS, status: 'applied', note: 'Deadline 1 Mar.\nAsk about housing.' })).status, 200);
  const item = (await (await call(jar, 'GET')).json()).items.find((i) => i.item_id === CRS);
  assert.equal(item.status, 'applied');
  assert.equal(item.note, 'Deadline 1 Mar.\nAsk about housing.');

  assert.equal((await call(jar, 'PATCH', { id: CRS, status: 'awarded' })).status, 422);
  assert.equal((await call(jar, 'PATCH', { id: 'nope', status: 'applied' })).status, 422);

  assert.equal((await call(jar, 'DELETE', { id: 'sch:abc-grant' })).status, 200);
  assert.deepEqual((await (await call(jar, 'GET')).json()).items.map((i) => i.item_id), [CRS]);
  assert.equal((await call(jar, 'DELETE', {})).status, 422);
  assert.equal(fake.saved.size, 1);
});

test('saving the same item again keeps its status and note (a guest merge cannot overwrite progress)', async () => {
  const { call, jar } = await setup();
  await call(jar, 'POST', { items: [{ id: CRS, title: 'B.Ed' }] });
  await call(jar, 'PATCH', { id: CRS, status: 'offer', note: 'Got it' });
  const again = await (await call(jar, 'POST', { items: [{ id: CRS, title: 'B.Ed' }, { id: 'int:abc123', title: 'Intern' }] })).json();
  assert.equal(again.added, 1);
  const it = again.items.find((i) => i.item_id === CRS);
  assert.equal(it.status, 'offer');
  assert.equal(it.note, 'Got it');
});

test('bad items in a batch are skipped, the rest are saved; the cap is 200', async () => {
  const { call, jar } = await setup();
  const r = await (await call(jar, 'POST', { items: [{ id: 'bad' }, { id: 'crs:u/ok', title: 'OK' }, 'x', null] })).json();
  assert.equal(r.added, 1);
  for (let b = 0; b < 2; b++) {
    const items = Array.from({ length: 100 }, (_, i) => ({ id: `int:b${b}n${i}`, title: `Item ${b}-${i}` }));
    await call(jar, 'POST', { items });
  }
  const full = await (await call(jar, 'POST', { items: [{ id: 'int:extra1', title: 'Extra' }] })).json();
  assert.equal(full.items.length, 200);
  assert.equal(full.capped, true);
  assert.equal(full.added, 0);
});

test('students cannot see each other\'s shortlist, and deleting the account removes it', async () => {
  const { call, jar, signIn, fake, env } = await setup();
  await call(jar, 'POST', { items: [{ id: CRS, title: 'Mine' }] });
  const other = await signIn('ravi.kumar@gmail.com');
  assert.deepEqual((await (await call(other, 'GET')).json()).items, []);
  await call(other, 'POST', { items: [{ id: 'sch:theirs', title: 'Theirs' }] });
  assert.deepEqual((await (await call(jar, 'GET')).json()).items.map((i) => i.item_id), [CRS]);
  const del = await handleMe(new Request(`${SITE}/api/me`, { method: 'DELETE', headers: { cookie: cookieHeader(jar), origin: SITE, 'content-type': 'application/json' }, body: JSON.stringify({ confirm: 'delete' }) }), env, fake.fetch, fake.clock.t);
  assert.equal(del.status, 200);
  assert.deepEqual([...fake.saved.values()].map((r) => r.item_id), ['sch:theirs']);
});

test('the data export includes the shortlist', async () => {
  const { call, jar, env, fake } = await setup();
  await call(jar, 'POST', { items: [{ id: CRS, title: 'Mine' }] });
  const r = await handleExport(new Request(`${SITE}/api/me/export`, { headers: { cookie: cookieHeader(jar) } }), env, fake.fetch, fake.clock.t);
  const j = await r.json();
  assert.equal(j.shortlist.length, 1);
  assert.equal(j.shortlist[0].title, 'Mine');
});
