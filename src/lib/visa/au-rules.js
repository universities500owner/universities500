// Australian student visa (subclass 500): the figures and rules the self-check uses, kept in ONE place so they are easy to update.
//
// Where a number comes from the Australian Government it is marked "official" and carries its source. Where it is a choice we made
// (how many points a factor is worth, how much spare money counts as comfortable) it is marked "ours". Our choices are not Home
// Affairs rules and the page says so. Nothing here comes from any agent, university or company.
//
// When the Government changes a figure, change it here, change CHECKED, and the page, the notes and the tests follow.

export const CHECKED = '2026-11-21'; // the day these figures were last compared with the sources below
export const CHECKED_LABEL = 'November 2026';

// ---- official: the money a student must be able to show for the first 12 months ---------------------------------
// Migration (LIN 19/198: Evidence of financial capacity - Subclass 500 Visa and Subclass 590 Visa) Instrument 2019,
// as compiled 10 May 2024, section 6(2): living costs for the student, a partner and each child; school costs per school-age child.
export const MONEY = {
  living: 29710,   // student, 12 months (AUD)
  partner: 10394,  // partner who comes too, 12 months
  child: 4449,     // each child who comes too, 12 months
  school: 13502,   // each school-age child who comes too, per year
};

// ---- official: the English test score the visa asks for -------------------------------------------------------------
// Migration (English Language Tests and Evidence Exemptions for Subclass 500 (Student) Visas) Instrument 2025 (LIN 25/090), Schedule 3,
// in force from 7 August 2025. `standard` is the usual case. `pathway` is for a student who first takes at least 10 weeks of English
// (ELICOS) or a foundation or pathway course. `margin` is OURS: how far above the visa score counts as a comfortable result.
export const ENGLISH = {
  ielts: { name: 'IELTS', standard: 6.0, pathway: 5.5, margin: 0.5 },
  pte: { name: 'PTE Academic', standard: 50, pathway: 42, margin: 8 },
  toefl: { name: 'TOEFL iBT', standard: 64, pathway: 46, margin: 15 },
};
// Duolingo and other tests are not on the list we checked, so the self-check cannot compare them with the visa score.

// ---- ours: how many points each part is worth (they add up to 100) --------------------------------------------------
export const WEIGHTS = { funds: 30, fit: 25, english: 15, history: 15, evidence: 15 };

// ---- ours: the bands --------------------------------------------------------------------------------------------------
export const BANDS = { green: 75, amber: 50 }; // score at or above → Green; at or above → Amber; below → Red

// ---- ours: how much spare money counts as comfortable (money you can show ÷ money counted) ---------------------------
// Travel and health cover are not counted in the money we add up, so being exactly on the line is tight.
export const COVER = [
  [1.25, 1],     // 25% or more spare: full points
  [1.1, 22 / 30],
  [1.0, 12 / 30],
  [0, 0],        // below the money counted: no points, and the result cannot be Green or Amber
  { label: 'Home Affairs: consultation on changes to the Genuine Student and money rules', url: 'https://www.homeaffairs.gov.au/help-and-support/how-to-engage-us/consultations/consultation-on-proposed-reforms-to-the-genuine-student-requirement-and-financial-capacity-framework' },
];

// ---- ours: how earlier visa results count (immigration history) ---------------------------------------------------
export const HISTORY = {
  recentYears: 3,   // a study visa refusal this recent holds the result at Amber at best
  refusedStudy: 9,  // points taken off, per refusal in the last five years
  refusedOther: 5,
  refusedOld: 2,    // a refusal more than five years ago
  cancelled: 6,
  withdrawn: 1,
  unknown: 10,      // "prefer not to say" or not answered: we do not count it for or against you
};

// Where to check the facts before you rely on them.
export const SOURCES = [
  { label: 'Home Affairs: Student visa (subclass 500)', url: 'https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/student-500' },
  { label: 'Home Affairs: Genuine Student requirement', url: 'https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/student-500/genuine-student-requirement' },
  { label: 'Money you must show: LIN 19/198 (compiled 10 May 2024)', url: 'https://www.legislation.gov.au/F2019L01366/2024-05-10/2024-05-10/text/original/epub/OEBPS/document_1/document_1.html' },
  { label: 'English test scores: LIN 25/090 (from 7 August 2025)', url: 'https://www.legislation.gov.au/F2025L00906/asmade/2025-08-06/text/original/epub/OEBPS/document_1/document_1.html' },
  { label: 'Home Affairs: consultation on changes to the Genuine Student and money rules', url: 'https://www.homeaffairs.gov.au/help-and-support/how-to-engage-us/consultations/consultation-on-proposed-reforms-to-the-genuine-student-requirement-and-financial-capacity-framework' },
];
