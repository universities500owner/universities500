// Subjects for course search. Plain functions with no site imports, so the build, the browser and the tests can all use them.
// A course gets a subject when its name or degree title contains one of the subject's words (see src/data/subjects.json).
// There is no AI and no guessing: a course that matches nothing has no subject and still shows under "all subjects".

export const norm = (s) => String(s == null ? '' : s)
  .toLowerCase()
  .normalize('NFD').replace(/[̀-ͯ]/g, '')
  .replace(/['’‘`]/g, '')
  .replace(/&/g, ' and ')
  .replace(/[^a-z0-9]+/g, ' ')
  .trim();

const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
// A word matches from its start ("nurs" finds nursing). A word ending in ! must match the whole word ("law!" does not find lawn).
const fragment = (p) => {
  const whole = p.endsWith('!');
  const w = norm(whole ? p.slice(0, -1) : p);
  return w ? esc(w) + (whole ? '\\b' : '') : '';
};
const regex = (list) => {
  const parts = (list || []).map(fragment).filter(Boolean);
  return parts.length ? new RegExp('\\b(?:' + parts.join('|') + ')') : null;
};

// What a visitor can type to name a subject: its full name, its first part ("nursing" for "Nursing and midwifery"), and the words in "also".
export const aliasOf = (name, also) => [...new Set([norm(name), norm(name.split(/ and |, | \(/)[0]), ...(also || []).map(norm)])];

// Subjects as the browser gets them: [id, name, also] with no matching words. Enough to name a subject, not to place a course in one.
export const compileLite = (list) => ({
  subjects: list.map(([id, name, also], index) => ({ id, name, index, alias: aliasOf(name, also) })),
});

// Turn the JSON definition into ready-to-use subjects. Order is kept.
export function compile(def) {
  const subjects = def.subjects.map((s, index) => ({
    index,
    id: s.id,
    name: s.name,
    group: s.group,
    includes: s.includes || [],
    also: s.also || [],
    any: regex(s.any),
    not: regex(s.not),
    key: norm(s.name),
    alias: aliasOf(s.name, s.also),
  }));
  const byId = new Map(subjects.map((s) => [s.id, s]));
  return { subjects, byId, groups: def.groups };
}

// Some course pages were saved with the university's name as the course name, but their own web address names the course
// (".../courses/accounting-finance-bsc"). That address is part of the course's source, so it can be read for subject words.
export function hintFromUrl(url) {
  let parts;
  try { parts = new URL(url).pathname.split('/').filter(Boolean); } catch { return ''; }
  while (parts.length > 1 && /(?:^|-)(?:19|20)\d\d(?:$|-)/.test(parts[parts.length - 1])) parts.pop();
  return parts.length ? norm(parts[parts.length - 1]) : '';
}

// A degree title that names its field ("Master of Nursing") helps. An abbreviation like "MBA" or "MSc" is not used: scraped
// pages about an MBA programme (class profile, awards) carry it, and they are not courses in that subject.
const namesField = (degree) => /^(?:master|bachelor|doctor|graduate|postgraduate|undergraduate)\b.*\b(?:of|in)\b/i.test(degree || '');

// Which subjects a course belongs to. Returns subject ids. A subject that "includes" others also covers what they cover.
// course: { name, degree, url }. The web address is read only when the name is just the university's own name (uniName).
export function subjectsOf(compiled, course, uniName) {
  const sameAsUni = uniName && norm(course.name) === norm(uniName);
  const text = norm(`${course.name || ''} ${namesField(course.degree) ? course.degree : ''} ${sameAsUni ? hintFromUrl(course.url) : ''}`);
  const own = new Set();
  for (const s of compiled.subjects) {
    if (s.any && s.any.test(text) && !(s.not && s.not.test(text))) own.add(s.id);
  }
  const all = new Set(own);
  for (const s of compiled.subjects) {
    if (s.includes.some((id) => own.has(id) || all.has(id))) all.add(s.id);
  }
  return compiled.subjects.filter((s) => all.has(s.id)).map((s) => s.id);
}

// The subject a typed phrase names exactly (its name, or one of the words in "also"). null if it does not name one.
export function exactSubject(compiled, text) {
  const t = norm(text);
  if (!t) return null;
  return compiled.subjects.find((s) => s.alias.includes(t)) || null;
}

// Subjects whose name or alias starts with what was typed, or has a word that does. Best first.
export function suggestSubjects(compiled, text, limit = 8) {
  const t = norm(text);
  if (!t) return [];
  const scored = [];
  for (const s of compiled.subjects) {
    let best = 0;
    for (const a of s.alias) {
      if (a === t) best = Math.max(best, 4);
      else if (a.startsWith(t)) best = Math.max(best, 3);
      else if (a.split(' ').some((w) => w.startsWith(t))) best = Math.max(best, 2);
      else if (t.length >= 3 && a.includes(t)) best = Math.max(best, 1);
    }
    if (best) scored.push([best, s]);
  }
  return scored.sort((a, b) => b[0] - a[0] || a[1].index - b[1].index).slice(0, limit).map(([, s]) => s);
}
