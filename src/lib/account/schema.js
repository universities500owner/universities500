// What a student account stores, and how each piece is checked.
// This one file is used by the server (to reject anything unexpected before it is saved) and by the
// dashboard pages (to draw the forms and the same error messages), so the two can never drift apart.
// It holds no secrets and imports nothing, so it is safe to ship to the browser.

export const CONSENT_VERSION = 'draft-2026-11';

// Where the student is on their way. The site does not take applications, so this tells us what help is useful.
export const STAGES = [
  ['exploring', 'Just exploring', 'Comparing countries, courses and costs.'],
  ['applying', 'Started applying', 'Preparing or sending applications.'],
  ['offer', 'Have an offer', 'Deciding which offer to accept.'],
  ['accepted', 'Accepted an offer', 'Sorting out the deposit, funds and documents.'],
  ['visa', 'At the visa stage', 'Preparing for or waiting on a student visa.'],
];

export const LEVELS = [
  ['foundation', 'Foundation or pathway'],
  ['diploma', 'Diploma'],
  ['bachelors', "Bachelor's degree"],
  ['masters', "Master's degree"],
  ['mba', 'MBA'],
  ['phd', 'PhD or research'],
];

// The same destinations as the guides (tests/account-schema.test.mjs checks this list against src/data/guides.json).
export const COUNTRIES = [
  ['australia', 'Australia'], ['canada', 'Canada'], ['france', 'France'], ['germany', 'Germany'], ['ireland', 'Ireland'],
  ['malaysia', 'Malaysia'], ['netherlands', 'Netherlands'], ['new-zealand', 'New Zealand'], ['norway', 'Norway'],
  ['singapore', 'Singapore'], ['sweden', 'Sweden'], ['uae', 'United Arab Emirates'], ['uk', 'United Kingdom'], ['usa', 'United States'],
];

// The same groups as the course search (tests/account-schema.test.mjs checks this against src/data/subjects.json).
export const SUBJECT_GROUPS = [
  ['health', 'Health and medicine'], ['business', 'Business and finance'], ['computing', 'Computing and data'],
  ['engineering', 'Engineering'], ['science', 'Science and maths'], ['society', 'Society, law and policy'], ['arts', 'Arts, media and design'],
  ['humanities', 'Humanities and education'],
];

const ids = (list) => list.map((x) => x[0]);

// ---- small checkers -------------------------------------------------------------------------------------------

// One line of plain text: no control characters or line breaks, collapsed spaces.
export const oneLine = (v) => String(v ?? '').replace(/[\u0000-\u001f\u007f\u2028\u2029]+/g, ' ').replace(/\s+/g, ' ').trim();

const YEAR_MIN = 1950;
const YEAR_MAX = 2045;
const blank = (v) => v === undefined || v === null || (typeof v === 'string' && v.trim() === '');

// Checks one field. Returns { value } (value undefined when left empty) or { error }.
export function cleanField(f, raw) {
  if (f.type === 'check') return { value: raw === true || raw === 'true' || raw === 'on' };
  if (blank(raw)) return f.required ? { error: f.requiredMsg || 'Fill this in.' } : { value: undefined };
  switch (f.type) {
    case 'text': {
      const s = oneLine(raw);
      if (s.length > f.max) return { error: `Keep this under ${f.max} characters.` };
      return { value: s };
    }
    case 'select': {
      const s = oneLine(raw);
      if (!f.options.some((o) => o[0] === s)) return { error: 'Choose one of the options.' };
      return { value: s };
    }
    case 'year': {
      const n = Number(raw);
      if (!Number.isInteger(n) || n < (f.min ?? YEAR_MIN) || n > (f.max ?? YEAR_MAX)) return { error: `Enter a year between ${f.min ?? YEAR_MIN} and ${f.max ?? YEAR_MAX}.` };
      return { value: n };
    }
    case 'month': {
      const s = oneLine(raw);
      const m = /^(\d{4})-(0[1-9]|1[0-2])$/.exec(s);
      if (!m || Number(m[1]) < YEAR_MIN || Number(m[1]) > YEAR_MAX) return { error: 'Choose a month and year.' };
      return { value: s };
    }
    case 'number': {
      const n = Number(raw);
      if (!Number.isFinite(n)) return { error: 'Enter a number.' };
      if ((f.min !== undefined && n < f.min) || (f.max !== undefined && n > f.max)) return { error: `Enter a number from ${f.min} to ${f.max}.` };
      if (f.int && !Number.isInteger(n)) return { error: 'Enter a whole number.' };
      return { value: n };
    }
    default:
      return { error: 'Unsupported field.' };
  }
}

// Checks a flat object against a field list. Fields hidden by show(values) are dropped.
function cleanObject(fields, input, path, errors) {
  const src = input && typeof input === 'object' && !Array.isArray(input) ? input : {};
  const out = {};
  // First pass: every field that is not conditional, so show() can look at the cleaned values.
  for (const pass of [0, 1]) {
    for (const f of fields) {
      if ((pass === 0) === !!f.show) continue;
      if (f.show && !f.show(out)) continue;
      const r = cleanField(f, src[f.id]);
      if (r.error) errors[path + f.id] = r.error;
      else if (r.value !== undefined && !(f.type === 'check' && r.value === false)) out[f.id] = r.value;
    }
  }
  return out;
}

// ---- the sections ----------------------------------------------------------------------------------------

const GRADE_TYPES = [['percentage', 'Percentage'], ['cgpa10', 'CGPA out of 10'], ['gpa4', 'GPA out of 4'], ['other', 'Other grading']];
const GRADE_MAX = { percentage: 100, cgpa10: 10, gpa4: 4, other: 1000 };

// English test score ranges: [min, max, step]. Duolingo has no separate skill scores.
export const ENGLISH_TESTS = [
  ['none', 'No test yet'], ['ielts', 'IELTS'], ['toefl', 'TOEFL iBT'], ['pte', 'PTE Academic'], ['duolingo', 'Duolingo English Test'], ['other', 'Another test'],
];
export const ENGLISH_RANGES = {
  ielts: { overall: [0, 9, 0.5], skill: [0, 9, 0.5] },
  toefl: { overall: [0, 120, 1], skill: [0, 30, 1] },
  pte: { overall: [10, 90, 1], skill: [10, 90, 1] },
  duolingo: { overall: [10, 160, 5], skill: null },
  other: { overall: [0, 1000, 0.5], skill: null },
};
const SKILLS = ['listening', 'reading', 'writing', 'speaking'];
const taken = (d) => d.test && d.test !== 'none' && d.status === 'taken';
const hasSkills = (d) => taken(d) && !!ENGLISH_RANGES[d.test]?.skill;

export const SECTIONS = {
  profile: {
    label: 'About you',
    blurb: 'The basics. Nothing here is shared with anyone.',
    fields: [
      { id: 'full_name', type: 'text', label: 'Full name', max: 100, required: true, requiredMsg: 'Enter your full name.', autocomplete: 'name' },
      { id: 'birth_year', type: 'year', label: 'Year of birth', min: 1950, max: 2030, required: true, requiredMsg: 'Enter the year you were born.', hint: 'The year only. You must be 18 or older to use an account.' },
      { id: 'nationality', type: 'text', label: 'Nationality', max: 60, required: true, requiredMsg: 'Enter your nationality.', placeholder: 'For example, Indian' },
      { id: 'city', type: 'text', label: 'City where you live', max: 60 },
    ],
    // Accounts are for adults. Only the year is asked, so this is a simple check against this year.
    check(d, at, errors, now = Date.now()) {
      if (d.birth_year && d.birth_year > new Date(now).getUTCFullYear() - 18) errors[at + 'birth_year'] = 'Accounts are for people aged 18 or older.';
    },
  },

  academic: {
    label: 'Academic history',
    blurb: 'Add each qualification you have finished or are studying now, latest first. Marks are used to check course entry requirements.',
    fields: [],
    list: {
      key: 'items', max: 6, noun: 'qualification', addLabel: 'Add a qualification',
      fields: [
        { id: 'level', type: 'select', label: 'Qualification', required: true, requiredMsg: 'Choose the qualification.', options: [['class10', 'Class 10 (secondary)'], ['class12', 'Class 12 (higher secondary)'], ['diploma', 'Diploma'], ['bachelors', "Bachelor's degree"], ['masters', "Master's degree"], ['other', 'Something else']] },
        { id: 'institution', type: 'text', label: 'School, college or university', max: 120, required: true, requiredMsg: 'Enter the name of the school or college.' },
        { id: 'field', type: 'text', label: 'Subject or stream', max: 100, placeholder: 'For example, Computer Science' },
        { id: 'status', type: 'select', label: 'Status', required: true, requiredMsg: 'Choose a status.', options: [['completed', 'Completed'], ['ongoing', 'Still studying']] },
        { id: 'start_year', type: 'year', label: 'Started', min: 1980, max: 2035 },
        { id: 'end_year', type: 'year', label: 'Finished, or expected to finish', min: 1980, max: 2040 },
        { id: 'grade_type', type: 'select', label: 'How your result is shown', options: GRADE_TYPES },
        { id: 'grade', type: 'number', label: 'Result so far', show: (d) => !!d.grade_type, min: 0, max: 1000, hint: 'For example 78 for a percentage, or 8.2 for a CGPA out of 10.' },
        { id: 'backlogs', type: 'number', label: 'Subjects not cleared yet', int: true, min: 0, max: 99, show: (d) => d.level === 'bachelors' || d.level === 'masters' || d.level === 'diploma', hint: 'Leave empty if none.' },
      ],
      check(item, at, errors) {
        if (item.start_year && item.end_year && item.end_year < item.start_year) errors[at + 'end_year'] = 'The finish year cannot be before the start year.';
        if (item.grade !== undefined && item.grade_type && item.grade > GRADE_MAX[item.grade_type]) errors[at + 'grade'] = `This cannot be more than ${GRADE_MAX[item.grade_type]} for that grading.`;
      },
    },
  },

  english: {
    label: 'English test',
    blurb: 'Tell us which English test you plan to take or have taken.',
    fields: [
      { id: 'test', type: 'select', label: 'English test', required: true, requiredMsg: 'Choose a test, or "No test yet".', options: ENGLISH_TESTS },
      { id: 'other_name', type: 'text', label: 'Name of the test', max: 40, show: (d) => d.test === 'other', required: true, requiredMsg: 'Enter the name of the test.' },
      { id: 'status', type: 'select', label: 'Where are you with it?', required: true, requiredMsg: 'Choose where you are with the test.', show: (d) => !!d.test && d.test !== 'none', options: [['planned', 'Planning to take it'], ['booked', 'Test date booked'], ['taken', 'Taken it, I have a score']] },
      { id: 'date', type: 'month', label: 'Test month', show: (d) => d.test && d.test !== 'none' && !!d.status },
      { id: 'overall', type: 'number', label: 'Overall score', show: taken, required: true, requiredMsg: 'Enter your overall score.' },
      ...SKILLS.map((s) => ({ id: s, type: 'number', label: s[0].toUpperCase() + s.slice(1), show: hasSkills })),
    ],
    check(d, at, errors) {
      const r = ENGLISH_RANGES[d.test];
      if (!r || !taken(d)) return;
      const bad = (v, [lo, hi, step]) => v < lo || v > hi || Math.abs(v / step - Math.round(v / step)) > 1e-9;
      const say = ([lo, hi, step]) => `Enter a score from ${lo} to ${hi}${step < 1 ? ` in steps of ${step}` : step > 1 ? ` in steps of ${step}` : ''}.`;
      if (d.overall !== undefined && bad(d.overall, r.overall)) errors[at + 'overall'] = say(r.overall);
      if (r.skill) for (const s of SKILLS) if (d[s] !== undefined && bad(d[s], r.skill)) errors[at + s] = say(r.skill);
    },
  },

  work: {
    label: 'Work experience',
    blurb: 'Jobs, internships and self-employment, latest first. Skip this if you have not worked yet.',
    fields: [{ id: 'none', type: 'check', label: 'I have no work experience yet' }],
    list: {
      key: 'items', max: 8, noun: 'job', addLabel: 'Add a job', show: (d) => !d.none,
      fields: [
        { id: 'employer', type: 'text', label: 'Employer', max: 120, required: true, requiredMsg: 'Enter the employer.' },
        { id: 'title', type: 'text', label: 'Job title', max: 100, required: true, requiredMsg: 'Enter your job title.' },
        { id: 'type', type: 'select', label: 'Type of work', options: [['full_time', 'Full time'], ['part_time', 'Part time'], ['internship', 'Internship'], ['self_employed', 'Self-employed']] },
        { id: 'start', type: 'month', label: 'Started', required: true, requiredMsg: 'Choose the month you started.' },
        { id: 'end', type: 'month', label: 'Ended', hint: 'Leave empty if you still work here.' },
      ],
      check(item, at, errors) {
        if (item.start && item.end && item.end < item.start) errors[at + 'end'] = 'The end month cannot be before the start month.';
      },
    },
  },

  immigration: {
    label: 'Immigration history',
    blurb: 'Optional. Earlier visa applications matter for later ones, so this helps us give you a fair self-check. Do not enter passport or visa numbers.',
    fields: [
      { id: 'history', type: 'select', label: 'Any earlier visa applications or immigration problems?', required: true, requiredMsg: 'Choose an answer, or "Prefer not to say".', options: [['none', 'No, none'], ['some', 'Yes, I have something to add'], ['prefer_not', 'Prefer not to say']] },
      { id: 'travel', type: 'text', label: 'Countries you have travelled to', max: 200, show: (d) => d.history === 'none' || d.history === 'some', placeholder: 'For example, Singapore, UAE', hint: 'Optional.' },
    ],
    list: {
      key: 'items', max: 10, noun: 'application', addLabel: 'Add an application', show: (d) => d.history === 'some',
      fields: [
        { id: 'country', type: 'text', label: 'Country applied to', max: 60, required: true, requiredMsg: 'Enter the country.' },
        { id: 'year', type: 'year', label: 'Year', min: 1990, max: 2035, required: true, requiredMsg: 'Enter the year.' },
        { id: 'kind', type: 'select', label: 'Type of visa', required: true, requiredMsg: 'Choose the type of visa.', options: [['study', 'Study'], ['visit', 'Visit or tourist'], ['work', 'Work'], ['other', 'Other']] },
        { id: 'outcome', type: 'select', label: 'What happened', required: true, requiredMsg: 'Choose what happened.', options: [['granted', 'Granted'], ['refused', 'Refused'], ['cancelled', 'Cancelled'], ['withdrawn', 'Withdrawn by me']] },
      ],
    },
  },

  // Answers for the Australian student visa self-check (/student/visa-check/). Not a profile page section: the visa page asks for it.
  // What the check needs that the profile does not already hold. English and visa history are read from the sections above.
  visa_au: {
    label: 'Visa self-check: Australia',
    blurb: 'Answers for the Australian student visa self-check. Do not enter passport numbers, visa numbers or bank account numbers.',
    fields: [
      { id: 'tuition', group: 'Money for your first year', type: 'number', int: true, min: 0, max: 400000, label: 'Tuition for your first 12 months (AUD)', required: true, requiredMsg: 'Enter the tuition fee, or 0 if it is fully covered.', hint: 'From your offer letter or the university fee page. For a course shorter than a year, enter the whole course fee.' },
      { id: 'funds', type: 'number', int: true, min: 0, max: 5000000, label: 'Money you can show (AUD)', required: true, requiredMsg: 'Enter the amount you can show, or 0 if none yet.', hint: 'Savings, fixed deposits, a sanctioned education loan and a scholarship you hold. Convert to Australian dollars.' },
      { id: 'funds_status', type: 'select', label: 'Where is that money?', required: true, requiredMsg: 'Choose where the money is.', options: [['ready', 'In an account, or a loan that is already sanctioned'], ['partial', 'Part is ready, the rest is in progress'], ['planned', 'Not arranged yet']] },
      { id: 'funds_trail', type: 'select', label: 'Can you show where the money came from?', required: true, requiredMsg: 'Choose an answer.', options: [['documented', 'Yes, I have the papers (statements, tax returns, loan papers)'], ['some', 'Some of it'], ['no', 'Not yet']] },
      { id: 'partner', type: 'check', label: 'My partner is coming with me' },
      { id: 'children', type: 'number', int: true, min: 0, max: 8, label: 'Children coming with you', hint: 'Leave empty if none.' },
      { id: 'school_children', type: 'number', int: true, min: 0, max: 8, label: 'How many of them are of school age?', show: (d) => (d.children || 0) > 0 },
      { id: 'course_link', group: 'Your course and your story', type: 'select', label: 'Is this course related to what you studied or did before?', required: true, requiredMsg: 'Choose an answer.', options: [['related', 'Yes, it follows from it'], ['partly', 'Partly'], ['unrelated', 'No, it is a change of direction']] },
      { id: 'reasons', type: 'select', label: 'Can you explain why this course and this university?', required: true, requiredMsg: 'Choose an answer.', options: [['clear', 'Yes, with specifics (modules, skills, the job it leads to)'], ['general', 'In general terms'], ['not_yet', 'Not yet']] },
      { id: 'gap', type: 'select', label: 'Is there a gap of more than a year in your study or work?', required: true, requiredMsg: 'Choose an answer.', options: [['none', 'No gap'], ['explained', 'Yes, and I can explain it with proof'], ['unexplained', 'Yes, and I cannot explain it well yet']] },
      { id: 'ties_family', group: 'Ties to home and your documents', type: 'check', label: 'Close family stays in my home country' },
      { id: 'ties_assets', type: 'check', label: 'I own property or a business at home' },
      { id: 'ties_career', type: 'check', label: 'I have a job or a clear career plan to return to' },
      { id: 'docs', type: 'select', label: 'How are your documents?', required: true, requiredMsg: 'Choose an answer.', options: [['ready', 'Ready'], ['some', 'Some are ready'], ['not_started', 'Not started']] },
    ],
    check(d, at, errors) {
      if ((d.school_children || 0) > (d.children || 0)) errors[at + 'school_children'] = 'This cannot be more than the number of children.';
    },
  },
};

// Every section that is stored, and the ones that are filled in on the profile page (the rest have their own page).
export const SECTION_IDS = Object.keys(SECTIONS);
export const PROFILE_SECTION_IDS = ['profile', 'academic', 'english', 'work', 'immigration'];

// Checks one section's data. Returns { value, errors }. errors is empty when the data is fine.
// Error keys are field ids, or "items.2.institution" for a field inside a list entry.
export function cleanSection(name, input, now = Date.now()) {
  const spec = SECTIONS[name];
  if (!spec) return { value: {}, errors: { _: 'Unknown section.' } };
  const errors = {};
  const src = input && typeof input === 'object' && !Array.isArray(input) ? input : {};
  const value = cleanObject(spec.fields, src, '', errors);
  if (spec.check && spec.fields.length) spec.check(value, '', errors, now);
  if (spec.list) {
    const l = spec.list;
    if (!l.show || l.show(value)) {
      const rows = Array.isArray(src[l.key]) ? src[l.key] : [];
      if (rows.length > l.max) errors[l.key] = `Add up to ${l.max} entries.`;
      value[l.key] = rows.slice(0, l.max).map((row, i) => {
        const at = `${l.key}.${i}.`;
        const item = cleanObject(l.fields, row, at, errors);
        if (l.check) l.check(item, at, errors);
        return item;
      });
    }
  }
  return { value, errors };
}

// ---- the plans part (stored on the student row) ---------------------------------------------------------------

const PLAN_FIELDS = {
  display_name: { type: 'text', max: 60 },
  level: { type: 'select', options: LEVELS },
  stage: { type: 'select', options: STAGES },
};

// Checks the fields of the student row a student may change. Only keys that are present are checked.
// Returns { value, errors }. value uses the database column names; a cleared choice becomes null.
export function cleanStudent(input) {
  const src = input && typeof input === 'object' && !Array.isArray(input) ? input : {};
  const value = {};
  const errors = {};
  for (const [k, f] of Object.entries(PLAN_FIELDS)) {
    if (!(k in src)) continue;
    const r = cleanField(f, src[k]);
    if (r.error) errors[k] = r.error;
    else value[k] = r.value === undefined ? null : r.value;
  }
  const list = (key, allowed, max) => {
    if (!(key in src)) return;
    const v = src[key];
    if (!Array.isArray(v)) { errors[key] = 'Choose from the list.'; return; }
    const seen = [...new Set(v.map((x) => oneLine(x)))];
    if (seen.length > max) errors[key] = `Choose up to ${max}.`;
    else if (seen.some((x) => !allowed(x))) errors[key] = 'Choose from the list.';
    else value[key] = seen;
  };
  const countryIds = new Set(ids(COUNTRIES));
  const groupIds = new Set(ids(SUBJECT_GROUPS));
  list('countries', (x) => countryIds.has(x), COUNTRIES.length);
  list('subject_groups', (x) => groupIds.has(x), SUBJECT_GROUPS.length);
  list('subjects', (x) => /^[a-z0-9-]{2,40}$/.test(x), 12);
  if ('marketing_opt_in' in src) value.marketing_opt_in = src.marketing_opt_in === true;
  return { value, errors };
}

// ---- progress -------------------------------------------------------------------------------------------------

export function sectionDone(name, data) {
  const d = data && typeof data === 'object' ? data : {};
  switch (name) {
    case 'profile': return !!(d.full_name && d.nationality && d.birth_year);
    case 'academic': return Array.isArray(d.items) && d.items.length > 0;
    case 'english': return !!d.test && (d.test === 'none' || !!d.status);
    case 'work': return !!d.none || (Array.isArray(d.items) && d.items.length > 0);
    case 'immigration': return !!d.history;
    case 'visa_au': return SECTIONS.visa_au.fields.filter((f) => f.required).every((f) => d[f.id] !== undefined && d[f.id] !== null && d[f.id] !== '');
    default: return false;
  }
}

export const plansDone = (s) => !!(s && s.countries?.length && s.level && s.subject_groups?.length && s.stage);

export const label = (list, id) => (list.find((x) => x[0] === id) || [])[1] || '';
