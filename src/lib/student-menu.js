// The student dashboard menu: one list for the side menu (src/layouts/Student.astro) and the phone bar (src/components/MobileBar.astro).
// [id, label, href]. A null href is a part that is not built yet; it is listed so students can see what is coming.
export const MENU = [
  ['overview', 'Overview', '/student/'],
  ['profile', 'My profile', '/student/profile/'],
  ['shortlist', 'My shortlist', '/student/shortlist/'],
  ['visa', 'Visa self-check', '/student/visa-check/'],
  ['sop', 'SOP builder', '/student/sop/'],
  ['lor', 'LOR helper', null],
  ['settings', 'Settings', '/student/settings/'],
];

// The four that sit in the phone bar, with the short label shown under each icon. Everything else in MENU goes under "More".
export const TABS = [
  ['overview', 'Overview'],
  ['profile', 'Profile'],
  ['shortlist', 'Shortlist'],
  ['visa', 'Visa'],
];
export const TAB_IDS = TABS.map(([id]) => id);
