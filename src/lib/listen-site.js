// Site side of Listen: given a page's clips, returns what the player needs, or null when the page has no current audio.
// A page with no audio, or whose text changed after its audio was made, simply shows no Listen button.
import cfg from '../data/listen/config.json';
import manifest from '../data/listen/manifest.json';
import { resolveListen } from './listen.js';

// PUBLIC_LISTEN_BASE lets a test build point at a local folder instead of the real audio address.
const config = { ...cfg, audioBase: import.meta.env?.PUBLIC_LISTEN_BASE || cfg.audioBase };

export const listenFor = (clips) => resolveListen(clips, manifest, config);
