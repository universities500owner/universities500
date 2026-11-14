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

// Open, closed, yet to open, or unknown. Decided only from dates found on the official page.
export function statusOf(it, todayIso = new Date().toISOString().slice(0, 10)) {
  const { deadline, opens, rolling } = it;
  if (deadline && todayIso > deadline) return 'closed';
  if (opens && todayIso < opens) return 'upcoming';
  if (deadline) return 'open';
  if (rolling) return 'open';
  return 'unknown';
}
export const STATUS_LABEL = { open: 'Open', closed: 'Closed', upcoming: 'Yet to open', unknown: 'Check the official page' };

const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
export function fmtIso(iso) {
  if (!iso) return '';
  const [y, m, d] = iso.split('-').map(Number);
  return `${d} ${MON[m - 1]} ${y}`;
}

export function statusNote(it, st) {
  if (st === 'open') return it.deadline ? `Closes ${fmtIso(it.deadline)}` : 'No fixed deadline stated';
  if (st === 'closed') return `Closed ${fmtIso(it.deadline)}. Check the official page for the next round.`;
  if (st === 'upcoming') return `Opens ${fmtIso(it.opens)}`;
  return it.deadlinePartial ? `Deadline ${it.deadlinePartial} (year not stated)` : 'No dates found on the page';
}

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
