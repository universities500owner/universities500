// Tick-box lists with a progress count. Nothing is saved: the ticks last while the page is open.
document.querySelectorAll('[data-checklist]').forEach((root) => {
  const boxes = [...root.querySelectorAll('input[type="checkbox"]')];
  const text = root.querySelector('[data-prog-text]');
  const bar = root.querySelector('[data-prog-bar]');
  const update = () => {
    const n = boxes.filter((b) => b.checked).length;
    if (text) text.textContent = `${n} of ${boxes.length} checked`;
    if (bar) bar.style.width = `${(n / boxes.length) * 100}%`;
  };
  boxes.forEach((b) => b.addEventListener('change', update));
  update();
});
