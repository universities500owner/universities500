#!/usr/bin/env python3
"""Build src/data/mba.json from the hand-read base (scripts/mba/pilot.json) and what the reader found (data/mba/read/<id>.json).

Rules:
  * The hand-read record is the base. A fact the program read AND verified (its numbers are in its own sentence) replaces the hand-read one,
    because it comes from a later look at the page. A fact the program did not find stays as read by hand.
  * Every fact records who read it and when, in `provenance`, so the programme page can say so and a person can tell hand from program.
  * Nothing is invented: a programme the reader never saw keeps its hand-read facts exactly.
  * `how` is 'hand', 'program' or 'both'. `readOn` is the latest date of any fact.

Usage: python3 scripts/mba/build_site_data.py [--pilot ...] [--read-dir ...] [--out src/data/mba.json]
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.resolve().parents[1]

FACTS = ('length', 'fee', 'exp', 'degree', 'test', 'english', 'start', 'deadlines', 'employment')


def load(p, default):
    try:
        return json.loads(Path(p).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def build_record(base, read):
    """One programme. base: hand-read record. read: reader output or {}."""
    rec = json.loads(json.dumps(base))
    hand_on = base.get('readOn') or ''
    prov = {}
    for k in FACTS:
        if rec.get(k):
            prov[k] = {'by': 'hand', 'on': hand_on}
            if k not in ('length', 'start') and not rec[k].get('u'):
                # the hand-read base leaves out the page address when the fact is on the programme's own page; every fact carries one
                rec[k]['u'] = (rec.get('feeUrl') if k == 'fee' else None) or rec['url']
    read_on = read.get('readOn') or ''
    for k, f in (read.get('facts') or {}).items():
        if k not in FACTS or not f or not f.get('u'):
            continue
        old = rec.get(k)
        new = dict(f)
        if k == 'fee' and old and old.get('note') and not new.get('note'):
            new['note'] = old['note']       # a note about how the fee is listed stays with it
        if k == 'fee':
            rec['feeUrl'] = f['u']
        rec[k] = {kk: vv for kk, vv in new.items() if vv is not None}
        prov[k] = {'by': 'program', 'on': read_on}
    rec['provenance'] = prov
    who = {v['by'] for v in prov.values()}
    rec['how'] = 'both' if who == {'hand', 'program'} else ('program' if who == {'program'} else 'hand')
    dates = [v['on'] for v in prov.values() if v.get('on')]
    rec['readOn'] = max(dates) if dates else hand_on
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pilot', default=str(HERE / 'pilot.json'))
    ap.add_argument('--read-dir', default=str(ROOT / 'data' / 'mba' / 'read'))
    ap.add_argument('--out', default=str(ROOT / 'src' / 'data' / 'mba.json'))
    args = ap.parse_args()
    pilot = load(args.pilot, {})
    items = []
    for base in pilot.get('items', []):
        read = load(Path(args.read_dir) / f"{base['id']}.json", {})
        items.append(build_record(base, read))
    doc = {'generatedAt': datetime.now(timezone.utc).date().isoformat(), 'items': items}
    Path(args.out).write_text(json.dumps(doc, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    both = sum(1 for r in items if r['how'] == 'both')
    print(f'{len(items)} programmes written to {args.out} ({both} with facts read by a program)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
