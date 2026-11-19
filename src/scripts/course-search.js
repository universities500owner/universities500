// Subject, level, countries and the other filters for the course list, plus compare.
// The page holds every course as compact data (#crs-data) and only the first rows as HTML. This script filters the data
// and builds the rows a visitor can see, so a long list does not mean a heavy page. Nothing is sent anywhere: saved courses stay in this browser.
import { $, fill } from './lib.js';
import { wireSaves, isSaved } from './saved.js';
import { exactSubject, suggestSubjects, compileLite } from '../lib/subjects.js';

const list = $('crs-list');
const q = $('crs-q'), u = $('crs-u'), f = $('crs-f'), e = $('crs-e'), m = $('crs-m'), o = $('crs-o');
const lvBox = $('crs-l'), cBox = $('crs-c'), say = $('crs-say'), pop = document.querySelector('.subj-pop');
const fee = $('crs-fee'), ie = $('crs-ie'), sv = $('crs-sv'), clear = $('crs-clear'), tally = $('crs-tally'), more = $('crs-more');
const fd = $('crs-fd'), fdSum = $('crs-fd-sum');
const unisBy = $('crs-unis-by'), unisByList = $('crs-unis-list'), unisBySum = $('crs-unis-sum');
const PAGE = 30;
const NOT_STATED = 'Not stated';
let shown = PAGE;
let level = '';               // '' (any), 'bachelor' or 'master'
const countries = new Set();  // empty means all countries

// ---------- the data ----------
const data = JSON.parse($('crs-data').textContent);
const BOOKMARK = $('crs-bookmark').innerHTML;
// Subjects: the same words the site used to give each course its subjects. `alias` is what a visitor can type to name one.
const compiled = compileLite(data.S.map(([id, name, , also]) => [id, name, also]));
const rows = data.C.map(([uni, slug, name, degree, lv, level, field, ln, years, feeText, ieText, score, st, months, sjs]) => {
  const [uniName, country] = data.U[uni];
  const countryName = data.K[country] || country;
  return {
    id: `crs:${uni}/${slug}`, uni, slug, name, lv, level, fd: field, ln, years, fe: feeText, ie: ieText, sc: score, st,
    mo: months ? months.split(' ') : [], sj: sjs ? sjs.split(' ').map(Number) : [], uniName, country, countryName,
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
  + `<div class="crs-meta"><p class="crs-where"><a href="/universities/${esc(r.uni)}/">${esc(r.uniName)}</a><span class="crs-ctry"><span aria-hidden="true"> · </span>${esc(r.countryName)}</span></p>`
  + `<ul class="crs-tags" aria-label="About this course"><li>${esc(r.lv)}</li>${r.fd ? `<li>${esc(r.fd)}</li>` : ''}</ul></div>`
  + `<dl class="crs-facts">${fact('Duration', r.ln)}<div><dt title="Fee for international students">Fees</dt><dd${r.fe ? '' : ' class="none"'}>${esc(r.fe || NOT_STATED)}</dd></div>${fact('Intakes', r.st)}</dl></div>`
  + `<div class="crs-act"><a class="btn" href="${esc(path(r))}">Details</a>`
  + `<button type="button" class="rc-save" data-save aria-pressed="${isSaved(r.id)}" aria-label="Shortlist ${esc(r.name)}" title="Shortlist on this device">${BOOKMARK}<span class="rc-save-t"><span class="t-off">Shortlist</span><span class="t-on">Shortlisted</span></span></button>`
  + `<label class="crs-cmp"><input type="checkbox" data-compare aria-label="Compare ${esc(r.name)}" /> Compare</label></div></li>`;

// The university list follows the destinations: only universities that have a course in the chosen countries.
const unis = new Map();
for (const r of rows) {
  const x = unis.get(r.uni) || { name: r.uniName, country: r.country, n: 0 };
  x.n += 1;
  unis.set(r.uni, x);
}
function fillUnis(keep) {
  const opts = [...unis].filter(([, x]) => !countries.size || countries.has(x.country))
    .sort((a, b) => col.compare(a[1].name, b[1].name))
    .map(([slug, x]) => ({ v: slug, l: `${x.name} (${x.n})` }));
  fill(u, [{ v: '', l: 'All universities' }, ...opts], keep && opts.some((x) => x.v === keep) ? keep : '');
}

// ---------- subject, level and countries ----------
const lvBtns = [...lvBox.querySelectorAll('[data-level]')];
const cBtns = [...cBox.querySelectorAll('[data-country]')];
const popBtns = [...pop.querySelectorAll('[data-subject]')];
const subjectName = (id) => (compiled.subjects.find((s) => s.id === id) || {}).name || '';
const press = (btn, on) => btn.setAttribute('aria-pressed', on ? 'true' : 'false');
const setLevel = (v) => { level = v === 'bachelor' || v === 'master' ? v : ''; lvBtns.forEach((b) => press(b, b.dataset.level === level)); };
const setCountries = (list) => {
  countries.clear();
  list.filter((x) => cBtns.some((b) => b.dataset.country === x)).forEach((x) => countries.add(x));
  cBtns.forEach((b) => press(b, b.dataset.country ? countries.has(b.dataset.country) : !countries.size));
};

const SELECTS = [[u, 'u'], [f, 'f'], [e, 'e'], [m, 'm'], [o, 'o']].filter(([el]) => el);
const CHECKS = [[fee, 'fee'], [ie, 'ie'], [sv, 'sv']];
function readUrl() {
  const p = new URLSearchParams(location.search);
  const s = p.get('s');
  q.value = s && subjectName(s) ? subjectName(s) : (p.get('q') || '');
  setLevel(p.get('l') || '');
  setCountries((p.get('c') || '').split(',').filter(Boolean));
  fillUnis(p.get('u'));
  const set = (el, key) => { const val = p.get(key); if (val && [...el.options].some((op) => op.value === val)) el.value = val; };
  for (const [el, key] of SELECTS) if (el !== u) set(el, key);
  for (const [el, key] of CHECKS) el.checked = p.get(key) === '1';
}
function writeUrl(subject) {
  const p = new URLSearchParams();
  if (subject) p.set('s', subject.id); else if (q.value.trim()) p.set('q', q.value.trim());
  if (level) p.set('l', level);
  if (countries.size) p.set('c', [...countries].join(','));
  for (const [el, key] of SELECTS) if (el.value && !(el === o && o.value === 'name')) p.set(key, el.value);
  for (const [el, key] of CHECKS) if (el.checked) p.set(key, '1');
  const qs = p.toString();
  history.replaceState(null, '', qs ? `?${qs}` : location.pathname);
}
const filtering = () => Boolean(q.value.trim() || level || countries.size || CHECKS.some(([el]) => el.checked) || SELECTS.some(([el]) => el !== o && el.value));

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
  const subject = exactSubject(compiled, q.value);
  const words = subject ? [] : q.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const limit = e.value ? Number(e.value) : 0;
  // Everything except level and countries first: the level and country buttons show how many courses each choice would leave.
  const base = rows.filter((r) => {
    if (subject && !r.sj.includes(subject.index)) return false;
    if (words.length && !words.every((w) => r.search.includes(w))) return false;
    if (u.value && r.uni !== u.value) return false;
    if (f.value && r.fd !== f.value) return false;
    // A course that does not state a score is kept unless "English score shown" is ticked: we do not guess one.
    if (limit && r.sc !== '' && Number(r.sc) > limit) return false;
    if (ie.checked && r.sc === '') return false;
    if (m && m.value && !r.mo.includes(m.value)) return false;
    if (fee.checked && !r.fe) return false;
    if (sv.checked && !isSaved(r.id)) return false;
    return true;
  });
  const inLevel = (r) => !level || r.level === level;
  const inCountry = (r) => !countries.size || countries.has(r.country);
  const matches = base.filter((r) => inLevel(r) && inCountry(r));
  matches.sort(sorters[o.value]);
  list.innerHTML = matches.slice(0, shown).map(rowHtml).join('');
  syncBoxes();

  // counts on the buttons
  const nLevel = { '': 0, bachelor: 0, master: 0 };
  for (const r of base) if (inCountry(r)) { nLevel[''] += 1; nLevel[r.level] += 1; }
  lvBtns.forEach((b) => { const n = nLevel[b.dataset.level]; const s = b.querySelector('.seg-n'); if (s) s.textContent = n.toLocaleString('en-GB'); b.dataset.n = n; });
  const nCountry = new Map();
  for (const r of base) if (inLevel(r)) nCountry.set(r.country, (nCountry.get(r.country) || 0) + 1);
  cBtns.forEach((b) => {
    if (!b.dataset.country) return;
    const n = nCountry.get(b.dataset.country) || 0;
    b.querySelector('.seg-n').textContent = n.toLocaleString('en-GB');
    b.dataset.n = n;
  });
  popBtns.forEach((b) => press(b, Boolean(subject && subject.id === b.dataset.subject)));

  // what the search understood, in plain words
  say.textContent = '';
  if (subject) {
    say.textContent = 'Matched on course titles. A course can sit in more than one subject, and nothing is ranked.';
  } else if (words.length) {
    const near = suggestSubjects(compiled, q.value.trim(), 4);
    say.append(`No subject is called "${q.value.trim()}", so this looks for those words in course, university and country names.`);
    if (near.length) {
      say.append(' Did you mean ');
      near.forEach((s, i) => {
        const b = document.createElement('button');
        b.type = 'button'; b.className = 'subj-link'; b.dataset.subject = s.id; b.textContent = s.name;
        say.append(b, i < near.length - 1 ? ', ' : '?');
      });
    }
  } else {
    say.textContent = 'Pick a subject to narrow the list, or leave it empty to see every course.';
  }

  // universities that teach this subject: a way to compare places without ranking them
  if (subject || words.length) {
    const per = new Map();
    for (const r of matches) { const x = per.get(r.uni) || { name: r.uniName, country: r.countryName, n: 0 }; x.n += 1; per.set(r.uni, x); }
    const arr = [...per].sort((a, b) => b[1].n - a[1].n || col.compare(a[1].name, b[1].name));
    unisBy.hidden = arr.length < 2;
    unisBySum.textContent = `${arr.length} universities have these courses`;
    unisByList.textContent = '';
    for (const [slug, x] of arr) {
      const li = document.createElement('li');
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'seg'; b.dataset.uni = slug;
      b.setAttribute('aria-pressed', u.value === slug ? 'true' : 'false');
      b.textContent = `${x.name} `;
      const n = document.createElement('span'); n.className = 'seg-n'; n.textContent = `${x.country} · ${x.n}`;
      b.append(n); li.append(b); unisByList.append(li);
    }
  } else {
    unisBy.hidden = true;
  }

  const others = Boolean(words.length || subject || level || countries.size || fee.checked || ie.checked || SELECTS.some(([el]) => el !== o && el.value));
  const n = matches.length;
  const what = subject ? ` in ${subject.name}` : '';
  tally.textContent = n === 0
    ? (sv.checked && !others ? 'Nothing saved yet. Use the bookmark on a course to save it on this device.' : 'No courses match. Try fewer filters or another country.')
    : `${n.toLocaleString('en-GB')} course${n === 1 ? '' : 's'}${what}` + (n > shown ? `, showing ${shown}` : '');
  more.hidden = n <= shown;
  clear.hidden = !filtering();
  const active = SELECTS.filter(([el]) => el !== o && el.value).length + CHECKS.filter(([el]) => el.checked).length;
  fdSum.textContent = active ? `More filters (${active})` : 'More filters';
  writeUrl(subject);
}

let typing;
q.addEventListener('input', () => {   // wait for a pause in typing so a long list is not rebuilt on every key
  clearTimeout(typing);
  typing = setTimeout(() => apply(true), 150);
});
q.addEventListener('change', () => { clearTimeout(typing); apply(true); });
[...SELECTS.map(([el]) => el), ...CHECKS.map(([el]) => el)].forEach((el) => el.addEventListener('change', () => apply(true)));
lvBox.addEventListener('click', (ev) => {
  const b = ev.target.closest('[data-level]');
  if (!b) return;
  setLevel(b.dataset.level);
  apply(true);
});
cBox.addEventListener('click', (ev) => {
  const b = ev.target.closest('[data-country]');
  if (!b) return;
  if (!b.dataset.country) countries.clear();
  else if (countries.has(b.dataset.country)) countries.delete(b.dataset.country);
  else countries.add(b.dataset.country);
  setCountries([...countries]);
  fillUnis(u.value);   // the university list starts again from the chosen countries
  apply(true);
});
// A subject button: the popular row, a "did you mean" link, or a university button under the tally.
document.addEventListener('click', (ev) => {
  const sb = ev.target.closest('[data-subject]');
  if (sb && (pop.contains(sb) || say.contains(sb))) {
    clearTimeout(typing);
    q.value = sb.getAttribute('aria-pressed') === 'true' ? '' : subjectName(sb.dataset.subject);
    apply(true);
    return;
  }
  const ub = ev.target.closest('[data-uni]');
  if (ub && unisByList.contains(ub)) {
    u.value = u.value === ub.dataset.uni ? '' : ub.dataset.uni;
    apply(true);
  }
});
clear.addEventListener('click', () => {
  clearTimeout(typing);
  q.value = '';
  setLevel('');
  setCountries([]);
  for (const [el] of CHECKS) el.checked = false;
  for (const [el] of SELECTS) if (el !== u) el.value = el === o ? 'name' : '';
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

// The finer filters stay folded so the first result is not far down the page; they open when a link already uses one.
readUrl();
fd.open = SELECTS.some(([el]) => el !== o && el.value) || CHECKS.some(([el]) => el.checked);
apply(true);
list.hidden = false;
