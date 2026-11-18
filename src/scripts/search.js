// Site search that reads a plain question. Everything runs on this device: the question is never sent anywhere.
// src/lib/understand.js turns the question into level, country, subject, budget, IELTS, start month and topics;
// this file finds courses, scholarships, internships, universities and pages that fit, and shows what it understood.
import { $ } from './lib.js';
import { norm, compileLite } from '../lib/subjects.js';
import { buildLexicon, understand } from '../lib/understand.js';

const form = $('ss-form'), input = $('ss-q'), tally = $('ss-tally'), says = $('ss-says'), out = $('ss-out');
const SAMPLE = 8;          // rows shown per section
const PER_UNI = 2;         // at most this many courses from one university in the course sample

// ---------- load once ----------
let ready = null;
const asJson = (r) => { if (!r.ok) throw new Error(r.status); return r.json(); };
function load() {
  if (!ready) {
    ready = Promise.all([fetch('/search-data.json').then(asJson), fetch('/search-index.json').then(asJson)]).then(([data, index]) => {
      const subjects = compileLite(data.S);
      const countries = Object.entries(data.K).map(([code, name]) => ({ code, name }));
      const lex = buildLexicon({ countries, subjects });
      const cname = (code) => data.K[code] || code;
      const courses = data.C.map(([uni, slug, name, lv, years, cur, amt, ie, mo, sj, ln, fe]) => {
        const [uniName, country] = data.U[uni];
        return { uni, slug, name, lv, years, cur, amt, ie, ln, fe, uniName, country, mo: mo ? mo.split(' ') : [], sj: sj ? sj.split(' ').map(Number) : [], hay: norm(`${name} ${uniName} ${cname(country)}`) };
      }).sort((a, b) => a.uniName.localeCompare(b.uniName) || a.name.localeCompare(b.name));
      const schol = data.H.map(([slug, name, provider, country, lv, value]) => ({ slug, name, provider, country, lv, value, hay: norm(`${name} ${provider}`) }));
      const intern = data.I.map(([title, org, city, country, url]) => ({ title, org, city, country, url, hay: norm(`${title} ${org} ${city}`) }));
      const pages = index.map((e) => ({ ...e, _t: norm(e.t), _d: norm(e.d || ''), _k: norm(e.k || '') }));
      return { data, lex, cname, courses, schol, intern, pages, subjects };
    });
  }
  return ready;
}

// ---------- small helpers ----------
function h(tag, props, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v === false || v == null) continue;
    if (k === 'class') el.className = v; else el.setAttribute(k, v === true ? '' : v);
  }
  for (const kid of kids.flat()) if (kid != null && kid !== false) el.append(kid.nodeType ? kid : document.createTextNode(kid));
  return el;
}
const num = (n) => n.toLocaleString('en-GB');
const plural = (n, one, many) => `${num(n)} ${n === 1 ? one : many}`;
const firstPart = (name) => norm(name.split(/ and |, | \(/)[0]);
const levelName = (lv) => (lv === 'm' ? "Master's" : "Bachelor's");
const levelKey = (u) => (u.level === 'master' ? 'm' : 'b');
const ext = (url) => ({ href: url, target: '_blank', rel: 'noopener' });
const row = (link, ...small) => h('li', null, link, h('small', null, small.filter(Boolean).join(' · ')));

// ---------- finding things ----------
function findCourses(u, d) {
  const words = u.restPlain;
  return d.courses.filter((c) => (!u.subject || c.sj.includes(u.subject.index))
    && (!u.level || c.lv === levelKey(u))
    && (!u.countries.length || u.countries.includes(c.country))
    // a course that does not state a score is kept: we do not guess one
    && (!u.ielts || c.ie == null || c.ie <= u.ielts)
    && (!u.month || c.mo.includes(u.month))
    && (!u.budget || !u.budget.currency || (c.cur === u.budget.currency && c.amt > 0 && c.amt <= u.budget.amount))
    && words.every((w) => c.hay.includes(w)));
}
// A readable sample: A to Z by university, never more than PER_UNI from one. Not a ranking.
function sample(list) {
  const per = new Map(); const pick = [];
  for (const c of list) {
    const n = per.get(c.uni) || 0;
    if (n >= PER_UNI) continue;
    per.set(c.uni, n + 1); pick.push(c);
    if (pick.length >= SAMPLE) break;
  }
  return pick;
}
function findScholarships(u, d, loose) {
  const sub = u.subject && !loose ? firstPart(d.subjects.subjects[u.subject.index].name) : '';
  return d.schol.filter((s) => (!u.countries.length || u.countries.includes(s.country))
    && (!u.level || s.lv.includes(levelKey(u)))
    && (!sub || s.hay.includes(sub))
    && u.restPlain.every((w) => s.hay.includes(w)));
}
function findInternships(u, d) {
  return d.intern.filter((i) => (!u.countries.length || u.countries.includes(i.country))
    && (!u.subject || i.hay.includes(firstPart(d.subjects.subjects[u.subject.index].name)))
    && u.restPlain.every((w) => i.hay.includes(w)));
}
function findUniversities(u, d) {
  const names = u.countries.map((c) => d.cname(c));
  return d.pages.filter((e) => e.u.startsWith('/universities/')
    && (!names.length || names.includes(e.d))
    && u.restPlain.every((w) => e._t.includes(w)));
}
function findPages(u, d) {
  const words = [...u.rest];
  for (const c of u.countries) words.push(...norm(d.cname(c)).split(' '));
  if (u.subject) words.push(...firstPart(d.subjects.subjects[u.subject.index].name).split(' '));
  const uniq = [...new Set(words)].filter((w) => w.length > 1);
  if (!uniq.length) return [];
  const pool = d.pages.filter((e) => !e.u.startsWith('/scholarships/') && !e.u.startsWith('/universities/'));
  const score = (e, w) => (e._t.includes(w) ? 5 : 0) + (e._d.includes(w) ? 2 : 0) + (e._k.includes(w) ? 1 : 0);
  const rank = (need) => pool.map((e) => {
    let hit = 0; let s = 0;
    for (const w of uniq) { const x = score(e, w); if (x) hit += 1; s += x; }
    return { e, hit, s };
  }).filter((x) => x.hit >= need).sort((a, b) => b.hit - a.hit || b.s - a.s).map((x) => x.e);
  let res = rank(uniq.length);
  if (!res.length && uniq.length >= 3) res = rank(uniq.length - 1);
  return res;
}

// ---------- links into the tools ----------
function courseLink(u, extra = {}) {
  const p = new URLSearchParams();
  if (u.subject) p.set('s', u.subject.id); else if (u.restPlain.length) p.set('q', u.restPlain.join(' '));
  if (u.level) p.set('l', u.level);
  if (u.countries.length) p.set('c', u.countries.join(','));
  if (u.ielts) p.set('e', String(u.ielts));
  if (u.month) p.set('m', u.month);
  for (const [k, v] of Object.entries(extra)) p.set(k, v);
  return `/courses/?${p}`;
}
const schLink = (u) => {
  const p = new URLSearchParams();
  if (u.countries.length === 1) p.set('c', u.countries[0]);
  if (u.level) p.set('l', u.level);
  if (u.restPlain.length) p.set('q', u.restPlain.join(' '));
  const s = p.toString();
  return s ? `/scholarships/?${s}` : '/scholarships/';
};

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
  const u = understand(text, d.lex, ignore);
  chips(u);

  const topic = new Set(u.topics);
  const wantsFunding = topic.has('scholarship');
  const wantsIntern = topic.has('internship');
  const otherTopic = ['visa', 'loan', 'test', 'mba', 'work', 'cost'].some((t) => topic.has(t));
  const wantCourses = Boolean(u.subject || u.level || u.ielts || u.month || u.budget || u.flags.courses) && !((wantsFunding || wantsIntern) && !u.subject);

  const secs = {};
  const found = [];
  if (wantCourses) {
    const list = findCourses(u, d);
    if (list.length) { secs.courses = coursesSection(u, d, list); found.push(plural(list.length, 'course', 'courses')); }
    else secs.courses = noCoursesSection(u, d);
  } else if (u.restPlain.length && !wantsFunding && !wantsIntern && !otherTopic && !u.countries.length) {
    // no filter words, only names: "leeds" finds that university's courses too
    const list = findCourses(u, d);
    if (list.length) { secs.courses = coursesSection(u, d, list); found.push(plural(list.length, 'course', 'courses')); }
  }
  if (wantsFunding) {
    let list = findScholarships(u, d, false);
    let label = '';
    if (!list.length && u.subject) { list = findScholarships(u, d, true); label = list.length ? `None are named for ${u.subject.name}, so these are for ${u.countries.length ? 'the country' : 'all subjects'} and level you asked about.` : ''; }
    if (list.length) { secs.scholarships = scholarshipsSection(u, d, list, label); found.push(plural(list.length, 'scholarship', 'scholarships')); }
  } else if (wantCourses && (u.countries.length || u.level)) {
    const list = findScholarships({ ...u, subject: null, restPlain: [] }, d, true);
    if (list.length) secs.fundingLine = h('p', { class: 'ss-more' }, `Looking for funding? `, h('a', { href: schLink({ ...u, restPlain: [] }) }, `${plural(list.length, 'scholarship', 'scholarships')}${u.level ? ` for ${u.level === 'master' ? "Master's" : "Bachelor's"} students` : ''}${u.countries.length === 1 ? ` in ${d.cname(u.countries[0])}` : ''}`));
  }
  if (wantsIntern) {
    const list = findInternships(u, d);
    if (list.length) { secs.internships = internshipsSection(u, d, list); found.push(plural(list.length, 'internship', 'internships')); }
  }
  if (!u.subject && !u.level && (u.flags.universities || u.countries.length || u.restPlain.length) && !wantsFunding && !wantsIntern && !otherTopic) {
    const list = findUniversities(u, d);
    if (list.length && (u.flags.universities || u.restPlain.length || u.countries.length)) { secs.universities = universitiesSection(u, d, list); found.push(plural(list.length, 'university', 'universities')); }
  }
  const pages = findPages(u, d);
  const mbaCard = topic.has('mba') ? h('li', null, h('a', { href: `/mba/${u.countries.length === 1 ? `?c=${u.countries[0]}` : ''}` }, 'MBA Explorer'), h('small', null, 'Compare MBA programmes by work experience, fees and English score')) : null;
  if (pages.length || mbaCard) { secs.pages = pagesSection(pages, mbaCard); found.push(plural(pages.length + (mbaCard ? 1 : 0), 'guide or tool', 'guides and tools')); }

  // order: what the question is mostly about first
  const order = wantsFunding ? ['scholarships', 'courses', 'pages', 'universities', 'internships']
    : wantsIntern ? ['internships', 'courses', 'pages', 'universities', 'scholarships']
      : otherTopic ? ['pages', 'courses', 'universities', 'scholarships', 'internships']
        : wantCourses ? ['courses', 'fundingLine', 'pages', 'universities', 'scholarships', 'internships']
          : ['universities', 'courses', 'pages', 'scholarships', 'internships'];
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
