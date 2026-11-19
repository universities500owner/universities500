#!/usr/bin/env node
// Makes the Listen audio that is missing or out of date.
//
//   node scripts/listen/generate.mjs --dry-run                  count what is missing and what it would cost; call nothing
//   node scripts/listen/generate.mjs --only guide:canada        make only the Canada guide
//   node scripts/listen/generate.mjs --kind articles            guides | articles
//   node scripts/listen/generate.mjs --provider stub            free test run: silent MP3s of the right length
//
// Options: --out <dir> (default out/audio), --cap <characters> (default: monthly cap from config or LISTEN_MONTHLY_CHARS),
//          --provider elevenlabs|stub (default: config), --max-clips <n>.
//
// Safe to stop and run again: a clip is recorded in the manifest only after its audio is written, and a clip whose text has
// not changed is never made twice. The run stops by itself when the monthly character cap is reached.
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { ROOT, loadConfig, loadManifest, manifestPath, listenPages } from './pages.mjs';
import { createProvider, FatalProviderError } from './providers.mjs';

const month = (d = new Date()) => d.toISOString().slice(0, 7);
const fmt = (n) => n.toLocaleString('en-US');

export function plan({ cfg, manifest, pages, only = [], kind = '' }) {
  const want = (p) => (!kind || p.kind + 's' === kind || p.kind === kind) && (!only.length || only.some((o) => p.key === o || p.key.startsWith(`${o}`)));
  const seen = new Set();
  const todo = [];
  const perPage = [];
  for (const p of pages.filter(want)) {
    let pending = 0;
    p.clips.forEach((c, i) => {
      if (manifest.clips[c.hash]) return;
      pending++;
      if (seen.has(c.hash)) return; // the same words on another page: made once, used by both
      seen.add(c.hash);
      todo.push({ ...c, page: p.key, prev: p.clips[i - 1]?.text, next: p.clips[i + 1]?.text });
    });
    perPage.push({ key: p.key, clips: p.clips.length, pending });
  }
  const chars = todo.reduce((n, c) => n + c.text.length, 0);
  return { todo, chars, perPage, cost: (chars / 1000) * (cfg.pricePer1kChars ?? 0.1) };
}

export async function run(opts) {
  const {
    root = ROOT, cfg = loadConfig(root), provider: providerName = cfg.provider, out = path.join(root, 'out/audio'),
    only = [], kind = '', dryRun = false, cap, maxClips = Infinity, synth: injected, log = console.log, now = new Date(),
  } = opts;
  const manifest = loadManifest(root);
  const pages = listenPages(cfg, root);
  const p = plan({ cfg, manifest, pages, only, kind });
  const key = month(now);
  const monthly = cap ?? Number(process.env.LISTEN_MONTHLY_CHARS || cfg.monthlyChars || 0);
  const used = manifest.usage[key] || 0;
  const room = providerName === 'stub' ? Infinity : monthly ? Math.max(0, monthly - used) : Infinity;

  log(`Pages checked: ${p.perPage.length}. Clips already voiced: ${p.perPage.reduce((n, x) => n + x.clips - x.pending, 0)}. To make: ${p.todo.length} clips, ${fmt(p.chars)} characters.`);
  for (const x of p.perPage.filter((x) => x.pending).slice(0, 80)) log(`  ${x.key}: ${x.pending} of ${x.clips} clips`);
  if (p.perPage.filter((x) => x.pending).length > 80) log('  ...');
  if (providerName !== 'stub') log(`Estimated cost: about $${p.cost.toFixed(2)} at $${cfg.pricePer1kChars ?? 0.1} per 1,000 characters (an estimate; your plan's own price applies).`);
  if (monthly && providerName !== 'stub') log(`Monthly cap: ${fmt(monthly)} characters; used so far this month (${key}): ${fmt(used)}; room: ${fmt(room)}.`);
  if (dryRun || !p.todo.length) {
    if (!p.todo.length) log('Nothing to make: all audio is up to date.');
    return { made: 0, failed: 0, skipped: 0, chars: 0, stoppedByCap: false, plan: p };
  }
  if (providerName !== 'stub' && monthly && p.todo[0].text.length > room) {
    log('The monthly cap leaves no room for even the first clip. Nothing made.');
    return { made: 0, failed: 0, skipped: p.todo.length, chars: 0, stoppedByCap: true, plan: p };
  }

  const synth = injected || createProvider(providerName, cfg);
  fs.mkdirSync(out, { recursive: true });
  const kbps = cfg.bitrateKbps || 64;
  let made = 0, failed = 0, spent = 0, stoppedByCap = false, fatal = null, next = 0;
  const work = p.todo.slice(0, Number.isFinite(maxClips) ? maxClips : undefined);

  const save = () => {
    const sorted = Object.fromEntries(Object.entries(manifest.clips).sort(([a], [b]) => a.localeCompare(b)));
    fs.writeFileSync(manifestPath(root), `${JSON.stringify({ clips: sorted, usage: manifest.usage }, null, 1)}\n`);
  };

  async function worker() {
    while (!fatal && !stoppedByCap) {
      const c = work[next++];
      if (!c) return;
      if (room !== Infinity && spent + c.text.length > room) { stoppedByCap = true; return; }
      spent += c.text.length; // reserved before the call so parallel workers cannot overshoot the cap
      try {
        const audio = await synth({ text: c.text, previousText: c.prev, nextText: c.next });
        fs.writeFileSync(path.join(out, `${c.hash}.mp3`), audio);
        manifest.clips[c.hash] = { seconds: Math.round(((audio.length * 8) / (kbps * 1000)) * 10) / 10, bytes: audio.length, chars: c.text.length };
        manifest.usage[key] = (manifest.usage[key] || 0) + c.text.length;
        made++;
        save();
        if (made % 10 === 0) log(`  made ${made} of ${work.length} clips`);
      } catch (e) {
        spent -= c.text.length;
        if (e instanceof FatalProviderError) { fatal = e; return; }
        failed++;
        log(`  FAILED ${c.id}: ${e.message}`);
      }
    }
  }
  await Promise.all(Array.from({ length: Math.max(1, Math.min(cfg.concurrency || 2, 6)) }, worker));
  if (fatal) throw fatal;
  const skipped = work.length - made - failed;
  log(`Done. Made ${made} clips (${fmt(spent)} characters). Failed: ${failed}. Left for a later run: ${p.todo.length - made - failed}${stoppedByCap ? ' (monthly cap reached)' : ''}.`);
  return { made, failed, skipped, chars: spent, stoppedByCap, plan: p };
}

function args(argv) {
  const o = { only: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--dry-run') o.dryRun = true;
    else if (a === '--only') o.only.push(...String(argv[++i] || '').split(',').map((s) => s.trim()).filter(Boolean));
    else if (a === '--kind') o.kind = argv[++i];
    else if (a === '--out') o.out = path.resolve(argv[++i]);
    else if (a === '--cap') o.cap = Number(argv[++i]);
    else if (a === '--provider') o.provider = argv[++i];
    else if (a === '--max-clips') o.maxClips = Number(argv[++i]);
    else throw new Error(`Unknown option ${a}`);
  }
  return o;
}

if (import.meta.url === pathToFileURL(process.argv[1] || '').href) {
  const o = args(process.argv.slice(2));
  const summary = [];
  run({ ...o, log: (m) => { console.log(m); summary.push(m); } })
    .then((r) => {
      if (process.env.GITHUB_STEP_SUMMARY) fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY, `### Listen audio\n\n\`\`\`\n${summary.join('\n')}\n\`\`\`\n`);
      process.exit(r.failed ? 1 : 0);
    })
    .catch((e) => {
      console.error(`\nStopped: ${e.message}`);
      process.exit(2);
    });
}
