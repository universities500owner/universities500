"""Official programmes and directories from data/scholarship_sources.json.
A programme is published only if its official page was fetched and contains the expected text."""
import extract as X
import textutil as T


def read_programmes(sources, fx, today):
    records, report = [], []
    for p in sources.get('programmes', []):
        got = None
        for url in p['urls']:
            res = fx.get(url)
            if not res.ok or 'html' not in (res.ctype or 'html').lower():
                report.append((p['id'], url, res.error or f'HTTP {res.status}'))
                continue
            page = X.Page(res.final_url, res.text, p['country'], p['provider'])
            hay = (page.title_tag + ' ' + page.h1 + ' ' + page.text[:4000]).lower()
            want = p.get('expect')
            want = [want] if isinstance(want, str) else (want or [])
            if want and not any(w.lower() in hay for w in want):
                report.append((p['id'], url, f"page does not mention '{want[0]}'"))
                continue
            got = (res.final_url, page)
            break
        if not got:
            continue
        url, page = got
        rec = X.make_record(
            name=p['name'], provider=p['provider'], provider_slug=p.get('providerSlug'), provider_type=p.get('providerType', 'government'), country=p['country'],
            url=url, text=page.text, today=today, origin='official', apply_url=X.find_apply_url(page),
            description=X.find_description(page), eligibility=X.find_eligibility(page), levels=p['levels'], intl='yes', lines=page.lines)
        rec['programmeId'] = p['id']
        records.append(rec)
        report.append((p['id'], url, 'ok'))
    return records, report


def read_directories(sources, fx, today):
    out = []
    for d in sources.get('directories', []):
        entry = {'id': d['id'], 'title': d['title'], 'countries': d['countries'], 'note': d.get('note'), 'url': None, 'ok': False, 'checked': None}
        for url in d['urls']:
            res = fx.get(url)
            if res.ok:
                entry.update(url=res.final_url, ok=True, checked=today)
                break
            entry['error'] = res.error
        if not entry['url']:
            entry['url'] = d['urls'][0]
        out.append(entry)
    return out


def read_third_party(sources, fx):
    """Link-outs only. We read robots.txt (and nothing else) so the run report shows what each site asks of crawlers."""
    import urllib.parse
    out = []
    for t in sources.get('thirdParty', []):
        p = urllib.parse.urlsplit(t['url'])
        try:
            allowed = fx.allowed(t['url'])
        except Exception:
            allowed = None
        out.append({**t, 'robotsAllowsRoot': allowed, 'robotsText': fx.robots_text.get(p.netloc, '')[:1500]})
    return out
