# Course reader

Reads the course pages of every university on the site and writes one file per university to `data/courses/<slug>.json`.
It keeps a course only if the page itself shows all three of these:

1. **Bachelor's or Master's degree.** PhD, MPhil, doctorates, diplomas, certificates, foundation years, pathway and pre-master's courses, associate degrees, short courses and executive education are left out.
2. **Full-time, on campus.** Online, distance and part-time-only courses are left out. A page that says both "on campus" and "fully online" is held back for a person to look at.
3. **Open to international students.** The page shows an international fee with an amount, an Australian CRICOS course code, or a sentence saying international students can apply or are welcome. English-test scores (IELTS, TOEFL), visa lines, work-rights lines and "International admissions" menu labels do not count: they also appear on pages for home students. If the course page is silent, the university's own international admissions page can stand in (`how: "university"`), but only a page about applying, entry or fees, never a visa, news, event, service, exchange, summer-school or pathway page. Add `--strict-international` to turn that off.

A page is also left out when it is *about* a programme but is not the programme: an FAQ, "how to apply", curriculum, fees or deadlines sub-page, a single course unit inside a degree (`/courses/arch-6006/`), a news article, or a branch campus in another country (`/dubai/...` on a UK university). A course that "may include some online delivery" or "blends on-campus with online coursework" is held for a person to look at. A price marked "total" is never shown as a yearly fee.

No AI is used. Every value is copied from a sentence on the page and the sentence is kept next to it (`evidence`, `context`), so anyone can check it. If a value cannot be read with confidence it stays `null`, and the site would say "Check the official page".

**Nothing here shows on the website until you switch it on.** `build_site_data.py` turns `data/courses/` into `src/data/courses.json` (checked records only, with the sentence each fact came from). The site reads that file only when `src/data/course_publish.json` says `"publish": true`. While it says `false`, `/courses/` keeps the placeholder search and stays out of search engines.

To look at real data on the site: run Courses with `commit` ticked, read the course pages it wrote, then set `publish` to `true` in a pull request. That one change turns on the course search, one page per course (`/courses/<university>/<course>/`), the course list on each university page, and the sitemap entries.

## What a record holds

```json
{
  "id": "aston-university:computer-science-bsc-hons:3f9a1c", "university": "aston-university",
  "name": "Computer Science BSc (Hons)", "degree": "BSc (Hons)", "level": "Bachelor",
  "field": "Computer science and IT",
  "url": "https://...", "studyMode": {"verdict": "full-time on campus", "evidence": "Study mode: Full-time on campus."},
  "international": {"how": "fee", "evidence": "International students: tuition fee £21,500 per year."},
  "fee": {"display": "GBP 21,500 a year", "context": "..."}, "duration": {"display": "3 years", "years": 3, "context": "..."},
  "intakes": {"months": ["Sep", "Jan"], "context": "..."}, "ielts": {"overall": 6.5, "context": "..."}, "cricos": null,
  "flags": null, "firstSeen": "2026-11-16", "lastVerified": "2026-11-16", "lastChanged": "2026-11-16", "hash": "..."
}
```

- `international.how`: `cricos` (Australian course code), `fee` (international fee on the page), `page` (international sentence on the page), `university` (the university's admissions page, not the course page).
- `field` is our label, chosen from words in the programme name. It is not the university's own category.
- `fee` is only taken from a sentence that names international (or overseas, non-EU, out-of-state) students. Home-student amounts, per-credit prices and whole-course totals are never turned into a yearly fee.
- `flags`: `integrated` (a four-year integrated master's such as MEng that starts at undergraduate level), `combined` (a double degree).
- `ielts.overall` is filled only when the sentence says it plainly. Otherwise it is `null` and only the sentence is kept.

Each university file also holds `status`, `note`, `robotsReason`, `pagesRead`, `intlOpen` (the international admissions page that was used), `counts.held` (how many pages were held back, by reason), `heldSamples` (up to 5 example addresses per reason) and `seen` (every page read, with the date and the result, so the next run knows what is due).

## How a run works

- Polite: robots.txt is obeyed (RFC 9309), one request at a time per website, 3 seconds between requests, a contact address in the User-Agent. No login, no forms, no pages behind a script.
- At most `--max-pages` (default 150) pages per university per run. The order is: the international admissions page, then course pages already known and due for a re-check (stalest first, at most 60% of the budget), then list pages, then new course pages from the sitemap, the home page and list pages.
- Known eligible courses are read again after `--refresh-days` (14); pages that were held back after `--held-days` (45). Repeated runs therefore reach deeper into big universities.
- A course whose page loads but is no longer an eligible course is dropped after 3 runs in a row. A page that fails to load (timeout, server error) is never counted. If more than half of the known pages fail at once, the website probably changed its addresses and nobody is counted as missing.
- Safety gate: if the number of eligible courses falls by more than half in one run, nothing is written and the run exits with code 3. Use `--allow-drop` if that is expected.
- Pages whose address says online, distance, pathway, foundation, diploma, certificate or PhD are not requested at all and are counted as `skipped-by-address:<reason>`.
- Pages in another language folder (`/de/`, `/fr/`, ...) are skipped.

## Running it

From GitHub: Actions, "Courses (read official pages)", Run workflow. It is manual only.

| Setting | What it does |
|---|---|
| `only` | slugs, comma-separated |
| `limit` | only the first N universities |
| `shards` | how many jobs share the list (1 to 8), default 4 |
| `max_pages` | pages per university, default 150 |
| `commit` | commit `data/courses/` to main when every job succeeded (default off) |

A first trial: `shards` 1, `limit` 12, `commit` off. The run summary shows the report; the `courses-all` artifact holds `course_report.md`, `universities.csv` (one row per university) and `course_samples.json`.

By hand: `python3 scripts/courses/run.py --only aston-university --max-pages 40 --delay 3 --contact you@example.com`.

## Reading the report

- **Held back (counted, not published)** lists why pages were not kept: `study-mode-unclear` (no sentence says full-time or on campus), `international-unclear`, `online-or-part-time`, `domestic-only`, `listing-page`, `not-a-course-page`, the `skipped-by-address:*` reasons and so on. A large `study-mode-unclear` or `international-unclear` count means the wording on that university's pages is not yet recognised: send the university and one address from `heldSamples` and the rule can be widened.
- **Universities that need a look**: `robots` (robots.txt does not allow us, shown with the reason), `unreachable`.
- **Readable, but no eligible course found**: usually course lists built with scripts (`js-only-or-empty`), or an address layout the finder missed. Hand-checked list pages can be added to `data/course_seeds.json` (same shape as `data/scholarship_seeds.json`: `{"seeds": {"<slug>": {"urls": ["https://..."]}}}`); they are read first and may sit on another domain.

## The Australian government register (CRICOS)

`data/cricos/<university>.json` holds each Australian university's registered Bachelor's and Master's courses (code, length in weeks, whole-course tuition, field, campuses) from the Commonwealth Register of Institutions and Courses for Overseas Students, Australian Government Department of Education, licensed Creative Commons Attribution 2.5 Australia (https://data.gov.au/data/dataset/cricos). The credit is shown on every course page that uses it.

It never creates a course and has no web address, start months or English scores, so a course is still listed only when the university's own page was read. It does three things:

1. **Open to international students.** A page whose programme name matches exactly one registered course at that university is accepted as open to international students (`international.how: "cricos"`, `cricosMatch: "name"`) when the page itself does not say so. Two registered courses with one name are not guessed. A code quoted on the page always comes first, and a page that says "domestic only" is never rescued. Study mode is **not** taken from the register: the page must still say full-time on campus.
2. **Official length, campuses and field** are added to a course the reader found (`reg` in `src/data/courses.json`). The length fills the course's length only when the page gave none, and only when it is a normal Bachelor's or Master's length.
3. **Registered tuition** is shown on the course page only, labelled "older figure": it is the whole-course amount, and it can be behind what the university charges now (Flinders' Bachelor of Accounting is AU$105,700 over 156 weeks in the register, about AU$35,200 a year, against AU$40,900 a year in Flinders' 2027 schedule; Edith Cowan's register fees match its pages). It is never the fee, never on a card and never in the fee filter. A fee of zero or blank is "not published".

To refresh: download the four files (`CRICOS_Institutions.csv`, `CRICOS_Courses.csv`, `CRICOS_Locations.csv`, `CRICOS_Course_Locations.csv`) from the dataset page, put them in one folder, then `python3 scripts/courses/cricos.py build --csv-dir <folder>` and update `downloaded` (and `snapshot`, the date the dataset page shows) in `data/cricos/providers.json`. `providers.json` lists the CRICOS provider code of each university; branch colleges, pathway colleges and training arms are left out on purpose. The register is out of date within weeks (the live site, https://cricos.education.gov.au, has the latest), so refresh it every few months.

## Tests

`python3 scripts/courses/test_courses.py` runs a stub university site on localhost (no internet). It covers eligible courses and every kind of page that must be left out (online, distance, part-time only, PhD, diploma, certificate, foundation, pathway, domestic only, robots-blocked), real-world fee wording (tables, whole-course totals, per-credit prices), the page budget, refresh order, merging between runs, the drop rule, the site-trouble rule and the safety gate.

The reader shares `fetcher.py`, `extract.py` and `textutil.py` with `scripts/scholarships/`.


## Reading the results of a run

The run summary and the `courses-all` artifact hold `course_report.md`, `universities.csv`, `course_samples.json` (first 3 courses per university) and `held_samples.json` (example addresses for every reason a page was held back, for example `study-mode-unclear`). Look at `held_samples.json` first when a reason count is large: it shows whether a rule is too strict.

`status` in the CSV: `ok`; `unreachable` (the note says why: the robots.txt answer such as `HTTP 502` or a network error, or `HTTP 403` for the home page); `robots` (robots.txt forbids us); `error` (the reader stopped on this university; the note names the error). A page the reader could not handle is counted as `page-error:<name>` and listed in the report; it never stops the rest of the university. The same cleaning is used by the scholarship reader (`scripts/scholarships/fetcher.py`: robots.txt that moves to another address is followed, odd characters in links are encoded).

## Course detail (Claude Haiku 5.5, Batch API)

`detail.py` and `detail_run.py` read what each course page says: overview, key facts, fees, entry and English requirements, modules, teaching, careers, accreditation, deadlines. Workflow: `course-detail.yml` (manual).

- The page is cut into sections at its headings by the same reader as everywhere else (robots.txt, 3 seconds between requests, identified User-Agent). The model never browses.
- The model only labels sections and returns short facts, each with a quote copied from the page. It never writes the text that is shown.
- Code copies each labelled section's text verbatim and checks every quote, number and name against the page text. A fee must be one of the numbers in its quote, an "international" fee needs the word in the quote, IELTS must be 4 to 9 and in the quote, module and employer names must appear on the page. What fails is thrown away and counted in the run report.
- Results: `src/data/course-detail/<university>.json`, one entry per course page address, with the page hash. A page is read again only when its text changed.
- `src/data/course_text_policy.json` decides how much of the university's own text the site shows (`full`, `excerpt`, or `optOut` per university). Change it and rebuild to respond to a takedown request.
- `mode = preview` prints how each page was cut (no API key, no cost). `mode = run` needs the repository secret `ANTHROPIC_API_KEY`. Batch rate for Haiku 5.5 is half the normal price; the run report prints tokens and cost.

### Pilot: universities the reader could not read (`source = held`)

For some universities the reader fetched pages but held them all back (`study-mode-unclear`, `international-unclear`, or a degree page taken for a listing), so the site lists no courses. The pilot gives those held pages to the model and measures what it recovers.

- `detail_run.py ... --source held --only <slugs>` takes each university's held pages from `data/courses/<slug>.json` (`seen`): first the pages it could not settle, then pages taken for listings whose address looks like a degree. News, events, contacts and the reader's firm decisions (online, domestic only, research degree, diploma, foundation) are left out.
- The model also says what each page is (`level`: bachelor, master, doctorate, other award, not a degree page), how it is taught (`delivery`) and whether international students can apply (`international`), each with a quote from the page. `eligibility()` applies the reader's rule to that: `yes` (bachelor's or master's, stated on campus, international open), `maybe` (not stated, nothing against), `no`.
- Fields: course name (the page's own heading is the fallback, never the model's words), overview, faculty or school, fees, scholarships, admission requirement, English tests, other tests or requirements, programme objectives, career outcomes, industry connections, internships. University name and the page's address come from code.
- Results go to `data/course-pilot/<slug>.json` and are never read by the site. The run's artifact has `pilot.csv` (one row per page) and `report.md` (pages, degree pages and eligibility per university; how often each field was filled; what was thrown away).
- Not covered yet: pages that hold university-wide facts (international admissions, English requirements, fees, scholarships) and finding degree pages at universities where the reader held none (Warwick, MIT: the reader spent its page budget on other pages).
