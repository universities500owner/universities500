# Internship reader

Reads internship postings and writes `src/data/internships.json`. No AI is used: titles are matched with whole-word patterns, and locations are mapped with explicit lists.

## Where the postings come from

- **Employers' public job-board feeds:** Greenhouse, Lever and Workable (the readers for Ashby and SmartRecruiters stay in the code, but both sites forbid automated reading in robots.txt, so their employers sit under `blockedByRobots` and are not asked). Each company has its own board, so the list of companies is in `data/internship_sources.json` under `employers` (`{name, ats, slug}`; the slug is the last part of the company's careers page address on that system). The first list was written from general knowledge and is unverified. A run asks each company live and the report lists the ones that do not exist, so they can be deleted.
- **Open feeds:** Sweden's Platsbanken (JobTech open data, CC0) and Arbeitnow (Germany and Europe; free API, asks for a link back).
- **Link-only portals:** `portals` in the same file. We do not read them. A run only checks that each link loads and records the site's robots.txt in the report.

Not included yet: Norway's NAV feed (needs a token and acceptance of its terms), Canada's Job Bank monthly open data, and Adzuna (its terms need a closer look for a free student site).

## What is kept

A posting is kept only if its title names an internship, co-op, placement or working-student role (`titles.py`), or the employer's own system labels it as an intern role, and its location is clearly one of our 14 destinations (`places.py`). Remote-only, unclear or two-country locations are skipped. PhD, high-school and staff roles about internship programmes are skipped. The word "stage" counts only in France and the Netherlands.

We store the title, company, city, destination, link, source and the dates. We do not store descriptions, logos or recruiter details.

## Cadence and safety nets

- `.github/workflows/internships.yml` runs daily and commits the data to `main`. From the Actions tab it can also be run by hand (`only` = employer slugs or `open`, `limit` = first N employers).
- Polite: obeys robots.txt and Crawl-delay, waits 2 seconds between requests to the same host, identifies itself as `Universities500Bot` with a link to `/bot/` and the `CONTACT_EMAIL` address (variable or secret).
- A board that fails to load keeps its last postings. A posting missing from a board that loaded fine is dropped after 2 runs in a row.
- If a run would remove more than half the postings, it stops with exit code 3 and writes nothing. `--allow-drop` overrides.
- Each run uploads a report (`internship_report.md`, `boards.csv`, `sample_items.json`, `robots_blocked.txt`) as the `internship-run` artifact.

## Publishing

`src/data/internship_publish.json` has `"publish": false` until the first run's `sample_items.json` has been checked against the employers' own pages. Set it to `true` to show listings. `/internships/` stays `noindex` until it is removed from the UNCHECKED list in `src/lib/noindex.js`.

## Run it locally

```
python3 scripts/internships/test_internships.py
python3 scripts/internships/run.py --only open --out /tmp/int.json --report /tmp/int-report
```

## Extra facts on a posting

Each posting always has a title, company, city, link and the date it was posted. Four more facts are copied **only when the employer's own feed states them**. If the feed is silent, the card says "check the listing". Nothing is estimated, converted or guessed.

| Field | Where it comes from |
|---|---|
| `pay` | Lever `salaryRange`; Greenhouse `pay_input_ranges` (read from each posting's own page, see below). Shown exactly as stated, for example `USD 45–55 / hour`. The period (hour, month, year) is added only when the feed names it. If one posting lists several location-based ranges, the card shows the lowest to the highest. |
| `team` | Lever team or department; Greenhouse department; Workable department; the first tag on an Arbeitnow listing. |
| `deadline` | Sweden's JobTech `application_deadline`. The other feeds do not publish a closing date. |
| `mode` | On-site, hybrid or remote, where Lever says so, or remote where Workable or Arbeitnow flag it. |

Greenhouse's list feed carries neither pay nor department, so each Greenhouse posting is read once from its own page (`/jobs/<id>`). A run reads at most 150 per run (`ENRICH_CAP` in `run.py`), and a posting already read is not asked again. The log prints `Greenhouse detail: N postings asked, N read, N with a pay range`.
