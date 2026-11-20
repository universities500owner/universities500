// The admin list: who has signed up, as a simple CRM view at /admin/. Read-only.
//
// Who may use it: a signed-in student whose Gmail address is in the ADMIN_EMAILS Worker setting (comma separated, for example
// "owner@gmail.com, partner@gmail.com"). Everyone else gets "not found", and with the setting empty it is switched off.
// The address is read from the student's own row in the database with their own session, so it cannot be faked by editing a cookie.
//
// What it shows: contact, interests, how far they have got and whether they agreed to updates. It never shows passport, phone or
// document data (none is collected), a student's private notes, or their immigration and visa answers. Those two show only as "added".
// Opening a student and downloading the CSV are written to the Cloudflare log (who and how many, never the data).
//
// Reads two Supabase views made by supabase/migrations/0004_admin_views.sql, which only the server's secret key can read.

import { normaliseGmail } from './gmail.js';
import { supabase } from './supabase.js';
import { UUID } from './session.js';
import { reply, guard, notConfigured, openSession, signedOut, safe } from './handlers.js';

const COLUMNS = 'id,email,display_name,full_name,created_at,updated_at,onboarded_at,marketing_opt_in,countries,level,stage,shortlist_count,sections';
const SORTS = ['created_at', 'updated_at', 'email', 'shortlist_count'];
const HIDDEN_SECTIONS = ['immigration', 'visa_au'];   // shown as "added", never opened here
const PAGE_MAX = 1000;                                  // what Supabase returns in one request
const EXPORT_MAX = 5000;
const DAY = 86400000;

export function adminEmails(env = {}) {
  return String(env.ADMIN_EMAILS || '').split(/[\s,;]+/).map((e) => normaliseGmail(e)).filter((r) => r.ok).map((r) => r.email);
}

const notFound = (cookies = []) => reply(404, { ok: false, error: 'not_found', message: 'Not found.' }, { cookies });

// Checks the caller is signed in and is an admin. Returns { sb, s } to carry on, or { res } to send back.
async function gate(request, env, fetchImpl, now) {
  const sb = supabase(env, fetchImpl);
  if (!sb.configured) return { res: notConfigured() };
  const s = await openSession(request, sb, now);
  if (!s) return { res: signedOut(request) };
  const allow = adminEmails(env);
  if (!allow.length) return { res: notFound(s.cookies) };
  const me = await sb.db(`students?id=eq.${s.uid}&select=email`, { jwt: s.jwt });
  if (me.status === 401) return { res: signedOut(request) };
  if (!me.ok) return { res: reply(502, { ok: false, error: 'unavailable', message: 'Could not check access. Try again.' }, { cookies: s.cookies }) };
  const mine = normaliseGmail(Array.isArray(me.data) && me.data[0] ? me.data[0].email : '');
  if (!mine.ok || !allow.includes(mine.email)) return { res: notFound(s.cookies) };
  return { sb, s };
}

// ---- the list --------------------------------------------------------------------------------------------------

// What the page may ask for. Anything else is ignored, and the search text is stripped of everything PostgREST or LIKE treats as syntax.
export function parseFilters(params, now) {
  const get = (k) => String(params.get(k) ?? '').trim();
  const q = get('q').normalize('NFKC').replace(/[^\p{L}\p{N}@.\- ]/gu, '').replace(/\s+/g, ' ').slice(0, 60).trim();
  const sort = SORTS.includes(get('sort')) ? get('sort') : 'created_at';
  const dir = get('dir') === 'asc' ? 'asc' : 'desc';
  const size = Math.min(100, Math.max(10, parseInt(get('size'), 10) || 25));
  const page = Math.min(10000, Math.max(1, parseInt(get('page'), 10) || 1));
  const f = [];
  if (q) f.push(`or=(email.ilike.*${q}*,display_name.ilike.*${q}*,full_name.ilike.*${q}*)`);
  if (get('marketing') === '1') f.push('marketing_opt_in=eq.true');
  if (get('onboarded') === '1') f.push('onboarded_at=not.is.null');
  if (get('onboarded') === '0') f.push('onboarded_at=is.null');
  const days = { '7': 7, '30': 30, '90': 90 }[get('joined')];
  if (days) f.push(`created_at=gte.${encodeURIComponent(new Date(now - days * DAY).toISOString())}`);
  if (/^[a-z0-9-]{2,40}$/.test(get('country'))) f.push(`countries=cs.{${get('country')}}`);
  if (get('has') === 'shortlist') f.push('shortlist_count=gt.0');
  if (get('has') === 'visa') f.push('sections=cs.{visa_au}');
  return { filters: f.join('&'), sort, dir, size, page, q };
}

const order = (sort, dir) => `order=${sort}.${dir}.nullslast,id.asc`;
const total = (range) => { const n = parseInt(String(range).split('/')[1], 10); return Number.isFinite(n) ? n : 0; };

async function listImpl(request, env = {}, fetchImpl = fetch, now = Date.now()) {
  const bad = guard(request, ['GET']);
  if (bad) return bad;
  const g = await gate(request, env, fetchImpl, now);
  if (g.res) return g.res;
  const p = parseFilters(new URL(request.url).searchParams, now);
  const [rows, stats] = await Promise.all([
    g.sb.db(`admin_students?select=${COLUMNS}&${p.filters ? p.filters + '&' : ''}${order(p.sort, p.dir)}&limit=${p.size}&offset=${(p.page - 1) * p.size}`, { prefer: 'count=exact' }),
    g.sb.db('admin_stats?select=*'),
  ]);
  if (!rows.ok || !stats.ok) {
    console.error('admin: list failed', rows.status, stats.status);
    return reply(502, { ok: false, error: 'unavailable', message: 'The student list could not be loaded. Has supabase/migrations/0004_admin_views.sql been run?' }, { cookies: g.s.cookies });
  }
  return reply(200, {
    ok: true,
    stats: Array.isArray(stats.data) ? stats.data[0] || {} : {},
    total: total(rows.range),
    page: p.page, size: p.size, sort: p.sort, dir: p.dir,
    rows: Array.isArray(rows.data) ? rows.data : [],
  }, { cookies: g.s.cookies });
}

// ---- one student ---------------------------------------------------------------------------------------------------

async function detailImpl(request, env = {}, fetchImpl = fetch, now = Date.now()) {
  const bad = guard(request, ['GET']);
  if (bad) return bad;
  const g = await gate(request, env, fetchImpl, now);
  if (g.res) return g.res;
  const id = new URL(request.url).searchParams.get('id') || '';
  if (!UUID.test(id)) return reply(400, { ok: false, error: 'bad_request', message: 'Not a student id.' }, { cookies: g.s.cookies });
  const [st, sec, sv] = await Promise.all([
    g.sb.db(`admin_students?id=eq.${id}&select=${COLUMNS},consent_at,consent_version,subject_groups`),
    g.sb.db(`profile_sections?student_id=eq.${id}&select=section,data,updated_at`),
    g.sb.db(`saved_items?student_id=eq.${id}&select=item_id,kind,title,sub,url,status,saved_at,updated_at&order=saved_at.desc&limit=200`),
  ]);
  if (!st.ok || !sec.ok || !sv.ok) return reply(502, { ok: false, error: 'unavailable', message: 'That student could not be loaded.' }, { cookies: g.s.cookies });
  if (!Array.isArray(st.data) || !st.data.length) return notFound(g.s.cookies);
  const sections = {};
  for (const r of Array.isArray(sec.data) ? sec.data : []) {
    sections[r.section] = HIDDEN_SECTIONS.includes(r.section) ? { hidden: true, updated_at: r.updated_at } : { data: r.data || {}, updated_at: r.updated_at };
  }
  console.info('admin: opened a student', g.s.uid, id);
  return reply(200, { ok: true, student: st.data[0], sections, shortlist: Array.isArray(sv.data) ? sv.data : [] }, { cookies: g.s.cookies });
}

// ---- CSV -------------------------------------------------------------------------------------------------------------

// A cell that starts with = + - @ is read as a formula by Excel and Sheets, so it gets a leading apostrophe. Everything is quoted.
export function csvCell(v) {
  let s = v == null ? '' : String(v);
  if (/^[=+\-@\t\r]/.test(s)) s = "'" + s;
  return '"' + s.replace(/"/g, '""') + '"';
}

const CSV_HEAD = ['Signed up', 'Email', 'Name', 'Countries', 'Level', 'Stage', 'Onboarded', 'Agreed to updates', 'Shortlist items', 'Profile sections saved', 'Last updated'];

export function toCsv(rows) {
  const day = (d) => (d ? String(d).slice(0, 10) : '');
  const lines = [CSV_HEAD.map(csvCell).join(',')];
  for (const r of rows) {
    lines.push([
      day(r.created_at), r.email, r.full_name || r.display_name || '', (r.countries || []).join('; '), r.level || '', r.stage || '',
      r.onboarded_at ? 'yes' : 'no', r.marketing_opt_in ? 'yes' : 'no', r.shortlist_count || 0, (r.sections || []).filter((s) => s !== 'visa_au').length, day(r.updated_at),
    ].map(csvCell).join(','));
  }
  return '﻿' + lines.join('\r\n') + '\r\n';
}

async function exportImpl(request, env = {}, fetchImpl = fetch, now = Date.now()) {
  const bad = guard(request, ['GET']);
  if (bad) return bad;
  const g = await gate(request, env, fetchImpl, now);
  if (g.res) return g.res;
  const p = parseFilters(new URL(request.url).searchParams, now);
  const all = [];
  for (let offset = 0; offset < EXPORT_MAX; offset += PAGE_MAX) {
    const r = await g.sb.db(`admin_students?select=${COLUMNS}&${p.filters ? p.filters + '&' : ''}${order(p.sort, p.dir)}&limit=${Math.min(PAGE_MAX, EXPORT_MAX - offset)}&offset=${offset}`);
    if (!r.ok || !Array.isArray(r.data)) {
      console.error('admin: export failed', r.status);
      return reply(502, { ok: false, error: 'unavailable', message: 'The export could not be made. Try again.' }, { cookies: g.s.cookies });
    }
    all.push(...r.data);
    if (r.data.length < PAGE_MAX) break;
  }
  console.info('admin: exported students', g.s.uid, all.length);
  const date = new Date(now).toISOString().slice(0, 10);
  return new Response(toCsv(all), {
    status: 200,
    headers: {
      'content-type': 'text/csv; charset=utf-8',
      'content-disposition': `attachment; filename="universities500-students-${date}.csv"`,
      'cache-control': 'no-store',
      'x-content-type-options': 'nosniff',
      ...(g.s.cookies.length ? { 'set-cookie': g.s.cookies[0] } : {}),
    },
  });
}

export const handleAdminList = safe('handleAdminList', listImpl);
export const handleAdminStudent = safe('handleAdminStudent', detailImpl);
export const handleAdminExport = safe('handleAdminExport', exportImpl);
