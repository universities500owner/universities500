// "My shortlist": what a student can save, the statuses each kind of item moves through, and the checks that keep
// what is stored tidy. Shared by the server (validation) and the dashboard page (labels).

export const CAP = 200;
export const NOTE_MAX = 500;

export const KINDS = {
  crs: { label: 'Courses', one: 'course' },
  mba: { label: 'MBA programmes', one: 'MBA programme' },
  sch: { label: 'Scholarships', one: 'scholarship' },
  int: { label: 'Internships', one: 'internship' },
};

// The first status is where a newly saved item starts.
export const STATUSES = {
  crs: ['shortlisted', 'preparing', 'applied', 'offer', 'accepted', 'dropped'],
  mba: ['shortlisted', 'preparing', 'applied', 'offer', 'accepted', 'dropped'],
  sch: ['saved', 'applying', 'applied', 'awarded', 'dropped'],
  int: ['saved', 'applying', 'applied', 'offer', 'dropped'],
};

export const STATUS_LABEL = {
  shortlisted: 'Shortlisted',
  saved: 'Saved',
  preparing: 'Preparing documents',
  applying: 'Applying',
  applied: 'Applied',
  offer: 'Offer received',
  accepted: 'Accepted',
  awarded: 'Awarded',
  dropped: 'Not going ahead',
};

export const ID_RE = /^(crs|sch|mba|int):[A-Za-z0-9._~/-]{1,120}$/;
export const kindOf = (id) => String(id).split(':')[0];

const oneLine = (v, max) =>
  String(v ?? '').replace(/[\u0000-\u001f\u007f\u2028\u2029]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, max);

// A link to a page of this site, or (for internships) to the employer's own page.
const cleanUrl = (v) => {
  const s = String(v ?? '').trim();
  if (s.length > 300) return '';
  if (/^\/(?!\/)[A-Za-z0-9._~!$&'()*+,;=:@%/#?-]*$/.test(s)) return s;
  if (/^https:\/\/[A-Za-z0-9.-]+(:\d+)?(\/[^\s"'<>\\]*)?$/.test(s)) return s;
  return '';
};

// An item the student saves. Returns { value } or { error }.
export function cleanItem(input) {
  const it = input && typeof input === 'object' ? input : {};
  const id = String(it.id ?? '');
  if (!ID_RE.test(id)) return { error: 'Unknown item.' };
  const kind = kindOf(id);
  const title = oneLine(it.title, 160) || oneLine(id.split(':')[1].split('/').pop().replace(/[-_]+/g, ' '), 160) || 'Saved item';
  return { value: { item_id: id, kind, title, sub: oneLine(it.sub, 160), url: cleanUrl(it.url), status: STATUSES[kind][0], note: '' } };
}

// A change to a saved item: its status and/or its note.
export function cleanChange(input) {
  const it = input && typeof input === 'object' ? input : {};
  const id = String(it.id ?? '');
  if (!ID_RE.test(id)) return { error: 'Unknown item.' };
  const out = {};
  if (it.status !== undefined) {
    if (!STATUSES[kindOf(id)].includes(it.status)) return { error: 'Choose one of the listed statuses.' };
    out.status = it.status;
  }
  if (it.note !== undefined) {
    const note = String(it.note ?? '').replace(/\r\n?/g, '\n').replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f\u2028\u2029]/g, '').trim();
    if (note.length > NOTE_MAX) return { error: `Keep the note under ${NOTE_MAX} characters.` };
    out.note = note;
  }
  if (!Object.keys(out).length) return { error: 'Nothing to change.' };
  return { id, value: out };
}
