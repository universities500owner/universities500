import test from 'node:test';
import assert from 'node:assert/strict';
import { speak, blockSpeech, guideClips, articleClips, clipHash, withHashes, resolveListen, MAX_CHARS, GUIDE_CLOSING } from '../src/lib/listen.js';

const CFG = { version: 1, provider: 'elevenlabs', model: 'eleven_multilingual_v2', voiceId: 'VOICE1', format: 'mp3_44100_64', settings: { stability: 0.5 }, audioBase: 'https://audio.example.com/' };
const R = (t, extra = {}) => ({ t, ...extra });

test('speak: currency codes and ranges become words', () => {
  assert.equal(speak('CAD 14,000 to CAD 22,000 per year'), '14,000 to 22,000 Canadian dollars per year');
  assert.equal(speak('AUD 50,500–55,500'), '50,500 to 55,500 Australian dollars');
  assert.equal(speak('CAD 40,000 to CAD 85,000+ per year'), '40,000 to 85,000 Canadian dollars or more per year');
  assert.equal(speak('£12,000 a year'), '12,000 pounds a year');
  assert.equal(speak('GBP 100 or USD 120'), '100 pounds or 120 US dollars');
  assert.equal(speak('1,000 Singapore dollars/month'), '1,000 Singapore dollars per month');
});

test('speak: symbols, abbreviations and temperatures', () => {
  assert.equal(speak('Tuition & fees'), 'Tuition and fees');
  assert.equal(speak('Intake 2026–2027'), 'Intake 2026 to 2027');
  assert.equal(speak('25°C to 32°C'), '25 to 32 degrees Celsius');
  assert.equal(speak('Cost = tuition + rent'), 'Cost equals tuition plus rent');
  assert.equal(speak('some costs, e.g. flights'), 'some costs, for example, flights');
  assert.equal(speak('See https://example.com/x for details'), 'See for details');
  assert.equal(speak('Dear Professor [Surname]'), 'Dear Professor Surname');
});

test('blockSpeech: lists, headings, questions and tables read as sentences', () => {
  assert.equal(blockSpeech({ t: 'p', runs: [R('Hello '), R('world', { b: 1 })] }), 'Hello world.');
  assert.equal(blockSpeech({ t: 'h', text: 'Costs' }), 'Costs.');
  assert.equal(
    blockSpeech({ t: 'ul', items: [{ lead: [R('Fees:')], runs: [R(' vary')] }, { runs: [R('Rent.')], sub: [{ runs: [R('Shared is cheaper')] }] }] }),
    'Fees: vary.\nRent. Shared is cheaper.',
  );
  assert.equal(blockSpeech({ t: 'qa', q: 'How much', a: [{ t: 'p', runs: [R('A lot')] }] }), 'How much?\nA lot.');
  const table = { t: 'table', head: [[R('Area')], [R('Fee')], [R('Note')]], rows: [[[R('Business')], [R('AUD 50,000')], [R('Guide')]]] };
  assert.equal(blockSpeech(table), 'Business. Fee: AUD 50,000. Note: Guide.');
  assert.equal(blockSpeech({ t: 'table', head: [[R('City')], [R('Check')]], rows: [[[R('Perth')], [R('Distance')]]] }), 'Perth: Distance.');
  assert.equal(blockSpeech({ t: 'nope' }), '');
});

const GUIDE = {
  slug: 'testland', title: 'Study in Testland', short: 'Testland', stats: [],
  sections: [
    { key: 'overview', title: 'Overview', blocks: [{ t: 'p', runs: [R('Testland is nice.')] }] },
    { key: 'costs', title: 'Costs', blocks: [{ t: 'p', runs: [R('Fees: CAD 1,000.')] }] },
    { key: 'empty', title: 'Nothing here', blocks: [] },
    { key: 'faq', title: 'FAQ’s', blocks: [{ t: 'qa', q: 'Is it nice?', a: [{ t: 'p', runs: [R('Yes.')] }] }] },
  ],
};

test('guideClips: title opens, sections follow, empty sections are skipped, a shared closing ends', () => {
  const c = guideClips(GUIDE);
  assert.deepEqual(c.map((x) => x.id), ['guide:testland#overview', 'guide:testland#costs', 'guide:testland#faq', 'guide:testland#closing']);
  assert.deepEqual(c.map((x) => x.sec), [0, 1, 2, 3]);
  assert.ok(c[0].text.startsWith('Study in Testland.'));
  assert.equal(c[2].title, 'Frequently asked questions');
  assert.ok(c[1].text.includes('1,000 Canadian dollars'));
  assert.equal(c[3].text, GUIDE_CLOSING);
});

const ART = {
  id: 'TST-01', title: 'What it costs', topic: 'visas', destination: 'testland',
  intro: [{ t: 'p', runs: [R('Intro text.')] }], quick: [{ t: 'p', runs: [R('Short answer text.')] }],
  sections: [{ title: 'Tuition', blocks: [{ t: 'p', runs: [R('Pay tuition.')] }] }],
  faq: [{ q: 'Why?', a: [{ t: 'p', runs: [R('Because.')] }] }],
};

test('articleClips: intro with the short answer, sections, questions, and a careful closing for visa topics', () => {
  const c = articleClips(ART);
  assert.deepEqual(c.map((x) => x.id), ['article:TST-01#intro', 'article:TST-01#s1', 'article:TST-01#faq', 'article:TST-01#closing']);
  assert.ok(c[0].text.includes('The short answer.'));
  assert.ok(c[3].text.includes('not immigration or legal advice'));
  assert.ok(!articleClips({ ...ART, topic: 'careers' })[3].text.includes('legal advice'));
  assert.deepEqual(articleClips({ ...ART, hold: true }), []);
});

test('long sections are split between blocks, never past the limit', () => {
  const para = (n) => ({ t: 'p', runs: [R(`${'Word '.repeat(n).trim()}.`)] });
  const g = { slug: 'x', title: 'T', sections: [{ key: 'a', title: 'A', blocks: [para(400), para(400), para(400)] }] };
  const c = guideClips(g, 2200).filter((x) => x.id !== 'guide:x#closing');
  assert.ok(c.length >= 2);
  assert.ok(c.every((x) => x.text.length <= 2200), c.map((x) => x.text.length).join(','));
  assert.deepEqual(new Set(c.map((x) => x.sec)), new Set([c[0].sec]));
  assert.ok(c.map((x) => x.id)[1].endsWith('#a.2'));
  assert.equal(MAX_CHARS, 4500);
});

test('fingerprints change with the text and with the voice, not with anything else', () => {
  const h = clipHash(CFG, 'Hello.');
  assert.equal(h, clipHash(CFG, 'Hello.'));
  assert.notEqual(h, clipHash(CFG, 'Hello!'));
  assert.notEqual(h, clipHash({ ...CFG, voiceId: 'VOICE2' }, 'Hello.'));
  assert.notEqual(h, clipHash({ ...CFG, model: 'eleven_flash_v2_5' }, 'Hello.'));
  assert.notEqual(h, clipHash({ ...CFG, version: 2 }, 'Hello.'));
  assert.equal(h, clipHash({ ...CFG, audioBase: 'https://elsewhere.example.com' }, 'Hello.'));
  assert.match(h, /^[0-9a-f]{24}$/);
});

test('resolveListen: audio is offered only when every clip matches the current text', () => {
  const clips = guideClips(GUIDE);
  const hashed = withHashes(clips, CFG);
  const have = (list) => ({ clips: Object.fromEntries(list.map((c) => [c.hash, { seconds: 60, bytes: 1, chars: 1 }])) });
  const full = resolveListen(clips, have(hashed), CFG);
  assert.equal(full.clips.length, 4);
  assert.equal(full.sections, 4);
  assert.equal(full.minutes, 4);
  assert.equal(full.clips[0].u, `https://audio.example.com/${hashed[0].hash}.mp3`);
  assert.deepEqual([full.clips[0].t, full.clips[0].s, full.clips[0].d], ['Overview', 0, 60]);
  assert.equal(resolveListen(clips, have(hashed.slice(1)), CFG), null, 'one clip missing');
  const edited = guideClips({ ...GUIDE, sections: GUIDE.sections.map((s) => (s.key === 'costs' ? { ...s, blocks: [{ t: 'p', runs: [R('Fees went up.')] }] } : s)) });
  assert.equal(resolveListen(edited, have(hashed), CFG), null, 'text changed since the audio was made');
  assert.equal(resolveListen(clips, have(hashed), { ...CFG, voiceId: '' }), null, 'no voice chosen');
  assert.equal(resolveListen([], have(hashed), CFG), null);
});
