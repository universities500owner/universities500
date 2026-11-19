// Reads the guides and articles from the data files and returns every page that can have audio, with its clips.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { guideClips, articleClips, withHashes } from '../../src/lib/listen.js';

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');

const readJson = (p) => JSON.parse(fs.readFileSync(p, 'utf8'));
export const loadConfig = (root = ROOT) => readJson(path.join(root, 'src/data/listen/config.json'));
export const manifestPath = (root = ROOT) => path.join(root, 'src/data/listen/manifest.json');
export const loadManifest = (root = ROOT) => {
  try {
    const m = readJson(manifestPath(root));
    return { clips: m.clips || {}, usage: m.usage || {} };
  } catch {
    return { clips: {}, usage: {} };
  }
};

// [{ key: 'guide:canada', kind: 'guide', clips: [{ id, sec, title, text, hash }] }, ...]
export function listenPages(cfg, root = ROOT) {
  const pages = [];
  const guides = readJson(path.join(root, 'src/data/guides.json')).slice().sort((a, b) => a.slug.localeCompare(b.slug));
  for (const g of guides) pages.push({ key: `guide:${g.slug}`, kind: 'guide', clips: withHashes(guideClips(g), cfg) });
  const dir = path.join(root, 'src/data/articles');
  const files = fs.readdirSync(dir).filter((f) => f.endsWith('.json')).sort();
  for (const f of files) {
    const a = readJson(path.join(dir, f));
    const clips = articleClips(a);
    if (clips.length) pages.push({ key: `article:${a.id}`, kind: 'article', clips: withHashes(clips, cfg) });
  }
  return pages;
}
