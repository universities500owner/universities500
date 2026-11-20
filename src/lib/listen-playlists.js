// Playlists for the Listen page and the home page: country guides lined up one after another, or the same section
// (costs, visas, work) from every country. No new audio is made: every item is a clip that already exists for a guide.
import { guideClips, withHashes } from './listen.js';

// "guide:canada#costs.2" -> "costs"
const keyOf = (id) => id.slice(id.indexOf('#') + 1).replace(/\.\d+$/, '');

export const TOPICS = [
  { id: 'costs', keys: ['costs'], label: 'Cost of studying', title: 'What it costs, country by country', note: 'Tuition and living costs in each country, back to back.' },
  { id: 'visa', keys: ['visa'], label: 'Student visa', title: 'Student visas, country by country', note: 'What each country’s student visa asks for, back to back.' },
  { id: 'work', keys: ['post-study', 'work'], label: '', title: 'Working while you study, and after', note: 'Part-time work rights and post-study work, country by country.' },
];

export const fmtLength = (seconds) => {
  const m = Math.max(1, Math.round(seconds / 60));
  // Non-breaking spaces keep "3 h 12 min" on one line on a narrow screen.
  return m < 60 ? `${m}\u00a0min` : `${Math.floor(m / 60)}\u00a0h ${String(m % 60).padStart(2, '0')}\u00a0min`;
};

// guides: [{ slug, name, sections }] in the order to play them. Only a guide whose audio is all ready is used.
// Returns null when nothing is ready, otherwise { base, titles, lists } where each list is
// { id, title, note, groups, seconds, length, items: [[hash, seconds, group, titleIndex], ...] } (group = the country, or the part of one guide).
export function buildHub(guides, manifest, cfg) {
  if (!cfg.voiceId) return null;
  const have = manifest?.clips || {};
  const ready = [];
  for (const g of guides) {
    const clips = withHashes(guideClips(g), cfg);
    if (clips.length && clips.every((c) => have[c.hash])) ready.push({ slug: g.slug, name: g.name, clips });
  }
  if (!ready.length) return null;

  const titles = [];
  const at = new Map();
  const ti = (t) => { if (!at.has(t)) { at.set(t, titles.length); titles.push(t); } return at.get(t); };
  const item = (c, group, title) => [c.hash, have[c.hash].seconds, group, ti(title)];
  const make = (id, title, note, items, groups, extra = {}) => {
    const seconds = items.reduce((n, i) => n + i[1], 0);
    return { id, title, note, groups, seconds: Math.round(seconds), length: fmtLength(seconds), items, ...extra };
  };

  const lists = [];
  const all = [];
  ready.forEach((g, gi) => g.clips.forEach((c) => {
    // The closing reminder is the same on every guide: play it once, at the very end.
    if (keyOf(c.id) === 'closing' && gi < ready.length - 1) return;
    all.push(item(c, gi, `${g.name}: ${c.title}`));
  }));
  lists.push(make('all', `All ${ready.length} country guides`, 'Every guide one after another. Skip to the next country at any time.', all, ready.length));

  for (const t of TOPICS) {
    const items = [];
    let group = 0;
    for (const g of ready) {
      const mine = g.clips.filter((c) => t.keys.includes(keyOf(c.id)));
      if (!mine.length) continue;
      mine.forEach((c) => items.push(item(c, group, `${g.name}: ${t.label || c.title}`)));
      group++;
    }
    if (group >= 2) lists.push(make(t.id, t.title, t.note, items, group));
  }

  for (const g of ready) {
    lists.push(make(`g:${g.slug}`, g.name, '', g.clips.map((c) => item(c, c.sec, c.title)), g.clips[g.clips.length - 1].sec + 1, { slug: g.slug }));
  }
  return { base: String(cfg.audioBase).replace(/\/$/, ''), titles, lists };
}

// Keeps only the lists named, and the titles they use, so a page that shows a few lists does not carry the rest.
export function pickLists(hub, ids) {
  if (!hub) return null;
  const lists = hub.lists.filter((l) => ids.includes(l.id));
  if (!lists.length) return null;
  const titles = [];
  const at = new Map();
  const remap = (i) => { const t = hub.titles[i]; if (!at.has(t)) { at.set(t, titles.length); titles.push(t); } return at.get(t); };
  return { base: hub.base, titles, lists: lists.map((l) => ({ ...l, items: l.items.map(([h, s, g, t]) => [h, s, g, remap(t)]) })) };
}
