# Scholarship reader

Reads public scholarship pages and writes `src/data/scholarships.json`. No AI is used: dates, values and eligibility are found with regular expressions and page structure.

## Where it runs

`.github/workflows/scholarships.yml` runs it on GitHub Actions. The cron fires daily, and a guard (`--if-older-than-hours 46`) skips the run unless the data is at least 46 hours old, so it works out to every two days. From the Actions tab you can also run it by hand ("Run workflow"): `only` limits it to one university slug, `limit` to the first N, and `commit` turns the commit step off.

After a run, the workflow commits `src/data/scholarships.json` to `main`, and Cloudflare rebuilds the site. Each run also uploads a report as the `scholarship-run` artifact: `scholarship_report.md`, `universities.csv`, `sample_records.json`, `errors.txt`, `robots_blocked.txt`.

## Rules the reader keeps

- Obeys robots.txt (including Crawl-delay). A host that blocks it is skipped.
- At least 3 seconds between requests to the same host. At most 30 pages per university.
- Identifies itself as `Universities500Bot` and links to `/bot/`. Set the repo variable `CONTACT_EMAIL` to put a contact address in the User-Agent.
- Keeps only scholarships that name Bachelor's or Master's study, are open to international students, and show at least one of value, deadline or eligibility.
- Never guesses. A field it cannot read is left empty and the site shows "Check the official page".
- Status (open, closed, yet to open) comes only from dates on the page.

## Safety nets

- A university that fails to load keeps its last records. A record not found on a readable page gets a `misses` count and is dropped at 3.
- If a run would remove more than half of the previous records, it stops with exit code 3 and writes nothing. Use `--allow-drop` to override after checking the report.

## Publishing

`src/data/scholarship_publish.json` has `"publish": false` until the first run's `sample_records.json` has been checked against the official pages. Set it to `true` to show listings and per-scholarship pages. `/scholarships/` stays `noindex` until it is removed from the UNCHECKED list in `src/lib/noindex.js`.

## Adding a government programme

Add an entry to `data/scholarship_sources.json` under `programmes` with candidate `urls`, an `expect` phrase that must appear on the page (the entry is published only if it does), and `levels` with a `levelsSource`. Directories (lists of scholarships) go under `directories`. Third-party sites go under `thirdParty` with `scrape: false` until their robots.txt and terms are checked.

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
