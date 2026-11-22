// The student dashboard. One script for every /student/ page: it asks /api/me who is signed in, then runs the code for the page
// named in data-page. Nothing a student typed is put into the page as HTML.
import { STAGES, LEVELS, COUNTRIES, SUBJECT_GROUPS, ENGLISH_TESTS, PROFILE_SECTION_IDS, sectionDone, plansDone, label } from '../lib/account/schema.js';
import { renderSection } from './student-form.js';
import { assessAu, BAND_LABEL, BAND_SAY } from '../lib/visa/au-check.js';
import { STATUSES, STATUS_LABEL, NOTE_MAX } from '../lib/account/saved.js';
import { syncWithAccount, api as savedApi, clearLocal, forgetLocal } from './saved-sync.js';
import { initSop } from './student-sop.js';

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
      : 'Two quick questions help us show what is useful to you. You can change any answer later.';
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
    const items = [['Your plans', '#plans', plansDone(s)]].concat(PROFILE_SECTION_IDS.map((id) => [
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
  for (const id of PROFILE_SECTION_IDS) {
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
    const card = target && target.matches('.st-sec') ? target : PROFILE_SECTION_IDS.map((id) => $(`#${id}`)).find((c) => !c.classList.contains('is-done'));
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
      clearLocal();
      notice('Your account has been deleted', 'Your details have been removed from Universities500. You can still browse the site without an account.', { label: 'Back to the home page', run: () => location.assign('/') });
    } else { go.disabled = false; say(dst, r.j.message || 'Could not delete the account. Try again, or contact us.', 'bad'); }
  });
}

// ---- My shortlist ----------------------------------------------------------------------------------------------

const TABS = [
  ['courses', 'Courses', ['crs', 'mba'], '/courses/', 'Browse courses', 'course or MBA programme'],
  ['scholarships', 'Scholarships', ['sch'], '/scholarships/', 'Browse scholarships', 'scholarship'],
  ['internships', 'Internships', ['int'], '/internships/', 'Browse internships', 'internship'],
];
const safeHref = (u) => (/^\/(?!\/)/.test(u) || /^https:\/\//.test(u) ? u : '');

function shortlist() {
  const tabsEl = $('[data-tabs]'), listEl = $('[data-list]'), emptyEl = $('[data-empty]'), st = $('[data-sl-status]');
  let items = [];
  let tab = TABS.some((t) => t[0] === location.hash.slice(1)) ? location.hash.slice(1) : 'courses';
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  const inTab = (t) => items.filter((i) => t[2].includes(i.kind));

  function paintTabs() {
    tabsEl.replaceChildren(...TABS.map((t) => {
      const b = el('button', '', t[1]);
      b.type = 'button';
      b.setAttribute('aria-pressed', String(t[0] === tab));
      b.append(el('span', 'n', `(${inTab(t).length})`));
      b.addEventListener('click', () => { tab = t[0]; history.replaceState(null, '', '#' + tab); say(st, ''); paint(); });
      return b;
    }));
  }

  function row(it) {
    const li = el('li', 'sl-item');
    li.dataset.status = it.status;
    const main = el('div', 'sl-main');
    const h = el('h3', 'sl-title');
    const href = safeHref(it.url || '');
    if (href) {
      const a = el('a', '', it.title); a.href = href;
      if (!href.startsWith('/')) { a.target = '_blank'; a.rel = 'noopener nofollow'; }
      h.append(a);
    } else h.textContent = it.title;
    main.append(h);
    if (it.sub) main.append(el('p', 'sl-sub', it.sub));
    if (it.saved_at) main.append(el('p', 'sl-when', 'Saved ' + new Date(it.saved_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })));

    const side = el('div', 'sl-side');
    const lab = el('label', 'sl-status');
    lab.append(el('span', '', 'Status'));
    const sel = el('select');
    for (const k of STATUSES[it.kind]) { const o = el('option', '', STATUS_LABEL[k]); o.value = k; sel.append(o); }
    sel.value = it.status;
    lab.append(sel);
    sel.addEventListener('change', async () => {
      const before = it.status;
      say(st, 'Saving…');
      const r = await savedApi('PATCH', { id: it.item_id, status: sel.value });
      if (r.status === 401) return toSignIn();
      if (r.ok) { it.status = sel.value; li.dataset.status = it.status; say(st, 'Saved.', 'ok'); }
      else { sel.value = before; say(st, r.j.message || 'Could not save. Try again.', 'bad'); }
    });
    const rm = el('button', 'sl-remove', 'Remove'); rm.type = 'button';
    rm.setAttribute('aria-label', `Remove ${it.title} from my shortlist`);
    rm.addEventListener('click', async () => {
      rm.disabled = true;
      const r = await savedApi('DELETE', { id: it.item_id });
      if (r.status === 401) return toSignIn();
      if (r.ok) { items = items.filter((x) => x.item_id !== it.item_id); forgetLocal(it.item_id); say(st, 'Removed.', 'ok'); paint(); }
      else { rm.disabled = false; say(st, r.j.message || 'Could not remove it. Try again.', 'bad'); }
    });
    side.append(lab, rm);

    const note = el('details', 'sl-note');
    note.open = !!it.note;
    const sum = el('summary', '', it.note ? 'Your note' : 'Add a note');
    const ta = el('textarea'); ta.rows = 3; ta.maxLength = NOTE_MAX; ta.value = it.note || '';
    ta.setAttribute('aria-label', `Note about ${it.title}`);
    const nst = el('p', 'st-status'); nst.setAttribute('role', 'status'); nst.setAttribute('aria-live', 'polite');
    ta.addEventListener('change', async () => {
      say(nst, 'Saving…');
      const r = await savedApi('PATCH', { id: it.item_id, note: ta.value });
      if (r.status === 401) return toSignIn();
      if (r.ok) { it.note = ta.value.trim(); sum.textContent = it.note ? 'Your note' : 'Add a note'; say(nst, 'Saved.', 'ok'); }
      else say(nst, r.j.message || 'Could not save the note. Try again.', 'bad');
    });
    note.append(sum, ta, nst);

    li.append(main, side, note);
    return li;
  }

  function paint() {
    paintTabs();
    const t = TABS.find((x) => x[0] === tab);
    const rows = inTab(t);
    listEl.replaceChildren(...rows.map(row));
    emptyEl.hidden = rows.length > 0;
    if (!rows.length) {
      const p = el('p', '', `Nothing saved here yet. Use the bookmark button on any ${t[5]} while you browse and it will appear here.`);
      const a = el('a', 'btn ghost', t[4]); a.href = t[3];
      emptyEl.replaceChildren(p, a);
    }
  }

  (async () => {
    const synced = await syncWithAccount();
    let list = synced;
    if (!list) {
      const r = await savedApi('GET');
      if (r.status === 401) return toSignIn();
      if (!r.ok) return notice('We could not load your shortlist', r.j.message || 'Please try again.', { label: 'Try again', run: () => location.reload() });
      list = r.j.items;
    }
    items = list;
    paint();
  })();
}

// ---- Visa self-check: Australia --------------------------------------------------------------------------------

const GLYPH = { green: '✓', amber: '!', red: '×' };
const aud = (n) => 'AUD ' + Math.round(n).toLocaleString('en-IN');

function visa() {
  const card = $('#visa_au'), result = $('[data-result]'), empty = $('[data-empty]');
  const form = renderSection($('[data-form]', card), 'visa_au', me.sections.visa_au || {});
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };

  // What is read from the profile, with a link to change it.
  function paintProfile() {
    const eng = me.sections.english || {}, imm = me.sections.immigration || {};
    let e = 'Not added yet';
    if (eng.test === 'none') e = 'No test yet';
    else if (eng.test) e = `${label(ENGLISH_TESTS, eng.test)}, ${eng.status === 'taken' && eng.overall !== undefined ? 'score ' + eng.overall : eng.status === 'booked' ? 'test date booked' : 'planning to take it'}`;
    let h = 'Not added yet';
    if (imm.history === 'none') h = 'No earlier problems';
    else if (imm.history === 'prefer_not') h = 'Prefer not to say';
    else if (imm.history === 'some') h = `${(imm.items || []).length} application${(imm.items || []).length === 1 ? '' : 's'} listed`;
    const row = (name, value, href) => {
      const li = el('li');
      li.append(el('span', 'k', name), el('span', 'v', value));
      const a = el('a', '', value === 'Not added yet' ? 'Add' : 'Edit'); a.href = href; a.setAttribute('aria-label', `${a.textContent} ${name.toLowerCase()} in your profile`);
      li.append(a);
      return li;
    };
    $('[data-profile]').replaceChildren(row('English test', e, '/student/profile/#english'), row('Earlier visa applications', h, '/student/profile/#immigration'));
  }

  function paint() {
    paintProfile();
    const done = sectionDone('visa_au', me.sections.visa_au);
    card.classList.toggle('is-done', done);
    $('.state', card).textContent = done ? 'Saved' : 'Not saved yet';
    const r = assessAu(me.sections);
    result.hidden = !r.complete;
    empty.hidden = r.complete;
    if (!r.complete) { card.open = true; return; }

    const band = $('[data-band]');
    band.dataset.band = r.band;
    $('[data-glyph]').textContent = GLYPH[r.band];
    $('[data-band-name]').textContent = BAND_LABEL[r.band];
    $('[data-score]').textContent = String(r.score);
    $('[data-score-bar]').style.width = r.score + '%';
    $('.vc-score', result).dataset.band = r.band;
    $('[data-say]').textContent = BAND_SAY[r.band];

    const held = $('[data-held]');
    held.replaceChildren();
    held.hidden = !r.flags.length;
    if (r.flags.length) {
      if (r.held) held.append(el('p', 'vc-held-lead', `Your points alone would be ${BAND_LABEL[r.scoreBand]}, but something holds the band down:`));
      const ul = el('ul');
      for (const f of r.flags) ul.append(el('li', '', f.text));
      held.append(ul);
    }

    const list = $('[data-factors]');
    list.replaceChildren();
    for (const f of r.factors) {
      const li = el('li', 'vc-factor');
      const head = el('div', 'vc-fhead');
      head.append(el('b', '', f.label), el('span', 'vc-fpts', `${f.score} / ${f.max}`));
      const bar = el('div', 'vc-bar vc-bar-s'); bar.setAttribute('aria-hidden', 'true');
      const fill = el('i'); fill.style.width = Math.round((f.score / f.max) * 100) + '%'; bar.append(fill);
      li.append(head, bar);
      const notes = el('ul', 'vc-notes-l');
      for (const n of f.notes) notes.append(el('li', '', n));
      li.append(notes);
      list.append(li);
    }

    const acts = $('[data-actions]');
    acts.replaceChildren();
    for (const a of r.actions) {
      const li = el('li');
      if (a.must) li.append(el('b', 'vc-must', 'Do this first. '));
      li.append(document.createTextNode(a.text));
      acts.append(li);
    }
    acts.hidden = !r.actions.length;
    $('[data-no-actions]').hidden = r.actions.length > 0;
  }

  const save = $('[data-save]', card), st = $('[data-status]', card);
  save.addEventListener('click', async () => {
    say(st, 'Saving…'); save.disabled = true;
    const r = await api('PATCH', '/api/me', { sections: { visa_au: form.collect() } });
    save.disabled = false;
    if (r.status === 401) return toSignIn();
    if (r.ok) {
      me.sections.visa_au = r.j.sections.visa_au || {};
      form.clearErrors(); say(st, 'Saved.', 'ok');
      paint();
      if (!result.hidden) { card.open = false; result.scrollIntoView({ block: 'start' }); result.focus({ preventScroll: true }); }
    } else if (r.status === 422) {
      const loose = form.showErrors(r.j.errors?.sections?.visa_au || {});
      say(st, loose.length ? loose.join(' ') : 'Check the highlighted answers.', 'bad');
    } else say(st, r.j.message || 'Could not save. Try again.', 'bad');
  });
  paint();
  // Nothing saved yet: open the questions. Saved before: show the result, with the answers one click away.
  card.open = !sectionDone('visa_au', me.sections.visa_au);
}

// ---- SOP builder -----------------------------------------------------------------------------------------------

function sop() { initSop({ root, me, api, getSaved: () => syncWithAccount() }); }

// ---- start -----------------------------------------------------------------------------------------------------

$$('[data-signout]').forEach((b) => b.addEventListener('click', async () => {
  b.disabled = true;
  await api('POST', '/api/auth/logout', {});
  clearLocal(); // bookmarks kept in this browser are cleared too, so the next person on this device does not see them
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
  ({ overview, profile, settings, shortlist, visa, sop }[page] || (() => {}))();
  if (page !== 'shortlist') syncWithAccount().then((list) => { const sum = $('[data-sl-sum]'); if (list && sum && list.length) sum.textContent = `${list.length} saved: ${list.filter((i) => ['crs', 'mba'].includes(i.kind)).length} courses, ${list.filter((i) => i.kind === 'sch').length} scholarships, ${list.filter((i) => i.kind === 'int').length} internships.`; });
})();
