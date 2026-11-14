import { $ } from './lib.js';

let index = null;
const norm = (s) => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');

async function run(q) {
  const box = $('ss-res');
  box.textContent = '';
  const words = norm(q).split(/[^a-z0-9]+/).filter((w) => w.length > 1);
  if (!words.length) {
    $('ss-tally').textContent = '';
    return;
  }
  if (!index) index = (await (await fetch('/search-index.json')).json()).map((e) => ({ ...e, _t: norm(e.t), _d: norm(e.d || ''), _k: norm(e.k || '') }));
  const scored = index
    .map((e) => {
      let hit = 0;
      let s = 0;
      for (const w of words) {
        const a = e._t.includes(w) ? 5 : 0;
        const b = e._d.includes(w) ? 2 : 0;
        const c = e._k.includes(w) ? 1 : 0;
        if (a + b + c) hit++;
        s += a + b + c;
      }
      return { e, hit, s };
    })
    .filter((x) => x.hit === words.length)
    .sort((x, y) => y.s - x.s)
    .slice(0, 30);
  $('ss-tally').textContent = scored.length ? scored.length + (scored.length === 1 ? ' result' : ' results') : 'Nothing found. Try a country, a topic or fewer words.';
  scored.forEach(({ e }) => {
    const li = document.createElement('li');
    const a = document.createElement('a');
    a.href = e.u;
    a.textContent = e.t;
    li.appendChild(a);
    if (e.d) {
      const sm = document.createElement('small');
      sm.textContent = e.d;
      li.appendChild(sm);
    }
    box.appendChild(li);
  });
}

const q0 = new URLSearchParams(location.search).get('q') || '';
$('ss-q').value = q0;
if (q0) run(q0);
$('ss-form').addEventListener('submit', (ev) => {
  ev.preventDefault();
  const q = $('ss-q').value.trim();
  try { history.replaceState(null, '', q ? '/search/?q=' + encodeURIComponent(q) : '/search/'); } catch (e) {}
  run(q);
});
