import { $, fill, load, save, toolData } from './lib.js';

const { SCH } = toolData();
const S = load('u500-sch', { list: [] });
const uniq = (key) => [...new Set(SCH.map((x) => x[key]))].sort();
fill($('sc-c'), ['All countries', ...uniq('c')]);
fill($('sc-l'), ['All levels', ...uniq('l')]);

function render() {
  const q = $('sc-q').value.trim().toLowerCase();
  const c = $('sc-c').value;
  const l = $('sc-l').value;
  const rows = SCH.filter((x) => (c === 'All countries' || x.c === c) && (l === 'All levels' || x.l === l) && (!q || x.n.toLowerCase().includes(q)));
  $('sc-tally').textContent = rows.length + (rows.length === 1 ? ' scholarship' : ' scholarships');
  const box = $('sc-list');
  box.textContent = '';
  if (!rows.length) {
    const e = document.createElement('p');
    e.className = 'empty';
    e.textContent = 'Nothing matches those filters.';
    box.appendChild(e);
  }
  rows.forEach((x) => {
    const card = document.createElement('div');
    card.className = 'sch';
    const left = document.createElement('div');
    const h = document.createElement('h4');
    h.textContent = x.n;
    const m = document.createElement('div');
    m.className = 'meta';
    m.textContent = x.c + ', ' + x.l + ', ' + x.f + '. Worth ' + x.a + '. Closes ' + x.d + '.';
    left.append(h, m);
    const on = S.list.includes(x.n);
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'pill';
    btn.textContent = on ? 'Shortlisted' : 'Shortlist';
    btn.setAttribute('aria-pressed', String(on));
    btn.addEventListener('click', () => {
      const i = S.list.indexOf(x.n);
      if (i < 0) S.list.push(x.n);
      else S.list.splice(i, 1);
      save('u500-sch', S);
      render();
    });
    card.append(left, btn);
    box.appendChild(card);
  });
  $('sc-short').textContent = S.list.length ? 'Shortlisted ' + S.list.length + ': ' + S.list.join('; ') : 'Nothing shortlisted yet. Pick the ones whose deadline you can actually make.';
}
$('sc-q').addEventListener('input', render);
$('sc-c').addEventListener('change', render);
$('sc-l').addEventListener('change', render);
render();
