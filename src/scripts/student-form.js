// Draws a profile section's form from its description in src/lib/account/schema.js, and reads it back.
// Nothing a student typed is ever put into the page as HTML: values go in through .value and .textContent only.
import { SECTIONS } from '../lib/account/schema.js';

function el(tag, attrs, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k === 'class') n.className = v;
    else if (k === 'text') n.textContent = v;
    else n.setAttribute(k, v === true ? '' : v);
  }
  for (const k of kids) if (k) n.append(k);
  return n;
}

const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

// One input for one field, plus its label, hint and (empty) error line.
function fieldRow(f, id, path, value) {
  if (f.type === 'check') {
    const box = el('input', { type: 'checkbox', id, 'data-key': f.id });
    box.checked = value === true;
    const row = el('div', { class: 'f', 'data-path': path, 'data-field': f.id }, el('label', { class: 'st-chk', for: id }, box, el('span', { text: f.label })));
    return row;
  }
  let input;
  if (f.type === 'select') {
    input = el('select', { id });
    input.append(el('option', { value: '', text: 'Choose…' }));
    for (const [v, l] of f.options) input.append(el('option', { value: v, text: l }));
  } else if (f.type === 'number' || f.type === 'year') {
    input = el('input', { id, type: 'number', inputmode: f.type === 'year' || f.int ? 'numeric' : 'decimal', step: f.type === 'number' && !f.int ? 'any' : '1', min: f.min, max: f.max });
  } else if (f.type === 'month') {
    input = el('input', { id, type: 'month', placeholder: 'YYYY-MM', pattern: '\\d{4}-\\d{2}' });
  } else {
    input = el('input', { id, type: 'text', maxlength: f.max, autocomplete: f.autocomplete || 'off', placeholder: f.placeholder });
  }
  input.setAttribute('data-key', f.id);
  input.setAttribute('aria-describedby', `${id}-err`);
  if (value !== undefined && value !== null) input.value = String(value);
  return el('div', { class: 'f' + (f.type === 'text' && f.max > 100 ? ' wide' : ''), 'data-path': path, 'data-field': f.id },
    el('label', { for: id, text: f.label }),
    input,
    f.hint ? el('p', { class: 'hint', text: f.hint }) : null,
    el('p', { class: 'ct-err', id: `${id}-err`, hidden: true }));
}

const readControl = (row) => {
  const c = row.querySelector('[data-key]');
  if (!c) return undefined;
  return c.type === 'checkbox' ? c.checked : c.value;
};

// Builds the form for section `name` inside `host` and returns { collect, showErrors }.
export function renderSection(host, name, data) {
  const spec = SECTIONS[name];
  const flat = el('div', { class: 'st-grid' });
  const rows = [];
  let group = null;
  for (const f of spec.fields) {
    if (f.group && f.group !== group) { group = f.group; flat.append(el('h3', { class: 'st-group', text: group })); }
    const row = fieldRow(f, `${name}-${f.id}`, f.id, data[f.id]);
    row.__f = f;
    rows.push(row);
    if (f.type === 'check') row.classList.add('wide');
    flat.append(row);
  }
  host.replaceChildren();
  if (spec.fields.length) host.append(flat);

  let listBox = null, entriesBox = null, addBtn = null;
  const listSpec = spec.list;
  const entryRows = (i) => [...entriesBox.children[i].querySelectorAll('.f')];

  const values = () => {
    const out = {};
    for (const row of rows) out[row.__f.id] = readControl(row);
    return out;
  };
  const itemValues = (entry) => {
    const out = {};
    for (const row of entry.querySelectorAll('.f')) out[row.getAttribute('data-field')] = readControl(row);
    return out;
  };

  function refresh() {
    const v = values();
    for (const row of rows) row.hidden = !!(row.__f.show && !row.__f.show(v));
    if (listSpec) {
      listBox.hidden = !!(listSpec.show && !listSpec.show(v));
      for (const entry of entriesBox.children) {
        const iv = itemValues(entry);
        for (const row of entry.querySelectorAll('.f')) {
          const f = row.__f;
          row.hidden = !!(f.show && !f.show(iv));
        }
      }
      addBtn.hidden = entriesBox.children.length >= listSpec.max;
    }
  }

  function addEntry(item) {
    const i = entriesBox.children.length;
    const entry = el('fieldset', { class: 'st-entry' });
    const rm = el('button', { type: 'button', class: 'st-link', text: 'Remove' });
    rm.setAttribute('aria-label', `Remove ${listSpec.noun} ${i + 1}`);
    entry.append(el('div', { class: 'st-entry-head' }, el('span', { text: `${cap(listSpec.noun)} ${i + 1}` }), rm));
    const grid = el('div', { class: 'st-grid' });
    for (const f of listSpec.fields) {
      const row = fieldRow(f, `${name}-${listSpec.key}-${i}-${f.id}`, `${listSpec.key}.${i}.${f.id}`, item[f.id]);
      row.__f = f;
      grid.append(row);
    }
    entry.append(grid);
    entriesBox.append(entry);
    rm.addEventListener('click', () => {
      const keep = [...entriesBox.children].map(itemValues);
      keep.splice([...entriesBox.children].indexOf(entry), 1);
      entriesBox.replaceChildren();
      keep.forEach(addEntry);
      refresh();
      (entriesBox.querySelector('input,select') || addBtn).focus();
    });
  }

  if (listSpec) {
    listBox = el('div', { class: 'st-list' });
    entriesBox = el('div', { class: 'st-entries' });
    addBtn = el('button', { type: 'button', class: 'btn ghost', text: listSpec.addLabel });
    listBox.append(entriesBox, addBtn);
    host.append(listBox);
    (Array.isArray(data[listSpec.key]) ? data[listSpec.key] : []).forEach(addEntry);
    addBtn.addEventListener('click', () => {
      addEntry({});
      refresh();
      const last = entriesBox.lastElementChild;
      last.querySelector('input,select').focus();
    });
  }

  host.addEventListener('input', refresh);
  host.addEventListener('change', refresh);
  refresh();

  function clearErrors() {
    host.querySelectorAll('.ct-err').forEach((p) => { p.hidden = true; p.textContent = ''; });
    host.querySelectorAll('[aria-invalid]').forEach((c) => c.removeAttribute('aria-invalid'));
  }

  return {
    collect() {
      const out = values();
      if (listSpec) out[listSpec.key] = [...entriesBox.children].map(itemValues);
      return out;
    },
    // errors: { "full_name": "Enter…", "items.0.grade": "…" }. Returns the messages it could not place on a field.
    showErrors(errors) {
      clearErrors();
      const loose = [];
      let first = null;
      for (const [path, msg] of Object.entries(errors || {})) {
        const row = [...host.querySelectorAll('.f')].find((r) => r.getAttribute('data-path') === path);
        if (!row) { loose.push(msg); continue; }
        const p = row.querySelector('.ct-err');
        if (p) { p.textContent = msg; p.hidden = false; }
        const c = row.querySelector('[data-key]');
        if (c) { c.setAttribute('aria-invalid', 'true'); first = first || c; }
      }
      if (first) first.focus();
      return loose;
    },
    clearErrors,
  };
}
