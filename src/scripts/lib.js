// Small helpers shared by the tool pages. Everything a visitor types stays in their own browser.
export const $ = (id) => document.getElementById(id);

export function fill(sel, arr, val) {
  sel.textContent = '';
  arr.forEach((o) => {
    const op = document.createElement('option');
    op.value = typeof o === 'string' ? o : o.v;
    op.textContent = typeof o === 'string' ? o : o.l;
    sel.appendChild(op);
  });
  if (val !== undefined && val !== null) sel.value = val;
}

export const pct = (a, b) => (b ? Math.round((100 * a) / b) : 0);

export function load(key, init) {
  try {
    const s = localStorage.getItem(key);
    if (s) return { ...init, ...JSON.parse(s) };
  } catch (e) {}
  return init;
}
export function save(key, v) {
  try {
    localStorage.setItem(key, JSON.stringify(v));
  } catch (e) {}
}

export const toolData = () => JSON.parse($('tool-data').textContent);

// Deadlines such as "15 January" in human terms.
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
function nextDeadline(sdl) {
  const m = /^(\d{1,2})\s+([A-Za-z]+)$/.exec(String(sdl).trim());
  if (!m) return null;
  const day = Number(m[1]);
  const mi = MONTHS.indexOf(m[2]);
  if (mi < 0 || !day) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  let dt = new Date(today.getFullYear(), mi, day);
  if (dt < today) dt = new Date(today.getFullYear() + 1, mi, day);
  return dt;
}
export function daysUntil(sdl) {
  const dt = nextDeadline(sdl);
  if (!dt) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((dt - today) / 86400000);
}
export function untilText(sdl) {
  const d = daysUntil(sdl);
  if (d === null) return '';
  if (d === 0) return 'today';
  if (d === 1) return 'tomorrow';
  if (d < 21) return 'in ' + d + ' days';
  if (d < 70) return 'in ' + Math.round(d / 7) + ' weeks';
  return 'in about ' + Math.round(d / 30) + ' months';
}

// A checklist whose items are already in the page as checkboxes. This saves ticks and fills the progress bar.
export function wireChecklist({ root, key, pctEl, barEl, sayEl, asPct = false, say }) {
  const store = load(key, {});
  const boxes = Array.from(root.querySelectorAll('input[type="checkbox"]'));
  function draw() {
    let done = 0;
    boxes.forEach((cb) => {
      cb.parentElement.classList.toggle('done', cb.checked);
      if (cb.checked) done++;
    });
    const p = pct(done, boxes.length);
    $(pctEl).textContent = asPct ? p + '%' : done + ' of ' + boxes.length;
    $(barEl).style.width = p + '%';
    $(sayEl).textContent = say(done, boxes.length, p);
  }
  boxes.forEach((cb) => {
    cb.checked = !!store[cb.dataset.k];
    cb.addEventListener('change', () => {
      store[cb.dataset.k] = cb.checked;
      save(key, store);
      draw();
    });
  });
  draw();
}
