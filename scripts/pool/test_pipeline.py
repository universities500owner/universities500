"""Checks enrich_ror.py and eligibility.py on small fixtures (no internet). Run: python3 test_pipeline.py"""
import contextlib
import csv
import io
import json
import os
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import eligibility as el
import enrich_ror as er

COLS = ["country", "name", "openalex_id", "wikidata", "ror", "homepage", "works_count", "cited_by_count", "h_index", "is_child"]
def cand(cc, name, ror="", home="", works=50000, wd="", child="no"):
    return dict(country=cc, name=name, openalex_id="I1", wikidata=wd, ror=ror, homepage=home, works_count=works, cited_by_count=0, h_index="", is_child=child)

CANDS = [
    cand("AU", "The University of Melbourne", "01ej9dk98", "https://www.unimelb.edu.au"),
    cand("AU", "Monash University", "02bfwt286", "https://www.monash.edu", wd="Q598841"),
    cand("AU", "Bond University", "", "https://bond.edu.au", works=14000),
    cand("CA", "St. Boniface Hospital", "0hosp0001", "https://www.saintboniface.ca", works=5000),
    cand("CA", "University of Toronto", "03dbr7087", "https://www.utoronto.ca"),
    cand("CA", "Université de Montréal", "0161xgx34", "https://www.umontreal.ca"),
    cand("GB", "University of Oxford", "052gg0110", "https://www.ox.ac.uk"),
    cand("GB", "University of Bath", "002h8g185", "https://www.bath.ac.uk"),
    cand("US", "University of Michigan–Ann Arbor", "00jmfr291", "https://umich.edu"),
    cand("US", "Medical School of Big Uni", "0child0001", "https://med.example.edu", works=8000, child="yes"),
    cand("DE", "Technical University of Munich", "02kkvpp62", "https://www.tum.de"),
]

def ror_rec(rid, name, types, wd="", status="active", est=1853):
    return {"id": f"https://ror.org/{rid}", "status": status, "types": types, "established": est,
            "names": [{"value": name, "types": ["ror_display", "label"]}],
            "locations": [{"geonames_details": {"country_code": "AU"}}],
            "external_ids": ([{"type": "wikidata", "all": [wd], "preferred": wd}] if wd else [])}

DUMP = [ror_rec("01ej9dk98", "University of Melbourne", ["education", "funder"], "Q319078"),
        ror_rec("02bfwt286", "Monash University", ["education"], "Q598841"),
        ror_rec("0hosp0001", "St. Boniface Hospital", ["healthcare"], "Q7"),
        ror_rec("03dbr7087", "University of Toronto", ["education"], "Q180865"),
        ror_rec("0child0001", "Medical School of Big Uni", ["education"], status="inactive")]

def write_csv(path, rows, cols):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)

def quiet(fn, *a):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        fn(*a)
    return buf.getvalue()

d = tempfile.mkdtemp(); os.chdir(d)
write_csv("pool_candidates.csv", CANDS, COLS)

# ---- ROR enrichment from a local zip dump
with zipfile.ZipFile("ror.zip", "w") as z:
    z.writestr("v9-2026-01-01-ror-data/v9-2026-01-01-ror-data_schema_v2.json", json.dumps(DUMP))
    z.writestr("v9-2026-01-01-ror-data/v9-2026-01-01-ror-data.csv", "ignored")
out = quiet(er.main, ["--dump", "ror.zip"])
rows = {r["name"]: r for r in csv.DictReader(open("pool_enriched.csv", encoding="utf-8"))}
assert rows["The University of Melbourne"]["wikidata_final"] == "Q319078" and rows["The University of Melbourne"]["ror_note"] == ""
assert rows["Monash University"]["wikidata_final"] == "Q598841"
assert rows["St. Boniface Hospital"]["ror_note"] == "not typed education (healthcare)"
assert rows["Bond University"]["ror_note"] == "no ROR id in OpenAlex"
assert rows["University of Oxford"]["ror_note"] == "ROR id not in dump"
assert "status inactive" in rows["Medical School of Big Uni"]["ror_note"]
assert "Wikidata ids: 1 of 11 from OpenAlex, 4 after adding ROR." in out, out

# ---- registers in the four layouts
os.makedirs("registers")
open("registers/AU.csv", "w", encoding="utf-8").write(
    "CRICOS Provider Code,Institution Name,Trading Name,Institution Capacity,Website\n"
    "00116K,The University of Melbourne,,50000,www.unimelb.edu.au\n"
    "00008C,Monash University Pty,,60000,https://www.monash.edu/\n")
open("registers/GB.csv", "w", encoding="utf-8").write(
    "Organisation Name,Town/City,County,Type & Rating,Route\n"
    '"The Chancellor, Masters and Scholars of the University of Oxford",Oxford,Oxfordshire,Student (Premium),Student\n'
    "University of Bath,Bath,Somerset,Student (Premium),Student\n")
open("registers/CA.html", "w", encoding="utf-8").write(
    "<html><body><table><tr><th>Province</th><th>Institution</th><th>DLI number</th><th>City</th><th>Campus</th><th>PGWP</th><th>Co-op</th><th>Type</th></tr>"
    "<tr><td>Ontario</td><td>University of Toronto</td><td>O19359</td><td>Toronto</td><td>St. George</td><td>Yes</td><td>Yes</td><td>Public</td></tr>"
    "<tr><td>Quebec</td><td>Universite de Montreal</td><td>O19360</td><td>Montreal</td><td>Main</td><td>Yes</td><td>Yes</td><td>Public</td></tr>"
    "</table></body></html>")
open("registers/US.csv", "w", encoding="utf-8").write(
    "School Name,Campus Name,City,State,Visa\nUniv of Michigan-Ann Arbor,Main Campus,Ann Arbor,MI,F-1 M-1\nSt. Benedict School,Main,Bronx,NY,F-1\n")

out = quiet(el.main, ["--candidates", "pool_enriched.csv"])
res = {r["name"]: r for r in csv.DictReader(open("pool_eligibility.csv", encoding="utf-8"))}
def st(n): return res[n]["elig_status"], res[n]["elig_how"]
assert st("The University of Melbourne") == ("confirmed", "same website")
assert st("Monash University") == ("confirmed", "same website")      # name differs ("Pty") but website matches
assert st("Bond University")[0] == "not_found"
assert st("University of Toronto") == ("confirmed", "same name")
assert st("Université de Montréal") == ("confirmed", "same name")    # accents ignored
assert st("St. Boniface Hospital")[0] == "not_found"
assert st("University of Oxford") == ("likely", "register name contains it")
assert st("University of Bath") == ("confirmed", "same name")
assert st("University of Michigan–Ann Arbor") == ("confirmed", "same name")  # Univ -> University, dash ignored
assert st("Technical University of Munich")[0] == "not_checked"
summary = open("eligibility_summary.md", encoding="utf-8").read()
assert "| AU | 3 | 2 | 0 | 1 |" in summary, summary
assert "| GB | 2 | 1 | 1 | 0 |" in summary, summary
assert "Medical School of Big Uni" not in out.split("needs a look")[1] if "needs a look" in out else True  # children are not listed for review

# a register whose layout changed is flagged, not silently trusted
names, hosts, info = el.build(el.REGISTERS["US"], ["col a", "title", "city"], [{"col a": "x", "title": "Some University", "city": "y"}])
assert info["fallback"] and "some university" in names

# fetch(): finds the CSV link on a GOV.UK-style page and a 'Download' anchor on a SEVP-style page
page = '<a href="https://assets.publishing.service.gov.uk/media/abc/2026-11-06_-_Student.csv">Register of Student sponsors</a>'
assert el.find_download(page, "https://www.gov.uk/x", el.REGISTERS["GB"]).endswith("2026-11-06_-_Student.csv")
page = '<a class="btn" href="/sites/default/files/certified-schools.csv"><span>Download Certified School List</span></a>'
assert el.find_download(page, "https://studyinthestates.dhs.gov/school-search", el.REGISTERS["US"]) == "https://studyinthestates.dhs.gov/sites/default/files/certified-schools.csv"
print("ok: ROR enrichment, 4 register layouts, matching rules, link finding")
