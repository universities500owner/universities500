import { $, fill, load, save, toolData } from './lib.js';

const { COURSES } = toolData();
const IDS = ['b-course', 'b-sch', 'b-funds', 'b-visa', 'b-flight', 'b-dep', 'b-ship'];
const S = load('u500-budget', {});
fill($('b-course'), COURSES.map((c, i) => ({ l: c.n + ', ' + c.c, v: i })), S['b-course'] ?? 0);
const num = (id) => Number($(id).value) || 0;

function render() {
  const c = COURSES[num('b-course')] || COURSES[0];
  const tuition = c.fee * c.yr;
  const living = c.live * 12 * c.yr;
  const once = num('b-visa') + num('b-flight') + num('b-dep') + num('b-ship');
  const sch = num('b-sch') * c.yr;
  const funds = num('b-funds');
  const gap = tuition + living + once - sch - funds;
  const box = $('b-out');
  box.textContent = '';
  [['Tuition, whole course', tuition], ['Living, whole course', living], ['One-time costs', once], ['Scholarship', -sch], ['Your own funds', -funds]].forEach((r) => {
    const row = document.createElement('div');
    row.className = 'line';
    const k = document.createElement('span');
    k.textContent = r[0];
    const b = document.createElement('b');
    b.textContent = (r[1] < 0 ? '−' : '') + Math.abs(r[1]).toLocaleString();
    row.append(k, b);
    box.appendChild(row);
  });
  const big = document.createElement('div');
  big.className = 'line big';
  const bk = document.createElement('span');
  bk.textContent = gap > 0 ? 'Still to cover' : 'Surplus';
  const bv = document.createElement('b');
  bv.textContent = Math.abs(gap).toLocaleString();
  big.append(bk, bv);
  box.appendChild(big);
  const note = document.createElement('p');
  note.className = 'src';
  note.textContent = gap > 0 ? 'A gap this size is what an education loan or a bigger scholarship has to close.' : 'Comfortable on these numbers. Visa evidence usually only asks for the first year.';
  box.appendChild(note);
}

IDS.forEach((id) => {
  if (S[id] !== undefined && S[id] !== '') $(id).value = S[id];
  ['input', 'change'].forEach((ev) =>
    $(id).addEventListener(ev, () => {
      S[id] = $(id).value;
      save('u500-budget', S);
      render();
    }),
  );
});
render();
