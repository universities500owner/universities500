// Build step: every link to another website opens in a new tab; links inside universities500.com stay in the same tab.
// It runs on the finished HTML, so it also works for readers whose browser has JavaScript off.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const OWN = new Set(['universities500.com', 'www.universities500.com']);
const NOTE = '(opens in a new tab)';

const attr = (tag, name) => {
  const m = tag.match(new RegExp(`\\s${name}\\s*=\\s*("([^"]*)"|'([^']*)'|([^\\s>]+))`, 'i'));
  return m ? { whole: m[0], value: m[2] ?? m[3] ?? m[4] ?? '' } : null;
};

export function isExternal(href) {
  if (!/^https?:\/\//i.test(href) && !href.startsWith('//')) return false;
  try {
    return !OWN.has(new URL(href, 'https://universities500.com').hostname.toLowerCase());
  } catch {
    return false;
  }
}

/** Rewrites one HTML string. Returns the new string and how many links were changed. */
export function rewrite(html) {
  let n = 0;
  const out = html.replace(/<a\b([^>]*)>([\s\S]*?)<\/a>/gi, (all, attrs, inner) => {
    const open = `<a${attrs}>`;
    const href = attr(open, 'href');
    if (!href || !isExternal(href.value.trim())) return all;
    let tag = open;
    const tgt = attr(tag, 'target');
    if (tgt) tag = tag.replace(tgt.whole, '');
    tag = tag.replace(/^<a\b/i, '<a target="_blank"');
    const rel = attr(tag, 'rel');
    const tokens = new Set((rel ? rel.value : '').split(/\s+/).filter(Boolean));
    tokens.add('noopener');
    if (rel) tag = tag.replace(rel.whole, '');
    tag = tag.replace(/^<a\b/i, `<a rel="${[...tokens].join(' ')}"`);
    // Tell screen-reader users too. A link with its own aria-label gets the note in the label.
    const label = attr(tag, 'aria-label');
    let body = inner;
    if (label) {
      if (!label.value.includes(NOTE)) tag = tag.replace(label.whole, ` aria-label="${label.value} ${NOTE}"`);
    } else if (!inner.includes(NOTE)) {
      body = `${inner}<span class="sr-only"> ${NOTE}</span>`;
    }
    n += 1;
    return `${tag}${body}</a>`;
  });
  return { html: out, changed: n };
}

function walk(dir, files = []) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) walk(p, files);
    else if (e.name.endsWith('.html')) files.push(p);
  }
  return files;
}

export default function externalLinks() {
  return {
    name: 'external-links-new-tab',
    hooks: {
      'astro:build:done': ({ dir, logger }) => {
        let pages = 0, links = 0;
        for (const f of walk(fileURLToPath(dir))) {
          const { html, changed } = rewrite(fs.readFileSync(f, 'utf-8'));
          if (changed) {
            fs.writeFileSync(f, html);
            pages += 1;
            links += changed;
          }
        }
        logger.info(`${links} outside links on ${pages} pages now open in a new tab`);
      },
    },
  };
}
