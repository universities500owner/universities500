// A short, dismissible note shown to a signed-out visitor the first time they save something.
// It shows once per browser session, and not again for 30 days after "Not now". Nothing is sent anywhere.
const SEEN = 'u500-su-seen';
const OFF = 'u500-su-off';
const QUIET_MS = 30 * 24 * 60 * 60 * 1000;

const area = (kind) => { try { return window[kind]; } catch (e) { return null; } };
const get = (kind, k) => { try { return area(kind).getItem(k); } catch (e) { return null; } };
const put = (kind, k, v) => { try { area(kind).setItem(k, v); } catch (e) { /* storage blocked: the in-memory flag below still stops repeats */ } };

let shown = false;

export function nudgeToSignUp() {
  if (shown || document.getElementById('su-toast')) return;
  if (get('sessionStorage', SEEN)) return;
  const off = Number(get('localStorage', OFF)) || 0;
  if (off && Date.now() - off < QUIET_MS) return;
  shown = true;
  put('sessionStorage', SEEN, '1');

  const box = document.createElement('div');
  box.id = 'su-toast';
  box.className = 'su-toast';
  box.setAttribute('role', 'status');
  box.setAttribute('aria-live', 'polite');

  const h = document.createElement('b');
  h.textContent = 'Saved on this device';
  const p = document.createElement('p');
  p.textContent = 'Sign up free to keep your shortlist on every device. What you saved here is added when you sign in.';

  const act = document.createElement('div');
  act.className = 'su-toast-act';
  const go = document.createElement('a');
  go.className = 'btn';
  go.href = '/sign-in/';
  go.textContent = 'Sign up free';
  const no = document.createElement('button');
  no.type = 'button';
  no.className = 'su-no';
  no.textContent = 'Not now';

  const close = () => { box.remove(); document.removeEventListener('keydown', onKey); };
  const onKey = (e) => { if (e.key === 'Escape') close(); };
  no.addEventListener('click', () => { put('localStorage', OFF, String(Date.now())); close(); });
  document.addEventListener('keydown', onKey);

  act.append(go, no);
  box.append(h, p, act);
  document.body.appendChild(box);
}
