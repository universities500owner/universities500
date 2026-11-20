# Student accounts: one-time setup

The site's account pages and `/api` functions are in the repository. They stay switched off, and the sign-in page says
"Sign-in is not open yet", until the three settings in step 5 exist. Nothing else on the site depends on them.

1. **Supabase project.** Create one named `universities500` in the Mumbai (South Asia) region.
2. **Resend.** Verify the `universities500.com` domain, then create an API key with Sending access.
3. **Supabase email settings.**
   - Authentication > Emails > SMTP Settings: custom SMTP on. Host `smtp.resend.com`, port `465`, username `resend`, password = the Resend API key. Sender `login@universities500.com`, name `Universities500`.
   - Authentication > Sign In / Providers: turn **off** "Allow new users to sign up". Email OTP length 6, expiry 600 seconds.
   - Authentication > Emails > Templates > Magic Link: make the body show the code with `{{ .Token }}` (for example "Your Universities500 sign-in code is {{ .Token }}. It works for 10 minutes.").
4. **Database.** Run `supabase/migrations/0001_students.sql` once in the SQL editor.
5. **Cloudflare Pages** > Settings > Variables and Secrets (Production), then redeploy:
   - `SUPABASE_URL` (the Project URL), `SUPABASE_ANON_KEY` (the **publishable** key, `sb_publishable_...`), `SUPABASE_SERVICE_KEY` (the **secret** key, `sb_secret_...`; Secret type; never anywhere else). The older `anon` and `service_role` keys also work in the same two settings.
   - Optional but recommended: `TURNSTILE_SECRET` (Secret) and `TURNSTILE_SITE_KEY` (plain text) from a Turnstile widget for `universities500.com`.
6. **Rate limit.** In Cloudflare > Security > WAF > Rate limiting rules, limit `/api/auth/` to about 10 requests per minute per IP.

Unconfirmed sign-ups leave a Supabase Auth user with no student record. Delete users who never signed in from
Authentication > Users now and then (or schedule a clean-up).
