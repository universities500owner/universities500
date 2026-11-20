// The student dashboard. One script for every /student/ page: it asks /api/me who is signed in, then runs the code for the page
// named in data-page. Nothing a student typed is put into the page as HTML.
import { STAGES, LEVELS, COUNTRIES, SUBJECT_GROUPS, SECTION_IDS, sectionDone, plansDone } from '../lib/account/schema.js';
import { renderSection } from './student-form.js';

const root = document.querySelector('[data-student]');
const page = root.dataset.page;
const $ = (sel, from = root) => from.querySelector(sel);
const $$ = (sel, from = root) => [...from.querySelectorAll(sel)];
const loading = $('[data-loading]'), content = $('[data-content]'), noticeBox = $('[data-notice]');

let me = null;

function api(method, url, body) {
  return fetch(url, { method, credentials: 'same-origin', headers: body ? { 'content-type': 'application/json' } : {}, body: body ? JSON.stringify(body) : undefined })
    .then((r) => r.json().catch(() => ({})).then((j) => ({ ok: r.ok && j.ok !== false, status: r.status, j })))
    .catch(() => ({ ok: false, status: 0, j: { message: 'We could not reach the site. Check your connection and try again.' } }));
}
const toSignIn = () => location.replace('/sign-in/?next=' + encodeURIComponent(location.pathname));
const say = (el, text, kind) => { el.textContent = text || ''; el.classList.toggle('is-bad', kind === 'bad'); el.classList.toggle('is-ok', kind === 'ok'); };

function notice(title, text, action) {
  loading.hidden = true; content.hidden = true; noticeBox.hidden = false;
  const h = document.createElement('h2'); h.textContent = title;
  const p = document.createElement('p'); p.textContent = text;
  noticeBox.replaceChildren(h, p);
  if (action) {
    const b = document.createElement('button'); b.type = 'button'; b.className = 'btn'; b.textContent = action.label; b.addEventListener('click', action.run);
    noticeBox.append(b);
  }
  noticeBox.focus?.();
}

// ---- Overview --------------------------------------------------------------------------------------------------

const NEXT = {
  exploring: [['/study-in/', 'Compare destinations'], ['/search/', 'Search courses'], ['/budget/', 'Check your budget']],
  applying: [['/application-prep/', 'Application prep'], ['/english-test/', 'English tests'], ['/scholarships/', 'Scholarships']],
  offer: [['/education-loan-guide/', 'Education loans'], ['/scholarships/', 'Scholarships'], ['/course-fitment/', 'Course fitment']],
  accepted: [['/before-you-fly/', 'Before you fly'], ['/visa-readiness/', 'Visa readiness'], ['/working-while-you-study/', 'Working while you study']],
  visa: [['/visa-readiness/', 'Visa readiness'], ['/before-you-fly/', 'Before you fly'], ['/working-while-you-study/', 'Working while you study']],
};

// The first name they gave us, or nothing. An email address is never turned into a name.
function firstName() {
  return (me.sections.profile.full_name || me.student.display_name || '').trim().split(/\s+/)[0];
}

function overview() {
  const s = me.student;
  const greet = () => {
    $('[data-hello]').textContent = firstName() ? `Hi ${firstName()}` : 'Welcome';
    $('[data-welcome]').textContent = s.onboarded_at
      ? 'Here is where you are, and what to do next.'
      : 'Welcome. Two quick questions help us show what is useful to you. You can change any answer later.';
  };

  // Where are you now
  const track = $('[data-track]');
  const paintTrack = () => {
    const at = STAGES.findIndex((x) => x[0] === s.stage);
    $$('.st-stage', track).forEach((lab, i) => {
      lab.classList.toggle('is-past', at >= 0 && i < at);
      lab.classList.toggle('is-now', i === at);
    });
    const next = $('[data-next]');
    const links = NEXT[s.stage];
    next.hidden = !links;
    if (links) {
      const ul = document.createElement('ul');
      for (const [href, text] of links) { const li = document.createElement('li'), a = document.createElement('a'); a.href = href; a.textContent = text; li.append(a); ul.append(li); }
      const p = document.createElement('p'); p.textContent = 'Useful at this stage:';
      next.replaceChildren(p, ul);
    }
  };
  STAGES.forEach(([id, name, hint]) => {
    const li = document.createElement('li');
    const lab = document.createElement('label'); lab.className = 'st-stage';
    const inp = document.createElement('input'); inp.type = 'radio'; inp.name = 'stage'; inp.value = id; inp.checked = s.stage === id;
    const dot = document.createElement('span'); dot.className = 'dot'; dot.setAttribute('aria-hidden', 'true');
    const b = document.createElement('b'); b.textContent = name;
    const sm = document.createElement('small'); sm.textContent = hint;
    lab.append(inp, dot, b, sm); li.append(lab); track.append(li);
    inp.addEventListener('change', async () => {
      const st = $('[data-stage-status]');
      say(st, 'Saving…');
      const r = await api('PATCH', '/api/me', { student: { stage: id } });
      if (r.status === 401) return toSignIn();
      if (r.ok) { s.stage = id; paintTrack(); say(st, 'Saved.', 'ok'); progress(); }
      else say(st, r.j.message || 'Could not save. Try again.', 'bad');
    });
  });

  // What you are looking for
  const chip = (box, name, type, value, text, checked) => {
    const lab = document.createElement('label'); lab.className = 'st-chip';
    const inp = document.createElement('input'); inp.type = type; inp.name = name; inp.value = value; inp.checked = checked;
    const sp = document.createElement('span'); sp.textContent = text;
    lab.append(inp, sp); box.append(lab);
  };
  COUNTRIES.forEach(([id, name]) => chip($('[data-countries]'), 'countries', 'checkbox', id, name, (s.countries || []).includes(id)));
  LEVELS.forEach(([id, name]) => chip($('[data-levels]'), 'level', 'radio', id, name, s.level === id));
  SUBJECT_GROUPS.forEach(([id, name]) => chip($('[data-groups]'), 'subject_groups', 'checkbox', id, name, (s.subject_groups || []).includes(id)));
  const subj = JSON.parse($('#st-subjects').textContent);
  const more = $('[data-subjects]');
  SUBJECT_GROUPS.forEach(([gid, gname]) => {
    const list = subj.filter((x) => x[2] === gid);
    if (!list.length) return;
    const h = document.createElement('h3'); h.textContent = gname;
    const box = document.createElement('div'); box.className = 'st-chips';
    list.forEach(([id, name]) => chip(box, 'subjects', 'checkbox', id, name, (s.subjects || []).includes(id)));
    more.append(h, box);
  });
  const titleOf = () => {
    $('[data-plans-title]').textContent = s.onboarded_at ? 'What you are looking for' : 'Tell us what you are looking for';
    $('[data-plans-save]').textContent = s.onboarded_at ? 'Save changes' : 'Save and continue';
  };
  $('[data-plans]').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const st = $('[data-plans-status]'), btn = $('[data-plans-save]');
    const pick = (name) => $$(`input[name="${name}"]:checked`).map((i) => i.value);
    const lvl = pick('level')[0] || '';
    say(st, 'Saving…'); btn.disabled = true;
    const r = await api('PATCH', '/api/me', { student: { countries: pick('countries'), level: lvl, subject_groups: pick('subject_groups'), subjects: pick('subjects') }, onboarded: true });
    btn.disabled = false;
    if (r.status === 401) return toSignIn();
    if (r.ok) {
      Object.assign(s, r.j.student);
      s.onboarded_at = s.onboarded_at || new Date().toISOString();
      say(st, 'Saved.', 'ok'); titleOf(); greet(); progress();
    } else if (r.status === 422) {
      say(st, Object.values(r.j.errors?.student || {}).join(' ') || 'Check your choices and try again.', 'bad');
    } else say(st, r.j.message || 'Could not save. Try again.', 'bad');
  });

  // What is left to fill in
  const progress = () => {
    const items = [['Your plans', '#plans', plansDone(s)]].concat(SECTION_IDS.map((id) => [
      { profile: 'About you', academic: 'Academic history', english: 'English test', work: 'Work experience', immigration: 'Immigration history' }[id],
      `/student/profile/#${id}`, sectionDone(id, me.sections[id]),
    ]));
    const done = items.filter((x) => x[2]).length;
    $('[data-prog-text]').textContent = `${done} of ${items.length} done`;
    $('[data-prog-bar]').style.width = `${Math.round((done / items.length) * 100)}%`;
    const ul = $('[data-todo]'); ul.replaceChildren();
    for (const [text, href, ok] of items) {
      const li = document.createElement('li'); if (ok) li.className = 'done';
      const a = document.createElement('a'); a.href = href;
      const tick = document.createElement('span'); tick.className = 'tick'; tick.setAttribute('aria-hidden', 'true');
      const t = document.createElement('span'); t.textContent = text;
      const go = document.createElement('span'); go.className = 'go'; go.textContent = ok ? 'Edit' : 'Add';
      a.append(tick, t, go); li.append(a); ul.append(li);
    }
  };

  greet(); paintTrack(); titleOf(); progress();
}

// ---- Profile ---------------------------------------------------------------------------------------------------

function profile() {
  const forms = {};
  const mark = (card, id) => {
    const ok = sectionDone(id, me.sections[id]);
    card.classList.toggle('is-done', ok);
    $('.state', card).textContent = ok ? 'Added' : 'Not added yet';
  };
  for (const id of SECTION_IDS) {
    const card = $(`#${id}`);
    const form = renderSection($('[data-form]', card), id, me.sections[id] || {});
    forms[id] = form;
    mark(card, id);
    const save = $('[data-save]', card), st = $('[data-status]', card);
    save.addEventListener('click', async () => {
      say(st, 'Saving…'); save.disabled = true;
      const r = await api('PATCH', '/api/me', { sections: { [id]: form.collect() } });
      save.disabled = false;
      if (r.status === 401) return toSignIn();
      if (r.ok) {
        me.sections[id] = r.j.sections[id] || {};
        form.clearErrors(); mark(card, id); say(st, 'Saved.', 'ok');
      } else if (r.status === 422) {
        const loose = form.showErrors(r.j.errors?.sections?.[id] || {});
        say(st, loose.length ? loose.join(' ') : 'Check the highlighted fields.', 'bad');
      } else say(st, r.j.message || 'Could not save. Try again.', 'bad');
    });
  }
  const openFrom = () => {
    const target = document.getElementById(location.hash.slice(1));
    const card = target && target.matches('.st-sec') ? target : SECTION_IDS.map((id) => $(`#${id}`)).find((c) => !c.classList.contains('is-done'));
    if (card) { card.open = true; if (target === card) card.scrollIntoView({ block: 'start' }); }
  };
  openFrom();
  window.addEventListener('hashchange', openFrom);
}

// ---- Settings --------------------------------------------------------------------------------------------------

function settings() {
  const s = me.student;
  $('[data-email]').textContent = s.email;
  $('[data-since]').textContent = s.created_at ? new Date(s.created_at).toLocaleDateString('en-IN', { year: 'numeric', month: 'long', day: 'numeric' }) : '';
  const mk = $('#st-marketing'), mst = $('[data-marketing-status]');
  mk.checked = !!s.marketing_opt_in;
  mk.addEventListener('change', async () => {
    say(mst, 'Saving…');
    const r = await api('PATCH', '/api/me', { student: { marketing_opt_in: mk.checked } });
    if (r.status === 401) return toSignIn();
    if (r.ok) say(mst, 'Saved.', 'ok');
    else { mk.checked = !mk.checked; say(mst, r.j.message || 'Could not save. Try again.', 'bad'); }
  });

  const text = $('#st-del-text'), go = $('[data-del-go]'), dst = $('[data-del-status]');
  text.addEventListener('input', () => { go.disabled = text.value.trim().toLowerCase() !== 'delete'; });
  go.addEventListener('click', async () => {
    go.disabled = true; say(dst, 'Deleting…');
    const r = await api('DELETE', '/api/me', { confirm: 'delete' });
    if (r.ok) {
      notice('Your account has been deleted', 'Your details have been removed from Universities500. You can still browse the site without an account.', { label: 'Back to the home page', run: () => location.assign('/') });
    } else { go.disabled = false; say(dst, r.j.message || 'Could not delete the account. Try again, or contact us.', 'bad'); }
  });
}

// ---- start -----------------------------------------------------------------------------------------------------

$$('[data-signout]').forEach((b) => b.addEventListener('click', async () => {
  b.disabled = true;
  await api('POST', '/api/auth/logout', {});
  location.assign('/sign-in/');
}));
// Coming back with the Back button after signing out must not show the old page from the cache.
window.addEventListener('pageshow', (e) => { if (e.persisted) location.reload(); });

(async function boot() {
  const r = await api('GET', '/api/me');
  if (r.status === 401) return toSignIn();
  if (r.status === 503) return notice('Sign-in is not open yet', 'Accounts will open soon. Everything else on the site works without one.');
  if (!r.ok) return notice('We could not load your dashboard', r.j.message || 'Please try again.', { label: 'Try again', run: () => location.reload() });
  me = r.j;
  loading.hidden = true; content.hidden = false;
  ({ overview, profile, settings }[page] || (() => {}))();
})();
