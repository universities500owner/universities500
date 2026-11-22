// A guard on what the course reader copied. Pure, so tests/courseGuard.test.mjs can run it without the site.
// Checked against official pages on 22 Nov 2026: about 3 in 10 sampled courses had a wrong fee, length or level.
// It only ever removes a value, so the page says "Check the official page" instead of showing a wrong one. The reader itself still needs the same fixes.
//  - a fee whose sentence is a deposit, a scholarship, an award or a per-credit price is not the course fee
//  - a length taken from a part-time sentence, "the first three years" or a credit count is not the course length
//  - a Scottish "MA (Honours)" is a four-year first degree, not a Master's
const FEE_NOT = /deposit|in advance|application fee|registration|per credit|per module|per unit|accommodation|visa|non-refundable|insurance|surcharge|bursary|scholarship|\baward\b|discount|reduction/i;
const LENGTH_NOT = /part[- ]time|first (?:two|three|four|five|\d) years?|in the first|years? (?:of|in) (?:industry|placement|abroad)|per year|credits?\b/i;
const MA_HONS = /\bMA\s*\(?(?:hons|honours)/i;
export function guard(i) {
  const o = { ...i };
  if (o.fee && FEE_NOT.test(o.fee.context || '')) o.fee = null;
  if (o.duration) {
    const c = o.duration.context || '';
    const n = String(o.duration.years ?? '').replace(/\.0$/, '');
    const fullTime = new RegExp(`\\b${n}\\s*years?\\s*(?:of\\s*)?full[- ]time`, 'i').test(c);       // "1 year full-time" backs a length of 1 year
    if (LENGTH_NOT.test(c) && !fullTime) o.duration = null;
  }
  if (MA_HONS.test(o.name || '')) { o.level = 'Bachelor'; o.duration = null; }
  return o;
}
