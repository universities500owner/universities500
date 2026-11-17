// MBA Explorer data. Read from src/data/mba.json, which holds one record per programme. Every record carries the school's own page and the date it was read.
// Nothing is shown until src/data/mba_publish.json says publish: true. A fact the school's page did not state is shown as "Not stated", never estimated.
import data from '../data/mba.json';
import gate from '../data/mba_publish.json';
import { all, countryName } from './data.js';
import { fmtIso } from './when.js';

export const PUBLISH = gate.publish === true;
export const NOT_STATED = 'Not stated';
const uniBySlug = new Map(all.map((u) => [u.slug, u]));

export const items = PUBLISH ? data.items : [];
export const generatedAt = data.generatedAt;
export const find = (id) => items.find((i) => i.id === id);
export const path = (i) => `/mba/${i.id}/`;
export const uniKnown = (i) => uniBySlug.has(i.uni);
export { countryName, fmtIso };

// ---------- the three tracks ----------
// A track is decided from the minimum work experience the school's page states, never from our own view of the programme.
//   Freshers and early career: master's programmes for recent graduates, deferred MBAs, and MBAs that state a minimum of two years or less.
//   3 to 5 years: MBAs whose stated minimum is five years or less, or that state none.
//   Executive MBA: Executive MBAs, and MBAs that state a minimum above five years.
// An MBA that asks for exactly two years is in both of the first two lists. The card says "Minimum 2 years" so nobody mistakes it for a pre-experience degree.
export const TRACKS = [
  { id: 'fresher', label: 'Freshers and early career', years: '0 to 2 years of experience', blurb: "Master's programmes for recent graduates, deferred MBAs, and MBAs that ask for two years or less. A programme that asks for two years is also in the next list." },
  { id: 'mid', label: '3 to 5 years', years: 'of work experience', blurb: 'Full-time MBAs for people with a few years of work behind them, including schools that state no minimum.' },
  { id: 'exec', label: 'Executive MBA', years: '5 or more years of experience', blurb: 'Part-time and modular programmes for managers, where you keep working while you study.' },
];
export const tracksOf = (i) => {
  if (i.kind === 'emba') return ['exec'];
  if (i.kind === 'mim' || i.kind === 'deferred') return ['fresher'];
  const min = i.exp && i.exp.min != null ? i.exp.min : null;
  if (min !== null && min > 5) return ['exec'];
  return min !== null && min <= 2 ? ['fresher', 'mid'] : ['mid'];
};
export const KIND = {
  mba: 'MBA',
  mim: "Master's in management",
  deferred: 'Deferred MBA',
  emba: 'Executive MBA',
};
export const KIND_NOTE = {
  mim: 'A pre-experience master’s degree. It is not an MBA.',
  deferred: 'You apply now and start the MBA after a few years of work.',
};
export const expChip = (i) => {
  const min = i.exp && i.exp.min != null ? i.exp.min : null;
  if (i.kind === 'mim' || i.kind === 'deferred') return min === 0 ? 'No work experience needed' : null;
  if (min === null) return null;
  return min === 0 ? 'No minimum experience' : `Minimum ${min} year${min === 1 ? '' : 's'}`;
};

// ---------- how a fact is worded ----------
export const val = (f, none = NOT_STATED) => (f && f.t ? f.t : none);
export const feeCard = (i) => (i.fee ? i.fee.t : NOT_STATED);

// ---------- lists for the filters, built from what is actually there ----------
export const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
export const filterLists = () => ({
  countries: [...new Set(items.map((i) => i.country))].map((c) => ({ code: c, name: countryName(c) })).sort((a, b) => a.name.localeCompare(b.name)),
  months: MONTHS.filter((m) => items.some((i) => i.start && i.start.months && i.start.months.includes(m))),
  kinds: Object.keys(KIND).filter((k) => items.some((i) => i.kind === k)).map((k) => ({ id: k, label: KIND[k] })),
});
export const trackCount = (id) => items.filter((i) => tracksOf(i).includes(id)).length;
