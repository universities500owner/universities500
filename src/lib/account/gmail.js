// Student sign-in uses a Gmail address only. This turns whatever was typed into one canonical address,
// so that  Jo.Smith+uni@GoogleMail.com  and  josmith@gmail.com  are the same student (they are the same mailbox).
//
// Gmail ignores dots and anything after a plus sign in the part before the @, and googlemail.com is the same
// service as gmail.com. Names are 6 to 30 letters, digits or dots, with no leading, trailing or doubled dots.

export const GMAIL_ERRORS = {
  empty: 'Enter your Gmail address.',
  not_gmail: 'Use a Gmail address that ends in @gmail.com. Other email providers are not supported yet.',
  invalid: 'That does not look like a valid Gmail address. Check it and try again.',
};

export function normaliseGmail(input) {
  const raw = String(input ?? '').normalize('NFKC').trim().toLowerCase();
  if (!raw) return { ok: false, error: 'empty', message: GMAIL_ERRORS.empty };
  if (raw.length > 254 || /[\s<>()[\]\\,;:"]/.test(raw)) return { ok: false, error: 'invalid', message: GMAIL_ERRORS.invalid };
  const at = raw.lastIndexOf('@');
  if (at < 1 || raw.indexOf('@') !== at) return { ok: false, error: 'invalid', message: GMAIL_ERRORS.invalid };
  const domain = raw.slice(at + 1);
  if (domain !== 'gmail.com' && domain !== 'googlemail.com') return { ok: false, error: 'not_gmail', message: GMAIL_ERRORS.not_gmail };
  let local = raw.slice(0, at);
  const plus = local.indexOf('+');
  if (plus >= 0) local = local.slice(0, plus);
  if (!/^[a-z0-9.]+$/.test(local) || local.startsWith('.') || local.endsWith('.') || local.includes('..')) {
    return { ok: false, error: 'invalid', message: GMAIL_ERRORS.invalid };
  }
  const bare = local.replace(/\./g, '');
  if (bare.length < 6 || bare.length > 30) return { ok: false, error: 'invalid', message: GMAIL_ERRORS.invalid };
  return { ok: true, email: `${bare}@gmail.com` };
}
