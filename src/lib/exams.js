// Exam guides: the seven tests a student may need. One record per exam, one shared set of steps and reminders.
// Facts were written by the site owner and re-checked against the test providers' published pages on CHECKED.
// Formats and scores change. Every page tells the reader to confirm with the test provider.
export const CHECKED = '2026-11-16';
export const CHECKED_LABEL = '16 November 2026';

export const GROUPS = {
  english: { label: 'English tests', blurb: 'Show a university or visa office that your English is strong enough for study.' },
  admissions: { label: 'Admissions tests', blurb: 'Show academic readiness for a bachelor’s, a master’s, a PhD or business school.' },
};

export const STEPS = [
  ['Confirm the requirement.', 'Check the exact test name and score required by your university and visa route.'],
  ['Create your test-provider account.', 'Enter your legal details exactly as shown on your accepted identification document.'],
  ['Choose test mode and date.', 'Confirm local availability, test-centre or online conditions, and the rules for your selected mode.'],
  ['Review fees and policies.', 'Check current local fees, rescheduling, cancellation and retake rules before paying.'],
  ['Plan score delivery.', 'Allow time for results and official score reporting before university deadlines.'],
];

export const SHARED = {
  before: 'Check the exact course requirement, accepted test version, delivery mode, minimum overall score and any section minimums. University admission and visa requirements may be different.',
  important: 'Do not book an exam simply because it is popular in your destination. Start with the requirements of your shortlisted universities and programmes.',
  scoreTip: 'There is no universal score that guarantees admission. Use the official entry requirements and published class profile for each course you plan to apply to.',
  prepTip: 'Take an official sample test or mock, identify your weakest areas and set a realistic study schedule around your application deadlines.',
  fees: 'Fees, dates, result timelines and delivery options can change by country and test provider. Confirm current details before booking.',
  resources: 'Use the official provider site for booking, the latest policies, practice materials and account management.',
};

export const exams = [
  {
    slug: 'ielts-academic',
    name: 'IELTS Academic',
    short: 'IELTS',
    group: 'english',
    level: 'English test, all degree levels',
    title: 'IELTS Academic: the English test for university study',
    lead: 'Understand IELTS Academic before you book: the four test sections, band scoring, registration considerations and a practical preparation plan for university applicants.',
    stats: [
      { v: '2h 45m', l: 'Approximate total test time' },
      { v: '4 skills', l: 'Listening, Reading, Writing, Speaking' },
      { v: '0–9', l: 'Band score scale' },
      { v: '2 years', l: 'Recommended result validity' },
    ],
    what: 'IELTS Academic assesses whether your English is suitable for an academic environment. It is commonly used for undergraduate and postgraduate study and some professional registration routes.',
    who: 'Students applying to English-taught higher education programmes where IELTS Academic is accepted. For university admission, Academic is commonly the relevant IELTS test; General Training serves different purposes.',
    pattern: [
      ['Listening', 'About 30 min', 'Four recordings; answer questions on conversations, monologues, detail and main ideas.'],
      ['Reading', '60 min', 'Three academic-style passages with questions on comprehension, detail, inference and argument.'],
      ['Writing', '60 min', 'Task 1: describe or summarise visual information. Task 2: write an essay responding to a point of view, argument or problem.'],
      ['Speaking', '11–14 min', 'Live examiner interview in three parts: introduction, individual long turn and discussion.'],
    ],
    scoring: 'You receive individual band scores for Listening, Reading, Writing and Speaking, plus an overall band. The overall score is the average of the four skills, rounded to the nearest half band. IELTS recommends that results be treated as valid for two years, although receiving organisations make their own decisions.',
    prep: [
      ['Listening', 'Practise varied accents, identify signposting and details, and review mistakes after timed recordings.'],
      ['Reading', 'Build skimming and scanning skills; practise inference, matching information and identifying the writer’s position.'],
      ['Writing', 'Learn the task requirements and assessment criteria. Practise Task 1 summaries and Task 2 essays under timed conditions.'],
      ['Speaking', 'Practise extending answers with reasons and examples. Record yourself and review fluency, coherence, vocabulary and pronunciation.'],
    ],
    faq: [
      ['Is IELTS accepted in every country?', 'IELTS is widely used, but acceptance and minimum scores depend on the university, programme and immigration authority.'],
      ['Can I retake one skill?', 'IELTS One Skill Retake is available in eligible locations for certain computer-based test takers. It must be completed within 60 days; check availability and acceptance first.'],
      ['Is there a pass mark?', 'No universal pass mark exists. Universities set their own overall and individual-skill requirements.'],
      ['How long are results valid?', 'IELTS recommends two years. The receiving organisation decides whether to accept an older result.'],
    ],
    official: { url: 'https://ielts.org/take-a-test/test-types/ielts-academic', label: 'IELTS official test information' },
  },
  {
    slug: 'toefl-ibt',
    name: 'TOEFL iBT',
    short: 'TOEFL',
    group: 'english',
    level: 'English test, all degree levels',
    title: 'TOEFL iBT: demonstrate your academic English',
    lead: 'Explore TOEFL iBT’s updated 2026 task types and score scale, four test sections, registration options and preparation strategy before choosing a test date.',
    stats: [
      { v: 'About 90 min', l: 'Approximate test time' },
      { v: '4 sections', l: 'Reading, Listening, Writing, Speaking' },
      { v: '1–6', l: 'New score scale from Jan 2026' },
      { v: '2 modes', l: 'Test centre or Home Edition' },
    ],
    what: 'TOEFL iBT is an English-language test from ETS. It measures the academic English skills students use to read, listen, speak and write in higher-education settings.',
    who: 'Applicants to English-taught undergraduate and postgraduate programmes where TOEFL iBT is accepted. It is familiar to many US institutions and is also accepted by universities in other countries.',
    pattern: [
      ['Reading', 'Approx. 30 min', 'Complete the Words, Read in Daily Life and Read an Academic Passage.'],
      ['Listening', 'Approx. 29 min', 'Listen and Choose a Response, conversations, announcements and academic talks.'],
      ['Writing', 'Approx. 23 min', 'Build a Sentence, Write an Email and Write for an Academic Discussion.'],
      ['Speaking', 'Approx. 8 min', 'Listen and Repeat and Take an Interview.'],
    ],
    scoring: 'For tests taken from 21 January 2026, ETS reports four section scores and an overall score on a 1–6 scale in half-point increments. The overall score is the average of the four sections, rounded to the nearest half band. During a two-year transition period, ETS also provides a comparable overall score on the previous 0–120 scale.',
    prep: [
      ['Reading', 'Practise vocabulary in context, sentence completion, reading for purpose and finding key details.'],
      ['Listening', 'Listen for main ideas, speaker purpose, transitions, examples and details in conversations and academic talks.'],
      ['Writing', 'Practise accurate sentence construction, clear email communication and structured academic discussion responses.'],
      ['Speaking', 'Work on clear repetition, pronunciation, pacing and natural interview-style responses. Record and review your answers.'],
    ],
    faq: [
      ['What is the TOEFL score scale now?', 'For tests from 21 January 2026, ETS reports scores on a 1–6 scale. A comparable 0–120 overall score is also provided during the transition period.'],
      ['Can I take TOEFL at home?', 'ETS offers the Home Edition in eligible locations, monitored by a live human proctor. Check institution acceptance of that mode.'],
      ['Is TOEFL accepted outside the US?', 'Many institutions worldwide accept TOEFL iBT, but score requirements and delivery rules vary.'],
      ['Does TOEFL replace SAT, GRE or GMAT?', 'No. TOEFL measures English proficiency; the other tests assess academic admissions readiness for different study levels.'],
    ],
    official: { url: 'https://www.ets.org/toefl/test-takers/ibt/about/content.html?version=after-jan-2026', label: 'ETS TOEFL iBT test information' },
  },
  {
    slug: 'pte-academic',
    name: 'PTE Academic',
    short: 'PTE',
    group: 'english',
    level: 'English test, all degree levels',
    title: 'PTE Academic: computer-based English proficiency test',
    lead: 'Understand PTE Academic’s three-part test format, integrated tasks, 10–90 scoring, booking process and preparation approach for international university applications.',
    stats: [
      { v: '≈2 hours', l: 'Approximate test time' },
      { v: '3 parts', l: 'Speaking & Writing, Reading, Listening' },
      { v: '10–90', l: 'Score scale' },
      { v: '≈2 days', l: 'Typical result timing' },
    ],
    what: 'PTE Academic is Pearson’s computer-based English proficiency test for people who need to demonstrate English ability for study and other approved purposes.',
    who: 'Students applying to institutions and programmes that accept PTE Academic. It may suit candidates who prefer computer-delivered testing and integrated speaking and writing tasks.',
    pattern: [
      ['Speaking & Writing', '76–84 min', 'Integrated speaking and writing tasks, including responding to prompts and producing spoken or written answers.'],
      ['Reading', '23–30 min', 'Reading comprehension and language use through several question types.'],
      ['Listening', '31–39 min', 'Understanding spoken information, identifying details and interpreting audio material.'],
    ],
    scoring: 'PTE Academic reports an overall score and communicative skill scores for Listening, Reading, Speaking and Writing on a 10–90 scale. The overall score is not simply the arithmetic average of the four skill scores. Some programmes set minimums for individual skills as well as the overall score.',
    prep: [
      ['Speaking & Writing', 'Practise clear speech, note-taking, summarising, sentence control, spelling and concise written responses.'],
      ['Reading', 'Build vocabulary and grammar awareness; practise reading for meaning and context under time limits.'],
      ['Listening', 'Practise identifying key information in audio, accurate note-taking and distinguishing main points from details.'],
      ['Full mocks', 'Use official scored practice tests to learn the interface and identify weaker skills.'],
    ],
    faq: [
      ['Is PTE Academic accepted for study abroad?', 'Many institutions accept it, but acceptance and minimum scores vary by programme and destination.'],
      ['How long does PTE take?', 'Pearson describes the current test as approximately two hours, across three parts.'],
      ['How quickly are results available?', 'Pearson says results are usually available in around two days, but timing can vary.'],
      ['Is PTE Academic the same as PTE Academic Online?', 'No. Different PTE products or delivery modes can have different acceptance rules. Confirm the exact test accepted.'],
    ],
    official: { url: 'https://www.pearsonpte.com/pte-academic/', label: 'Pearson PTE Academic' },
  },
  {
    slug: 'duolingo-english-test',
    name: 'Duolingo English Test',
    short: 'Duolingo',
    group: 'english',
    level: 'English test, check university and visa rules',
    title: 'Duolingo English Test: an online English proficiency option',
    lead: 'Learn how the DET adaptive online test works, its score scale, at-home testing requirements and how to check whether your target university and visa route accept it.',
    stats: [
      { v: '≈1 hour', l: 'Approximate test time' },
      { v: '10–160', l: 'Score scale' },
      { v: 'Adaptive', l: 'Question difficulty can change' },
      { v: 'At home', l: 'Online test with security checks' },
    ],
    what: 'The Duolingo English Test is an online English proficiency assessment that can be taken from home under controlled testing conditions. It assesses practical English ability through adaptive tasks.',
    who: 'Applicants whose target universities explicitly accept DET and who prefer a flexible online test. Do not assume that acceptance for university admission means acceptance for visa purposes.',
    pattern: [
      ['Introduction & onboarding', 'About 5 min', 'Check the test environment, camera, speakers and microphone; complete identity and room checks.'],
      ['Adaptive test', 'About 45 min', 'Complete a range of English tasks. Question difficulty and the number of questions can adapt as you progress.'],
      ['Writing & Speaking samples', 'About 10 min', 'Respond to open-ended prompts. The samples are shared with institutions that receive your results.'],
    ],
    scoring: 'The DET reports an overall score on a 10–160 scale, with additional subscores that describe different aspects of English ability. The test is adaptive, so the difficulty and number of questions may vary. Institutions set their own score requirements.',
    prep: [
      ['Build all four skills', 'Read varied texts, listen to natural speech, practise speaking spontaneously and write clear responses.'],
      ['Practise varied task types', 'Become comfortable switching between short recognition tasks, listening, speaking and writing activities.'],
      ['Improve response clarity', 'Focus on relevant answers, logical organisation, grammar, vocabulary and pronunciation.'],
      ['Rehearse the setup', 'Practise with the computer, camera, microphone and room you plan to use on test day.'],
    ],
    faq: [
      ['Can I take DET from home?', 'Yes. It is an online test, subject to identity, room, equipment and proctoring requirements.'],
      ['How long does it take?', 'Allow about one hour of uninterrupted time. The test is adaptive.'],
      ['What is the score range?', 'The overall score is reported on a 10–160 scale, with additional subscores.'],
      ['Is DET accepted for student visas?', 'Do not assume so. Check the relevant immigration authority and visa category separately.'],
    ],
    official: { url: 'https://englishtest.duolingo.com/applicants', label: 'Duolingo English Test applicant guide' },
  },
  {
    slug: 'digital-sat',
    name: 'Digital SAT',
    short: 'SAT',
    group: 'admissions',
    level: 'Admissions test, bachelor’s',
    title: 'Digital SAT: a guide for undergraduate applicants',
    lead: 'Planning for a bachelor’s degree abroad? Understand what the Digital SAT measures, its adaptive Reading and Writing and Math sections, 400–1600 scoring and preparation strategy.',
    stats: [
      { v: '2h 14m', l: 'Testing time' },
      { v: '98', l: 'Questions in total' },
      { v: '400–1600', l: 'Total score range' },
      { v: '2 sections', l: 'Reading & Writing, Math' },
    ],
    what: 'The SAT is a standardised admissions test administered by the College Board. Universities use it as one part of undergraduate admissions, particularly in the United States and at selected institutions elsewhere.',
    who: 'High-school students applying to bachelor’s programmes where SAT scores are required, considered or useful for admission or scholarship review. Some universities are test-optional or test-free.',
    pattern: [
      ['Reading & Writing', '54 questions · 64 min', 'Two 32-minute modules. Assesses reading comprehension, information and ideas, craft and structure, expression of ideas and standard English conventions.'],
      ['Math', '44 questions · 70 min', 'Two 35-minute modules. Assesses algebra, advanced math, problem-solving and data analysis, geometry and trigonometry.'],
    ],
    scoring: 'The total SAT score ranges from 400 to 1600. Reading and Writing contributes 200–800 points and Math contributes 200–800 points. The first module’s performance affects the difficulty of the second module. Some universities superscore by combining the highest section scores from different test dates.',
    prep: [
      ['Reading & Writing', 'Practise short-passage comprehension, grammar, punctuation, evidence, inference, vocabulary in context and rhetorical purpose.'],
      ['Math', 'Review algebra and advanced math, practise data interpretation and multi-step problems, and learn the approved on-screen tools.'],
      ['Digital practice', 'Use the official Bluebook experience to learn navigation, timing, tools and the two-module structure.'],
      ['Score strategy', 'Compare your result with the score ranges and test policies of your target universities.'],
    ],
    faq: [
      ['Can I take the Digital SAT from home?', 'No. It is taken at an authorised school or test centre under supervision using an approved device and Bluebook.'],
      ['Do all US universities require the SAT?', 'No. Policies vary by institution and application cycle.'],
      ['How many times can I take it?', 'The College Board does not set a lifetime attempt limit. Consider registration costs and application timelines before retaking.'],
      ['Does SAT prove English proficiency?', 'Not automatically. Universities may require a separate English proficiency test.'],
    ],
    official: { url: 'https://satsuite.collegeboard.org/sat/whats-on-the-test/structure', label: 'College Board SAT Suite' },
  },
  {
    slug: 'gre-general-test',
    name: 'GRE General Test',
    short: 'GRE',
    group: 'admissions',
    level: 'Admissions test, master’s and PhD',
    title: 'GRE General Test: a guide for master’s and PhD applicants',
    lead: 'Considering a master’s or PhD abroad? Explore GRE Verbal, Quantitative and Analytical Writing sections, adaptive format, score reporting and preparation for graduate admissions.',
    stats: [
      { v: '1h 58m', l: 'Approximate test time' },
      { v: '5 sections', l: '1 writing, 2 verbal, 2 quantitative' },
      { v: '260–340', l: 'Verbal + Quant combined range' },
      { v: '5 years', l: 'Score reportability period' },
    ],
    what: 'The GRE General Test is administered by ETS and is used by many graduate, business and selected professional programmes to assess verbal reasoning, quantitative reasoning and analytical writing.',
    who: 'Applicants to master’s and doctoral programmes across disciplines where GRE is required, recommended or accepted. Some business and law programmes also consider GRE scores. Requirements differ by course and department.',
    pattern: [
      ['Analytical Writing', '1 essay · 30 min', 'One Analyze an Issue task; assesses the ability to develop and support a position with clear reasoning and coherent writing.'],
      ['Verbal Reasoning', '27 questions · 41 min', 'Two sections (12 + 15); reading comprehension, text completion and sentence equivalence.'],
      ['Quantitative Reasoning', '27 questions · 47 min', 'Two sections (12 + 15); arithmetic, algebra, geometry and data analysis.'],
    ],
    scoring: 'Verbal Reasoning and Quantitative Reasoning are each scored 130–170 in one-point increments. Analytical Writing is scored 0–6 in half-point increments. Verbal and Quantitative combine to 260–340. ETS states scores are reportable for five years and are typically available around 8–10 days after the test.',
    prep: [
      ['Verbal', 'Build vocabulary through context; practise dense reading passages, argument structure and eliminating unsupported choices.'],
      ['Quantitative', 'Refresh arithmetic, algebra, geometry and data interpretation. Build accuracy before speed.'],
      ['Analytical Writing', 'Practise taking a clear position, supporting it with examples and structuring paragraphs logically.'],
      ['Full-length practice', 'Use official POWERPREP tests and practise the current shorter test format.'],
    ],
    faq: [
      ['Is GRE only for STEM students?', 'No. It is used across many disciplines, including humanities, social sciences, sciences and selected business or professional programmes.'],
      ['Does GRE replace IELTS or TOEFL?', 'No. GRE measures graduate-level reasoning and writing; English proficiency evidence is separate where required.'],
      ['How long are scores valid?', 'ETS states GRE scores are reportable for five years following the test date.'],
      ['Can I choose which scores to send?', 'ETS ScoreSelect lets eligible test takers choose which test-date scores to send from the available reporting period.'],
    ],
    official: { url: 'https://www.ets.org/gre/test-takers/general-test/prepare/test-structure.html', label: 'ETS GRE General Test' },
  },
  {
    slug: 'gmat',
    name: 'GMAT',
    short: 'GMAT',
    group: 'admissions',
    level: 'Admissions test, MBA and business master’s',
    title: 'GMAT: a guide for MBA and business master’s applicants',
    lead: 'Planning an MBA, MiM or business master’s? Learn what the current GMAT measures, how its three sections work, how scores are reported and how to prepare strategically.',
    stats: [
      { v: '2h 15m', l: 'Test time' },
      { v: '64', l: 'Questions across 3 sections' },
      { v: '205–805', l: 'Total score range' },
      { v: '5 years', l: 'Score validity' },
    ],
    what: 'The GMAT is a graduate business-school admissions assessment administered by GMAC. Business schools use it as one component of an application to understand quantitative, verbal reasoning and data literacy skills.',
    who: 'Applicants to MBA, Master in Management, Master of Finance and other business or management programmes that require or accept the GMAT. Some schools accept GRE instead or offer waivers.',
    pattern: [
      ['Quantitative Reasoning', '21 questions · 45 min', 'Arithmetic, algebraic foundations, problem solving and quantitative reasoning. No calculator is available in this section.'],
      ['Verbal Reasoning', '23 questions · 45 min', 'Reading comprehension and critical reasoning, including understanding written material and evaluating arguments.'],
      ['Data Insights', '20 questions · 45 min', 'Data literacy and interpretation: Data Sufficiency, Multi-Source Reasoning, Table Analysis, Graphics Interpretation and Two-Part Analysis.'],
    ],
    scoring: 'The total GMAT score ranges from 205 to 805 in 10-point increments. Each of the three sections contributes equally to the total score. Scores are valid for five years from the test date. There is no universal good score: compare your result with the class profile of target business schools.',
    prep: [
      ['Quantitative', 'Refresh arithmetic, ratios, percentages and algebra. Practise logical problem-solving without a calculator.'],
      ['Verbal', 'Practise reading comprehension and critical reasoning; identify assumptions, evidence and logical gaps.'],
      ['Data Insights', 'Interpret tables, charts and multiple sources. Practise data sufficiency and multi-step reasoning.'],
      ['Test strategy', 'Take an official diagnostic mock, choose a section order that suits your strengths and use review tools strategically.'],
    ],
    faq: [
      ['How many times can I take the GMAT?', 'GMAC states up to five attempts in a rolling 12-month period, with at least 16 days between attempts. Check GMAC for any lifetime limit before you plan retakes.'],
      ['Is a calculator allowed?', 'No calculator is available in Quantitative Reasoning. An on-screen calculator is available in Data Insights.'],
      ['Can I take GRE instead?', 'Many business schools accept either, but not all programmes do. Check each school’s current policy.'],
      ['Can I choose the section order?', 'Yes. GMAC allows candidates to select their section order.'],
    ],
    official: { url: 'https://www.mba.com/exams/gmat-exam/about/exam-structure', label: 'GMAT official exam information' },
  },
];

export const bySlug = Object.fromEntries(exams.map((e) => [e.slug, e]));
export const href = (e) => `/exams/${e.slug}/`;

// The four English tests side by side. Cells are plain statements from the guides above.
export const COMPARE = {
  cols: ['ielts-academic', 'toefl-ibt', 'pte-academic', 'duolingo-english-test'],
  rows: [
    ['Run by', ['IELTS partners: British Council, IDP and Cambridge', 'ETS', 'Pearson', 'Duolingo']],
    ['Format', ['Paper or computer', 'Computer, at a test centre or at home (Home Edition)', 'Computer, scored by machine', 'Online and adaptive, taken from home']],
    ['About how long', ['2 hours 45 minutes', 'About 90 minutes', 'About 2 hours', 'About 1 hour']],
    ['Speaking', ['Live interview with an examiner', 'Recorded on a microphone', 'Recorded and scored by machine', 'Recorded video responses']],
    ['Score scale', ['0–9 bands, in half bands', '1–6 in half-point steps from 21 January 2026, with a comparable 0–120 score during the transition', '10–90', '10–160']],
    ['Results', ['Computer: up to 5 days. Paper: 13 days', 'Faster since the January 2026 update. Check ETS for current timing', 'About 2 days', 'About 2 days']],
    ['Suits you if', ['You would rather speak to a person than a microphone', 'You are comfortable with lecture-style English and typing', 'You want a fast result and a fully computer-based test', 'You need a flexible online test and your university accepts it']],
  ],
};

export const FINDER = {
  levels: [['ug', 'Bachelor’s degree'], ['pg', 'Master’s degree'], ['mba', 'MBA or business master’s'], ['phd', 'PhD or doctoral']],
  needs: [['english', 'English proficiency'], ['aptitude', 'Academic readiness for admission'], ['both', 'Both English and academic readiness']],
};

export const CHECKLIST = [
  'I have shortlisted universities and specific programmes.',
  'I have checked whether the test is required, optional or not accepted.',
  'I have checked separate visa-language requirements for my destination.',
  'I have confirmed the accepted test version and delivery mode.',
  'I know the minimum overall and section scores I need.',
  'I have allowed time for preparation, results and a possible retake.',
  'I have checked score validity and score-reporting deadlines.',
  'I am using official test-maker preparation resources.',
];

// "Which test should I look at first?" One answer for each pair of choices. It never says who is eligible.
const ENGLISH = {
  text: 'Start by comparing IELTS Academic, TOEFL iBT, PTE Academic and the Duolingo English Test. Confirm which test versions your university and visa route accept.',
  slugs: ['ielts-academic', 'toefl-ibt', 'pte-academic', 'duolingo-english-test'],
};
const APTITUDE = {
  ug: { text: 'For undergraduate admission, check whether your universities require or consider the SAT. Some are test-optional. You may also need an English proficiency test.', slugs: ['digital-sat'] },
  pg: { text: 'For a master’s degree, check whether your programme requires or accepts the GRE. Some programmes do not require a standardised admissions test.', slugs: ['gre-general-test'] },
  phd: { text: 'For a PhD, check whether your programme requires or accepts the GRE. Some programmes do not require a standardised admissions test.', slugs: ['gre-general-test'] },
  mba: { text: 'For an MBA or business programme, compare the GMAT and GRE policies of each school. Many accept either, but requirements differ.', slugs: ['gmat', 'gre-general-test'] },
};
export function finderResult(level, need) {
  if (need === 'english') return ENGLISH;
  const a = APTITUDE[level] || APTITUDE.ug;
  if (need === 'aptitude') return a;
  return { text: `${a.text} You will also need to show your English, with a test such as IELTS, TOEFL iBT, PTE Academic or the Duolingo English Test.`, slugs: [...a.slugs, ...ENGLISH.slugs] };
}
export const finderTable = () => {
  const out = {};
  for (const [l] of FINDER.levels) for (const [n] of FINDER.needs) {
    const r = finderResult(l, n);
    out[`${l}|${n}`] = { text: r.text, links: r.slugs.map((s) => ({ name: bySlug[s].name, href: href(bySlug[s]) })) };
  }
  return out;
};
