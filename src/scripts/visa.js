import { $, fill, load, save, pct, toolData } from './lib.js';

const { VISA, VITEM } = toolData();
const S = load('u500-visa', { dest: 'Australia', done: {} });
fill($('v-dest'), VISA.map((v) => v.c), S.dest);

function render() {
  const v = VISA.find((x) => x.c === $('v-dest').value) || VISA[0];
  S.dest = v.c;
  save('u500-visa', S);

  const req = $('v-req');
  req.textContent = '';
  const meta = document.createElement('div');
  meta.className = 'dmeta';
  [['Visa', v.v], ['Official source', v.src], ['Items to clear', String(v.need.length)]].forEach((r) => {
    const row = document.createElement('div');
    const k = document.createElement('span');
    k.textContent = r[0];
    const b = document.createElement('b');
    b.textContent = r[1];
    row.append(k, b);
    meta.appendChild(row);
  });
  req.appendChild(meta);
  const warn = document.createElement('p');
  warn.className = 'src';
  warn.textContent = 'Financial thresholds, processing times and document lists change often, so none are quoted here. Take them from ' + v.src + ' on the day you apply.';
  req.appendChild(warn);

  const store = (S.done[v.c] = S.done[v.c] || {});
  const box = $('v-items');
  box.textContent = '';
  let done = 0;
  v.need.forEach((k) => {
    const lab = document.createElement('label');
    lab.className = 'check';
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.checked = !!store[k];
    if (cb.checked) {
      done++;
      lab.classList.add('done');
    }
    const sp = document.createElement('span');
    sp.textContent = VITEM[k];
    cb.addEventListener('change', () => {
      store[k] = cb.checked;
      save('u500-visa', S);
      render();
    });
    lab.append(cb, sp);
    box.appendChild(lab);
  });
  const p = pct(done, v.need.length);
  $('v-pct').textContent = p + '%';
  $('v-bar').style.width = p + '%';
  $('v-say').textContent =
    p === 100 ? 'Every item cleared. Check the current thresholds before you file.' : p >= 60 ? 'Close. ' + (v.need.length - done) + ' to go for ' + v.c + '.' : p > 0 ? 'Early stage. Clear the offer and funds first, they gate the rest.' : 'Nothing cleared yet for ' + v.c + '.';
}
$('v-dest').addEventListener('change', render);
render();
