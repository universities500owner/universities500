#!/usr/bin/env python3
"""Add ROR facts to the pool candidates: Wikidata id, organisation type, status, founding year.

Source: the ROR data dump (CC0), downloaded once from Zenodo. No API key and no per-institution calls.

Usage:
  python enrich_ror.py                        # reads pool_candidates.csv, writes pool_enriched.csv
  python enrich_ror.py --dump ror.zip         # use a dump you already have (zip or .json)

A "note" column marks rows worth a human look: no ROR id, id not found, not typed as education, or not active.
"""
import argparse
import csv
import io
import json
import sys
import urllib.request
import zipfile

UA = "Universities500-pool-pilot/0.1 (research list building; https://universities500.com)"
ZENODO_URLS = [
    "https://zenodo.org/api/communities/ror-data/records?sort=newest&size=1",
    "https://zenodo.org/api/records?communities=ror-data&sort=mostrecent&size=1",
]


def get_bytes(url, timeout=600):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def file_list(rec):
    """(name, url) pairs from a Zenodo record, whichever response shape it uses."""
    out = []
    f = rec.get("files")
    if isinstance(f, list):
        for x in f:
            links = x.get("links") or {}
            out.append((x.get("key") or x.get("filename"), links.get("self") or links.get("download")))
    elif isinstance(f, dict):
        for k, x in (f.get("entries") or {}).items():
            links = x.get("links") or {}
            out.append((x.get("key", k), links.get("content") or links.get("self")))
    return [(k, u) for k, u in out if k and u]


def latest_dump():
    last = None
    for u in ZENODO_URLS:
        try:
            rec = json.loads(get_bytes(u, 60))["hits"]["hits"][0]
            zips = [(k, v) for k, v in file_list(rec) if k.lower().endswith(".zip")]
            if zips:
                md = rec.get("metadata") or {}
                return {"url": zips[0][1], "name": zips[0][0], "version": md.get("version", ""), "date": md.get("publication_date", "")}
        except Exception as e:  # try the next endpoint
            last = e
    raise RuntimeError(f"could not find the latest ROR data dump on Zenodo: {last}")


def load_records(data, name=""):
    if name.lower().endswith(".json") or data[:1] in (b"[", b"{"):
        return json.loads(data)
    z = zipfile.ZipFile(io.BytesIO(data))
    members = [n for n in z.namelist() if n.lower().endswith(".json")]
    pick = [n for n in members if "schema_v2" in n] or members
    if not pick:
        raise RuntimeError("no JSON file inside the ROR dump")
    return json.loads(z.read(pick[0]))


def short(ror):
    return (ror or "").strip().rstrip("/").rsplit("/", 1)[-1]


def facts(rec):
    wd = ""
    for e in rec.get("external_ids") or []:
        if e.get("type") == "wikidata":
            wd = e.get("preferred") or (e.get("all") or [""])[0]
    names = rec.get("names") or []
    disp = next((n.get("value") for n in names if "ror_display" in (n.get("types") or [])), "") or (names[0].get("value") if names else "")
    country = ""
    for loc in rec.get("locations") or []:
        country = (loc.get("geonames_details") or {}).get("country_code") or country
    return {
        "ror_name": disp,
        "ror_types": ";".join(rec.get("types") or []),
        "ror_status": rec.get("status") or "",
        "ror_established": rec.get("established") or "",
        "ror_country": country,
        "ror_wikidata": wd,
        "ror_predecessors": ";".join(short(x.get("id")) for x in rec.get("relationships") or [] if x.get("type") == "predecessor"),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--candidates", default="pool_candidates.csv")
    ap.add_argument("--out", default="pool_enriched.csv")
    ap.add_argument("--dump", default="", help="local ROR dump (zip or json) instead of downloading")
    a = ap.parse_args(argv)

    rows = list(csv.DictReader(open(a.candidates, encoding="utf-8")))
    if not rows:
        sys.exit("No candidates found in " + a.candidates)
    need = {short(r.get("ror")) for r in rows if short(r.get("ror"))}

    if a.dump:
        data, src = open(a.dump, "rb").read(), {"name": a.dump, "version": "", "date": ""}
    else:
        src = latest_dump()
        print(f"Downloading ROR dump {src['name']} (version {src['version']}, published {src['date']}) ...", file=sys.stderr)
        data = get_bytes(src["url"])
    records = load_records(data, src["name"])
    index = {short(r.get("id")): r for r in records if short(r.get("id")) in need}
    print(f"ROR dump: {len(records):,} records; {len(index)} of {len(need)} candidate ROR ids found.")

    extra = ["ror_name", "ror_types", "ror_status", "ror_established", "ror_country", "ror_wikidata", "ror_predecessors",
             "wikidata_final", "ror_note", "works_combined", "merged_from"]
    out_rows, notes = [], []
    for r in rows:
        rid = short(r.get("ror"))
        f = {k: "" for k in extra}
        if not rid:
            f["ror_note"] = "no ROR id in OpenAlex"
        elif rid not in index:
            f["ror_note"] = "ROR id not in dump"
        else:
            f.update(facts(index[rid]))
            bits = []
            if "education" not in f["ror_types"].split(";"):
                bits.append(f"not typed education ({f['ror_types'] or 'no type'})")
            if f["ror_status"] and f["ror_status"] != "active":
                bits.append(f"status {f['ror_status']}")
            f["ror_note"] = "; ".join(bits)
        f["wikidata_final"] = r.get("wikidata") or f["ror_wikidata"]
        r.update(f)
        out_rows.append(r)
        if f["ror_note"]:
            notes.append(r)

    # An active institution formed by a merger starts with little publication history of its own, so its
    # threshold count includes the institutions it was formed from (found among the candidates).
    by_ror = {short(r["ror"]): r for r in out_rows if short(r.get("ror"))}

    def combined(r, seen):
        total, names = int(r["works_count"] or 0), []
        for pid in filter(None, (r.get("ror_predecessors") or "").split(";")):
            pr = by_ror.get(pid)
            if pr and pid not in seen:
                seen.add(pid)
                sub_total, sub_names = combined(pr, seen)
                total += sub_total
                names += [pr["name"]] + sub_names
        return total, names

    merged = []
    for r in out_rows:
        own = int(r["works_count"] or 0)
        r["works_combined"], r["merged_from"] = own, ""
        if r["ror_status"] in ("", "active") and r.get("ror_predecessors"):
            tot, names = combined(r, {short(r["ror"])})
            if names:
                r["works_combined"], r["merged_from"] = tot, ";".join(names)
                merged.append((r, own, tot))

    with open(a.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)

    before = sum(1 for r in out_rows if r.get("wikidata"))
    after = sum(1 for r in out_rows if r["wikidata_final"])
    print(f"Wikidata ids: {before} of {len(out_rows)} from OpenAlex, {after} after adding ROR.")
    print(f"Active institutions formed by a merger (counts combined): {len(merged)}")
    for r, own, tot in sorted(merged, key=lambda x: (x[0]["country"], -x[2])):
        print(f"  {r['country']}\t{own:>9,} -> {tot:>9,}\t{r['name']}\tfrom: {r['merged_from']}")
    print(f"Rows with a note: {len(notes)}")
    for r in sorted(notes, key=lambda r: (r["country"], -int(r["works_count"] or 0))):
        print(f"  {r['country']}\t{int(r['works_count']):>9,}\t{r['name']}\t{r['ror_note']}")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as err:
        sys.exit(f"Stopped: {err}")
