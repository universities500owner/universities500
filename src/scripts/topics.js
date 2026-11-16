// Collapsible topics: expand all, collapse all, and open the topic a link points at.
const all = () => [...document.querySelectorAll('#g-topics details.topic')];
document.getElementById('g-open')?.addEventListener('click', () => all().forEach((d) => { d.open = true; }));
document.getElementById('g-close')?.addEventListener('click', () => all().forEach((d) => { d.open = false; }));
function reveal() {
  const id = decodeURIComponent(location.hash.slice(1));
  if (!id) return;
  const el = document.getElementById(id);
  if (!el) return;
  const d = el.closest('details');
  if (d) { d.open = true; el.scrollIntoView(); }
}
window.addEventListener('hashchange', reveal);
reveal();
