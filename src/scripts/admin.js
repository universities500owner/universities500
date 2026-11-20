// The owner's student list (/admin/). Asks /api/admin/students for one page at a time; the server decides who may see it.
// Nothing a student typed is put into the page as HTML.
import { STAGES, LEVELS, COUNTRIES, SUBJECT_GROUPS, SECTIONS, label } from '../lib/account/schema.js';

const root = document.querySelector('[data-admin]');
const $ = (sel, from = root) => from.querySelector(sel);
const $$ = (sel, from = root) => [...from.querySelectorAll(sel)];
const loading = $('[data-loading]'), content = $('[data-content]'), noticeBox = $('[data-notice]');
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };

const FILTERS = ['q', 'joined', 'country', 'onboarded', 'marketing', 'has'];
const state = { q: '', joined: '', country: '', onboarded: '', marketing: '', has: '', sort: 'created_at', dir: 'desc', page: 1, size: 25 };
let data = null, timer = 0, seq = 0;

const fmtDate = (iso) => (iso ? new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '');
const fmtFull = (iso) => (iso ? new Date(iso).toLocaleString('en-GB') : '');
const countryName = (slug) => label(COUNTRIES, slug) || slug;

// ---- talking to the server --------------------------------------------------------------------------------

function query(extra = {}) {
  const p = new URLSearchParams();
  for (const k of FILTERS) if (state[k]) p.set(k, state[k]);
  const all = { ...extra };
  for (const [k, v] of Object.entries(all)) p.set(k, v);
  return p.toString();
}

async function get(url) {
  try {
    const r = await fetch(url, { credentials: 'same-origin' });
    const j = await r.json().catch(() => ({}));
    return { ok: r.ok && j.ok !== false, status: r.status, j };
  } catch { return { ok: false, status: 0, j: { message: 'We could not reach the site. Check your connection and try again.' } }; }
}

function notice(title, text, action) {
  loading.hidden = true; content.hidden = true; noticeBox.hidden = false;
  noticeBox.replaceChildren(el('h2', '', title), el('p', '', text));
  if (action) {
    const a = el('a', 'ad-btn', action.label); a.href = action.href; noticeBox.append(a);
  }
}

// ---- the list ---------------------------------------------------------------------------------------------

async function load() {
  const mine = ++seq;
  const r = await get('/api/admin/students?' + query({ sort: state.sort, dir: state.dir, page: state.page, size: state.size }));
  if (mine !== seq) return; // a newer search is already on its way
  if (r.status === 401) return notice('Sign in to continue', 'Sign in with the Gmail address of the site owner.', { label: 'Sign in', href: '/sign-in/?next=/admin/' });
  if (r.status === 404) return notice('Not available', 'This page is only for the site owner.', { label: 'Go to my dashboard', href: '/student/' });
  if (r.status === 503) return notice('Not open yet', r.j.message || 'Sign-in is not open yet.');
  if (!r.ok) return notice('Could not load the list', r.j.message || 'Something went wrong. Try again in a moment.');
  data = r.j;
  loading.hidden = true; noticeBox.hidden = true; content.hidden = false;
  paint();
}

const STAT_DEFS = [
  ['total', 'All students', {}],
  ['last_7', 'Joined in 7 days', { joined: '7' }],
  ['last_30', 'Joined in 30 days', { joined: '30' }],
  ['onboarded', 'Finished setup', { onboarded: '1' }],
  ['marketing', 'Agreed to updates', { marketing: '1' }],
  ['with_shortlist', 'Have a shortlist', { has: 'shortlist' }],
  ['with_visa_check', 'Did the visa self-check', { has: 'visa' }],
];

function paintStats() {
  const ul = $('[data-stats]');
  ul.replaceChildren();
  for (const [key, name, set] of STAT_DEFS) {
    const li = el('li');
    const b = el('button', 'ad-stat'); b.type = 'button';
    b.append(el('b', '', String(data.stats[key] ?? 0)), el('span', '', name));
    b.addEventListener('click', () => {
      for (const k of FILTERS) state[k] = '';
      Object.assign(state, set); state.page = 1;
      syncForm(); go();
    });
    li.append(b); ul.append(li);
  }
}

function chips(slugs) {
  const wrap = el('span', 'ad-chips');
  const shown = slugs.slice(0, 3);
  for (const s of shown) wrap.append(el('span', 'ad-chip', countryName(s)));
  if (slugs.length > 3) wrap.append(el('span', 'ad-chip ad-more', `+${slugs.length - 3}`));
  return wrap;
}

function paint() {
  paintStats();
  const rows = $('[data-rows]');
  rows.replaceChildren();
  for (const r of data.rows) {
    const tr = el('tr');
    const who = el('td', 'ad-who');
    const name = r.full_name || r.display_name;
    const open = el('button', 'ad-open' + (name ? '' : ' is-none'), name || 'No name yet'); open.type = 'button';
    open.setAttribute('aria-label', `Open details for ${name || r.email}`);
    who.append(open, el('span', 'ad-mail', r.email));
    const joined = el('td', '', fmtDate(r.created_at)); joined.title = fmtFull(r.created_at);
    const interest = el('td');
    if ((r.countries || []).length) interest.append(chips(r.countries));
    if (r.level) interest.append(el('span', 'ad-sub', label(LEVELS, r.level) || r.level));
    if (!(r.countries || []).length && !r.level) interest.append(el('span', 'ad-dash', '–'));
    const stage = el('td', '', r.stage ? label(STAGES, r.stage) || r.stage : '–');
    const profileSections = (r.sections || []).filter((s) => s !== 'visa_au').length;
    const prof = el('td', '', `${profileSections} of 5`);
    if ((r.sections || []).includes('visa_au')) prof.append(el('span', 'ad-sub', 'Visa check done'));
    const sl = el('td', 'ad-num', String(r.shortlist_count || 0));
    const up = el('td', '', r.marketing_opt_in ? 'Yes' : '–');
    const upd = el('td', '', fmtDate(r.updated_at)); upd.title = fmtFull(r.updated_at);
    tr.append(who, joined, interest, stage, prof, sl, up, upd);
    tr.addEventListener('click', (e) => { if (!(e.target instanceof HTMLButtonElement)) openStudent(r); });
    open.addEventListener('click', () => openStudent(r));
    rows.append(tr);
  }

  const from = data.total ? (data.page - 1) * data.size + 1 : 0;
  const to = Math.min(data.total, (data.page - 1) * data.size + data.rows.length);
  $('[data-count]').textContent = data.total ? `Showing ${from} to ${to} of ${data.total} student${data.total === 1 ? '' : 's'}` : '';
  $('[data-wrap]').hidden = !data.rows.length;
  const empty = $('[data-empty]');
  empty.hidden = !!data.rows.length;
  if (!data.rows.length) empty.textContent = FILTERS.some((k) => state[k]) ? 'No students match these filters. Choose Clear to see everyone.' : 'Nobody has signed up yet.';
  const pages = Math.max(1, Math.ceil(data.total / data.size));
  $('[data-page-info]').textContent = `Page ${data.page} of ${pages}`;
  $('[data-prev]').disabled = data.page <= 1;
  $('[data-next]').disabled = data.page >= pages;
  $('[data-pager]').hidden = data.total <= 25;
  $('[data-export]').href = '/api/admin/export?' + query({ sort: state.sort, dir: state.dir });
  for (const th of $$('th[data-sort]')) th.setAttribute('aria-sort', th.dataset.sort === state.sort ? (state.dir === 'asc' ? 'ascending' : 'descending') : 'none');
}

// ---- controls ---------------------------------------------------------------------------------------------

function syncForm() {
  const bar = $('[data-bar]');
  for (const k of FILTERS) { const f = bar.elements[k]; if (f) f.value = state[k]; }
  $('[data-size]').value = String(state.size);
}
function readUrl() {
  const p = new URLSearchParams(location.search);
  for (const k of FILTERS) state[k] = (p.get(k) || '').slice(0, 60);
  if (['created_at', 'updated_at', 'email', 'shortlist_count'].includes(p.get('sort'))) state.sort = p.get('sort');
  if (p.get('dir') === 'asc') state.dir = 'asc';
  state.page = Math.max(1, parseInt(p.get('page'), 10) || 1);
  state.size = [25, 50, 100].includes(parseInt(p.get('size'), 10)) ? parseInt(p.get('size'), 10) : 25;
}
// Keeps the address in step with the list, so a reload or a shared link shows the same view.
function go() {
  const url = '/admin/?' + query({ sort: state.sort, dir: state.dir, page: state.page, size: state.size });
  history.replaceState(null, '', url);
  load();
}

function setup() {
  const sel = $('#ad-country');
  for (const [slug, name] of COUNTRIES) { const o = el('option', '', name); o.value = slug; sel.append(o); }
  readUrl(); syncForm();
  const bar = $('[data-bar]');
  bar.addEventListener('submit', (e) => e.preventDefault());
  bar.addEventListener('input', (e) => {
    const t = e.target;
    if (!(t instanceof HTMLInputElement || t instanceof HTMLSelectElement) || !FILTERS.includes(t.name)) return;
    state[t.name] = t.value.trim(); state.page = 1;
    clearTimeout(timer);
    timer = setTimeout(go, t.name === 'q' ? 300 : 0);
  });
  $('[data-clear]').addEventListener('click', () => { for (const k of FILTERS) state[k] = ''; state.page = 1; syncForm(); go(); });
  for (const th of $$('th[data-sort]')) {
    $('button', th).addEventListener('click', () => {
      if (state.sort === th.dataset.sort) state.dir = state.dir === 'asc' ? 'desc' : 'asc';
      else { state.sort = th.dataset.sort; state.dir = th.dataset.sort === 'email' ? 'asc' : 'desc'; }
      state.page = 1; go();
    });
  }
  $('[data-prev]').addEventListener('click', () => { state.page = Math.max(1, state.page - 1); go(); });
  $('[data-next]').addEventListener('click', () => { state.page += 1; go(); });
  $('[data-size]').addEventListener('change', (e) => { state.size = parseInt(e.target.value, 10) || 25; state.page = 1; go(); });
  $('[data-d-close]').addEventListener('click', () => $('[data-dialog]').close());
  $('[data-dialog]').addEventListener('click', (e) => { if (e.target === e.currentTarget) e.currentTarget.close(); }); // a click on the backdrop
  load();
}

// ---- one student ------------------------------------------------------------------------------------------

const PROFILE_SECTIONS = ['profile', 'academic', 'english', 'work'];
const HIDDEN_NAMES = { immigration: 'Earlier visa applications', visa_au: 'Visa self-check answers' };

function fmtValue(field, v) {
  if (v === true) return 'Yes';
  if (Array.isArray(v)) return v.map(String).join(', ');
  if (field.type === 'select' && Array.isArray(field.options)) { const o = field.options.find((x) => x[0] === v); return o ? o[1] : String(v); }
  return String(v);
}

function dl(pairs) {
  const d = el('dl', 'ad-dl');
  for (const [k, v] of pairs) { if (v === '' || v == null) continue; d.append(el('dt', '', k), el('dd', '', v)); }
  return d;
}

async function openStudent(r) {
  const dlg = $('[data-dialog]'), body = $('[data-d-body]'), err = $('[data-d-error]'), busy = $('[data-d-loading]');
  $('#ad-d-name').textContent = r.full_name || r.display_name || 'No name yet';
  $('[data-d-email]').textContent = r.email;
  body.replaceChildren(); err.hidden = true; busy.hidden = false;
  if (!dlg.open) dlg.showModal();
  $('#ad-d-name').focus();
  const res = await get('/api/admin/student?id=' + encodeURIComponent(r.id));
  busy.hidden = true;
  if (!res.ok) { err.hidden = false; err.textContent = res.j.message || 'That student could not be loaded.'; return; }
  const { student: s, sections, shortlist } = res.j;

  const sum = el('section', 'ad-d-sec');
  sum.append(el('h3', '', 'Account'), dl([
    ['Joined', fmtFull(s.created_at)],
    ['Agreed to Terms and Privacy', `${fmtFull(s.consent_at)} (version ${s.consent_version})`],
    ['Agreed to updates', s.marketing_opt_in ? 'Yes' : 'No'],
    ['Stage', s.stage ? label(STAGES, s.stage) || s.stage : ''],
    ['Level', s.level ? label(LEVELS, s.level) || s.level : ''],
    ['Countries', (s.countries || []).map(countryName).join(', ')],
    ['Subjects', (s.subject_groups || []).map((g) => label(SUBJECT_GROUPS, g) || g).join(', ')],
    ['Finished setup', s.onboarded_at ? fmtFull(s.onboarded_at) : 'Not yet'],
    ['Last changed', fmtFull(s.updated_at)],
  ]));
  body.append(sum);

  for (const id of PROFILE_SECTIONS) {
    const got = sections[id];
    if (!got || got.hidden) continue;
    const spec = SECTIONS[id];
    const pairs = [];
    for (const f of spec.fields) {
      const v = got.data[f.id];
      if (v === undefined || v === null || v === '' || (Array.isArray(v) && !v.length)) continue;
      pairs.push([f.label, fmtValue(f, v)]);
    }
    const items = spec.list && Array.isArray(got.data[spec.list.key]) ? got.data[spec.list.key] : [];
    items.forEach((it, i) => {
      const parts = spec.list.fields.map((f) => (it[f.id] === undefined || it[f.id] === null || it[f.id] === '' ? '' : fmtValue(f, it[f.id]))).filter(Boolean);
      if (parts.length) pairs.push([`${spec.list.noun[0].toUpperCase()}${spec.list.noun.slice(1)} ${i + 1}`, parts.join(' · ')]);
    });
    if (!pairs.length) continue;
    const sec = el('section', 'ad-d-sec');
    sec.append(el('h3', '', spec.label), dl(pairs));
    body.append(sec);
  }

  const hidden = Object.keys(HIDDEN_NAMES).filter((k) => sections[k]);
  if (hidden.length) {
    const sec = el('section', 'ad-d-sec');
    sec.append(el('h3', '', 'Kept private'), el('p', 'ad-sub', 'Added by the student. Not shown here, on purpose.'), dl(hidden.map((k) => [HIDDEN_NAMES[k], 'Added'])));
    body.append(sec);
  }

  const sl = el('section', 'ad-d-sec');
  sl.append(el('h3', '', `Shortlist (${shortlist.length})`));
  if (!shortlist.length) sl.append(el('p', 'ad-sub', 'Nothing saved yet.'));
  else {
    const ul = el('ul', 'ad-short');
    for (const it of shortlist) {
      const li = el('li');
      const safe = /^(\/|https:\/\/)/.test(it.url || '');
      if (safe) { const a = el('a', '', it.title); a.href = it.url; a.rel = 'noopener nofollow'; a.target = '_blank'; li.append(a); } else li.append(el('span', '', it.title));
      li.append(el('span', 'ad-sub', `${{ crs: 'Course', mba: 'MBA', sch: 'Scholarship', int: 'Internship' }[it.kind] || it.kind} · ${it.status} · saved ${fmtDate(it.saved_at)}`));
      ul.append(li);
    }
    sl.append(ul);
  }
  body.append(sl);
}

setup();
