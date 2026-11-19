// Voice providers. Each one turns text into MP3 bytes: synth({ text, previousText, nextText }) -> Buffer.
// The rest of the generator does not know which provider it is talking to.
import { spawnSync } from 'node:child_process';

// A problem that will repeat for every clip (bad key, no credits, blocked voice). The run stops at once.
export class FatalProviderError extends Error {}

const sleepMs = (ms) => new Promise((r) => setTimeout(r, ms));
const clip = (s, n) => String(s || '').trim().slice(0, n);

export function elevenlabs({ apiKey, cfg, fetchImpl = fetch, sleep = sleepMs, retries = 4 }) {
  if (!apiKey) throw new FatalProviderError('ELEVENLABS_API_KEY is not set.');
  if (!cfg.voiceId) throw new FatalProviderError('No voice chosen yet: set "voiceId" in src/data/listen/config.json.');
  // The "continue from the neighbouring text" fields are for models that support them (not confirmed for v3 or v4, so not sent).
  const stitch = cfg.stitch !== false && !/v[34]/i.test(cfg.model);
  const url = `https://api.elevenlabs.io/v1/text-to-speech/${encodeURIComponent(cfg.voiceId)}?output_format=${encodeURIComponent(cfg.format)}`;

  return async function synth({ text, previousText, nextText }) {
    const body = { text, model_id: cfg.model, voice_settings: cfg.settings };
    if (stitch && previousText) body.previous_text = clip(previousText.slice(-400), 400);
    if (stitch && nextText) body.next_text = clip(nextText, 400);
    let last = '';
    for (let attempt = 0; attempt <= retries; attempt++) {
      let res;
      try {
        res = await fetchImpl(url, {
          method: 'POST',
          headers: { 'xi-api-key': apiKey, 'Content-Type': 'application/json', Accept: 'audio/mpeg' },
          body: JSON.stringify(body),
        });
      } catch (e) {
        last = `network error: ${e.message}`;
        await sleep(1500 * 2 ** attempt);
        continue;
      }
      if (res.ok) {
        const buf = Buffer.from(await res.arrayBuffer());
        if (buf.length < 500) throw new Error(`ElevenLabs returned only ${buf.length} bytes of audio.`);
        return buf;
      }
      const raw = await res.text().catch(() => '');
      let detail = raw;
      try {
        const j = JSON.parse(raw);
        detail = typeof j.detail === 'string' ? j.detail : j.detail?.message || j.detail?.status || JSON.stringify(j.detail ?? j);
      } catch {}
      last = `HTTP ${res.status}: ${clip(detail, 300)}`;
      if (res.status === 401 || res.status === 402 || res.status === 403) {
        throw new FatalProviderError(`ElevenLabs refused the request (${last}). Check the key, its permissions, its character limit, and that the voice is available on your plan.`);
      }
      if (res.status === 429 || res.status >= 500) {
        const wait = Number(res.headers?.get?.('retry-after')) * 1000 || 2000 * 2 ** attempt;
        await sleep(Math.min(wait, 60000));
        continue;
      }
      throw new Error(last); // 400/422: this clip's text or settings are the problem; other clips may be fine
    }
    throw new Error(`Gave up after ${retries + 1} tries (${last}).`);
  };
}

// For trying the whole pipeline without spending anything: real, playable MP3s of silence, as long as the text would take to say.
export function stub({ cfg }) {
  const kbps = cfg.bitrateKbps || 64;
  return async function synth({ text }) {
    const seconds = Math.max(1, Math.round(text.length / 15));
    const r = spawnSync('ffmpeg', ['-v', 'error', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono', '-t', String(seconds), '-c:a', 'libmp3lame', '-b:a', `${kbps}k`, '-f', 'mp3', 'pipe:1'], { maxBuffer: 64 * 1024 * 1024 });
    if (r.status === 0 && r.stdout?.length) return r.stdout;
    return Buffer.alloc(Math.round((kbps * 1000 * seconds) / 8), 0xff); // no ffmpeg: placeholder bytes of the right size
  };
}

export function createProvider(name, cfg, env = process.env) {
  if (name === 'elevenlabs') return elevenlabs({ apiKey: env.ELEVENLABS_API_KEY, cfg });
  if (name === 'stub') return stub({ cfg });
  throw new Error(`Unknown provider "${name}". Use elevenlabs or stub.`);
}
