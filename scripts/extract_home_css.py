#!/usr/bin/env python3
"""One-off: pull the CSS that styles the earlier home view out of the old single-page build.

Usage: extract_home_css.py <old_index.html> <out.css>
Keeps every rule that matches an element inside #home (in light and in dark), the two token blocks and the
keyframes, and scopes the rules under .home-v1 so they cannot leak onto the other pages.
"""
import json
import re
import sys
from playwright.sync_api import sync_playwright

JS = r"""
() => {
  const home = document.getElementById('home');
  const els = [home, ...home.querySelectorAll('*')];
  const strip = (sel) => sel
    .replace(/::?(before|after|placeholder|selection|-webkit-[\w-]+|-moz-[\w-]+|hover|focus|focus-visible|focus-within|active|visited|checked|disabled|first-line|first-letter)/g, '')
    .replace(/\s+/g, ' ').trim();
  const out = [];
  const keep = (rule) => {
    const sels = rule.selectorText.split(/,(?![^()]*\))/).map(s => s.trim());
    const hit = sels.filter(s => {
      if (/^(:root|html|body)(\[data-theme="dark"\])?$/.test(s)) return false;
      const c = strip(s);
      if (!c) return false;
      try { return els.some(e => e.matches(c)); } catch (e) { return false; }
    });
    return hit;
  };
  const walk = (rules, wrap) => {
    for (const r of rules) {
      if (r.type === 1) {
        const hit = keep(r);
        if (hit.length) out.push({ wrap, sel: hit, body: r.cssText.slice(r.cssText.indexOf('{') + 1, r.cssText.lastIndexOf('}')).trim() });
      } else if (r.type === 4 || r.type === 12) {
        walk(r.cssRules, [...wrap, (r.type === 4 ? '@media ' : '@supports ') + r.conditionText]);
      } else if (r.type === 7) {
        out.push({ raw: r.cssText });
      }
    }
  };
  for (const sh of document.styleSheets) { try { walk(sh.cssRules, []); } catch (e) {} }
  const tokens = [];
  for (const sh of document.styleSheets) {
    try {
      for (const r of sh.cssRules) {
        if (r.type === 1 && /^(:root|html\[data-theme="dark"\])$/.test(r.selectorText.trim())) tokens.push(r.cssText);
      }
    } catch (e) {}
  }
  return { out, tokens };
}
"""


def main(src, dst):
    seen = {}
    tokens = None
    with sync_playwright() as p:
        b = p.chromium.launch()
        for theme in ("light", "dark"):
            pg = b.new_page(viewport={"width": 1280, "height": 900})
            pg.goto("file://" + src)
            pg.evaluate(f"document.documentElement.dataset.theme='{theme}'")
            res = pg.evaluate(JS)
            tokens = res["tokens"]
            for item in res["out"]:
                key = json.dumps(item, sort_keys=True)
                seen[key] = item
            pg.close()
        b.close()

    def scope(sel):
        dark = sel.startswith('html[data-theme="dark"] ')
        s = sel[len('html[data-theme="dark"] '):] if dark else sel
        s = s.replace("#home", ".home-v1")
        if ".home-v1" not in s:
            s = ".home-v1 " + s
        return ('html[data-theme="dark"] ' if dark else "") + s

    css = []
    for item in seen.values():
        if "raw" in item:
            css.append(item["raw"])
            continue
        sels = ",\n".join(scope(s) for s in item["sel"])
        rule = f"{sels}{{{item['body']}}}"
        for head in reversed(item["wrap"]):
            rule = f"{head}{{{rule}}}"
        css.append(rule)
    open(dst, "w", encoding="utf-8").write("/* Extracted from the earlier home view. Scoped under .home-v1. */\n" + "\n".join(css) + "\n")
    open(dst.replace(".css", ".tokens.css"), "w", encoding="utf-8").write("\n".join(tokens) + "\n")
    print(len(css), "rules,", len(tokens), "token blocks")


if __name__ == "__main__":
    main(*sys.argv[1:3])
