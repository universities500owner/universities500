import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import fs from 'node:fs';
import { DRAFT, UNCHECKED } from './src/lib/noindex.js';

// Pages that must not be listed in the sitemap: drafts, and university pages that are still thin.
const unis = JSON.parse(fs.readFileSync(new URL('./src/data/universities.json', import.meta.url), 'utf-8'));
const hidden = new Set([...DRAFT, ...UNCHECKED]);
for (const u of unis) if (!u.listed) hidden.add(`/universities/${u.slug}/`);

export default defineConfig({
  site: 'https://universities500.com',
  trailingSlash: 'always',
  build: { format: 'directory' },
  integrations: [
    sitemap({
      filter: (page) => !hidden.has(new URL(page).pathname),
    }),
  ],
});
