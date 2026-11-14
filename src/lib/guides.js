import raw from '../data/guides.json';
import tools from '../data/tools.json';

// The guide files use short names; the destination table uses the full ones.
const LABEL = { usa: 'United States', uk: 'United Kingdom', uae: 'United Arab Emirates' };

export const guides = raw
  .map((g) => ({ ...g, name: LABEL[g.slug] || g.short }))
  .sort((a, b) => a.name.localeCompare(b.name));
export const guideBySlug = Object.fromEntries(guides.map((g) => [g.slug, g]));

// English is a national language: you study and live in English.
export const livesInEnglish = (g) => !!tools.DEST.find((d) => d.c === g.name)?.eng;
export const englishGuides = guides.filter(livesInEnglish);
export const otherGuides = guides.filter((g) => !livesInEnglish(g));

// One plain-text string for a list of formatted runs.
export const runsText = (runs = []) => runs.map((r) => r.t).join('');
export const stripLead = (s) => s.replace(/^\s+/, '');
