// Scholarship data for the site. Read from src/data/scholarships.json, which the GitHub Action refreshes every two days.
// Nothing is shown until src/data/scholarship_publish.json says publish: true.
import data from '../data/scholarships.json';
import gate from '../data/scholarship_publish.json';
import { countries, countryName } from './data.js';

export const PUBLISH = gate.publish === true;
export const items = PUBLISH ? data.items : [];
export const generatedAt = data.generatedAt;
export const directories = (data.directories || []).filter((d) => d.ok);
export const thirdParty = data.thirdParty || [];
export const hubFor = (slug) => (PUBLISH ? data.universities?.[slug] : null);
export const itemsFor = (slug) => items.filter((i) => i.providerSlug === slug);
export const bySlug = (slug) => items.find((i) => i.slug === slug);

export { statusOf, STATUS_LABEL, statusNote, scholarshipPill, fmtIso } from './when.js';

export const CHECK = 'Check the official page';
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
