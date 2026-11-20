-- Universities500 student accounts. Run once in the Supabase SQL editor (Project > SQL Editor > New query).
-- Sign-up is closed in Supabase Auth; the site's own function creates a student after checking a Gmail address.
-- Row level security means a signed-in student can only ever read or change their own rows.

create table if not exists public.students (
  id              uuid primary key references auth.users (id) on delete cascade,
  email           text not null,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  consent_at      timestamptz not null,            -- when they confirmed they are 18+ and accept the Terms and Privacy page
  consent_version text not null,                   -- which version of those pages they saw
  marketing_opt_in boolean not null default false, -- separate, optional
  display_name    text check (char_length(display_name) <= 60),
  countries       text[] not null default '{}',    -- destination guide slugs
  level           text,
  subject_groups  text[] not null default '{}',
  subjects        text[] not null default '{}',
  stage           text,
  onboarded_at    timestamptz
);

create table if not exists public.profile_sections (
  student_id uuid not null references public.students (id) on delete cascade,
  section    text not null check (section in ('profile', 'academic', 'english', 'work', 'immigration')),
  data       jsonb not null default '{}'::jsonb check (pg_column_size(data) <= 16384),
  updated_at timestamptz not null default now(),
  primary key (student_id, section)
);

alter table public.students enable row level security;
alter table public.profile_sections enable row level security;

drop policy if exists students_select on public.students;
drop policy if exists students_update on public.students;
create policy students_select on public.students for select to authenticated using (auth.uid() = id);
create policy students_update on public.students for update to authenticated using (auth.uid() = id) with check (auth.uid() = id);
-- No insert or delete policy on purpose: rows are created and removed only by the site's server (service key).

drop policy if exists sections_all on public.profile_sections;
create policy sections_all on public.profile_sections for all to authenticated
  using (auth.uid() = student_id) with check (auth.uid() = student_id);

-- A student must not be able to rewrite the consent record or the email from the browser.
revoke update on public.students from authenticated;
grant update (display_name, countries, level, subject_groups, subjects, stage, onboarded_at, marketing_opt_in, updated_at)
  on public.students to authenticated;
grant select on public.students to authenticated;
grant select, insert, update, delete on public.profile_sections to authenticated;
