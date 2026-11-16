# Course reader

Reads the course pages of every university on the site and writes one file per university to `data/courses/<slug>.json`.
It keeps a course only if the page itself shows all three of these:

1. **Bachelor's or Master's degree.** PhD, MPhil, doctorates, diplomas, certificates, foundation years, pathway and pre-master's courses, associate degrees, short courses and executive education are left out.
2. **Full-time, on campus.** Online, distance and part-time-only courses are left out. A page that says both "on campus" and "fully online" is held back for a person to look at.
3. **Open to international students.** The page shows an international fee, an Australian CRICOS course code, or a sentence about international applicants. If the course page is silent, the university's own international admissions page can stand in (`how: "university"`). Add `--strict-international` to turn that off.

No AI is used. Every value is copied from a sentence on the page and the sentence is kept next to it (`evidence`, `context`), so anyone can check it. If a value cannot be read with confidence it stays `null`, and the site would say "Check the official page".

**Nothing here changes the website.** The files are not under `src/`, nothing imports them, and no page shows them yet. They are data for review first.

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

## Tests

`python3 scripts/courses/test_courses.py` runs a stub university site on localhost (no internet). It covers eligible courses and every kind of page that must be left out (online, distance, part-time only, PhD, diploma, certificate, foundation, pathway, domestic only, robots-blocked), real-world fee wording (tables, whole-course totals, per-credit prices), the page budget, refresh order, merging between runs, the drop rule, the site-trouble rule and the safety gate.

The reader shares `fetcher.py`, `extract.py` and `textutil.py` with `scripts/scholarships/`.
