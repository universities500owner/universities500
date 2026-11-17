// What the university's own course page says, read by scripts/courses/detail_run.py into src/data/course-detail/<university>.json (one entry per course page).
// Used only by the course page, so no other page or script carries this data. The text of each section was copied from the page by code, and every fact
// was checked against the page's text before it was saved. How much text is shown is set in src/data/course_text_policy.json.
import policy from '../data/course_text_policy.json';

const files = import.meta.glob('../data/course-detail/*.json', { eager: true });
const byUni = new Map(Object.entries(files).map(([p, m]) => [p.split('/').pop().replace('.json', ''), (m.default || m).pages || {}]));

export const detailOf = (c) => (byUni.get(c.uni) || {})[c.url] || null;

// ---------- how much of the university's text to show ----------
export const textMode = (uni) => ((policy.optOut || []).includes(uni) ? 'none' : policy.mode === 'excerpt' ? 'excerpt' : 'full');

// Lines from the page become paragraphs and bullet lists: runs of short lines without a full stop are a list (modules, requirements, employers).
export function paras(text) {
  const out = [];
  let run = [];
  const flush = () => {
    if (run.length > 1) out.push({ list: run });
    else if (run.length === 1) out.push({ p: run[0] });
    run = [];
  };
  for (const line of String(text || '').split('\n').map((l) => l.trim()).filter(Boolean)) {
    const short = line.length <= 90 && !/[.!?:]$/.test(line);
    if (short) run.push(line);
    else {
      flush();
      out.push({ p: line });
    }
  }
  flush();
  return out;
}

const cut = (text, words) => {
  const w = String(text || '').split(/\s+/);
  if (w.length <= words) return { text, more: false };
  return { text: w.slice(0, words).join(' ').replace(/[,;:\s]+$/, '') + '…', more: true };
};

// The blocks of one or more section types, ready to show: [{ heading, paras, more }]. Nothing when the university opted out.
export function blocks(detail, types, uni) {
  const mode = textMode(uni);
  if (!detail || mode === 'none') return [];
  const out = [];
  for (const t of types) {
    for (const b of (detail.sections && detail.sections[t]) || []) {
      const lines = String(b.text || '');
      if (mode === 'excerpt') {
        const e = cut(lines.replace(/\n+/g, ' '), policy.excerptWords || 70);
        out.push({ type: t, heading: b.heading, paras: [{ p: e.text }], more: e.more });
      } else out.push({ type: t, heading: b.heading, paras: paras(lines), more: false });
    }
  }
  return out;
}

// ---------- the short facts ----------
const SYMBOL = { GBP: '£', USD: '$', EUR: '€', AUD: 'A$', CAD: 'C$', NZD: 'NZ$', SGD: 'S$', HKD: 'HK$', JPY: '¥', CHF: 'CHF ', AED: 'AED ', MYR: 'RM', INR: '₹', CNY: 'CN¥', KRW: '₩' };
const PERIOD = { year: ' a year', total: ' for the whole course', term: ' a term', credit: ' per credit', unknown: '' };
export const feeLine = (f) => `${SYMBOL[f.currency] ?? (f.currency ? `${f.currency} ` : '')}${Number(f.amount).toLocaleString('en-GB')}${PERIOD[f.period] ?? ''}${f.year ? ` (${f.year})` : ''}`;
export const intlFee = (d) => ((d && d.facts && d.facts.fees) || []).find((f) => f.audience === 'international') || null;

export const englishLine = (d) => {
  const f = d && d.facts;
  if (!f) return null;
  const parts = [];
  if (f.ielts) parts.push(`IELTS ${f.ielts.overall} overall${f.ielts.minBand ? `, ${Number(f.ielts.minBand).toFixed(1)} in each part` : ''}`);
  for (const t of f.otherEnglish || []) parts.push(`${t.test} ${t.score}`);
  return parts.length ? parts.join('. ') : null;
};
