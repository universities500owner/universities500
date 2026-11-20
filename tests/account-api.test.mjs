// Run with: npm test   (node --test)
// The whole sign-in and profile flow against an in-memory Supabase (tests/fake-supabase.mjs).
import test from 'node:test';
import assert from 'node:assert/strict';
import { handleConfig, handleRequestCode, handleVerify, handleLogout, handleMe, handleExport } from '../src/lib/account/handlers.js';
import { createFakeSupabase, post, cookieJar, cookieHeader } from './fake-supabase.mjs';

const SITE = 'https://universities500.com';
const J = (r) => r.json();
const T = (f) => f.clock.t;

function setup(extraEnv = {}) {
  const fake = createFakeSupabase();
  const env = { ...fake.env, ...extraEnv };
  const api = {
    config: () => handleConfig(new Request(`${SITE}/api/auth/config`), env, fake.fetch),
    request: (body, extra) => handleRequestCode(post(`${SITE}/api/auth/request`, body, extra), env, fake.fetch, T(fake)),
    verify: (body, extra) => handleVerify(post(`${SITE}/api/auth/verify`, body, extra), env, fake.fetch, T(fake)),
    logout: (jar) => handleLogout(post(`${SITE}/api/auth/logout`, {}, { cookie: cookieHeader(jar) }), env, fake.fetch),
    me: (jar, method = 'GET', body, now = T(fake)) => {
      const headers = { cookie: cookieHeader(jar) };
      const req = method === 'GET'
        ? new Request(`${SITE}/api/me`, { headers })
        : new Request(`${SITE}/api/me`, { method, headers: { ...headers, origin: SITE, 'content-type': 'application/json' }, body: JSON.stringify(body) });
      return handleMe(req, env, fake.fetch, now);
    },
    export: (jar) => handleExport(new Request(`${SITE}/api/me/export`, { headers: { cookie: cookieHeader(jar) } }), env, fake.fetch, T(fake)),
  };
  // Signs a student in all the way and returns their cookies.
  api.signIn = async (email = 'asha.rao@gmail.com', extra = {}) => {
    const a = await api.request({ email, adult: true, terms: true, ...extra });
    assert.equal(a.status, 200, JSON.stringify(await a.clone().json()));
    fake.clock.t += 61000; // past Supabase's one-code-a-minute limit, so repeat sign-ins in a test work
    const code = fake.outbox.at(-1).code;
    const v = await api.verify({ email, code });
    assert.equal(v.status, 200);
    return cookieJar(v);
  };
  return { fake, env, api };
}

// ---- configuration ---------------------------------------------------------------------------------------------

test('without Supabase settings every call says sign-in is not open, and the page is told', async () => {
  const fake = createFakeSupabase();
  const empty = {};
  assert.deepEqual(await J(await handleConfig(new Request(`${SITE}/api/auth/config`), empty, fake.fetch)), { ok: true, configured: false, turnstileSiteKey: null });
  const r = await handleRequestCode(post(`${SITE}/api/auth/request`, { email: 'asha.rao@gmail.com', adult: true, terms: true }), empty, fake.fetch);
  assert.equal(r.status, 503);
  assert.equal((await J(r)).error, 'not_configured');
  assert.equal((await handleMe(new Request(`${SITE}/api/me`), empty, fake.fetch)).status, 503);
  assert.equal(fake.calls.length, 0, 'nothing was sent anywhere');
});

test('the config answer shows the Turnstile site key only when Turnstile is fully set up', async () => {
  assert.equal((await J(await setup({ TURNSTILE_SITE_KEY: 'site' }).api.config())).turnstileSiteKey, null);
  assert.equal((await J(await setup({ TURNSTILE_SECRET: 's', TURNSTILE_SITE_KEY: 'site' }).api.config())).turnstileSiteKey, 'site');
  assert.equal((await J(await setup().api.config())).configured, true);
});

// ---- asking for a code -----------------------------------------------------------------------------------------

test('asking for a code creates the account once and emails a code to the canonical Gmail address', async () => {
  const { fake, api } = setup();
  const a = await api.request({ email: 'Asha.Rao+uni@googlemail.com', adult: true, terms: true, marketing: true });
  assert.equal(a.status, 200);
  assert.deepEqual(await J(a), { ok: true, email: 'asharao@gmail.com' });
  assert.deepEqual(fake.outbox, [{ email: 'asharao@gmail.com', code: '123456' }]);
  assert.equal(fake.users.size, 1);
  const user = [...fake.users.values()][0];
  assert.equal(user.user_metadata.marketing_opt_in, true);
  assert.equal(user.user_metadata.consent_at, new Date(T(fake)).toISOString());
  assert.equal(fake.students.size, 0, 'the student record waits until the code is confirmed');

  fake.clock.t += 61000;
  const b = await api.request({ email: 'asha.rao@gmail.com', adult: true, terms: true });
  assert.equal(b.status, 200);
  assert.equal(fake.users.size, 1, 'the same mailbox is the same student');
  assert.equal(fake.outbox.length, 2);
});

test('a code request needs a Gmail address and both confirmations', async () => {
  const { fake, api } = setup();
  assert.equal((await api.request({ email: 'asha@yahoo.com', adult: true, terms: true })).status, 422);
  assert.match((await J(await api.request({ email: 'asha@yahoo.com', adult: true, terms: true }))).errors.email, /@gmail.com/);
  const noConsent = await api.request({ email: 'asha.rao@gmail.com', adult: true, terms: false });
  assert.equal(noConsent.status, 422);
  assert.ok((await J(noConsent)).errors.consent);
  assert.equal((await api.request({ email: 'asha.rao@gmail.com', terms: true })).status, 422);
  assert.equal(fake.users.size, 0);
  assert.equal(fake.outbox.length, 0);
});

test('a code request is refused from other sites and without an Origin header', async () => {
  const { fake, api } = setup();
  const body = { email: 'asha.rao@gmail.com', adult: true, terms: true };
  assert.equal((await api.request(body, { origin: 'https://evil.example' })).status, 403);
  const noOrigin = new Request(`${SITE}/api/auth/request`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
  assert.equal((await handleRequestCode(noOrigin, fake.env, fake.fetch)).status, 403);
  assert.equal((await handleRequestCode(new Request(`${SITE}/api/auth/request`), fake.env, fake.fetch)).status, 405);
  assert.equal(fake.users.size, 0);
});

test('bad bodies are refused', async () => {
  const { api, env, fake } = setup();
  const raw = (text, extra = {}) => handleRequestCode(new Request(`${SITE}/api/auth/request`, { method: 'POST', headers: { origin: SITE, ...extra }, body: text }), env, fake.fetch);
  assert.equal((await raw('not json')).status, 400);
  assert.equal((await raw('[1,2]')).status, 400);
  assert.equal((await raw('x'.repeat(70000))).status, 413);
  assert.equal((await api.request({})).status, 422);
});

test('Turnstile is enforced when it is switched on', async () => {
  const { fake, api } = setup({ TURNSTILE_SECRET: 'secret', TURNSTILE_SITE_KEY: 'site' });
  const base = { email: 'asha.rao@gmail.com', adult: true, terms: true };
  assert.equal((await api.request(base)).status, 403);
  assert.equal((await api.request({ ...base, turnstile: 'wrong' })).status, 403);
  assert.equal(fake.users.size, 0);
  assert.equal((await api.request({ ...base, turnstile: 'good-token' })).status, 200);
  assert.equal(fake.users.size, 1);
});

test('asking again too soon gives a plain rate-limit answer, and an email outage a plain failure', async () => {
  const { fake, api } = setup();
  const body = { email: 'asha.rao@gmail.com', adult: true, terms: true };
  assert.equal((await api.request(body)).status, 200);
  const again = await api.request(body);
  assert.equal(again.status, 429);
  assert.equal((await J(again)).error, 'rate_limited');
  fake.clock.t += 61000;
  fake.failNext.add('otp');
  const down = await api.request(body);
  assert.equal(down.status, 502);
  assert.match((await J(down)).message, /try again/);
});

// ---- confirming the code ---------------------------------------------------------------------------------------

test('the right code signs the student in with safe cookies and creates the record with the consent given', async () => {
  const { fake, api } = setup();
  await api.request({ email: 'asha.rao@gmail.com', adult: true, terms: true, marketing: true });
  const v = await api.verify({ email: 'Asha.Rao@gmail.com', code: '123 456' });
  assert.equal(v.status, 200);
  assert.deepEqual(await J(v), { ok: true, next: '/student/' });
  const lines = v.headers.getSetCookie();
  const line = (n) => lines.find((l) => l.startsWith(n + '='));
  assert.match(line('u500_at'), /HttpOnly/);
  assert.match(line('u500_at'), /Path=\/api;/);
  assert.match(line('u500_at'), /SameSite=Lax/);
  assert.match(line('u500_at'), /Secure/);
  assert.match(line('u500_rt'), /HttpOnly/);
  assert.match(line('u500_rt'), /Max-Age=2592000/);
  assert.doesNotMatch(line('u500_in'), /HttpOnly/);
  assert.match(line('u500_in'), /Path=\/;/);
  assert.doesNotMatch(line('u500_in'), /eyJ/, 'the flag holds no token');
  const [row] = [...fake.students.values()];
  assert.equal(row.email, 'asharao@gmail.com');
  assert.equal(row.marketing_opt_in, true);
  assert.equal(row.consent_version, 'draft-2026-11');
  assert.equal(row.consent_at, new Date(Date.UTC(2026, 10, 20, 12)).toISOString());
});

test('the cookies are not marked Secure on a local http address', async () => {
  const { fake, env, api } = setup();
  await api.request({ email: 'asha.rao@gmail.com', adult: true, terms: true });
  const req = post('http://localhost:8788/api/auth/verify', { email: 'asha.rao@gmail.com', code: '123456' });
  const v = await handleVerify(req, env, fake.fetch);
  assert.equal(v.status, 200);
  assert.ok(v.headers.getSetCookie().every((l) => !/Secure/.test(l)));
});

test('a wrong, malformed or reused code does not sign anyone in', async () => {
  const { fake, api } = setup();
  await api.request({ email: 'asha.rao@gmail.com', adult: true, terms: true });
  for (const code of ['000000', '12345', 'abcdef', '', undefined]) {
    const v = await api.verify({ email: 'asha.rao@gmail.com', code });
    assert.ok([401, 422].includes(v.status), String(code));
    assert.equal(v.headers.getSetCookie().length, 0);
  }
  assert.equal(fake.students.size, 0);
  assert.equal((await api.verify({ email: 'asha.rao@gmail.com', code: '123456' })).status, 200);
  assert.equal((await api.verify({ email: 'asha.rao@gmail.com', code: '123456' })).status, 401, 'a code works once');
});

test('a code stops working after ten minutes', async () => {
  const { fake, api } = setup();
  await api.request({ email: 'asha.rao@gmail.com', adult: true, terms: true });
  fake.clock.t += 11 * 60000;
  assert.equal((await api.verify({ email: 'asha.rao@gmail.com', code: '123456' })).status, 401);
});

test('if the student record cannot be created nobody is signed in', async () => {
  const { fake, api } = setup();
  await api.request({ email: 'asha.rao@gmail.com', adult: true, terms: true });
  fake.failNext.add('students-insert');
  const v = await api.verify({ email: 'asha.rao@gmail.com', code: '123456' });
  assert.equal(v.status, 502);
  assert.equal(v.headers.getSetCookie().length, 0);
});

test('signing in again keeps the first consent record', async () => {
  const { fake, api } = setup();
  await api.signIn('asha.rao@gmail.com', { marketing: true });
  const first = { ...[...fake.students.values()][0] };
  fake.clock.t += 86400000;
  await api.signIn('asha.rao@gmail.com', { marketing: false });
  assert.equal(fake.students.size, 1);
  const row = [...fake.students.values()][0];
  assert.equal(row.consent_at, first.consent_at);
  assert.equal(row.marketing_opt_in, true);
});

// ---- the signed-in student -------------------------------------------------------------------------------------

test('reading the account needs a session', async () => {
  const { api } = setup();
  const r = await api.me({});
  assert.equal(r.status, 401);
  assert.equal((await J(r)).error, 'signed_out');
  assert.ok(r.headers.getSetCookie().some((l) => l.startsWith('u500_in=;')), 'the dashboard flag is cleared');
  const forged = await api.me({ u500_at: 'aaa.bbb.ccc' });
  assert.equal(forged.status, 401);
  const badSub = `x.${Buffer.from(JSON.stringify({ sub: "1' or 1=1", exp: 9999999999 })).toString('base64url')}.y`;
  assert.equal((await api.me({ u500_at: badSub })).status, 401);
});

test('a new student gets an empty account back', async () => {
  const { api } = setup();
  const jar = await api.signIn();
  const r = await api.me(jar);
  assert.equal(r.status, 200);
  const j = await J(r);
  assert.equal(j.student.email, 'asharao@gmail.com');
  assert.equal(j.student.stage, null);
  assert.equal(j.student.onboarded_at, null);
  assert.deepEqual(Object.keys(j.sections), ['profile', 'academic', 'english', 'work', 'immigration']);
  assert.ok(!('consent_at' in j.student));
});

test('saving plans and sections, then reading them back', async () => {
  const { api } = setup();
  const jar = await api.signIn();
  const saved = await api.me(jar, 'PATCH', {
    student: { countries: ['australia', 'canada'], level: 'masters', subject_groups: ['computing'], stage: 'exploring', display_name: 'Asha' },
    onboarded: true,
    sections: {
      profile: { full_name: 'Asha Rao', birth_year: 2001, nationality: 'Indian' },
      english: { test: 'ielts', status: 'taken', overall: 7, listening: 7.5, reading: 7, writing: 6.5, speaking: 7 },
    },
  });
  assert.equal(saved.status, 200);
  const j = await J(saved);
  assert.equal(j.sections.profile.full_name, 'Asha Rao');
  const back = await J(await api.me(jar));
  assert.deepEqual(back.student.countries, ['australia', 'canada']);
  assert.equal(back.student.stage, 'exploring');
  assert.ok(back.student.onboarded_at);
  assert.equal(back.sections.english.overall, 7);
  assert.equal(back.sections.profile.nationality, 'Indian');
  assert.ok(back.updated.profile);
  // Saving one section does not disturb another.
  await api.me(jar, 'PATCH', { sections: { work: { none: true } } });
  const after = await J(await api.me(jar));
  assert.equal(after.sections.english.overall, 7);
  assert.equal(after.sections.work.none, true);
});

test('invalid data is rejected with field messages and nothing is saved', async () => {
  const { fake, api } = setup();
  const jar = await api.signIn();
  const r = await api.me(jar, 'PATCH', {
    student: { stage: 'nope' },
    sections: { academic: { items: [{ level: 'bachelors', institution: 'X', status: 'completed', grade_type: 'gpa4', grade: 9 }] }, profile: { full_name: 'Fine', birth_year: 2001, nationality: 'Indian' }, passport: { number: '1' } },
  });
  assert.equal(r.status, 422);
  const j = await J(r);
  assert.ok(j.errors.student.stage);
  assert.match(j.errors.sections.academic['items.0.grade'], /more than 4/);
  assert.ok(j.errors.sections.passport);
  assert.equal(fake.sections.size, 0, 'the valid profile was not saved either');
  assert.equal([...fake.students.values()][0].stage, null);
});

test('email, consent and id cannot be changed through the API', async () => {
  const { fake, api } = setup();
  const jar = await api.signIn();
  const before = { ...[...fake.students.values()][0] };
  const r = await api.me(jar, 'PATCH', { student: { email: 'someone.else@gmail.com', consent_at: '2000-01-01T00:00:00Z', id: 'x', stage: 'visa' } });
  assert.equal(r.status, 200);
  const row = [...fake.students.values()][0];
  assert.equal(row.email, before.email);
  assert.equal(row.consent_at, before.consent_at);
  assert.equal(row.id, before.id);
  assert.equal(row.stage, 'visa');
});

test('onboarded_at is set once and keeps its first value', async () => {
  const { fake, api } = setup();
  const jar = await api.signIn();
  await api.me(jar, 'PATCH', { onboarded: true });
  const first = [...fake.students.values()][0].onboarded_at;
  assert.ok(first);
  fake.clock.t += 3600000;
  await api.me(jar, 'PATCH', { onboarded: true, student: { stage: 'offer' } });
  assert.equal([...fake.students.values()][0].onboarded_at, first);
});

test('a student only ever sees their own details', async () => {
  const { fake, api } = setup();
  const a = await api.signIn('asha.rao@gmail.com');
  await api.me(a, 'PATCH', { sections: { profile: { full_name: 'Asha Rao', birth_year: 2001, nationality: 'Indian' } } });
  const b = await api.signIn('ravi.kumar@gmail.com');
  await api.me(b, 'PATCH', { sections: { profile: { full_name: 'Ravi Kumar', birth_year: 2000, nationality: 'Indian' } } });
  assert.equal((await J(await api.me(a))).sections.profile.full_name, 'Asha Rao');
  assert.equal((await J(await api.me(b))).sections.profile.full_name, 'Ravi Kumar');
  const exportA = await api.export(a);
  const text = await exportA.text();
  assert.ok(!text.includes('Ravi') && !text.includes('ravikumar'));
  assert.equal(fake.students.size, 2);
});

test('an expired access token is renewed quietly and the new cookies are sent', async () => {
  const { fake, api } = setup();
  const jar = await api.signIn();
  fake.clock.t += 2 * 3600000;
  const r = await api.me(jar, 'GET', undefined, T(fake));
  assert.equal(r.status, 200);
  const next = cookieJar(r, jar);
  assert.notEqual(next.u500_at, jar.u500_at);
  assert.notEqual(next.u500_rt, jar.u500_rt);
  assert.equal((await api.me(next)).status, 200);
  // The old refresh token has been used up.
  assert.equal((await api.me({ ...jar, u500_at: undefined })).status, 401);
});

test('an expired access token with no usable refresh token signs the student out', async () => {
  const { fake, api } = setup();
  const jar = await api.signIn();
  fake.clock.t += 2 * 3600000;
  const r = await api.me({ u500_at: jar.u500_at });
  assert.equal(r.status, 401);
  assert.ok(r.headers.getSetCookie().some((l) => l.startsWith('u500_at=;')));
});

test('PATCH and DELETE are refused from other sites', async () => {
  const { api, env, fake } = setup();
  const jar = await api.signIn();
  for (const method of ['PATCH', 'DELETE']) {
    const req = new Request(`${SITE}/api/me`, { method, headers: { cookie: cookieHeader(jar), origin: 'https://evil.example', 'content-type': 'application/json' }, body: '{"confirm":"delete"}' });
    assert.equal((await handleMe(req, env, fake.fetch, T(fake))).status, 403, method);
  }
  assert.equal(fake.users.size, 1);
});

// ---- export, sign out, delete ----------------------------------------------------------------------------------

test('the export is a downloadable file of everything stored', async () => {
  const { api } = setup();
  const jar = await api.signIn();
  await api.me(jar, 'PATCH', { student: { stage: 'visa' }, sections: { immigration: { history: 'none' } } });
  const r = await api.export(jar);
  assert.equal(r.status, 200);
  assert.match(r.headers.get('content-disposition'), /attachment; filename="universities500-my-data.json"/);
  const j = await J(r);
  assert.equal(j.student.stage, 'visa');
  assert.equal(j.student.email, 'asharao@gmail.com');
  assert.equal(j.sections.immigration.history, 'none');
  assert.equal((await api.export({})).status, 401);
});

test('signing out clears the cookies', async () => {
  const { api } = setup();
  const jar = await api.signIn();
  const r = await api.logout(jar);
  assert.equal(r.status, 200);
  const after = cookieJar(r, jar);
  assert.deepEqual(Object.keys(after), []);
});

test('deleting the account needs a confirmation and removes everything', async () => {
  const { fake, api } = setup();
  const jar = await api.signIn();
  await api.me(jar, 'PATCH', { sections: { work: { none: true } } });
  assert.equal((await api.me(jar, 'DELETE', {})).status, 422);
  assert.equal(fake.users.size, 1);
  const r = await api.me(jar, 'DELETE', { confirm: 'delete' });
  assert.equal(r.status, 200);
  assert.equal(fake.users.size + fake.students.size + fake.sections.size, 0);
  assert.deepEqual(Object.keys(cookieJar(r, jar)), []);
  assert.equal((await api.me(jar)).status, 401, 'the old session no longer works');
  // Signing in again starts a fresh account.
  const again = await api.signIn();
  assert.deepEqual((await J(await api.me(again))).sections.work, {});
});

test('a failed deletion says so and keeps the account', async () => {
  const { fake, api } = setup();
  const jar = await api.signIn();
  fake.failNext.add('delete');
  const r = await api.me(jar, 'DELETE', { confirm: 'delete' });
  assert.equal(r.status, 502);
  assert.equal(fake.users.size, 1);
});

test('no response ever contains the Supabase keys or a token in its body', async () => {
  const { fake, api } = setup();
  const jar = await api.signIn();
  const bodies = [await (await api.me(jar)).text(), await (await api.export(jar)).text(), await (await api.config()).text()];
  for (const b of bodies) assert.ok(!/service-key|anon-key|eyJ|rt-/.test(b));
  assert.ok(fake.calls.length > 0);
});

test('new-style keys go in the apikey header only, old JWT keys also as the bearer', async () => {
  const { supabase } = await import('../src/lib/account/supabase.js');
  const seen = [];
  const spy = async (url, init) => { seen.push(new Headers(init.headers)); return new Response('{}', { status: 200 }); };
  const modern = supabase({ SUPABASE_URL: 'https://x.supabase.co', SUPABASE_ANON_KEY: 'sb_publishable_abc', SUPABASE_SERVICE_KEY: 'sb_secret_def' }, spy);
  await modern.createUser('a@gmail.com', {});
  await modern.sendCode('a@gmail.com');
  await modern.db('students?id=eq.1', { jwt: 'user.jwt.token' });
  assert.equal(seen[0].get('apikey'), 'sb_secret_def');
  assert.equal(seen[0].get('authorization'), null);
  assert.equal(seen[1].get('apikey'), 'sb_publishable_abc');
  assert.equal(seen[1].get('authorization'), null);
  assert.equal(seen[2].get('apikey'), 'sb_publishable_abc');
  assert.equal(seen[2].get('authorization'), 'Bearer user.jwt.token');
  seen.length = 0;
  const legacy = supabase({ SUPABASE_URL: 'https://x.supabase.co', SUPABASE_ANON_KEY: 'eyJanon', SUPABASE_SERVICE_KEY: 'eyJservice' }, spy);
  await legacy.createUser('a@gmail.com', {});
  assert.equal(seen[0].get('authorization'), 'Bearer eyJservice');
});

test('an unexpected failure becomes a readable JSON answer, not an error page', async () => {
  const fake = createFakeSupabase();
  const broken = { ...fake.env, get SUPABASE_URL() { throw new Error('boom'); } };
  const r = await handleRequestCode(post(`${SITE}/api/auth/request`, { email: 'asha.rao@gmail.com', adult: true, terms: true }), broken, fake.fetch);
  assert.equal(r.status, 500);
  const j = await J(r);
  assert.equal(j.error, 'server_error');
  assert.match(j.message, /something went wrong/);
});
