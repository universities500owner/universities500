// The Search page: shows what was understood and the results, section by section.
// The engine (loading the data, finding things, deciding what the question is about) is in search-core.js,
// which the floating search button shares. Everything runs on this device: the question is never sent anywhere.
import { $ } from './lib.js';
import { load, understand, plan, sample, findCourses, courseLink, schLink, SAMPLE, h, num, plural } from './search-core.js';

const form = $('ss-form'), input = $('ss-q'), tally = $('ss-tally'), says = $('ss-says'), out = $('ss-out');

// ---------- small helpers ----------
const levelName = (lv) => (lv === 'm' ? "Master's" : "Bachelor's");
const ext = (url) => ({ href: url, target: '_blank', rel: 'noopener' });
const row = (link, ...small) => h('li', null, link, h('small', null, small.filter(Boolean).join(' · ')));

// ---------- sections ----------
function coursesSection(u, d, list) {
  const shown = sample(list);
  const unis = new Map();
  for (const c of list) unis.set(c.uni, (unis.get(c.uni) || 0) + 1);
  const hint = [];
  if (u.ielts) hint.push(`Courses that ask for IELTS ${u.ielts} or lower, or do not state a score.`);
  if (u.budget && u.budget.currency) hint.push(`Only courses with a fee stated in ${u.budget.currency} are included. The fee is as the page shows it, often per year.`);
  const sec = h('section', { class: 'ss-sec', 'aria-labelledby': 'ss-h-courses' },
    h('h2', { id: 'ss-h-courses' }, 'Courses ', h('span', { class: 'muted' }, num(list.length))),
    h('p', { class: 'small' }, `${plural(list.length, 'course', 'courses')} at ${plural(unis.size, 'university', 'universities')}, listed A to Z by university. This is not a ranking.`, hint.length ? ` ${hint.join(' ')}` : ''),
    h('ol', { class: 'ss-res' }, shown.map((c) => row(h('a', { href: `/courses/${c.uni}/${c.slug}/` }, c.name), c.uniName, d.cname(c.country), levelName(c.lv), c.ln, c.fe))),
    h('p', null, h('a', { class: 'btn', href: courseLink(u) }, `See all ${num(list.length)} ${plural(list.length, 'course', 'courses').replace(/^[\d,]+ /, '')}`)));
  if (!u.countries.length) {
    const per = new Map();
    for (const c of list) per.set(c.country, (per.get(c.country) || 0) + 1);
    const top = [...per].sort((a, b) => b[1] - a[1]).slice(0, 8);
    if (top.length > 1) {
      sec.append(h('p', { class: 'small ss-narrow-l' }, 'Narrow by country: '), h('ul', { class: 'segs ss-narrow' }, top.map(([code, n]) => h('li', null, h('a', { class: 'seg', href: `/search/?q=${encodeURIComponent(`${u.text} in ${d.cname(code)}`)}` }, d.cname(code), ' ', h('span', { class: 'seg-n' }, num(n)))))));
    }
  }
  return sec;
}
// When nothing fits all of the question, say what would fit if one part were dropped.
function noCoursesSection(u, d) {
  const options = [];
  for (const c of u.chips) {
    const v = understand(u.text, d.lex, new Set([...ignore, c.kind]));
    const n = findCourses(v, d).length;
    if (n > 0) options.push([c, n]);
  }
  return h('section', { class: 'ss-sec', 'aria-labelledby': 'ss-h-courses' },
    h('h2', { id: 'ss-h-courses' }, 'Courses ', h('span', { class: 'muted' }, '0')),
    h('p', null, 'No course matches all of that.', options.length ? ' Drop one part to widen it:' : ' Try fewer words.'),
    options.length ? h('ul', { class: 'segs ss-narrow' }, options.map(([c, n]) => h('li', null, h('button', { type: 'button', class: 'seg', 'data-x': c.kind }, `Remove ${c.label}`, ' ', h('span', { class: 'seg-n' }, plural(n, 'course', 'courses')))))) : null);
}
function scholarshipsSection(u, d, list, label) {
  const shown = list.slice(0, SAMPLE);
  return h('section', { class: 'ss-sec', 'aria-labelledby': 'ss-h-sch' },
    h('h2', { id: 'ss-h-sch' }, 'Scholarships ', h('span', { class: 'muted' }, num(list.length))),
    label ? h('p', { class: 'small' }, label) : null,
    h('ol', { class: 'ss-res' }, shown.map((s) => row(h('a', { href: `/scholarships/${s.slug}/` }, s.name), s.provider, d.cname(s.country), s.value))),
    h('p', null, h('a', { class: 'btn', href: schLink(u) }, `See all ${num(list.length)} in the scholarship search`)));
}
function internshipsSection(u, d, list) {
  const p = new URLSearchParams();
  if (u.countries.length === 1) p.set('c', u.countries[0]);
  if (u.restPlain.length) p.set('q', u.restPlain.join(' '));
  return h('section', { class: 'ss-sec', 'aria-labelledby': 'ss-h-int' },
    h('h2', { id: 'ss-h-int' }, 'Internships ', h('span', { class: 'muted' }, num(list.length))),
    h('p', { class: 'small' }, 'Each opens the employer\'s own page in a new tab.'),
    h('ol', { class: 'ss-res' }, list.slice(0, SAMPLE).map((i) => row(h('a', ext(i.url), i.title), i.org, i.city, d.cname(i.country)))),
    h('p', null, h('a', { class: 'btn', href: `/internships/${p.toString() ? `?${p}` : ''}` }, `See all ${num(list.length)} in the internship search`)));
}
function universitiesSection(u, d, list) {
  return h('section', { class: 'ss-sec', 'aria-labelledby': 'ss-h-uni' },
    h('h2', { id: 'ss-h-uni' }, 'Universities ', h('span', { class: 'muted' }, num(list.length))),
    h('ol', { class: 'ss-res' }, list.slice(0, 10).map((e) => row(h('a', { href: e.u }, e.t), e.d))));
}
function pagesSection(list, extraTop) {
  return h('section', { class: 'ss-sec', 'aria-labelledby': 'ss-h-pg' },
    h('h2', { id: 'ss-h-pg' }, 'Guides and tools ', h('span', { class: 'muted' }, num(list.length + (extraTop ? 1 : 0)))),
    h('ol', { class: 'ss-res' }, extraTop, list.slice(0, 12).map((e) => {
      const a = h('a', { href: e.u });
      a.textContent = e.t;
      if (/^https?:\/\//.test(e.u) && new URL(e.u).origin !== location.origin) { a.target = '_blank'; a.rel = 'noopener'; }
      return h('li', null, a, e.d ? h('small', null, e.d) : null);
    })));
}

// ---------- one search ----------
let ignore = new Set();
const tries = ['masters in nursing in canada', 'data science under 25000 AUD', 'scholarships for engineering in germany', 'bachelor business UK IELTS 6', 'student visa canada'];

function chips(u) {
  says.textContent = '';
  if (u.fixes.length) says.append(h('p', { class: 'ss-fix' }, 'Showing results for ', h('strong', null, u.fixes.map(([, to]) => to).join(', ')), ` instead of "${u.fixes.map(([from]) => from).join('", "')}".`));
  if (u.chips.length) {
    says.append(h('p', { class: 'ss-under' }, 'Understood as: ', h('span', { class: 'segs' }, u.chips.map((c) => h('button', { type: 'button', class: 'seg', 'data-x': c.kind, 'aria-label': `Remove ${c.label}`, title: 'Remove this' }, c.label, ' ', h('span', { class: 'seg-n', 'aria-hidden': 'true' }, '×'))))));
  }
  for (const n of u.notes) says.append(h('p', { class: 'small' }, n));
  if (u.flags.ranking) says.append(h('p', { class: 'small' }, 'We do not rank universities or courses. Results are listed A to Z. Narrow them by level, country, subject, fee or English score instead.'));
}

async function run(q) {
  out.textContent = '';
  says.textContent = '';
  const text = q.trim();
  const topTries = $('ss-try-top');
  if (topTries) topTries.hidden = Boolean(text);   // the examples are for an empty box
  if (!text) { tally.textContent = ''; return; }
  tally.textContent = 'Searching…';
  let d;
  try { d = await load(); } catch (e) { tally.textContent = 'Search could not load. Check your connection and try again.'; return; }
  const P = plan(text, d, ignore);
  const u = P.u;
  chips(u);

  const secs = {};
  const found = [];
  if (P.courses) {
    const list = P.courses.list;
    if (list.length) { secs.courses = coursesSection(u, d, list); found.push(plural(list.length, 'course', 'courses')); }
    else secs.courses = noCoursesSection(u, d);
  }
  if (P.scholarships) { secs.scholarships = scholarshipsSection(u, d, P.scholarships.list, P.scholarships.label); found.push(plural(P.scholarships.list.length, 'scholarship', 'scholarships')); }
  if (P.fundingLine) {
    const list = P.fundingLine;
    secs.fundingLine = h('p', { class: 'ss-more' }, `Looking for funding? `, h('a', { href: schLink({ ...u, restPlain: [] }) }, `${plural(list.length, 'scholarship', 'scholarships')}${u.level ? ` for ${u.level === 'master' ? "Master's" : "Bachelor's"} students` : ''}${u.countries.length === 1 ? ` in ${d.cname(u.countries[0])}` : ''}`));
  }
  if (P.internships) { secs.internships = internshipsSection(u, d, P.internships); found.push(plural(P.internships.length, 'internship', 'internships')); }
  if (P.universities) { secs.universities = universitiesSection(u, d, P.universities); found.push(plural(P.universities.length, 'university', 'universities')); }
  const mbaCard = P.mba ? h('li', null, h('a', { href: `/mba/${u.countries.length === 1 ? `?c=${u.countries[0]}` : ''}` }, 'MBA Explorer'), h('small', null, 'Compare MBA programmes by work experience, fees and English score')) : null;
  if (P.pages.length || mbaCard) { secs.pages = pagesSection(P.pages, mbaCard); found.push(plural(P.pages.length + (mbaCard ? 1 : 0), 'guide or tool', 'guides and tools')); }

  const order = P.order;
  for (const k of order) if (secs[k]) out.append(secs[k]);
  if (secs.fundingLine && !order.includes('fundingLine')) out.append(secs.fundingLine);

  if (!out.children.length) {
    tally.textContent = 'Nothing found.';
    out.append(h('p', null, 'Try a subject, a level and a country, for example:'), h('ul', { class: 'ss-try' }, tries.map((t) => h('li', null, h('a', { href: `/search/?q=${encodeURIComponent(t)}` }, t)))));
  } else {
    tally.textContent = `Found ${found.join(', ')}.`;
  }
}

// ---------- wiring ----------
function go(q, replace = true) {
  const p = new URLSearchParams();
  if (q) p.set('q', q);
  if (ignore.size) p.set('x', [...ignore].join(','));
  try { history[replace ? 'replaceState' : 'pushState'](null, '', p.toString() ? `/search/?${p}` : '/search/'); } catch (e) { /* the address is only for sharing */ }
  run(q);
}
const p0 = new URLSearchParams(location.search);
ignore = new Set((p0.get('x') || '').split(',').filter(Boolean));
input.value = p0.get('q') || '';
if (input.value) run(input.value);
form.addEventListener('submit', (ev) => {
  ev.preventDefault();
  ignore = new Set();   // a new question starts without removed chips
  go(input.value.trim());
});
for (const box of [says, out]) {
  box.addEventListener('click', (ev) => {
    const b = ev.target.closest('[data-x]');
    if (!b) return;
    ignore.add(b.dataset.x);
    go(input.value.trim());
  });
}
