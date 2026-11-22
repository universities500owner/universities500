// The checked university profiles (scripts/profiles/publish.py writes the file). Only values that passed the checks are in it;
// a university with no entry, or with parts missing, simply shows less.
import raw from '../data/university_profiles.json';

export const profileFor = (slug) => raw[slug] || null;

export const num = (n) => Number(n).toLocaleString('en-US');

export const SOCIAL = {
  instagram: 'Instagram',
  linkedin: 'LinkedIn',
  youtube: 'YouTube',
};

// Google Maps search link: free, needs no key.
export const mapsLink = (name, uniName) => `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${name} ${uniName}`)}`;

export const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

export const host = (url) => { try { return new URL(url).host.replace(/^www\./, ''); } catch { return ''; } };
