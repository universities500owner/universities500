// Filters and sort for the scholarship list. The list is already in the page, so this only shows, hides and reorders.
// Status is worked out again here from the dates, so it stays right between site builds.
import { $, fill } from './lib.js';
import { statusOf, scholarshipPill, daysBetween } from '../lib/when.js';
import { wireSaves, isSaved } from './saved.js';

const list = $('sch-list');
const rows = [...list.children];
const q = $('sch-q'), c = $('sch-c'), u = $('sch-u'), l = $('sch-l'), s = $('sch-s'), d = $('sch-d'), v = $('sch-v'), o = $('sch-o'), sv = $('sch-sv'), clear = $('sch-clear'), tally = $('sch-tally'), more = $('sch-more');
const PAGE = 30;
let shown = PAGE;
const pad = (n) => String(n).padStart(2, '0');
const today = (() => { const d = new Date(); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; })();

// Refresh each card's status pill if the date has moved on since the site was built.
for (const r of rows) {
  const st = statusOf(r.dataset, today);
  r.dataset.status = st;
  const pill = r.querySelector('[data-pill]');
  pill.className = `rc-pill rc-${st}`;
  pill.querySelector('[data-pill-text]').textContent = scholarshipPill(r.dataset, st, today);
}

const rank = { open: 0, upcoming: 1, unknown: 2, closed: 3 };
const sorters = {
  status: (a, b) => rank[a.dataset.status] - rank[b.dataset.status]
    || (a.dataset.status === 'closed' ? (b.dataset.deadline || '').localeCompare(a.dataset.deadline || '') : (a.dataset.deadline || '9999').localeCompare(b.dataset.deadline || '9999'))
    || a.dataset.name.localeCompare(b.dataset.name),
  name: (a, b) => a.dataset.name.localeCompare(b.dataset.name),
  country: (a, b) => a.dataset.country.localeCompare(b.dataset.country) || a.dataset.name.localeCompare(b.dataset.name),
  // open scholarships with a deadline, soonest first; the rest after them
  soon: (a, b) => {
    const da = a.dataset.status === 'open' && a.dataset.deadline, db = b.dataset.status === 'open' && b.dataset.deadline;
    return (da ? 0 : 1) - (db ? 0 : 1) || (da || '').localeCompare(db || '') || a.dataset.name.localeCompare(b.dataset.name);
  },
};

// The university list follows the destination: only universities that have a scholarship here.
const unis = new Map();
for (const r of rows) {
  const e = unis.get(r.dataset.provider) || { name: r.dataset.pname, country: r.dataset.country, n: 0 };
  e.n += 1;
  unis.set(r.dataset.provider, e);
}
function fillUnis(keep) {
  const opts = [...unis].filter(([, e]) => !c.value || e.country === c.value)
    .sort((a, b) => a[1].name.localeCompare(b[1].name))
    .map(([slug, e]) => ({ v: slug, l: `${e.name} (${e.n})` }));
  fill(u, [{ v: '', l: 'All universities' }, ...opts], keep && opts.some((x) => x.v === keep) ? keep : '');
}

const FILTERS = [[c, 'c'], [u, 'u'], [l, 'l'], [s, 's'], [d, 'd'], [v, 'v'], [o, 'o']];
function readUrl() {
  const p = new URLSearchParams(location.search);
  q.value = p.get('q') || '';
  const set = (el, key) => { const val = p.get(key); if (val && [...el.options].some((op) => op.value === val)) el.value = val; };
  set(c, 'c');
  fillUnis(p.get('u'));
  for (const [el, key] of FILTERS) if (el !== c && el !== u) set(el, key);
}
function writeUrl() {
  const p = new URLSearchParams();
  if (q.value) p.set('q', q.value);
  for (const [el, key] of FILTERS) if (el.value && !(el === o && o.value === 'status')) p.set(key, el.value);
  const qs = p.toString();
  history.replaceState(null, '', qs ? `?${qs}` : location.pathname);
}
const active = () => Boolean(q.value.trim() || sv.checked || FILTERS.some(([el]) => el !== o && el.value));

// Does the scholarship close within `days` days? Only open scholarships with a deadline on the official page count.
const closesWithin = (r, days) => {
  if (r.dataset.status !== 'open' || !r.dataset.deadline) return false;
  const n = daysBetween(today, r.dataset.deadline);
  return n >= 0 && n <= days;
};

function apply(reset) {
  if (reset) shown = PAGE;
  const term = q.value.trim().toLowerCase();
  const matches = rows.filter((r) =>
    (!term || term.split(/\s+/).every((w) => r.dataset.name.includes(w))) &&
    (!c.value || r.dataset.country === c.value) &&
    (!u.value || r.dataset.provider === u.value) &&
    (!l.value || r.dataset.levels.split(' ').includes(l.value)) &&
    (!s.value || r.dataset.status === s.value) &&
    (!d.value || (d.value === 'none' ? !r.dataset.deadline : closesWithin(r, Number(d.value)))) &&
    (!v.value || r.dataset.vt === v.value) &&
    (!sv.checked || isSaved(r.dataset.id)));
  matches.sort(sorters[o.value]);
  const keep = new Set(matches);
  matches.forEach((r) => list.appendChild(r));
  rows.filter((r) => !keep.has(r)).forEach((r) => { r.hidden = true; list.appendChild(r); });
  matches.forEach((r, i) => { r.hidden = i >= shown; });
  tally.textContent = matches.length === 0
    ? (sv.checked && !q.value.trim() && !FILTERS.some(([el]) => el !== o && el.value) ? 'Nothing saved yet. Use the bookmark on a card to save it on this device.' : 'No scholarships match. Try fewer filters.')
    : `${matches.length} scholarship${matches.length === 1 ? '' : 's'}` + (matches.length > shown ? `, showing ${shown}` : '');
  more.hidden = matches.length <= shown;
  clear.hidden = !active();
  writeUrl();
}

[q, c, u, l, s, d, v, o, sv].forEach((el) => el.addEventListener(el === q ? 'input' : 'change', () => {
  if (el === c) fillUnis('');  // a new destination: the university list starts again
  apply(true);
}));
clear.addEventListener('click', () => {
  q.value = '';
  sv.checked = false;
  for (const [el] of FILTERS) el.value = el === o ? 'status' : '';
  fillUnis('');
  apply(true);
  q.focus();
});
wireSaves(list, () => { if (sv.checked) apply(true); });
more.addEventListener('click', () => { shown += PAGE; apply(false); });
readUrl();
apply(true);
