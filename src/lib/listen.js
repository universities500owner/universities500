// Listen: turns a guide or an article into short spoken clips, and says which clips already have audio.
//
// Plain JavaScript that needs only Node, so the site build and the audio generator (scripts/listen/) use the same code.
// It runs at build time only; the browser never loads it.
//
// How "stays current" works: every clip is named after a fingerprint of the exact text it speaks plus the voice settings.
// Change a sentence and its fingerprint changes, so the old audio no longer matches. The page then hides its Listen button
// until the new audio is made. Unchanged clips keep their files, so only what changed is ever voiced again.

import { createHash } from 'node:crypto';

export const GUIDE_CLOSING = 'Fees, visa settings and work rules change often. Check each one on the official government or university site before you rely on it.';
export const ARTICLE_CLOSING = 'Fees, rules and deadlines change. Check the official pages before you act.';
export const ARTICLE_CLOSING_CAREFUL = `${ARTICLE_CLOSING} This is general information, not immigration or legal advice.`;

// ---------- Plain text for speaking ----------

const CURRENCY = {
  CAD: 'Canadian dollars', AUD: 'Australian dollars', USD: 'US dollars', NZD: 'New Zealand dollars', SGD: 'Singapore dollars',
  GBP: 'pounds', EUR: 'euros', INR: 'rupees', MYR: 'Malaysian ringgit', AED: 'UAE dirhams',
  SEK: 'Swedish kronor', NOK: 'Norwegian kroner', CHF: 'Swiss francs',
};
const SYMBOL = { '£': 'pounds', '€': 'euros', '₹': 'rupees' };
const CODES = Object.keys(CURRENCY).join('|');
const NUM = '\\d[\\d,]*(?:\\.\\d+)?';

// Makes written text easier to say. This is deliberately small: the voice model already reads most things well.
export function speak(input) {
  let s = String(input ?? '')
    .replace(/https?:\/\/\S+/g, '')
    .replace(/[  ]/g, ' ')
    .replace(/\s+&\s+/g, ' and ');
  // "CAD 14,000–22,000+" or "CAD 14,000 to CAD 22,000" -> "14,000 to 22,000 Canadian dollars"
  const RANGE = '(?:\\s?[–]\\s?|\\s+to\\s+)';
  s = s.replace(new RegExp(`\\b(${CODES})\\s?(${NUM})(?:${RANGE}(?:(${CODES})\\s?)?(${NUM}))?(\\+)?`, 'g'), (_, code, a, code2, b, plus) => {
    const more = plus ? ' or more' : '';
    if (code2 && code2 !== code) return `${a} ${CURRENCY[code]} to ${b} ${CURRENCY[code2]}${more}`;
    return `${a}${b ? ` to ${b}` : ''} ${CURRENCY[code]}${more}`;
  });
  s = s.replace(new RegExp(`([£€₹])\\s?(${NUM})(?:${RANGE}(?:[£€₹]\\s?)?(${NUM}))?(\\+)?`, 'g'), (_, sym, a, b, plus) =>
    `${a}${b ? ` to ${b}` : ''} ${SYMBOL[sym]}${plus ? ' or more' : ''}`);
  s = s.replace(new RegExp(`\\b(${CODES})\\b`, 'g'), (c) => CURRENCY[c]);
  // Ranges of plain numbers: "2026–2027", "30–60 days".
  s = s.replace(/(\d)\s?–\s?(\d)/g, '$1 to $2');
  s = s
    .replace(/(\d+)\s?°\s?([CF])\s?(?:–|to)\s?(\d+)\s?°\s?\2\b/g, (_, a, u, b) => `${a} to ${b} degrees ${u === 'C' ? 'Celsius' : 'Fahrenheit'}`)
    .replace(/(\d+)\s?°\s?([CF])\b/g, (_, a, u) => `${a} degrees ${u === 'C' ? 'Celsius' : 'Fahrenheit'}`)
    .replace(/\s?\/\s?(month|year|week|day|hour|semester|term|credit)s?\b/gi, ' per $1')
    .replace(/\s=\s/g, ' equals ')
    .replace(/\s×\s/g, ' times ')
    .replace(/\s÷\s/g, ' divided by ')
    .replace(/\s[−]\s/g, ' minus ')
    .replace(/\s\+\s/g, ' plus ')
    .replace(/[\[\]]/g, '')
    .replace(/\be\.g\.,?/gi, 'for example,')
    .replace(/\bi\.e\.,?/gi, 'that is,')
    .replace(/\bvs\.?(?=\s)/gi, 'versus')
    .replace(/\bapprox\.(?=\s)/gi, 'approximately');
  return s.replace(/[ \t]+/g, ' ').replace(/ *\n */g, '\n').trim();
}

const END = /[.!?:;…]["'”’)]*$/;
const sentence = (s) => {
  const t = String(s ?? '').replace(/\s+/g, ' ').trim();
  if (!t) return '';
  const u = t.replace(/[,]+$/, '');
  return END.test(u) ? u : `${u}.`;
};
const runs = (rs = []) => rs.map((r) => (r.br ? ' ' : r.t ?? '')).join('');
const item = (i) => {
  const own = sentence(`${runs(i.lead)} ${runs(i.runs)}`);
  const sub = (i.sub || []).map(item).join(' ');
  return [own, sub].filter(Boolean).join(' ');
};

// One block of a guide or an article -> the sentences to say, or '' when there is nothing to say.
export function blockSpeech(b) {
  if (!b) return '';
  if (b.t === 'p') return sentence(runs(b.runs));
  if (b.t === 'h') return sentence(b.text);
  if (b.t === 'ul' || b.t === 'ol') return b.items.map(item).filter(Boolean).join('\n');
  if (b.t === 'qa') {
    const q = String(b.q ?? '').trim();
    const question = q ? (/[?]$/.test(q) ? q : `${q}?`) : '';
    return [question, ...(b.a || []).map(blockSpeech)].filter(Boolean).join('\n');
  }
  if (b.t === 'callout') return [b.title ? sentence(b.title) : '', ...(b.blocks || []).map(blockSpeech)].filter(Boolean).join('\n');
  if (b.t === 'quote') return (b.blocks || []).map(blockSpeech).filter(Boolean).join('\n');
  if (b.t === 'table') {
    const head = (b.head || []).map(runs);
    return (b.rows || [])
      .map((r) => {
        const cells = r.map(runs);
        if (cells.length === 1) return sentence(cells[0]);
        if (cells.length === 2) return sentence(`${cells[0].replace(/[.:;]+$/, '')}: ${cells[1]}`);
        const [first, ...rest] = cells;
        return [sentence(first), ...rest.map((c, k) => sentence(head[k + 1] ? `${head[k + 1].replace(/[.:;]+$/, '')}: ${c}` : c))].join(' ');
      })
      .filter(Boolean)
      .join('\n');
  }
  return '';
}

// ---------- Splitting a long section into parts ----------

function splitLong(text, max) {
  if (text.length <= max) return [text];
  const out = [];
  let cur = '';
  for (const piece of text.split(/(?<=[.!?])\s+/)) {
    if (cur && cur.length + piece.length + 1 > max) { out.push(cur); cur = ''; }
    cur = cur ? `${cur} ${piece}` : piece;
  }
  if (cur) out.push(cur);
  return out;
}

// Joins a section's block texts into parts no longer than `max` characters, breaking between blocks where it can.
function parts(texts, max) {
  const flat = texts.flatMap((t) => splitLong(t, max));
  const out = [];
  let cur = '';
  for (const t of flat) {
    if (cur && cur.length + t.length + 2 > max) { out.push(cur); cur = ''; }
    cur = cur ? `${cur}\n\n${t}` : t;
  }
  if (cur) out.push(cur);
  return out;
}

// ---------- Pages -> clips ----------

// A section is {key, title, lead?, blocks}. `lead` is spoken before the blocks (usually the heading).
function sectionClips(pageKey, sec, index, max) {
  const texts = [sec.lead ? sentence(sec.lead) : '', ...sec.blocks.map(blockSpeech)].filter(Boolean).map(speak).filter(Boolean);
  if (!texts.length) return [];
  return parts(texts, max).map((text, n) => ({
    id: `${pageKey}#${sec.key}${n ? `.${n + 1}` : ''}`,
    sec: index,
    title: sec.title,
    text,
  }));
}

function build(pageKey, sections, closing, max) {
  const out = [];
  sections.forEach((s) => out.push(...sectionClips(pageKey, s, out.length ? out[out.length - 1].sec + 1 : 0, max)));
  const last = out.length ? out[out.length - 1].sec + 1 : 0;
  if (out.length && closing) out.push({ id: `${pageKey}#closing`, sec: last, title: 'Before you rely on this', text: speak(closing) });
  return out;
}

export const MAX_CHARS = 4500;

// A destination guide (one entry of guides.json).
export function guideClips(g, max = MAX_CHARS) {
  const sections = (g.sections || [])
    .filter((s) => s.blocks && s.blocks.length)
    .map((s) => {
      if (s.key === 'overview') return { key: s.key, title: 'Overview', lead: g.title, blocks: s.blocks };
      if (s.key === 'faq') return { key: s.key, title: 'Frequently asked questions', lead: 'Frequently asked questions', blocks: s.blocks };
      return { key: s.key, title: s.title, lead: s.title, blocks: s.blocks };
    });
  return build(`guide:${g.slug}`, sections, GUIDE_CLOSING, max);
}

// An article (one file of src/data/articles). Articles marked `hold` are not on the site, so they get no audio.
export function articleClips(a, max = MAX_CHARS) {
  if (a.hold) return [];
  const intro = [...(a.intro || [])];
  const quick = (a.quick || []).length ? [{ t: 'h', text: 'The short answer' }, ...a.quick] : [];
  const sections = [{ key: 'intro', title: 'Introduction', lead: a.title, blocks: [...intro, ...quick] }];
  (a.sections || []).forEach((s, i) => sections.push({ key: `s${i + 1}`, title: s.title || 'Section', lead: s.title, blocks: s.blocks || [] }));
  if ((a.faq || []).length) {
    sections.push({ key: 'faq', title: 'Common questions', lead: 'Common questions', blocks: a.faq.map((q) => ({ t: 'qa', q: q.q, a: q.a })) });
  }
  const careful = a.topic === 'visas' || a.topic === 'after-study';
  return build(`article:${a.id}`, sections, careful ? ARTICLE_CLOSING_CAREFUL : ARTICLE_CLOSING, max);
}

// ---------- Fingerprints and the manifest ----------

// Anything that changes how the audio sounds belongs here. Change it and every clip counts as new.
export const voiceKey = (cfg) =>
  [cfg.version ?? 1, cfg.provider, cfg.model, cfg.voiceId, cfg.format, JSON.stringify(cfg.settings ?? {})].join('|');

export const clipHash = (cfg, text) => createHash('sha256').update(`${voiceKey(cfg)}\n${text}`).digest('hex').slice(0, 24);

// Eleven v3 and v4 read bracketed cues such as [warmly] as direction, not words. Older models would say them aloud,
// so the tone cue (config "tonePrefix") is added only for v3/v4 models. It is part of the text, so it is part of the fingerprint.
export const takesTags = (cfg) => /v[34]/i.test(String(cfg.model ?? ''));
export const spokenText = (cfg, text) => (cfg.tonePrefix && takesTags(cfg) ? `${cfg.tonePrefix} ${text}` : text);

export const withHashes = (clips, cfg) =>
  clips.map((c) => {
    const text = spokenText(cfg, c.text);
    return { ...c, text, hash: clipHash(cfg, text) };
  });

// The manifest is { clips: { <hash>: { seconds, bytes, chars } }, usage: { 'YYYY-MM': characters } }.
// Returns the data the player needs, or null when any clip of the page has no audio for its current text.
export function resolveListen(clips, manifest, cfg) {
  if (!cfg.voiceId || !clips.length) return null;
  const have = manifest?.clips || {};
  const list = [];
  let seconds = 0;
  for (const c of withHashes(clips, cfg)) {
    const m = have[c.hash];
    if (!m) return null;
    seconds += m.seconds;
    list.push({ u: `${String(cfg.audioBase).replace(/\/$/, '')}/${c.hash}.mp3`, t: c.title, s: c.sec, d: m.seconds });
  }
  return { clips: list, sections: list[list.length - 1].s + 1, seconds, minutes: Math.max(1, Math.round(seconds / 60)) };
}
