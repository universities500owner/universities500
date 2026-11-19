// The search engine behind the Search page and the floating search button. Everything runs on this device:
// the question is never sent anywhere. src/lib/understand.js turns the question into level, country, subject,
// budget, IELTS, start month and topics; this file loads the data once, finds courses, scholarships,
// internships, universities and pages that fit, and decides which of them the question is about (plan).
import { norm, compileLite } from '../lib/subjects.js';
import { buildLexicon, understand } from '../lib/understand.js';

export { understand };
export const SAMPLE = 8;          // rows shown per section on the Search page
export const PER_UNI = 2;         // at most this many courses from one university in the course sample

// ---------- load once ----------
let ready = null;
const asJson = (r) => { if (!r.ok) throw new Error(r.status); return r.json(); };
export function load() {
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
    }).catch((e) => { ready = null; throw e; });   // a failed load can be tried again
  }
  return ready;
}

// ---------- small helpers ----------
export function h(tag, props, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v === false || v == null) continue;
    if (k === 'class') el.className = v; else el.setAttribute(k, v === true ? '' : v);
  }
  for (const kid of kids.flat()) if (kid != null && kid !== false) el.append(kid.nodeType ? kid : document.createTextNode(kid));
  return el;
}
export const num = (n) => n.toLocaleString('en-GB');
export const plural = (n, one, many) => `${num(n)} ${n === 1 ? one : many}`;
export const firstPart = (name) => norm(name.split(/ and |, | \(/)[0]);
export const levelKey = (u) => (u.level === 'master' ? 'm' : 'b');

// ---------- finding things ----------
export function findCourses(u, d) {
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
export function sample(list, size = SAMPLE) {
  const per = new Map(); const pick = [];
  for (const c of list) {
    const n = per.get(c.uni) || 0;
    if (n >= PER_UNI) continue;
    per.set(c.uni, n + 1); pick.push(c);
    if (pick.length >= size) break;
  }
  return pick;
}
export function findScholarships(u, d, loose) {
  const sub = u.subject && !loose ? firstPart(d.subjects.subjects[u.subject.index].name) : '';
  return d.schol.filter((s) => (!u.countries.length || u.countries.includes(s.country))
    && (!u.level || s.lv.includes(levelKey(u)))
    && (!sub || s.hay.includes(sub))
    && u.restPlain.every((w) => s.hay.includes(w)));
}
export function findInternships(u, d) {
  return d.intern.filter((i) => (!u.countries.length || u.countries.includes(i.country))
    && (!u.subject || i.hay.includes(firstPart(d.subjects.subjects[u.subject.index].name)))
    && u.restPlain.every((w) => i.hay.includes(w)));
}
export function findUniversities(u, d) {
  const names = u.countries.map((c) => d.cname(c));
  return d.pages.filter((e) => e.u.startsWith('/universities/')
    && (!names.length || names.includes(e.d))
    && u.restPlain.every((w) => e._t.includes(w)));
}
export function findPages(u, d) {
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
export function courseLink(u, extra = {}) {
  const p = new URLSearchParams();
  if (u.subject) p.set('s', u.subject.id); else if (u.restPlain.length) p.set('q', u.restPlain.join(' '));
  if (u.level) p.set('l', u.level);
  if (u.countries.length) p.set('c', u.countries.join(','));
  if (u.ielts) p.set('e', String(u.ielts));
  if (u.month) p.set('m', u.month);
  for (const [k, v] of Object.entries(extra)) p.set(k, v);
  return `/courses/?${p}`;
}
export const schLink = (u) => {
  const p = new URLSearchParams();
  if (u.countries.length === 1) p.set('c', u.countries[0]);
  if (u.level) p.set('l', u.level);
  if (u.restPlain.length) p.set('q', u.restPlain.join(' '));
  const s = p.toString();
  return s ? `/scholarships/?${s}` : '/scholarships/';
};

// ---------- what the question is about ----------
// Returns what was found for each kind of result and the order to show them in. Rendering is left to the caller.
//   courses: { list } when courses are wanted (an empty list means "nothing fits all of it"), or null
//   scholarships: { list, label } or null; fundingLine: list of scholarships for a one-line pointer, or null
//   internships, universities: list or null; pages: list; mba: true when the question is about MBAs
export function plan(text, d, ignore = new Set()) {
  const u = understand(text, d.lex, ignore);
  const topic = new Set(u.topics);
  const wantsFunding = topic.has('scholarship');
  const wantsIntern = topic.has('internship');
  const otherTopic = ['visa', 'loan', 'test', 'mba', 'work', 'cost'].some((t) => topic.has(t));
  const wantCourses = Boolean(u.subject || u.level || u.ielts || u.month || u.budget || u.flags.courses) && !((wantsFunding || wantsIntern) && !u.subject);

  const P = { u, courses: null, scholarships: null, fundingLine: null, internships: null, universities: null, pages: [], mba: topic.has('mba') };
  if (wantCourses) {
    P.courses = { list: findCourses(u, d) };
  } else if (u.restPlain.length && !wantsFunding && !wantsIntern && !otherTopic && !u.countries.length) {
    // no filter words, only names: "leeds" finds that university's courses too
    const list = findCourses(u, d);
    if (list.length) P.courses = { list };
  }
  if (wantsFunding) {
    let list = findScholarships(u, d, false);
    let label = '';
    if (!list.length && u.subject) { list = findScholarships(u, d, true); label = list.length ? `None are named for ${u.subject.name}, so these are for ${u.countries.length ? 'the country' : 'all subjects'} and level you asked about.` : ''; }
    if (list.length) P.scholarships = { list, label };
  } else if (wantCourses && (u.countries.length || u.level)) {
    const list = findScholarships({ ...u, subject: null, restPlain: [] }, d, true);
    if (list.length) P.fundingLine = list;
  }
  if (wantsIntern) {
    const list = findInternships(u, d);
    if (list.length) P.internships = list;
  }
  if (!u.subject && !u.level && (u.flags.universities || u.countries.length || u.restPlain.length) && !wantsFunding && !wantsIntern && !otherTopic) {
    const list = findUniversities(u, d);
    if (list.length && (u.flags.universities || u.restPlain.length || u.countries.length)) P.universities = list;
  }
  P.pages = findPages(u, d);

  // order: what the question is mostly about first
  P.order = wantsFunding ? ['scholarships', 'courses', 'pages', 'universities', 'internships']
    : wantsIntern ? ['internships', 'courses', 'pages', 'universities', 'scholarships']
      : otherTopic ? ['pages', 'courses', 'universities', 'scholarships', 'internships']
        : wantCourses ? ['courses', 'fundingLine', 'pages', 'universities', 'scholarships', 'internships']
          : ['universities', 'courses', 'pages', 'scholarships', 'internships'];
  return P;
}
