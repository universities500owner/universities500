-- Universities500 "My shortlist": courses, MBA programmes, scholarships and internships a student has saved, with a status and a note.
-- Run once in the Supabase SQL editor after 0001_students.sql. Safe to run again.

create table if not exists public.saved_items (
  student_id uuid not null references public.students (id) on delete cascade,
  item_id    text not null check (item_id ~ '^(crs|sch|mba|int):[A-Za-z0-9._~/-]{1,120}$'),
  kind       text not null check (kind in ('crs', 'sch', 'mba', 'int')),
  title      text not null check (char_length(title) between 1 and 160),
  sub        text not null default '' check (char_length(sub) <= 160),
  url        text not null default '' check (char_length(url) <= 300),
  status     text not null,
  note       text not null default '' check (char_length(note) <= 500),
  saved_at   timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (student_id, item_id),
  check (
    (kind in ('crs', 'mba') and status in ('shortlisted', 'preparing', 'applied', 'offer', 'accepted', 'dropped')) or
    (kind = 'sch' and status in ('saved', 'applying', 'applied', 'awarded', 'dropped')) or
    (kind = 'int' and status in ('saved', 'applying', 'applied', 'offer', 'dropped'))
  ),
  check (split_part(item_id, ':', 1) = kind)
);

alter table public.saved_items enable row level security;

drop policy if exists saved_all on public.saved_items;
create policy saved_all on public.saved_items for all to authenticated
  using (auth.uid() = student_id) with check (auth.uid() = student_id);

-- At most 200 saved items per student, whatever calls the database.
create or replace function public.saved_items_cap() returns trigger language plpgsql as $$
begin
  if (select count(*) from public.saved_items where student_id = new.student_id) >= 200 then
    raise exception 'saved_items limit reached' using errcode = 'check_violation';
  end if;
  return new;
end $$;

drop trigger if exists saved_items_cap on public.saved_items;
create trigger saved_items_cap before insert on public.saved_items for each row execute function public.saved_items_cap();

-- New Supabase projects do not give the API roles access to new tables automatically, so the grants are explicit.
grant select, insert, update, delete on public.saved_items to authenticated;
grant select, insert, update, delete on public.saved_items to service_role;
