# Industry news

A daily reader of official news for international students, for the 14 destination countries. It feeds the **Industry news** menu item, the strip of the four newest headlines above the footer, and the `/industry-news/` page.

## What it keeps, and what it never does

- **Sources**: government and immigration bodies, and official study agencies, listed in `data/news_sources.json`. Each source says which website addresses are its own (`domains`); a link anywhere else is dropped.
- **Text**: the headline, the date and the note are the official body's own words. The note is the first sentences of the official summary, cut at a sentence end (at most about 360 characters). Nothing is rewritten, nothing is generated, no AI is used.
- **Language**: English official pages only. Items in another language are dropped, never translated.
- **Relevance**: sources marked `filter: "student"` keep an item only if it has a strong word (student visa, study permit, graduate route, SEVP, ...), or a student word together with an international or visa word. A source marked `context: "immigration"` is an immigration authority, so a student word alone is enough. Enforcement and crime headlines (arrests, detainers, convictions) and items about asylum or borders are dropped even when a student is named. Sources marked `filter: "all"` (study agencies that only publish for students) keep everything. Word lists are in `news_rules.py`.
- **Dates**: an item with no readable date is skipped. A numeric date such as 03/04/2026 is never guessed.
- **Age and size**: an item stays 12 months (365 days), at most 60 official and 40 trade-press items per country. Six stored items are re-opened each run; one whose official page is gone (404 or 410) is removed.
- **12 months**: the first run for a source (nothing stored yet) reads back a year through the body's archives: Federal Register date filter, GOV.UK search, a site's WordPress API, long feeds. Later runs only read the last 21 days. A source that gives no archive still fills up day by day. To read every source back 12 months again (the first real run, or after adding sources), tick *backfill* in the workflow.
- **Trade press**: ICEF Monitor and The PIE News (`kind: "media"`, `country: "*"`, `tag: true`, `filter: "policy"`). They are not official. Only the headline, the date and the link are stored, never the publisher's text. The country comes from the headline (an item can sit under up to three), and only headlines with a policy word (visa, cap, permit, fee, rule...) are kept. They show under the official items of each country, labelled as trade press, and never in the strip above the footer.
- **Safety**: if no source answers in a run, the data file is left exactly as it was and the run fails loudly.

## How a source is read

Every endpoint that gives items is used, and the items are merged by address:

1. `feeds[]`: RSS, Atom or RDF addresses.
2. `fr[]`: Federal Register search terms (US only, official JSON API).
3. `govuk{orgs, q}`: the GOV.UK search API for an organisation and search words (UK only). `wp{base, queries, pages}`: a site's WordPress API, searched by word, paged.
4. `home`: opened and searched for a `<link rel="alternate">` feed.
5. `list` (one address or several): pages of dated headlines, read from their HTML. A block with one link and a readable date counts.
6. Only when nothing came from the above: the news pages the home page links to (link text or address says news, press, media, latest, notices), on the body's own domains.

A page that loads but gives no items is described in the report (visible text, links, `<time>` tags, dates, scripts) so it is clear whether the headlines are loaded by script. When the feed has no summary, up to four official article pages per source are opened to read the page's own description.

A source with no items gets one of these statuses: `blocked` (robots.txt, or the site answers 401/403/429: we never work around it), `unreadable` (the page loads but no headlines can be read), `failed` (not reached or not found). The page lists the body with a short note so a reader knows to open its site.

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
- **Real run**: untick *probe*, tick *commit* (and tick *backfill* the first time), run it from `main`. A run from any other branch never commits.
- **One country**: type its code in *only* (for example `uk`).
- **Locally**: `python3 scripts/news/test_news.py`, then `python3 scripts/news/news_run.py --probe --only uk`.

## Going live

1. Run a trial and read `news_report.md`. A source that gave nothing is fixed by editing its addresses in `data/news_sources.json`.
2. Merge, then run once from `main` with *commit* ticked. Read the items in `src/data/industry_news.json` against the official pages.
3. Set `publish` to `true` in `src/data/industry_news_publish.json`. That one edit adds the menu item, the footer link, the strip above the footer, the search entry and the sitemap entry, and lets the page be indexed.
