// Filters, sort and compare for the course list. The list is already in the page, so this only shows, hides and reorders.
// Nothing is sent anywhere: saved courses stay in this browser.
import { $, fill } from './lib.js';
import { wireSaves, isSaved } from './saved.js';

const list = $('crs-list');
const rows = [...list.children];
const q = $('crs-q'), c = $('crs-c'), u = $('crs-u'), l = $('crs-l'), f = $('crs-f'), e = $('crs-e'), m = $('crs-m'), o = $('crs-o');
const fee = $('crs-fee'), ie = $('crs-ie'), sv = $('crs-sv'), clear = $('crs-clear'), tally = $('crs-tally'), more = $('crs-more');
const fd = $('crs-fd'), fdSum = $('crs-fd-sum');
const PAGE = 30;
let shown = PAGE;

const byName = (a, b) => a.dataset.name.localeCompare(b.dataset.name) || a.dataset.uniname.localeCompare(b.dataset.uniname);
const sorters = {
  name: byName,
  uni: (a, b) => a.dataset.uniname.localeCompare(b.dataset.uniname) || byName(a, b),
  country: (a, b) => a.dataset.country.localeCompare(b.dataset.country) || a.dataset.uniname.localeCompare(b.dataset.uniname) || byName(a, b),
  // a course with no stated length goes last: we do not guess it
  short: (a, b) => (a.dataset.years ? Number(a.dataset.years) : 99) - (b.dataset.years ? Number(b.dataset.years) : 99) || byName(a, b),
};

// The university list follows the destination: only universities that have a course here.
const unis = new Map();
for (const r of rows) {
  const x = unis.get(r.dataset.uni) || { name: r.dataset.uniname, country: r.dataset.country, n: 0 };
  x.n += 1;
  unis.set(r.dataset.uni, x);
}
function fillUnis(keep) {
  const opts = [...unis].filter(([, x]) => !c.value || x.country === c.value)
    .sort((a, b) => a[1].name.localeCompare(b[1].name))
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

function apply(reset) {
  if (reset) shown = PAGE;
  const words = q.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const limit = e.value ? Number(e.value) : 0;
  const matches = rows.filter((r) => {
    const d = r.dataset;
    if (words.length && !words.every((w) => d.search.includes(w))) return false;
    if (c.value && d.country !== c.value) return false;
    if (u.value && d.uni !== u.value) return false;
    if (l.value && d.level !== l.value) return false;
    if (f.value && d.field !== f.value) return false;
    // A course that does not state a score is kept unless "English score shown" is ticked: we do not guess one.
    if (limit && d.ielts && Number(d.ielts) > limit) return false;
    if (ie.checked && !d.ielts) return false;
    if (m && m.value && !d.months.split(' ').includes(m.value)) return false;
    if (fee.checked && !d.fee) return false;
    if (sv.checked && !isSaved(d.id)) return false;
    return true;
  });
  matches.sort(sorters[o.value]);
  const keep = new Set(matches);
  matches.forEach((r) => list.appendChild(r));
  rows.filter((r) => !keep.has(r)).forEach((r) => { r.hidden = true; list.appendChild(r); });
  matches.forEach((r, i) => { r.hidden = i >= shown; });
  const others = Boolean(words.length || fee.checked || ie.checked || SELECTS.some(([el]) => el !== o && el.value));
  tally.textContent = matches.length === 0
    ? (sv.checked && !others ? 'Nothing saved yet. Use the bookmark on a course to save it on this device.' : 'No courses match. Try fewer filters.')
    : `${matches.length} course${matches.length === 1 ? '' : 's'}` + (matches.length > shown ? `, showing ${shown}` : '');
  more.hidden = matches.length <= shown;
  clear.hidden = !filtering();
  const n = SELECTS.filter(([el]) => el !== o && el.value).length + CHECKS.filter(([el]) => el.checked).length;
  fdSum.textContent = n ? `Filters (${n})` : 'Filters';
  writeUrl();
}

[q, ...SELECTS.map(([el]) => el), ...CHECKS.map(([el]) => el)].forEach((el) => el.addEventListener(el === q ? 'input' : 'change', () => {
  if (el === c) fillUnis('');   // a new destination: the university list starts again
  apply(true);
}));
clear.addEventListener('click', () => {
  q.value = '';
  for (const [el] of CHECKS) el.checked = false;
  for (const [el] of SELECTS) el.value = el === o ? 'name' : '';
  fillUnis('');
  apply(true);
  q.focus();
});
more.addEventListener('click', () => { shown += PAGE; apply(false); });
wireSaves(list, () => { if (sv.checked) apply(true); });

// ---------- compare up to three ----------
const MAX = 3;
const picked = [];
const cmpSec = $('compare'), cmpSay = $('crs-cmp-say'), cmpBox = $('crs-cmp');
const cell = (r, sel) => (r.querySelector(sel) ? r.querySelector(sel).textContent.trim() : '');
const FACTS = [
  ['University', (r) => r.dataset.uniname],
  ['Level', (r) => cell(r, '.crs-tags li')],
  ['Field', (r) => r.dataset.field || 'Check the official page'],
  ['Length', (r) => cell(r, '.crs-facts div:nth-child(1) dd')],
  ['International fee', (r) => cell(r, '.crs-facts div:nth-child(2) dd')],
  ['English', (r) => cell(r, '.crs-facts div:nth-child(3) dd')],
  ['Starts', (r) => cell(r, '.crs-facts div:nth-child(4) dd')],
];
function renderCompare() {
  cmpSec.hidden = picked.length === 0;
  list.querySelectorAll('[data-compare]').forEach((cb) => {
    const r = cb.closest('.crs');
    cb.checked = picked.includes(r);
    cb.disabled = !cb.checked && picked.length >= MAX;
  });
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
    a.href = r.querySelector('.crs-title a').href;
    a.textContent = r.querySelector('.crs-title a').textContent;
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
    a.href = r.querySelector('.crs-title a').href;
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
  const r = cb.closest('.crs');
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
