#!/usr/bin/env python3
"""Check pool candidates against official registers of institutions that can enrol international students.

Registers handled (each is the government's own list):
  AU  CRICOS institutions         data.gov.au, CC BY 2.5 AU
  GB  Register of licensed sponsors: students   GOV.UK (UK Visas and Immigration)
  CA  Designated learning institutions list     IRCC, canada.ca
  US  SEVP-certified schools                    DHS Study in the States

Usage:
  python eligibility.py --fetch               # download the registers, then match
  python eligibility.py                       # match against files already in ./registers

Status per candidate: confirmed (same website or same name), likely (close or contained name; needs a look),
not_found, or not_checked (no register for that country yet). The log shows what each register looked like,
because these files change layout from time to time.
"""
import argparse
import csv
import difflib
import html.parser
import io
import json
import os
import re
import sys
import unicodedata
import urllib.parse
import urllib.request

UA = "Universities500-pool-pilot/0.1 (research list building; https://universities500.com)"

REGISTERS = {
    "AU": dict(
        label="CRICOS institutions (Australian Government Department of Education, data.gov.au, CC BY 2.5 AU)",
        url="https://data.gov.au/data/dataset/e5ae7059-bfa8-4fa4-a5c0-c13cf3520193/resource/7f6941f3-5327-4db7-b556-5f16d77f63c1/download/cricos-institutions.csv",
        name_keys=["institution name", "trading name"], site_keys=["website"]),
    "GB": dict(
        label="Register of licensed sponsors: students (UK Visas and Immigration, GOV.UK)",
        page="https://www.gov.uk/government/publications/register-of-licensed-sponsors-students",
        link_re=r"https://assets\.publishing\.service\.gov\.uk/[^\"'\s>]+\.csv",
        name_keys=["organisation name"], site_keys=[]),
    "CA": dict(
        label="Designated learning institutions list (Immigration, Refugees and Citizenship Canada)",
        page="https://www.canada.ca/en/immigration-refugees-citizenship/services/study-canada/study-permit/prepare/designated-learning-institutions-list.html",
        html=True, name_keys=["institution"], site_keys=[]),
    "US": dict(
        label="SEVP-certified schools (US Department of Homeland Security, Study in the States)",
        page="https://studyinthestates.dhs.gov/school-search",
        name_keys=["school name", "campus name"], site_keys=[]),
}
ABBR = {"univ": "university", "coll": "college", "inst": "institute", "st": "saint"}


def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(ABBR.get(t, t) for t in s.split() if t != "the")


def host(url):
    if not url:
        return ""
    h = urllib.parse.urlsplit(url if "//" in url else "//" + url).hostname or ""
    return h[4:] if h.startswith("www.") else h


def decode(b):
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            pass
    return b.decode("utf-8", "replace")


# ---------- reading register files ----------
def table_from_rows(rows):
    """First row with two or more filled cells is the header."""
    for i, row in enumerate(rows):
        if sum(1 for c in row if str(c).strip()) >= 2:
            headers = [str(h).strip().lower() for h in row]
            return headers, [dict(zip(headers, [str(c).strip() for c in r])) for r in rows[i + 1:]]
    return [], []


def read_csv(b):
    return table_from_rows(list(csv.reader(io.StringIO(decode(b)))))


def read_xlsx(path):
    import openpyxl  # installed by the workflow
    ws = openpyxl.load_workbook(path, read_only=True, data_only=True).worksheets[0]
    return table_from_rows([["" if c is None else c for c in r] for r in ws.iter_rows(values_only=True)])


class Tables(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables, self._t, self._r, self._c = [], None, None, None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._t = []
            self.tables.append(self._t)
        elif tag == "tr" and self._t is not None:
            self._r = []
            self._t.append(self._r)
        elif tag in ("td", "th") and self._r is not None:
            self._c = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._c is not None and self._r is not None:
            self._r.append(" ".join("".join(self._c).split()))
            self._c = None
        elif tag == "tr":
            self._r = None
        elif tag == "table":
            self._t = None

    def handle_data(self, d):
        if self._c is not None:
            self._c.append(d)


def read_html(b):
    p = Tables()
    p.feed(decode(b))
    best = ([], [])
    for t in p.tables:
        headers, rows = table_from_rows(t)
        if len(rows) > len(best[1]):
            best = (headers, rows)
    return best


def load_register_file(path):
    raw = open(path, "rb").read()
    ext = os.path.splitext(path)[1].lower()
    if ext == ".xlsx":
        return read_xlsx(path)
    if ext in (".html", ".htm"):
        return read_html(raw)
    return read_csv(raw)


def build(spec, headers, rows):
    """Return (names, hosts, info): normalised name -> display name, website host -> display name."""
    name_cols = [h for h in headers if any(k in h for k in spec["name_keys"])]
    fallback = False
    if not name_cols:  # layout changed: use any 'name' column, else the second column
        name_cols = [h for h in headers if "name" in h] or headers[1:2]
        fallback = True
    site_cols = [h for h in headers if any(k in h for k in spec.get("site_keys", []))]
    names, hosts = {}, {}
    for r in rows:
        disp = ""
        for h in name_cols:
            v = (r.get(h) or "").strip()
            if v:
                disp = disp or v
                names.setdefault(norm(v), v)
        for h in site_cols:
            hh = host(r.get(h, ""))
            if hh and disp:
                hosts.setdefault(hh, disp)
    return names, hosts, {"name_cols": name_cols, "site_cols": site_cols, "fallback": fallback, "rows": len(rows)}


# ---------- downloading ----------
def fetch_bytes(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read(), dict(r.headers)


def find_download(page_html, base, spec):
    if spec.get("link_re"):
        m = re.search(spec["link_re"], page_html)
        if m:
            return m.group(0)
    anchors = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', page_html, re.S | re.I)
    for href, text in anchors:  # a link labelled download, or any csv/xlsx link
        t = re.sub(r"<[^>]+>", " ", text).lower()
        if ("download" in t and "list" in t) or re.search(r"\.(csv|xlsx)(\?|$)", href, re.I):
            return urllib.parse.urljoin(base, href)
    return ""


def fetch(cc, spec, outdir):
    os.makedirs(outdir, exist_ok=True)
    url = spec.get("url")
    if not url:
        page, _ = fetch_bytes(spec["page"])
        if spec.get("html"):
            path = os.path.join(outdir, f"{cc}.html")
            open(path, "wb").write(page)
            return path, {"url": spec["page"], "bytes": len(page), "last_modified": ""}
        url = find_download(decode(page), spec["page"], spec)
        if not url:
            raise RuntimeError("could not find the download link on " + spec["page"])
    data, headers = fetch_bytes(url)
    ext = ".xlsx" if re.search(r"\.xlsx(\?|$)", url, re.I) else ".csv"
    path = os.path.join(outdir, cc + ext)
    open(path, "wb").write(data)
    lm = next((v for k, v in headers.items() if k.lower() == "last-modified"), "")
    return path, {"url": url, "bytes": len(data), "last_modified": lm}


# ---------- matching ----------
def match(cand, names, hosts, norms):
    h = host(cand.get("homepage", ""))
    if h and h in hosts:
        return "confirmed", "same website", hosts[h]
    for nm in (cand.get("name", ""), cand.get("ror_name", "")):
        n = norm(nm)
        if n and n in names:
            return "confirmed", "same name", names[n]
    n = norm(cand.get("name", ""))
    if len(n.split()) >= 3:
        pat = f" {n} "
        for k, v in names.items():
            if pat in f" {k} ":
                return "likely", "register name contains it", v
    cm = difflib.get_close_matches(n, norms, n=1, cutoff=0.9)
    if cm:
        return "likely", "close name", names[cm[0]]
    return "not_found", "", ""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--candidates", default="")
    ap.add_argument("--registers", default="registers", help="folder holding (or receiving) the register files")
    ap.add_argument("--countries", default=",".join(REGISTERS))
    ap.add_argument("--fetch", action="store_true", help="download the registers first")
    ap.add_argument("--out", default="pool_eligibility.csv")
    ap.add_argument("--summary", default="eligibility_summary.md")
    a = ap.parse_args(argv)

    cpath = a.candidates or ("pool_enriched.csv" if os.path.exists("pool_enriched.csv") else "pool_candidates.csv")
    cands = list(csv.DictReader(open(cpath, encoding="utf-8")))
    ccs = [c.strip().upper() for c in a.countries.split(",") if c.strip()]
    print(f"Candidates: {len(cands)} rows from {cpath}")

    result, lines = {}, ["# Eligibility check against official registers", ""]
    for cc in ccs:
        spec = REGISTERS[cc]
        meta, err = {}, ""
        try:
            if a.fetch:
                path, meta = fetch(cc, spec, a.registers)
            else:
                path = next((os.path.join(a.registers, f) for f in sorted(os.listdir(a.registers)) if f.split(".")[0] == cc and not f.endswith(".json")), "")
                if not path:
                    raise RuntimeError(f"no file for {cc} in {a.registers}")
            headers, rows = load_register_file(path)
            names, hosts, info = build(spec, headers, rows)
        except Exception as e:
            print(f"\n[{cc}] register unavailable: {e}")
            lines.append(f"- {cc}: register unavailable ({e})")
            result[cc] = None
            continue
        print(f"\n[{cc}] {spec['label']}")
        print(f"  file: {os.path.basename(path)}  rows: {info['rows']}  {json.dumps(meta)}")
        print(f"  columns: {headers}")
        print(f"  name columns used: {info['name_cols']}{'  (FALLBACK: layout not as expected)' if info['fallback'] else ''}; website columns: {info['site_cols']}")
        print(f"  sample: {[dict(list(r.items())[:4]) for r in rows[:2]]}")
        norms = list(names)
        result[cc] = (spec, meta, names, hosts, norms, info)

    fields = list(cands[0].keys()) + ["elig_register", "elig_status", "elig_how", "elig_register_name"]
    review = {}
    for c in cands:
        cc = c["country"]
        res = result.get(cc)
        if cc not in REGISTERS:
            st, how, rn, reg = "not_checked", "no register set up for this country yet", "", ""
        elif res is None:
            st, how, rn, reg = "not_checked", "register unavailable in this run", "", REGISTERS[cc]["label"]
        else:
            st, how, rn = match(c, res[2], res[3], res[4])
            reg = res[0]["label"]
        c.update(elig_register=reg, elig_status=st, elig_how=how, elig_register_name=rn)
        if st in ("likely", "not_found") and c["is_child"] == "no":
            review.setdefault(cc, []).append(c)

    with open(a.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(cands)

    lines += ["Parent institutions only (faculties and schools inside a parent are left out).", "",
              "| Country | Candidates | Confirmed | Likely (check) | Not found |", "|---|---:|---:|---:|---:|"]
    for cc in ccs:
        if result.get(cc) is None:
            continue
        mine = [c for c in cands if c["country"] == cc and c["is_child"] == "no"]
        k = {s: sum(1 for c in mine if c["elig_status"] == s) for s in ("confirmed", "likely", "not_found")}
        lines.append(f"| {cc} | {len(mine)} | {k['confirmed']} | {k['likely']} | {k['not_found']} |")
    for cc, meta in ((cc, result[cc][1]) for cc in ccs if result.get(cc)):
        lines.append(f"\n{cc}: {REGISTERS[cc]['label']}. File: {meta.get('url', 'local')}. Last-Modified: {meta.get('last_modified') or 'not given'}.")
    open(a.summary, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n" + "\n".join(lines))

    for cc, rows in review.items():
        print(f"\n[{cc}] needs a look ({len(rows)}):")
        for c in sorted(rows, key=lambda c: -int(c["works_count"] or 0)):
            print(f"  {int(c['works_count']):>9,}\t{c['name']}\t{c['elig_status']}\t{c['elig_register_name']}\t{c['elig_how']}")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as err:
        sys.exit(f"Stopped: {err}")
