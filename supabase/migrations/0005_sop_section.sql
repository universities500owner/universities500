-- Student accounts, phase 5: the SOP builder keeps the student's course, answers and draft as one more section of the profile.
-- Run this once in the Supabase SQL Editor, after 0001 to 0004. It is safe to run again.
--
-- It only widens the list of section names the table accepts. No data changes and no new grants are needed:
-- profile_sections already has the grants and row-level security from 0001.
-- The staff console never shows what is in this section (src/lib/account/admin.js lists it as "Added").

alter table public.profile_sections drop constraint if exists profile_sections_section_check;
alter table public.profile_sections
  add constraint profile_sections_section_check
  check (section in ('profile', 'academic', 'english', 'work', 'immigration', 'visa_au', 'sop'));
