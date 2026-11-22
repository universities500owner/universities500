#!/usr/bin/env python3
"""A one-file review page for the pilot: one card per university with the facts, link checks, social accounts, campus thumbnails
(linked to Google Maps) and gallery photos with their credit lines, so a person can judge quality at a glance.

The photos are fetched as small thumbnails (330 px, a standard Wikimedia size) and embedded in the page, so the file opens anywhere with no
internet. Standard library only.

  python review.py --in out/profiles.json --out out/review.html"""
import argparse
import base64
import html
import json
import re
import threading
import time
import urllib.request

UA = 'Universities500Bot/1.0 (+https://universities500.com/bot/; profile pilot review page)'
E = html.escape


def small(url):
    """The 960 px thumbnail URL -> the 330 px one (both are standard Wikimedia sizes)."""
    return re.sub(r'/\d+px-', '/330px-', url or '', count=1)


_GATE = threading.Lock()


def fetch_thumb(url, delay=0.4):
    """A data: URI for one thumbnail, or '' when it cannot be fetched (the card then shows a grey box).
    Requests start at least `delay` seconds apart, even when several threads ask at once."""
    try:
        with _GATE:
            time.sleep(delay)
        req = urllib.request.Request(small(url), headers={'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read(400_000)
            ctype = r.headers.get('Content-Type', 'image/jpeg').split(';')[0]
        return f'data:{ctype};base64,{base64.b64encode(data).decode()}'
    except Exception:  # noqa: BLE001 - a missing thumbnail must not stop the page
        return ''


CSS = """
:root{--ink:#1b1f24;--mut:#5d6672;--line:#dfe3e8;--ok:#1f7a4d;--okbg:#e4f3ea;--rv:#8a5a00;--rvbg:#fff1d6;--no:#6b7280;--nobg:#eceff2;--bad:#a12626;--badbg:#fbe4e4}
*{box-sizing:border-box}body{margin:0;font:15px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:var(--ink);background:#f5f6f8}
header{padding:20px 16px 8px;max-width:1100px;margin:0 auto}h1{font-size:22px;margin:0 0 6px}
.lead{color:var(--mut);margin:0 0 10px;max-width:70ch}
.legend{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0 4px}
main{max-width:1100px;margin:0 auto;padding:8px 12px 40px;display:grid;gap:14px}
.card{background:#fff;border:1px solid var(--line);border-radius:10px;padding:14px}
.card h2{font-size:17px;margin:0}.sub{color:var(--mut);font-size:13px;margin-bottom:8px}
.row{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0;align-items:center}.lab{font-size:12px;color:var(--mut);min-width:74px}
.chip{display:inline-block;padding:2px 8px;border-radius:999px;font-size:12.5px;text-decoration:none;border:1px solid transparent}
.ok{background:var(--okbg);color:var(--ok)}.rv{background:var(--rvbg);color:var(--rv)}.no{background:var(--nobg);color:var(--no)}.bad{background:var(--badbg);color:var(--bad)}
a.chip:hover{border-color:currentColor}
.camps{display:flex;flex-wrap:wrap;gap:10px;margin:8px 0}.camp{width:150px;font-size:12.5px}
.camp img,.camp .ph{width:150px;height:96px;border-radius:6px;background:#e6e9ee;object-fit:cover;display:block}
.camp a{color:var(--ink);font-weight:600}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px;margin-top:6px}
.g img,.g .ph{width:100%;height:100px;object-fit:cover;border-radius:6px;background:#e6e9ee;display:block}
.cr{font-size:10.5px;color:var(--mut);line-height:1.25;margin-top:2px;word-break:break-word}.cr a{color:var(--mut)}
.src{font-size:10px;color:var(--mut);margin-left:6px}.names{font-size:13px;color:var(--mut)}.brief{margin:6px 0 8px;max-width:75ch}
"""


def chip(text, kind, href=''):
    t = f'<a class="chip {kind}" href="{E(href)}" target="_blank" rel="noopener">{E(text)}</a>' if href else f'<span class="chip {kind}">{E(text)}</span>'
    return t


def img(src, cls=''):
    return f'<img class="{cls}" alt="" src="{src}">' if src else f'<div class="ph {cls}"></div>'


def credit(p):
    who = E((p.get('author') or '')[:50])
    return (f'<div class="cr">{who}, <a href="{E(p.get("licenceUrl") or p.get("page") or "")}" target="_blank" rel="noopener">{E(p.get("licence") or "")}</a>'
            f'{", " + str(p["year"]) if p.get("year") else ""} · <a href="{E(p.get("page") or "")}" target="_blank" rel="noopener">Commons</a></div>')


def card(r, thumb):
    fo, st, w = r.get('founded') or {}, r.get('students') or {}, r.get('website') or {}
    out = [f'<section class="card"><h2>{E(r["name"])}</h2><div class="sub">{E(r["country"])}</div>']
    br = r.get('brief') or {}
    if br.get('status') == 'verified' and br.get('text'):
        out.append(f'<p class="brief">{E(br["text"])}</p>')
    elif str(br.get('status', '')).startswith('rejected'):
        out.append(f'<p class="names">Brief not used: {E(br["status"])}</p>')
    fk = {'confirmed': 'ok', 'official': 'ok', 'ok': 'rv', 'check': 'rv', 'conflict': 'rv'}.get(fo.get('status'), 'no')
    if fo.get('differs'):
        fk = 'rv'
    lead = f' (lead says {", ".join(map(str, fo["lead_years"]))})' if fo.get('lead_years') and fo.get('status') == 'check' else ''
    if (fo.get('status') == 'check' or fo.get('differs')) and fo.get('wikidata'):
        lead = f' (Wikidata says {fo["wikidata"]})'
    pf = fo.get('present_form')
    note = f'<span class="src">Present form {pf["v"]}</span>' if pf else ''
    srcline = f'<span class="src">{E(fo["source_text"])}</span>' if fo.get('source_text') else ''
    out.append(f'<div class="row"><span class="lab">Established</span>{chip(str(fo.get("v") or "missing") + lead, fk, fo.get("src", ""))}{note}{srcline}</div>')
    sk = {'verified': 'ok', 'official': 'ok', 'single-source': 'rv', 'site-only': 'rv', 'missing-year': 'rv', 'official-no-year': 'rv', 'check': 'rv'}.get(st.get('status'), 'no')
    sv = f'{st["v"]:,} as on {st["asof"] or "year unknown"}' if st.get('v') else 'missing'
    sec = st.get('second') or {}
    srcline = f'<span class="src">{E(st["source_text"])}</span>' if st.get('source_text') else ''
    shown = (r.get('publish') or {}).get('students')
    out.append(f'<div class="row"><span class="lab">Students</span>{chip(sv, sk, st.get("src", ""))}{srcline}'
               + (f'{chip("site says " + format(sec["v"], ","), "no")}' if sec else '') + f'{chip(st.get("status", "missing"), "no")}'
               + ('' if shown is None else f'{chip("shown" if shown else "hidden", "ok" if shown else "no")}') + '</div>')
    ws = 'ok' if w.get('status') == 200 else 'bad'
    out.append(f'<div class="row"><span class="lab">Own site</span>{chip("readable" if w.get("status") == 200 else (w.get("error") or "not readable"), ws, w.get("url") or "")}</div>')
    row = ['<div class="row"><span class="lab">Pages</span>']
    for role in ('admissions', 'courses', 'scholarships', 'partners', 'faculties', 'campuses', 'facts'):
        l = (r.get('links') or {}).get(role) or {}
        g = l.get('grade')
        row.append(chip(role, {'verified': 'ok', 'weak': 'rv', 'external': 'rv'}.get(g, 'no'), l.get('url') or '' if g in ('verified', 'weak', 'external') else ''))
    out.append(''.join(row) + '</div>')
    soc = ['<div class="row"><span class="lab">Social</span>']
    for kind in ('instagram', 'linkedin', 'youtube'):
        s = (r.get('social') or {}).get(kind)
        soc.append(chip(kind, 'ok' if s and s['status'] == 'verified' else ('rv' if s else 'no'), (s or {}).get('url', '')))
    out.append(''.join(soc) + '</div>')
    fac = r.get('faculties') or []
    out.append(f'<div class="row"><span class="lab">Faculties</span><span class="names">{len(fac)} found: ' + E('; '.join(f['name'] for f in fac[:6])) + ('…' if len(fac) > 6 else '') + '</span></div>')
    pn = (r.get('partners') or {}).get('names') or []
    if pn:
        out.append(f'<div class="row"><span class="lab">Partners</span><span class="names">{len(pn)} named: ' + E('; '.join(x['name'] for x in pn[:8])) + ('…' if len(pn) > 8 else '') + '</span></div>')
    camps = []
    for c in r.get('campuses') or []:
        ph = c.get('photo')
        camps.append(f'<div class="camp">{img(thumb(ph["thumb"]) if ph else "")}<a href="{E(c["maps"])}" target="_blank" rel="noopener">{E(c["name"])}</a>'
                     + (credit(ph) if ph else '<div class="cr">no photo found</div>') + '</div>')
    out.append('<div class="camps">' + ''.join(camps) + '</div>')
    ph = (r.get('gallery') or {}).get('photos') or []
    out.append('<div class="grid">' + ''.join(f'<div class="g">{img(thumb(p["thumb"]))}{credit(p)}</div>' for p in ph[:6]) + '</div>')
    if not ph:
        out.append('<div class="names">No gallery photos found.</div>')
    out.append('</section>')
    return ''.join(out)


def build(recs, thumb=fetch_thumb):
    legend = ''.join([chip('ready: sources agree or page verified', 'ok'), chip('review: found, check it', 'rv'), chip('missing', 'no'), chip('failed', 'bad')])
    body = ''.join(card(r, thumb) for r in recs)
    return (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Profile pilot review</title><style>{CSS}</style></head><body><header><h1>Profile pilot: {len(recs)} universities</h1>'
            f'<p class="lead">What the collector found for each university, with its evidence. Chips link to the source or the page it chose. '
            f'Campus names open Google Maps. Photos are Wikimedia Commons files; the small line under each is its credit.</p>'
            f'<div class="legend">{legend}</div></header><main>{body}</main></body></html>')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--in', dest='inp', default='out/profiles.json')
    ap.add_argument('--out', default='out/review.html')
    a = ap.parse_args()
    recs = json.load(open(a.inp, encoding='utf-8'))
    cache = {}

    def thumb(url):
        if url not in cache:
            cache[url] = fetch_thumb(url)
        return cache[url]
    open(a.out, 'w', encoding='utf-8').write(build(recs, thumb))
    got = sum(1 for v in cache.values() if v)
    print(f'review page: {len(recs)} universities, {got}/{len(cache)} thumbnails embedded')


if __name__ == '__main__':
    main()
