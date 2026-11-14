#!/usr/bin/env python3
"""Pilot: how many research-active universities does open data find in each country?

Source: OpenAlex (open scholarly metadata, CC0). No university ranking is read or used.
Uses only the Python standard library.

Usage:
  python pool_pilot.py --mailto you@example.com                 # the 14 countries
  python pool_pilot.py --mailto you@example.com --countries AU,CA

Writes two files in the current folder:
  pool_candidates.csv   one row per institution (name, country, Wikidata id, publication counts)
  pool_summary.md       how many institutions pass each publication-count threshold, per country

Be polite: one request at a time, a pause between requests, and your email in the request so
OpenAlex can contact you if something goes wrong (their "polite pool").
"""
import argparse
import csv
import datetime
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

COUNTRIES = {
    "AU": "Australia", "US": "United States", "GB": "United Kingdom", "CA": "Canada", "IE": "Ireland",
    "NZ": "New Zealand", "DE": "Germany", "FR": "France", "NL": "Netherlands", "SG": "Singapore",
    "AE": "United Arab Emirates", "MY": "Malaysia", "SE": "Sweden", "NO": "Norway",
}
THRESHOLDS = [1000, 2500, 5000, 10000, 20000]
FIELDS = "id,display_name,country_code,type,works_count,cited_by_count,summary_stats,ids,homepage_url,lineage"
UA = "Universities500-pool-pilot/0.1 (research list building; https://universities500.com)"


def get(url, tries=4):
    """GET a JSON document. Retries on rate limits and server errors; a 400 is raised to the caller."""
    last = None
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 400:
                raise
            last = e
            if e.code not in (429, 500, 502, 503, 504):
                raise
        except urllib.error.URLError as e:
            last = e
        time.sleep(2 ** (k + 1))
    raise RuntimeError(f"giving up on {url}: {last}")


def qid_of(ids):
    w = (ids or {}).get("wikidata") or ""
    return w.rsplit("/", 1)[-1] if w else ""


def parse(r):
    stats = r.get("summary_stats") or {}
    lineage = r.get("lineage") or []
    return {
        "country": r.get("country_code") or "",
        "name": r.get("display_name") or "",
        "openalex_id": (r.get("id") or "").rsplit("/", 1)[-1],
        "wikidata": qid_of(r.get("ids")),
        "homepage": r.get("homepage_url") or "",
        "works_count": int(r.get("works_count") or 0),
        "cited_by_count": int(r.get("cited_by_count") or 0),
        "h_index": stats.get("h_index") if stats.get("h_index") is not None else "",
        # A faculty, school or institute that sits inside a parent institution has a longer lineage.
        "is_child": "yes" if len(lineage) > 1 else "no",
    }


def fetch_country(base, cc, min_works, mailto, pause):
    """All education institutions in one country with at least min_works publications, biggest first."""
    rows = []
    use_select = True
    cursor = "*"
    while True:
        params = {
            "filter": f"country_code:{cc},type:education",
            "sort": "works_count:desc",
            "per-page": "100",
            "cursor": cursor,
        }
        if use_select:
            params["select"] = FIELDS
        if mailto:
            params["mailto"] = mailto
        url = base.rstrip("/") + "/institutions?" + urllib.parse.urlencode(params, safe=":,*")
        try:
            data = get(url)
        except urllib.error.HTTPError as e:
            if e.code == 400 and use_select:  # the API rejected the field list: ask for everything instead
                use_select = False
                continue
            raise
        results = data.get("results") or []
        for r in results:
            if int(r.get("works_count") or 0) < min_works:
                return rows
            rows.append(parse(r))
        cursor = (data.get("meta") or {}).get("next_cursor")
        if not cursor or not results:
            return rows
        time.sleep(pause)


def write_outputs(all_rows, ccs, min_works, when):
    cols = ["country", "name", "openalex_id", "wikidata", "homepage", "works_count", "cited_by_count", "h_index", "is_child"]
    with open("pool_candidates.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(all_rows)

    lines = [
        "# Open-data pool pilot",
        "",
        f"Run on {when}. Source: OpenAlex institutions of type education, counted by number of publications.",
        f"Only institutions with at least {min_works:,} publications were fetched. "
        "Faculties and schools inside a parent institution are left out of these counts (they are marked in the CSV).",
        "",
        "| Country | " + " | ".join(f"≥ {t:,}" for t in THRESHOLDS if t >= min_works) + " |",
        "|---|" + "---:|" * len([t for t in THRESHOLDS if t >= min_works]),
    ]
    totals = {t: 0 for t in THRESHOLDS}
    for cc in ccs:
        mine = [r for r in all_rows if r["country"] == cc and r["is_child"] == "no"]
        cells = []
        for t in THRESHOLDS:
            if t < min_works:
                continue
            n = sum(1 for r in mine if r["works_count"] >= t)
            totals[t] += n
            cells.append(str(n))
        lines.append(f"| {COUNTRIES.get(cc, cc)} | " + " | ".join(cells) + " |")
    lines.append("| **Total** | " + " | ".join(f"**{totals[t]}**" for t in THRESHOLDS if t >= min_works) + " |")
    lines += [
        "",
        "Notes",
        "- Publication count measures research volume, so it favours large institutions and medical schools.",
        "- Not every institution here takes international students. That needs an official register for each country.",
        "- OpenAlex can hold duplicates or non-university colleges. Check the CSV before anything is published.",
    ]
    open("pool_summary.md", "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mailto", default="", help="your email, sent to OpenAlex so they can contact you (recommended)")
    ap.add_argument("--countries", default=",".join(COUNTRIES), help="comma-separated ISO codes, e.g. AU,CA")
    ap.add_argument("--min-works", type=int, default=1000, help="stop below this many publications (default 1000)")
    ap.add_argument("--base-url", default="https://api.openalex.org", help="API root (only change this for testing)")
    ap.add_argument("--pause", type=float, default=0.5, help="seconds to wait between requests")
    a = ap.parse_args(argv)

    ccs = [c.strip().upper() for c in a.countries.split(",") if c.strip()]
    bad = [c for c in ccs if c not in COUNTRIES]
    if bad:
        sys.exit(f"Unknown country code(s): {', '.join(bad)}. Use any of: {', '.join(COUNTRIES)}")
    if not a.mailto:
        print("Tip: add --mailto your@email so OpenAlex can reach you if needed.", file=sys.stderr)

    all_rows = []
    for cc in ccs:
        print(f"Fetching {COUNTRIES[cc]} ...", file=sys.stderr)
        all_rows += fetch_country(a.base_url, cc, a.min_works, a.mailto, a.pause)
        time.sleep(a.pause)
    write_outputs(all_rows, ccs, a.min_works, datetime.date.today().isoformat())


if __name__ == "__main__":
    main()
