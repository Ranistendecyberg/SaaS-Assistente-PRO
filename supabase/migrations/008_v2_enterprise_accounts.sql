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
