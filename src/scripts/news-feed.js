// The industry-news feed: pick destinations, show official only, show more. The full list is already in the page,
// so with scripts off everything is shown. The choice is kept in the address (#uk,canada) so it can be shared.
const PAGE = 30;
const feed = document.getElementById('feed');
const bar = document.getElementById('feed-filters');
if (feed && bar) {
  const rows = [...feed.children];
  const chips = [...bar.querySelectorAll('[data-c]')];
  const allBtn = bar.querySelector('[data-all]');
  const kindBtns = [...bar.querySelectorAll('[data-k]')];
  const count = document.getElementById('feed-count');
  const empty = document.getElementById('feed-empty');
  const more = document.getElementById('feed-more');
  const state = { cs: new Set(), official: false, shown: PAGE };

  const fromHash = () => {
    const h = decodeURIComponent(location.hash.replace(/^#/, ''));
    if (h === 'where') { const d = document.getElementById('where'); if (d) d.open = true; return; }
    h.split(',').map((s) => s.trim()).filter((s) => chips.some((c) => c.dataset.c === s)).forEach((s) => state.cs.add(s));
    if (/official/.test(h)) state.official = true;
  };
  const toHash = () => {
    const parts = [...state.cs, ...(state.official ? ['official'] : [])];
    try { history.replaceState(null, '', parts.length ? '#' + parts.join(',') : location.pathname); } catch (e) { /* ignore */ }
  };

  const paint = () => {
    const match = rows.filter((r) => (!state.official || r.dataset.k === 'official') && (state.cs.size === 0 || r.dataset.c.split(' ').some((c) => state.cs.has(c))));
    const keep = new Set(match.slice(0, state.shown));
    rows.forEach((r) => { r.hidden = !keep.has(r); });
    chips.forEach((b) => b.setAttribute('aria-pressed', String(state.cs.has(b.dataset.c))));
    allBtn.setAttribute('aria-pressed', String(state.cs.size === 0));
    kindBtns.forEach((b) => b.setAttribute('aria-pressed', String((b.dataset.k === 'official') === state.official)));
    const names = chips.filter((b) => state.cs.has(b.dataset.c)).map((b) => b.dataset.name);
    count.textContent = match.length === 0 ? '' : keep.size < match.length ? `Showing ${keep.size} of ${match.length} updates` : `${match.length} ${match.length === 1 ? 'update' : 'updates'}`;
    empty.hidden = match.length > 0;
    if (match.length === 0) {
      const who = names.length ? names.join(', ') : 'these filters';
      empty.innerHTML = '';
      empty.append(`No ${state.official ? 'official ' : ''}update in English found for ${who} in the last 12 months. `);
      const a = document.createElement('a'); a.href = '#where'; a.textContent = 'See the official pages we look at';
      a.addEventListener('click', () => { const d = document.getElementById('where'); if (d) d.open = true; });
      empty.append(a, '.');
    }
    more.hidden = keep.size >= match.length;
    more.textContent = `Show ${Math.min(PAGE, match.length - keep.size)} more`;
  };
  const change = () => { state.shown = PAGE; toHash(); paint(); };

  chips.forEach((b) => b.addEventListener('click', () => { const c = b.dataset.c; if (state.cs.has(c)) state.cs.delete(c); else state.cs.add(c); change(); }));
  allBtn.addEventListener('click', () => { state.cs.clear(); change(); });
  kindBtns.forEach((b) => b.addEventListener('click', () => { state.official = b.dataset.k === 'official'; change(); }));
  more.addEventListener('click', () => { state.shown += PAGE; paint(); });

  fromHash();
  bar.hidden = false;
  paint();
}
