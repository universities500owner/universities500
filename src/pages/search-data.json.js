import { PUBLISH as COURSES_ON, items as courses, SUBJECTS, subjectList, filterLists, lengthText, feeText, ieltsScore } from '../lib/courses.js';
import { PUBLISH as SCH_ON, items as scholarships } from '../lib/scholarships.js';
import { PUBLISH as INT_ON, items as internships } from '../lib/internships.js';
import { countryName } from '../lib/data.js';

// What the search page needs to answer a plain question about courses, scholarships and internships, on the visitor's device.
// Compact on purpose: one short list per kind. Each course carries the positions of its subjects in S.
export function GET() {
  const subs = COURSES_ON ? subjectList() : [];
  const idx = new Map(subs.map((s, i) => [s.id, i]));
  const money = (c) => { const m = c.fee && c.fee.display && c.fee.display.match(/^([A-Z]{3})\s*([\d,]+(?:\.\d+)?)/); return m ? [m[1], Number(m[2].replace(/,/g, ''))] : ['', 0]; };
  const unis = new Map();
  for (const c of courses) unis.set(c.uni, [c.uniName, c.country]);
  const codes = new Set([...courses.map((c) => c.country), ...(SCH_ON ? scholarships.map((s) => s.country) : []), ...(INT_ON ? internships.map((i) => i.country) : [])]);
  const out = {
    K: Object.fromEntries([...codes].filter(Boolean).map((c) => [c, countryName(c)])),
    S: subs.map((s) => [s.id, s.name, s.also]),
    U: Object.fromEntries(unis),
    // uni, slug, name, level (b or m), years, fee currency, fee amount, IELTS score, start months, subject positions, length text, fee text
    C: courses.map((c) => {
      const [cur, amt] = money(c);
      return [c.uni, c.slug, c.name, c.level === 'Bachelor' ? 'b' : 'm', (c.duration && c.duration.years) || 0, cur, amt, ieltsScore(c), ((c.intakes && c.intakes.months) || []).join(' '),
        c.sj.map((id) => idx.get(id)).filter((x) => x !== undefined).join(' '), lengthText(c, ''), feeText(c, '')];
    }),
    // slug, name, provider, country, levels (b, m or bm), what it is worth
    H: SCH_ON ? scholarships.map((s) => [s.slug, s.name, s.provider, s.country, (s.levels || []).map((l) => (l === 'Bachelor' ? 'b' : l === 'Master' ? 'm' : '')).join(''), (s.value && s.value.display) || '']) : [],
    // title, organisation, city, country, link (the employer's own page)
    I: INT_ON ? internships.map((i) => [i.title, i.org, i.city || '', i.country, i.url]) : [],
  };
  return new Response(JSON.stringify(out), { headers: { 'Content-Type': 'application/json' } });
}
