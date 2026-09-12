-- SaaS Assistente PRO 2.0 - impede que uma cobranca antiga ative assentos novos.

begin;

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
  v_superseded jsonb := '[]'::jsonb;
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
    and period_start = v_period_start and period_end = v_period_end
  for update;

  if v_invoice.status = 'open' and (
    v_invoice.principal_seats is distinct from v_principal
    or v_invoice.additional_seats is distinct from v_additional
    or v_invoice.base_price is distinct from v_subscription.base_price
    or v_invoice.additional_seat_price is distinct from v_subscription.additional_seat_price
    or v_invoice.total_amount is distinct from v_total
  ) then
    update public.billing_payment_attempts
    set status = 'cancelled',
        provider_status_detail = 'invoice_seat_count_changed',
        expires_at = least(coalesce(expires_at, now()), now()),
        provider_payload = coalesce(provider_payload, '{}'::jsonb) ||
          jsonb_build_object('local_reason', 'invoice_seat_count_changed',
                             'superseded_at', now())
    where invoice_id = v_invoice.id and status = 'pending';

    update public.billing_invoices
    set principal_seats = v_principal,
        additional_seats = v_additional,
        base_price = v_subscription.base_price,
        additional_seat_price = v_subscription.additional_seat_price,
        total_amount = v_total
    where id = v_invoice.id
    returning * into v_invoice;

    insert into public.audit_events(action, target_type, target_id, metadata)
    values (
      'billing.invoice_repriced', 'billing_invoice', v_invoice.id::text,
      jsonb_build_object('principal_seats', v_principal,
                         'additional_seats', v_additional,
                         'total_amount', v_total)
    );
  end if;

  -- Mantem tentativas PIX superseded na fila ate o provedor confirmar o
  -- cancelamento. Assim uma falha temporaria nao permite criar outra cobranca.
  select coalesce(jsonb_agg(jsonb_build_object(
    'id', id,
    'payment_method', payment_method,
    'provider_order_id', provider_order_id,
    'provider_payment_id', provider_payment_id
  )), '[]'::jsonb)
  into v_superseded
  from public.billing_payment_attempts
  where invoice_id = v_invoice.id
    and status = 'cancelled'
    and provider_status_detail = 'invoice_seat_count_changed'
    and provider_order_id is not null;

  return jsonb_build_object(
    'ok', true,
    'invoice', to_jsonb(v_invoice),
    'superseded_attempts', v_superseded
  );
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
  v_principal integer;
  v_additional integer;
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

  v_attempt_status := case
    when p_provider_status = 'approved'
      or (p_provider_status = 'processed' and p_provider_status_detail = 'accredited')
      then 'approved'
    when p_provider_status in ('failed', 'rejected') then 'rejected'
    when p_provider_status in ('cancelled', 'canceled') then 'cancelled'
    when p_provider_status = 'expired' then 'expired'
    when p_provider_status = 'refunded' then 'refunded'
    else 'pending'
  end;

  if v_attempt_status = 'approved' then
    if v_attempt.status = 'approved' and v_invoice.status = 'paid' then
      return jsonb_build_object(
        'ok', true, 'invoice_id', v_invoice.id,
        'invoice_status', 'paid', 'attempt_status', 'approved'
      );
    end if;
    if v_attempt.status <> 'pending' or v_invoice.status <> 'open' then
      return jsonb_build_object('ok', false, 'error', 'ATTEMPT_NOT_PAYABLE');
    end if;
    if round(p_total_amount, 2) <> v_invoice.total_amount then
      return jsonb_build_object('ok', false, 'error', 'AMOUNT_MISMATCH');
    end if;

    select
      count(*) filter (where device_class = 'principal'),
      count(*) filter (where device_class = 'additional')
    into v_principal, v_additional
    from public.installations
    where company_id = v_invoice.company_id and billing_status <> 'removed';
    v_principal := least(coalesce(v_principal, 0), 1);
    v_additional := coalesce(v_additional, 0);
    if v_principal <> v_invoice.principal_seats
       or v_additional <> v_invoice.additional_seats then
      return jsonb_build_object('ok', false, 'error', 'SEAT_COUNT_MISMATCH');
    end if;
  end if;

  update public.billing_payment_attempts set
    status = v_attempt_status,
    provider_status = p_provider_status,
    provider_status_detail = p_provider_status_detail,
    approved_at = case when v_attempt_status = 'approved'
                       then coalesce(approved_at, now()) else approved_at end
  where id = v_attempt.id;

  if v_attempt_status = 'approved' then
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
                         'amount', v_invoice.total_amount,
                         'principal_seats', v_invoice.principal_seats,
                         'additional_seats', v_invoice.additional_seats)
    );
  end if;

  return jsonb_build_object(
    'ok', true, 'invoice_id', v_invoice.id,
    'invoice_status', case when v_attempt_status = 'approved' then 'paid' else v_invoice.status end,
    'attempt_status', v_attempt_status
  );
end;
$$;

revoke all on function public.prepare_company_invoice_server(uuid, uuid)
  from public, anon, authenticated;
revoke all on function public.apply_mercado_pago_order_server(text, text, numeric, text, text)
  from public, anon, authenticated;
grant execute on function public.prepare_company_invoice_server(uuid, uuid) to service_role;
grant execute on function public.apply_mercado_pago_order_server(text, text, numeric, text, text) to service_role;

commit;
