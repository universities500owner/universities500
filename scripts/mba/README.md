# MBA reader

Reads the school pages of the MBA Explorer and writes one file per programme to `data/mba/read/<id>.json`.
**No AI and no API key.** It works from page structure and fixed patterns, the same way the course reader does.

## Parts

| File | What it does |
|---|---|
| `data/mba_sources.json` | The register. `programmes`: each programme and the school pages that state its facts (programme, fees, admissions, FAQ, employment report). `waves`: which destinations are read in which round (a proposal). `candidates`: schools proposed for later rounds, with no pages yet. |
| `scripts/mba/mbafacts.py` | Finds length, tuition, work experience, test (GMAT/GRE/Executive Assessment), English, start, deadlines, degree, and the link to the employment report. Each value keeps the sentence it came from, and is dropped if its numbers are not in that sentence. |
| `scripts/mba/read.py` | Fetches the pages (polite: identified bot, robots.txt, 3 s between requests, no work-around for a 403 or a bot check), skips programmes whose pages have not changed, and prints a report of where the program and the hand reading agree or differ. |
| `scripts/mba/pilot.json` | The hand-read base: 13 programmes, read from the school pages by a person. |
| `scripts/mba/build_site_data.py` | Makes `src/data/mba.json`: the hand-read record, with any fact the program read and verified replacing the hand-read one. Every fact records who read it and when (`provenance`). |
| `scripts/mba/test_mba.py` | Offline tests with a stub school website. Run `python3 scripts/mba/test_mba.py`. |
| `.github/workflows/mba.yml` | Manual run in GitHub Actions. The sandbox cannot reach school websites, so the reader runs there. |

## Rules

- A fact the page does not state is shown as "Not stated". Nothing is estimated and nothing comes from a third-party site.
- Every fact carries the page address it was read from and the date.
- A programme that shares a page with other programmes (`mbs-executive-mba`) is read by hand until it has its own page, because a program cannot tell which facts belong to it.
- Rankings are used only by a person to pick which schools to read. None is stored or shown, and none orders a page.
- The track a programme appears under comes from the minimum work experience its page states.

## First trial

1. Settings > Secrets and variables > Actions: set `CONTACT_EMAIL` (optional but polite).
2. Actions > MBA (read official pages) > Run workflow. Leave `commit` unticked. Try `only` = `oxford-mba`.
3. Read the run summary. For each programme it lists the facts that agree with the hand reading, the facts that differ, and the facts only the program found. Check every difference against the school's page before ticking `commit` on main.
