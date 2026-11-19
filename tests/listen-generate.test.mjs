import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { run, plan } from '../scripts/listen/generate.mjs';
import { loadManifest, listenPages } from '../scripts/listen/pages.mjs';
import { elevenlabs, FatalProviderError } from '../scripts/listen/providers.mjs';

const R = (t) => ({ t });
const CFG = { version: 1, provider: 'elevenlabs', model: 'eleven_multilingual_v2', voiceId: 'V1', format: 'mp3_44100_64', bitrateKbps: 64, settings: { stability: 0.5 }, stitch: true, concurrency: 2, monthlyChars: 100000, pricePer1kChars: 0.1, audioBase: 'https://a.example.com' };
const guide = (slug, costs = `Fees in ${slug} are fine.`) => ({
  slug, short: slug, title: `Study in ${slug}`, stats: [],
  sections: [
    { key: 'overview', title: 'Overview', blocks: [{ t: 'p', runs: [R(`${slug} is great.`)] }] },
    { key: 'costs', title: 'Costs', blocks: [{ t: 'p', runs: [R(costs)] }] },
  ],
});

function setup(guides = [guide('aa'), guide('bb')]) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'listen-'));
  fs.mkdirSync(path.join(root, 'src/data/listen'), { recursive: true });
  fs.mkdirSync(path.join(root, 'src/data/articles'), { recursive: true });
  fs.writeFileSync(path.join(root, 'src/data/guides.json'), JSON.stringify(guides));
  fs.writeFileSync(path.join(root, 'src/data/listen/config.json'), JSON.stringify(CFG));
  fs.writeFileSync(path.join(root, 'src/data/listen/manifest.json'), JSON.stringify({ clips: {}, usage: {} }));
  return root;
}
const fake = () => {
  const calls = [];
  const synth = async (x) => { calls.push(x); return Buffer.alloc(8000, 1); }; // 1 second at 64 kbps
  return { synth, calls };
};
const NOW = new Date('2026-11-19T10:00:00Z');
const quiet = () => {};

test('dry run counts and costs but calls nothing and writes nothing', async () => {
  const root = setup();
  const { synth, calls } = fake();
  const r = await run({ root, cfg: CFG, dryRun: true, synth, log: quiet, now: NOW });
  assert.equal(calls.length, 0);
  assert.equal(r.made, 0);
  assert.equal(r.plan.todo.length, 5, '2 guides x (overview + costs) + ONE shared closing');
  assert.ok(r.plan.cost > 0);
  assert.deepEqual(loadManifest(root).clips, {});
});

test('makes every clip once, records it, and a second run has nothing to do', async () => {
  const root = setup();
  const out = path.join(root, 'out');
  const { synth, calls } = fake();
  const r = await run({ root, cfg: CFG, out, synth, log: quiet, now: NOW });
  assert.equal(r.made, 5);
  assert.equal(calls.length, 5);
  const m = loadManifest(root);
  assert.equal(Object.keys(m.clips).length, 5);
  for (const [hash, info] of Object.entries(m.clips)) {
    assert.ok(fs.existsSync(path.join(out, `${hash}.mp3`)));
    assert.equal(info.seconds, 1);
  }
  assert.equal(m.usage['2026-11'], r.chars);
  const again = await run({ root, cfg: CFG, out, synth, log: quiet, now: NOW });
  assert.equal(again.made, 0);
  assert.equal(calls.length, 5);
});

test('changing one sentence makes only that clip again', async () => {
  const root = setup();
  const { synth, calls } = fake();
  await run({ root, cfg: CFG, out: path.join(root, 'o'), synth, log: quiet, now: NOW });
  fs.writeFileSync(path.join(root, 'src/data/guides.json'), JSON.stringify([guide('aa', 'Fees went up.'), guide('bb')]));
  const r = await run({ root, cfg: CFG, out: path.join(root, 'o'), synth, log: quiet, now: NOW });
  assert.equal(r.made, 1);
  assert.ok(calls.at(-1).text.includes('Fees went up.'));
});

test('neighbouring text is passed along for a smooth join', async () => {
  const root = setup([guide('aa')]);
  const { synth, calls } = fake();
  await run({ root, cfg: CFG, out: path.join(root, 'o'), synth, log: quiet, now: NOW, maxClips: 99 });
  const costs = calls.find((c) => c.text.startsWith('Costs.'));
  assert.ok(costs.previousText.includes('aa is great'));
  assert.ok(costs.nextText.includes('Fees, visa settings'));
});

test('the monthly cap stops the run, and the next run carries on', async () => {
  const root = setup();
  const { synth } = fake();
  const o = path.join(root, 'o');
  const first = await run({ root, cfg: CFG, out: o, synth, log: quiet, now: NOW, cap: 100, provider: 'elevenlabs' });
  assert.equal(first.stoppedByCap, true);
  assert.ok(first.made >= 1 && first.made < 5);
  const used = loadManifest(root).usage['2026-11'];
  assert.ok(used <= 100, `spent ${used}`);
  const later = await run({ root, cfg: CFG, out: o, synth, log: quiet, now: new Date('2026-12-02T00:00:00Z'), cap: 100000 });
  assert.equal(first.made + later.made, 5);
  assert.equal(loadManifest(root).usage['2026-12'], later.chars, 'a new month counts from zero');
});

test('a refused key stops everything at once and keeps what was already saved', async () => {
  const root = setup();
  let n = 0;
  const synth = async () => { if (++n === 3) throw new FatalProviderError('bad key'); return Buffer.alloc(8000, 1); };
  await assert.rejects(run({ root, cfg: CFG, out: path.join(root, 'o'), synth, log: quiet, now: NOW }), /bad key/);
  const kept = Object.keys(loadManifest(root).clips).length;
  assert.ok(kept >= 1 && kept < 5, `kept ${kept}`);
});

test('one clip failing does not stop the others', async () => {
  const root = setup();
  const synth = async ({ text }) => { if (text.startsWith('Costs.')) throw new Error('HTTP 422'); return Buffer.alloc(8000, 1); };
  const r = await run({ root, cfg: CFG, out: path.join(root, 'o'), synth, log: quiet, now: NOW });
  assert.equal(r.failed, 2);
  assert.equal(r.made, 3);
});

test('--only limits the run to the pages asked for', async () => {
  const root = setup();
  const p = plan({ cfg: CFG, manifest: loadManifest(root), pages: listenPages(CFG, root), only: ['guide:bb'] });
  assert.equal(p.perPage.length, 1);
  assert.equal(p.todo.length, 3);
});

// ---- the ElevenLabs request ----

const okRes = (n = 9000) => new Response(Buffer.alloc(n, 1), { status: 200 });
test('ElevenLabs: sends the key, voice, format and neighbouring text', async () => {
  const seen = [];
  const synth = elevenlabs({ apiKey: 'sk_test', cfg: CFG, fetchImpl: async (u, i) => { seen.push({ u, i }); return okRes(); } });
  const buf = await synth({ text: 'Hello there.', previousText: 'Before.', nextText: 'After.' });
  assert.equal(buf.length, 9000);
  assert.equal(seen[0].u, 'https://api.elevenlabs.io/v1/text-to-speech/V1?output_format=mp3_44100_64');
  assert.equal(seen[0].i.headers['xi-api-key'], 'sk_test');
  const body = JSON.parse(seen[0].i.body);
  assert.deepEqual([body.text, body.model_id, body.previous_text, body.next_text], ['Hello there.', 'eleven_multilingual_v2', 'Before.', 'After.']);
  assert.deepEqual(body.voice_settings, { stability: 0.5 });
});

test('ElevenLabs: v3 and v4 models are sent without neighbouring text', async () => {
  let body;
  const synth = elevenlabs({ apiKey: 'k', cfg: { ...CFG, model: 'eleven_v4' }, fetchImpl: async (u, i) => { body = JSON.parse(i.body); return okRes(); } });
  await synth({ text: 'Hi.', previousText: 'a', nextText: 'b' });
  assert.equal(body.previous_text, undefined);
  assert.equal(body.next_text, undefined);
});

test('ElevenLabs: waits and tries again when busy, and gives up on a refused key', async () => {
  let n = 0;
  const waits = [];
  const busy = elevenlabs({ apiKey: 'k', cfg: CFG, sleep: async (ms) => waits.push(ms), fetchImpl: async () => (++n < 3 ? new Response('{"detail":{"status":"too_many_concurrent_requests"}}', { status: 429 }) : okRes()) });
  assert.equal((await busy({ text: 'Hi.' })).length, 9000);
  assert.equal(n, 3);
  assert.equal(waits.length, 2);
  const refused = elevenlabs({ apiKey: 'k', cfg: CFG, fetchImpl: async () => new Response('{"detail":{"status":"quota_exceeded","message":"You have run out of credits."}}', { status: 401 }) });
  await assert.rejects(refused({ text: 'Hi.' }), (e) => e instanceof FatalProviderError && /run out of credits/.test(e.message));
  assert.throws(() => elevenlabs({ apiKey: '', cfg: CFG }), /ELEVENLABS_API_KEY/);
  assert.throws(() => elevenlabs({ apiKey: 'k', cfg: { ...CFG, voiceId: '' } }), /voiceId/);
  const tiny = elevenlabs({ apiKey: 'k', cfg: CFG, fetchImpl: async () => okRes(10) });
  await assert.rejects(tiny({ text: 'Hi.' }), /only 10 bytes/);
});
