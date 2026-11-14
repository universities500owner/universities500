// Internship data for the site. Read from src/data/internships.json, which the GitHub Action refreshes every day.
// Nothing is listed until src/data/internship_publish.json says publish: true.
import data from '../data/internships.json';
import gate from '../data/internship_publish.json';
import { countries, countryName } from './data.js';
import { fmtIso } from './scholarships.js';

export const PUBLISH = gate.publish === true;
export const generatedAt = data.generatedAt;
export const portals = (data.portals || []).filter((p) => p.ok);
export { countryName, fmtIso };

export const KIND_SLUG = { Internship: 'internship', 'Co-op': 'coop', Placement: 'placement', 'Working student': 'working' };
export const KIND_LABEL = { internship: 'Internship', coop: 'Co-op', placement: 'Placement', working: 'Working student' };

// Our own first run lists everything at once, so "first seen" on that day says nothing about how new a posting is.
const baseline = (data.items || []).reduce((m, i) => (!m || i.firstSeen < m ? i.firstSeen : m), '');
export const effDate = (i) => i.posted || (i.firstSeen && i.firstSeen !== baseline ? i.firstSeen : '');

const raw = PUBLISH ? data.items : [];
export const items = [...raw].sort(
  (a, b) => (effDate(b) || '').localeCompare(effDate(a) || '') || a.org.localeCompare(b.org) || a.title.localeCompare(b.title),
);

export const forCountry = (code) => items.filter((i) => i.country === code);
export const counts = Object.fromEntries(countries.map((c) => [c.code, forCountry(c.code).length]));
export const portalsFor = (code) => portals.filter((p) => p.countries.includes(code) || p.countries.includes('all'));

export function daysAgo(iso, todayIso) {
  if (!iso) return null;
  return Math.round((Date.parse(todayIso) - Date.parse(iso)) / 86400000);
}
export const isNew = (i, todayIso) => {
  const d = daysAgo(effDate(i), todayIso);
  return d !== null && d >= 0 && d <= 7;
};

export const initials = (org) =>
  (org || '?')
    .replace(/\(.*?\)/g, '')
    .split(/[\s.\-&]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0].toUpperCase())
    .join('') || '?';
export const hue = (s) => [...(s || '')].reduce((h, c) => (h * 31 + c.charCodeAt(0)) % 360, 7);

export const ATTRIBUTION = {
  jobtech: "Swedish job ads come from Arbetsförmedlingen's JobTech open data (CC0).",
  arbeitnow: "Some German listings come from Arbeitnow's free job board API and link back to Arbeitnow.",
};
export const attributions = [...new Set(items.map((i) => i.source))].map((s) => ATTRIBUTION[s]).filter(Boolean);
