#!/usr/bin/env python3
"""Build src/data/universities.json for the site from the working data files.

Usage: prep_data.py <uni_auto.json> <uni_list.json> <out.json>

Rules (set 2026-11-14):
- No ranking data goes to the site: the rank fields (r, p) are dropped.
- The size and type fields (z, s) came with the same list, so they are dropped too until
  they are rebuilt from open sources (Wikidata).
- News headlines and logos are not shipped in phase 1.
- Only text that has a source URL is kept. Overview text is Wikipedia (CC BY-SA 4.0),
  facts are Wikidata (CC0).
"""
import json
import re
import sys

# Sentences that talk about rankings are dropped from the Wikipedia overviews (no ranking text on the
# site for now). Every drop is logged to scripts/rank_scrub_report.txt so it can be reviewed.
RANKY = re.compile(
    r"\branking|\branked|\brankings|\bQS\b|Times Higher|U\.S\. News|US News|\btop[- ]\d+|"
    r"highest[- ]ranked|world[- ]class|\bbest universit",
    re.I,
)

COUNTRIES = {
    "usa": "United States", "uk": "United Kingdom", "germany": "Germany", "australia": "Australia",
    "canada": "Canada", "france": "France", "netherlands": "Netherlands", "malaysia": "Malaysia",
    "new-zealand": "New Zealand", "sweden": "Sweden", "ireland": "Ireland",
    "uae": "United Arab Emirates", "norway": "Norway", "singapore": "Singapore",
}


def main(auto_path, list_path, out_path):
    auto = json.load(open(auto_path, encoding="utf-8"))
    base = json.load(open(list_path, encoding="utf-8"))
    out = []
    report = []
    for row in base:
        uid = row["id"]
        a = auto.get(uid, {})
        name = a.get("formal") or row["n"]
        rec = {
            "slug": uid,
            "name": name,
            "country": row["c"],
            "countryName": COUNTRIES[row["c"]],
            "qid": a.get("qid"),
            "read": a.get("readD"),
        }
        if a.get("web"):
            rec["web"] = a["web"]
            rec["webSrc"] = a.get("webSrc")
        if a.get("founded"):
            rec["founded"] = {"v": a["founded"]["v"], "src": a["founded"]["src"]}
        if a.get("overview"):
            sentences = re.split(r"(?<=[.!?])\s+", a["overview"].strip())
            kept = [s for s in sentences if not RANKY.search(s)]
            for s in sentences:
                if RANKY.search(s):
                    report.append(f"{uid}: dropped sentence: {s}")
            if kept:
                rec["overview"] = " ".join(kept)
                rec["overviewSrc"] = a["overviewSrc"]
                if len(kept) != len(sentences):
                    rec["overviewTrimmed"] = True
        if a.get("campuses"):
            rec["campuses"] = a["campuses"][:6]
            rec["campusSrc"] = a.get("campusSrc")
        if a.get("alumni"):
            rec["alumni"] = [{"n": x["n"], "w": x.get("w", ""), "u": x["u"]} for x in a["alumni"][:6]]
        if a.get("stats"):
            rec["stats"] = [{"l": s["l"], "v": s["v"], "a": s.get("a"), "src": s["src"]} for s in a["stats"]]
        if a.get("ig"):
            rec["ig"] = a["ig"]
        if a.get("yt"):
            rec["yt"] = a["yt"]
        rec["wikidata"] = f"https://www.wikidata.org/wiki/{a['qid']}" if a.get("qid") else None
        # A page is listed (indexable, in the sitemap) only when it has real content.
        rec["listed"] = bool(rec.get("overview") and rec.get("web") and rec.get("founded") and rec.get("campuses"))
        out.append(rec)
    out.sort(key=lambda r: r["name"].lower())
    json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with open("scripts/rank_scrub_report.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(report) + ("\n" if report else ""))
    print(f"{len(report)} ranking sentence(s) dropped, see scripts/rank_scrub_report.txt")
    listed = sum(1 for r in out if r["listed"])
    print(f"{len(out)} universities, {listed} listed, {len(out) - listed} thin (noindex)")


if __name__ == "__main__":
    main(*sys.argv[1:4])
