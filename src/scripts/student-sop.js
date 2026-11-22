// The SOP builder page (/student/sop/). Started by student.js once the student is signed in and their account is loaded.
// Four screens: home (what is still missing from the profile), start (destination, university, course), story (six
// questions and a voice) and draft (the draft with the facts it used). Nothing a student typed is put into the page as HTML.
import { COUNTRIES, SUBJECT_GROUPS, sectionDone, label } from '../lib/account/schema.js';
import {
  PROFILE_GATE, NOTE_MAX, ARCS, TONES, QIDS, WORDS, LIMIT_MIN, LIMIT_MAX, wordsTarget, withThe, questions, courseChosen, storyDone, toneDone, answered, answersDone, nextStep,
  factsFor, buildDraft, checks, draftText, wordCount,
} from '../lib/sop/model.js';

const VIEWS = ['home', 'start', 'story', 'draft'];
const GAP_RX = /\[[^\]\n]+\]/g; // for counting only; use HAS_GAP to test (a global regex keeps its position between tests)
const HAS_GAP = /\[[^\]\n]+\]/;

function h(tag, o = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(o)) {
    if (v === undefined || v === null || v === false) continue;
    if (k === 'class') e.className = v;
    else if (k === 'text') e.textContent = v;
    else if (k === 'on') for (const [ev, fn] of Object.entries(v)) e.addEventListener(ev, fn);
    else if (k === 'props') Object.assign(e, v);
    else e.setAttribute(k, v === true ? '' : v);
  }
  for (const c of kids.flat()) if (c !== null && c !== undefined && c !== false) e.append(c.nodeType ? c : document.createTextNode(String(c)));
  return e;
}

export function initSop({ root, me, api, getSaved }) {
  const $ = (sel, from = root) => from.querySelector(sel);
  const view = (name) => $(`[data-view="${name}"]`);
  const sections = me.sections;
  let S = JSON.parse(JSON.stringify(sections.sop || {}));
  let current = 'home';

  // ---- what we know about the profile ------------------------------------------------------------------------
  const have = () => Object.fromEntries(PROFILE_GATE.map(([id]) => [id, sectionDone(id, sections[id])]));
  const gateMet = () => PROFILE_GATE.every(([id]) => have()[id]);
  const destName = () => label(COUNTRIES, S.dest) || '';
  // The length to aim for: what the student chose, or the university's own limit if that is lower.
  const aimWords = () => Math.min(wordsTarget(S), S.limit || Infinity);
  const profileChips = () => [
    ...((sections.work && sections.work.items) || []).slice(0, 2).map((w) => `My work as ${w.title} at ${w.employer}`),
    ...((sections.academic && sections.academic.items) || []).filter((a) => a.institution).slice(0, 2).map((a) => (a.field ? `My studies in ${a.field} at ${a.institution}` : `My studies at ${a.institution}`)),
  ];
  const ctx = () => ({
    destName: withThe(S.dest, destName()), courseName: S.course_name || '', uniName: S.uni_name || '', group: S.group || '', profileChips: profileChips(),
    academic: (sections.academic && sections.academic.items) || [],
    work: sections.work && !sections.work.none ? (sections.work.items || []) : [],
  });
  const forText = () => [S.course_name, S.uni_name, destName()].filter(Boolean).join(' · ');

  // ---- the university data (loaded only when needed) ----------------------------------------------------------
  const cache = { index: null, list: null, uni: new Map() }; // index: the request; list: what it returned
  const getJson = (url) => fetch(url, { credentials: 'same-origin' }).then((r) => (r.ok ? r.json() : Promise.reject(new Error('load'))));
  const loadIndex = () => (cache.index ||= getJson('/student/sop-data/index.json').then((d) => (cache.list = d)).catch((e) => { cache.index = null; throw e; }));
  const loadUni = (slug) => {
    if (!cache.uni.has(slug)) cache.uni.set(slug, getJson(`/student/sop-data/${encodeURIComponent(slug)}.json`).catch((e) => { cache.uni.delete(slug); throw e; }));
    return cache.uni.get(slug);
  };

  // ---- saving ---------------------------------------------------------------------------------------------------
  let timer = null;
  const statusEl = () => $('[data-status]', view(current));
  const say = (text, kind) => { const el = statusEl(); if (!el) return; el.textContent = text || ''; el.classList.toggle('is-bad', kind === 'bad'); el.classList.toggle('is-ok', kind === 'ok'); };
  async function saveNow() {
    clearTimeout(timer);
    const r = await api('PATCH', '/api/me', { sections: { sop: S } });
    if (r.ok) { sections.sop = r.j.sections.sop || {}; return true; }
    const errs = r.j.errors && r.j.errors.sections && r.j.errors.sections.sop;
    say(errs ? Object.values(errs).join(' ') : (r.j.message || 'Could not save. Try again.'), 'bad');
    return false;
  }
  function queueSave() {
    clearTimeout(timer);
    say('Saving…');
    timer = setTimeout(async () => { if (await saveNow()) say('Saved', 'ok'); }, 700);
  }

  // ---- steps bar and routing ---------------------------------------------------------------------------------
  function renderSteps() {
    const max = VIEWS.indexOf(nextStep(have(), S));
    const labels = [['home', 'Your profile'], ['start', 'Course'], ['story', 'Your story'], ['draft', 'Draft']];
    $('[data-steps]').replaceChildren(...labels.map(([id, text], i) => {
      const cls = id === current ? 'is-now' : i < max ? 'is-done' : '';
      return h('li', { class: cls }, i <= max ? h('a', { href: '#' + id, 'aria-current': id === current ? 'step' : undefined }, text) : h('span', {}, text));
    }));
  }

  function route() {
    const max = nextStep(have(), S);
    const asked = location.hash.replace('#', '');
    const want = VIEWS.includes(asked) ? asked : max;
    const go = VIEWS.indexOf(want) > VIEWS.indexOf(max) ? max : want;
    show(go);
  }

  let shown = false;
  function show(name) {
    current = name;
    for (const v of VIEWS) view(v).hidden = v !== name;
    ({ home: renderHome, start: renderStart, story: renderStory, draft: renderDraft }[name])();
    renderSteps();
    const head = $('[tabindex="-1"]', view(name));
    if (head && shown) head.focus({ preventScroll: true }); // not on first load: the page itself has just been announced
    shown = true;
    window.scrollTo({ top: 0 });
  }

  // ---- 1. home ------------------------------------------------------------------------------------------------
  function renderHome() {
    const g = have();
    const ok = gateMet();
    const rows = [
      ...PROFILE_GATE.map(([id, text]) => ({ text, done: g[id], href: `/student/profile/#${id}`, state: g[id] ? 'Done' : 'Complete now' })),
      { text: 'Course for your SOP', done: courseChosen(S), href: ok ? '#start' : null, state: courseChosen(S) ? S.course_name : (ok ? 'Choose' : 'After your profile') },
      { text: 'Your story (6 quick questions)', done: storyDone(S), href: ok && courseChosen(S) ? '#story' : null, state: storyDone(S) ? 'Done' : (ok && courseChosen(S) ? 'Complete now' : 'After your course') },
      { text: 'Voice and tone', done: toneDone(S), href: ok && courseChosen(S) ? '#story' : null, state: toneDone(S) ? 'Done' : (ok && courseChosen(S) ? 'Add' : 'After your course') },
    ];
    const done = rows.filter((r) => r.done).length;
    $('[data-pct]', view('home')).textContent = `${Math.round((done / rows.length) * 100)}% ready`;
    $('[data-bar]', view('home')).style.width = `${Math.round((done / rows.length) * 100)}%`;
    $('[data-rows]').replaceChildren(...rows.map((r) => h('li', { class: r.done ? 'done' : '' },
      r.href
        ? h('a', { href: r.href }, h('span', { class: 'tick', 'aria-hidden': 'true' }), h('span', { text: r.text }), h('span', { class: 'go', text: r.state }))
        : h('span', { class: 'sop-row-off' }, h('span', { class: 'tick', 'aria-hidden': 'true' }), h('span', { text: r.text }), h('span', { class: 'go', text: r.state })))));
    const go = $('[data-go]');
    if (!ok) {
      const first = PROFILE_GATE.find(([id]) => !g[id])[0];
      go.textContent = 'Complete my profile';
      go.setAttribute('href', `/student/profile/#${first}`);
    } else {
      const next = nextStep(g, S);
      go.textContent = next === 'start' ? 'Start my SOP' : next === 'story' ? 'Continue with my story' : 'Open my draft';
      go.setAttribute('href', '#' + next);
    }
  }

  // ---- 2. start -----------------------------------------------------------------------------------------------
  let sel = {};
  function renderStart() {
    const v = view('start');
    sel = { dest: S.dest || '', uni: S.uni || '', uni_name: S.uni_name || '', course_id: S.course_id || '', course_name: S.course_name || '', group: S.group || '' };
    let uniFile = null;
    let uniLimit = 24, courseLimit = 12; // lists show a few and then "Show more", so the page never scrolls inside a box
    const more = (shown, total, grow) => (total > shown ? [h('li', { class: 'sop-more' }, h('button', { type: 'button', class: 'btn ghost', on: { click: grow } }, `Show more (${total - shown} left)`))] : []);

    const dests = $('[data-dests]', v);
    dests.replaceChildren(...COUNTRIES.map(([id, name]) => h('label', { class: 'st-chip' },
      h('input', { type: 'radio', name: 'sop-dest', value: id, props: { checked: sel.dest === id }, on: { change: () => { sel = { ...sel, dest: id, uni: '', uni_name: '', course_id: '', course_name: '', group: '' }; uniFile = null; uniLimit = 24; $('[data-uni-q]', v).value = ''; paint(); } } }),
      h('span', { text: name }))));

    const grp = $('[data-group]', v);
    grp.replaceChildren(h('option', { value: '', text: 'Not sure' }), ...SUBJECT_GROUPS.map(([id, name]) => h('option', { value: id, text: name })));
    grp.onchange = () => { sel = { ...sel, group: grp.value }; };

    const paint = () => {
      const index = cache.list;
      $('[data-uni-card]', v).classList.toggle('is-off', !sel.dest);
      $('[data-course-card]', v).classList.toggle('is-off', !sel.uni);
      for (const n of v.querySelectorAll('.sop-n')) n.classList.toggle('is-done', !!({ 1: sel.dest, 2: sel.uni, 3: sel.course_name }[n.dataset.n]));
      // universities
      const list = $('[data-unis]', v), empty = $('[data-uni-empty]', v);
      if (!sel.dest) { list.replaceChildren(); empty.hidden = true; }
      else if (!index) { list.replaceChildren(); empty.hidden = false; empty.textContent = 'Loading the universities…'; }
      else {
        const q = $('[data-uni-q]', v).value.trim().toLowerCase();
        const rows = index.filter((u) => u.c === sel.dest && (!q || u.n.toLowerCase().includes(q)));
        empty.hidden = rows.length > 0;
        empty.textContent = 'No university matches that search.';
        // the chosen university stays on screen even when it is past the limit
        const shown = rows.slice(0, uniLimit);
        const chosen = rows.find((u) => u.s === sel.uni);
        if (chosen && !shown.includes(chosen)) shown.push(chosen);
        list.replaceChildren(...shown.map((u) => h('li', {}, h('button', {
          type: 'button', class: 'sop-opt', 'aria-pressed': String(sel.uni === u.s),
          on: { click: () => { sel = { ...sel, uni: u.s, uni_name: u.n, course_id: '', course_name: '', group: '' }; uniFile = null; courseLimit = 12; $('[data-course-q]', v).value = ''; paint(); loadCourses(); } },
        }, h('b', { text: u.n })))), ...more(shown.length, rows.length, () => { uniLimit += 24; paint(); }));
      }
      // courses
      const cl = $('[data-courses]', v), note = $('[data-course-note]', v), find = $('[data-course-find]', v), typed = $('[data-typed]', v);
      if (!sel.uni) { cl.replaceChildren(); note.textContent = ''; find.hidden = true; }
      else if (!uniFile) { cl.replaceChildren(); note.textContent = 'Loading the courses…'; find.hidden = true; }
      else {
        const all = uniFile.courses;
        note.textContent = all.length ? `${all.length} course${all.length === 1 ? '' : 's'} we have read from ${sel.uni_name}'s website. Pick yours, or add it below if it is not here.` : `We have not read ${sel.uni_name}'s courses yet. Add your course below.`;
        find.hidden = all.length <= 12;
        const q = $('[data-course-q]', v).value.trim().toLowerCase();
        const rows = all.filter((c) => !q || c.n.toLowerCase().includes(q));
        const shown = rows.slice(0, courseLimit);
        const chosen = rows.find((c) => c.id === sel.course_id);
        if (chosen && !shown.includes(chosen)) shown.push(chosen);
        cl.replaceChildren(...shown.map((c) => h('li', {}, h('button', {
          type: 'button', class: 'sop-opt', 'aria-pressed': String(sel.course_id === c.id),
          on: { click: () => { sel = { ...sel, course_id: c.id, course_name: c.n, group: c.g || '' }; paint(); } },
        }, h('b', { text: c.n }), h('span', { text: [c.lv, c.d].filter(Boolean).join(' · ') })))), ...more(shown.length, rows.length, () => { courseLimit += 24; paint(); }));
        if (!all.length) typed.open = true;
      }
      $('[data-group-wrap]', v).hidden = !sel.course_name;
      grp.value = sel.group || '';
      const ready = !!(sel.dest && sel.uni && sel.course_name);
      $('[data-summary]', v).textContent = [sel.course_name, sel.uni_name, label(COUNTRIES, sel.dest)].filter(Boolean).join(' · ') || 'Nothing chosen yet';
      $('[data-next]', v).disabled = !ready;
    };

    async function loadCourses() {
      try { uniFile = await loadUni(sel.uni); } catch { uniFile = { courses: [] }; say('We could not load the courses. You can still add yours below.', 'bad'); }
      paint();
    }
    $('[data-uni-q]', v).oninput = () => { uniLimit = 24; paint(); };
    $('[data-course-q]', v).oninput = () => { courseLimit = 12; paint(); };
    $('[data-use-typed]', v).onclick = () => {
      const name = $('[data-course-name]', v).value.replace(/\s+/g, ' ').trim();
      if (!name) { say('Enter the course name.', 'bad'); return; }
      sel = { ...sel, course_id: '', course_name: name.slice(0, 140), group: '' };
      say('');
      paint();
    };
    $('[data-next]', v).onclick = async (e) => {
      const btn = e.currentTarget;
      btn.disabled = true;
      const changed = sel.course_id !== (S.course_id || '') || sel.course_name !== (S.course_name || '') || sel.uni !== (S.uni || '');
      S = { ...S, dest: sel.dest, uni: sel.uni, uni_name: sel.uni_name, course_name: sel.course_name };
      if (sel.course_id) S.course_id = sel.course_id; else delete S.course_id;
      if (sel.group) S.group = sel.group; else delete S.group;
      if (changed) pruneAnswers();
      if (await saveNow()) location.hash = '#story'; else btn.disabled = false;
    };

    // shortlist shortcut
    const short = $('[data-short]', v);
    short.hidden = true;
    Promise.resolve(getSaved ? getSaved() : null).then((items) => {
      const crs = (items || []).filter((i) => i.kind === 'crs').slice(0, 3);
      if (!crs.length) return;
      short.hidden = false;
      $('[data-short-list]', v).replaceChildren(...crs.map((i) => h('li', {}, h('button', {
        type: 'button', class: 'sop-opt',
        on: { click: async () => {
          const slug = String(i.item_id).replace(/^crs:/, '').split('/')[0];
          try {
            const f = await loadUni(slug);
            const c = f.courses.find((x) => x.id === i.item_id);
            if (!c) throw new Error('missing');
            sel = { dest: f.c, uni: f.s, uni_name: f.n, course_id: c.id, course_name: c.n, group: c.g || '' };
            await ensureIndex(); uniFile = f;
            for (const r of dests.querySelectorAll('input')) r.checked = r.value === sel.dest;
            paint();
          } catch { say('We could not find that course. Pick it below.', 'bad'); }
        } },
      }, h('b', { text: i.title }), h('span', { text: i.sub || '' })))));
    }).catch(() => {});

    async function ensureIndex() { try { await loadIndex(); } catch { /* the list below says so */ } }
    ensureIndex().then(() => { paint(); if (sel.uni) loadCourses(); });
    paint();
  }

  // The destination and subject area decide which roles are offered, so a course change drops answers that no longer fit.
  function pruneAnswers() {
    if (!S.picks) return;
    const q5 = questions(ctx())[4].chips.map((c) => c.id);
    if (S.picks.q5) { S.picks.q5 = S.picks.q5.filter((id) => q5.includes(id)); if (!S.picks.q5.length) delete S.picks.q5; }
    if (!Object.keys(S.picks).length) delete S.picks;
  }

  // ---- 3. story -----------------------------------------------------------------------------------------------
  function renderStory() {
    const v = view('story');
    $('[data-for]', v).textContent = forText();
    const qs = questions(ctx());
    S.picks = S.picks || {};
    S.notes = S.notes || {};

    const refresh = () => {
      const n = answered(S);
      $('[data-done-text]', v).textContent = `${n} of 7 answered`;
      $('[data-bar]', v).style.width = `${Math.round((n / 7) * 100)}%`;
      $('[data-make]', v).disabled = !answersDone(S);
      for (const q of qs) {
        const cur = S.picks[q.id] || [];
        const el = v.querySelector(`[data-q="${q.id}"]`);
        const c = $('.sop-count', el);
        c.textContent = `${cur.length} of ${q.max} chosen`;
        c.classList.toggle('is-ok', cur.length > 0);
        for (const box of el.querySelectorAll('input[type=checkbox]')) box.disabled = !box.checked && cur.length >= q.max;
      }
      // how much the answers and the profile can fill, against the length the student is aiming for
      const target = aimWords();
      const lower = S.limit && S.limit < wordsTarget(S) ? `The university's limit is ${S.limit} words, so we aim for that. ` : '';
      const have = wordCount(draftText(buildDraft(S, ctx(), [])));
      $('[data-meter]', v).textContent = lower + (have >= target * 0.9
        ? `Your answers and profile already make about ${have} words of draft, enough for the length you chose.`
        : `Your answers and profile make about ${have} words of draft so far. For about ${target} words, add two or three sentences of your own under the questions, most of all questions 2 and 4.`);
      const tc = $('[data-tone-count]', v);
      tc.textContent = S.tone ? '1 of 1 chosen' : '0 of 1 chosen';
      tc.classList.toggle('is-ok', !!S.tone);
    };

    $('[data-qs]', v).replaceChildren(...qs.map((q, i) => {
      const cur = () => S.picks[q.id] || [];
      const set = (arr) => { if (arr.length) S.picks[q.id] = arr; else delete S.picks[q.id]; };
      const chips = q.chips.map((c) => h('label', { class: 'st-chip' },
        h('input', { type: 'checkbox', value: c.id, props: { checked: cur().includes(c.id) }, on: { change: (e) => {
          let arr = cur().filter((x) => x !== c.id);
          if (e.target.checked) {
            if (q.id === 'q3') arr = c.id === 'none' ? [] : arr.filter((x) => x !== 'none');
            arr.push(c.id);
          }
          set(arr);
          if (q.id === 'q3') for (const box of e.target.closest('fieldset').querySelectorAll('input[type=checkbox]')) box.checked = arr.includes(box.value);
          refresh(); queueSave();
        } } }),
        h('span', { text: c.own ? `${c.text} (profile)` : c.text })));
      const noteId = `sop-note-${q.id}`;
      const counter = h('small', { class: 'sop-chars', text: `${(S.notes[q.id] || '').length}/${NOTE_MAX}` });
      return h('div', { class: 'st-card sop-q', 'data-q': q.id },
        h('fieldset', { class: 'st-q' },
          h('legend', { text: `${i + 1}. ${q.title}` }),
          h('p', { class: 'sop-hint' }, q.hint + ' ', h('b', { class: 'sop-count' })),
          h('div', { class: 'st-chips' }, chips)),
        h('label', { class: 'sop-lab', for: noteId, text: 'Add a few words of your own (optional)' }),
        h('textarea', { id: noteId, class: 'sop-note', rows: 3, maxlength: String(NOTE_MAX), placeholder: q.placeholder, props: { value: S.notes[q.id] || '' }, on: { input: (e) => {
          const t = e.target.value.replace(/\s+/g, ' ').trim();
          if (t) S.notes[q.id] = e.target.value.slice(0, NOTE_MAX); else delete S.notes[q.id];
          counter.textContent = `${e.target.value.length}/${NOTE_MAX}`;
          queueSave();
        } } }),
        counter);
    }));

    $('[data-tones]', v).replaceChildren(...TONES.map(([id, name, sample]) => h('label', { class: 'sop-tone' },
      h('input', { type: 'radio', name: 'sop-tone', value: id, props: { checked: S.tone === id }, on: { change: () => { S.tone = id; refresh(); queueSave(); } } }),
      h('span', {}, h('b', { text: name }), h('i', { text: `“${sample}”` })))));

    $('[data-lengths]', v).replaceChildren(...WORDS.map((n) => h('label', { class: 'st-chip' },
      h('input', { type: 'radio', name: 'sop-words', value: String(n), props: { checked: wordsTarget(S) === n }, on: { change: () => { S.words = n; refresh(); queueSave(); } } }),
      h('span', { text: `About ${n} words` }))));
    const limitBox = $('[data-limit]', v), limitMsg = $('[data-limit-msg]', v);
    limitBox.value = S.limit || '';
    limitBox.oninput = () => {
      const raw = limitBox.value.trim();
      const n = Number(raw);
      if (!raw) { delete S.limit; limitMsg.textContent = ''; }
      else if (Number.isInteger(n) && n >= LIMIT_MIN && n <= LIMIT_MAX) { S.limit = n; limitMsg.textContent = ''; }
      else { delete S.limit; limitMsg.textContent = `Enter a whole number from ${LIMIT_MIN} to ${LIMIT_MAX}, or leave it empty.`; }
      refresh();
      queueSave();
    };

    $('[data-make]', v).onclick = async (e) => {
      e.currentTarget.disabled = true;
      cleanNotes();
      if (await saveNow()) location.hash = '#draft'; else refresh();
    };
    refresh();
  }
  function cleanNotes() {
    for (const k of Object.keys(S.notes || {})) if (!S.notes[k].trim()) delete S.notes[k];
    if (S.notes && !Object.keys(S.notes).length) delete S.notes;
    if (S.picks && !Object.keys(S.picks).length) delete S.picks;
  }

  // ---- 4. draft -----------------------------------------------------------------------------------------------
  let editing = false;
  async function renderDraft() {
    const v = view('draft');
    editing = false;
    $('[data-for]', v).textContent = forText();
    cleanNotes();
    let file = null;
    try { file = await loadUni(S.uni); } catch { /* the draft is then written without course facts */ }
    if (current !== 'draft') return;
    const rec = file && S.course_id ? file.courses.find((c) => c.id === S.course_id) : null;
    const card = rec ? { course: { duration: rec.d, months: rec.m, ielts: rec.ie, src: rec.u, on: rec.on } } : null;
    const facts = factsFor(card, sections);
    const paras = buildDraft(S, ctx(), facts);
    const generated = draftText(paras);
    const text = () => S.edited || generated;

    $('[data-sub]', v).textContent = card
      ? 'Built from your answers and the checked facts for this course. Review every line, fill the gaps and make it your own.'
      : 'Built from your answers. We have no checked facts for this course, so the course lines show gaps for you to fill from the university\'s page.';

    // opening
    $('[data-arcs]', v).replaceChildren(...ARCS.map(([id, name, hint], i) => h('label', { class: 'sop-arc' },
      h('input', { type: 'radio', name: 'sop-arc', value: id, props: { checked: (S.arc || 0) === i }, on: { change: async () => { S.arc = i; queueSave(); renderDraft(); } } }),
      h('span', {}, h('b', { text: name }), h('small', { text: hint })))));
    const tone = TONES.find((t) => t[0] === S.tone);
    $('[data-voice]', v).textContent = tone ? `Voice you chose: ${tone[1]}. Writing in that voice is the next update. For now the draft keeps your own words and uses short, plain sentences.` : '';

    // facts and checks
    const hot = new Set();
    const paint = () => {
      for (const s of v.querySelectorAll('.sop-s[data-f]')) s.classList.toggle('is-hot', s.dataset.f.split(' ').some((id) => hot.has(id)));
      for (const b of v.querySelectorAll('.sop-fact')) b.setAttribute('aria-pressed', String(hot.has(b.dataset.id)));
    };
    const toggle = (id) => { if (hot.has(id)) hot.delete(id); else { hot.clear(); hot.add(id); } paint(); };
    $('[data-facts]', v).replaceChildren(...facts.map((f) => h('li', {},
      h('button', { type: 'button', class: 'sop-fact' + (f.own ? ' is-own' : ''), 'data-id': f.id, 'aria-pressed': 'false', on: { click: () => toggle(f.id) } },
        h('span', { class: 'sop-fact-top' }, h('b', { text: f.label }), h('em', { class: 'sop-chip' + (f.soon ? ' is-soon' : '') + (f.own ? ' is-own' : ''), text: f.chip })),
        h('span', { class: 'sop-fact-val', text: f.value }),
        h('small', { text: f.checked })),
      f.sourceUrl ? h('a', { class: 'sop-src', href: f.sourceUrl, target: '_blank', rel: 'noopener nofollow', text: f.source || 'Source page' }) : h('span', { class: 'sop-src', text: f.source }))));
    $('[data-facts-sub]', v).textContent = facts.length ? 'Tap a fact to see where it is used.' : 'No checked facts for this course yet.';

    const aim = aimWords();
    const lengthRows = () => {
      const n = wordCount(text());
      const rows = [['Length', `${n} of about ${aim} words`]];
      if (S.limit) rows.push(['University limit', n > S.limit ? `${n - S.limit} words over` : `${S.limit - n} words to spare`]);
      return rows;
    };
    const renderChecks = () => {
      const c = checks(paras, facts);
      const edited = !!S.edited;
      const gaps = edited ? (S.edited.match(GAP_RX) || []).length : c.gaps;
      const rows = edited
        ? [...lengthRows(), ['Gaps left to fill', gaps], ['Your edits', 'Saved in your account']]
        : [...lengthRows(), ['Checked facts in this draft', c.factsUsed], ['Not due for a re-check', `${c.factsFresh} of ${c.factsUsed}`], ['Your own statements (not verified)', c.own], ['Gaps for you to fill', c.gaps]];
      $('[data-checks]', v).replaceChildren(...rows.map(([k, val]) => h('li', {}, h('span', { text: k }), h('b', { text: String(val) }))));
    };

    // the paper
    const paper = $('[data-paper]', v), ta = $('[data-edit]', v), toggleBtn = $('[data-edit-toggle]', v), restore = $('[data-restore]', v), note = $('[data-edited-note]', v);
    const dl = $('[data-download]', v), review = $('[data-review]', v);
    const draw = () => {
      const t = text();
      const n = wordCount(t);
      $('[data-words]', v).textContent = `${n} words`;
      const len = $('[data-len]', v);
      const over = S.limit && n > S.limit;
      len.classList.toggle('is-bad', !!over);
      len.textContent = over
        ? `This is ${n - S.limit} words over the university's limit of ${S.limit}. Trim it before you submit.`
        : `You are aiming for about ${aim} words${S.limit && S.limit < wordsTarget(S) ? ', the university\'s limit' : ''}. Writing to this length comes in the next update. For now the draft is as long as your answers and profile make it${n < aim * 0.9 ? `, so add detail in your own words or under the questions to get closer` : ''}.`;
      if (S.edited) {
        paper.replaceChildren(...S.edited.split(/\n{2,}/).map((p) => h('p', {}, ...p.split(/(\[[^\]\n]+\])/).map((bit) => (HAS_GAP.test(bit) ? h('span', { class: 'sop-s sop-s-g', text: bit }) : bit)))));
        note.hidden = false;
        note.textContent = 'You edited this draft. Colours are off for edited text. Changing the opening or your answers does not change it until you rebuild.';
        restore.hidden = false;
      } else {
        paper.replaceChildren(...paras.map((p) => h('p', {}, ...p.items.flatMap((s, i) => [i ? ' ' : '', h('span', { class: `sop-s sop-s-${s.k}`, 'data-f': s.f.join(' ') || undefined, text: s.t })]))));
        note.hidden = true;
        restore.hidden = true;
      }
      renderChecks();
      paint();
    };
    draw();

    toggleBtn.textContent = 'Edit in my own words';
    toggleBtn.onclick = async () => {
      if (!editing) {
        editing = true;
        ta.value = text();
        paper.hidden = true; ta.hidden = false; $('[data-edit-label]', v).hidden = false;
        toggleBtn.textContent = 'Done editing';
        ta.focus();
      } else {
        editing = false;
        const t = ta.value.replace(/\r\n?/g, '\n').trim();
        if (!t || t === generated) delete S.edited; else S.edited = t;
        paper.hidden = false; ta.hidden = true; $('[data-edit-label]', v).hidden = true;
        toggleBtn.textContent = 'Edit in my own words';
        draw();
        if (await saveNow()) say('Saved', 'ok');
      }
    };
    let armed = null;
    restore.onclick = async () => {
      if (!armed) { restore.textContent = 'Click again to replace your edits'; armed = setTimeout(() => { armed = null; restore.textContent = 'Rebuild from my answers'; }, 4000); return; }
      clearTimeout(armed); armed = null; restore.textContent = 'Rebuild from my answers';
      delete S.edited;
      draw();
      if (await saveNow()) say('Saved', 'ok');
    };

    review.checked = false;
    dl.disabled = true;
    review.onchange = () => { dl.disabled = !review.checked; };
    dl.onclick = () => {
      const t = (editing ? ta.value : text()).trim();
      if (HAS_GAP.test(t)) { say('Fill the [gaps] first, or delete them if you do not need them.', 'bad'); return; }
      const url = URL.createObjectURL(new Blob([t + '\n'], { type: 'text/plain;charset=utf-8' }));
      const a = h('a', { href: url, download: `sop-${S.uni || 'draft'}.txt` });
      document.body.append(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      say('Downloaded', 'ok');
    };
  }

  window.addEventListener('hashchange', route);
  route();
}
