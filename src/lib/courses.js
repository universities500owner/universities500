// Course data for the site. Read from src/data/courses.json, which scripts/courses/build_site_data.py writes from the reader's files.
// Nothing real is shown until src/data/course_publish.json says publish: true; until then /courses/ keeps its placeholder search.
import data from '../data/courses.json';
import gate from '../data/course_publish.json';
import { all, countryName } from './data.js';
import { fmtIso } from './when.js';

export const PUBLISH = gate.publish === true;
export const CHECK = 'Check the official page';
const uniBySlug = new Map(all.map((u) => [u.slug, u]));

// Every course gets its university and destination. A course whose university is not in the list is left out rather than guessed.
export const items = PUBLISH
  ? data.items.filter((i) => uniBySlug.has(i.uni)).map((i) => ({ ...i, country: uniBySlug.get(i.uni).country, uniName: uniBySlug.get(i.uni).name }))
  : [];
export const generatedAt = data.generatedAt;
export const total = items.length;
export const uniOf = (slug) => uniBySlug.get(slug);
export const find = (uni, slug) => items.find((i) => i.uni === uni && i.slug === slug);
export const itemsFor = (uni) => items.filter((i) => i.uni === uni);
export const path = (i) => `/courses/${i.uni}/${i.slug}/`;
export { countryName, fmtIso };

// ---------- how a fact is worded ----------
// The reader keeps the sentence each fact came from. We show the fact as the page gave it and say plainly what the page did not say.
export const levelText = (i) => (i.level === 'Master' ? "Master's" : "Bachelor's") + (i.flags && i.flags.includes('integrated') ? ' (four-year integrated)' : '');
export const NOT_STATED = 'Not stated';
export const lengthText = (i, none = CHECK) => (i.duration ? i.duration.display : none);
// A fee comes with its period only when the page gave one. Without it we do not guess: it may be per year, per term or for the whole course.
export const feeText = (i, none = CHECK) => (i.fee ? i.fee.display : none);
export const feePeriodNote = (i) => (i.fee && !/\ba (?:year|term|semester|month)\b/i.test(i.fee.display) ? 'The page does not say what period this covers.' : '');
// The reader sometimes finds a sentence about IELTS without one clear overall score. That is kept as a quote on the course page, but it is not shown as a score.
export const ieltsScore = (i) => (i.ielts && i.ielts.overall != null ? i.ielts.overall : null);
export const ieltsText = (i, none = CHECK) => (ieltsScore(i) != null ? `IELTS ${ieltsScore(i)} overall` : none);
export const startsText = (i, none = CHECK) => (i.intakes && i.intakes.months && i.intakes.months.length ? i.intakes.months.join(', ') : none);
export const INTL_HOW = {
  cricos: 'The course has a CRICOS code, which means it is registered to take international students.',
  fee: 'The page lists a fee for international students.',
  page: 'The page says international students can apply.',
  university: "The university's own admissions page says it takes international students.",
};

// ---------- the government register entry (Australia) ----------
// data/cricos/ holds the register's Bachelor's and Master's courses. The tuition there is for the whole course and can be older than what the
// university charges now, so it is shown on the course page only, labelled as an older figure. It is never the fee, never on a card, never filtered.
export const REGISTER = data.register || null;
export const regTuitionText = (i) => (i.reg && i.reg.tuition
  ? `AU$${i.reg.tuition.toLocaleString('en-GB')} in total${i.reg.weeks ? ` over ${i.reg.weeks} weeks` : ''}`
  : 'Not published');
export const regPlaces = (i) => (i.reg && i.reg.places ? i.reg.places.map(([city, state]) => (state ? `${city}, ${state}` : city)) : []);
export const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

// ---------- lists for the filters, built from what is actually there ----------
export const filterLists = () => {
  const countries = [...new Set(items.map((i) => i.country))].map((c) => ({ code: c, name: countryName(c) })).sort((a, b) => a.name.localeCompare(b.name));
  const fields = [...new Set(items.map((i) => i.field).filter(Boolean))].sort();
  const months = MONTHS.filter((m) => items.some((i) => i.intakes && i.intakes.months && i.intakes.months.includes(m)));
  return { countries, fields, months };
};
// Universities that have at least one course, for the page that lists them all.
export const universitiesWithCourses = () => {
  const n = new Map();
  for (const i of items) n.set(i.uni, (n.get(i.uni) || 0) + 1);
  return [...n].map(([slug, count]) => ({ u: uniBySlug.get(slug), count })).sort((a, b) => a.u.name.localeCompare(b.u.name));
};
