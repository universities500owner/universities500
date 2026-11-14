# Articles

Each destination pack (a Word file of articles with SEO and GEO notes) becomes one JSON file per article in `src/data/articles/`. The site builds an HBR-style page for each one.

## Add a new destination pack

1. Put the `.docx` somewhere (it does not go in the repo).
2. Run, from the repo root (needs `pandoc`):

   ```
   python3 scripts/articles/import_docx.py path/to/*.docx --out src/data/articles --report scripts/articles/last_report.txt
   ```

   Run it on **all** packs each time. It rewrites every article file, so the result is the same whichever order you run in.
3. Read `last_report.txt`. It lists every sentence it left out as an editor's note, every ranking or "guarantee" wording to check against the site rules, and any article it could not read.
4. Fix anything the report shows in `overrides.json` (see below), run the importer again, then `npm run build`.
5. Open a pull request. The pages appear when it is merged.

## What the importer reads

- An article starts at a line like `UK-03 | Post-Study & PR`. The prefix sets the destination (`UK`, `USA`, `CAN`, `IRE`, `NZ`, `SGP`, `NLD`, `MYS`, `NOR`, `SWE`, `UAE`, `FRA`, `GER`, `AUS`, `GLB`).
- The category (`Cost & Budgeting`, `Visa & Compliance`, `Post-Study & PR`, `Admissions & Tests`, `Universities & Courses`, `Student Life & Work`, `Finance & Scholarships`, `Career & ROI`) sets the topic. A new category needs a line in `TOPICS` here and in `src/lib/articles.js`.
- It keeps: the headline, the opening paragraphs, the quick answer, the numbered sections, the FAQs and the official sources.
- It leaves out: SEO and metadata tables (the SEO title, meta description and suggested address are stored as fields), product and build briefs, data models, publishing checklists, accuracy notes, appendices, and any sentence written for editors ("the proposed interactive element…", "before publication…").
- Sources written once for the whole pack are shown on each article as "sources we used for our <destination> articles".

## overrides.json

Per article ID: `title`, `seoTitle`, `metaDescription`, `slug`, `dropSections` (words in a section title), `dropFaq` (words in a question), `hold` (true keeps the article off the site), and `why` (printed in the report). Use it when the pack headline promises something the article does not support, or when a section breaks a site rule (for example, no ranking numbers).

## Site rules this keeps

- No ranking numbers or ranking claims of our own. Rankings that a government sets as an eligibility rule (for example, the Netherlands zoekjaar) stay, because that is the rule, not our claim.
- No guaranteed outcomes. The report flags "guarantee" wording that is not negated.
- External links open in a new tab (done at build time for the whole site).

## Tests

`python3 scripts/articles/test_import.py`
