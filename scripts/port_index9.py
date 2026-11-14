#!/usr/bin/env python3
"""One-off: move the data out of the earlier single-file build (index-9.html) into the Astro site.

Usage: port_index9.py <index-9.html>

Writes
  src/data/guides.json       the 14 destination guides, with every ranking claim removed
  src/data/tools.json        reference data for the tool pages (courses, destinations, visa, work rights, scholarships)
  scripts/guides_scrub_report.txt   every change made to the guide text, so nothing is silently dropped

Guide wording is not rewritten. The only edits are deletions: ranking figures and ranking sentences.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------- read the source

src = open(sys.argv[1], encoding="utf8", errors="replace").read()
scripts = re.findall(r"<script([^>]*)>(.*?)</script>", src, re.S)
guides = None
app = None
for attrs, body in scripts:
    if 'id="guides-data"' in attrs:
        guides = json.loads(body)
    elif "var DEST=[" in body:
        app = body
assert guides and app, "guides-data or the main script was not found"

# ---------------------------------------------------------------- tool data (evaluated, not retyped)

head = app[: app.index("/* ---------- state ---------- */")]


def grab(name, closer):
    m = re.search(r"var %s=([\[{].*?\n[\]}]);" % name, app, re.S)
    assert m, name
    return "var %s=%s;" % (name, m.group(1))


js = head + "\n" + "\n".join(grab(n, c) for n, c in [("VITEM", "}"), ("VISA", "]"), ("WORKRIGHTS", "]"), ("SCH", "]")])
js += "\nprocess.stdout.write(JSON.stringify({FIELDS,GOALS,GRADES,YEARS,NATS,BUDGETS,DEST,REL,GREL,COURSES,VITEM,VISA,WORKRIGHTS,SCH}))"
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
    f.write(js)
out = subprocess.run(["node", f.name], capture_output=True, text=True, check=True).stdout
tools = json.loads(out)
os.unlink(f.name)

# The destination list carried a count of "top 500" universities per country. That is a ranking claim: drop it.
for d in tools["DEST"]:
    d.pop("n", None)

with open(os.path.join(ROOT, "src/data/tools.json"), "w", encoding="utf8") as f:
    json.dump(tools, f, ensure_ascii=False, indent=1)
print("tools.json:", {k: len(v) for k, v in tools.items()})

# ---------------------------------------------------------------- scrub ranking claims from the guides

RANKY = re.compile(
    r"(\bQS\b|Times Higher|(?-i:\bTHE (?:World|Impact))|U\.?S\.? News|\bUniRank\b|\bARWU\b|Shanghai Ranking|\bCWUR\b"
    r"|\brank(?:s|ed|ing|ings)?\b|\btop[- ]?\d+|\btop (?:ten|twenty|fifty|hundred)\b|\bglobal top\b|\bworld[’']s top\b"
    r"|league table|#\d+)",
    re.I,
)
# "National University of Singapore (NUS) – World Rank #10"  ->  "National University of Singapore (NUS)"
SUFFIX = re.compile(r"\s*[–—-]\s*(?:World|Global|QS|National)?\s*Rank(?:ed|ing)?\s*(?:#|No\.?\s*)?\d+(?:\s*[–-]\s*\d+)?\+?", re.I)
PAREN = re.compile(r"\s*\([^)]*(?:QS|Rankings?|ranked)[^)]*\)", re.I)
SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z“\"(0-9])")

report = []


def log(slug, kind, text):
    report.append("%s\t%s\t%s" % (slug, kind, re.sub(r"\s+", " ", text).strip()[:260]))


def runs_text(runs):
    return "".join(r["t"] for r in runs)


def trim_runs(runs, slug):
    """Apply the suffix and parenthesis rules inside each run."""
    out = []
    for r in runs:
        t = r["t"]
        t2 = PAREN.sub("", SUFFIX.sub("", t))
        if t2 != t:
            log(slug, "trimmed", t)
        r = dict(r)
        r["t"] = t2
        if t2:
            out.append(r)
    return out


def drop_sentences(runs, slug):
    """Remove whole sentences that still mention a ranking. Formatting of the rest is kept."""
    text = runs_text(runs)
    if not RANKY.search(text):
        return runs, False
    # character -> run index
    owner = []
    for i, r in enumerate(runs):
        owner += [i] * len(r["t"])
    spans = []
    pos = 0
    for m in SENT.finditer(text):
        spans.append((pos, m.start()))
        pos = m.end()
    spans.append((pos, len(text)))
    keep = [True] * len(text)
    changed = False
    for a, b in spans:
        if RANKY.search(text[a:b]):
            changed = True
            log(slug, "dropped sentence", text[a:b])
            for k in range(a, min(len(text), b + 1)):
                keep[k] = False  # include the space after
    if not changed:
        return runs, False
    out = []
    for i, r in enumerate(runs):
        chars = "".join(c for c, o, k in zip(text, owner, keep) if o == i and k)
        if chars:
            r = dict(r)
            r["t"] = chars
            out.append(r)
    if out:
        out[-1]["t"] = out[-1]["t"].rstrip()
    return out, True


def scrub_runs(runs, slug):
    runs = trim_runs(runs, slug)
    runs, _ = drop_sentences(runs, slug)
    return runs


def scrub_item(it, slug):
    """One list item. Items can carry a nested list under "sub"."""
    lead = it.get("lead") or []
    if RANKY.search(runs_text(trim_runs(lead, slug))):
        log(slug, "dropped item", runs_text(lead) + " " + runs_text(it["runs"]))
        return None
    body = it["runs"]
    had_body = bool(runs_text(body).strip())
    body = scrub_runs(body, slug)
    if had_body and not runs_text(body).strip():
        log(slug, "dropped item", runs_text(lead) + " " + runs_text(it["runs"]))
        return None
    new = {**it, "runs": body}
    if lead:
        new["lead"] = trim_runs(lead, slug)
    if "sub" in it:
        sub = [x for x in (scrub_item(s2, slug) for s2 in it["sub"]) if x]
        if sub:
            new["sub"] = sub
        else:
            new.pop("sub")
            if it["sub"]:
                log(slug, "dropped nested list", runs_text(body))
    if not runs_text(body).strip() and not lead and not new.get("sub"):
        return None
    return new


def scrub_block(b, slug):
    t = b["t"]
    if t == "p":
        runs = scrub_runs(b["runs"], slug)
        return {**b, "runs": runs} if runs_text(runs).strip() else None
    if t == "h":
        text = PAREN.sub("", SUFFIX.sub("", b["text"]))
        if text != b["text"]:
            log(slug, "trimmed heading", b["text"])
        if RANKY.search(text):
            log(slug, "dropped heading", text)
            return None
        return {**b, "text": text}
    if t == "ul":
        items = [x for x in (scrub_item(it, slug) for it in b["items"]) if x]
        return {**b, "items": items} if items else None
    if t == "qa":
        if RANKY.search(PAREN.sub("", SUFFIX.sub("", b["q"]))):
            log(slug, "dropped question", b["q"])
            return None
        ans = [x for x in (scrub_block(a, slug) for a in b["a"]) if x]
        if not ans:
            log(slug, "dropped question (no answer left)", b["q"])
            return None
        return {**b, "a": ans}
    raise ValueError(t)


clean = []
for g in guides:
    slug = g["slug"]
    stats = []
    for s in g.get("stats", []):
        if RANKY.search(s["v"] + " " + s["l"]):
            log(slug, "dropped stat", s["v"] + " | " + s["l"])
        else:
            stats.append(s)
    secs = []
    for s in g["sections"]:
        blocks = [x for x in (scrub_block(b, slug) for b in s["blocks"]) if x]
        # a heading with nothing under it is left over from a dropped list
        while blocks and blocks[-1]["t"] == "h":
            log(slug, "dropped orphan heading", blocks[-1]["text"])
            blocks.pop()
        if not blocks:
            log(slug, "dropped section (empty after scrub)", s["title"])
            continue
        title = PAREN.sub("", SUFFIX.sub("", s["title"]))
        if RANKY.search(title):
            log(slug, "section title still ranky", title)
        secs.append({**s, "title": title, "blocks": blocks})
    clean.append({**g, "stats": stats, "sections": secs})

# nothing ranky may remain anywhere
left = []
for g in clean:
    blob = json.dumps(g, ensure_ascii=False)
    for m in RANKY.finditer(blob):
        left.append((g["slug"], blob[max(0, m.start() - 60): m.end() + 60]))
if left:
    print("STILL RANKY:", len(left))
    for x in left[:20]:
        print("  ", x)
    sys.exit(1)

with open(os.path.join(ROOT, "src/data/guides.json"), "w", encoding="utf8") as f:
    json.dump(clean, f, ensure_ascii=False, indent=1)
with open(os.path.join(ROOT, "scripts/guides_scrub_report.txt"), "w", encoding="utf8") as f:
    f.write("slug\tchange\ttext (first 260 characters)\n" + "\n".join(report) + "\n")
print("guides.json:", len(clean), "guides;", len(report), "edits logged")
for g in clean:
    n = sum(len(s["blocks"]) for s in g["sections"])
    print("  ", g["slug"], len(g["sections"]), "sections", n, "blocks", len(g["stats"]), "stats")
