# Scholarship reader

Reads public scholarship pages and writes `src/data/scholarships.json`. No AI is used: dates, values and eligibility are found with regular expressions and page structure.

## Where it runs

`.github/workflows/scholarships.yml` runs it on GitHub Actions. The cron fires daily, and a guard (`--if-older-than-hours 46`) skips the run unless the data is at least 46 hours old, so it works out to every two days. From the Actions tab you can also run it by hand ("Run workflow"): `only` limits it to one university slug, `limit` to the first N, and `commit` turns the commit step off.

After a run, the workflow commits `src/data/scholarships.json` to `main`, and Cloudflare rebuilds the site. Each run also uploads a report as the `scholarship-run` artifact: `scholarship_report.md`, `universities.csv`, `sample_records.json`, `errors.txt`, `robots_blocked.txt`.

## Rules the reader keeps

- Obeys robots.txt (including Crawl-delay). A host that blocks it is skipped. An explicit `Disallow` is always honoured, for the home page and for any page we were given.
- At least 3 seconds between requests to the same host. At most 60 pages per university (`--max-pages`).
- Identifies itself as `Universities500Bot` and links to `/bot/`. Set the repo variable `CONTACT_EMAIL` to put a contact address in the User-Agent.
- Keeps only scholarships that name Bachelor's or Master's study, are open to international students, and show at least one of value, deadline or eligibility.
- Never guesses. A field it cannot read is left empty and the site shows "Check the official page".
- Status (open, closed, yet to open) comes only from dates on the page.

## Reaching more universities

Three things decide how many universities give us anything. All three keep the rules above.

**Pages checked by hand (`data/scholarship_seeds.json`).** A university can have one or more scholarship page addresses, taken from its own site. The reader reads these first, they may sit on another domain (a university's trust, for example), and they win the choice of "scholarships page" shown on the university's page over anything the reader guesses. A seed is never used to skip robots.txt. If the home page cannot be read but a seed can, the seed is read on its own and the result counts as partial, so it cannot remove records we did not reach. The run report has a section, "Pages checked by hand: what the reader found", that says for each address whether it was read, loads but needs scripts, does not mention scholarships, failed, or is blocked by robots.txt. To add one, add the university's slug under `seeds` with a `urls` list and update `checked`.

**Usual places.** When a site gives no clear link to scholarships (no sitemap hit, no link on the home page), the reader asks for a few usual addresses such as `/scholarships/` and `/study/scholarships/`. A 404 costs one request.

**International context.** A scholarship linked from an international students page, or from a page whose address or title says international or overseas, counts as open to international students when it does not say otherwise. A page that says "home students only" still counts as no.

**robots.txt answers.** Following RFC 9309: a 4xx answer for robots.txt (including 401 and 403) means there are no rules for us, so the site can be read. A 5xx answer or no answer means we must not read it. An explicit `Disallow` always stops us. `--strict-robots` treats 401/403 as a full stop too. The report and `universities.csv` give the reason for every university skipped by robots.txt (`disallow`, `forbidden` or `unreachable`), so the share that really forbids us can be seen.

## What the page says about India

`india` holds one sentence from the page, copied as written (trimmed around the word when it is very long), when the sentence names India or Indian students, citizens or institutions. It is never turned into "eligible" or "not eligible": a page can name India to include it, to exclude it, or only to list it among many countries, and a program cannot tell which. The site shows it as "The page says about India", with a link to the official page. "American Indian", "Indian Ocean" and similar are ignored, and a sentence that only contains the word India needs an eligibility word beside it.

## Safety nets

- A university that fails to load keeps its last records. A record not found on a readable page gets a `misses` count and is dropped at 3.
- If a run would remove more than half of the previous records, it stops with exit code 3 and writes nothing. Use `--allow-drop` to override after checking the report.

## Publishing

`src/data/scholarship_publish.json` has `"publish": false` until the first run's `sample_records.json` has been checked against the official pages. Set it to `true` to show listings and per-scholarship pages. `/scholarships/` stays `noindex` until it is removed from the UNCHECKED list in `src/lib/noindex.js`.

## Adding a government programme

Add an entry to `data/scholarship_sources.json` under `programmes` with candidate `urls`, an `expect` phrase that must appear on the page (the entry is published only if it does), and `levels` with a `levelsSource`. Directories (lists of scholarships) go under `directories`. Third-party sites go under `thirdParty` with `scrape: false` until their robots.txt and terms are checked.

Optional keys on a programme: `providerSlug` and `providerType` (for a scholarship run by one university, so it also shows on that university's page), and `expect` as a list when the page may carry either of two names. New programmes are only published when the page loads and contains an expected name; a wrong address just shows up in the run log as a failure.

## Extra facts (`details.py`)

Besides value, deadline, level and eligibility, the reader looks for four more things, each from one sentence on the page and never worked out:

- `awards`: how many are given ("Up to 10 scholarships are available each year").
- `duration`: "Full length of the course", "Up to 4 years", "First year only".
- `covers`: tuition, living costs, travel, health insurance, accommodation, books. Sentences with "not", "except" and similar are skipped.
- `applyMode`: `automatic` when the page says no separate application is needed, `application` when it asks you to apply.

A field the page does not state stays empty and the site shows nothing for it.

## Reading the run log

The log ends with fill rates (the share of records that have each field) and up to 18 pages where the text looks like it holds a deadline or value the reader did not take, with the sentence. Use those lines to improve the patterns in `textutil.py` and `details.py`.

## Run it locally

```
pip install beautifulsoup4 lxml
python3 scripts/scholarships/test_scholarships.py
python3 scripts/scholarships/run.py --only monash-university --out /tmp/sch.json --report /tmp/sch-report
```

## Quality rules (`quality.py`)

Every record has to pass these before it is kept. They run when a page is read, and again on the saved data at the start of each run, so a mistake from an older version cannot stay.

- The name must name one scholarship. Page headings ("Fees and scholarships", "Find a scholarship"), table cells ("All programs", "£12,600", "January"), news and event posts, and names with an old year are dropped.
- Not for our students: PhD, postdoc, staff and studentship records; prizes for enrolled students; exchange, travel and study-abroad grants; New Colombo Plan; home-student-only awards.
- Pages under `/domestic/`, `/dom/`, `/outgoing/`, `/exchange…/` and similar are skipped.
- `data/scholarship_exclude.json` is a hand-kept list of page addresses to leave out, each with a reason. Add a line there when a check by hand shows a page is wrong. Remove a line to bring a page back.

To clean a saved data file without reading any websites: `python3 scripts/scholarships/quality.py src/data/scholarships.json`
