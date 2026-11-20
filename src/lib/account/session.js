// Sign-in cookies. The tokens live in HttpOnly cookies, so a script on the page can never read them.
//   u500_at  the short-lived access token (about an hour)
//   u500_rt  the refresh token (30 days), used to get a new access token without asking for a new code
//   u500_in  a plain flag the pages read to show "My dashboard" instead of "Sign in". It holds no identity and grants nothing.
// The two tokens are sent only to /api, never to ordinary pages.

const DAY = 86400;
export const REFRESH_DAYS = 30;

export function parseCookies(header) {
  const out = {};
  for (const part of String(header || '').split(';')) {
    const i = part.indexOf('=');
    if (i < 1) continue;
    const k = part.slice(0, i).trim();
    if (!(k in out)) out[k] = part.slice(i + 1).trim();
  }
  return out;
}

const attrs = (secure, path, maxAge, httpOnly) =>
  `Path=${path}; Max-Age=${maxAge}; SameSite=Lax${secure ? '; Secure' : ''}${httpOnly ? '; HttpOnly' : ''}`;

export function sessionCookies({ access_token, refresh_token, expires_in }, secure) {
  const ttl = Math.max(60, Math.min(Number(expires_in) || 3600, DAY));
  return [
    `u500_at=${access_token}; ${attrs(secure, '/api', ttl, true)}`,
    `u500_rt=${refresh_token}; ${attrs(secure, '/api', REFRESH_DAYS * DAY, true)}`,
    `u500_in=1; ${attrs(secure, '/', REFRESH_DAYS * DAY, false)}`,
  ];
}

export function clearCookies(secure) {
  return [
    `u500_at=; ${attrs(secure, '/api', 0, true)}`,
    `u500_rt=; ${attrs(secure, '/api', 0, true)}`,
    `u500_in=; ${attrs(secure, '/', 0, false)}`,
  ];
}

// Reads the claims of a token without checking its signature. That is safe here because the token is only used
// to learn when it expires and which student it names; the database checks the signature on every request it receives.
export function jwtClaims(token) {
  try {
    const part = String(token).split('.')[1];
    const b64 = part.replace(/-/g, '+').replace(/_/g, '/');
    return JSON.parse(atob(b64 + '='.repeat((4 - (b64.length % 4)) % 4)));
  } catch {
    return null;
  }
}

export const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
