"""Checks pool_pilot.py against a stub OpenAlex server (no internet needed). Run: python3 test_pool.py"""
import csv
import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))

def inst(i, name, works, cc="AU", lineage=None):
    return {"id": f"https://openalex.org/I{i}", "display_name": name, "country_code": cc, "type": "education",
            "works_count": works, "cited_by_count": works * 10, "summary_stats": {"h_index": works // 100},
            "ids": {"wikidata": f"https://www.wikidata.org/entity/Q{i}"}, "homepage_url": f"https://u{i}.example",
            "lineage": lineage or [f"https://openalex.org/I{i}"]}

DATA = {
    "AU": [inst(1, "Big Uni", 90000), inst(2, "Mid Uni", 12000), inst(3, "Medical School of Big Uni", 8000, lineage=["https://openalex.org/I3", "https://openalex.org/I1"]),
           inst(4, "Small Uni", 3000), inst(5, "Tiny College", 400)],
    "CA": [inst(6, "Maple Uni", 30000, "CA"), inst(7, "Lake Uni", 1500, "CA")],
}
CALLS = []
REJECT = {"on": False}

class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        CALLS.append(q)
        cc = q["filter"][0].split(",")[0].split(":")[1]
        rows = DATA[cc]
        cur = q["cursor"][0]
        start = 0 if cur == "*" else int(cur)
        page = rows[start:start + 2]  # tiny pages to force paging
        nxt = str(start + 2) if start + 2 < len(rows) else None
        if "select" in q and REJECT["on"]:
            self.send_response(400); self.end_headers(); return
        body = json.dumps({"meta": {"next_cursor": nxt}, "results": page}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)

def run(env_extra=None):
    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    d = tempfile.mkdtemp()
    env = dict(os.environ, **(env_extra or {}))
    r = subprocess.run([sys.executable, os.path.join(HERE, "pool_pilot.py"), "--countries", "AU,CA", "--pause", "0",
                        "--base-url", f"http://127.0.0.1:{srv.server_port}", "--mailto", "t@example.com"],
                       cwd=d, capture_output=True, text=True, env=env)
    srv.shutdown()
    assert r.returncode == 0, r.stderr
    return d

d = run()
rows = list(csv.DictReader(open(os.path.join(d, "pool_candidates.csv"), encoding="utf-8")))
names = [r["name"] for r in rows]
assert "Tiny College" not in names, "stops below the minimum"
assert names[:4] == ["Big Uni", "Mid Uni", "Medical School of Big Uni", "Small Uni"], names
assert [r["is_child"] for r in rows[:4]] == ["no", "no", "yes", "no"]
assert rows[0]["wikidata"] == "Q1" and rows[0]["works_count"] == "90000"
summ = open(os.path.join(d, "pool_summary.md"), encoding="utf-8").read()
assert "| Australia | 3 | 3 | 2 | 2 | 1 |" in summ, summ
assert "| Canada | 2 | 1 | 1 | 1 | 1 |" in summ, summ
assert all("mailto" in c for c in CALLS)
# a server that rejects the field list: the script must retry without it
CALLS.clear()
REJECT["on"] = True
d2 = run()
assert os.path.exists(os.path.join(d2, "pool_candidates.csv"))
assert any("select" not in c for c in CALLS)
print("ok: paging, minimum, child flag, thresholds, select fallback")
