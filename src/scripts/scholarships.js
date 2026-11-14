// Filters and sort for the scholarship list. The list is already in the page, so this only shows, hides and reorders.
// Status is worked out again here from the dates, so it stays right between site builds.
import { $ } from './lib.js';
import { statusOf, scholarshipPill } from '../lib/when.js';
import { wireSaves, isSaved } from './saved.js';

const list = $('sch-list');
const rows = [...list.children];
const q = $('sch-q'), c = $('sch-c'), l = $('sch-l'), s = $('sch-s'), o = $('sch-o'), sv = $('sch-sv'), tally = $('sch-tally'), more = $('sch-more');
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
};

function readUrl() {
  const p = new URLSearchParams(location.search);
  q.value = p.get('q') || '';
  for (const [el, k] of [[c, 'c'], [l, 'l'], [s, 's'], [o, 'o']]) {
    const v = p.get(k);
    if (v && [...el.options].some((op) => op.value === v)) el.value = v;
  }
}
function writeUrl() {
  const p = new URLSearchParams();
  if (q.value) p.set('q', q.value);
  if (c.value) p.set('c', c.value);
  if (l.value) p.set('l', l.value);
  if (s.value) p.set('s', s.value);
  if (o.value !== 'status') p.set('o', o.value);
  const qs = p.toString();
  history.replaceState(null, '', qs ? `?${qs}` : location.pathname);
}

function apply(reset) {
  if (reset) shown = PAGE;
  const term = q.value.trim().toLowerCase();
  const matches = rows.filter((r) =>
    (!term || term.split(/\s+/).every((w) => r.dataset.name.includes(w))) &&
    (!c.value || r.dataset.country === c.value) &&
    (!l.value || r.dataset.levels.split(' ').includes(l.value)) &&
    (!s.value || r.dataset.status === s.value) &&
    (!sv.checked || isSaved(r.dataset.id)));
  matches.sort(sorters[o.value]);
  const keep = new Set(matches);
  matches.forEach((r) => list.appendChild(r));
  rows.filter((r) => !keep.has(r)).forEach((r) => { r.hidden = true; list.appendChild(r); });
  matches.forEach((r, i) => { r.hidden = i >= shown; });
  tally.textContent = matches.length === 0 ? (sv.checked ? 'Nothing saved yet. Use the bookmark on a card to save it on this device.' : 'No scholarships match. Try fewer filters.') : `${matches.length} scholarship${matches.length === 1 ? '' : 's'}` + (matches.length > shown ? `, showing ${shown}` : '');
  more.hidden = matches.length <= shown;
  writeUrl();
}

[q, c, l, s, o, sv].forEach((el) => el.addEventListener(el === q ? 'input' : 'change', () => apply(true)));
wireSaves(list, () => { if (sv.checked) apply(true); });
more.addEventListener('click', () => { shown += PAGE; apply(false); });
readUrl();
apply(true);
