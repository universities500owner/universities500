#!/usr/bin/env python3
"""Combine the checks into one pool file and count it at several publication thresholds.

Reads pool_eligibility.csv (from eligibility.py) and, if present, a file of manual decisions.
Each row gets a pool_status:
  included     parent institution, active in ROR, typed education, and confirmed on its country's register
  provisional  as above, but its country has no register check yet (or the register was unavailable)
  review       a human needs to look: no ROR record, or the register match was only "likely" or "not found"
  excluded     faculty or school inside a parent, inactive or withdrawn in ROR, or not an education organisation
Manual decisions (data/pool_overrides.csv: openalex_id, decision include|exclude, reason, source, checked_on)
override review rows only. Nothing is dropped for a name mismatch alone.

Usage: python build_pool.py [--overrides ../../data/pool_overrides.csv] [--threshold 10000]
"""
import argparse
import csv
import os
import sys

THRESHOLDS = (5000, 10000, 15000, 20000)


def status(r, ov):
    if r["is_child"] == "yes":
        return "excluded", "faculty or school inside a parent institution"
    if r.get("ror_status") not in (None, "", "active"):
        return "excluded", f"ROR status {r['ror_status']}"
    if r.get("ror_types") and "education" not in r["ror_types"].split(";"):
        return "excluded", f"ROR type {r['ror_types']}"
    d = ov.get(r["openalex_id"])
    if r.get("ror_note", "").startswith(("no ROR", "ROR id not")):
        if d:
            return ("included" if d["decision"] == "include" else "excluded"), "manual: " + d["reason"]
        return "review", r["ror_note"]
    st = r.get("elig_status", "")
    if st == "confirmed":
        return "included", r.get("elig_how", "")
    if st == "not_checked":
        return "provisional", r.get("elig_how", "")
    if d:  # likely / not_found, decided by a person
        return ("included" if d["decision"] == "include" else "excluded"), "manual: " + d["reason"]
    return "review", f"register match {st}: {r.get('elig_register_name') or r.get('elig_how', '')}"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="inp", default="pool_eligibility.csv")
    ap.add_argument("--overrides", default="")
    ap.add_argument("--out", default="pool.csv")
    ap.add_argument("--summary", default="pool_counts.md")
    ap.add_argument("--threshold", type=int, default=10000, help="threshold for the per-country table and review list")
    a = ap.parse_args(argv)

    rows = list(csv.DictReader(open(a.inp, encoding="utf-8")))
    ov = {}
    if a.overrides and os.path.exists(a.overrides):
        ov = {r["openalex_id"]: r for r in csv.DictReader(open(a.overrides, encoding="utf-8")) if r.get("openalex_id")}
    for r in rows:
        r["pool_status"], r["pool_reason"] = status(r, ov)
        r["works_used"] = int(r.get("works_combined") or r["works_count"] or 0)
    fields = list(rows[0].keys())
    with open(a.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    ccs = list(dict.fromkeys(r["country"] for r in rows))
    def count(cc, t, *sts):
        return sum(1 for r in rows if (cc is None or r["country"] == cc) and r["works_used"] >= t and r["pool_status"] in sts)

    L = ["# Pool counts", "",
         f"Institutions with at least {a.threshold:,} publications (merged institutions count their predecessors too).", "",
         "| Country | Included | Provisional | Review | Excluded |", "|---|---:|---:|---:|---:|"]
    for cc in ccs:
        L.append(f"| {cc} | " + " | ".join(str(count(cc, a.threshold, s)) for s in ("included", "provisional", "review", "excluded")) + " |")
    L.append("| **All** | " + " | ".join(f"**{count(None, a.threshold, s)}**" for s in ("included", "provisional", "review", "excluded")) + " |")
    L += ["", "Pool size at other thresholds:", "", "| Publications at least | Included + provisional | Plus review |", "|---:|---:|---:|"]
    for t in THRESHOLDS:
        L.append(f"| {t:,} | {count(None, t, 'included', 'provisional')} | {count(None, t, 'included', 'provisional', 'review')} |")
    L += ["", "Included = confirmed on the official register. Provisional = country not checked yet. Review = needs a person.",
          "Excluded rows are listed in pool.csv with the reason."]
    open(a.summary, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))

    rev = sorted((r for r in rows if r["pool_status"] == "review" and r["works_used"] >= a.threshold), key=lambda r: (r["country"], -r["works_used"]))
    print(f"\nReview list at {a.threshold:,}+ ({len(rev)}):")
    for r in rev:
        print(f"  {r['country']}\t{r['works_used']:>9,}\t{r['openalex_id']}\t{r['name']}\t{r['pool_reason']}")
    exc = [r for r in rows if r["pool_status"] == "excluded" and r["is_child"] == "no" and r["works_used"] >= a.threshold]
    print(f"\nExcluded at {a.threshold:,}+, not faculties ({len(exc)}):")
    for r in sorted(exc, key=lambda r: (r["country"], -r["works_used"])):
        print(f"  {r['country']}\t{r['works_used']:>9,}\t{r['name']}\t{r['pool_reason']}")


if __name__ == "__main__":
    main()
