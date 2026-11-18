// Reads a plain-words question ("masters in nursing in canada under 30000 aud") and says what it asks for.
// No AI and nothing sent anywhere: fixed word lists, the subject list and a spelling check against the site's own words.
// Plain functions, so the browser and the tests use the same code.

import { norm, exactSubject } from './subjects.js';

const COUNTRY_ALIASES = {
  uk: ['uk', 'united kingdom', 'britain', 'great britain', 'england', 'scotland', 'wales', 'northern ireland'],
  usa: ['usa', 'united states', 'united states of america', 'america'],
  canada: ['canada'],
  australia: ['australia', 'aus'],
  'new-zealand': ['new zealand', 'nz', 'aotearoa'],
  ireland: ['ireland', 'republic of ireland'],
  germany: ['germany', 'deutschland'],
  france: ['france'],
  netherlands: ['netherlands', 'the netherlands', 'holland'],
  malaysia: ['malaysia'],
  uae: ['uae', 'united arab emirates', 'dubai', 'abu dhabi', 'emirates'],
  singapore: ['singapore'],
  sweden: ['sweden'],
  norway: ['norway'],
};
// The fee currency a destination uses, for when someone gives an amount with no currency.
export const CURRENCY_OF = { uk: 'GBP', usa: 'USD', canada: 'CAD', australia: 'AUD', 'new-zealand': 'NZD', ireland: 'EUR', germany: 'EUR', france: 'EUR', netherlands: 'EUR', malaysia: 'MYR', uae: 'AED', singapore: 'SGD' };

const LEVEL_WORDS = {
  master: ['master', 'masters', 'msc', 'ma', 'meng', 'mres', 'mph', 'postgraduate', 'postgrad', 'post graduate', 'pg', 'graduate', 'graduate degree', 'postgraduate degree'],
  bachelor: ['bachelor', 'bachelors', 'bsc', 'ba', 'beng', 'undergraduate', 'undergrad', 'under graduate', 'ug', 'undergraduate degree', 'first degree'],
};
const MONTHS = { january: 'Jan', february: 'Feb', march: 'Mar', april: 'Apr', may: 'May', june: 'Jun', july: 'Jul', august: 'Aug', september: 'Sep', october: 'Oct', november: 'Nov', december: 'Dec',
  jan: 'Jan', feb: 'Feb', mar: 'Mar', apr: 'Apr', jun: 'Jun', jul: 'Jul', aug: 'Aug', sep: 'Sep', sept: 'Sep', oct: 'Oct', nov: 'Nov', dec: 'Dec' };

// Words that name a kind of thing the visitor wants (not a filter on courses).
const TOPIC_WORDS = {
  scholarship: ['scholarship', 'scholarships', 'bursary', 'bursaries', 'funding', 'grant', 'grants', 'fellowship', 'fellowships', 'financial aid', 'stipend'],
  internship: ['internship', 'internships', 'intern', 'interns', 'co op', 'coop', 'working student', 'work placement'],
  visa: ['visa', 'visas', 'study permit', 'student route', 'permit'],
  loan: ['loan', 'loans', 'education loan', 'student loan'],
  test: ['ielts', 'toefl', 'pte', 'gre', 'gmat', 'sat', 'duolingo', 'english test', 'english tests', 'exam', 'exams'],
  mba: ['mba', 'emba', 'executive mba'],
  work: ['work rights', 'part time work', 'post study work', 'work permit', 'psw', 'graduate route'],
  cost: ['cost', 'costs', 'budget', 'tuition', 'living costs', 'cost of living', 'fees', 'fee'],
};
const STOP = new Set(('i me my we you your a an the and or of in on at to for from with by as is are be can could would should will do does did how what where which who when why '
  + 'want wants wanted need needs looking look find show get give tell list search any some all every best top good great better cheap cheapest affordable popular '
  + 'study studying studies course courses program programs programme programmes degree degrees abroad overseas international internationally student students '
  + 'university universities college colleges school schools institution institutions available offer offers offering offered near around about like please '
  + 'also just only more most many much very really option options place places country countries intake intakes starting start starts year years yr yrs 2025 2026 2027 2028 2029 '
  + 'under below less than up upto max maximum within not at most cheaper').split(' '));
const RANKING_WORDS = new Set(['best', 'top', 'ranked', 'ranking', 'rankings', 'rank', 'leading', 'greatest']);
const UNI_WORDS = new Set(['university', 'universities', 'college', 'colleges', 'institution', 'institutions']);
const COURSE_WORDS = new Set(['course', 'courses', 'program', 'programs', 'programme', 'programmes', 'degree', 'degrees', 'study', 'studying', 'studies']);
const CURRENCY_WORDS = { gbp: 'GBP', usd: 'USD', aud: 'AUD', cad: 'CAD', nzd: 'NZD', eur: 'EUR', inr: 'INR', sgd: 'SGD', aed: 'AED', myr: 'MYR',
  pound: 'GBP', pounds: 'GBP', sterling: 'GBP', euro: 'EUR', euros: 'EUR', dollar: 'USD', dollars: 'USD', rupee: 'INR', rupees: 'INR' };
const SYMBOL = { '£': 'GBP', '€': 'EUR', '₹': 'INR', $: '$' };

// ---------- spelling ----------
// Edit distance, with a swap of two neighbouring letters counted as one change.
export function distance(a, b) {
  if (a === b) return 0;
  const prev2 = [];
  let prev = Array.from({ length: b.length + 1 }, (_, j) => j);
  for (let i = 1; i <= a.length; i += 1) {
    const cur = [i];
    for (let j = 1; j <= b.length; j += 1) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost);
      if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) cur[j] = Math.min(cur[j], prev2[j - 2] + 1);
    }
    prev2.splice(0, prev2.length, ...prev);
    prev = cur;
  }
  return prev[b.length];
}

// ---------- the word lists, ready to use ----------
// countries: [{ code, name }] the destinations the site has. subjects: the result of compileLite or compile.
export function buildLexicon({ countries, subjects }) {
  const codes = new Set(countries.map((c) => c.code));
  const country = new Map();
  for (const [code, list] of Object.entries(COUNTRY_ALIASES)) if (codes.has(code)) for (const a of list) country.set(norm(a), code);
  for (const c of countries) country.set(norm(c.name), c.code);
  const level = new Map();
  for (const [k, list] of Object.entries(LEVEL_WORDS)) for (const w of list) level.set(norm(w), k);
  const topic = new Map();
  for (const [k, list] of Object.entries(TOPIC_WORDS)) for (const w of list) topic.set(norm(w), k);
  // single words the spell check may correct to: long enough that one wrong letter is not another word
  const vocab = new Set();
  const add = (w) => { if (w.length >= 4 && !STOP.has(w)) vocab.add(w); };
  for (const w of country.keys()) w.split(' ').forEach(add);
  for (const w of topic.keys()) w.split(' ').forEach(add);
  for (const s of subjects.subjects) for (const a of s.alias) a.split(' ').forEach(add);
  for (const w of Object.keys(MONTHS)) if (w.length >= 5) vocab.add(w);
  for (const w of level.keys()) w.split(' ').forEach(add);
  const known = new Set([...vocab, ...STOP, ...country.keys(), ...level.keys(), ...topic.keys(), ...Object.keys(MONTHS), ...Object.keys(CURRENCY_WORDS)]);
  return { subjects, country, level, topic, vocab: [...vocab], known, countryName: new Map(countries.map((c) => [c.code, c.name])) };
}

function correct(word, lex) {
  if (word.length < 4 || /\d/.test(word) || lex.known.has(word)) return null;
  const limit = word.length >= 8 ? 2 : 1;
  let best = null;
  for (const v of lex.vocab) {
    if (Math.abs(v.length - word.length) > limit) continue;
    const d = distance(word, v);
    if (d <= limit && (!best || d < best[1])) best = [v, d];
  }
  return best ? best[0] : null;
}

// ---------- numbers: budget and IELTS ----------
const num = (s) => Number(String(s).replace(/,/g, ''));
function takeIelts(text) {
  const a = text.match(/\bielts\s*(?:score|of|band|overall|at|:)?\s*(\d(?:\.\d)?)\b/i) || text.match(/\b(\d(?:\.\d)?)\s*(?:band\s*)?(?:in\s+|on\s+)?ielts\b/i);
  if (!a) return null;
  const v = Number(a[1]);
  if (v < 4 || v > 9) return null;
  return { value: v, span: a[0] };
}
const BUDGET_RE = /(?:\b(under|below|less than|up to|upto|max(?:imum)?|within|budget(?: of| is)?|cheaper than|not more than|at most|around|about)\s+)?(?:(£|\$|€|₹)\s?)?(\d[\d,]*(?:\.\d+)?)\s?(k|thousand|lakhs?|lacs?)?\s?(gbp|usd|aud|cad|nzd|eur|inr|sgd|aed|myr|pounds?|dollars?|euros?|rupees?)?\b/gi;
function takeBudget(text, countries) {
  for (const m of text.matchAll(BUDGET_RE)) {
    const [span, trigger, symbol, digits, mult, cur] = m;
    if (!trigger && !symbol && !cur) continue;
    let amount = num(digits);
    const unit = (mult || '').toLowerCase();
    if (unit === 'k' || unit === 'thousand') amount *= 1000;
    if (/^la/.test(unit)) amount *= 100000;
    if (amount < 1000) continue;
    if (!symbol && !cur && !unit && amount >= 1990 && amount <= 2100) continue;   // a year, not money
    let currency = cur ? CURRENCY_WORDS[cur.toLowerCase()] : symbol && symbol !== '$' ? SYMBOL[symbol] : null;
    if (!currency && /^la/.test(unit)) currency = 'INR';
    if (!currency) {
      // no currency given: use the destination's, when there is one and it is a dollar when "$" was written
      const own = [...new Set(countries.map((c) => CURRENCY_OF[c]).filter(Boolean))];
      if (own.length === 1 && (symbol !== '$' || ['USD', 'AUD', 'CAD', 'NZD', 'SGD'].includes(own[0]))) currency = own[0];
    }
    return { amount, currency, span: span.trim() };
  }
  return null;
}

// ---------- the main step ----------
// ignore: kinds the visitor removed from the chips ('level', 'subject', 'budget', 'ielts', 'month', 'country:uk').
export function understand(raw, lex, ignore = new Set()) {
  const text = String(raw || '').slice(0, 300);
  const out = { text, level: null, countries: [], subject: null, budget: null, ielts: null, month: null, topics: [], rest: [], fixes: [], chips: [], flags: { ranking: false, universities: false, courses: false }, notes: [] };

  // numbers first, because normalising the text would break "6.5" and "20,000"
  const ie = takeIelts(text);
  let body = text;
  if (ie) body = body.replace(ie.span, ' ');
  // countries named in the text help to pick a currency for "under 20000"
  const quick = [];
  for (const [alias, code] of lex.country) if (new RegExp(`(^|[^a-z])${alias.replace(/ /g, '\\s+')}([^a-z]|$)`, 'i').test(norm(text))) quick.push(code);
  const bu = takeBudget(body, quick);
  if (bu) body = body.replace(bu.span, ' ');

  // words
  // "US" and "U.S." count as the country only when written in capitals, so "tell us" is not read as a place
  body = body.replace(/\bU\.S\.A?\.?|\bUSA\b|\bUS\b/g, ' usa ');
  let tokens = norm(body).split(' ').filter(Boolean);
  const fixes = [];
  tokens = tokens.map((t) => {
    const f = correct(t, lex);
    if (f) { fixes.push([t, f]); return f; }
    return t;
  });
  out.fixes = fixes;

  const used = new Array(tokens.length).fill(false);
  const grab = (map, maxN = 4) => {
    const found = [];
    for (let n = maxN; n >= 1; n -= 1) {
      for (let i = 0; i + n <= tokens.length; i += 1) {
        if (used.slice(i, i + n).some(Boolean)) continue;
        const key = tokens.slice(i, i + n).join(' ');
        if (map.has(key)) { for (let j = i; j < i + n; j += 1) used[j] = true; found.push([map.get(key), key, i]); }
      }
    }
    return found.sort((a, b) => a[2] - b[2]);
  };

  // destinations
  const codes = [];
  for (const [code] of grab(lex.country)) if (!codes.includes(code)) codes.push(code);
  for (const code of codes) {
    if (ignore.has(`country:${code}`)) continue;
    out.countries.push(code);
    out.chips.push({ kind: `country:${code}`, label: lex.countryName.get(code) || code });
  }

  // topics (before level, so "graduate route" is a visa topic and not a Master's)
  const topics = new Set();
  grab(lex.topic, 3).forEach(([t]) => topics.add(t));

  // level
  const lv = new Set(grab(lex.level, 3).map((x) => x[0]));
  if (lv.size === 1 && !ignore.has('level')) {
    out.level = [...lv][0];
    out.chips.push({ kind: 'level', label: out.level === 'master' ? "Master's" : "Bachelor's" });
  }

  // start month ("may" only after a word that makes it a month)
  tokens.forEach((t, i) => {
    if (used[i] || !MONTHS[t] || out.month) return;
    if (t === 'may' && !['in', 'for', 'from', 'starting', 'intake', 'start'].includes(tokens[i - 1])) return;
    used[i] = true;
    if (!ignore.has('month')) { out.month = MONTHS[t]; out.chips.push({ kind: 'month', label: `Starts ${MONTHS[t]}` }); }
  });

  // subject: the longest run of words that names one
  search: for (let n = 4; n >= 1; n -= 1) {
    for (let i = 0; i + n <= tokens.length; i += 1) {
      if (used.slice(i, i + n).some(Boolean)) continue;
      const words = tokens.slice(i, i + n);
      if (n === 1 && STOP.has(words[0])) continue;
      const sub = exactSubject(lex.subjects, words.join(' '));
      if (!sub) continue;
      for (let j = i; j < i + n; j += 1) used[j] = true;
      if (!ignore.has('subject')) { out.subject = { id: sub.id, name: sub.name, index: sub.index }; out.chips.push({ kind: 'subject', label: sub.name }); }
      break search;
    }
  }

  // what is left over
  tokens.forEach((t, i) => {
    if (RANKING_WORDS.has(t)) out.flags.ranking = true;
    if (UNI_WORDS.has(t)) out.flags.universities = true;
    if (COURSE_WORDS.has(t)) out.flags.courses = true;
  });
  out.topics = [...topics];
  // words kept for plain text matching: not used, not filler. Topic words stay (a page about "visa" needs the word).
  const topicWords = new Set();
  for (const [phrase, t] of lex.topic) if (topics.has(t)) phrase.split(' ').forEach((w) => topicWords.add(w));
  tokens.forEach((t, i) => {
    if (STOP.has(t) || /^\d+$/.test(t)) return;
    if (used[i] && !topicWords.has(t)) return;
    out.rest.push(t);
  });
  out.restPlain = out.rest.filter((w) => !topicWords.has(w));

  if (ie && !ignore.has('ielts')) { out.ielts = ie.value; out.chips.push({ kind: 'ielts', label: `IELTS ${ie.value}` }); }
  if (bu && !ignore.has('budget')) {
    out.budget = { amount: bu.amount, currency: bu.currency };
    const shown = bu.amount.toLocaleString('en-GB');
    out.chips.push({ kind: 'budget', label: bu.currency ? `Fee up to ${bu.currency} ${shown}` : `Fee up to ${shown} (currency?)` });
    if (!bu.currency) out.notes.push('Fees are shown in each country\'s own currency, so say it with the amount, for example "under 20000 AUD", or add a country.');
    if (bu.currency === 'INR') out.notes.push('We do not convert currencies, and our course fees are not in rupees, so the budget cannot filter courses.');
  }
  // the chips read in a steady order: level, subject, destinations, start, English, fee
  const rank = (k) => ['level', 'subject', 'country', 'month', 'ielts', 'budget'].indexOf(k.split(':')[0]);
  out.chips.sort((a, b) => rank(a.kind) - rank(b.kind));
  return out;
}
