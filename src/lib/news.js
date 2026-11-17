// Industry news for the site. Read from src/data/industry_news.json, which the daily GitHub Action refreshes.
// Every item is the official text (headline, a shortened summary, the date the body gave) with a link to the official page.
// Nothing is listed until src/data/industry_news_publish.json says publish: true.
import data from '../data/industry_news.json';
import gate from '../data/industry_news_publish.json';
import { countries, countryName } from './data.js';
import { fmtIso } from './when.js';

export const PUBLISH = gate.publish === true;
export const generatedAt = data.generatedAt || '';
export const keepDays = data.keepDays || 365;
export { countryName, fmtIso };

const byNewest = (a, b) => (b.published || '').localeCompare(a.published || '') || (b.firstSeen || '').localeCompare(a.firstSeen || '') || a.title.localeCompare(b.title);
export const items = PUBLISH ? [...(data.items || [])].sort(byNewest) : [];

// Trade press (ICEF Monitor, The PIE News) is kept apart: headline, date and link only, never shown as an official source.
export const isPress = (i) => i.kind === 'media';
// The newest n official items across all countries, for the strip above the footer. Trade press never goes in the strip.
export const latest = (n = 4) => items.filter((i) => !isPress(i)).slice(0, n);
export const forCountry = (code) => items.filter((i) => i.country === code && !isPress(i));
export const pressFor = (code) => items.filter((i) => i.country === code && isPress(i));
export const counts = Object.fromEntries(countries.map((c) => [c.code, forCountry(c.code).length + pressFor(c.code).length]));

// The /industry-news/ page is one feed, newest first, official and trade press mixed and each labelled.
// A trade-press article that names more than one destination is one entry carrying all of them.
export const feed = (() => {
  const byUrl = new Map();
  for (const i of items) {
    const e = byUrl.get(i.url);
    if (e) { if (!e.countries.includes(i.country)) e.countries.push(i.country); }
    else byUrl.set(i.url, { ...i, countries: [i.country] });
  }
  return [...byUrl.values()];
})();
const ORDER = ['usa', 'uk', 'canada', 'australia', 'new-zealand', 'ireland', 'germany', 'france', 'netherlands', 'sweden', 'norway', 'singapore', 'malaysia', 'uae'];
// Destinations in a fixed order, each with its number of entries in the feed.
export const destinations = countries
  .map((c) => ({ ...c, n: feed.filter((e) => e.countries.includes(c.code)).length }))
  .sort((a, b) => (ORDER.indexOf(a.code) + 1 || 99) - (ORDER.indexOf(b.code) + 1 || 99));
// A small colour per destination so a reader can tell them apart at a glance. The name always sits next to it.
export const COLOR = { usa: '#E4572E', uk: '#4F7BD9', canada: '#C2185B', australia: '#E8A33D', 'new-zealand': '#1F8A8A', ireland: '#3C9D4E', germany: '#A07A3E', france: '#6F7FE0', netherlands: '#F08A5D', sweden: '#2E86C1', norway: '#A569BD', singapore: '#D4AC0D', malaysia: '#16A085', uae: '#A93226' };
// "ICEF Monitor (trade press)" -> "ICEF Monitor": the label beside it already says it is trade press.
export const sourceName = (body) => (body || '').replace(/\s*\(trade press\)\s*$/i, '');

// The official bodies we read for a country, with the date of the last check. Failed ones are kept in the list and marked, never hidden.
export function sourcesFor(code) {
  return Object.entries(data.sources || {})
    .filter(([, s]) => s.country === code && s.kind !== 'media')
    .map(([id, s]) => ({ id, body: s.body, kind: s.kind, url: s.url, status: s.status, checked: s.checked }))
    .sort((a, b) => (a.kind === b.kind ? a.body.localeCompare(b.body) : a.kind === 'government' ? -1 : 1));
}
export const lastChecked = (code) => sourcesFor(code).map((s) => s.checked).filter(Boolean).sort().at(-1) || '';
export const lastCheckedAny = Object.values(data.sources || {}).map((s) => s.checked).filter(Boolean).sort().at(-1) || '';

// "www.ica.gov.sg" -> "ica.gov.sg", so the reader sees which website a link opens.
export const host = (url) => { try { return new URL(url).hostname.replace(/^www\./, ''); } catch { return ''; } };
