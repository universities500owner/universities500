// The student account API. Each handler takes a Request and returns a Response, and gets fetch and the clock
// passed in, so the tests can run them against a fake Supabase (tests/fake-supabase.mjs) with no network.
//
// Cloudflare Pages settings (Settings > Variables and Secrets). Until the first three are set every handler
// answers "not_configured" and the sign-in page says sign-in is not open yet; nothing else on the site is affected.
//   SUPABASE_URL           Secret or plain text. Project URL, like https://abcdwxyz.supabase.co
//   SUPABASE_ANON_KEY      Secret. The "anon public" key
//   SUPABASE_SERVICE_KEY   Secret. The "service_role" key. Never put this anywhere else.
//   TURNSTILE_SECRET       Secret, optional. When set, the sign-in form must pass Cloudflare Turnstile.
//   TURNSTILE_SITE_KEY     Plain text, optional. The matching public site key.
//
// Privacy by design: the only identifier is a Gmail address. No passwords, phone numbers, passport numbers or
// documents are collected. A student can download everything stored and delete the account at any time.

import { normaliseGmail } from './gmail.js';
import { supabase } from './supabase.js';
import { parseCookies, sessionCookies, clearCookies, jwtClaims, UUID } from './session.js';
import { CONSENT_VERSION, SECTION_IDS, cleanSection, cleanStudent } from './schema.js';

const MAX_BODY = 64 * 1024;
const STUDENT_COLUMNS = 'email,display_name,countries,level,subject_groups,subjects,stage,onboarded_at,marketing_opt_in,created_at';

// ---- plumbing -------------------------------------------------------------------------------------------------

function reply(status, body, { cookies = [], headers = {} } = {}) {
  const h = new Headers({ 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store', ...headers });
  for (const c of cookies) h.append('set-cookie', c);
  return new Response(JSON.stringify(body), { status, headers: h });
}

const isSecure = (request) => new URL(request.url).protocol === 'https:';

// State-changing calls must come from the site's own pages. The browser always sends Origin on these.
function sameOrigin(request) {
  const origin = request.headers.get('origin');
  if (!origin) return false;
  try { return new URL(origin).host === new URL(request.url).host; } catch { return false; }
}

async function readJson(request) {
  if (Number(request.headers.get('content-length') || 0) > MAX_BODY) return { error: 'too_large' };
  let text;
  try { text = await request.text(); } catch { return { error: 'bad_request' }; }
  if (text.length > MAX_BODY) return { error: 'too_large' };
  try {
    const v = JSON.parse(text);
    return v && typeof v === 'object' && !Array.isArray(v) ? { value: v } : { error: 'bad_request' };
  } catch { return { error: 'bad_request' }; }
}

const guard = (request, methods) => {
  if (!methods.includes(request.method)) return reply(405, { ok: false, error: 'method_not_allowed' }, { headers: { allow: methods.join(', ') } });
  if (request.method !== 'GET' && !sameOrigin(request)) return reply(403, { ok: false, error: 'forbidden', message: 'This request could not be completed from here.' });
  return null;
};

const notConfigured = () => reply(503, { ok: false, error: 'not_configured', message: 'Sign-in is not open yet. Please check back soon.' });

async function bodyOr(request) {
  const b = await readJson(request);
  return b.error ? { res: reply(b.error === 'too_large' ? 413 : 400, { ok: false, error: b.error, message: 'That request could not be read.' }) } : { body: b.value };
}

async function turnstileOk(env, token, ip, fetchImpl) {
  if (!env.TURNSTILE_SECRET) return true;
  if (!token || typeof token !== 'string') return false;
  try {
    const form = new FormData();
    form.append('secret', env.TURNSTILE_SECRET);
    form.append('response', token);
    if (ip) form.append('remoteip', ip);
    const r = await fetchImpl('https://challenges.cloudflare.com/turnstile/v0/siteverify', { method: 'POST', body: form });
    const j = await r.json();
    return !!j.success;
  } catch { return false; }
}

// ---- sign-in --------------------------------------------------------------------------------------------------

// What the sign-in page needs to know before it draws itself.
export async function handleConfig(request, env = {}, fetchImpl = fetch) {
  const bad = guard(request, ['GET']);
  if (bad) return bad;
  return reply(200, { ok: true, configured: supabase(env, fetchImpl).configured, turnstileSiteKey: env.TURNSTILE_SECRET && env.TURNSTILE_SITE_KEY ? env.TURNSTILE_SITE_KEY : null });
}

// Step 1. A Gmail address, the two consents and (when switched on) the Turnstile check. Creates the account the
// first time, then asks Supabase to email a 6-digit code. The answer is the same for new and returning students.
export async function handleRequestCode(request, env = {}, fetchImpl = fetch, now = Date.now()) {
  const bad = guard(request, ['POST']);
  if (bad) return bad;
  const sb = supabase(env, fetchImpl);
  if (!sb.configured) return notConfigured();
  const { res, body } = await bodyOr(request);
  if (res) return res;

  const gm = normaliseGmail(body.email);
  if (!gm.ok) return reply(422, { ok: false, error: 'invalid', errors: { email: gm.message } });
  if (body.adult !== true || body.terms !== true) {
    return reply(422, { ok: false, error: 'invalid', errors: { consent: 'Please confirm you are 18 or older and accept the Terms and Privacy page.' } });
  }
  if (!(await turnstileOk(env, body.turnstile, request.headers.get('cf-connecting-ip'), fetchImpl))) {
    return reply(403, { ok: false, error: 'captcha', message: 'We could not confirm you are not a robot. Please try again.' });
  }

  // The consent is kept with the account and written to the student record when the first code is confirmed.
  const made = await sb.createUser(gm.email, { consent_at: new Date(now).toISOString(), consent_version: CONSENT_VERSION, marketing_opt_in: body.marketing === true });
  const exists = made.status === 422 || (made.status === 400 && /already|registered|exists/i.test(JSON.stringify(made.data || '')));
  if (!made.ok && !exists) {
    console.error('account: could not create the user', made.status);
    return reply(502, { ok: false, error: 'unavailable', message: 'Sorry, we could not start sign-in. Please try again in a few minutes.' });
  }

  const sent = await sb.sendCode(gm.email);
  if (sent.status === 429) return reply(429, { ok: false, error: 'rate_limited', message: 'A code was sent a moment ago. Wait a minute, then ask for a new one.' });
  if (!sent.ok) {
    console.error('account: could not send the code', sent.status);
    return reply(502, { ok: false, error: 'unavailable', message: 'Sorry, we could not send the code. Please try again in a few minutes.' });
  }
  return reply(200, { ok: true, email: gm.email });
}

// Step 2. The 6-digit code. On success the session cookies are set and the student record exists.
export async function handleVerify(request, env = {}, fetchImpl = fetch, now = Date.now()) {
  const bad = guard(request, ['POST']);
  if (bad) return bad;
  const sb = supabase(env, fetchImpl);
  if (!sb.configured) return notConfigured();
  const { res, body } = await bodyOr(request);
  if (res) return res;

  const gm = normaliseGmail(body.email);
  const code = String(body.code ?? '').replace(/\s+/g, '');
  if (!gm.ok) return reply(422, { ok: false, error: 'invalid', errors: { email: gm.message } });
  if (!/^\d{6}$/.test(code)) return reply(422, { ok: false, error: 'invalid', errors: { code: 'Enter the 6-digit code from the email.' } });

  const v = await sb.verifyCode(gm.email, code);
  if (v.status === 429) return reply(429, { ok: false, error: 'rate_limited', message: 'Too many tries. Wait a few minutes, then try again.' });
  if (!v.ok || !v.data?.access_token || !v.data?.user?.id) {
    if (v.status >= 500 || v.status === 0) return reply(502, { ok: false, error: 'unavailable', message: 'Sorry, we could not check the code. Please try again in a few minutes.' });
    return reply(401, { ok: false, error: 'bad_code', errors: { code: 'That code is wrong or has expired. Check it, or ask for a new one.' } });
  }

  const user = v.data.user;
  const meta = user.user_metadata || {};
  const row = await sb.db('students', {
    method: 'POST',
    prefer: 'resolution=ignore-duplicates,return=minimal',
    body: {
      id: user.id,
      email: gm.email,
      consent_at: typeof meta.consent_at === 'string' ? meta.consent_at : new Date(now).toISOString(),
      consent_version: typeof meta.consent_version === 'string' ? meta.consent_version : CONSENT_VERSION,
      marketing_opt_in: meta.marketing_opt_in === true,
    },
  });
  if (!row.ok) {
    console.error('account: could not create the student record', row.status);
    return reply(502, { ok: false, error: 'unavailable', message: 'Sorry, we could not finish signing you in. Please try again.' });
  }
  return reply(200, { ok: true, next: '/student/' }, { cookies: sessionCookies(v.data, isSecure(request)) });
}

export async function handleLogout(request, env = {}, fetchImpl = fetch) {
  const bad = guard(request, ['POST']);
  if (bad) return bad;
  const jwt = parseCookies(request.headers.get('cookie')).u500_at;
  if (jwt && supabase(env, fetchImpl).configured) await supabase(env, fetchImpl).signOut(jwt); // best effort
  return reply(200, { ok: true }, { cookies: clearCookies(isSecure(request)) });
}

// ---- a signed-in student --------------------------------------------------------------------------------------

// Finds the student's session from the cookies, refreshing it when the access token has run out.
// Returns { jwt, uid, cookies } or null. cookies holds new Set-Cookie lines when the session was refreshed.
async function openSession(request, sb, now) {
  const c = parseCookies(request.headers.get('cookie'));
  let jwt = c.u500_at;
  let claims = jwt ? jwtClaims(jwt) : null;
  let cookies = [];
  if (!(claims && claims.sub && claims.exp * 1000 > now + 15000)) {
    if (!c.u500_rt) return null;
    const r = await sb.refresh(c.u500_rt);
    if (!r.ok || !r.data?.access_token) return null;
    jwt = r.data.access_token;
    claims = jwtClaims(jwt);
    cookies = sessionCookies(r.data, isSecure(request));
  }
  if (!claims || !UUID.test(String(claims.sub))) return null;
  return { jwt, uid: claims.sub, cookies };
}

const signedOut = (request) =>
  reply(401, { ok: false, error: 'signed_out', message: 'Please sign in again.' }, { cookies: clearCookies(isSecure(request)) });

// Reads the whole account in two parallel calls.
async function loadAccount(sb, s) {
  const [st, sec] = await Promise.all([
    sb.db(`students?id=eq.${s.uid}&select=${STUDENT_COLUMNS}`, { jwt: s.jwt }),
    sb.db(`profile_sections?student_id=eq.${s.uid}&select=section,data,updated_at`, { jwt: s.jwt }),
  ]);
  if (st.status === 401 || sec.status === 401) return { gone: true };
  if (!st.ok || !sec.ok) return { error: true };
  if (!Array.isArray(st.data) || !st.data.length) return { gone: true };
  const sections = Object.fromEntries(SECTION_IDS.map((id) => [id, {}]));
  const updated = {};
  for (const r of Array.isArray(sec.data) ? sec.data : []) {
    if (SECTION_IDS.includes(r.section)) { sections[r.section] = r.data || {}; updated[r.section] = r.updated_at; }
  }
  return { student: st.data[0], sections, updated };
}

// /api/me: GET reads the account, PATCH saves changes, DELETE removes the account and everything in it.
export async function handleMe(request, env = {}, fetchImpl = fetch, now = Date.now()) {
  const bad = guard(request, ['GET', 'PATCH', 'DELETE']);
  if (bad) return bad;
  const sb = supabase(env, fetchImpl);
  if (!sb.configured) return notConfigured();
  const s = await openSession(request, sb, now);
  if (!s) return signedOut(request);
  const out = (status, body) => reply(status, body, { cookies: s.cookies });

  if (request.method === 'GET') {
    const a = await loadAccount(sb, s);
    if (a.gone) return signedOut(request);
    if (a.error) return out(502, { ok: false, error: 'unavailable', message: 'Sorry, your details could not be loaded. Please try again.' });
    return out(200, { ok: true, ...a });
  }

  const { res, body } = await bodyOr(request);
  if (res) return res;

  if (request.method === 'DELETE') {
    if (body.confirm !== 'delete') return out(422, { ok: false, error: 'invalid', message: 'Confirm that you want to delete your account.' });
    const d = await sb.deleteUser(s.uid);
    if (!d.ok && d.status !== 404) {
      console.error('account: could not delete the user', d.status);
      return out(502, { ok: false, error: 'unavailable', message: 'Sorry, the account could not be deleted. Please try again, or contact us.' });
    }
    return reply(200, { ok: true }, { cookies: clearCookies(isSecure(request)) });
  }

  // PATCH: { student?: {...}, onboarded?: true, sections?: { academic: {...} } }
  const errors = {};
  const studentIn = body.student && typeof body.student === 'object' ? body.student : null;
  const cs = studentIn ? cleanStudent(studentIn) : { value: {}, errors: {} };
  if (Object.keys(cs.errors).length) errors.student = cs.errors;

  const sectionsIn = body.sections && typeof body.sections === 'object' && !Array.isArray(body.sections) ? body.sections : {};
  const rows = [];
  const cleaned = {};
  for (const [name, data] of Object.entries(sectionsIn)) {
    if (!SECTION_IDS.includes(name)) { (errors.sections ||= {})[name] = { _: 'Unknown section.' }; continue; }
    const c = cleanSection(name, data, now);
    if (Object.keys(c.errors).length) (errors.sections ||= {})[name] = c.errors;
    else { cleaned[name] = c.value; rows.push({ student_id: s.uid, section: name, data: c.value, updated_at: new Date(now).toISOString() }); }
  }
  if (Object.keys(errors).length) return out(422, { ok: false, error: 'invalid', errors });

  const iso = new Date(now).toISOString();
  const jobs = [];
  if (Object.keys(cs.value).length) {
    jobs.push(sb.db(`students?id=eq.${s.uid}`, { method: 'PATCH', jwt: s.jwt, prefer: 'return=minimal', body: { ...cs.value, updated_at: iso } }));
  }
  if (rows.length) {
    jobs.push(sb.db('profile_sections?on_conflict=student_id,section', { method: 'POST', jwt: s.jwt, prefer: 'resolution=merge-duplicates,return=minimal', body: rows }));
  }
  if (body.onboarded === true) {
    jobs.push(sb.db(`students?id=eq.${s.uid}&onboarded_at=is.null`, { method: 'PATCH', jwt: s.jwt, prefer: 'return=minimal', body: { onboarded_at: iso } }));
  }
  const results = await Promise.all(jobs);
  if (results.some((r) => r.status === 401)) return signedOut(request);
  if (results.some((r) => !r.ok)) {
    console.error('account: save failed', results.map((r) => r.status).join(','));
    return out(502, { ok: false, error: 'unavailable', message: 'Sorry, your changes could not be saved. Please try again.' });
  }
  return out(200, { ok: true, student: cs.value, sections: cleaned, onboarded: body.onboarded === true });
}

// /api/me/export: everything stored about the student, as a file they can keep.
export async function handleExport(request, env = {}, fetchImpl = fetch, now = Date.now()) {
  const bad = guard(request, ['GET']);
  if (bad) return bad;
  const sb = supabase(env, fetchImpl);
  if (!sb.configured) return notConfigured();
  const s = await openSession(request, sb, now);
  if (!s) return signedOut(request);
  const a = await loadAccount(sb, s);
  if (a.gone) return signedOut(request);
  if (a.error) return reply(502, { ok: false, error: 'unavailable', message: 'Sorry, your details could not be loaded. Please try again.' }, { cookies: s.cookies });
  return reply(
    200,
    { exported_at: new Date(now).toISOString(), site: 'universities500.com', student: a.student, sections: a.sections },
    { cookies: s.cookies, headers: { 'content-disposition': 'attachment; filename="universities500-my-data.json"' } },
  );
}
