// Filters, sort and compare for the course list.
// The page holds every course as compact data (#crs-data) and only the first rows as HTML. This script filters the data
// and builds the rows a visitor can see, so a long list does not mean a heavy page. Nothing is sent anywhere: saved courses stay in this browser.
import { $, fill } from './lib.js';
import { wireSaves, isSaved } from './saved.js';

const list = $('crs-list');
const q = $('crs-q'), c = $('crs-c'), u = $('crs-u'), l = $('crs-l'), f = $('crs-f'), e = $('crs-e'), m = $('crs-m'), o = $('crs-o');
const fee = $('crs-fee'), ie = $('crs-ie'), sv = $('crs-sv'), clear = $('crs-clear'), tally = $('crs-tally'), more = $('crs-more');
const fd = $('crs-fd'), fdSum = $('crs-fd-sum');
const PAGE = 30;
const NOT_STATED = 'Not stated';
let shown = PAGE;

// ---------- the data ----------
const data = JSON.parse($('crs-data').textContent);
const BOOKMARK = $('crs-bookmark').innerHTML;
const rows = data.C.map(([uni, slug, name, degree, lv, level, field, ln, years, feeText, ieText, score, st, months]) => {
  const [uniName, country] = data.U[uni];
  const countryName = data.K[country] || country;
  return {
    id: `crs:${uni}/${slug}`, uni, slug, name, lv, level, fd: field, ln, years, fe: feeText, ie: ieText, sc: score, st,
    mo: months ? months.split(' ') : [], uniName, country, countryName,
    nameL: name.toLowerCase(),
    search: [name, uniName, field, degree, countryName].join(' ').toLowerCase(),
  };
});
const byId = new Map(rows.map((r) => [r.id, r]));

const col = new Intl.Collator();
const byName = (a, b) => col.compare(a.nameL, b.nameL) || col.compare(a.uniName, b.uniName);
const sorters = {
  name: byName,
  uni: (a, b) => col.compare(a.uniName, b.uniName) || byName(a, b),
  country: (a, b) => col.compare(a.country, b.country) || col.compare(a.uniName, b.uniName) || byName(a, b),
  // a course with no stated length goes last: we do not guess it
  short: (a, b) => (a.years || 99) - (b.years || 99) || byName(a, b),
};

// ---------- one row, the same markup as components/CourseRow.astro ----------
const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const path = (r) => `/courses/${r.uni}/${r.slug}/`;
const fact = (label, v) => `<div><dt>${label}</dt><dd${v ? '' : ' class="none"'}>${esc(v || NOT_STATED)}</dd></div>`;
const rowHtml = (r) => `<li class="crs" data-id="${esc(r.id)}">`
  + `<div class="crs-main"><h3 class="crs-title"><a href="${esc(path(r))}">${esc(r.name)}</a></h3>`
  + `<p class="crs-where"><a href="/universities/${esc(r.uni)}/">${esc(r.uniName)}</a><span aria-hidden="true"> · </span>${esc(r.countryName)}</p>`
  + `<ul class="crs-tags" aria-label="About this course"><li>${esc(r.lv)}</li>${r.fd ? `<li>${esc(r.fd)}</li>` : ''}</ul></div>`
  + `<dl class="crs-facts">${fact('Length', r.ln)}${fact('International fee', r.fe)}${fact('English', r.ie)}${fact('Starts', r.st)}</dl>`
  + `<div class="crs-act"><button type="button" class="rc-save" data-save aria-pressed="${isSaved(r.id)}" aria-label="Save ${esc(r.name)}" title="Save on this device">${BOOKMARK}</button>`
  + `<label class="crs-cmp"><input type="checkbox" data-compare aria-label="Compare ${esc(r.name)}" /> Compare</label>`
  + `<a class="btn ghost" href="${esc(path(r))}">Details</a></div></li>`;

// The university list follows the destination: only universities that have a course here.
const unis = new Map();
for (const r of rows) {
  const x = unis.get(r.uni) || { name: r.uniName, country: r.country, n: 0 };
  x.n += 1;
  unis.set(r.uni, x);
}
function fillUnis(keep) {
  const opts = [...unis].filter(([, x]) => !c.value || x.country === c.value)
    .sort((a, b) => col.compare(a[1].name, b[1].name))
    .map(([slug, x]) => ({ v: slug, l: `${x.name} (${x.n})` }));
  fill(u, [{ v: '', l: 'All universities' }, ...opts], keep && opts.some((x) => x.v === keep) ? keep : '');
}

const SELECTS = [[c, 'c'], [u, 'u'], [l, 'l'], [f, 'f'], [e, 'e'], [m, 'm'], [o, 'o']].filter(([el]) => el);
const CHECKS = [[fee, 'fee'], [ie, 'ie'], [sv, 'sv']];
function readUrl() {
  const p = new URLSearchParams(location.search);
  q.value = p.get('q') || '';
  const set = (el, key) => { const val = p.get(key); if (val && [...el.options].some((op) => op.value === val)) el.value = val; };
  set(c, 'c');
  fillUnis(p.get('u'));
  for (const [el, key] of SELECTS) if (el !== c && el !== u) set(el, key);
  for (const [el, key] of CHECKS) el.checked = p.get(key) === '1';
}
function writeUrl() {
  const p = new URLSearchParams();
  if (q.value) p.set('q', q.value);
  for (const [el, key] of SELECTS) if (el.value && !(el === o && o.value === 'name')) p.set(key, el.value);
  for (const [el, key] of CHECKS) if (el.checked) p.set(key, '1');
  const qs = p.toString();
  history.replaceState(null, '', qs ? `?${qs}` : location.pathname);
}
const filtering = () => Boolean(q.value.trim() || CHECKS.some(([el]) => el.checked) || SELECTS.some(([el]) => el !== o && el.value));

// ---------- compare up to three ----------
const MAX = 3;
const picked = [];
const cmpSec = $('compare'), cmpSay = $('crs-cmp-say'), cmpBox = $('crs-cmp');
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
  const limit = e.value ? Number(e.value) : 0;
  const matches = rows.filter((r) => {
    if (words.length && !words.every((w) => r.search.includes(w))) return false;
    if (c.value && r.country !== c.value) return false;
    if (u.value && r.uni !== u.value) return false;
    if (l.value && r.level !== l.value) return false;
    if (f.value && r.fd !== f.value) return false;
    // A course that does not state a score is kept unless "English score shown" is ticked: we do not guess one.
    if (limit && r.sc !== '' && Number(r.sc) > limit) return false;
    if (ie.checked && r.sc === '') return false;
    if (m && m.value && !r.mo.includes(m.value)) return false;
    if (fee.checked && !r.fe) return false;
    if (sv.checked && !isSaved(r.id)) return false;
    return true;
  });
  matches.sort(sorters[o.value]);
  list.innerHTML = matches.slice(0, shown).map(rowHtml).join('');
  syncBoxes();
  const others = Boolean(words.length || fee.checked || ie.checked || SELECTS.some(([el]) => el !== o && el.value));
  const n = matches.length;
  tally.textContent = n === 0
    ? (sv.checked && !others ? 'Nothing saved yet. Use the bookmark on a course to save it on this device.' : 'No courses match. Try fewer filters.')
    : `${n.toLocaleString('en-GB')} course${n === 1 ? '' : 's'}` + (n > shown ? `, showing ${shown}` : '');
  more.hidden = n <= shown;
  clear.hidden = !filtering();
  const active = SELECTS.filter(([el]) => el !== o && el.value).length + CHECKS.filter(([el]) => el.checked).length;
  fdSum.textContent = active ? `Filters (${active})` : 'Filters';
  writeUrl();
}

let typing;
[q, ...SELECTS.map(([el]) => el), ...CHECKS.map(([el]) => el)].forEach((el) => el.addEventListener(el === q ? 'input' : 'change', () => {
  if (el === c) fillUnis('');   // a new destination: the university list starts again
  if (el === q) {               // wait for a pause in typing so a long list is not rebuilt on every key
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
  ['University', (r) => r.uniName],
  ['Level', (r) => r.lv],
  ['Field', (r) => r.fd || 'Check the official page'],
  ['Length', (r) => r.ln || NOT_STATED],
  ['International fee', (r) => r.fe || NOT_STATED],
  ['English', (r) => r.ie || NOT_STATED],
  ['Starts', (r) => r.st || NOT_STATED],
];
function renderCompare() {
  cmpSec.hidden = picked.length === 0;
  syncBoxes();
  cmpBox.textContent = '';
  if (!picked.length) return;
  cmpSay.textContent = picked.length === 1
    ? 'Tick one or two more courses to line them up. Rows that differ are what should decide it.'
    : `${picked.length} of ${MAX} courses. Rows that differ are in bold. Fees are what each page showed, so they may cover different periods.`;
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
  tr.insertCell().textContent = 'Official page';
  for (const r of picked) {
    const td = tr.insertCell();
    const a = document.createElement('a');
    a.href = path(r);
    a.textContent = 'Course page, with the link to the university';
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
apply(true);
list.hidden = false;
