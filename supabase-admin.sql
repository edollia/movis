-- Movis owner panel setup.
-- 1. Create your Supabase Auth user first.
-- 2. This script grants admin access to UID f7f96a98-985d-402f-9233-9cd0bc0439ce.

create table if not exists public.movis_admins (
  user_id uuid primary key references auth.users(id) on delete cascade,
  email text not null,
  created_at timestamptz not null default now()
);

create unique index if not exists movis_admins_email_lower_key
  on public.movis_admins (lower(email));

create table if not exists public.movis_settings (
  key text primary key,
  show_loading_screen boolean not null default true,
  loading_line_1 text not null default 'Knock, knock, Neo.',
  loading_line_2 text not null default 'Have you gooned today?',
  show_signal_support boolean not null default true,
  support_label text not null default 'support',
  support_handle text not null default '@pawswirl',
  support_url text not null default 'https://www.instagram.com/pawswirl/',
  updated_at timestamptz not null default now(),
  constraint movis_settings_site_key check (key = 'site'),
  constraint movis_loading_line_1_len check (char_length(loading_line_1) between 1 and 80),
  constraint movis_loading_line_2_len check (char_length(loading_line_2) between 1 and 80),
  constraint movis_support_label_len check (char_length(support_label) between 1 and 28),
  constraint movis_support_handle_len check (char_length(support_handle) between 1 and 42),
  constraint movis_support_url_http check (support_url ~ '^https?://')
);

create or replace function public.movis_touch_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists movis_settings_touch_updated_at on public.movis_settings;
create trigger movis_settings_touch_updated_at
before update on public.movis_settings
for each row
execute function public.movis_touch_updated_at();

insert into public.movis_settings (key)
values ('site')
on conflict (key) do nothing;

alter table public.movis_admins enable row level security;
alter table public.movis_settings enable row level security;

create or replace function public.is_movis_admin()
returns boolean
language sql
stable
security definer
set search_path = public, auth
as $$
  select exists (
    select 1
    from public.movis_admins
    where user_id = auth.uid()
  );
$$;

revoke all on function public.is_movis_admin() from public;
grant execute on function public.is_movis_admin() to anon, authenticated;

drop policy if exists "movis admins can read own row" on public.movis_admins;
create policy "movis admins can read own row"
on public.movis_admins
for select
to authenticated
using (user_id = (select auth.uid()));

drop policy if exists "public can read movis settings" on public.movis_settings;
create policy "public can read movis settings"
on public.movis_settings
for select
to anon, authenticated
using (key = 'site');

drop policy if exists "movis admins can insert settings" on public.movis_settings;
create policy "movis admins can insert settings"
on public.movis_settings
for insert
to authenticated
with check (key = 'site' and public.is_movis_admin());

drop policy if exists "movis admins can update settings" on public.movis_settings;
create policy "movis admins can update settings"
on public.movis_settings
for update
to authenticated
using (key = 'site' and public.is_movis_admin())
with check (key = 'site' and public.is_movis_admin());

grant select on public.movis_admins to authenticated;
grant select on public.movis_settings to anon, authenticated;
grant insert, update on public.movis_settings to authenticated;

do $$
declare
  admin_user_id uuid := 'f7f96a98-985d-402f-9233-9cd0bc0439ce';
  admin_email text;
begin
  select email into admin_email
  from auth.users
  where id = admin_user_id
  limit 1;

  if admin_email is null then
    raise exception 'No Supabase Auth user found for UID %. Create the user, then rerun this script.', admin_user_id;
  end if;

  insert into public.movis_admins (user_id, email)
  values (admin_user_id, admin_email)
  on conflict (user_id) do update
  set email = excluded.email;

  delete from public.movis_admins
  where user_id <> admin_user_id;
end $$;
