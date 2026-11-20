// The owner's student list: who may open it, what it returns and hides, filters, paging, the CSV and its formula guard.
import test from 'node:test';
import assert from 'node:assert/strict';
import { handleRequestCode, handleVerify } from '../src/lib/account/handlers.js';
import { handleAdminList, handleAdminStudent, handleAdminExport, adminEmails, parseFilters, csvCell, toCsv } from '../src/lib/account/admin.js';
import { createFakeSupabase, post, cookieJar, cookieHeader } from './fake-supabase.mjs';

const SITE = 'https://universities500.com';
const OWNER = 'pss.rajaram@gmail.com'; // Gmail ignores the dots, so this is pssrajaram@gmail.com
const DAY = 86400000;

function setup(extraEnv = {}) {
  const fake = createFakeSupabase();
  const env = { ...fake.env, ADMIN_EMAILS: ` ${OWNER} , not-an-address, other.admin@gmail.com`, ...extraEnv };
  const T = () => fake.clock.t;
  // Like a browser: keeps the cookies a response sets, so a session that was refreshed keeps working.
  const keep = async (jar, p) => { const r = await p; if (jar) { const n = cookieJar(r.clone(), jar); for (const k of Object.keys(jar)) delete jar[k]; Object.assign(jar, n); } return r; };
  const api = {
    signIn: async (email) => {
      const a = await handleRequestCode(post(`${SITE}/api/auth/request`, { email, adult: true, terms: true }), env, fake.fetch, T());
      assert.equal(a.status, 200);
      fake.clock.t += 61000;
      const v = await handleVerify(post(`${SITE}/api/auth/verify`, { email, code: fake.outbox.at(-1).code }), env, fake.fetch, T());
      assert.equal(v.status, 200);
      return cookieJar(v);
    },
    list: (jar, qs = '') => keep(jar, handleAdminList(new Request(`${SITE}/api/admin/students${qs}`, { headers: { cookie: jar ? cookieHeader(jar) : '' } }), env, fake.fetch, T())),
    one: (jar, id) => keep(jar, handleAdminStudent(new Request(`${SITE}/api/admin/student?id=${id}`, { headers: { cookie: cookieHeader(jar) } }), env, fake.fetch, T())),
    csv: (jar, qs = '') => keep(jar, handleAdminExport(new Request(`${SITE}/api/admin/export${qs}`, { headers: { cookie: cookieHeader(jar) } }), env, fake.fetch, T())),
  };
  return { fake, env, api };
}

// Signs up a few students with different details, then returns the owner's session.
async function world() {
  const w = setup();
  const ids = {};
  for (const [name, email, patch] of [
    ['owner', OWNER, { display_name: 'Raja', marketing_opt_in: true }],
    ['asha', 'asha.rao@gmail.com', { display_name: 'Asha Rao', countries: ['australia', 'canada'], level: 'masters', stage: 'applying', marketing_opt_in: true, onboarded_at: '2026-11-01T00:00:00.000Z' }],
    ['ravi', 'ravi.kumar@gmail.com', { countries: ['uk'], level: 'bachelors', stage: 'exploring' }],
    ['evil', 'evil.person@gmail.com', { display_name: '=HYPERLINK("http://x","click")' }],
  ]) {
    const jar = await w.api.signIn(email);
    const st = [...w.fake.students.values()].find((s) => s.email.startsWith(email.replace(/\./g, '').split('@')[0]));
    Object.assign(st, patch);
    ids[name] = { id: st.id, jar, student: st };
  }
  // They signed up three days, two days, one day and one hour ago.
  const now = w.fake.clock.t;
  [3 * DAY, 2 * DAY, DAY, 3600000].forEach((ago, i) => { Object.values(ids)[i].student.created_at = new Date(now - ago).toISOString(); });
  return { ...w, ids, owner: ids.owner.jar };
}
const J = (r) => r.json();

test('adminEmails reads the setting, ignores junk, and treats Gmail dots and plus tags as the same address', () => {
  assert.deepEqual(adminEmails({ ADMIN_EMAILS: ' Pss.Rajaram+x@googlemail.com, nope, a@yahoo.com ;  other.admin@gmail.com ' }), ['pssrajaram@gmail.com', 'otheradmin@gmail.com']);
  assert.deepEqual(adminEmails({}), []);
  assert.deepEqual(adminEmails({ ADMIN_EMAILS: '' }), []);
});

test('signed out gets 401; a student who is not on the list gets 404; with no list set nobody gets in', async () => {
  const { api, ids, env, fake } = await world();
  assert.equal((await api.list(null)).status, 401);
  for (const call of [api.list, (j) => api.one(j, ids.asha.id), api.csv]) {
    const r = await call(ids.asha.jar);
    assert.equal(r.status, 404);
    assert.equal((await r.json()).error, 'not_found');
  }
  assert.equal(fake.adminReads.length, 0, 'the views were never read for someone who is not an admin');
  const off = { ...env, ADMIN_EMAILS: '' };
  const r = await handleAdminList(new Request(`${SITE}/api/admin/students`, { headers: { cookie: cookieHeader(ids.owner.jar) } }), off, fake.fetch, fake.clock.t);
  assert.equal(r.status, 404);
});

test('a forged cookie cannot make someone an admin', async () => {
  const { api, fake } = await world();
  const forged = { u500_at: `x.${Buffer.from(JSON.stringify({ sub: '00000000-0000-4000-8000-000000000001', exp: 9999999999, email: OWNER })).toString('base64url')}.y` };
  const r = await api.list(forged);
  assert.ok([401, 404].includes(r.status));
  assert.equal(fake.adminReads.length, 0);
});

test('the owner sees every student, newest first, with totals', async () => {
  const { api, owner } = await world();
  const r = await api.list(owner);
  assert.equal(r.status, 200);
  const j = await J(r);
  assert.equal(j.total, 4);
  assert.deepEqual(j.rows.map((x) => x.email.split('@')[0]), ['evilperson', 'ravikumar', 'asharao', 'pssrajaram']);
  assert.equal(j.stats.total, 4);
  assert.equal(j.stats.marketing, 2);
  assert.equal(j.stats.onboarded, 1);
  assert.equal(r.headers.get('cache-control'), 'no-store');
  // a row carries what the list needs and nothing more
  assert.deepEqual(Object.keys(j.rows[0]).sort(), ['countries', 'created_at', 'display_name', 'email', 'full_name', 'id', 'level', 'marketing_opt_in', 'onboarded_at', 'sections', 'shortlist_count', 'stage', 'updated_at']);
});

test('the other address in the list is an admin too, and the owner may use dots or not', async () => {
  const { api, fake } = await world();
  const jar = await api.signIn('other.admin@gmail.com');
  assert.equal((await api.list(jar)).status, 200);
  assert.ok(fake.adminReads.length > 0);
});

test('search, filters and sorting', async () => {
  const { api, owner, fake } = await world();
  const emails = async (qs) => (await J(await api.list(owner, qs))).rows.map((x) => x.email.split('@')[0]);
  assert.deepEqual(await emails('?q=asha'), ['asharao']);
  assert.deepEqual(await emails('?q=ASHA%20rao'), ['asharao'], 'search by name, any case');
  assert.deepEqual(await emails('?q=ravi'), ['ravikumar']);
  assert.deepEqual(await emails('?marketing=1'), ['asharao', 'pssrajaram']);
  assert.deepEqual(await emails('?onboarded=1'), ['asharao']);
  assert.deepEqual((await emails('?onboarded=0')).sort(), ['evilperson', 'pssrajaram', 'ravikumar']);
  assert.deepEqual(await emails('?country=canada'), ['asharao']);
  assert.deepEqual(await emails('?country=uk'), ['ravikumar']);
  assert.deepEqual(await emails('?joined=7'), ['evilperson', 'ravikumar', 'asharao', 'pssrajaram']);
  assert.deepEqual(await emails('?sort=email&dir=asc'), ['asharao', 'evilperson', 'pssrajaram', 'ravikumar']);
  assert.deepEqual(await emails('?sort=created_at&dir=asc'), ['pssrajaram', 'asharao', 'ravikumar', 'evilperson']);
  // old sign-ups drop out of "joined in 7 days"
  fake.clock.t += 10 * DAY;
  assert.deepEqual(await emails('?joined=7'), []);
  assert.equal((await J(await api.list(owner, '?joined=7'))).total, 0);
  assert.equal((await J(await api.list(owner, '?joined=30'))).total, 4);
});

test('shortlist and visa-check filters, and the counts that go with them', async () => {
  const { api, owner, fake, ids } = await world();
  const now = new Date(fake.clock.t).toISOString();
  fake.saved.set(`${ids.asha.id}|crs:a/b`, { student_id: ids.asha.id, item_id: 'crs:a/b', kind: 'crs', title: 'MSc', status: 'shortlisted', note: 'my private note', sub: '', url: '/courses/a/b/', saved_at: now, updated_at: now });
  fake.saved.set(`${ids.asha.id}|sch:z`, { student_id: ids.asha.id, item_id: 'sch:z', kind: 'sch', title: 'Award', status: 'saved', note: '', sub: '', url: '', saved_at: now, updated_at: now });
  fake.sections.set(`${ids.asha.id}|visa_au`, { student_id: ids.asha.id, section: 'visa_au', data: { funds: 123456 }, updated_at: now });
  const j = await J(await api.list(owner, '?has=shortlist'));
  assert.deepEqual(j.rows.map((r) => [r.email.split('@')[0], r.shortlist_count]), [['asharao', 2]]);
  assert.equal(j.stats.with_shortlist, 1);
  assert.equal((await J(await api.list(owner, '?has=visa'))).total, 1);
  assert.equal((await J(await api.list(owner))).stats.with_visa_check, 1);
});

test('paging: pages of the size asked for, with the right total, and sizes are clamped', async () => {
  const { api, owner } = await world();
  const p1 = await J(await api.list(owner, '?size=10&page=1'));
  assert.equal(p1.size, 10); assert.equal(p1.total, 4); assert.equal(p1.rows.length, 4);
  assert.equal((await J(await api.list(owner, '?size=10&page=2'))).rows.length, 0);
  assert.equal((await J(await api.list(owner, '?size=1'))).size, 10, 'a size under 10 becomes 10');
  assert.equal((await J(await api.list(owner, '?size=9999'))).size, 100);
  assert.equal((await J(await api.list(owner, '?page=-4&size=abc'))).page, 1);
});

test('search text is stripped of anything that could change the query', async () => {
  const { api, owner, fake } = await world();
  const bad = '?q=' + encodeURIComponent('x*),email.neq.0,(%_\\"');
  const r = await api.list(owner, bad);
  assert.equal(r.status, 200);
  const q = fake.adminReads.at(-2).query; // the list read (the other read is the totals)
  assert.ok(!/[%\\"]/.test(decodeURIComponent(q.split('or=')[1] || '')), q);
  assert.equal(parseFilters(new URLSearchParams({ q: '  a,b(c)*d%e_f  ' }), 0).q, 'abcdef');
  assert.equal(parseFilters(new URLSearchParams({ q: 'jo.smith@gmail.com' }), 0).q, 'jo.smith@gmail.com');
  assert.equal(parseFilters(new URLSearchParams({ q: 'x'.repeat(200) }), 0).q.length, 60);
  // anything not on the list of sorts and filters is ignored
  const p = parseFilters(new URLSearchParams({ sort: 'password', country: 'a;drop', has: 'x', joined: '5', onboarded: 'maybe' }), 0);
  assert.equal(p.sort, 'created_at'); assert.equal(p.filters, '');
});

test('opening one student: details, with immigration and visa answers kept private and notes left out', async () => {
  const { api, owner, fake, ids } = await world();
  const now = new Date(fake.clock.t).toISOString();
  fake.sections.set(`${ids.asha.id}|profile`, { student_id: ids.asha.id, section: 'profile', data: { full_name: 'Asha Rao' }, updated_at: now });
  fake.sections.set(`${ids.asha.id}|immigration`, { student_id: ids.asha.id, section: 'immigration', data: { history: 'some', items: [{ country: 'Canada', year: 2024, kind: 'study', outcome: 'refused' }] }, updated_at: now });
  fake.sections.set(`${ids.asha.id}|visa_au`, { student_id: ids.asha.id, section: 'visa_au', data: { funds: 999 }, updated_at: now });
  fake.saved.set(`${ids.asha.id}|crs:a/b`, { student_id: ids.asha.id, item_id: 'crs:a/b', kind: 'crs', title: 'MSc', status: 'shortlisted', note: 'my private note', sub: 'Uni', url: '/courses/a/b/', saved_at: now, updated_at: now });
  const r = await api.one(owner, ids.asha.id);
  assert.equal(r.status, 200);
  const text = JSON.stringify(await J(r));
  const j = JSON.parse(text);
  assert.equal(j.student.email, 'asharao@gmail.com');
  assert.equal(j.sections.profile.data.full_name, 'Asha Rao');
  assert.deepEqual(j.sections.immigration, { hidden: true, updated_at: now });
  assert.deepEqual(j.sections.visa_au, { hidden: true, updated_at: now });
  assert.ok(!/refused|Canada|999|my private note/.test(text), 'private answers and notes are not sent');
  assert.equal(j.shortlist.length, 1);
  assert.equal(j.shortlist[0].title, 'MSc');
  assert.equal((await api.one(owner, 'not-a-uuid')).status, 400);
  assert.equal((await api.one(owner, '00000000-0000-4000-8000-0000000000ff')).status, 404);
  assert.equal((await api.one(ids.asha.jar, ids.asha.id)).status, 404, 'a student cannot open even their own record here');
});

test('opening a student and exporting are written to the log, without the data', async () => {
  const { api, owner, ids } = await world();
  const lines = [];
  const orig = console.info; console.info = (...a) => lines.push(a.join(' '));
  try { await api.one(owner, ids.asha.id); await api.csv(owner); } finally { console.info = orig; }
  assert.equal(lines.length, 2);
  assert.match(lines[0], /admin: opened a student/);
  assert.match(lines[1], /admin: exported students .* 4$/);
  assert.ok(!lines.join('').includes('asharao'));
});

test('the CSV: every match, the filters respected, formula text defused, and a clear file name', async () => {
  const { api, owner, fake } = await world();
  const r = await api.csv(owner);
  assert.equal(r.status, 200);
  assert.match(r.headers.get('content-type'), /^text\/csv/);
  assert.match(r.headers.get('content-disposition'), /^attachment; filename="universities500-students-\d{4}-\d{2}-\d{2}\.csv"$/);
  assert.equal(r.headers.get('cache-control'), 'no-store');
  const text = await r.text();
  const lines = text.replace(/^﻿/, '').trim().split('\r\n');
  assert.equal(lines.length, 5, 'header and four students');
  assert.match(lines[0], /^"Signed up","Email","Name"/);
  assert.ok(lines.some((l) => l.includes('"\'=HYPERLINK(""http://x"",""click"")"')), 'a name that starts with = is defused and quoted');
  assert.ok(!/(^|,)"=/m.test(text), 'no cell starts with =');
  assert.ok(lines.find((l) => l.includes('asharao@gmail.com')).includes('"Australia; Canada"') || lines.find((l) => l.includes('asharao@gmail.com')).includes('"australia; canada"'));
  // filters carry over to the export
  const only = (await (await api.csv(owner, '?marketing=1')).text()).trim().split('\r\n');
  assert.equal(only.length, 3);
  assert.equal(fake.adminReads.length > 0, true);
});

test('csvCell quotes everything and defuses = + - @ and control characters', () => {
  assert.equal(csvCell('plain'), '"plain"');
  assert.equal(csvCell('say "hi"'), '"say ""hi"""');
  assert.equal(csvCell('a,b\nc'), '"a,b\nc"');
  for (const bad of ['=1+1', '+1', '-1', '@x', '\tx', '\rx']) assert.ok(csvCell(bad).startsWith('"\''), bad);
  assert.equal(csvCell(0), '"0"');
  assert.equal(csvCell(null), '""');
  assert.match(toCsv([]), /^﻿"Signed up"/);
});

test('if the views are missing or the database fails, the owner is told what to check, not shown a blank page', async () => {
  const { api, owner, fake } = await world();
  fake.failNext.add('admin-view');
  const r = await api.list(owner);
  assert.equal(r.status, 502);
  assert.match((await J(r)).message, /0004_admin_views\.sql/);
});
