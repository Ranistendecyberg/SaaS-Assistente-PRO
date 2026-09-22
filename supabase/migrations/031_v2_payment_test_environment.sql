-- Ambiente de homologacao financeira por empresa.
-- A selecao acontece exclusivamente no servidor e expira automaticamente.
begin;

alter table public.billing_payment_attempts
  add column if not exists provider_environment text not null default 'production',
  add column if not exists provider_resource_type text not null default 'payment';

update public.billing_payment_attempts
set provider_resource_type = case when payment_method = 'boleto' then 'order' else 'payment' end;

do $$ begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'billing_attempts_provider_environment_check'
  ) then
    alter table public.billing_payment_attempts
      add constraint billing_attempts_provider_environment_check
      check (provider_environment in ('production', 'test'));
  end if;
end $$;

do $$ begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'billing_attempts_provider_resource_check'
  ) then
    alter table public.billing_payment_attempts
      add constraint billing_attempts_provider_resource_check
      check (provider_resource_type in ('payment', 'order'));
  end if;
end $$;

create table if not exists public.billing_payment_test_companies (
  company_id uuid primary key references public.companies(id) on delete cascade,
  expires_at timestamptz not null,
  reason text not null check (length(trim(reason)) between 3 and 300),
  created_at timestamptz not null default now(),
  check (expires_at > created_at)
);

alter table public.billing_payment_test_companies enable row level security;
alter table public.billing_payment_test_companies force row level security;
revoke all on table public.billing_payment_test_companies from public, anon, authenticated;
grant select, insert, update, delete on table public.billing_payment_test_companies to service_role;

create or replace function public.capture_billing_attempt_snapshot()
returns trigger language plpgsql security definer set search_path = public as $$
declare v_invoice public.billing_invoices%rowtype; v_company uuid; v_ids uuid[];
begin
  if TG_OP = 'UPDATE' then
    if new.invoice_snapshot is distinct from old.invoice_snapshot
      or new.invoice_id is distinct from old.invoice_id
      or new.external_reference is distinct from old.external_reference
      or new.idempotency_key is distinct from old.idempotency_key
      or new.provider_environment is distinct from old.provider_environment
      or new.provider_resource_type is distinct from old.provider_resource_type then
      raise exception 'IMMUTABLE_PAYMENT_SNAPSHOT';
    end if;
    return new;
  end if;
  select company_id into v_company from public.billing_invoices where id = new.invoice_id;
  perform 1 from public.company_subscriptions where company_id = v_company for update;
  select * into v_invoice from public.billing_invoices where id = new.invoice_id for update;
  select coalesce(array_agg(id order by id),'{}'::uuid[]) into v_ids from public.installations
    where company_id = v_company and billing_status <> 'removed';
  if v_invoice.status <> 'open' or v_invoice.installation_ids is null
    or v_invoice.installation_ids is distinct from v_ids then raise exception 'INVOICE_CHANGED'; end if;
  new.provider_environment := case when exists (
    select 1 from public.billing_payment_test_companies
    where company_id = v_company and expires_at > clock_timestamp()
  ) then 'test' else 'production' end;
  new.provider_resource_type := case
    when new.payment_method = 'boleto' or new.provider_environment = 'test' then 'order'
    else 'payment' end;
  new.invoice_snapshot := jsonb_build_object('installation_ids',v_invoice.installation_ids,
    'total_amount',v_invoice.total_amount,'period_start',v_invoice.period_start,'period_end',v_invoice.period_end,
    'provider_environment',new.provider_environment,
    'provider_resource_type',new.provider_resource_type);
  return new;
end $$;

revoke all on function public.capture_billing_attempt_snapshot() from public,anon,authenticated,service_role;

create or replace function public.claim_payment_status_check_server(
  p_user_id uuid, p_company_id uuid, p_attempt_id uuid
) returns jsonb language plpgsql security definer set search_path = public
as $$
declare v_attempt public.billing_payment_attempts%rowtype;
begin
  if not exists (select 1 from public.company_members
    where company_id=p_company_id and user_id=p_user_id and active and role='owner') then
    return jsonb_build_object('ok',false,'error','OWNER_REQUIRED');
  end if;
  select a.* into v_attempt from public.billing_payment_attempts a
    join public.billing_invoices i on i.id=a.invoice_id
    where a.id=p_attempt_id and i.company_id=p_company_id for update of a;
  if not found then
    return jsonb_build_object('ok',false,'error','PAYMENT_NOT_FOUND');
  end if;
  if v_attempt.provider_order_id is null then
    return jsonb_build_object('ok',false,'error','PAYMENT_NOT_RECORDED');
  end if;
  if v_attempt.last_provider_check_at > clock_timestamp()-interval '30 seconds' then
    return jsonb_build_object('ok',false,'error','PAYMENT_RATE_LIMITED');
  end if;
  update public.billing_payment_attempts set last_provider_check_at=clock_timestamp()
    where id=p_attempt_id;
  return jsonb_build_object('ok',true,'provider_id',v_attempt.provider_order_id,
    'payment_method',v_attempt.payment_method,'external_reference',v_attempt.external_reference,
    'provider_environment',v_attempt.provider_environment,
    'provider_resource_type',v_attempt.provider_resource_type);
end;
$$;

revoke all on function public.claim_payment_status_check_server(uuid,uuid,uuid)
  from public,anon,authenticated;
grant execute on function public.claim_payment_status_check_server(uuid,uuid,uuid)
  to service_role;

commit;
