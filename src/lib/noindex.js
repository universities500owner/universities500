// Pages kept out of search results and the sitemap. Everything else is indexed, and the site footer says it is a work in progress.
// DRAFT: stubs whose own text says "Draft" (legal and method pages), and the 404 page.
export const DRAFT = ['/privacy/', '/terms/', '/404/'];
// UNCHECKED: pages whose figures are labelled placeholders, and the on-site search page (it has no content of its own).
// Remove a path from this list once its facts are real and sourced.
export const UNCHECKED = [
  '/courses/',
  '/course-fitment/',
  '/budget/',
  '/search/',
];
// A path is hidden if it is listed, or sits under a listed path.
export const hiddenFromSearch = (path) => [...DRAFT, ...UNCHECKED].some((p) => path === p || (p !== '/' && path.startsWith(p)));
