# Student accounts: one-time setup

The site's account pages and `/api` functions are in the repository. They stay switched off, and the sign-in page says
"Sign-in is not open yet", until the three settings in step 5 exist. Nothing else on the site depends on them.

1. **Supabase project.** Create one named `universities500` in the Mumbai (South Asia) region.
2. **Resend.** Verify the `universities500.com` domain, then create an API key with Sending access.
3. **Supabase email settings.**
   - Authentication > Emails > SMTP Settings: custom SMTP on. Host `smtp.resend.com`, port `465`, username `resend`, password = the Resend API key. Sender `login@universities500.com`, name `Universities500`.
   - Authentication > Sign In / Providers: turn **off** "Allow new users to sign up". Email OTP length 6 (the site accepts 6 to 10 digits), expiry 600 seconds.
   - Authentication > Emails > Templates > **Magic Link** (the one template students receive): set Subject to `Your Universities500 sign-in code`, then replace the whole message body with the contents of `supabase/email-templates/sign-in-code.html` and save. It is the site's blue band, mint title bar and yellow button, and shows the code with `{{ .Token }}`. The other templates (Confirm sign up, Invite, and so on) are never sent, because the server creates accounts itself. To check it, send yourself a code from the sign-in page.
4. **Database.** Run `supabase/migrations/0001_students.sql` once in the SQL editor (it is safe to run again). It includes explicit grants, because new Supabase projects no longer give the API roles access to new tables automatically. Then run `supabase/migrations/0002_saved_items.sql` the same way (the shortlist table). Then `supabase/migrations/0003_visa_section.sql` (lets the visa self-check save its answers). Then `supabase/migrations/0004_admin_views.sql` (the two read-only views behind the owner's `/admin/` student list). Run each one once, in order.
5. **Cloudflare** > Workers & Pages > universities500 > Settings > Variables and Secrets (the Worker's runtime settings, not the build settings), then redeploy:
   - `SUPABASE_URL` (the Project URL), `SUPABASE_ANON_KEY` (the **publishable** key, `sb_publishable_...`), `SUPABASE_SERVICE_KEY` (the **secret** key, `sb_secret_...`; Secret type; never anywhere else). The older `anon` and `service_role` keys also work in the same two settings.
   - Optional but recommended: `TURNSTILE_SECRET` (Secret) and `TURNSTILE_SITE_KEY` (plain text) from a Turnstile widget for `universities500.com`.
6. **Owner access to `/admin/`.** Add `ADMIN_EMAILS` to the same runtime settings: the Gmail address(es) of the site owner, separated by commas. Dots and `+tags` are ignored when matching. Leave it empty or unset and nobody can open the page. Anyone else, or anyone signed out, sees "Not available". Optional extra lock: a Cloudflare Access policy on `universities500.com/admin/*` and `/api/admin/*`.
7. **Rate limit.** In Cloudflare > Security > WAF > Rate limiting rules, limit `/api/auth/` to about 10 requests per minute per IP.

The admin list shows contact details, interests, progress and whether the student agreed to updates. Immigration and visa self-check answers show only as "Added", and private notes on saved items are never sent. Opening a student and downloading the CSV each write a line to the Worker logs. Email only students who agreed to updates.

Unconfirmed sign-ups leave a Supabase Auth user with no student record. Delete users who never signed in from
Authentication > Users now and then (or schedule a clean-up).
