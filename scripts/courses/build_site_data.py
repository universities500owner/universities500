#!/usr/bin/env python3
"""Turn data/courses/<university>.json (everything the reader saw) into src/data/courses.json (what the website needs).

The site file keeps one entry per eligible course with the facts and the sentence each fact was copied from, and leaves out
the reader's working notes (pages seen, held-back counts, hashes). The same checks the reader uses on every run are applied
again here, so a record saved before a rule existed never reaches the site.

    python3 scripts/courses/build_site_data.py [--in data/courses] [--out src/data/courses.json]

Nothing is invented: every value is copied from the reader's record. The page slug is built from the programme name and
the short code already in the record's id, so it does not change when the course's facts change.
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'scholarships'))
sys.path.insert(0, str(HERE))   # this folder first: scholarships has a run.py too
import checks as Q  # noqa: E402
import run as R  # noqa: E402
import textutil as T  # noqa: E402

KEEP = ('name', 'degree', 'level', 'field', 'url', 'duration', 'fee', 'ielts', 'intakes', 'cricos', 'flags', 'firstSeen', 'lastVerified', 'lastChanged')


def page_slug(rec):
    """`<programme-name>-<six letters and digits>`: the six come from the id the reader gave the course (a hash of its address)."""
    code = rec['id'].rsplit(':', 1)[-1] if rec.get('id') else ''
    return f"{T.slugify(rec['name'], 60) or 'course'}-{code}" if code else (T.slugify(rec['name'], 60) or 'course')


def site_record(rec, uni_slug):
    out = {'slug': page_slug(rec), 'uni': uni_slug}
    for k in KEEP:
        out[k] = rec.get(k)
    out['studyMode'] = (rec.get('studyMode') or {}).get('evidence') or ''
    intl = rec.get('international') or {}
    out['intl'] = {'how': intl.get('how'), 'evidence': intl.get('evidence') or ''}
    return out


def build(src_dir):
    """Return (document, stats). `src_dir` holds one file per university."""
    items, unis, stats = [], {}, {'files': 0, 'read': 0, 'kept': 0, 'checks': {}, 'duplicates': 0, 'slug-clash': 0}
    for f in sorted(Path(src_dir).glob('*.json')):
        try:
            doc = json.loads(f.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            stats['checks']['unreadable-file'] = stats['checks'].get('unreadable-file', 0) + 1
            continue
        stats['files'] += 1
        slug = doc.get('slug') or f.stem
        good = {}
        for rec in doc.get('courses') or []:
            stats['read'] += 1
            why = Q.problem(rec)
            if why:
                stats['checks'][why] = stats['checks'].get(why, 0) + 1
                continue
            good[rec['url']] = rec
        for url in R.duplicates(good):
            good.pop(url, None)
            stats['duplicates'] += 1
        used = set()
        for rec in sorted(good.values(), key=lambda c: (c['level'], c['name'].lower(), c['url'])):
            item = site_record(rec, slug)
            if item['slug'] in used:         # two records cannot share a page address
                stats['slug-clash'] += 1
                continue
            used.add(item['slug'])
            items.append(item)
        if used:
            unis[slug] = {'n': len(used), 'read': (doc.get('generatedAt') or '')[:10] or None, 'status': doc.get('status')}
    stats['kept'] = len(items)
    items.sort(key=lambda i: (i['uni'], i['level'], i['name'].lower(), i['url']))
    dates = [i['lastVerified'] for i in items if i.get('lastVerified')]
    return {'generatedAt': max(dates) if dates else None, 'total': len(items), 'universities': dict(sorted(unis.items())), 'items': items}, stats


def dump(doc):
    """One course per line, so a git diff shows what changed."""
    head = {k: v for k, v in doc.items() if k != 'items'}
    parts = ['{']
    for k, v in head.items():
        parts.append(f'"{k}": {json.dumps(v, ensure_ascii=False)},')
    parts.append('"items": [')
    parts.append(',\n'.join(json.dumps(i, ensure_ascii=False) for i in doc['items']))
    parts.append(']')
    parts.append('}')
    return '\n'.join(parts) + '\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--in', dest='src', default='data/courses')
    ap.add_argument('--out', default='src/data/courses.json')
    a = ap.parse_args()
    doc, stats = build(a.src)
    Path(a.out).write_text(dump(doc), encoding='utf-8')
    print(f"{stats['files']} university files, {stats['read']} courses read, {stats['kept']} written to {a.out}")
    for k, v in sorted(stats['checks'].items(), key=lambda kv: -kv[1]):
        print(f'  dropped by check {k}: {v}')
    if stats['duplicates']:
        print(f"  dropped as repeats of another address: {stats['duplicates']}")
    if stats['slug-clash']:
        print(f"  dropped for sharing a page address: {stats['slug-clash']}")


if __name__ == '__main__':
    main()
