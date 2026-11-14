import unis from '../data/universities.json';

export const SITE = 'https://universities500.com';
export const all = unis;

export const countries = Object.values(
  unis.reduce((m, u) => {
    (m[u.country] ||= { code: u.country, name: u.countryName, count: 0 }).count++;
    return m;
  }, {}),
).sort((a, b) => a.name.localeCompare(b.name));

export const byCountry = (code) => unis.filter((u) => u.country === code);
export const countryName = (code) => countries.find((c) => c.code === code)?.name ?? code;

export const latestRead = unis.map((u) => u.read).filter(Boolean).sort().at(-1);

// First sentence, trimmed for a meta description.
export function blurb(text, max = 155) {
  if (!text) return '';
  const first = text.split(/(?<=[.!?])\s+/)[0] || text;
  if (first.length <= max) return first;
  return first.slice(0, max - 1).replace(/\s+\S*$/, '') + '…';
}

// Next few universities in the same country, wrapping round the alphabetical list.
export function related(u, n = 6) {
  const peers = byCountry(u.country);
  const i = peers.findIndex((p) => p.slug === u.slug);
  const out = [];
  for (let k = 1; k < peers.length && out.length < n; k++) out.push(peers[(i + k) % peers.length]);
  return out;
}

export function fmtDate(iso) {
  if (!iso) return '';
  const d = new Date(iso + 'T00:00:00Z');
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });
}
