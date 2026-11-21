// The yellow bar at the bottom of a phone screen, for a visitor who is not signed in. Which line it shows depends on the page,
// so the offer matches what the student is reading. Nothing moves. All the wording and page rules are here, in one place.

// Keep each line short: on a 390 px phone about 23 characters fit on one line beside the button, and a longer line makes the bar taller.
export const LINES = {
  shortlist: 'Save your shortlist',
  prep: 'Prepare to apply',
  visa: 'Ready for your visa?',
};

// Destinations that have a visa self-check today. Add a slug (the one in /study-in/<slug>/) when a destination gets its own.
// The bar, and only the bar, uses this list to decide where it may talk about the visa self-check.
export const VISA_SELF_CHECK_COUNTRIES = ['australia'];

// Pages about getting an application ready. Anything under these paths counts.
const PREP_PAGES = ['/application-prep/', '/english-test/', '/exams/'];
// The visa hub covers every destination, so it always counts.
const VISA_PAGES = ['/visa-readiness/'];

const withSlash = (p) => {
  const s = String(p || '/').split(/[?#]/)[0];
  return s.endsWith('/') ? s : s + '/';
};

// 'shortlist', 'prep' or 'visa' for a page path such as '/study-in/australia/'.
export function lineFor(pathname, visaCountries = VISA_SELF_CHECK_COUNTRIES) {
  const p = withSlash(pathname);
  if (VISA_PAGES.includes(p)) return 'visa';
  const m = p.match(/^\/study-in\/([^/]+)\/$/);
  if (m && visaCountries.includes(m[1])) return 'visa';
  if (PREP_PAGES.some((x) => p.startsWith(x))) return 'prep';
  return 'shortlist';
}
