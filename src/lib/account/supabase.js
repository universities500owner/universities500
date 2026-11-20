// A thin wrapper over Supabase's web APIs, using plain fetch so it runs on Cloudflare and in tests.
// Two keys are used, both set as Cloudflare Worker secrets and never sent to the browser:
//   SUPABASE_ANON_KEY     the publishable key (or the older anon key): asks for sign-in codes, checks them, refreshes sessions, and acts as the student
//   SUPABASE_SERVICE_KEY  the secret key (or the older service_role key): creates and deletes accounts, and writes the consent record. Server only.
// Every call returns { ok, status, data } and never throws on an HTTP error.

// Supabase's newer keys (sb_publishable_..., sb_secret_...) are not JWTs and must be sent in the apikey header only.
// The older anon and service_role keys are JWTs and are also sent as the bearer token, as before.
const isJwt = (k) => typeof k === 'string' && k.startsWith('eyJ');

export function supabase(env = {}, fetchImpl = fetch) {
  const base = String(env.SUPABASE_URL || '').replace(/\/+$/, '');
  const anon = env.SUPABASE_ANON_KEY;
  const service = env.SUPABASE_SERVICE_KEY;

  async function call(path, { method = 'GET', key, jwt, body, headers = {} } = {}) {
    let res;
    try {
      res = await fetchImpl(base + path, {
        method,
        headers: {
          apikey: key,
          ...(jwt ? { authorization: `Bearer ${jwt}` } : isJwt(key) ? { authorization: `Bearer ${key}` } : {}),
          ...(body !== undefined ? { 'content-type': 'application/json' } : {}),
          ...headers,
        },
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });
    } catch (e) {
      return { ok: false, status: 0, data: null, network: true };
    }
    let data = null;
    try {
      const text = await res.text();
      if (text) { try { data = JSON.parse(text); } catch { data = text; } }
    } catch { /* an empty or unreadable body is fine */ }
    // content-range is how PostgREST reports a total (Prefer: count=exact), like "0-24/137".
    return { ok: res.ok, status: res.status, data, range: res.headers.get('content-range') || '' };
  }

  return {
    configured: !!(base && anon && service),
    // Accounts are created only here, after the Gmail address has been checked. Sign-up itself is switched off in Supabase.
    createUser: (email, metadata) => call('/auth/v1/admin/users', { method: 'POST', key: service, body: { email, email_confirm: true, user_metadata: metadata } }),
    sendCode: (email) => call('/auth/v1/otp', { method: 'POST', key: anon, body: { email, create_user: false } }),
    verifyCode: (email, token) => call('/auth/v1/verify', { method: 'POST', key: anon, body: { type: 'email', email, token } }),
    refresh: (refreshToken) => call('/auth/v1/token?grant_type=refresh_token', { method: 'POST', key: anon, body: { refresh_token: refreshToken } }),
    signOut: (jwt) => call('/auth/v1/logout?scope=local', { method: 'POST', key: anon, jwt }),
    deleteUser: (id) => call(`/auth/v1/admin/users/${id}`, { method: 'DELETE', key: service }),
    // Database calls act as the signed-in student when a jwt is given (so row level security applies), or as the server otherwise.
    db: (path, { method = 'GET', jwt, body, prefer } = {}) =>
      call('/rest/v1/' + path, { method, key: jwt ? anon : service, jwt, body, headers: prefer ? { prefer } : {} }),
  };
}
