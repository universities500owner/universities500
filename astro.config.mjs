import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import fs from 'node:fs';
import { hiddenFromSearch } from './src/lib/noindex.js';
import externalLinks from './scripts/external-links.mjs';

// Pages that must not be listed in the sitemap: drafts, and university pages that are still thin.
const unis = JSON.parse(fs.readFileSync(new URL('./src/data/universities.json', import.meta.url), 'utf-8'));
const hidden = new Set();
for (const u of unis) if (!u.listed) hidden.add(`/universities/${u.slug}/`);
// Industry news stays out of the sitemap until src/data/industry_news_publish.json says publish: true.
const newsGate = JSON.parse(fs.readFileSync(new URL('./src/data/industry_news_publish.json', import.meta.url), 'utf-8'));
if (newsGate.publish !== true) hidden.add('/industry-news/');

export default defineConfig({
  site: 'https://universities500.com',
  trailingSlash: 'always',
  build: { format: 'directory' },
  integrations: [
    sitemap({
      filter: (page) => { const p = new URL(page).pathname; return !hidden.has(p) && !hiddenFromSearch(p); },
    }),
    externalLinks(),
  ],
});
