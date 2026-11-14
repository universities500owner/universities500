# Universities500 public site (phase 1)

Static site built with Astro. Every page is plain HTML, so search engines and AI crawlers can read it.

## Commands

- `npm install`
- `npm run prep -- <uni_auto.json> <uni_list.json> src/data/universities.json` rebuilds the site data
- `npm run build` writes the site to `dist/`
- `npm run dev` starts a local preview

## Rules this build follows

- No ranking numbers, rank sorts or rank filters anywhere. `prep_data.py` drops the rank, size and type
  fields that came with the working list, and drops any Wikipedia sentence that talks about rankings.
  Dropped sentences are logged in `scripts/rank_scrub_report.txt`.
- Every fact has a source link and the date it was read. Overview text is Wikipedia (CC BY-SA 4.0) and
  facts are Wikidata (CC0).
- University pages without enough content (overview, website, founding year, campus) get `noindex` and
  stay out of the sitemap. Draft pages (method, privacy, terms, rankings) are also `noindex`.
- The current list of 263 is a placeholder. It will be rebuilt from open sources before launch.

## Not in this phase

Destination guides (they contain rank numbers and need a review first), scholarships, accounts, the
dashboard and the Content Admin.

## Links to other websites

`scripts/external-links.mjs` runs at the end of every build. It finds each link to another website in the finished HTML and makes it open in a new tab (`target="_blank" rel="noopener"`, plus a screen-reader note). Links to universities500.com stay in the same tab. It works without JavaScript. Test: `node --test scripts/external-links.test.mjs`.
