// Sign-in page: asks for a Gmail address and consent, then for the 6-digit code. All checks that matter are repeated
// on the server (src/lib/account/handlers.js); the checks here only save a round trip.
const $ = (id) => document.getElementById(id);
const step1 = $('si-step1'), step2 = $('si-step2');
let cfg = { configured: true, turnstileSiteKey: null };
let widget = null, token = '';
let email = '';

function say(el, text, bad) { el.textContent = text || ''; el.classList.toggle('is-bad', !!bad); }
function fieldErr(inputId, errId, text) {
  const p = $(errId), i = inputId && $(inputId);
  p.textContent = text || ''; p.hidden = !text;
  if (i) { if (text) i.setAttribute('aria-invalid', 'true'); else i.removeAttribute('aria-invalid'); }
}
function post(url, body) {
  return fetch(url, { method: 'POST', credentials: 'same-origin', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) })
    .then((r) => r.json().catch(() => ({})).then((j) => ({ status: r.status, j })));
}
function show(n) {
  step1.hidden = n !== 1; step2.hidden = n !== 2;
  (n === 1 ? $('si-email') : $('si-code')).focus();
}
// Only /student/ pages may be the place to land after sign-in.
function landing(fallback) {
  const n = new URLSearchParams(location.search).get('next') || '';
  return /^\/student\/[a-z0-9\/-]*$/.test(n) ? n : fallback || '/student/';
}

function loadTurnstile(siteKey) {
  const s = document.createElement('script');
  s.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
  s.async = true;
  s.onload = () => {
    widget = window.turnstile.render('#si-turnstile', {
      sitekey: siteKey,
      callback: (t) => { token = t; },
      'expired-callback': () => { token = ''; },
      'error-callback': () => { token = ''; },
    });
  };
  document.head.appendChild(s);
}
function resetCaptcha() { token = ''; if (widget !== null && window.turnstile) window.turnstile.reset(widget); }

if (document.documentElement.dataset.in) $('si-in').hidden = false;

fetch('/api/auth/config', { credentials: 'same-origin' })
  .then((r) => r.json())
  .then((c) => {
    cfg = c;
    if (!c.configured) {
      $('si-off').hidden = false;
      $('si-send').disabled = true;
      return;
    }
    if (c.turnstileSiteKey) loadTurnstile(c.turnstileSiteKey);
  })
  .catch(() => { /* the form still works; the server answers if something is wrong */ });

$('si-form').addEventListener('submit', (ev) => {
  ev.preventDefault();
  const status = $('si-status');
  say(status, '');
  fieldErr('si-email', 'si-email-err', '');
  fieldErr(null, 'si-consent-err', '');
  email = $('si-email').value.trim();
  if (!email) { fieldErr('si-email', 'si-email-err', 'Enter your Gmail address.'); $('si-email').focus(); return; }
  if (!$('si-adult').checked || !$('si-terms').checked) {
    fieldErr(null, 'si-consent-err', 'Please confirm you are 18 or older and accept the Terms and Privacy page.');
    return;
  }
  if (cfg.turnstileSiteKey && !token) { say(status, 'One moment while we run a quick security check, then press the button again.', true); return; }
  const btn = $('si-send');
  btn.disabled = true; btn.textContent = 'Sending…';
  post('/api/auth/request', { email, adult: true, terms: true, marketing: $('si-marketing').checked, turnstile: token })
    .then(({ status: code, j }) => {
      if (code === 200 && j.ok) {
        email = j.email; // the canonical address the code went to
        $('si-sent-to').textContent = email;
        $('si-code').value = '';
        say($('si-status2'), '');
        show(2);
        return;
      }
      if (j.errors && j.errors.email) { fieldErr('si-email', 'si-email-err', j.errors.email); $('si-email').focus(); }
      else if (j.errors && j.errors.consent) fieldErr(null, 'si-consent-err', j.errors.consent);
      else say(status, j.message || 'Sorry, something went wrong. Please try again.', true);
    })
    .catch(() => say(status, 'Sorry, we could not reach the site. Check your connection and try again.', true))
    .then(() => { resetCaptcha(); btn.disabled = !cfg.configured; btn.textContent = 'Email me a code'; });
});

$('si-code-form').addEventListener('submit', (ev) => {
  ev.preventDefault();
  const status = $('si-status2');
  say(status, '');
  fieldErr('si-code', 'si-code-err', '');
  const code = $('si-code').value.replace(/\s+/g, '');
  if (!/^\d{6}$/.test(code)) { fieldErr('si-code', 'si-code-err', 'Enter the 6-digit code from the email.'); $('si-code').focus(); return; }
  const btn = $('si-verify');
  btn.disabled = true; btn.textContent = 'Checking…';
  post('/api/auth/verify', { email, code })
    .then(({ status: s, j }) => {
      if (s === 200 && j.ok) { say(status, 'Signed in. Opening your dashboard…'); location.assign(landing(j.next)); return; }
      btn.disabled = false; btn.textContent = 'Confirm and sign in';
      if (j.errors && j.errors.code) { fieldErr('si-code', 'si-code-err', j.errors.code); $('si-code').select(); }
      else say(status, j.message || 'Sorry, something went wrong. Please try again.', true);
    })
    .catch(() => { btn.disabled = false; btn.textContent = 'Confirm and sign in'; say(status, 'Sorry, we could not reach the site. Check your connection and try again.', true); });
});

$('si-back').addEventListener('click', () => { show(1); });
