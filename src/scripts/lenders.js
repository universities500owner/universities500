// Lender directory: search by name and filter by type. Without this script every lender is simply listed.
const root = document.getElementById('lenders');
if (root) {
  const q = root.querySelector('#lender-q');
  const cards = [...root.querySelectorAll('.lender')];
  const pills = [...root.querySelectorAll('[data-type]')].filter((b) => b.tagName === 'BUTTON');
  const empty = root.querySelector('#lender-empty');
  const tally = root.querySelector('#lender-tally');
  let active = 'all';
  const apply = () => {
    const text = (q.value || '').trim().toLowerCase();
    let shown = 0;
    cards.forEach((c) => {
      const ok = (active === 'all' || c.dataset.type === active) && c.textContent.toLowerCase().includes(text);
      c.hidden = !ok;
      if (ok) shown += 1;
    });
    empty.hidden = shown > 0;
    tally.textContent = `${shown} ${shown === 1 ? 'provider' : 'providers'}`;
  };
  pills.forEach((b) => b.addEventListener('click', () => {
    active = b.dataset.type;
    pills.forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    apply();
  }));
  q.addEventListener('input', apply);
}
