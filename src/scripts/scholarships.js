// Filters and sort for the scholarship list. The list is already in the page, so this only shows, hides and reorders.
// Status is worked out again here from the dates, so it stays right between site builds.
import { $ } from './lib.js';

const list = $('sch-list');
const rows = [...list.children];
const q = $('sch-q'), c = $('sch-c'), l = $('sch-l'), s = $('sch-s'), o = $('sch-o'), tally = $('sch-tally'), more = $('sch-more');
const PAGE = 30;
let shown = PAGE;
const LABEL = { open: 'Open', closed: 'Closed', upcoming: 'Yet to open', unknown: 'Check the official page' };
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const fmt = (iso) => { const [y, m, d] = iso.split('-').map(Number); return `${d} ${MON[m - 1]} ${y}`; };
const pad = (n) => String(n).padStart(2, '0');
const today = (() => { const d = new Date(); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; })();

function statusOf(r) {
  const { deadline: dl, opens: op, rolling } = r.dataset;
  if (dl && today > dl) return 'closed';
  if (op && today < op) return 'upcoming';
  if (dl || rolling) return 'open';
  return 'unknown';
}

// Refresh each row's status chip if the date has moved on since the site was built.
for (const r of rows) {
  const st = statusOf(r);
  if (st !== r.dataset.status) {
    r.dataset.status = st;
    const chip = r.querySelector('[data-st]');
    chip.className = `st st-${st}`;
    chip.textContent = LABEL[st];
    r.querySelector('[data-stnote]').textContent =
      st === 'closed' ? `Closed ${fmt(r.dataset.deadline)}. Check the official page for the next round.`
      : st === 'upcoming' ? `Opens ${fmt(r.dataset.opens)}`
      : st === 'open' ? (r.dataset.deadline ? `Closes ${fmt(r.dataset.deadline)}` : 'No fixed deadline stated')
      : 'No dates found on the page';
  }
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
    (!s.value || r.dataset.status === s.value));
  matches.sort(sorters[o.value]);
  const keep = new Set(matches);
  matches.forEach((r) => list.appendChild(r));
  rows.filter((r) => !keep.has(r)).forEach((r) => { r.hidden = true; list.appendChild(r); });
  matches.forEach((r, i) => { r.hidden = i >= shown; });
  tally.textContent = matches.length === 0 ? 'No scholarships match. Try fewer filters.' : `${matches.length} scholarship${matches.length === 1 ? '' : 's'}` + (matches.length > shown ? `, showing ${shown}` : '');
  more.hidden = matches.length <= shown;
  writeUrl();
}

[q, c, l, s, o].forEach((el) => el.addEventListener(el === q ? 'input' : 'change', () => apply(true)));
more.addEventListener('click', () => { shown += PAGE; apply(false); });
readUrl();
apply(true);
