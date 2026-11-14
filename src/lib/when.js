// Dates and status, shared by the pages (at build time) and the list scripts (in the browser).
// No data is imported here, so it is safe to load in the browser.

const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
export function fmtIso(iso) {
  if (!iso) return '';
  const [y, m, d] = iso.split('-').map(Number);
  return `${d} ${MON[m - 1]} ${y}`;
}

const DAY = 86400000;
export const daysBetween = (fromIso, toIso) => Math.round((Date.parse(toIso) - Date.parse(fromIso)) / DAY);

// "3 days", "2 weeks", "1 month". Whole numbers only, rounded.
export function span(n) {
  if (n < 14) return n === 1 ? '1 day' : `${n} days`;
  if (n < 30) return `${Math.round(n / 7)} weeks`;
  if (n >= 730) return `${Math.floor(n / 365)} years`;
  const m = Math.round(n / 30);
  return m === 1 ? '1 month' : `${m} months`;
}

// Open, closed, yet to open, or unknown. Decided only from dates found on the official page.
export function statusOf(it, todayIso = new Date().toISOString().slice(0, 10)) {
  const { deadline, opens, rolling } = it;
  if (deadline && todayIso > deadline) return 'closed';
  if (opens && todayIso < opens) return 'upcoming';
  if (deadline) return 'open';
  if (rolling) return 'open';
  return 'unknown';
}
export const STATUS_LABEL = { open: 'Open', closed: 'Closed', upcoming: 'Yet to open', unknown: 'Check the official page' };

export function statusNote(it, st) {
  if (st === 'open') return it.deadline ? `Closes ${fmtIso(it.deadline)}` : 'No fixed deadline stated';
  if (st === 'closed') return `Closed ${fmtIso(it.deadline)}. Check the official page for the next round.`;
  if (st === 'upcoming') return `Opens ${fmtIso(it.opens)}`;
  return it.deadlinePartial ? `Deadline ${it.deadlinePartial} (year not stated)` : 'No dates found on the page';
}

// The short line on a result card, like "Closing in 1 month".
export function closingText(deadlineIso, todayIso) {
  const n = daysBetween(todayIso, deadlineIso);
  if (n < 0) return 'Closed';
  if (n > 365) return `Closes ${fmtIso(deadlineIso)}`; // a date this far off reads better as a date
  if (n === 0) return 'Closes today';
  if (n === 1) return 'Closes tomorrow';
  return `Closing in ${span(n)}`;
}

// Scholarship card: the label for the status pill. Only dates from the official page are used.
export function scholarshipPill(it, st, todayIso) {
  if (st === 'open') return it.deadline ? closingText(it.deadline, todayIso) : 'Open, no fixed deadline';
  if (st === 'upcoming') return `Opens in ${span(Math.max(daysBetween(todayIso, it.opens), 1))}`;
  if (st === 'closed') return 'Closed';
  return STATUS_LABEL.unknown;
}

// Internship card: a closing date if the feed gave one, otherwise how long ago it was posted.
// `posted` is false when we only know when we first saw it.
export function internshipPill(deadlineIso, dateIso, posted, todayIso) {
  if (deadlineIso) {
    const t = closingText(deadlineIso, todayIso);
    return { text: t, tone: t === 'Closed' ? 'closed' : 'open', icon: 'clock' };
  }
  if (!dateIso) return null;
  const n = daysBetween(dateIso, todayIso);
  if (n < 0) return null;
  const ago = n === 0 ? 'today' : n === 1 ? 'yesterday' : `${span(n)} ago`;
  return { text: `${posted ? 'Posted' : 'Added'} ${ago}`, tone: n <= 7 ? 'open' : 'plain', icon: 'clock' };
}
