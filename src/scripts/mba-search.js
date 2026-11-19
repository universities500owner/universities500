// Tracks, filters, sort and compare for the MBA Explorer.
// The page holds every programme as compact data (#mba-data) and only the first rows as HTML. This script filters the data
// and builds the rows a visitor can see. Nothing is sent anywhere: saved programmes stay in this browser.
import { $, fill } from './lib.js';
import { wireSaves, isSaved } from './saved.js';

const list = $('mba-list');
const q = $('mba-q'), c = $('mba-c'), u = $('mba-u'), k = $('mba-k'), m = $('mba-m'), l = $('mba-l'), o = $('mba-o');
const fee = $('mba-fee'), emp = $('mba-emp'), sv = $('mba-sv'), clear = $('mba-clear'), tally = $('mba-tally'), more = $('mba-more');
const fd = $('mba-fd'), fdSum = $('mba-fd-sum'), blurb = $('mba-blurb');
const PAGE = 30;
const NOT_STATED = 'Not stated';
let shown = PAGE;
let track = 'fresher';

// ---------- the data ----------
const data = JSON.parse($('mba-data').textContent);
const BOOKMARK = $('mba-bookmark').innerHTML;
const rows = data.M.map(([id, name, kind, kindLabel, uniName, school, country, ln, months, feeText, exp, test, starts, startMonths, hasEmp, tracks, chip]) => ({
  id: `mba:${id}`, slug: id, name, kind, kindLabel, uniName, school, country, countryName: data.K[country] || country,
  ln, mo: months, fe: feeText, ex: exp, ts: test, st: starts, sm: startMonths ? startMonths.split(' ') : [], emp: hasEmp === 1, tr: tracks.split(' '), chip,
  nameL: name.toLowerCase(),
  search: [name, uniName, school, kindLabel, data.K[country] || country].join(' ').toLowerCase(),
}));
const byId = new Map(rows.map((r) => [r.id, r]));

const col = new Intl.Collator();
const byName = (a, b) => col.compare(a.nameL, b.nameL) || col.compare(a.school, b.school);
const sorters = {
  name: byName,
  uni: (a, b) => col.compare(a.uniName, b.uniName) || byName(a, b),
  country: (a, b) => col.compare(a.countryName, b.countryName) || col.compare(a.uniName, b.uniName) || byName(a, b),
  // a programme with no stated length goes last: we do not guess it
  short: (a, b) => (a.mo || 999) - (b.mo || 999) || byName(a, b),
};

// ---------- one row, the same markup as components/MbaRow.astro ----------
const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const path = (r) => `/mba/${r.slug}/`;
const fact = (label, v) => `<div><dt>${label}</dt><dd${v ? '' : ' class="none"'}>${esc(v || NOT_STATED)}</dd></div>`;
const rowHtml = (r) => `<li class="crs mba" data-id="${esc(r.id)}">`
  + `<div class="crs-main"><h3 class="crs-title"><a href="${esc(path(r))}">${esc(r.name)}</a></h3>`
  + `<div class="crs-meta"><p class="crs-where">${esc(r.school)}<span class="crs-ctry"><span aria-hidden="true"> · </span>${esc(r.uniName)}<span aria-hidden="true"> · </span>${esc(r.countryName)}</span></p>`
  + `<ul class="crs-tags" aria-label="About this programme"><li>${esc(r.kindLabel)}</li>${r.chip ? `<li>${esc(r.chip)}</li>` : ''}</ul></div>`
  + `<dl class="crs-facts">${fact('Length', r.ln)}${fact('Tuition', r.fe)}${fact('Work experience', r.ex)}${fact('Test', r.ts)}${fact('Starts', r.st)}</dl></div>`
  + `<div class="crs-act"><a class="btn" href="${esc(path(r))}">Details</a>`
  + `<button type="button" class="rc-save" data-save aria-pressed="${isSaved(r.id)}" aria-label="Shortlist ${esc(r.name)}" title="Shortlist on this device">${BOOKMARK}<span class="rc-save-t"><span class="t-off">Shortlist</span><span class="t-on">Shortlisted</span></span></button>`
  + `<label class="crs-cmp"><input type="checkbox" data-compare aria-label="Compare ${esc(r.name)}" /> Compare</label></div></li>`;

// The university list follows the destination and the track: only universities that have a programme here.
function fillUnis(keep) {
  const seen = new Map();
  for (const r of rows) {
    if (!r.tr.includes(track) || (c.value && r.country !== c.value)) continue;
    const x = seen.get(r.uniName) || { n: 0 };
    x.n += 1;
    seen.set(r.uniName, x);
  }
  const opts = [...seen].sort((a, b) => col.compare(a[0], b[0])).map(([name, x]) => ({ v: name, l: `${name} (${x.n})` }));
  fill(u, [{ v: '', l: 'All universities' }, ...opts], keep && opts.some((x) => x.v === keep) ? keep : '');
}

const SELECTS = [[c, 'c'], [u, 'u'], [k, 'k'], [m, 'm'], [l, 'l'], [o, 'o']].filter(([el]) => el);
const CHECKS = [[fee, 'fee'], [emp, 'emp'], [sv, 'sv']];
function readUrl() {
  const p = new URLSearchParams(location.search);
  q.value = p.get('q') || '';
  const t = p.get('track');
  if (t && data.T[t]) track = t;
  const set = (el, key) => { const val = p.get(key); if (val && [...el.options].some((op) => op.value === val)) el.value = val; };
  set(c, 'c');
  fillUnis(p.get('u'));
  for (const [el, key] of SELECTS) if (el !== c && el !== u) set(el, key);
  for (const [el, key] of CHECKS) el.checked = p.get(key) === '1';
}
function writeUrl() {
  const p = new URLSearchParams();
  if (track !== 'fresher') p.set('track', track);
  if (q.value) p.set('q', q.value);
  for (const [el, key] of SELECTS) if (el.value && !(el === o && o.value === 'name')) p.set(key, el.value);
  for (const [el, key] of CHECKS) if (el.checked) p.set(key, '1');
  const qs = p.toString();
  history.replaceState(null, '', qs ? `?${qs}` : location.pathname);
}
const filtering = () => Boolean(q.value.trim() || CHECKS.some(([el]) => el.checked) || SELECTS.some(([el]) => el !== o && el.value));

// ---------- the three tracks ----------
const tabs = [...document.querySelectorAll('.mba-tab')];
function setTrack(id, focus) {
  track = id;
  tabs.forEach((t) => {
    const on = t.dataset.track === id;
    t.setAttribute('aria-selected', String(on));
    t.tabIndex = on ? 0 : -1;
    if (on && focus) t.focus();
  });
  $('mba-panel').setAttribute('aria-labelledby', `mba-tab-${id}`);
  blurb.textContent = data.T[id];
  fillUnis(u.value);
  apply(true);
}
tabs.forEach((t, i) => {
  t.addEventListener('click', () => setTrack(t.dataset.track, false));
  t.addEventListener('keydown', (ev) => {
    const to = ev.key === 'ArrowRight' ? (i + 1) % tabs.length : ev.key === 'ArrowLeft' ? (i + tabs.length - 1) % tabs.length : null;
    if (to === null) return;
    ev.preventDefault();
    setTrack(tabs[to].dataset.track, true);
  });
});
// How many programmes each track holds, not counting any filter.
for (const t of tabs) {
  const n = rows.filter((r) => r.tr.includes(t.dataset.track)).length;
  const el = t.querySelector('[data-count]');
  if (el) el.textContent = n;
}

// ---------- compare up to three ----------
const MAX = 3;
const picked = [];
const cmpSec = $('compare'), cmpSay = $('mba-cmp-say'), cmpBox = $('mba-cmp');
function syncBoxes() {
  list.querySelectorAll('[data-compare]').forEach((cb) => {
    const r = byId.get(cb.closest('.crs').dataset.id);
    cb.checked = picked.includes(r);
    cb.disabled = !cb.checked && picked.length >= MAX;
  });
}

function apply(reset) {
  if (reset) shown = PAGE;
  const words = q.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const maxMonths = l.value ? Number(l.value) : 0;
  const matches = rows.filter((r) => {
    if (!r.tr.includes(track)) return false;
    if (words.length && !words.every((w) => r.search.includes(w))) return false;
    if (c.value && r.country !== c.value) return false;
    if (u.value && r.uniName !== u.value) return false;
    if (k.value && r.kind !== k.value) return false;
    if (m && m.value && !r.sm.includes(m.value)) return false;
    // A programme that does not state its length is kept: we do not guess one.
    if (maxMonths && r.mo && r.mo > maxMonths) return false;
    if (fee.checked && !r.fe) return false;
    if (emp.checked && !r.emp) return false;
    if (sv.checked && !isSaved(r.id)) return false;
    return true;
  });
  matches.sort(sorters[o.value]);
  list.innerHTML = matches.slice(0, shown).map(rowHtml).join('');
  syncBoxes();
  const others = Boolean(words.length || CHECKS.some(([el]) => el.checked) || SELECTS.some(([el]) => el !== o && el.value));
  const n = matches.length;
  tally.textContent = n === 0
    ? (sv.checked && !others ? 'Nothing saved yet. Use the bookmark on a programme to save it on this device.' : 'No programmes match. Try fewer filters, or another tab.')
    : `${n.toLocaleString('en-GB')} programme${n === 1 ? '' : 's'}` + (n > shown ? `, showing ${shown}` : '');
  more.hidden = n <= shown;
  clear.hidden = !filtering();
  const active = SELECTS.filter(([el]) => el !== o && el.value).length + CHECKS.filter(([el]) => el.checked).length;
  fdSum.textContent = active ? `Filters (${active})` : 'Filters';
  writeUrl();
}

let typing;
[q, ...SELECTS.map(([el]) => el), ...CHECKS.map(([el]) => el)].forEach((el) => el.addEventListener(el === q ? 'input' : 'change', () => {
  if (el === c) fillUnis('');   // a new destination: the university list starts again
  if (el === q) {               // wait for a pause in typing so the list is not rebuilt on every key
    clearTimeout(typing);
    typing = setTimeout(() => apply(true), 120);
    return;
  }
  apply(true);
}));
clear.addEventListener('click', () => {
  clearTimeout(typing);
  q.value = '';
  for (const [el] of CHECKS) el.checked = false;
  for (const [el] of SELECTS) el.value = el === o ? 'name' : '';
  fillUnis('');
  apply(true);
  q.focus();
});
more.addEventListener('click', () => { shown += PAGE; apply(false); });
wireSaves(list, () => { if (sv.checked) apply(true); });

// ---------- the comparison table ----------
const FACTS = [
  ['School', (r) => r.school],
  ['University', (r) => r.uniName],
  ['Type', (r) => r.kindLabel],
  ['Length', (r) => r.ln || NOT_STATED],
  ['Tuition', (r) => r.fe || NOT_STATED],
  ['Work experience', (r) => r.ex || NOT_STATED],
  ['Test', (r) => r.ts || NOT_STATED],
  ['Starts', (r) => r.st || NOT_STATED],
];
function renderCompare() {
  cmpSec.hidden = picked.length === 0;
  syncBoxes();
  cmpBox.textContent = '';
  if (!picked.length) return;
  cmpSay.textContent = picked.length === 1
    ? 'Tick one or two more programmes to line them up. Rows that differ are what should decide it.'
    : `${picked.length} of ${MAX} programmes. Rows that differ are in bold. Tuition is shown as each school's page gave it, so currencies, years and what the fee covers may differ.`;
  const wrap = document.createElement('div');
  wrap.className = 'tbl-wrap';
  const t = document.createElement('table');
  t.className = 'tbl';
  const head = t.createTHead().insertRow();
  head.appendChild(document.createElement('th'));
  for (const r of picked) {
    const th = document.createElement('th');
    th.scope = 'col';
    const a = document.createElement('a');
    a.href = path(r);
    a.textContent = r.name;
    th.appendChild(a);
    head.appendChild(th);
  }
  const body = t.createTBody();
  for (const [label, get] of FACTS) {
    const tr = body.insertRow();
    tr.insertCell().textContent = label;
    const vals = picked.map(get);
    const same = vals.every((v) => v === vals[0]);
    vals.forEach((v) => { const td = tr.insertCell(); td.textContent = v; if (!same) td.style.fontWeight = '600'; });
  }
  const tr = body.insertRow();
  tr.insertCell().textContent = 'Details';
  for (const r of picked) {
    const td = tr.insertCell();
    const a = document.createElement('a');
    a.href = path(r);
    a.textContent = 'Programme page, with the link to the school';
    td.appendChild(a);
  }
  wrap.appendChild(t);
  cmpBox.appendChild(wrap);
  const b = document.createElement('button');
  b.type = 'button';
  b.className = 'btn-ghost';
  b.textContent = 'Clear comparison';
  b.addEventListener('click', () => { picked.length = 0; renderCompare(); });
  cmpBox.appendChild(b);
}
list.addEventListener('change', (ev) => {
  const cb = ev.target.closest('[data-compare]');
  if (!cb) return;
  const r = byId.get(cb.closest('.crs').dataset.id);
  const i = picked.indexOf(r);
  if (cb.checked && i < 0 && picked.length < MAX) picked.push(r);
  if (!cb.checked && i >= 0) picked.splice(i, 1);
  renderCompare();
});

// On a phone the filters fold away so the first result is not three screens down; on a wide screen they stay open.
const narrow = window.matchMedia('(max-width: 620px)');
const fold = () => { fd.open = !narrow.matches; };
fold();
narrow.addEventListener('change', fold);

readUrl();
setTrack(track, false);
list.hidden = false;
