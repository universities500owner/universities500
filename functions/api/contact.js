// Cloudflare Pages Function: receives the contact form at /api/contact.
// The logic and the settings it needs are described in src/lib/contact-handler.js.
import { handleContact } from '../../src/lib/contact-handler.js';

export const onRequestPost = ({ request, env }) => handleContact(request, env);

// Any other method (a visitor opening /api/contact in the address bar, for example).
export const onRequest = () =>
  new Response(JSON.stringify({ ok: false, error: 'method_not_allowed' }), {
    status: 405,
    headers: { allow: 'POST', 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' },
  });
