// Pages kept out of search results and the sitemap.
// DRAFT: wording or legal text still to be finished.
export const DRAFT = ['/privacy/', '/terms/', '/method/', '/rankings/', '/404/'];
// UNCHECKED: pages built on sample or indicative figures. Remove a path from this list once its facts are checked and sourced.
export const UNCHECKED = [
  '/courses/',
  '/course-fitment/',
  '/scholarships/',
  '/internships/',
  '/budget/',
  '/loan/',
  '/visa-readiness/',
  '/working-while-you-study/',
  '/search/',
];
// A path is hidden if it is listed, or sits under a listed path (for example /scholarships/some-award/).
export const hiddenFromSearch = (path) => [...DRAFT, ...UNCHECKED].some((p) => path === p || (p !== '/' && path.startsWith(p)));
