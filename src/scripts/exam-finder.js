// The exam finder on /exams/. The answers are written at build time and sit in a data attribute.
const root = document.getElementById('x-find');
if (root) {
  const data = JSON.parse(root.dataset.finder || '{}');
  const level = document.getElementById('x-level');
  const need = document.getElementById('x-need');
  const out = document.getElementById('x-result');
  const show = () => {
    const r = data[`${level.value}|${need.value}`];
    if (!r) return;
    out.textContent = '';
    const p = document.createElement('p');
    const b = document.createElement('strong');
    b.textContent = 'Where to start: ';
    p.append(b, r.text);
    const links = document.createElement('p');
    links.append('Read the guide: ');
    r.links.forEach((l, i) => {
      if (i) links.append(', ');
      const a = document.createElement('a');
      a.href = l.href;
      a.textContent = l.name;
      links.append(a);
    });
    out.append(p, links);
  };
  level.addEventListener('change', show);
  need.addEventListener('change', show);
}
