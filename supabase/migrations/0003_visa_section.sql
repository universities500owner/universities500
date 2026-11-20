-- Student accounts, phase 3: the visa self-check keeps its answers as one more section of the student's profile.
-- Run this once in the Supabase SQL Editor, after 0001 and 0002. It is safe to run again.
--
-- It only widens the list of section names the table accepts. No data changes and no new grants are needed:
-- profile_sections already has the grants and row-level security from 0001.

alter table public.profile_sections drop constraint if exists profile_sections_section_check;
alter table public.profile_sections
  add constraint profile_sections_section_check
  check (section in ('profile', 'academic', 'english', 'work', 'immigration', 'visa_au'));
