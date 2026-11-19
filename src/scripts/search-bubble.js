// The floating search panel: type a question, see the best few results of each kind, open the full Search page for more.
// Uses the same engine as the Search page (search-core.js). Everything runs on this device: nothing typed is sent anywhere or saved.
import { load, plan, sample, h, num, plural } from './search-core.js';

const SHOW = 3;                       // rows per kind of result
const WAIT = 160;                     // ms to wait after the last key before searching
const levelName = (lv) => (lv === 'm' ? "Master's" : "Bachelor's");
const full = (q) => `/search/?q=${encodeURIComponent(q)}`;

let refresh = () => {};
// Called each time the panel opens: the page's sections can differ from one page to the next, so the list is rebuilt.
export function opened() { refresh(); }

export function start(dlg) {
  const $ = (id) => dlg.querySelector(`#${id}`);
  const input = $('fs-q'), form = $('fs-form'), tries = $('fs-try'), says = $('fs-says'), tally = $('fs-tally'), out = $('fs-out'), foot = $('fs-foot'), body = $('fs-body');
  const idle = $('fs-idle'), priv = $('fs-priv'), here = $('fs-here'), hereList = $('fs-here-list');
  let seq = 0;          // the latest search wins
  let timer = 0;
  let data = null;      // the loaded search data, once it has arrived

  const link = (href, text, newTab) => h('a', newTab ? { href, target: '_blank', rel: 'noopener' } : { href }, text);
  const row = (a, ...small) => h('li', null, a, h('small', null, small.filter(Boolean).join(' · ')));
  const group = (id, title, count, rows) => h('section', { class: 'fs-sec', 'aria-labelledby': `fs-h-${id}` },
    h('h3', { id: `fs-h-${id}`, class: 'fs-h' }, title, ' ', h('span', { class: 'muted' }, num(count))),
    h('ul', { class: 'fs-res' }, rows));

  function sections(P, d) {
    const u = P.u;
    const s = {};
    if (P.courses && P.courses.list.length) {
      const list = P.courses.list;
      s.courses = group('courses', 'Courses', list.length, sample(list, SHOW).map((c) => row(link(`/courses/${c.uni}/${c.slug}/`, c.name), c.uniName, d.cname(c.country), levelName(c.lv), c.ln, c.fe)));
    }
    if (P.scholarships) s.scholarships = group('sch', 'Scholarships', P.scholarships.list.length, P.scholarships.list.slice(0, SHOW).map((x) => row(link(`/scholarships/${x.slug}/`, x.name), x.provider, d.cname(x.country), x.value)));
    if (P.internships) s.internships = group('int', 'Internships', P.internships.length, P.internships.slice(0, SHOW).map((i) => row(link(i.url, i.title, true), i.org, i.city, d.cname(i.country), 'opens in a new tab')));
    if (P.universities) s.universities = group('uni', 'Universities', P.universities.length, P.universities.slice(0, SHOW).map((e) => row(link(e.u, e.t), e.d)));
    const mba = P.mba ? h('li', null, link(`/mba/${u.countries.length === 1 ? `?c=${u.countries[0]}` : ''}`, 'MBA Explorer'), h('small', null, 'Compare MBA programmes by work experience, fees and English score')) : null;
    if (P.pages.length || mba) {
      const rows = P.pages.slice(0, mba ? SHOW - 1 : SHOW).map((e) => {
        const away = /^https?:\/\//.test(e.u) && new URL(e.u).origin !== location.origin;
        return h('li', null, link(e.u, e.t, away), e.d ? h('small', null, e.d) : null);
      });
      s.pages = group('pg', 'Guides and tools', P.pages.length + (mba ? 1 : 0), [mba, ...rows]);
    }
    return s;
  }

  function showNothing(text, P) {
    const none = P && P.courses && !P.courses.list.length;
    out.replaceChildren(h('p', { class: 'small' }, none
      ? 'The Search page shows what was understood and lets you drop a part of it. Or try a subject, a level and a country, for example:'
      : 'Try a subject, a level and a country, for example:'));
    tries.hidden = false; idle.hidden = true; priv.hidden = true;
    foot.replaceChildren(...[
      none ? h('a', { class: 'btn', href: full(text) }, 'Open the Search page') : null,
      h('a', { class: none ? 'fs-msg' : 'btn ghost', href: '/contact/' }, 'Send us a message'),
    ].filter(Boolean));
    foot.hidden = false;
    tally.textContent = none ? 'No course matches all of that.' : `Nothing found for “${text}”.`;
  }

  function render(text) {
    const t = text.trim();
    const d = data;
    tries.hidden = Boolean(t); idle.hidden = Boolean(t); priv.hidden = Boolean(t);
    if (!t) { says.replaceChildren(); out.replaceChildren(); foot.replaceChildren(); foot.hidden = true; tally.textContent = ''; return; }
    const P = plan(t, d);
    const u = P.u;
    // what the search understood, so the results make sense
    const notes = [];
    if (u.fixes.length) notes.push(h('p', { class: 'fs-fix' }, 'Showing results for ', h('strong', null, u.fixes.map(([, to]) => to).join(', ')), '.'));
    if (u.chips.length) notes.push(h('p', { class: 'fs-under' }, 'Understood as: ', u.chips.map((c) => c.label).join(' · ')));
    if (u.flags.ranking) notes.push(h('p', { class: 'small' }, 'We do not rank universities or courses. Results are listed A to Z.'));
    says.replaceChildren(...notes);

    const s = sections(P, d);
    const shown = P.order.filter((k) => s[k]);
    if (!shown.length) { showNothing(t, P); return; }
    out.replaceChildren(...shown.map((k) => s[k]));
    const found = [];
    if (P.courses && P.courses.list.length) found.push(plural(P.courses.list.length, 'course', 'courses'));
    if (P.scholarships) found.push(plural(P.scholarships.list.length, 'scholarship', 'scholarships'));
    if (P.internships) found.push(plural(P.internships.length, 'internship', 'internships'));
    if (P.universities) found.push(plural(P.universities.length, 'university', 'universities'));
    if (P.pages.length || P.mba) found.push(plural(P.pages.length + (P.mba ? 1 : 0), 'guide or tool', 'guides and tools'));
    tally.textContent = `Found ${found.join(', ')}.`;
    foot.replaceChildren(h('a', { class: 'btn', href: full(t) }, 'See all results'));
    foot.hidden = false;
    body.scrollTop = 0;
  }

  async function run() {
    const t = input.value.trim();
    const my = ++seq;
    if (!t) { render(''); return; }
    if (!data) {
      tally.textContent = 'Getting search ready…';
      try { data = await load(); } catch (e) {
        if (my !== seq) return;
        out.replaceChildren(h('p', null, 'Search could not load. Check your connection and try again.'), h('p', null, h('button', { type: 'button', class: 'btn ghost', id: 'fs-retry' }, 'Try again')));
        tally.textContent = '';
        return;
      }
      if (my !== seq) return;
    }
    render(t);
  }
  const later = () => { clearTimeout(timer); timer = setTimeout(run, WAIT); };

  // "On this page": the sections of the page the visitor is on, so a long guide can be jumped through.
  function buildHere() {
    const seen = new Set();
    const items = [];
    document.querySelectorAll('main h2').forEach((el, i) => {
      if (el.closest('[hidden]') || !el.getClientRects().length) return;     // skip headings that are not showing
      const text = el.textContent.replace(/\s+/g, ' ').trim();
      if (!text || seen.has(text)) return;
      seen.add(text);
      if (!el.id) el.id = `sec-${i + 1}`;
      items.push({ id: el.id, text });
    });
    const list = items.slice(0, 10);
    hereList.replaceChildren(...list.map((x) => h('li', null, h('a', { href: `#${x.id}`, 'data-jump': x.id }, h('span', null, x.text), h('span', { class: 'n', 'aria-hidden': 'true' }, '›')))));
    here.hidden = list.length < 3;
  }
  refresh = buildHere;
  hereList.addEventListener('click', (ev) => {
    const a = ev.target.closest('a[data-jump]');
    if (!a) return;
    ev.preventDefault();
    dlg.dataset.jump = a.dataset.jump;       // the page script scrolls there once the panel has closed
    dlg.close();
  });

  input.addEventListener('input', later);
  form.addEventListener('submit', (ev) => { if (!input.value.trim()) { ev.preventDefault(); input.focus(); } });   // a filled box goes to the Search page
  tries.addEventListener('click', (ev) => {
    const b = ev.target.closest('button[data-q]');
    if (!b) return;
    input.value = b.dataset.q;
    run();
  });
  out.addEventListener('click', (ev) => { if (ev.target.closest('#fs-retry')) run(); });

  // start loading now: the panel has just been opened, so a question is likely
  load().then((d) => { data = d; if (input.value.trim()) run(); }, () => { if (input.value.trim()) run(); });
  if (input.value.trim()) run();
}
