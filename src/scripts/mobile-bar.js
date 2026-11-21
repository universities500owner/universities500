// The phone bar (src/components/MobileBar.astro): hide the sign-up bar for a week, open the "More" sheet, sign out from any page,
// and keep the bar off the keyboard while a student types. Which version shows is decided in CSS from flags on <html>.
import { clearLocal } from './saved-sync.js';

const root = document.documentElement;
const KEY = 'u500_bar_off';   // when the student hid the bar, the time it comes back (the head script of every page reads it)
const WEEK = 7 * 24 * 60 * 60 * 1000;

document.querySelectorAll('[data-mb-hide]').forEach((b) => b.addEventListener('click', () => {
  try { localStorage.setItem(KEY, String(Date.now() + WEEK)); } catch (e) { /* storage blocked: hidden until the page closes */ }
  root.dataset.barOff = '1';
}));

// ---- the "More" sheet ----
const more = document.querySelector('[data-mb-more]');
const sheet = document.querySelector('[data-mb-sheet]');
if (more && sheet) {
  const setOpen = (open, back) => {
    sheet.hidden = !open;
    more.setAttribute('aria-expanded', String(open));
    if (open) (sheet.querySelector('a, button') || more).focus();
    else if (back) more.focus();
  };
  more.addEventListener('click', () => setOpen(sheet.hidden));
  sheet.addEventListener('click', (e) => { if (e.target === sheet) setOpen(false, true); });   // a tap outside the card
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !sheet.hidden) setOpen(false, true); });
  window.addEventListener('pageshow', () => setOpen(false));                                     // Back button: never come back to an open sheet
}

// ---- sign out (the same steps as the dashboard's own button) ----
document.querySelectorAll('[data-mb-signout]').forEach((b) => b.addEventListener('click', async () => {
  b.disabled = true;
  try { await fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin', headers: { 'content-type': 'application/json' }, body: '{}' }); } catch (e) { /* the cookie flag is cleared by the reply; if the call failed the next page asks again */ }
  clearLocal(); // bookmarks kept in this browser are cleared too, so the next person on this device does not see them
  location.assign('/sign-in/');
}));

// ---- out of the way of the keyboard ----
const FIELD = 'input:not([type=checkbox]):not([type=radio]):not([type=button]):not([type=submit]):not([type=range]):not([type=file]), textarea, select';
document.addEventListener('focusin', (e) => { if (e.target.matches && e.target.matches(FIELD)) root.dataset.typing = '1'; });
document.addEventListener('focusout', (e) => { if (e.target.matches && e.target.matches(FIELD)) delete root.dataset.typing; });

// ---- keep the page's bottom padding equal to the bar's real height (it grows if a line wraps or the student uses large text) ----
const bars = [...document.querySelectorAll('.mb')];
const out = document.querySelector('.mb-out');
const size = () => {
  if (out && out.offsetHeight > 0) { out.classList.remove('mb-tight'); if (out.offsetHeight > 96) out.classList.add('mb-tight'); }   // too tall (large text): drop the sign-in line
  const shown = bars.find((el) => el.offsetHeight > 0);
  if (shown) document.body.style.setProperty('--mb-h', shown.offsetHeight + 'px');
  else if (!root.dataset.typing) document.body.style.removeProperty('--mb-h');   // hidden for good: the stylesheet's own value applies
};
if (window.ResizeObserver) { const ro = new ResizeObserver(size); bars.forEach((el) => ro.observe(el)); }
window.addEventListener('resize', size);
size();
