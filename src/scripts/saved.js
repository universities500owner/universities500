// Bookmarks for result cards. Signed out, they are kept only in this browser (localStorage) and never sent anywhere.
// Signed in, they are also saved to the student's shortlist (see saved-sync.js).
import { readIds, writeIds, readMeta, writeMeta, metaFromCard, signedIn, saveToAccount, removeFromAccount, syncWithAccount } from './saved-sync.js';

let ids = readIds();
const persist = () => writeIds(ids);

export const isSaved = (id) => ids.has(id);

/** Marks the saved cards in `list` and toggles on click. `onChange` runs after each toggle. */
export function wireSaves(list, onChange) {
  const paint = (li) => {
    const b = li.querySelector('[data-save]');
    if (b) b.setAttribute('aria-pressed', String(ids.has(li.dataset.id)));
  };
  [...list.children].forEach(paint);

  // Signed in: add this browser's earlier bookmarks to the account and show what the account already holds.
  if (signedIn()) {
    const seen = {};
    for (const li of list.children) if (li.dataset && li.dataset.id && ids.has(li.dataset.id)) seen[li.dataset.id] = metaFromCard(li);
    syncWithAccount(seen).then((items) => {
      if (!items) return;
      ids = readIds();
      [...list.children].forEach(paint);
      onChange();
    });
  }

  list.addEventListener('click', (e) => {
    const b = e.target.closest('[data-save]');
    if (!b) return;
    const li = b.closest('[data-id]');
    const id = li.dataset.id;
    const meta = readMeta();
    if (ids.has(id)) {
      ids.delete(id);
      delete meta[id];
      if (signedIn()) removeFromAccount(id);
    } else {
      ids.add(id);
      meta[id] = metaFromCard(li);
      if (signedIn()) saveToAccount(id, meta[id]);
    }
    writeMeta(meta);
    paint(li);
    persist();
    onChange();
  });
}
