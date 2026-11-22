// The SOP builder: what a student is asked, how the answers are checked, which university facts a draft may use, and the
// draft itself. Plain functions with no site imports, so the server (to reject anything unexpected), the dashboard page and
// the tests all use this one file.
//
// The rule behind all of it: a draft says only what the student told us or what a checked source says. Where something is
// missing, the draft shows a gap for the student to fill. It never fills one itself.

export const NOTE_MAX = 700;
export const EDIT_MAX = 9000;
// How long the student wants the statement to be (words), and the range for a limit the university sets itself.
export const WORDS = [400, 600, 800];
export const WORDS_DEFAULT = 600;
export const LIMIT_MIN = 100;
export const LIMIT_MAX = 3000;
export const wordsTarget = (s) => (WORDS.includes(s && s.words) ? s.words : WORDS_DEFAULT);
export const FACT_MAX_AGE_DAYS = 365; // a source checked longer ago than this is not used in a draft
export const FACT_SOON_DAYS = 30; // within this many days of that limit, a fact is marked "Re-check soon"

const oneLine = (v, max) => String(v ?? '').replace(/[\u0000-\u001f\u007f\u2028\u2029]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, max);

// ---- what a student is asked ------------------------------------------------------------------------------------

// Each chip is [id, text]. {dest} becomes the destination's name and {course} the course name when the page is drawn.
const Q = {
  q1: {
    title: 'What first got you interested in this subject?', hint: 'Pick up to 2.', max: 2, ph: 'e.g. what you saw, who you helped',
    chips: [['project', 'A project at college'], ['job', 'A job or internship'], ['problem', 'A problem I noticed around me'], ['family', "Someone in my family's work"],
      ['course', 'A course or book'], ['event', 'A competition or event'], ['hobby', 'A hobby that became serious']],
  },
  q2: {
    title: 'Which work are you proudest of?', hint: 'Pick up to 2. Chips marked "profile" come from your account. Two or three sentences below make the draft fuller.', max: 2, ph: 'e.g. what you built and what changed',
    chips: [['intern', 'An internship task'], ['team', 'A team project'], ['paper', 'A research paper'], ['side', 'A side project of my own'], ['volunteer', 'Volunteer work']],
  },
  q3: {
    title: 'Is there anything in your record you want to explain?', hint: 'Pick all that apply, or choose none. A short honest note helps more than silence.', max: 3, ph: 'e.g. what happened and what you did next',
    chips: [['none', 'Nothing to explain'], ['lowmark', 'A low mark in one semester', 'I had a low mark in one semester.'], ['backlogs', 'Backlogs I later cleared', 'I had backlogs that I later cleared.'],
      ['studygap', 'A study gap', 'I had a gap in my studies.'], ['workgap', 'A work gap', 'I had a gap in my work.'], ['switch', 'I changed my field', 'I changed my field.']],
  },
  q4: {
    title: 'Why {dest} and this course?', hint: 'Pick up to 3. We add the verified course facts ourselves. Two or three sentences below make the draft fuller.', max: 3, ph: 'e.g. the part of the course that matters to you',
    chips: [['taught', 'The way it is taught', 'the way it is taught'], ['practical', 'Practical work and projects', 'its practical work and projects'], ['industry', 'Links with industry', 'its links with industry'],
      ['research', 'Research facilities', 'its research facilities'], ['psw', 'Post-study work options', 'the post-study work options'], ['cost', 'Cost and scholarships', 'the cost and scholarships'],
      ['safe', 'Safe and welcoming', 'how safe and welcoming it is'], ['content', 'The course content matches my goal', 'how well the course content matches my goal']],
  },
  q5: {
    title: 'What do you want to do after the course?', hint: 'Pick up to 2.', max: 2, ph: 'e.g. the kind of organisation or problem',
    chips: [], // roles for the subject area, then the two below
  },
  q6: {
    title: 'What will you bring to your classmates and campus?', hint: 'Pick up to 2.', max: 2, ph: 'e.g. a time you did this',
    chips: [['team', 'Teamwork'], ['lead', 'Leadership'], ['view', 'A different point of view'], ['community', 'Community or volunteer work'], ['skills', 'Technical skills'], ['mentor', 'Mentoring others']],
  },
};

// Roles by the course's subject area (the same eight groups as the course search). 'other' is used when the area is not known.
export const ROLES = {
  computing: [['r_analyst', 'Data analyst'], ['r_scientist', 'Data scientist'], ['r_swe', 'Software engineer'], ['r_ml', 'Machine learning engineer'], ['r_product', 'Product or business analyst'], ['r_research', 'Research or PhD']],
  business: [['r_biz', 'Business or financial analyst'], ['r_consult', 'Consultant'], ['r_market', 'Marketing or brand manager'], ['r_ops', 'Operations or supply chain manager'], ['r_venture', 'Start my own venture'], ['r_research', 'Research or PhD']],
  engineering: [['r_design', 'Design or R&D engineer'], ['r_project', 'Project or site engineer'], ['r_systems', 'Systems engineer'], ['r_process', 'Manufacturing or process engineer'], ['r_research', 'Research or PhD'], ['r_venture', 'Start my own venture']],
  health: [['r_clinic', 'Clinical or hospital role'], ['r_public', 'Public health or policy'], ['r_hdata', 'Health data or research'], ['r_research', 'Research or PhD'], ['r_venture', 'Start my own venture']],
  science: [['r_scientist2', 'Research scientist'], ['r_lab', 'Lab or technical specialist'], ['r_scientist', 'Data scientist'], ['r_research', 'Research or PhD'], ['r_teach', 'Teaching or outreach']],
  society: [['r_policy', 'Policy or public service'], ['r_legal', 'Legal or compliance role'], ['r_ngo', 'Development or non-profit work'], ['r_research', 'Research or PhD'], ['r_comms', 'Journalism or communications']],
  arts: [['r_creative', 'Designer or creative lead'], ['r_content', 'Producer or content strategist'], ['r_research', 'Research or PhD'], ['r_studio', 'Start my own studio or venture'], ['r_teach', 'Teaching or outreach']],
  humanities: [['r_teacher', 'Teacher or educator'], ['r_academic', 'Researcher or academic'], ['r_writer', 'Writer or editor'], ['r_policy', 'Policy or public service'], ['r_research', 'Research or PhD']],
  other: [['r_role', 'A role in my field'], ['r_research', 'Research or PhD'], ['r_venture', 'Start my own venture'], ['r_teach', 'Teaching or outreach']],
};
const WHERE = [['w_home', 'Work back in my home country'], ['w_dest', 'Work in {dest} first']];

export const TONES = [
  ['plain', 'Plain and direct', 'I like to say what I did and what came out of it, without extra words.'],
  ['warm', 'Warm and conversational', 'I have always been the person friends call when something needs sorting out, and I enjoy it.'],
  ['measured', 'Thoughtful and measured', 'I tend to think a problem through before I act, and I try to be clear about what I do not yet know.'],
];
export const ARCS = [
  ['moment', 'Start with a moment', 'Opens on what you wrote for question 1.'],
  ['interest', 'Start with what drew you', 'Opens on what first got you interested, then your own account.'],
  ['goal', 'Start with the goal', 'Opens on what you want to do after the course.'],
];
export const QIDS = ['q1', 'q2', 'q3', 'q4', 'q5', 'q6'];

// "the United States", "the Netherlands": the destinations that take an article when named in a sentence.
export const withThe = (id, name) => (['usa', 'uk', 'uae', 'netherlands'].includes(id) ? `the ${name}` : name);

const groupOf = (g) => (ROLES[g] ? g : 'other');
const fill = (t, ctx) => t.replace(/\{dest\}/g, ctx.destName || 'your destination').replace(/\{course\}/g, ctx.courseName || 'this course');

// The questions as the page draws them. ctx: { destName, courseName, group, profileChips: [text, ...] }
export function questions(ctx = {}) {
  const roles = ROLES[groupOf(ctx.group)];
  return QIDS.map((id) => {
    const q = Q[id];
    let chips = q.chips.map(([cid, text, say]) => ({ id: cid, text: fill(text, ctx), say: say ? fill(say, ctx) : '', own: false }));
    if (id === 'q2') chips = [...(ctx.profileChips || []).slice(0, 4).map((text) => ({ id: 'p:' + oneLine(text, 117), text: oneLine(text, 117), say: '', own: true })), ...chips];
    if (id === 'q5') chips = [...roles, ...WHERE].map(([cid, text]) => ({ id: cid, text: fill(text, ctx), say: '', own: false }));
    return { id, title: fill(q.title, ctx), hint: q.hint, max: q.max, placeholder: q.ph, chips };
  });
}

// ---- checking what was saved ------------------------------------------------------------------------------------

const staticIds = (qid) => (qid === 'q5' ? [...Object.values(ROLES).flat(), ...WHERE] : Q[qid].chips).map((c) => c[0]);

const COUNTRY_IDS = ['australia', 'canada', 'france', 'germany', 'ireland', 'malaysia', 'netherlands', 'new-zealand', 'norway', 'singapore', 'sweden', 'uae', 'uk', 'usa'];
const GROUP_IDS = ['health', 'business', 'computing', 'engineering', 'science', 'society', 'arts', 'humanities'];
const SLUG = /^[a-z0-9][a-z0-9-]{1,100}$/;

// Checks one student's SOP section. Returns { value, errors }. Anything not listed here is dropped.
export function cleanSop(input) {
  const src = input && typeof input === 'object' && !Array.isArray(input) ? input : {};
  const out = {};
  const errors = {};

  if (src.dest !== undefined && src.dest !== '') {
    if (COUNTRY_IDS.includes(src.dest)) out.dest = src.dest; else errors.dest = 'Choose a destination from the list.';
  }
  if (src.uni !== undefined && src.uni !== '') {
    if (typeof src.uni === 'string' && SLUG.test(src.uni)) out.uni = src.uni; else errors.uni = 'Choose a university from the list.';
  }
  if (out.uni) out.uni_name = oneLine(src.uni_name, 120);
  if (src.course_id) {
    const id = oneLine(src.course_id, 140);
    if (/^crs:[A-Za-z0-9._~/-]{1,130}$/.test(id)) out.course_id = id; else errors.course_id = 'Choose a course from the list.';
  }
  const cname = oneLine(src.course_name, 140);
  if (cname) out.course_name = cname;
  if (src.group !== undefined && src.group !== '') {
    if (GROUP_IDS.includes(src.group)) out.group = src.group; else errors.group = 'Choose a subject area from the list.';
  }

  const picks = {};
  const notes = {};
  const sp = src.picks && typeof src.picks === 'object' && !Array.isArray(src.picks) ? src.picks : {};
  const sn = src.notes && typeof src.notes === 'object' && !Array.isArray(src.notes) ? src.notes : {};
  for (const qid of QIDS) {
    if (qid in sp) {
      const arr = Array.isArray(sp[qid]) ? [...new Set(sp[qid].map((x) => oneLine(x, 120)))] : null;
      const ok = staticIds(qid);
      if (!arr) errors['picks.' + qid] = 'Choose from the options.';
      else if (arr.length > Q[qid].max) errors['picks.' + qid] = `Choose up to ${Q[qid].max}.`;
      else if (arr.some((x) => !(ok.includes(x) || (qid === 'q2' && x.startsWith('p:') && x.length > 2)))) errors['picks.' + qid] = 'Choose from the options.';
      else if (qid === 'q3' && arr.includes('none') && arr.length > 1) errors['picks.q3'] = '"Nothing to explain" cannot be chosen with another option.';
      else if (arr.length) picks[qid] = arr;
    }
    if (qid in sn) {
      const t = oneLine(sn[qid], NOTE_MAX + 1);
      if (t.length > NOTE_MAX) errors['notes.' + qid] = `Keep this under ${NOTE_MAX} characters.`;
      else if (t) notes[qid] = t;
    }
  }
  if (Object.keys(picks).length) out.picks = picks;
  if (Object.keys(notes).length) out.notes = notes;

  if (src.tone !== undefined && src.tone !== '') {
    if (TONES.some((t) => t[0] === src.tone)) out.tone = src.tone; else errors.tone = 'Choose one of the voices.';
  }
  if (src.arc !== undefined && src.arc !== '') {
    const n = Number(src.arc);
    if (Number.isInteger(n) && n >= 0 && n < ARCS.length) out.arc = n; else errors.arc = 'Choose one of the openings.';
  }
  if (src.words !== undefined && src.words !== '') {
    const n = Number(src.words);
    if (WORDS.includes(n)) out.words = n; else errors.words = 'Choose one of the lengths.';
  }
  if (src.limit !== undefined && src.limit !== '' && src.limit !== null) {
    const n = Number(src.limit);
    if (Number.isInteger(n) && n >= LIMIT_MIN && n <= LIMIT_MAX) out.limit = n; else errors.limit = `Enter a whole number from ${LIMIT_MIN} to ${LIMIT_MAX}, or leave it empty.`;
  }
  if (src.edited !== undefined && src.edited !== '') {
    // The student's own edited text. Line breaks are kept; other control characters are not.
    const t = String(src.edited).replace(/\r\n?/g, '\n').replace(/[\u0000-\u0009\u000b-\u001f\u007f\u2028\u2029]+/g, ' ').replace(/[ \t]+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim();
    if (t.length > EDIT_MAX) errors.edited = `Keep the text under ${EDIT_MAX} characters.`;
    else if (t) out.edited = t;
  }
  return { value: out, errors };
}

// ---- progress ---------------------------------------------------------------------------------------------------

export const courseChosen = (s) => !!(s && s.dest && s.uni && s.course_name);
export const storyDone = (s) => !!(s && QIDS.every((q) => s.picks?.[q]?.length > 0));
export const toneDone = (s) => !!(s && s.tone);
export const answersDone = (s) => storyDone(s) && toneDone(s);
// How many of the six questions have an answer, plus the voice as the seventh.
export const answered = (s) => QIDS.filter((q) => s?.picks?.[q]?.length > 0).length + (toneDone(s) ? 1 : 0);

// The profile parts a draft is built from. All four must be filled in before the builder opens.
export const PROFILE_GATE = [
  ['profile', 'About you'],
  ['academic', 'Education history'],
  ['english', 'English test'],
  ['work', 'Work experience'],
];

// The next step a student should be on. have: the sections that are done, e.g. { profile: true, academic: false, ... }
export function nextStep(have, s) {
  if (!PROFILE_GATE.every(([id]) => have[id])) return 'home';
  if (!courseChosen(s)) return 'start';
  if (!answersDone(s)) return 'story';
  return 'draft';
}

// ---- facts a draft may use --------------------------------------------------------------------------------------

const DAY = 86400000;
const parse = (iso) => { const t = Date.parse(String(iso || '').slice(0, 10) + 'T00:00:00Z'); return Number.isFinite(t) ? t : null; };
export const fmtDay = (iso) => {
  const t = parse(iso);
  return t === null ? '' : new Date(t).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
};

// How a fact stands today: 'verified', 'recheck' (the limit is near), or 'old' (past the limit: not used in a draft).
export function standing(checkedOn, now = Date.now()) {
  const t = parse(checkedOn);
  if (t === null) return 'old';
  const left = Math.floor((t + FACT_MAX_AGE_DAYS * DAY - now) / DAY);
  if (left < 0) return 'old';
  return left <= FACT_SOON_DAYS ? 'recheck' : 'verified';
}
export function validUntil(checkedOn) {
  const t = parse(checkedOn);
  return t === null ? '' : fmtDay(new Date(t + FACT_MAX_AGE_DAYS * DAY).toISOString());
}

const engText = (e) => (e && e.status === 'taken' && e.test && e.overall !== undefined && e.overall !== null ? { test: e.test, score: Number(e.overall) } : null);
const TEST_NAME = { ielts: 'IELTS', toefl: 'TOEFL iBT', pte: 'PTE Academic', duolingo: 'Duolingo English Test' };

// The facts for one chosen course. card: what /student/sop-data/<slug>.json says about the course
// ({ course?: { duration, months, ielts, src, on } }); sections: the student's profile.
// Each fact: { id, label, value, source, sourceUrl, checked, chip, num? }. chip is 'Verified', 'Re-check soon' or 'Your data'.
// Only a fact checked within the last year is returned, so a draft never rests on an old page.
export function factsFor(card, sections, now = Date.now()) {
  const facts = [];
  const c = card && card.course;
  const add = (id, label, value, src, on, extra = {}) => {
    const st = standing(on, now);
    if (st === 'old' || !value) return;
    facts.push({ id, label, value, source: hostOf(src), sourceUrl: src || '', checked: `Checked ${fmtDay(on)} · valid until ${validUntil(on)}`, chip: st === 'recheck' ? 'Re-check soon' : 'Verified', soon: st === 'recheck', ...extra });
  };
  if (c) {
    add('F1', 'Course length', c.duration, c.src, c.on);
    if (c.months && c.months.length) add('F2', 'Intake', c.months.join(', '), c.src, c.on);
    if (c.ielts !== null && c.ielts !== undefined) add('F3', 'English requirement', `IELTS overall ${c.ielts}`, c.src, c.on, { num: Number(c.ielts), test: 'ielts' });
  }
  const e = engText(sections && sections.english);
  if (e) facts.push({ id: 'P1', label: 'Your profile', value: `${TEST_NAME[e.test] || 'English test'} overall ${e.score}`, source: 'From your English test section', sourceUrl: '', checked: 'Entered by you', chip: 'Your data', own: true, num: e.score, test: e.test });
  return facts;
}

function hostOf(url) { try { return new URL(url).host.replace(/^www\./, '') + new URL(url).pathname.replace(/\/$/, ''); } catch { return ''; } }

// ---- the draft --------------------------------------------------------------------------------------------------

// A sentence is { t: text, k: 's' (the student's own words), 'f' (a checked fact) or 'g' (a gap), f: [fact ids] }.
const S = (t, k = 's', f = []) => ({ t, k, f });
const GAP = (t) => S(`[${t}]`, 'g');
const endStop = (x) => (/[.!?]$/.test(x) ? x : x + '.');
const list = (a, sep = ',') => (a.length <= 1 ? a.join('') : a.slice(0, -1).join(sep + ' ') + ' and ' + a.at(-1));
// "A project at college" -> "a project at college", but "I changed my field" and "Research or PhD" keep their capitals.
const lc = (x) => (/^(A|An|The)\s/.test(x) || /^[A-Z][a-z]/.test(x) ? x[0].toLowerCase() + x.slice(1) : x);

// The chips a student picked: [{ id, text, say }]. ctx comes from questions().
const picked = (qs, qid, picks) => {
  const q = qs.find((x) => x.id === qid);
  return (picks?.[qid] || []).map((id) => q.chips.find((c) => c.id === id) || (id.startsWith('p:') ? { id, text: id.slice(2), say: '' } : null)).filter(Boolean);
};

// ---- the student's profile as the backbone of the story --------------------------------------------------------

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const monthLabel = (ym) => { const m = /^(\d{4})-(\d{2})$/.exec(String(ym || '')); return m ? `${MONTHS[Number(m[2]) - 1]} ${m[1]}` : ''; };
const LEVEL = { class10: 'Class 10', class12: 'Class 12', diploma: 'my diploma', bachelors: "my Bachelor's degree", masters: "my Master's degree", other: 'my studies' };
const RANK = { class10: 1, class12: 2, diploma: 3, other: 3, bachelors: 4, masters: 5 };

// "78%", "a CGPA of 8.2 out of 10", "a GPA of 3.4 out of 4". Another grading system is not worded: we cannot say what it means.
function gradeText(a) {
  if (a.grade === undefined || a.grade === null || a.grade === '') return '';
  if (a.grade_type === 'percentage') return `${a.grade}%`;
  if (a.grade_type === 'cgpa10') return `a CGPA of ${a.grade} out of 10`;
  if (a.grade_type === 'gpa4') return `a GPA of ${a.grade} out of 4`;
  return '';
}

// The up-to-two highest qualifications, oldest first, as sentences in the student's own details.
function foundationLines(items) {
  const rows = (items || []).filter((a) => a && a.institution);
  rows.sort((x, y) => (RANK[y.level] || 0) - (RANK[x.level] || 0) || (Number(y.end_year) || 0) - (Number(x.end_year) || 0));
  const out = [];
  for (const a of rows.slice(0, 2).reverse()) {
    const what = LEVEL[a.level] || 'my studies';
    const field = a.field ? ` in ${a.field}` : '';
    const grade = gradeText(a);
    if (a.status === 'ongoing') {
      out.push(S(`I am studying ${what}${field} at ${a.institution}${a.end_year ? `, due to finish in ${a.end_year}` : ''}.`));
      if (grade) out.push(S(`My result so far is ${grade}.`));
    } else {
      out.push(S(`I completed ${what}${field} at ${a.institution}${a.end_year ? ` in ${a.end_year}` : ''}${grade ? `, with ${grade}` : ''}.`));
    }
  }
  return out;
}

const workChipText = (w) => `My work as ${w.title} at ${w.employer}`;
const workChipId = (w) => 'p:' + oneLine(workChipText(w), 117);
const when = (w) => { const a = monthLabel(w.start), b = monthLabel(w.end); return a ? (b ? `${a} to ${b}` : `since ${a}`) : ''; };

// The student's jobs, oldest first (up to two), as sentences. A job the student picked as their proudest work is left out
// here, because the "proudest" sentence names it, with its dates.
function workLines(items, skipIds) {
  const out = [];
  for (const w of (items || []).filter((x) => x && x.employer && x.title).slice(0, 2).reverse()) {
    if (skipIds.includes(workChipId(w))) continue;
    const d = when(w) ? `, ${when(w).startsWith('since') ? '' : 'from '}${when(w)}` : '';
    if (w.type === 'internship') out.push(S(`I did an internship as ${w.title} at ${w.employer}${d}.`));
    else if (w.type === 'part_time') out.push(S(`I worked part time as ${w.title} at ${w.employer}${d}.`));
    else if (w.type === 'self_employed') out.push(S(`I worked for myself as ${w.title} (${w.employer})${d}.`));
    else out.push(S(`I worked as ${w.title} at ${w.employer}${d}.`));
  }
  return out;
}

// ---- the draft --------------------------------------------------------------------------------------------------

// Builds the draft from the answers and the profile, as a story in six paragraphs:
//   1 where the interest began   2 the education behind it   3 the work and projects   4 why this course and university
//   5 what comes after           6 what they bring, returning to where it began
// Deterministic: the same answers always give the same draft, and the draft holds nothing that is not an answer, the
// student's own profile, a checked fact or a gap. (Writing in the student's chosen voice and length comes later.)
// ctx: { destName, courseName, uniName, group, profileChips, academic: [...], work: [...] } (the last two are the profile items)
export function buildDraft(s, ctx, facts) {
  const qs = questions(ctx);
  const pk = s.picks || {};
  const nt = s.notes || {};
  const fact = (id) => facts.find((f) => f.id === id);
  const uni = ctx.uniName || 'the university';
  const course = ctx.courseName || 'this course';
  const own = (t) => (t ? S(endStop(t)) : null);
  const gapMoment = () => GAP('Add what you saw or did that first interested you: one or two sentences');

  const interest = picked(qs, 'q1', pk);
  const interestList = interest.length ? list(interest.map((c) => lc(c.text))) : '';
  const interestLine = interest.length ? S(`My interest in this subject started with ${interestList}.`) : null;
  const moment = own(nt.q1) || gapMoment();

  const roles = picked(qs, 'q5', pk).filter((c) => c.id.startsWith('r_'));
  const where = picked(qs, 'q5', pk).filter((c) => c.id.startsWith('w_'));
  const goal = [];
  if (roles.length) goal.push(S(`After the course I am looking at these paths: ${roles.map((c) => lc(c.text)).join('; ')}.`));
  if (where.some((c) => c.id === 'w_dest')) goal.push(S(`I would like to work in ${ctx.destName || 'the destination country'} first.`));
  if (where.some((c) => c.id === 'w_home')) goal.push(S('I plan to work back in my home country.'));
  if (!goal.length) goal.push(GAP('Add what you want to do after the course'));

  // 1. the opening
  const arc = ARCS[s.arc || 0][0];
  let opening;
  if (arc === 'moment') opening = [moment, interestLine];
  else if (arc === 'interest') opening = [interestLine, moment];
  else opening = [...goal, interestLine, own(nt.q1)];

  // 2. the education behind it, and anything in the record the student wants to explain
  const education = foundationLines(ctx.academic);
  if (!education.length) education.push(GAP('Add where you studied and what you completed'));
  const rec = picked(qs, 'q3', pk).filter((c) => c.id !== 'none');
  if (rec.length) {
    for (const c of rec) education.push(S(c.say));
    education.push(own(nt.q3) || GAP('Add a short, honest explanation: what happened and what you did next'));
  }

  // 3. the work and projects
  const proud = picked(qs, 'q2', pk);
  const workItems = ctx.work || [];
  const proudText = (c) => {
    const w = workItems.find((x) => x && x.employer && x.title && workChipId(x) === c.id);
    return lc(c.text) + (w && when(w) ? ` (${when(w)})` : '');
  };
  const experience = [...workLines(workItems, proud.map((c) => c.id))];
  if (proud.length) experience.push(S(`The work I am proudest of is ${list(proud.map(proudText))}.`));
  experience.push(own(nt.q2) || GAP('Add what you did and what changed because of it: numbers help if you have them'));

  // 4. why this course and university
  const why = [S(`I am applying for the ${course} at ${uni}.`)];
  const f1 = fact('F1'), f2 = fact('F2'), f3 = fact('F3'), p1 = fact('P1');
  if (f1 || f2) {
    const bits = [];
    if (f1) bits.push(`takes ${f1.value}`);
    if (f2) bits.push(`has intakes in ${list(f2.value.split(', '))}`);
    why.push(S(`The course ${bits.join(', and ')}.`, 'f', [f1 && 'F1', f2 && 'F2'].filter(Boolean)));
  }
  const reasons = picked(qs, 'q4', pk).map((c) => c.say).filter(Boolean);
  if (reasons.length) why.push(S(`I chose it for ${list(reasons)}.`));
  why.push(own(nt.q4) || GAP('Add the part of the course that matters to you, and why'));
  // Said only when both numbers are on the page and the score meets the requirement. A score below it is not mentioned here.
  if (f3 && p1 && f3.test === p1.test && p1.num >= f3.num) why.push(S(`My ${p1.value.replace(/ overall /, ' overall score of ')} meets the course requirement of ${f3.num}.`, 'f', ['F3', 'P1']));

  // 5. what comes after (when the draft opens with the goal, the goal has been said already)
  const after = [...(arc === 'goal' ? [] : goal), own(nt.q5)];

  // 6. what they bring, and back to where it began
  const bring = picked(qs, 'q6', pk);
  const close = [];
  if (bring.length) close.push(S(`On campus I will bring ${list(bring.map((c) => lc(c.text)))}.`));
  close.push(own(nt.q6));
  if (interestList) close.push(S(`It began with ${interestList}, and I want to take it further at ${uni}.`));

  return [opening, education, experience, why, after, close].map((p) => p.filter(Boolean)).filter((p) => p.length).map((items) => ({ items }));
}

// Counts for the panel beside the draft.
export function checks(paras, facts) {
  const sents = paras.flatMap((p) => p.items);
  const used = new Set(sents.flatMap((x) => x.f));
  const theirs = facts.filter((f) => !f.own);
  const usedChecked = theirs.filter((f) => used.has(f.id));
  return {
    factsUsed: usedChecked.length,
    factsFresh: usedChecked.filter((f) => !f.soon).length,
    own: sents.filter((x) => x.k === 's').length,
    gaps: sents.filter((x) => x.k === 'g').length,
  };
}

export const draftText = (paras) => paras.map((p) => p.items.map((x) => x.t).join(' ')).join('\n\n');
export const wordCount = (text) => (String(text).replace(/\[[^\]]*\]/g, ' ').match(/\S+/g) || []).length;
