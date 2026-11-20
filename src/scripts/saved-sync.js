// Keeps the bookmarks on the site's cards (kept in this browser) in step with the signed-in student's shortlist.
// Signed out: nothing is sent anywhere. Signed in: saves and removals are sent to /api/me/saved, and bookmarks made
// before signing in are added to the account once.
export const KEY = 'u500-saved';
export const META = 'u500-saved-meta';

export const signedIn = () => /(?:^|;\s*)u500_in=1/.test(document.cookie);

const read = (k, d) => { try { return JSON.parse(localStorage.getItem(k) || ''); } catch (e) { return d; } };
const write = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* storage blocked: last until the page closes */ } };
export const readIds = () => new Set(Array.isArray(read(KEY, [])) ? read(KEY, []).filter((x) => typeof x === 'string') : []);
export const writeIds = (ids) => write(KEY, [...ids]);
export const readMeta = () => { const m = read(META, {}); return m && typeof m === 'object' && !Array.isArray(m) ? m : {}; };
export const writeMeta = (m) => write(META, m);
export function forgetLocal(id) {
  const ids = readIds(); ids.delete(id); writeIds(ids);
  const m = readMeta(); delete m[id]; writeMeta(m);
}
export const clearLocal = () => { try { localStorage.removeItem(KEY); localStorage.removeItem(META); } catch (e) { /* ignore */ } };

// Title, a short line under it and a link, copied from a card on the page.
export function metaFromCard(li) {
  const t = li.querySelector('.crs-title, .rc-title');
  const a = (t && t.querySelector('a')) || li.querySelector('a.rc-go');
  const sub = li.querySelector('.crs-where, .rc-org');
  let u = '';
  if (a) { const h = a.getAttribute('href') || ''; u = h.startsWith('/') ? h : a.href; }
  return {
    t: (t ? t.textContent : '').replace(/\s+/g, ' ').trim().slice(0, 160),
    s: (sub ? sub.textContent : '').replace(/\s+/g, ' ').trim().slice(0, 160),
    u: u.slice(0, 300),
  };
}

// When a bookmark was made before this script kept titles, the address can still be worked out from the id.
function guessUrl(id) {
  const [k, rest] = [id.split(':')[0], id.slice(id.indexOf(':') + 1)];
  if (k === 'crs') return `/courses/${rest}/`;
  if (k === 'mba') return `/mba/${rest}/`;
  if (k === 'sch') return `/scholarships/${rest}/`;
  return '';
}
const asItem = (id, m) => ({ id, title: (m && m.t) || '', sub: (m && m.s) || '', url: (m && m.u) || guessUrl(id) });

export function api(method, body) {
  return fetch('/api/me/saved', { method, credentials: 'same-origin', headers: body ? { 'content-type': 'application/json' } : {}, body: body ? JSON.stringify(body) : undefined })
    .then((r) => r.json().catch(() => ({})).then((j) => ({ ok: r.ok && j.ok !== false, status: r.status, j })))
    .catch(() => ({ ok: false, status: 0, j: {} }));
}

export function saveToAccount(id, m) { return api('POST', { items: [asItem(id, m)] }); }
export function removeFromAccount(id) { return api('DELETE', { id }); }

// Adds the bookmarks held in this browser to the account, then makes this browser's list match the account.
// Returns the account's items, or null when not signed in or the account could not be reached.
let once = null;
export function syncWithAccount(extraMeta = {}) {
  if (!signedIn()) return Promise.resolve(null);
  if (once) return once;
  once = (async () => {
    const meta = { ...readMeta(), ...extraMeta };
    let r = await api('GET');
    if (!r.ok) return null;
    const have = new Set(r.j.items.map((i) => i.item_id));
    const missing = [...readIds()].filter((id) => !have.has(id));
    for (let i = 0; i < missing.length; i += 100) {
      const w = await api('POST', { items: missing.slice(i, i + 100).map((id) => asItem(id, meta[id])) });
      if (!w.ok) return null;
      r = w;
    }
    const items = r.j.items;
    writeIds(new Set(items.map((i) => i.item_id)));
    const keep = {};
    for (const i of items) if (meta[i.item_id]) keep[i.item_id] = meta[i.item_id];
    writeMeta(keep);
    return items;
  })();
  return once;
}
