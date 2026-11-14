// Filters and sort for the internship list. The list is already in the page, so this only shows, hides and reorders.
import { $ } from './lib.js';
import { internshipPill } from '../lib/when.js';
import { wireSaves, isSaved } from './saved.js';

const list = $('int-list');
const rows = [...list.children];
const q = $('int-q'), c = $('int-c'), k = $('int-k'), o = $('int-o'), n = $('int-n'), sv = $('int-sv'), tally = $('int-tally'), more = $('int-more');
const PAGE = 30;
let shown = PAGE;
const pad = (x) => String(x).padStart(2, '0');
const d = new Date();
const todayIso = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const today = Date.parse(todayIso);
const isNew = (r) => {
  if (!r.dataset.date) return false;
  const age = Math.round((today - Date.parse(r.dataset.date)) / 86400000);
  return age >= 0 && age <= 7;
};
// Keep the "New" badge and the date pill right between site builds.
for (const r of rows) {
  const pill = r.querySelector('[data-pill]');
  if (pill) {
    const p = internshipPill(r.dataset.deadline, r.dataset.date, Boolean(r.dataset.posted), todayIso);
    if (p) { pill.className = `rc-pill rc-${p.tone}`; pill.querySelector('[data-pill-text]').textContent = p.text; }
  }
  const has = r.querySelector('[data-newb]');
  if (isNew(r) && !has) {
    const b = document.createElement('span');
    b.className = 'rc-new';
    b.dataset.newb = '';
    b.textContent = 'New';
    r.querySelector('.rc-head').insertBefore(b, r.querySelector('[data-save]'));
  } else if (!isNew(r) && has) has.remove();
}

const sorters = {
  new: (a, b) => (b.dataset.date || '').localeCompare(a.dataset.date || '') || a.dataset.org.localeCompare(b.dataset.org) || a.dataset.title.localeCompare(b.dataset.title),
  org: (a, b) => a.dataset.org.localeCompare(b.dataset.org) || a.dataset.title.localeCompare(b.dataset.title),
  title: (a, b) => a.dataset.title.localeCompare(b.dataset.title) || a.dataset.org.localeCompare(b.dataset.org),
};

function readUrl() {
  const p = new URLSearchParams(location.search);
  q.value = p.get('q') || '';
  for (const [el, key] of [[c, 'c'], [k, 'k'], [o, 'o']]) {
    const v = p.get(key);
    if (el && v && [...el.options].some((op) => op.value === v)) el.value = v;
  }
  n.checked = p.get('new') === '1';
}
function writeUrl() {
  const p = new URLSearchParams();
  if (q.value) p.set('q', q.value);
  if (c && c.value) p.set('c', c.value);
  if (k.value) p.set('k', k.value);
  if (o.value !== 'new') p.set('o', o.value);
  if (n.checked) p.set('new', '1');
  const qs = p.toString();
  history.replaceState(null, '', qs ? `?${qs}` : location.pathname);
}

function apply(reset) {
  if (reset) shown = PAGE;
  const words = q.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const matches = rows.filter((r) =>
    words.every((w) => r.dataset.name.includes(w)) &&
    (!c || !c.value || r.dataset.country === c.value) &&
    (!k.value || r.dataset.kind === k.value) &&
    (!n.checked || isNew(r)) &&
    (!sv.checked || isSaved(r.dataset.id)));
  matches.sort(sorters[o.value]);
  const keep = new Set(matches);
  matches.forEach((r) => list.appendChild(r));
  rows.filter((r) => !keep.has(r)).forEach((r) => { r.hidden = true; list.appendChild(r); });
  matches.forEach((r, i) => { r.hidden = i >= shown; });
  tally.textContent = matches.length === 0
    ? (sv.checked ? 'Nothing saved yet. Use the bookmark on a card to save it on this device.' : 'No internships match. Try fewer filters.')
    : `${matches.length} internship${matches.length === 1 ? '' : 's'}` + (matches.length > shown ? `, showing ${shown}` : '');
  more.hidden = matches.length <= shown;
  writeUrl();
}

[q, c, k, o, n, sv].filter(Boolean).forEach((el) => el.addEventListener(el === q ? 'input' : 'change', () => apply(true)));
wireSaves(list, () => { if (sv.checked) apply(true); });
more.addEventListener('click', () => { shown += PAGE; apply(false); });
readUrl();
apply(true);
