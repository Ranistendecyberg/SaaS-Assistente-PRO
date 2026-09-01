-- SaaS Assistente Desktop - fundacao segura do banco
-- Projeto: saas-assistente-desktop-prod
-- Este script nao importa dados e nao altera o Firebase antigo.

begin;

create extension if not exists pgcrypto;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

revoke all on function public.set_updated_at() from public, anon, authenticated;

create table if not exists public.companies (
  id uuid primary key default gen_random_uuid(),
  name text not null check (char_length(trim(name)) between 2 and 160),
  manager_name text,
  phone text,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.installations (
  id uuid primary key default gen_random_uuid(),
  company_id uuid references public.companies(id) on delete set null,
  hardware_id text not null unique check (char_length(hardware_id) between 8 and 128),
  token_hash text unique,
  status text not null default 'pending'
    check (status in ('pending', 'active', 'blocked', 'revoked')),
  app_version text,
  online boolean not null default false,
  last_seen_at timestamptz,
  token_issued_at timestamptz,
  token_revoked_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.licenses (
  id uuid primary key default gen_random_uuid(),
  installation_id uuid not null unique
    references public.installations(id) on delete cascade,
  status text not null default 'trial'
    check (status in ('trial', 'active', 'expired', 'blocked', 'cancelled')),
  license_type text not null default 'trial'
    check (license_type in ('trial', 'subscription', 'courtesy')),
  expires_at timestamptz not null,
  offline_grace_hours integer not null default 72
    check (offline_grace_hours between 0 and 168),
  extra_messages integer not null default 0 check (extra_messages >= 0),
  monthly_price numeric(10,2) check (monthly_price is null or monthly_price >= 0),
  report_links jsonb not null default '{}'::jsonb,
  adjustment_notice text,
  detailed_diagnostics_until timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.license_keys (
  id uuid primary key default gen_random_uuid(),
  code_hash text not null unique,
  code_prefix text not null check (char_length(code_prefix) between 3 and 24),
  key_type text not null
    check (key_type in ('days', 'messages', 'fixed_expiry')),
  days_to_add integer check (days_to_add is null or days_to_add > 0),
  messages_to_add integer check (messages_to_add is null or messages_to_add > 0),
  fixed_expiry timestamptz,
  status text not null default 'new'
    check (status in ('new', 'used', 'expired', 'revoked')),
  intended_company text,
  usable_until timestamptz not null,
  redeemed_by uuid references public.installations(id) on delete set null,
  redeemed_at timestamptz,
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint license_key_payload_check check (
    (key_type = 'days' and days_to_add is not null
      and messages_to_add is null and fixed_expiry is null)
    or
    (key_type = 'messages' and messages_to_add is not null
      and days_to_add is null and fixed_expiry is null)
    or
    (key_type = 'fixed_expiry' and fixed_expiry is not null
      and days_to_add is null and messages_to_add is null)
  )
);

create table if not exists public.daily_usage (
  installation_id uuid not null
    references public.installations(id) on delete cascade,
  usage_date date not null,
  sent_count integer not null default 0 check (sent_count >= 0),
  updated_at timestamptz not null default now(),
  primary key (installation_id, usage_date)
);

create table if not exists public.telemetry_events (
  id uuid primary key default gen_random_uuid(),
  installation_id uuid not null
    references public.installations(id) on delete cascade,
  occurred_at timestamptz not null,
  received_at timestamptz not null default now(),
  level text not null check (level in ('INFO', 'WARN', 'ERROR')),
  component text not null check (char_length(component) between 1 and 60),
  event_name text not null check (char_length(event_name) between 1 and 80),
  session_id text check (session_id is null or char_length(session_id) <= 64),
  app_version text,
  diagnostic_mode boolean not null default false,
  environment jsonb not null default '{}'::jsonb,
  details jsonb not null default '{}'::jsonb,
  expires_at timestamptz not null
);

create table if not exists public.suggestions (
  id uuid primary key default gen_random_uuid(),
  installation_id uuid not null
    references public.installations(id) on delete cascade,
  suggestion_text text not null check (char_length(trim(suggestion_text)) between 3 and 4000),
  status text not null default 'new'
    check (status in ('new', 'reviewing', 'accepted', 'rejected', 'done')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.system_config (
  singleton boolean primary key default true check (singleton),
  current_version text not null default '0.0.0',
  minimum_version text not null default '0.0.0',
  update_required boolean not null default false,
  installer_url text,
  installer_sha256 text check (
    installer_sha256 is null or installer_sha256 ~ '^[a-fA-F0-9]{64}$'
  ),
  installer_signature text,
  default_monthly_price numeric(10,2) not null default 250.00
    check (default_monthly_price >= 0),
  global_notice text,
  maintenance_mode boolean not null default false,
  maintenance_message text,
  updated_at timestamptz not null default now(),
  updated_by uuid references auth.users(id) on delete set null
);

insert into public.system_config (singleton)
values (true)
on conflict (singleton) do nothing;

create table if not exists public.admin_users (
  user_id uuid primary key references auth.users(id) on delete cascade,
  role text not null default 'support'
    check (role in ('owner', 'admin', 'support', 'viewer')),
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.audit_events (
  id bigint generated always as identity primary key,
  actor_user_id uuid references auth.users(id) on delete set null,
  actor_installation_id uuid references public.installations(id) on delete set null,
  action text not null check (char_length(action) between 2 and 100),
  target_type text not null check (char_length(target_type) between 2 and 60),
  target_id text,
  success boolean not null default true,
  metadata jsonb not null default '{}'::jsonb,
  occurred_at timestamptz not null default now()
);

create index if not exists idx_installations_company
  on public.installations(company_id);
create index if not exists idx_installations_last_seen
  on public.installations(last_seen_at desc);
create index if not exists idx_license_keys_status_expiry
  on public.license_keys(status, usable_until);
create index if not exists idx_telemetry_installation_time
  on public.telemetry_events(installation_id, occurred_at desc);
create index if not exists idx_telemetry_level_time
  on public.telemetry_events(level, occurred_at desc);
create index if not exists idx_telemetry_expiry
  on public.telemetry_events(expires_at);
create index if not exists idx_audit_time
  on public.audit_events(occurred_at desc);
create index if not exists idx_audit_target
  on public.audit_events(target_type, target_id);

drop trigger if exists companies_set_updated_at on public.companies;
create trigger companies_set_updated_at
before update on public.companies
for each row execute function public.set_updated_at();

drop trigger if exists installations_set_updated_at on public.installations;
create trigger installations_set_updated_at
before update on public.installations
for each row execute function public.set_updated_at();

drop trigger if exists licenses_set_updated_at on public.licenses;
create trigger licenses_set_updated_at
before update on public.licenses
for each row execute function public.set_updated_at();

drop trigger if exists license_keys_set_updated_at on public.license_keys;
create trigger license_keys_set_updated_at
before update on public.license_keys
for each row execute function public.set_updated_at();

drop trigger if exists suggestions_set_updated_at on public.suggestions;
create trigger suggestions_set_updated_at
before update on public.suggestions
for each row execute function public.set_updated_at();

drop trigger if exists admin_users_set_updated_at on public.admin_users;
create trigger admin_users_set_updated_at
before update on public.admin_users
for each row execute function public.set_updated_at();

alter table public.companies enable row level security;
alter table public.companies force row level security;
alter table public.installations enable row level security;
alter table public.installations force row level security;
alter table public.licenses enable row level security;
alter table public.licenses force row level security;
alter table public.license_keys enable row level security;
alter table public.license_keys force row level security;
alter table public.daily_usage enable row level security;
alter table public.daily_usage force row level security;
alter table public.telemetry_events enable row level security;
alter table public.telemetry_events force row level security;
alter table public.suggestions enable row level security;
alter table public.suggestions force row level security;
alter table public.system_config enable row level security;
alter table public.system_config force row level security;
alter table public.admin_users enable row level security;
alter table public.admin_users force row level security;
alter table public.audit_events enable row level security;
alter table public.audit_events force row level security;

-- Nenhuma tabela pode ser acessada diretamente pelo Desktop ou por um usuario.
-- As futuras Edge Functions usarao a service_role somente no servidor.
revoke all on table public.companies from anon, authenticated;
revoke all on table public.installations from anon, authenticated;
revoke all on table public.licenses from anon, authenticated;
revoke all on table public.license_keys from anon, authenticated;
revoke all on table public.daily_usage from anon, authenticated;
revoke all on table public.telemetry_events from anon, authenticated;
revoke all on table public.suggestions from anon, authenticated;
revoke all on table public.system_config from anon, authenticated;
revoke all on table public.admin_users from anon, authenticated;
revoke all on table public.audit_events from anon, authenticated;

revoke all on all sequences in schema public from anon, authenticated;
alter default privileges in schema public
  revoke all on tables from anon, authenticated;
alter default privileges in schema public
  revoke all on sequences from anon, authenticated;
alter default privileges in schema public
  revoke execute on functions from public, anon, authenticated;

comment on schema public is
  'Acesso direto bloqueado. Operacoes do SaaS Desktop devem passar por Edge Functions.';

commit;

