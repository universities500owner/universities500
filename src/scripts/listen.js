// The Listen player. Plays a page's clips one after another, like a podcast made from the page.
// One <audio> element is reused for every clip so phones keep playing with the screen locked.
const root = document.querySelector('[data-listen]');
if (root) init(root);

function init(root) {
  let data;
  try { data = JSON.parse(root.querySelector('[data-listen-data]').textContent); } catch { return; }
  const clips = data.clips;
  const bar = document.getElementById('lp');
  if (!clips || !clips.length || !bar) return;
  document.body.appendChild(bar); // the bar is fixed to the screen; keep it out of the page layout

  const $ = (k) => bar.querySelector(`[data-lp="${k}"]`);
  const btn = root.querySelector('.listen-btn');
  const el = { sec: $('sec'), count: $('count'), close: $('close'), pos: $('pos'), len: $('len'), seek: $('seek'), back: $('back'), play: $('play'), fwd: $('fwd'), speed: $('speed'), note: $('note'), live: $('live') };
  const html = document.documentElement;
  const RATES = [1, 1.25, 1.5, 2];
  const last = clips.length - 1;
  const sections = clips[last].s + 1;
  const dur = clips.map((c) => c.d); // seconds; replaced by the real length as each clip loads
  const warm = new Set();
  let idx = 0, want = false, finished = false, pending = null, dragging = false, announced = -1, lastState = 0;

  const audio = new Audio();
  audio.preload = 'metadata';
  let rate = 1;
  try { const r = Number(localStorage.getItem('u500-listen-rate')); if (RATES.includes(r)) rate = r; } catch {}
  const applyRate = () => {
    audio.defaultPlaybackRate = rate;
    audio.playbackRate = rate;
    el.speed.textContent = `${rate}×`;
    el.speed.setAttribute('aria-label', `Playback speed ${rate} times. Change speed`);
  };

  const fmt = (s) => {
    s = Math.max(0, Math.round(s || 0));
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
    return h ? `${h}:${String(m).padStart(2, '0')}:${String(x).padStart(2, '0')}` : `${m}:${String(x).padStart(2, '0')}`;
  };
  const starts = () => { let t = 0; return dur.map((d) => { const s = t; t += d; return s; }); };
  const total = () => dur.reduce((a, b) => a + b, 0);
  const pos = () => starts()[idx] + (pending ?? (audio.currentTime || 0));

  // ---- what the person sees ----
  function paint() {
    const t = pos(), T = Math.max(1, total());
    el.seek.max = String(Math.round(T));
    if (!dragging) el.seek.value = String(Math.round(Math.min(t, T)));
    el.seek.style.setProperty('--p', `${Math.min(100, (t / T) * 100)}%`);
    el.pos.textContent = fmt(dragging ? Number(el.seek.value) : t);
    el.len.textContent = fmt(T);
    el.seek.setAttribute('aria-valuetext', `${fmt(t)} of ${fmt(T)}`);
  }
  function section() {
    const c = clips[idx];
    el.sec.textContent = c.t;
    el.count.textContent = `${c.s + 1} of ${sections}`;
    if (announced !== c.s) {
      announced = c.s;
      el.live.textContent = `${c.t}, part ${c.s + 1} of ${sections}`;
    }
    if ('mediaSession' in navigator && window.MediaMetadata) {
      navigator.mediaSession.metadata = new MediaMetadata({ title: c.t, artist: 'Universities500', album: document.querySelector('h1')?.textContent?.trim() || 'Universities500' });
    }
  }
  function state(playing) {
    const open = !bar.hidden;
    // SVG elements have no .hidden property, so the attribute is set directly.
    const icon = (host, on) => { host.querySelector('.ic-play').toggleAttribute('hidden', on); host.querySelector('.ic-pause').toggleAttribute('hidden', !on); };
    icon(btn, playing);
    icon(el.play, playing);
    el.play.setAttribute('aria-label', playing ? 'Pause' : 'Play');
    btn.querySelector('.listen-t').textContent = playing ? 'Pause' : open && !finished ? 'Resume' : `Listen to this ${data.noun}`;
    btn.querySelector('.listen-m').hidden = playing || open;
    if ('mediaSession' in navigator) navigator.mediaSession.playbackState = playing ? 'playing' : 'paused';
  }
  function message(text) { el.note.textContent = text; el.note.classList.toggle('lp-err', text !== NOTE); }
  const NOTE = el.note.textContent;
  function measure() {
    const top = Math.max(0, window.innerHeight - bar.getBoundingClientRect().top);
    html.style.setProperty('--lp-top', `${Math.ceil(top)}px`);
  }

  // ---- loading and playing ----
  function load(i, at = 0) {
    idx = i;
    pending = at || null;
    finished = false;
    audio.src = clips[i].u;
    applyRate();
    section();
    paint();
  }
  function play() {
    message(NOTE);
    if (finished) load(0);
    if (!audio.src) load(idx);
    want = true;
    const p = audio.play();
    if (p && p.catch) p.catch((e) => { if (e && e.name !== 'AbortError') { want = false; state(false); } });
  }
  function pause() { want = false; audio.pause(); }
  function seekTo(t) {
    const T = total();
    t = Math.max(0, Math.min(T - 0.1, t));
    const s = starts();
    let i = s.findIndex((x, k) => t >= x && (k === last || t < s[k + 1]));
    if (i < 0) i = last;
    finished = false;
    if (i === idx && audio.readyState >= 1) audio.currentTime = t - s[i];
    else { load(i, t - s[i]); if (want) play(); }
    paint();
  }
  function skipSection(dir) {
    const s = starts();
    if (dir < 0) {
      // Back: the start of this part, or the part before it when already near the start.
      const mine = clips.findIndex((c) => c.s === clips[idx].s);
      const near = pos() - s[mine] < 4;
      const target = near && clips[mine - 1] ? clips.findIndex((c) => c.s === clips[mine - 1].s) : mine;
      seekTo(s[Math.max(0, target)]);
    } else {
      const k = clips.findIndex((c, n) => n > idx && c.s > clips[idx].s);
      if (k >= 0) seekTo(s[k]);
    }
  }
  function open() {
    if (bar.hidden) {
      bar.hidden = false;
      html.classList.add('has-lp');
      measure();
      section();
      paint();
    }
  }
  function close() {
    pause();
    bar.hidden = true;
    html.classList.remove('has-lp');
    html.style.removeProperty('--lp-top');
    state(false);
    btn.focus();
  }

  // ---- the audio element ----
  audio.addEventListener('loadedmetadata', () => {
    if (Number.isFinite(audio.duration) && audio.duration > 0) dur[idx] = audio.duration;
    if (pending != null) { try { audio.currentTime = pending; } catch {} pending = null; }
    paint();
  });
  audio.addEventListener('play', () => state(true));
  audio.addEventListener('pause', () => { if (!audio.ended) state(false); });
  audio.addEventListener('waiting', () => bar.classList.add('lp-wait'));
  audio.addEventListener('playing', () => { bar.classList.remove('lp-wait'); message(NOTE); });
  audio.addEventListener('timeupdate', () => {
    paint();
    const now = Date.now();
    if (now - lastState > 1000 && 'mediaSession' in navigator && navigator.mediaSession.setPositionState && Number.isFinite(audio.duration) && audio.duration > 0) {
      lastState = now;
      try { navigator.mediaSession.setPositionState({ duration: audio.duration, position: Math.min(audio.currentTime, audio.duration), playbackRate: audio.playbackRate }); } catch {}
    }
    // Start fetching the next clip a little early so there is no gap between parts.
    if (idx < last && audio.duration > 0 && audio.currentTime / audio.duration > 0.6 && !warm.has(idx + 1)) {
      warm.add(idx + 1);
      const w = new Audio();
      w.preload = 'auto';
      w.src = clips[idx + 1].u;
    }
  });
  audio.addEventListener('ended', () => {
    if (idx < last) { load(idx + 1); play(); return; }
    want = false;
    finished = true;
    state(false);
    paint();
  });
  audio.addEventListener('error', () => {
    want = false;
    bar.classList.remove('lp-wait');
    state(false);
    message('This part of the audio could not be loaded. Check your connection, then press play to try again.');
    if (audio.src) { const at = audio.currentTime; audio.removeAttribute('src'); pending = at || pending; }
  });

  // ---- controls ----
  btn.addEventListener('click', () => {
    open();
    if (want) pause(); else play();
  });
  el.play.addEventListener('click', () => { if (want) pause(); else play(); });
  el.back.addEventListener('click', () => seekTo(pos() - 15));
  el.fwd.addEventListener('click', () => seekTo(pos() + 15));
  el.speed.addEventListener('click', () => {
    rate = RATES[(RATES.indexOf(rate) + 1) % RATES.length];
    try { localStorage.setItem('u500-listen-rate', String(rate)); } catch {}
    applyRate();
  });
  el.close.addEventListener('click', close);
  el.seek.addEventListener('input', () => { dragging = true; el.pos.textContent = fmt(Number(el.seek.value)); el.seek.style.setProperty('--p', `${(Number(el.seek.value) / Math.max(1, total())) * 100}%`); });
  el.seek.addEventListener('change', () => { dragging = false; seekTo(Number(el.seek.value)); });
  window.addEventListener('resize', () => { if (!bar.hidden) measure(); });
  if ('ResizeObserver' in window) new ResizeObserver(() => { if (!bar.hidden) measure(); }).observe(bar);

  if ('mediaSession' in navigator) {
    const set = (a, f) => { try { navigator.mediaSession.setActionHandler(a, f); } catch {} };
    set('play', play);
    set('pause', pause);
    set('seekbackward', () => seekTo(pos() - 15));
    set('seekforward', () => seekTo(pos() + 15));
    set('previoustrack', () => skipSection(-1));
    set('nexttrack', () => skipSection(1));
    set('seekto', (d) => { if (d && Number.isFinite(d.seekTime)) seekTo(starts()[idx] + d.seekTime); });
  }

  applyRate();
  section();
  paint();
  root.classList.add('is-ready');
  // Test hook for the page's own checks; harmless otherwise.
  root.__listen = { audio, seekTo, state: () => ({ idx, want, finished, rate, total: total() }) };
}
