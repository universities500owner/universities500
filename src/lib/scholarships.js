// Scholarship data for the site. Read from src/data/scholarships.json, which the GitHub Action refreshes every two days.
// Nothing is shown until src/data/scholarship_publish.json says publish: true.
import data from '../data/scholarships.json';
import gate from '../data/scholarship_publish.json';
import { all, countries, countryName } from './data.js';

export const PUBLISH = gate.publish === true;
export const items = PUBLISH ? data.items : [];
export const generatedAt = data.generatedAt;
export const directories = (data.directories || []).filter((d) => d.ok);
export const thirdParty = data.thirdParty || [];
export const hubFor = (slug) => (PUBLISH ? data.universities?.[slug] : null);
export const itemsFor = (slug) => items.filter((i) => i.providerSlug === slug);
export const bySlug = (slug) => items.find((i) => i.slug === slug);

export { statusOf, STATUS_LABEL, statusNote, scholarshipPill, fmtIso, valueType, VALUE_LABEL, shortAbout } from './when.js';

export const CHECK = 'Check the official page';

// How the page describes the number of awards and whether you apply. Both are copied from the page's own wording.
export const awardsText = (a) => (a && a.n ? `${a.upTo ? 'Up to ' : ''}${a.n}` : '');
export const APPLY_MODE_LABEL = { automatic: 'Considered automatically, no separate application', application: 'Apply through the official page' };

// A university's scholarships page. Where the reader found one, it is that page. Where it could not read the site
// (robots.txt, no scholarships page found, site down) we do not guess an address: the link is a web search limited to the university's own domain.
export function siteSearchUrl(web) {
  try {
    const host = new URL(web).hostname.replace(/^www\./, '');
    return `https://www.google.com/search?q=${encodeURIComponent(`site:${host} scholarships international students`)}`;
  } catch { return null; }
}
export function scholarshipsLink(u) {
  const hub = hubFor(u.slug);
  if (hub && hub.hubUrl) return { url: hub.hubUrl, kind: 'page', checked: hub.checked };
  const url = u.web ? siteSearchUrl(u.web) : null;
  return url ? { url, kind: 'search', checked: null } : null;
}
// Every university, by destination, with the best link we have and how many scholarships we read from it.
export function universityLinks() {
  const out = [];
  for (const c of countries) {
    const list = all.filter((u) => u.country === c.code && u.web)
      .map((u) => ({ u, link: scholarshipsLink(u), n: itemsFor(u.slug).length }))
      .filter((x) => x.link)
      .sort((a, b) => a.u.name.localeCompare(b.u.name));
    if (list.length) out.push({ code: c.code, name: c.name, list });
  }
  return out;
}
export const levelsText = (l) => (l && l.length ? l.join(', ') : CHECK);

// Official places to look, grouped by destination.
export function lookGroups() {
  const out = [];
  for (const c of countries) {
    const dirs = directories.filter((d) => d.countries.includes(c.code));
    const tp = thirdParty.filter((t) => t.countries.includes(c.code));
    if (dirs.length || tp.length) out.push({ code: c.code, name: c.name, dirs, tp });
  }
  const any = thirdParty.filter((t) => t.countries.includes('all'));
  if (any.length) out.push({ code: 'all', name: 'Any destination', dirs: [], tp: any });
  return out;
}
export { countryName };
