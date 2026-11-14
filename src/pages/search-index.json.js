import { NAV } from '../lib/nav.js';
import { guides, runsText } from '../lib/guides.js';
import { all } from '../lib/data.js';
import { items as scholarships } from '../lib/scholarships.js';
import { articles, blockText as artText } from '../lib/articles.js';

const blockText = (b) =>
  b.t === 'p' ? runsText(b.runs)
  : b.t === 'h' ? b.text
  : b.t === 'ul' ? b.items.map((i) => runsText(i.lead) + ' ' + runsText(i.runs) + ' ' + (i.sub ? i.sub.map((s) => runsText(s.runs)).join(' ') : '')).join(' ')
  : b.t === 'qa' ? b.q + ' ' + b.a.map(blockText).join(' ')
  : '';
const clean = (s) => s.replace(/\s+/g, ' ').trim();

// One short index for the search page: pages, guide sections, FAQ questions and universities.
export function GET() {
  const out = [];
  for (const g of NAV) for (const [u, t, , d] of g.items) out.push({ t, u, d, k: '' });
  for (const g of guides) {
    out.push({ t: `Study in ${g.name}`, u: `/study-in/${g.slug}/`, d: g.title, k: '' });
    for (const s of g.sections) {
      const text = clean(s.blocks.map(blockText).join(' '));
      out.push({ t: `${g.name}: ${s.title}`, u: `/study-in/${g.slug}/#s-${s.key}`, d: text.slice(0, 150), k: text.slice(0, 900) });
      if (s.key === 'faq') {
        for (const b of s.blocks.filter((x) => x.t === 'qa')) out.push({ t: b.q, u: `/study-in/${g.slug}/#s-faq`, d: `${g.name}, frequently asked questions`, k: clean(b.a.map(blockText).join(' ')).slice(0, 400) });
      }
    }
  }
  for (const a of articles) {
    const text = clean([...a.quick, ...a.intro].map(artText).join(' '));
    out.push({ t: a.title, u: a.href, d: `Article: ${a.destName}, ${a.topicLabel.toLowerCase()}`, k: clean(`${text} ${a.sections.map((s) => s.title).join(' ')}`).slice(0, 900) });
  }
  for (const x of scholarships) out.push({ t: x.name, u: `/scholarships/${x.slug}/`, d: `${x.provider}, scholarship`, k: [x.value && x.value.display, x.description].filter(Boolean).join(' ').slice(0, 300) });
  for (const u of all) out.push({ t: u.name, u: `/universities/${u.slug}/`, d: u.countryName, k: '' });
  return new Response(JSON.stringify(out), { headers: { 'Content-Type': 'application/json' } });
}
