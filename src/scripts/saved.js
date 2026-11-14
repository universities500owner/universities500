// Bookmarks for result cards. They are kept only in this browser (localStorage), never sent anywhere.
const KEY = 'u500-saved';
let ids = new Set();
try { ids = new Set(JSON.parse(localStorage.getItem(KEY) || '[]')); } catch (e) { /* storage blocked: bookmarks last until the page closes */ }
const persist = () => { try { localStorage.setItem(KEY, JSON.stringify([...ids])); } catch (e) { /* ignore */ } };

export const isSaved = (id) => ids.has(id);

/** Marks the saved cards in `list` and toggles on click. `onChange` runs after each toggle. */
export function wireSaves(list, onChange) {
  const paint = (li) => {
    const b = li.querySelector('[data-save]');
    if (b) b.setAttribute('aria-pressed', String(ids.has(li.dataset.id)));
  };
  [...list.children].forEach(paint);
  list.addEventListener('click', (e) => {
    const b = e.target.closest('[data-save]');
    if (!b) return;
    const li = b.closest('[data-id]');
    if (ids.has(li.dataset.id)) ids.delete(li.dataset.id); else ids.add(li.dataset.id);
    paint(li);
    persist();
    onChange();
  });
}
