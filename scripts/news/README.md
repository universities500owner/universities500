# Industry news

A daily reader of official news for international students, for the 14 destination countries. It feeds the **Industry news** menu item, the strip of the four newest headlines above the footer, and the `/industry-news/` page.

## What it keeps, and what it never does

- **Sources**: government and immigration bodies, and official study agencies, listed in `data/news_sources.json`. Each source says which website addresses are its own (`domains`); a link anywhere else is dropped.
- **Text**: the headline, the date and the note are the official body's own words. The note is the first sentences of the official summary, cut at a sentence end (at most about 360 characters). Nothing is rewritten, nothing is generated, no AI is used.
- **Language**: English official pages only. Items in another language are dropped, never translated.
- **Relevance**: sources marked `filter: "student"` keep an item only if it has a strong word (student visa, study permit, graduate route, SEVP, ...), or a student word together with an international or visa word. A source marked `context: "immigration"` is an immigration authority, so a student word alone is enough. Enforcement and crime headlines (arrests, detainers, convictions) and items about asylum or borders are dropped even when a student is named. Sources marked `filter: "all"` (study agencies that only publish for students) keep everything. Word lists are in `news_rules.py`.
- **Dates**: an item with no readable date is skipped. A numeric date such as 03/04/2026 is never guessed.
- **Age and size**: an item stays 120 days, at most 30 per country. Six stored items are re-opened each run; one whose official page is gone (404 or 410) is removed.
- **Safety**: if no source answers in a run, the data file is left exactly as it was and the run fails loudly.

## How a source is read (first one that gives items wins)

1. `feeds[]`: RSS, Atom or RDF addresses.
2. `fr[]`: Federal Register search terms (US only, official JSON API).
3. `home`: the page is opened and searched for a `<link rel="alternate">` feed.
4. `list`: a page of dated headlines, read from its HTML. Blocks with one link and a readable date count.

When the feed has no summary, up to four official article pages per source are opened to read the page's own description.

## Files

| file | what |
|---|---|
| `data/news_sources.json` | the list of official sources. Edit it to add or retire one |
| `src/data/industry_news.json` | the result, written by the daily run |
| `src/data/industry_news_publish.json` | `publish: false` keeps everything off the site |
| `.github/workflows/news.yml` | daily at 05:47 India time, plus a manual trial mode |
| `scripts/news/news_*.py` | rules, feed readers, source reader, runner |
| `scripts/news/test_news.py` | offline tests against a stub website |

## Running it

- **Trial (writes nothing)**: Actions > *Industry news (read official sources)* > Run workflow, leave *probe* ticked. The whole report is also printed in the job log. Or download the `news-run` artifact: `news_report.md` (per-source table, addresses tried, examples the relevance rule rejected) and `news_probe.json`.
- **Real run**: untick *probe*, tick *commit*, run it from `main`. A run from any other branch never commits.
- **One country**: type its code in *only* (for example `uk`).
- **Locally**: `python3 scripts/news/test_news.py`, then `python3 scripts/news/news_run.py --probe --only uk`.

## Going live

1. Run a trial and read `news_report.md`. A source that gave nothing is fixed by editing its addresses in `data/news_sources.json`.
2. Merge, then run once from `main` with *commit* ticked. Read the items in `src/data/industry_news.json` against the official pages.
3. Set `publish` to `true` in `src/data/industry_news_publish.json`. That one edit adds the menu item, the footer link, the strip above the footer, the search entry and the sitemap entry, and lets the page be indexed.
