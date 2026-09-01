-- SaaS Assistente PRO 2.0 - fundação limpa para o SQL Editor
-- Projeto: hnwvtoiiuqagzmuqygkw
-- Não contém empresas, licenças, chaves ou identificadores do projeto 1.9.6.

-- ===== 001_secure_foundation.sql =====
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



-- ===== 002_secure_server_operations.sql =====
-- Operações atômicas usadas exclusivamente pelas Edge Functions.
-- Clientes anon/authenticated não recebem EXECUTE direto.

begin;

create or replace function public.redeem_license_key_server(
  p_installation_id uuid,
  p_code_hash text
) returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  key_row public.license_keys%rowtype;
  license_row public.licenses%rowtype;
  company_name text;
  new_expiry timestamptz;
  new_extra integer;
begin
  if p_installation_id is null or char_length(coalesce(p_code_hash, '')) <> 64 then
    return jsonb_build_object('ok', false, 'error', 'INVALID_KEY');
  end if;

  select * into key_row
  from public.license_keys
  where code_hash = p_code_hash
  for update;

  if not found then
    return jsonb_build_object('ok', false, 'error', 'INVALID_KEY');
  end if;
  if key_row.status <> 'new' then
    return jsonb_build_object('ok', false, 'error', 'KEY_' || upper(key_row.status));
  end if;
  if key_row.usable_until < now() then
    update public.license_keys set status = 'expired' where id = key_row.id;
    return jsonb_build_object('ok', false, 'error', 'KEY_EXPIRED');
  end if;

  select c.name into company_name
  from public.installations i
  join public.companies c on c.id = i.company_id
  where i.id = p_installation_id and i.status = 'active';
  if company_name is null then
    return jsonb_build_object('ok', false, 'error', 'INSTALLATION_NOT_FOUND');
  end if;
  if key_row.intended_company is not null
     and lower(trim(key_row.intended_company)) <> lower(trim(company_name)) then
    return jsonb_build_object('ok', false, 'error', 'KEY_COMPANY_MISMATCH');
  end if;

  select * into license_row
  from public.licenses
  where installation_id = p_installation_id
  for update;
  if not found then
    return jsonb_build_object('ok', false, 'error', 'LICENSE_NOT_FOUND');
  end if;

  if key_row.key_type = 'messages' then
    update public.licenses
    set extra_messages = extra_messages + key_row.messages_to_add
    where id = license_row.id
    returning expires_at, extra_messages into new_expiry, new_extra;
  elsif key_row.key_type = 'days' then
    new_expiry := greatest(license_row.expires_at, now())
      + make_interval(days => key_row.days_to_add);
    update public.licenses
    set status = 'active', license_type = 'subscription', expires_at = new_expiry
    where id = license_row.id
    returning extra_messages into new_extra;
  elsif key_row.key_type = 'fixed_expiry' then
    -- Regra comercial: nunca encurtar uma licença que já vence mais tarde.
    new_expiry := greatest(license_row.expires_at, key_row.fixed_expiry);
    update public.licenses
    set status = 'active', license_type = 'subscription', expires_at = new_expiry
    where id = license_row.id
    returning extra_messages into new_extra;
  else
    return jsonb_build_object('ok', false, 'error', 'INVALID_KEY_TYPE');
  end if;

  update public.license_keys
  set status = 'used', redeemed_by = p_installation_id, redeemed_at = now()
  where id = key_row.id;

  insert into public.audit_events (
    actor_installation_id, action, target_type, target_id, metadata
  ) values (
    p_installation_id, 'license.key_redeemed', 'license_key', key_row.id::text,
    jsonb_build_object('key_type', key_row.key_type, 'expires_at', new_expiry)
  );

  return jsonb_build_object(
    'ok', true, 'key_type', key_row.key_type,
    'expires_at', new_expiry, 'extra_messages', coalesce(new_extra, 0)
  );
end;
$$;

create or replace function public.consume_message_server(
  p_installation_id uuid,
  p_daily_limit integer
) returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  license_row public.licenses%rowtype;
  local_day date := timezone('America/Fortaleza', now())::date;
  current_count integer;
  remaining_extra integer;
begin
  if p_daily_limit < 1 or p_daily_limit > 1000 then
    return jsonb_build_object('ok', false, 'error', 'INVALID_DAILY_LIMIT');
  end if;

  select l.* into license_row
  from public.licenses l
  join public.installations i on i.id = l.installation_id
  where l.installation_id = p_installation_id
    and i.status = 'active'
  for update of l;

  if not found or license_row.status not in ('trial', 'active')
     or license_row.expires_at <= now() then
    return jsonb_build_object('ok', false, 'error', 'LICENSE_NOT_ACTIVE');
  end if;

  if license_row.extra_messages > 0 then
    update public.licenses
    set extra_messages = extra_messages - 1
    where id = license_row.id
    returning extra_messages into remaining_extra;
    return jsonb_build_object(
      'ok', true, 'allowed', true, 'source', 'extra',
      'extra_messages', remaining_extra
    );
  end if;

  insert into public.daily_usage (installation_id, usage_date, sent_count)
  values (p_installation_id, local_day, 0)
  on conflict (installation_id, usage_date) do nothing;

  select sent_count into current_count
  from public.daily_usage
  where installation_id = p_installation_id and usage_date = local_day
  for update;

  if current_count >= p_daily_limit then
    return jsonb_build_object(
      'ok', false, 'allowed', false, 'error', 'DAILY_LIMIT_REACHED',
      'sent_count', current_count, 'daily_limit', p_daily_limit
    );
  end if;

  update public.daily_usage
  set sent_count = sent_count + 1
  where installation_id = p_installation_id and usage_date = local_day
  returning sent_count into current_count;

  return jsonb_build_object(
    'ok', true, 'allowed', true, 'source', 'daily',
    'sent_count', current_count, 'daily_limit', p_daily_limit
  );
end;
$$;

revoke all on function public.redeem_license_key_server(uuid, text)
  from public, anon, authenticated;
revoke all on function public.consume_message_server(uuid, integer)
  from public, anon, authenticated;
grant execute on function public.redeem_license_key_server(uuid, text)
  to service_role;
grant execute on function public.consume_message_server(uuid, integer)
  to service_role;

commit;


-- ===== 003_service_role_privileges.sql =====
-- Permissoes explicitas para as Edge Functions.
-- anon e authenticated permanecem sem acesso direto.

begin;

grant usage on schema public to service_role;
grant all privileges on all tables in schema public to service_role;
grant all privileges on all sequences in schema public to service_role;
grant execute on all functions in schema public to service_role;

alter default privileges in schema public
  grant all privileges on tables to service_role;
alter default privileges in schema public
  grant all privileges on sequences to service_role;
alter default privileges in schema public
  grant execute on functions to service_role;

-- Reafirma o bloqueio dos clientes depois dos grants do servidor.
revoke all on all tables in schema public from anon, authenticated;
revoke all on all sequences in schema public from anon, authenticated;

commit;

select
  has_schema_privilege('service_role', 'public', 'usage') as servidor_acessa_schema,
  has_table_privilege('service_role', 'public.admin_users', 'select') as servidor_le_admins,
  has_table_privilege('anon', 'public.admin_users', 'select') as anon_le_admins,
  has_table_privilege('authenticated', 'public.admin_users', 'select') as usuario_le_admins;


-- ===== 004_legacy_migration_claims.sql =====
-- Vinculacao segura e de uso unico para instalacoes migradas do Firebase.

begin;

alter table public.installations
  add column if not exists migration_claim_hash text,
  add column if not exists migration_claim_until timestamptz,
  add column if not exists migration_claimed_at timestamptz,
  add column if not exists legacy_imported_at timestamptz;

create unique index if not exists idx_installations_migration_claim_hash
  on public.installations(migration_claim_hash)
  where migration_claim_hash is not null;

alter table public.installations
  drop constraint if exists installations_migration_claim_consistency;
alter table public.installations
  add constraint installations_migration_claim_consistency check (
    (migration_claim_hash is null and migration_claim_until is null)
    or
    (migration_claim_hash is not null and migration_claim_until is not null)
  );

grant all privileges on table public.installations to service_role;
revoke all on table public.installations from anon, authenticated;

commit;


-- ===== 007_secure_pix_payments.sql =====
-- Sessões PIX vinculadas à instalação. O cliente nunca altera a licença.
begin;

create table if not exists public.payment_sessions (
  provider_payment_id text primary key,
  installation_id uuid not null references public.installations(id) on delete cascade,
  amount numeric(10,2) not null check (amount > 0),
  status text not null default 'pending' check (status in ('pending', 'applied', 'expired', 'cancelled')),
  created_at timestamptz not null default now(),
  expires_at timestamptz not null default (now() + interval '24 hours'),
  applied_at timestamptz
);

create index if not exists payment_sessions_installation_idx
  on public.payment_sessions (installation_id, created_at desc);

alter table public.payment_sessions enable row level security;
alter table public.payment_sessions force row level security;
revoke all on table public.payment_sessions from public, anon, authenticated;
grant select, insert, update on table public.payment_sessions to service_role;

create or replace function public.apply_approved_payment_server(
  p_installation_id uuid,
  p_provider_payment_id text
) returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  payment_row public.payment_sessions%rowtype;
  new_expiry timestamptz;
begin
  select * into payment_row
  from public.payment_sessions
  where provider_payment_id = p_provider_payment_id
    and installation_id = p_installation_id
  for update;

  if not found then
    return jsonb_build_object('ok', false, 'error', 'PAYMENT_NOT_FOUND');
  end if;
  if payment_row.status = 'applied' then
    select expires_at into new_expiry from public.licenses
      where installation_id = p_installation_id;
    return jsonb_build_object('ok', true, 'already_applied', true, 'expires_at', new_expiry);
  end if;
  if payment_row.status <> 'pending' or payment_row.expires_at < now() then
    update public.payment_sessions set status = 'expired'
      where provider_payment_id = p_provider_payment_id and status = 'pending';
    return jsonb_build_object('ok', false, 'error', 'PAYMENT_SESSION_EXPIRED');
  end if;

  update public.licenses
  set status = 'active',
      license_type = 'subscription',
      expires_at = greatest(expires_at, now()) + interval '30 days',
      updated_at = now()
  where installation_id = p_installation_id
  returning expires_at into new_expiry;

  if new_expiry is null then
    return jsonb_build_object('ok', false, 'error', 'LICENSE_NOT_FOUND');
  end if;

  update public.payment_sessions
  set status = 'applied', applied_at = now()
  where provider_payment_id = p_provider_payment_id;

  insert into public.audit_events (
    actor_installation_id, action, target_type, target_id, metadata
  ) values (
    p_installation_id, 'license.pix_renewed', 'installation', p_installation_id::text,
    jsonb_build_object('provider_payment_id_hash', encode(extensions.digest(p_provider_payment_id, 'sha256'), 'hex'),
                       'amount', payment_row.amount, 'expires_at', new_expiry)
  );

  return jsonb_build_object('ok', true, 'already_applied', false, 'expires_at', new_expiry);
end;
$$;

revoke all on function public.apply_approved_payment_server(uuid, text)
  from public, anon, authenticated;
grant execute on function public.apply_approved_payment_server(uuid, text)
  to service_role;

commit;


-- ===== 008_v2_enterprise_accounts.sql =====
-- SaaS Assistente PRO 2.0 - contas empresariais e cobrança consolidada.
-- MIGRAÇÃO LOCAL: não publicar sem executar o checklist da versão 2.0.
-- Compatível com a v1.9.6: as tabelas licenses e payment_sessions antigas
-- permanecem intactas durante a transição.

begin;

create table if not exists public.business_units (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  unit_type text not null default 'branch'
    check (unit_type in ('headquarters', 'branch')),
  display_name text not null check (char_length(trim(display_name)) between 2 and 160),
  cnpj text check (cnpj is null or cnpj ~ '^[0-9]{14}$'),
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists business_units_cnpj_unique
  on public.business_units(cnpj) where cnpj is not null;
create index if not exists business_units_company_idx
  on public.business_units(company_id, active);

create table if not exists public.company_members (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null check (role in ('owner', 'admin', 'operator')),
  active boolean not null default true,
  invited_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (company_id, user_id)
);

create unique index if not exists company_single_active_owner
  on public.company_members(company_id)
  where role = 'owner' and active = true;
create index if not exists company_members_user_idx
  on public.company_members(user_id, active);

alter table public.installations
  add column if not exists business_unit_id uuid references public.business_units(id) on delete set null,
  add column if not exists device_class text,
  add column if not exists billing_status text,
  add column if not exists activated_by uuid references auth.users(id) on delete set null,
  add column if not exists activated_at timestamptz,
  add column if not exists removal_scheduled_for timestamptz,
  add column if not exists removed_at timestamptz;

update public.installations set device_class = 'additional' where device_class is null;
update public.installations set billing_status = 'active' where billing_status is null;

with first_installation as (
  select distinct on (company_id) id
  from public.installations
  where company_id is not null
  order by company_id, created_at, id
)
update public.installations i
set device_class = 'principal'
from first_installation f
where i.id = f.id;

alter table public.installations
  alter column device_class set default 'additional',
  alter column device_class set not null,
  alter column billing_status set default 'active',
  alter column billing_status set not null;

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'installations_device_class_check') then
    alter table public.installations add constraint installations_device_class_check
      check (device_class in ('principal', 'additional'));
  end if;
  if not exists (select 1 from pg_constraint where conname = 'installations_billing_status_check') then
    alter table public.installations add constraint installations_billing_status_check
      check (billing_status in ('active', 'pending_removal', 'blocked', 'removed'));
  end if;
end $$;

create unique index if not exists installations_single_principal
  on public.installations(company_id)
  where device_class = 'principal' and billing_status <> 'removed';
create index if not exists installations_unit_idx
  on public.installations(business_unit_id, billing_status);

-- Cria uma unidade provisória para cada empresa existente. O CNPJ será
-- solicitado no onboarding 2.0; não inventamos documento fiscal no backfill.
insert into public.business_units (company_id, unit_type, display_name)
select c.id, 'headquarters', c.name
from public.companies c
where not exists (
  select 1 from public.business_units u where u.company_id = c.id
);

update public.installations i
set business_unit_id = u.id
from public.business_units u
where i.company_id = u.company_id
  and u.unit_type = 'headquarters'
  and i.business_unit_id is null;

create table if not exists public.company_subscriptions (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null unique references public.companies(id) on delete cascade,
  status text not null default 'trial'
    check (status in ('trial', 'active', 'past_due', 'suspended', 'cancelled')),
  pricing_origin text not null default 'v2_standard'
    check (pricing_origin in ('v2_standard', 'legacy_preserved', 'custom')),
  base_price numeric(10,2) not null default 300.00 check (base_price >= 0),
  additional_seat_price numeric(10,2) not null default 50.00 check (additional_seat_price >= 0),
  trial_expires_at timestamptz,
  current_period_start timestamptz,
  current_period_end timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Em projeto novo aplica a tabela comercial 2.0. Em uma migração de projeto
-- existente, não altera silenciosamente o preço que já estava em produção.
update public.system_config
set default_monthly_price = 300.00
where singleton = true and current_version = '0.0.0';

insert into public.company_subscriptions (
  company_id, status, pricing_origin, base_price, additional_seat_price,
  trial_expires_at, current_period_end
)
select
  c.id,
  case
    when bool_or(l.status = 'active') then 'active'
    when bool_or(l.status = 'trial') then 'trial'
    else 'past_due'
  end,
  'legacy_preserved',
  coalesce(
    (array_agg(l.monthly_price order by i.created_at)
      filter (where l.monthly_price is not null))[1],
    (select default_monthly_price from public.system_config where singleton = true),
    300.00
  ),
  50.00,
  max(l.expires_at) filter (where l.license_type = 'trial'),
  max(l.expires_at)
from public.companies c
join public.installations i on i.company_id = c.id
join public.licenses l on l.installation_id = i.id
group by c.id
on conflict (company_id) do nothing;

create table if not exists public.device_link_codes (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  business_unit_id uuid references public.business_units(id) on delete cascade,
  code_hash text not null unique,
  code_prefix text not null check (char_length(code_prefix) between 3 and 24),
  status text not null default 'new'
    check (status in ('new', 'used', 'expired', 'revoked')),
  expires_at timestamptz not null,
  created_by uuid not null references auth.users(id) on delete cascade,
  redeemed_by_installation uuid references public.installations(id) on delete set null,
  redeemed_by_user uuid references auth.users(id) on delete set null,
  redeemed_at timestamptz,
  created_at timestamptz not null default now()
);
create index if not exists device_link_codes_lookup_idx
  on public.device_link_codes(status, expires_at);

create table if not exists public.billing_profiles (
  company_id uuid primary key references public.companies(id) on delete cascade,
  legal_name text not null check (char_length(trim(legal_name)) between 2 and 180),
  billing_cnpj text not null check (billing_cnpj ~ '^[0-9]{14}$'),
  billing_email text not null check (position('@' in billing_email) > 1),
  postal_code text not null check (postal_code ~ '^[0-9]{8}$'),
  street text not null,
  street_number text not null,
  address_extra text,
  neighborhood text not null,
  city text not null,
  state text not null check (state ~ '^[A-Z]{2}$'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.billing_invoices (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  period_start date not null,
  period_end date not null,
  due_at timestamptz not null,
  principal_seats integer not null default 1 check (principal_seats in (0, 1)),
  additional_seats integer not null default 0 check (additional_seats >= 0),
  base_price numeric(10,2) not null check (base_price >= 0),
  additional_seat_price numeric(10,2) not null check (additional_seat_price >= 0),
  total_amount numeric(10,2) not null check (total_amount >= 0),
  status text not null default 'open'
    check (status in ('draft', 'open', 'paid', 'void', 'expired', 'refunded')),
  paid_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (company_id, period_start, period_end)
);
create index if not exists billing_invoices_company_idx
  on public.billing_invoices(company_id, created_at desc);

create table if not exists public.billing_payment_attempts (
  id uuid primary key default gen_random_uuid(),
  invoice_id uuid not null references public.billing_invoices(id) on delete cascade,
  provider text not null default 'mercado_pago',
  payment_method text not null check (payment_method in ('pix', 'boleto')),
  provider_payment_id text unique,
  external_reference text not null unique,
  idempotency_key text not null unique,
  status text not null default 'pending'
    check (status in ('pending', 'approved', 'rejected', 'cancelled', 'expired', 'refunded')),
  payment_url text,
  pix_copy_paste text,
  boleto_barcode text,
  expires_at timestamptz,
  provider_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists billing_attempts_invoice_idx
  on public.billing_payment_attempts(invoice_id, created_at desc);

-- Reutiliza o gatilho seguro de updated_at já criado na fundação.
drop trigger if exists business_units_set_updated_at on public.business_units;
create trigger business_units_set_updated_at before update on public.business_units
for each row execute function public.set_updated_at();
drop trigger if exists company_members_set_updated_at on public.company_members;
create trigger company_members_set_updated_at before update on public.company_members
for each row execute function public.set_updated_at();
drop trigger if exists company_subscriptions_set_updated_at on public.company_subscriptions;
create trigger company_subscriptions_set_updated_at before update on public.company_subscriptions
for each row execute function public.set_updated_at();
drop trigger if exists billing_profiles_set_updated_at on public.billing_profiles;
create trigger billing_profiles_set_updated_at before update on public.billing_profiles
for each row execute function public.set_updated_at();
drop trigger if exists billing_invoices_set_updated_at on public.billing_invoices;
create trigger billing_invoices_set_updated_at before update on public.billing_invoices
for each row execute function public.set_updated_at();
drop trigger if exists billing_attempts_set_updated_at on public.billing_payment_attempts;
create trigger billing_attempts_set_updated_at before update on public.billing_payment_attempts
for each row execute function public.set_updated_at();

alter table public.business_units enable row level security;
alter table public.business_units force row level security;
alter table public.company_members enable row level security;
alter table public.company_members force row level security;
alter table public.company_subscriptions enable row level security;
alter table public.company_subscriptions force row level security;
alter table public.device_link_codes enable row level security;
alter table public.device_link_codes force row level security;
alter table public.billing_profiles enable row level security;
alter table public.billing_profiles force row level security;
alter table public.billing_invoices enable row level security;
alter table public.billing_invoices force row level security;
alter table public.billing_payment_attempts enable row level security;
alter table public.billing_payment_attempts force row level security;

revoke all on table public.business_units from public, anon, authenticated;
revoke all on table public.company_members from public, anon, authenticated;
revoke all on table public.company_subscriptions from public, anon, authenticated;
revoke all on table public.device_link_codes from public, anon, authenticated;
revoke all on table public.billing_profiles from public, anon, authenticated;
revoke all on table public.billing_invoices from public, anon, authenticated;
revoke all on table public.billing_payment_attempts from public, anon, authenticated;

grant select, insert, update, delete on table public.business_units to service_role;
grant select, insert, update, delete on table public.company_members to service_role;
grant select, insert, update, delete on table public.company_subscriptions to service_role;
grant select, insert, update, delete on table public.device_link_codes to service_role;
grant select, insert, update, delete on table public.billing_profiles to service_role;
grant select, insert, update, delete on table public.billing_invoices to service_role;
grant select, insert, update, delete on table public.billing_payment_attempts to service_role;

comment on table public.company_subscriptions is
  'Contrato consolidado da empresa; não substitui licenses até a migração 2.0 ser concluída.';
comment on table public.device_link_codes is
  'Códigos descartáveis de 24h; somente o hash é persistido.';

commit;


-- ===== 009_verify_v2_foundation.sql =====
-- Verificação sem dados pessoais da fundação 2.0.

select
  to_regclass('public.companies') is not null as companies_ok,
  to_regclass('public.business_units') is not null as units_ok,
  to_regclass('public.company_members') is not null as members_ok,
  to_regclass('public.installations') is not null as installations_ok,
  to_regclass('public.company_subscriptions') is not null as subscriptions_ok,
  to_regclass('public.device_link_codes') is not null as link_codes_ok,
  to_regclass('public.billing_profiles') is not null as billing_profiles_ok,
  to_regclass('public.billing_invoices') is not null as invoices_ok,
  to_regclass('public.billing_payment_attempts') is not null as payment_attempts_ok;

select
  count(*) filter (where rowsecurity) as tabelas_com_rls,
  count(*) as total_tabelas_publicas
from pg_tables
where schemaname = 'public';

select
  has_table_privilege('anon', 'public.companies', 'select') as anon_le_empresas,
  has_table_privilege('authenticated', 'public.company_members', 'select') as usuario_le_membros,
  has_table_privilege('service_role', 'public.company_subscriptions', 'select') as servidor_le_assinaturas,
  has_function_privilege(
    'anon', 'public.consume_message_server(uuid,integer)', 'execute'
  ) as anon_consumiria_mensagem,
  has_function_privilege(
    'service_role', 'public.consume_message_server(uuid,integer)', 'execute'
  ) as servidor_consumiria_mensagem;

select current_version, default_monthly_price, maintenance_mode
from public.system_config
where singleton = true;
