// Contact form: checks a message from /contact/ and emails it to the site owner through Resend.
// The destination address lives only in the Cloudflare setting CONTACT_TO, never in this repository or on a page.
//
// Cloudflare Pages settings (Settings > Variables and Secrets), all as Secret type:
//   RESEND_API_KEY  an API key from resend.com (Sending access is enough)
//   CONTACT_TO      the address that receives the messages
//   CONTACT_FROM    optional sender, for example  Universities500 <contact@universities500.com>
//                   once that domain is verified in Resend. Without it, Resend's test sender is used,
//                   which Resend delivers only to the address the Resend account was opened with.
//
// Nothing is stored here. The message goes straight to the email and is not kept on the site.

export const LIMITS = { name: 100, email: 254, subject: 150, messageMin: 10, message: 4000 };

const DEFAULT_FROM = 'Universities500 <onboarding@resend.dev>';
const MIN_FILL_MS = 2500; // a person cannot read and fill four fields faster than this
const MAX_BODY_BYTES = 20000;

const json = (status, body) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' },
  });

// For visitors without JavaScript the form posts normally, so answer with a small page instead of JSON.
const page = (status, heading, text) =>
  new Response(
    `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">` +
      `<meta name="robots" content="noindex"><title>${heading} | Universities500</title></head>` +
      `<body style="font-family:system-ui,sans-serif;max-width:34rem;margin:4rem auto;padding:0 1rem;line-height:1.5">` +
      `<h1>${heading}</h1><p>${text}</p><p><a href="/contact/">Back to the contact form</a> · <a href="/">Home</a></p></body></html>`,
    { status, headers: { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store' } },
  );

// One line of plain text: no control characters, no line breaks, collapsed spaces.
const oneLine = (v) => String(v ?? '').replace(/[\u0000-\u001f\u007f\u2028\u2029]+/g, ' ').replace(/\s+/g, ' ').trim();
// Message text keeps its line breaks but loses other control characters.
const multiLine = (v) =>
  String(v ?? '').replace(/\r\n?/g, '\n').replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f\u2028\u2029]/g, '').trim();

const EMAIL = /^[^\s@<>()[\]\\,;:"]+@[^\s@<>()[\]\\,;:"]+\.[^\s@<>()[\]\\,;:"]{2,}$/;

export function validate(form) {
  const name = oneLine(form.get('name'));
  const email = oneLine(form.get('email'));
  const subject = oneLine(form.get('subject'));
  const message = multiLine(form.get('message'));
  const errors = {};
  if (!name) errors.name = 'Enter your name.';
  else if (name.length > LIMITS.name) errors.name = `Keep your name under ${LIMITS.name} characters.`;
  if (!email) errors.email = 'Enter your email address.';
  else if (email.length > LIMITS.email || !EMAIL.test(email)) errors.email = 'Enter a valid email address, like name@example.com.';
  if (!subject) errors.subject = 'Enter a subject.';
  else if (subject.length > LIMITS.subject) errors.subject = `Keep the subject under ${LIMITS.subject} characters.`;
  if (!message) errors.message = 'Write your message.';
  else if (message.length < LIMITS.messageMin) errors.message = 'Write a little more so we can help.';
  else if (message.length > LIMITS.message) errors.message = `Keep your message under ${LIMITS.message} characters.`;
  return { values: { name, email, subject, message }, errors };
}

export async function handleContact(request, env = {}, fetchImpl = fetch, now = Date.now()) {
  const wantsJson = (request.headers.get('accept') || '').includes('application/json');
  const fail = (status, error, text) =>
    wantsJson ? json(status, { ok: false, error, message: text }) : page(status, 'Message not sent', text);
  const done = () =>
    wantsJson ? json(200, { ok: true }) : page(200, 'Message sent', 'Thank you. We will reply to the email address you gave us.');

  if (request.method !== 'POST') return json(405, { ok: false, error: 'method_not_allowed' });

  // Only the site's own pages may post here (the preview addresses work too, because the host is compared, not fixed).
  const origin = request.headers.get('origin');
  if (origin) {
    let same = false;
    try { same = new URL(origin).host === new URL(request.url).host; } catch { same = false; }
    if (!same) return fail(403, 'forbidden', 'This message could not be sent from here.');
  }

  const len = Number(request.headers.get('content-length') || 0);
  if (len > MAX_BODY_BYTES) return fail(413, 'too_large', 'That message is too long to send.');

  let form;
  try { form = await request.formData(); } catch { return fail(400, 'bad_request', 'The form could not be read. Please try again.'); }

  // Spam traps. A filled hidden field, or a form sent within a moment of loading, gets a normal "sent" answer
  // so the sender learns nothing, but nothing is emailed.
  if (oneLine(form.get('website'))) return done();
  const t = Number(form.get('t'));
  if (Number.isFinite(t) && t > 0 && now - t < MIN_FILL_MS) return done();

  const { values, errors } = validate(form);
  if (Object.keys(errors).length) {
    return wantsJson
      ? json(422, { ok: false, error: 'invalid', errors })
      : page(422, 'Message not sent', `Please go back and check: ${Object.values(errors).join(' ')}`);
  }

  if (!env.RESEND_API_KEY || !env.CONTACT_TO) {
    console.error('contact: RESEND_API_KEY or CONTACT_TO is not set in the Cloudflare Pages settings');
    return fail(500, 'not_configured', 'Sorry, messages cannot be sent right now. Please try again later.');
  }

  const sent = new Date(now).toISOString();
  const text = `From: ${values.name} <${values.email}>\nSent: ${sent}\n\n${values.message}\n\n--\nSent from the contact form on universities500.com. Reply to this email to answer ${values.name}.`;

  let res;
  try {
    res = await fetchImpl('https://api.resend.com/emails', {
      method: 'POST',
      headers: { authorization: `Bearer ${env.RESEND_API_KEY}`, 'content-type': 'application/json' },
      body: JSON.stringify({
        from: env.CONTACT_FROM || DEFAULT_FROM,
        to: [env.CONTACT_TO],
        reply_to: values.email,
        subject: `[Universities500 contact] ${values.subject}`,
        text,
      }),
    });
  } catch (e) {
    console.error('contact: could not reach Resend', e && e.message);
    return fail(502, 'send_failed', 'Sorry, your message could not be sent. Please try again in a few minutes.');
  }
  if (!res.ok) {
    let detail = '';
    try { detail = (await res.text()).slice(0, 300); } catch { /* ignore */ }
    console.error('contact: Resend answered', res.status, detail);
    return fail(502, 'send_failed', 'Sorry, your message could not be sent. Please try again in a few minutes.');
  }
  return done();
}
