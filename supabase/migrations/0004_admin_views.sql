-- Universities500 admin list (/admin/): two read-only views that the site's own server reads with the secret key.
-- Run once in the Supabase SQL Editor, after 0001 to 0003. Safe to run again.
--
-- Nobody but the server can read these. They are not granted to the public (anon) or signed-in (authenticated) roles,
-- and they are security_invoker views, so even a mistaken grant would still be held to each student's row level security.
-- They hold no passport, phone or document data (none is collected) and no free-text answers: only contact, interests
-- and counts. The detail panel on /admin/ reads one student's rows through the server, one at a time.

create or replace view public.admin_students with (security_invoker = true) as
select
  s.id,
  s.email,
  s.display_name,
  (select p.data ->> 'full_name' from public.profile_sections p where p.student_id = s.id and p.section = 'profile') as full_name,
  s.created_at,
  s.updated_at,
  s.onboarded_at,
  s.consent_at,
  s.consent_version,
  s.marketing_opt_in,
  s.countries,
  s.level,
  s.stage,
  s.subject_groups,
  (select count(*) from public.saved_items i where i.student_id = s.id)::int as shortlist_count,
  coalesce((select array_agg(p.section order by p.section) from public.profile_sections p where p.student_id = s.id), '{}'::text[]) as sections
from public.students s;

create or replace view public.admin_stats with (security_invoker = true) as
select
  count(*)::int                                                                      as total,
  count(*) filter (where s.created_at >= now() - interval '7 days')::int             as last_7,
  count(*) filter (where s.created_at >= now() - interval '30 days')::int            as last_30,
  count(*) filter (where s.onboarded_at is not null)::int                            as onboarded,
  count(*) filter (where s.marketing_opt_in)::int                                    as marketing,
  count(*) filter (where exists (select 1 from public.saved_items i where i.student_id = s.id))::int as with_shortlist,
  count(*) filter (where exists (select 1 from public.profile_sections p where p.student_id = s.id and p.section = 'visa_au'))::int as with_visa_check
from public.students s;

revoke all on public.admin_students from public, anon, authenticated;
revoke all on public.admin_stats from public, anon, authenticated;
grant select on public.admin_students to service_role;
grant select on public.admin_stats to service_role;
