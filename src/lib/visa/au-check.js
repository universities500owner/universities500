// The Australian student visa self-check. Pure functions: answers in, a result out. No network, no AI, no student data leaves the browser
// or the server to produce it. The rules and figures are in au-rules.js.
//
// This is a self-check and a way to see what to strengthen. It is not a prediction, a probability or advice. Home Affairs decides every
// application on its own facts, and it sees things this check never does.
import { SECTIONS } from '../account/schema.js';
import { MONEY, ENGLISH, WEIGHTS, BANDS, COVER, HISTORY, CHECKED, CHECKED_LABEL, SOURCES } from './au-rules.js';

export const BAND_LABEL = { green: 'Green', amber: 'Amber', red: 'Red' };
export const BAND_SAY = {
  green: 'Looking ready. Keep your evidence in order.',
  amber: 'Some gaps to close before you apply.',
  red: 'Not ready to apply yet. Fix the first items below.',
};

// What the check needs that is not already in the profile. Order is the order they are asked in.
export const REQUIRED = SECTIONS.visa_au.fields.filter((f) => f.required).map((f) => f.id);

const num = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : 0);
const money = (n) => 'AUD ' + Math.round(n).toLocaleString('en-IN');
const round = (n) => Math.round(n * 10) / 10;

// The money the rules count for the first 12 months: tuition + living costs for the student, a partner and children + school costs.
export function moneyNeeded(v) {
  const kids = Math.max(0, Math.floor(num(v.children)));
  const school = Math.min(kids, Math.max(0, Math.floor(num(v.school_children))));
  const living = MONEY.living + (v.partner ? MONEY.partner : 0) + kids * MONEY.child;
  const schooling = school * MONEY.school;
  const tuition = num(v.tuition);
  return { tuition, living, schooling, total: tuition + living + schooling };
}

function fundsFactor(v, flags, tips) {
  const max = WEIGHTS.funds;
  const need = moneyNeeded(v);
  const have = num(v.funds);
  const ratio = need.total > 0 ? have / need.total : 0;
  const tier = COVER.find(([from]) => ratio >= from) || COVER[COVER.length - 1];
  const status = { ready: 1, partial: 0.75, planned: 0.4 }[v.funds_status] ?? 0.4;
  const score = Math.round(max * tier[1] * status);
  const notes = [];
  notes.push(`Money the rules count for 12 months: ${money(need.total)} (tuition ${money(need.tuition)}, living costs ${money(need.living)}${need.schooling ? `, school costs ${money(need.schooling)}` : ''}).`);
  notes.push(`Money you can show: ${money(have)}${ratio ? `, which is ${Math.round(ratio * 100)}% of that` : ''}.`);
  notes.push('Travel to Australia and health cover are not in that total. You need those too.');

  if (ratio < 1) {
    flags.push({ id: 'funds_short', cap: 'red', text: `You can show less than the ${money(need.total)} the rules count. Until that is covered, the result stays Red.` });
    tips.push({ gain: max - score, must: true, text: `Cover the shortfall of ${money(need.total - have)} (and the travel and health cover on top) with money you can document, or choose a course with lower fees.` });
  } else if (ratio < COVER[0][0]) {
    tips.push({ gain: max - score, text: 'Build more room above the amount counted. Travel, health cover and changes in the exchange rate come out of the same money.' });
  }
  if (v.funds_status !== 'ready') tips.push({ gain: Math.round(max * tier[1] * (1 - status)), text: v.funds_status === 'partial' ? 'Finish arranging the rest of the money, for example the loan sanction letter, so it is in an account before you apply.' : 'Arrange the money first: savings in an account, or a sanctioned loan. Plans on paper do not count as evidence.' });
  return { id: 'funds', label: 'Money for the first year', score, max, notes, need, have, ratio };
}

function fitFactor(v, tips) {
  const max = WEIGHTS.fit;
  const link = { related: 11, partly: 7, unrelated: 3 }[v.course_link] ?? 0;
  const reasons = { clear: 8, general: 4, not_yet: 1 }[v.reasons] ?? 0;
  const gap = { none: 6, explained: 4, unexplained: 0 }[v.gap] ?? 0;
  const notes = [];
  notes.push({ related: 'The course follows from what you studied or did before.', partly: 'The course is partly related to your past study or work.', unrelated: 'The course is a change of direction from your past study or work.' }[v.course_link] || '');
  notes.push({ clear: 'You can explain why this course and this university in specific terms.', general: 'You have a general idea why this course and university.', not_yet: 'You cannot yet explain why this course and university.' }[v.reasons] || '');
  notes.push({ none: 'No gap of more than a year in your study or work.', explained: 'You have a gap, and you can explain it with evidence.', unexplained: 'You have a gap you cannot yet explain.' }[v.gap] || '');
  if (v.course_link === 'unrelated') tips.push({ gain: 11 - link, text: 'A change of field is fine, but you must show why. Link it to a skill, a job you want or a gap in your home job market, and keep proof of any bridging work.' });
  else if (v.course_link === 'partly') tips.push({ gain: 11 - link, text: 'Spell out how this course builds on what you have already done.' });
  if (v.reasons !== 'clear') tips.push({ gain: 8 - reasons, text: 'Write down, in your own words, why this course and this university: modules, what you will learn, the job it leads to. Check them against the course page.' });
  if (v.gap === 'unexplained') tips.push({ gain: 6 - gap, text: 'Write a short, honest explanation of the gap and gather anything that backs it up, such as a course, a job, a medical or family reason.' });
  else if (v.gap === 'explained') tips.push({ gain: 6 - gap, text: 'Keep the proof for your gap together with your other documents.' });
  return { id: 'fit', label: 'Course fit and your story', score: link + reasons + gap, max, notes: notes.filter(Boolean) };
}

// Turns an English result into a number of points, and says whether it meets the visa score.
function englishFactor(eng, flags, tips) {
  const max = WEIGHTS.english;
  const e = eng && typeof eng === 'object' ? eng : {};
  const notes = [];
  const rule = ENGLISH[e.test];
  let score = 0;

  if (!e.test) {
    score = 3;
    notes.push('You have not added an English test in your profile yet.');
    tips.push({ gain: max - score, text: 'Add your English test in your profile. A valid score is part of a student visa application unless you are exempt.' });
  } else if (e.test === 'none') {
    score = 3;
    notes.push('You have no English test yet.');
    tips.push({ gain: max - score, text: `Book an English test. The usual visa score is ${ENGLISH.ielts.standard} on IELTS, ${ENGLISH.pte.standard} on PTE Academic or ${ENGLISH.toefl.standard} on TOEFL iBT. Your university may ask for more.` });
  } else if (!rule) {
    score = 6;
    notes.push('We cannot compare this test with the visa score.');
    tips.push({ gain: max - score, text: 'Check on the Home Affairs site that this test is accepted for the student visa. If it is not on the list, plan a test that is.' });
  } else if (e.status !== 'taken' || typeof e.overall !== 'number') {
    score = 6;
    notes.push(`You are planning ${rule.name}. The usual visa score is ${rule.standard}.`);
    tips.push({ gain: max - score, text: `Take the test and aim for ${round(rule.standard + rule.margin)} or more, so you have room above the visa score of ${rule.standard}.` });
  } else if (e.overall >= rule.standard + rule.margin) {
    score = max;
    notes.push(`Your ${rule.name} score of ${e.overall} is comfortably above the usual visa score of ${rule.standard}.`);
  } else if (e.overall >= rule.standard) {
    score = 11;
    notes.push(`Your ${rule.name} score of ${e.overall} meets the usual visa score of ${rule.standard}. Your course may ask for more.`);
    tips.push({ gain: max - score, text: 'Check your course page for its own English score. Many courses ask for more than the visa does.' });
  } else if (e.overall >= rule.pathway) {
    score = 6;
    notes.push(`Your ${rule.name} score of ${e.overall} is below the usual visa score of ${rule.standard}. It can work if you first study English or a pathway course, at the lower score of ${rule.pathway}.`);
    flags.push({ id: 'english_below', cap: 'amber', text: 'Your English score is below the usual visa score. The result stays Amber at best until you retake or take an English course first.' });
    tips.push({ gain: max - score, must: true, text: `Retake the test to reach ${rule.standard}, or ask your university about a package with at least 10 weeks of English before the main course.` });
  } else {
    score = 2;
    notes.push(`Your ${rule.name} score of ${e.overall} is below the lowest score the rules allow for a pathway.`);
    flags.push({ id: 'english_below', cap: 'amber', text: 'Your English score is well below the usual visa score. The result stays Amber at best.' });
    tips.push({ gain: max - score, must: true, text: 'Work on your English and retake the test before you apply. A language course first can be a way in.' });
  }
  return { id: 'english', label: 'English', score, max, notes };
}

function historyFactor(imm, now, flags, tips) {
  const max = WEIGHTS.history;
  const d = imm && typeof imm === 'object' ? imm : {};
  const notes = [];
  const year = new Date(now).getUTCFullYear();
  let score;
  if (d.history === 'none') {
    score = max;
    notes.push('No earlier visa problems.');
  } else if (d.history === 'some') {
    score = max;
    const items = Array.isArray(d.items) ? d.items : [];
    let cancelled = false, recentStudy = false;
    for (const it of items) {
      const age = year - (it.year || year);
      if (it.outcome === 'refused') {
        const cut = age <= 5 ? (it.kind === 'study' ? HISTORY.refusedStudy : HISTORY.refusedOther) : HISTORY.refusedOld;
        score -= cut;
        if (it.kind === 'study' && age <= HISTORY.recentYears) recentStudy = true;
      } else if (it.outcome === 'cancelled') { score -= HISTORY.cancelled; cancelled = true; }
      else if (it.outcome === 'withdrawn') score -= HISTORY.withdrawn;
    }
    score = Math.max(0, score);
    const n = items.filter((x) => x.outcome === 'refused').length;
    notes.push(items.length ? `You listed ${items.length} earlier application${items.length === 1 ? '' : 's'}${n ? `, ${n} refused` : ''}.` : 'You said you have something to add but have not listed it yet.');
    if (recentStudy) {
      flags.push({ id: 'recent_refusal', cap: 'amber', text: `A study visa refusal in the last ${HISTORY.recentYears} years keeps the result at Amber at best.` });
      tips.push({ gain: 0, must: true, text: 'Get the refusal reasons, understand them, and show in your answers what is different now. Applying again with the same case is unlikely to change the outcome.' });
    } else if (n) {
      tips.push({ gain: 0, text: 'Be ready to explain each refusal plainly and truthfully. Applications are checked against your history.' });
    }
    if (cancelled) {
      flags.push({ id: 'cancelled', cap: 'amber', text: 'A cancelled visa keeps the result at Amber at best.' });
      tips.push({ gain: 0, must: true, text: 'Get advice from a registered migration agent or a legal adviser before you apply. A cancellation needs a careful, honest explanation.' });
    }
  } else {
    score = HISTORY.unknown;
    notes.push(d.history === 'prefer_not' ? 'You chose not to say, so we have not counted this for or against you.' : 'You have not added this in your profile, so we have not counted it for or against you.');
    tips.push({ gain: max - score, text: 'Add your earlier visa history in your profile for a fuller result. Always answer the real application truthfully.' });
  }
  return { id: 'history', label: 'Visa history', score, max, notes };
}

function evidenceFactor(v, tips) {
  const max = WEIGHTS.evidence;
  const ties = [v.ties_family, v.ties_assets, v.ties_career].filter(Boolean).length;
  const docs = { ready: 4, some: 2, not_started: 0 }[v.docs] ?? 0;
  const trail = { documented: 5, some: 2, no: 0 }[v.funds_trail] ?? 0;
  const score = ties * 2 + docs + trail;
  const notes = [];
  notes.push(ties ? `${ties} of 3 ties to home you can show.` : 'No ties to home added yet.');
  notes.push({ ready: 'Your documents are ready.', some: 'Some documents are ready.', not_started: 'You have not started gathering documents.' }[v.docs] || '');
  notes.push({ documented: 'You can show where the money came from.', some: 'You can show part of where the money came from.', no: 'You cannot yet show where the money came from.' }[v.funds_trail] || '');
  if (ties < 3) tips.push({ gain: (3 - ties) * 2, text: 'List what ties you to home and keep proof: a family link, property or a business, or a job or career plan you will return to.' });
  if (v.funds_trail !== 'documented') tips.push({ gain: 5 - trail, text: 'Trace the money: bank statements, tax returns, sale papers or loan papers that show where it came from and how long it has been there.' });
  if (v.docs !== 'ready') tips.push({ gain: 4 - docs, text: 'Start your document checklist now, and use the Home Affairs checklist for your country. Evidence carries more weight than a statement alone.' });
  return { id: 'evidence', label: 'Ties and evidence', score, max, notes: notes.filter(Boolean) };
}

const RANK = { red: 0, amber: 1, green: 2 };

// sections: the student's saved sections { english, immigration, visa_au }. now: a time in ms (for "refused in the last 3 years").
export function assessAu(sections, now = Date.now()) {
  const s = sections && typeof sections === 'object' ? sections : {};
  const v = s.visa_au && typeof s.visa_au === 'object' ? s.visa_au : {};
  const missing = REQUIRED.filter((k) => v[k] === undefined || v[k] === null || v[k] === '');
  const base = { checked: CHECKED, checkedLabel: CHECKED_LABEL, sources: SOURCES };
  if (missing.length) return { ...base, complete: false, missing };

  const flags = [], tips = [];
  const factors = [
    fundsFactor(v, flags, tips),
    fitFactor(v, tips),
    englishFactor(s.english, flags, tips),
    historyFactor(s.immigration, now, flags, tips),
    evidenceFactor(v, tips),
  ];
  const score = factors.reduce((a, f) => a + f.score, 0);
  const byScore = score >= BANDS.green ? 'green' : score >= BANDS.amber ? 'amber' : 'red';
  // A flag can hold the band down. It can never raise it.
  const band = flags.reduce((b, f) => (RANK[f.cap] < RANK[b] ? f.cap : b), byScore);
  const actions = tips
    .filter((t) => t.text)
    .sort((a, b) => (b.must ? 1 : 0) - (a.must ? 1 : 0) || b.gain - a.gain)
    .slice(0, 5);

  return { ...base, complete: true, score, band, scoreBand: byScore, held: band !== byScore, flags, factors, actions, money: factors[0] };
}
