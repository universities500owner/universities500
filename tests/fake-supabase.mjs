// An in-memory stand-in for the parts of Supabase the account code uses (Auth, the email code, and the two tables
// with row level security). It is used only by tests, so the whole sign-in and profile flow runs with no network.
// It imitates the real service where the code depends on it: one-time codes that expire, refresh tokens that rotate,
// a rate limit on codes, service key versus student key, and the column grants from supabase/migrations/0001_students.sql.

export const KEYS = { anon: 'anon-key', service: 'service-key' };
export const URL_BASE = 'https://fake.supabase.test';

const b64url = (o) => Buffer.from(JSON.stringify(o)).toString('base64url');
const STUDENT_UPDATABLE = ['display_name', 'countries', 'level', 'subject_groups', 'subjects', 'stage', 'onboarded_at', 'marketing_opt_in', 'updated_at'];

export function createFakeSupabase({ clock = { t: Date.UTC(2026, 10, 20, 12, 0, 0) } } = {}) {
  const f = {
    clock,
    users: new Map(),        // id -> { id, email, user_metadata }
    students: new Map(),     // id -> row
    sections: new Map(),     // `${id}|${section}` -> row
    codes: new Map(),        // email -> { code, at }
    outbox: [],              // every sign-in email "sent": { email, code }
    tokens: new Map(),       // access token -> { sub, exp }
    refresh: new Map(),      // refresh token -> user id (valid only until used)
    calls: [],               // every request, for assertions: "METHOD path"
    nextCode: '123456',
    failNext: new Set(),     // names: 'otp', 'students-insert', 'delete'
    captchaGood: 'good-token',
  };
  let n = 0;
  const uuid = () => `00000000-0000-4000-8000-${String(++n).padStart(12, '0')}`;
  const res = (status, data) => new Response(data === undefined ? null : JSON.stringify(data), { status, headers: { 'content-type': 'application/json' } });

  const issue = (user) => {
    const exp = Math.floor(f.clock.t / 1000) + 3600;
    const access = `${b64url({ alg: 'HS256', typ: 'JWT' })}.${b64url({ sub: user.id, exp, role: 'authenticated', email: user.email })}.sig${++n}`;
    const refresh = `rt-${user.id}-${++n}`;
    f.tokens.set(access, { sub: user.id, exp });
    f.refresh.set(refresh, user.id);
    return { access_token: access, refresh_token: refresh, expires_in: 3600, token_type: 'bearer', user };
  };

  // Who is calling the database: the server (service key) or a student (a valid access token).
  const caller = (headers) => {
    // Like the real service: a student's token comes in Authorization; the keys come in apikey.
    const bearer = String(headers.get('authorization') || '').replace(/^Bearer /, '') || headers.get('apikey');
    if (bearer === KEYS.service) return { role: 'service' };
    const t = f.tokens.get(bearer);
    if (t && t.exp * 1000 > f.clock.t) return { role: 'student', id: t.sub };
    if (bearer === KEYS.anon) return { role: 'anon' };
    return { role: 'invalid' };
  };

  const pick = (row, select) => {
    if (!select || select === '*') return { ...row };
    const out = {};
    for (const c of select.split(',')) out[c] = row[c];
    return out;
  };
  const matches = (row, params) => {
    for (const [k, v] of params) {
      if (['select', 'on_conflict', 'order', 'limit'].includes(k)) continue;
      if (v.startsWith('eq.')) { if (String(row[k]) !== v.slice(3)) return false; }
      else if (v === 'is.null') { if (row[k] !== null && row[k] !== undefined) return false; }
      else return false;
    }
    return true;
  };

  f.fetch = async (url, init = {}) => {
    const u = new URL(url);
    const method = (init.method || 'GET').toUpperCase();
    const headers = new Headers(init.headers || {});
    f.calls.push(`${method} ${u.pathname}`);

    if (u.host === 'challenges.cloudflare.com') {
      const token = init.body && init.body.get ? init.body.get('response') : '';
      return res(200, { success: token === f.captchaGood });
    }
    if (u.origin !== URL_BASE) return res(500, { error: 'unexpected host ' + u.host });

    const body = init.body && typeof init.body === 'string' ? JSON.parse(init.body) : undefined;
    const apikey = headers.get('apikey');
    if (apikey !== KEYS.anon && apikey !== KEYS.service) return res(401, { message: 'No API key found' });
    const who = caller(headers);

    // ---- Auth ----
    if (u.pathname === '/auth/v1/admin/users' && method === 'POST') {
      if (who.role !== 'service') return res(403, { message: 'not_admin' });
      if ([...f.users.values()].some((x) => x.email === body.email)) return res(422, { error_code: 'email_exists', msg: 'A user with this email address has already been registered' });
      const user = { id: uuid(), email: body.email, user_metadata: body.user_metadata || {} };
      f.users.set(user.id, user);
      return res(200, user);
    }
    if (u.pathname.startsWith('/auth/v1/admin/users/') && method === 'DELETE') {
      if (who.role !== 'service') return res(403, { message: 'not_admin' });
      if (f.failNext.delete('delete')) return res(500, { msg: 'boom' });
      const id = u.pathname.split('/').pop();
      if (!f.users.delete(id)) return res(404, { msg: 'User not found' });
      f.students.delete(id); // on delete cascade
      for (const k of [...f.sections.keys()]) if (k.startsWith(id + '|')) f.sections.delete(k);
      for (const [t, v] of f.tokens) if (v.sub === id) f.tokens.delete(t);
      for (const [t, v] of f.refresh) if (v === id) f.refresh.delete(t);
      return res(200, {});
    }
    if (u.pathname === '/auth/v1/otp' && method === 'POST') {
      if (f.failNext.delete('otp')) return res(500, { msg: 'smtp down' });
      const user = [...f.users.values()].find((x) => x.email === body.email);
      if (!user) return res(422, { error_code: 'otp_disabled', msg: 'Signups not allowed for otp' });
      const prev = f.codes.get(body.email);
      if (prev && f.clock.t - prev.at < 60000) return res(429, { error_code: 'over_email_send_rate_limit', msg: 'For security purposes, you can only request this after 60 seconds.' });
      const code = f.nextCode;
      f.codes.set(body.email, { code, at: f.clock.t });
      f.outbox.push({ email: body.email, code });
      return res(200, {});
    }
    if (u.pathname === '/auth/v1/verify' && method === 'POST') {
      const c = f.codes.get(body.email);
      const user = [...f.users.values()].find((x) => x.email === body.email);
      if (!c || !user || c.code !== body.token || f.clock.t - c.at > 600000) return res(403, { error_code: 'otp_expired', msg: 'Token has expired or is invalid' });
      f.codes.delete(body.email);
      return res(200, issue(user));
    }
    if (u.pathname === '/auth/v1/token' && method === 'POST') {
      const id = f.refresh.get(body.refresh_token);
      if (!id || !f.users.has(id)) return res(400, { error_code: 'refresh_token_not_found', msg: 'Invalid Refresh Token' });
      f.refresh.delete(body.refresh_token); // rotation
      return res(200, issue(f.users.get(id)));
    }
    if (u.pathname === '/auth/v1/logout' && method === 'POST') {
      const bearer = String(headers.get('authorization') || '').replace(/^Bearer /, '');
      f.tokens.delete(bearer);
      return res(204);
    }

    // ---- Database (PostgREST) with row level security ----
    if (u.pathname.startsWith('/rest/v1/')) {
      if (who.role === 'invalid') return res(401, { code: 'PGRST301', message: 'JWT expired' });
      const table = u.pathname.slice('/rest/v1/'.length);
      const store = table === 'students' ? f.students : table === 'profile_sections' ? f.sections : null;
      if (!store) return res(404, { message: 'no such table' });
      const owner = (row) => (table === 'students' ? row.id : row.student_id);
      const visible = (row) => who.role === 'service' || (who.role === 'student' && owner(row) === who.id);
      const prefer = headers.get('prefer') || '';

      if (method === 'GET') {
        const rows = [...store.values()].filter((r) => visible(r) && matches(r, u.searchParams));
        return res(200, rows.map((r) => pick(r, u.searchParams.get('select'))));
      }
      if (method === 'POST') {
        const items = Array.isArray(body) ? body : [body];
        if (table === 'students') {
          if (who.role !== 'service') return res(403, { message: 'new row violates row-level security policy' });
          if (f.failNext.delete('students-insert')) return res(500, { message: 'boom' });
          for (const it of items) {
            if (store.has(it.id)) { if (prefer.includes('ignore-duplicates')) continue; return res(409, { code: '23505' }); }
            store.set(it.id, { display_name: null, countries: [], level: null, subject_groups: [], subjects: [], stage: null, onboarded_at: null, created_at: new Date(f.clock.t).toISOString(), ...it });
          }
          return res(201);
        }
        for (const it of items) {
          if (who.role === 'student' && it.student_id !== who.id) return res(403, { message: 'new row violates row-level security policy' });
          if (who.role !== 'student' && who.role !== 'service') return res(403, { message: 'denied' });
          if (!f.students.has(it.student_id)) return res(409, { code: '23503', message: 'foreign key' });
          const key = `${it.student_id}|${it.section}`;
          if (store.has(key) && !prefer.includes('merge-duplicates')) return res(409, { code: '23505' });
          store.set(key, { ...(store.get(key) || {}), ...it });
        }
        return res(201);
      }
      if (method === 'PATCH') {
        if (who.role === 'student' && table === 'students') {
          const bad = Object.keys(body).filter((k) => !STUDENT_UPDATABLE.includes(k));
          if (bad.length) return res(403, { code: '42501', message: `permission denied for column ${bad[0]}` });
        }
        for (const r of store.values()) if (visible(r) && matches(r, u.searchParams)) Object.assign(r, body);
        return res(204);
      }
      return res(405, {});
    }
    return res(404, { message: 'not found: ' + u.pathname });
  };

  f.env = { SUPABASE_URL: URL_BASE, SUPABASE_ANON_KEY: KEYS.anon, SUPABASE_SERVICE_KEY: KEYS.service };
  return f;
}

// Small helpers shared by the tests.
export const post = (url, body, extra = {}) =>
  new Request(url, { method: 'POST', headers: { 'content-type': 'application/json', origin: new URL(url).origin, ...extra }, body: JSON.stringify(body) });

// Turns a response's Set-Cookie lines into a Cookie header for the next request.
export function cookieJar(response, previous = {}) {
  const jar = { ...previous };
  for (const line of response.headers.getSetCookie()) {
    const [pair, ...attrs] = line.split(';').map((s) => s.trim());
    const i = pair.indexOf('=');
    const name = pair.slice(0, i), value = pair.slice(i + 1);
    if (value === '' || attrs.some((a) => /^Max-Age=0$/i.test(a))) delete jar[name];
    else jar[name] = value;
  }
  return jar;
}
export const cookieHeader = (jar) => Object.entries(jar).map(([k, v]) => `${k}=${v}`).join('; ');
