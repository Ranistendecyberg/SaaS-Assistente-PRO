-- SaaS Assistente PRO 2.0 - faturamento empresarial consolidado.
-- Aplicar somente no projeto Supabase isolado da versao 2.0.

begin;

alter table public.billing_payment_attempts
  add column if not exists provider_order_id text,
  add column if not exists provider_status text,
  add column if not exists provider_status_detail text,
  add column if not exists approved_at timestamptz;

create unique index if not exists billing_attempts_provider_order_unique
  on public.billing_payment_attempts(provider_order_id)
  where provider_order_id is not null;

create unique index if not exists billing_attempts_one_pending_method
  on public.billing_payment_attempts(invoice_id, payment_method)
  where status = 'pending';

create or replace function public.prepare_company_invoice_server(
  p_user_id uuid,
  p_company_id uuid
) returns jsonb
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  v_subscription public.company_subscriptions%rowtype;
  v_invoice public.billing_invoices%rowtype;
  v_principal integer;
  v_additional integer;
  v_period_start date;
  v_period_end date;
  v_total numeric(10,2);
begin
  if not exists (
    select 1 from public.company_members
    where company_id = p_company_id and user_id = p_user_id
      and role = 'owner' and active = true
  ) then
    return jsonb_build_object('ok', false, 'error', 'OWNER_REQUIRED');
  end if;

  select * into v_subscription
  from public.company_subscriptions
  where company_id = p_company_id
  for update;
  if not found then
    return jsonb_build_object('ok', false, 'error', 'SUBSCRIPTION_NOT_FOUND');
  end if;
  if v_subscription.status in ('suspended', 'cancelled') then
    return jsonb_build_object('ok', false, 'error', 'SUBSCRIPTION_NOT_BILLABLE');
  end if;

  select
    count(*) filter (where device_class = 'principal'),
    count(*) filter (where device_class = 'additional')
  into v_principal, v_additional
  from public.installations
  where company_id = p_company_id and billing_status <> 'removed';
  v_principal := least(coalesce(v_principal, 0), 1);
  v_additional := coalesce(v_additional, 0);
  if v_principal = 0 then
    return jsonb_build_object('ok', false, 'error', 'PRINCIPAL_DEVICE_REQUIRED');
  end if;

  v_period_start := greatest(
    current_date,
    coalesce(v_subscription.current_period_end::date,
             v_subscription.trial_expires_at::date, current_date)
  );
  v_period_end := (v_period_start + interval '1 month')::date;
  v_total := round(
    v_subscription.base_price * v_principal
      + v_subscription.additional_seat_price * v_additional,
    2
  );

  insert into public.billing_invoices (
    company_id, period_start, period_end, due_at,
    principal_seats, additional_seats, base_price,
    additional_seat_price, total_amount, status
  ) values (
    p_company_id, v_period_start, v_period_end, now() + interval '3 days',
    v_principal, v_additional, v_subscription.base_price,
    v_subscription.additional_seat_price, v_total, 'open'
  )
  on conflict (company_id, period_start, period_end) do nothing;

  select * into v_invoice from public.billing_invoices
  where company_id = p_company_id
    and period_start = v_period_start and period_end = v_period_end;

  return jsonb_build_object('ok', true, 'invoice', to_jsonb(v_invoice));
end;
$$;

create or replace function public.prepare_billing_attempt_server(
  p_user_id uuid,
  p_invoice_id uuid,
  p_payment_method text
) returns jsonb
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  v_invoice public.billing_invoices%rowtype;
  v_attempt public.billing_payment_attempts%rowtype;
  v_external_reference text;
  v_idempotency_key text;
begin
  if p_payment_method not in ('pix', 'boleto') then
    return jsonb_build_object('ok', false, 'error', 'INVALID_PAYMENT_METHOD');
  end if;

  select * into v_invoice from public.billing_invoices
  where id = p_invoice_id for update;
  if not found then
    return jsonb_build_object('ok', false, 'error', 'INVOICE_NOT_FOUND');
  end if;
  if not exists (
    select 1 from public.company_members
    where company_id = v_invoice.company_id and user_id = p_user_id
      and role = 'owner' and active = true
  ) then
    return jsonb_build_object('ok', false, 'error', 'OWNER_REQUIRED');
  end if;
  if v_invoice.status <> 'open' then
    return jsonb_build_object('ok', false, 'error', 'INVOICE_NOT_OPEN');
  end if;

  select * into v_attempt from public.billing_payment_attempts
  where invoice_id = p_invoice_id and payment_method = p_payment_method
    and status = 'pending'
  order by created_at desc limit 1;

  if not found then
    v_external_reference := 'invoice:' || p_invoice_id::text || ':' || gen_random_uuid()::text;
    v_idempotency_key := gen_random_uuid()::text;
    insert into public.billing_payment_attempts (
      invoice_id, payment_method, external_reference, idempotency_key,
      status, expires_at
    ) values (
      p_invoice_id, p_payment_method, v_external_reference,
      v_idempotency_key, 'pending', now() + interval '3 days'
    ) returning * into v_attempt;
  end if;

  return jsonb_build_object(
    'ok', true,
    'invoice', to_jsonb(v_invoice),
    'attempt', to_jsonb(v_attempt)
  );
end;
$$;

create or replace function public.record_provider_order_server(
  p_attempt_id uuid,
  p_provider_order_id text,
  p_provider_payment_id text,
  p_provider_status text,
  p_provider_status_detail text,
  p_payment_url text,
  p_pix_copy_paste text,
  p_boleto_barcode text
) returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_attempt public.billing_payment_attempts%rowtype;
begin
  update public.billing_payment_attempts set
    provider_order_id = coalesce(provider_order_id, p_provider_order_id),
    provider_payment_id = coalesce(provider_payment_id, p_provider_payment_id),
    provider_status = p_provider_status,
    provider_status_detail = p_provider_status_detail,
    payment_url = p_payment_url,
    pix_copy_paste = p_pix_copy_paste,
    boleto_barcode = p_boleto_barcode,
    provider_payload = jsonb_build_object(
      'order_status', p_provider_status,
      'order_status_detail', p_provider_status_detail
    )
  where id = p_attempt_id and status = 'pending'
    and (provider_order_id is null or provider_order_id = p_provider_order_id)
  returning * into v_attempt;
  if not found then
    return jsonb_build_object('ok', false, 'error', 'ATTEMPT_CONFLICT');
  end if;
  return jsonb_build_object('ok', true, 'attempt', to_jsonb(v_attempt));
end;
$$;

create or replace function public.apply_mercado_pago_order_server(
  p_provider_order_id text,
  p_external_reference text,
  p_total_amount numeric,
  p_provider_status text,
  p_provider_status_detail text
) returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_attempt public.billing_payment_attempts%rowtype;
  v_invoice public.billing_invoices%rowtype;
  v_attempt_status text;
begin
  select * into v_attempt from public.billing_payment_attempts
  where provider_order_id = p_provider_order_id for update;
  if not found then
    return jsonb_build_object('ok', false, 'error', 'ORDER_NOT_FOUND');
  end if;
  if v_attempt.external_reference <> p_external_reference then
    return jsonb_build_object('ok', false, 'error', 'EXTERNAL_REFERENCE_MISMATCH');
  end if;

  select * into v_invoice from public.billing_invoices
  where id = v_attempt.invoice_id for update;
  if round(p_total_amount, 2) <> v_invoice.total_amount then
    return jsonb_build_object('ok', false, 'error', 'AMOUNT_MISMATCH');
  end if;

  v_attempt_status := case
    when p_provider_status = 'processed' and p_provider_status_detail = 'accredited' then 'approved'
    when p_provider_status in ('failed', 'rejected') then 'rejected'
    when p_provider_status in ('cancelled', 'canceled') then 'cancelled'
    when p_provider_status = 'expired' then 'expired'
    when p_provider_status = 'refunded' then 'refunded'
    else 'pending'
  end;

  update public.billing_payment_attempts set
    status = v_attempt_status,
    provider_status = p_provider_status,
    provider_status_detail = p_provider_status_detail,
    approved_at = case when v_attempt_status = 'approved'
                       then coalesce(approved_at, now()) else approved_at end
  where id = v_attempt.id;

  if v_attempt_status = 'approved' and v_invoice.status <> 'paid' then
    update public.billing_invoices
    set status = 'paid', paid_at = now()
    where id = v_invoice.id;

    update public.company_subscriptions set
      status = 'active',
      current_period_start = v_invoice.period_start::timestamptz,
      current_period_end = v_invoice.period_end::timestamptz
    where company_id = v_invoice.company_id;

    update public.licenses l set
      status = 'active', license_type = 'subscription',
      expires_at = v_invoice.period_end::timestamptz
    from public.installations i
    where l.installation_id = i.id
      and i.company_id = v_invoice.company_id
      and i.billing_status <> 'removed';

    insert into public.audit_events(action, target_type, target_id, metadata)
    values (
      'billing.invoice_paid', 'billing_invoice', v_invoice.id::text,
      jsonb_build_object('provider', 'mercado_pago',
                         'provider_order_id_hash', encode(digest(p_provider_order_id, 'sha256'), 'hex'),
                         'amount', v_invoice.total_amount)
    );
  end if;

  return jsonb_build_object(
    'ok', true, 'invoice_id', v_invoice.id,
    'invoice_status', case when v_attempt_status = 'approved' then 'paid' else v_invoice.status end,
    'attempt_status', v_attempt_status
  );
end;
$$;

revoke all on function public.prepare_company_invoice_server(uuid, uuid) from public, anon, authenticated;
revoke all on function public.prepare_billing_attempt_server(uuid, uuid, text) from public, anon, authenticated;
revoke all on function public.record_provider_order_server(uuid, text, text, text, text, text, text, text) from public, anon, authenticated;
revoke all on function public.apply_mercado_pago_order_server(text, text, numeric, text, text) from public, anon, authenticated;
grant execute on function public.prepare_company_invoice_server(uuid, uuid) to service_role;
grant execute on function public.prepare_billing_attempt_server(uuid, uuid, text) to service_role;
grant execute on function public.record_provider_order_server(uuid, text, text, text, text, text, text, text) to service_role;
grant execute on function public.apply_mercado_pago_order_server(text, text, numeric, text, text) to service_role;

commit;
