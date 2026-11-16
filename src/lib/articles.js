// The article library. One JSON file per article in src/data/articles/ (made by scripts/articles/import_docx.py).
import { guideBySlug } from './guides.js';

const files = import.meta.glob('../data/articles/*.json', { eager: true });

// The eight reader-facing topics, in the order they appear in menus and the footer.
// `tools` are the site tools that help with that topic; they are shown at the end of each article.
export const TOPICS = {
  'cost-and-budgeting': {
    label: 'Costs and budgeting',
    blurb: 'What studying there really costs: tuition, living costs and the money a visa asks you to show.',
    tools: [['/budget/', 'Budget planner'], ['/loan/', 'Education loan']],
  },
  visas: {
    label: 'Visas and paperwork',
    blurb: 'Student visa steps, documents and interviews, and the mistakes that cause delays.',
    tools: [['/visa-readiness/', 'Visa readiness'], ['/before-you-fly/', 'Before you fly']],
  },
  'after-study': {
    label: 'Work after study',
    blurb: 'What each destination lets you do once the course ends, and what it asks of you.',
    tools: [['/internships/', 'Internships'], ['/working-while-you-study/', 'Working while you study']],
  },
  admissions: {
    label: 'Admissions and tests',
    blurb: 'Entry requirements, document checks and English-language proof, explained step by step.',
    tools: [['/application-prep/', 'Application prep'], ['/english-test/', 'English test']],
  },
  'universities-and-courses': {
    label: 'Universities and courses',
    blurb: 'How to compare universities and course types without relying on a single number.',
    tools: [['/courses/', 'Course search'], ['/universities/', 'Find my university']],
  },
  'student-life': {
    label: 'Student life and work',
    blurb: 'Housing, living day to day and working part-time while you study.',
    tools: [['/before-you-fly/', 'Before you fly'], ['/working-while-you-study/', 'Working while you study']],
  },
  'scholarships-and-funding': {
    label: 'Scholarships and funding',
    blurb: 'Where study money can come from, and what to ask before you count on it.',
    tools: [['/scholarships/', 'Scholarships'], ['/budget/', 'Budget planner']],
  },
  careers: {
    label: 'Careers and jobs',
    blurb: 'Skilled-work routes and how to judge what a course may lead to.',
    tools: [['/internships/', 'Internships'], ['/working-while-you-study/', 'Working while you study']],
  },
};
const TOPIC_ORDER = Object.keys(TOPICS);

// Which topics belong on which tool page.
export const TOOL_TOPICS = {
  budget: ['cost-and-budgeting', 'scholarships-and-funding'],
  loan: ['cost-and-budgeting'],
  'visa-readiness': ['visas', 'after-study'],
  'working-while-you-study': ['student-life', 'after-study', 'careers'],
  'application-prep': ['admissions'],
  'english-test': ['admissions'],
  exams: ['admissions'],
  'before-you-fly': ['student-life', 'visas'],
  scholarships: ['scholarships-and-funding', 'cost-and-budgeting'],
  internships: ['careers', 'after-study'],
  courses: ['universities-and-courses'],
  universities: ['universities-and-courses'],
};

const PRIORITY = { high: 0, medium: 1, low: 2 };
const prio = (a) => PRIORITY[String(a.priority || '').toLowerCase()] ?? 3;
// The pack gives each article a suggested address. Keep its last part, and put the country in front when it is not already there.
const ALIAS = { sweden: ['sweden', 'swedish'], netherlands: ['netherlands', 'dutch'], uae: ['uae', 'dubai'], 'new-zealand': ['new-zealand'], uk: ['uk'], usa: ['usa'] };
const urlSlug = (a) => {
  const s = String(a.slug || a.id).split('/').filter(Boolean).pop().toLowerCase().replace(/[^a-z0-9-]+/g, '-');
  const words = ALIAS[a.destination] || [a.destination];
  const has = words.some((w) => `-${s}-`.includes(`-${w}-`));
  return has || a.destination === 'global' ? s : `${a.destination}-${s}`;
};

export const runsText = (runs = []) => runs.map((r) => (r.t === undefined ? ' ' : r.t)).join('');
export const blockText = (b) => {
  if (b.t === 'p') return runsText(b.runs);
  if (b.t === 'h') return b.text;
  if (b.t === 'ul' || b.t === 'ol') {
    return b.items.map((i) => `${runsText(i.lead)} ${runsText(i.runs)} ${(i.sub || []).map((s) => `${runsText(s.lead)} ${runsText(s.runs)}`).join(' ')}`).join(' ');
  }
  if (b.t === 'table') return [b.head, ...b.rows].filter(Boolean).map((r) => r.map(runsText).join(' ')).join(' ');
  if (b.t === 'callout' || b.t === 'quote') return b.blocks.map(blockText).join(' ');
  return '';
};
export const flat = (s) => s.replace(/\s+/g, ' ').trim();
export const slugify = (s) => s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
const firstSentence = (s, max = 150) => {
  const one = flat(s).split(/(?<=[.!?])\s+/)[0];
  return one.length > max ? one.slice(0, max - 1).replace(/\s+\S*$/, '') + '…' : one;
};

const seen = new Set();
export const articles = Object.values(files)
  .map((m) => m.default)
  .filter((a) => !a.hold)
  .sort((a, b) => prio(a) - prio(b) || a.id.localeCompare(b.id))
  .map((a) => {
    let slug = urlSlug(a);
    if (seen.has(slug)) slug = `${slug}-${a.id.toLowerCase()}`;
    seen.add(slug);
    const destName = a.destination === 'global' ? 'All destinations' : guideBySlug[a.destination]?.name || a.destination;
    const lead = a.quick.length ? blockText(a.quick[0]) : a.intro.length ? blockText(a.intro[0]) : '';
    return {
      ...a,
      slug,
      href: `/articles/${slug}/`,
      destName,
      topicLabel: TOPICS[a.topic]?.label || a.topicLabel,
      snippet: firstSentence(lead),
    };
  });

export const bySlug = Object.fromEntries(articles.map((a) => [a.slug, a]));

export const destinations = [...new Set(articles.map((a) => a.destination))]
  .map((slug) => ({ slug, name: slug === 'global' ? 'All destinations' : guideBySlug[slug]?.name || slug, count: articles.filter((a) => a.destination === slug).length }))
  .sort((a, b) => a.name.localeCompare(b.name));

export const topics = TOPIC_ORDER.map((slug) => ({ slug, ...TOPICS[slug], count: articles.filter((a) => a.topic === slug).length })).filter((t) => t.count > 0);

export const byDestination = (d) => articles.filter((a) => a.destination === d);
export const byTopic = (t) => articles.filter((a) => a.topic === t);

// Up to n articles, taking turns between topics so a page does not show five of the same kind.
export function forTopics(topicSlugs, n = 3, { dest } = {}) {
  const lists = topicSlugs.map((t) => byTopic(t).filter((a) => !dest || a.destination === dest));
  const out = [];
  for (let i = 0; out.length < n && lists.some((l) => i < l.length); i++) {
    for (const l of lists) if (l[i] && out.length < n && !out.includes(l[i])) out.push(l[i]);
  }
  return out;
}

export const forDestination = (dest, n = 6) => byDestination(dest).slice(0, n);

// A handful for the home page: different topics and different destinations.
export function featured(n = 6) {
  const out = [], topicsUsed = new Set(), destUsed = new Set();
  for (const a of articles) {
    if (out.length >= n) break;
    if (!topicsUsed.has(a.topic) && !destUsed.has(a.destination)) { out.push(a); topicsUsed.add(a.topic); destUsed.add(a.destination); }
  }
  for (const a of articles) if (out.length < n && !out.includes(a)) out.push(a);
  return out;
}

export function related(a) {
  const sameDest = byDestination(a.destination).filter((x) => x.id !== a.id && x.topic !== a.topic);
  const sameTopic = byTopic(a.topic).filter((x) => x.id !== a.id && x.destination !== a.destination);
  const more = byDestination(a.destination).filter((x) => x.id !== a.id && !sameDest.includes(x));
  return { sameDest: [...sameDest, ...more].slice(0, 3), sameTopic: sameTopic.slice(0, 3) };
}

export const readLabel = (a) => `${a.readMinutes} min read`;
export const checkedLabel = (a) => {
  if (!a.reviewed) return '';
  const d = new Date(`${a.reviewed}T00:00:00Z`);
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });
};

// A short list of official sources for the foot of an article: the few that best match what the article is about.
// Government and official-registry pages come first, then whichever source shares the most words with the article.
const STOP = new Set('the and for with from that this your you are how what when where which into about study student students international studying guide'.split(' '));
const words = (t) => String(t || '').toLowerCase().replace(/[^a-z0-9 ]+/g, ' ').split(/\s+/).filter((w) => w.length > 2 && !STOP.has(w));
const OFFICIAL = /(\.gov(\.|\/)|\.gouv\.|\.govt\.|\.gc\.ca|canada\.ca|\.europa\.eu|\.admin\.ch|\.edu(\.|\/)|\.ac\.|studyinaustralia|studyaustralia|educationinireland|studyinsweden|studyinnorway|nuffic|campusfrance|studyinnz|educationnz|icas\.|ukcisa|britishcouncil|iie\.org|studyinthenetherlands|daad|study-in-germany|immigration|immi\.|migri|udi\.no|ind\.nl|ica\.gov|moe\.gov|mom\.gov)/i;
// Some packs give a bare web address as the title and put the readable name first in the note.
const isDomain = (t) => /^[\w.-]+\.[a-z]{2,}(\/\S*)?$/i.test(String(t || '').trim());
const sourceLabel = (s) => (isDomain(s.title) && s.note ? String(s.note).split(/\.\s/)[0].replace(/\.$/, '') : s.title);
export const shortSources = (a, n = 3) => {
  const mine = new Set(words([a.title, a.primaryKeyword, ...(a.secondaryKeywords || []), a.topicLabel].join(' ')));
  return [...(a.sources || [])]
    .map((s, i) => {
      const w = words(`${s.title} ${s.url} ${s.note || ''}`);
      const hit = w.filter((x) => mine.has(x)).length;
      return { s, i, score: hit + (OFFICIAL.test(s.url) ? 3 : 0) };
    })
    .sort((x, y) => y.score - x.score || x.i - y.i)
    .slice(0, n)
    .sort((x, y) => x.i - y.i)
    .map((x) => ({ title: sourceLabel(x.s), url: x.s.url }));
};
