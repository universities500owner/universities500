// Pages kept out of search results and the sitemap.
// DRAFT: wording or legal text still to be finished.
export const DRAFT = ['/privacy/', '/terms/', '/method/', '/rankings/', '/404/'];
// UNCHECKED: pages built on sample or indicative figures. Remove a path from this list once its facts are checked and sourced.
export const UNCHECKED = [
  '/courses/',
  '/course-fitment/',
  '/scholarships/',
  '/budget/',
  '/loan/',
  '/visa-readiness/',
  '/working-while-you-study/',
  '/search/',
];
export const hiddenFromSearch = (path) => DRAFT.includes(path) || UNCHECKED.includes(path);
