// Cloudflare Worker entry. The site is static files in dist/; this Worker only answers the /api/ addresses
// (wrangler.jsonc sends nothing else to it). Each route hands the request to a plain function whose logic and
// settings are described in src/lib/account/handlers.js and src/lib/contact-handler.js.
import { handleConfig, handleRequestCode, handleVerify, handleLogout, handleMe, handleSaved, handleExport } from './lib/account/handlers.js';
import { handleContact } from './lib/contact-handler.js';

const json = (status, body, headers = {}) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store', ...headers },
  });

// The contact form only accepts POST; opening the address in a browser gets a plain 405.
const contact = (request, env) =>
  request.method === 'POST' ? handleContact(request, env) : json(405, { ok: false, error: 'method_not_allowed' }, { allow: 'POST' });

export const ROUTES = {
  '/api/contact': contact,
  '/api/auth/config': handleConfig,
  '/api/auth/request': handleRequestCode,
  '/api/auth/verify': handleVerify,
  '/api/auth/logout': handleLogout,
  '/api/me': handleMe,
  '/api/me/saved': handleSaved,
  '/api/me/export': handleExport,
};

export default {
  async fetch(request, env) {
    const { pathname } = new URL(request.url);
    const route = ROUTES[pathname.length > 1 ? pathname.replace(/\/+$/, '') : pathname];
    if (route) return route(request, env);
    if (pathname.startsWith('/api/')) return json(404, { ok: false, error: 'not_found', message: 'No such address.' });
    return env.ASSETS.fetch(request); // anything else is a page or file of the site
  },
};
