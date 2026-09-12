-- Aplicar após 019. Cobranças anteriores sem snapshot exigem conferência;
-- nunca presumir quais computadores um PIX antigo pagou.
begin;

alter table public.billing_invoices add column if not exists installation_ids uuid[];
alter table public.billing_payment_attempts add column if not exists invoice_snapshot jsonb;

create table if not exists public.billing_reconciliation_cases (
  attempt_id uuid primary key references public.billing_payment_attempts(id),
  company_id uuid not null references public.companies(id),
  reason text not null,
  received_amount numeric,
  provider_status text not null,
  created_at timestamptz not null default now(),
  resolved_at timestamptz
);
alter table public.billing_reconciliation_cases enable row level security;
alter table public.billing_reconciliation_cases force row level security;
revoke all on public.billing_reconciliation_cases from public, anon, authenticated;
grant select, insert, update on public.billing_reconciliation_cases to service_role;

-- Preserva as implementações anteriores como internas, sem acesso via RPC.
do $$ begin
  if to_regprocedure('public.prepare_company_invoice_v019(uuid,uuid)') is null then
    alter function public.prepare_company_invoice_server(uuid,uuid) rename to prepare_company_invoice_v019;
    alter function public.prepare_billing_attempt_server(uuid,uuid,text) rename to prepare_billing_attempt_v019;
    alter function public.apply_mercado_pago_order_server(text,text,numeric,text,text) rename to apply_mercado_pago_order_v019;
  end if;
end $$;
alter function public.apply_mercado_pago_order_v019(text,text,numeric,text,text)
  set search_path = public, extensions;
revoke all on function public.prepare_company_invoice_v019(uuid,uuid) from public, anon, authenticated, service_role;
revoke all on function public.prepare_billing_attempt_v019(uuid,uuid,text) from public, anon, authenticated, service_role;
revoke all on function public.apply_mercado_pago_order_v019(text,text,numeric,text,text) from public, anon, authenticated, service_role;

-- Revalida o emissor do código no momento do resgate e adquire o bloqueio antes
-- de bloquear o código; evita upgrade concorrente FOR SHARE -> FOR UPDATE.
do $$ begin
  if to_regprocedure('public.redeem_device_link_code_server(text,text,text)') is not null
    and to_regprocedure('public.redeem_device_link_code_v018(text,text,text)') is null then
    alter function public.redeem_device_link_code_server(text,text,text) rename to redeem_device_link_code_v018;
  end if;
end $$;
create or replace function public.redeem_device_link_code_server(p_code_hash text,p_hardware_id text,p_app_version text default null)
returns jsonb language plpgsql security definer set search_path=public as $$
declare v_code public.device_link_codes%rowtype; v_result jsonb;
begin
  select * into v_code from public.device_link_codes where code_hash=p_code_hash;
  if found then
    perform 1 from public.company_subscriptions where company_id=v_code.company_id for update;
    if not exists(select 1 from public.company_members where company_id=v_code.company_id
      and user_id=v_code.created_by and active and role in ('owner','admin')) then
      return jsonb_build_object('ok',false,'error','LINK_CODE_NOT_AVAILABLE'); end if;
    if v_code.business_unit_id is not null and not exists(select 1 from public.business_units
      where id=v_code.business_unit_id and company_id=v_code.company_id and active) then
      return jsonb_build_object('ok',false,'error','LINK_CODE_NOT_AVAILABLE'); end if;
  end if;
  v_result:=public.redeem_device_link_code_v018(p_code_hash,p_hardware_id,p_app_version);
  return v_result;
end $$;
revoke all on function public.redeem_device_link_code_server(text,text,text) from public,anon,authenticated;
grant execute on function public.redeem_device_link_code_server(text,text,text) to service_role;
do $$ begin
  if to_regprocedure('public.redeem_device_link_code_v018(text,text,text)') is not null then
    revoke all on function public.redeem_device_link_code_v018(text,text,text) from public,anon,authenticated,service_role;
  end if;
end $$;

-- O mesmo bloqueio da assinatura serializa emissão, webhook e alterações de máquinas.
create or replace function public.lock_installation_company_billing()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  if TG_OP = 'UPDATE' and new.company_id is distinct from old.company_id then
    raise exception 'COMPANY_TRANSFER_NOT_ALLOWED';
  end if;
  perform 1 from public.company_subscriptions
    where company_id = case when TG_OP = 'DELETE' then old.company_id else new.company_id end
    for update;
  if TG_OP = 'DELETE' then
    -- Mantém identidade e histórico das máquinas empresariais.
    if exists (select 1 from public.company_subscriptions where company_id = old.company_id) then
      raise exception 'ENTERPRISE_DEVICE_DELETE_FORBIDDEN';
    end if;
    return old;
  end if;
  return new;
end $$;
drop trigger if exists installations_billing_lock on public.installations;
create trigger installations_billing_lock before insert or update or delete on public.installations
for each row execute function public.lock_installation_company_billing();

create or replace function public.prepare_company_invoice_server(p_user_id uuid, p_company_id uuid)
returns jsonb language plpgsql security definer set search_path = public as $$
declare
  v_result jsonb;
  v_invoice public.billing_invoices%rowtype;
  v_ids uuid[];
  v_superseded jsonb;
begin
  perform 1 from public.company_subscriptions where company_id = p_company_id for update;
  if not exists(select 1 from public.company_members where company_id=p_company_id
    and user_id=p_user_id and role='owner' and active) then
    return jsonb_build_object('ok',false,'error','OWNER_REQUIRED'); end if;
  -- Um recebimento divergente deve ser resolvido antes de emitir outra cobrança.
  if exists (select 1 from public.billing_reconciliation_cases
    where company_id = p_company_id and resolved_at is null) then
    return jsonb_build_object('ok',false,'error','PAYMENT_RECONCILIATION_REQUIRED');
  end if;
  v_result := public.prepare_company_invoice_v019(p_user_id,p_company_id);
  if not coalesce((v_result->>'ok')::boolean,false) then return v_result; end if;
  select * into v_invoice from public.billing_invoices
    where id = (v_result->'invoice'->>'id')::uuid for update;
  select coalesce(array_agg(id order by id),'{}'::uuid[]) into v_ids
    from public.installations where company_id = p_company_id and billing_status <> 'removed';
  if v_invoice.status = 'open' and v_invoice.installation_ids is distinct from v_ids then
    update public.billing_payment_attempts set status = 'cancelled',
      provider_status_detail = 'invoice_seat_count_changed'
      where invoice_id = v_invoice.id and status = 'pending';
    update public.billing_invoices set installation_ids = v_ids
      where id = v_invoice.id returning * into v_invoice;
  end if;
  -- Inclui cobranças de períodos anteriores: mudar a data não contorna a conciliação.
  select coalesce(jsonb_agg(jsonb_build_object('id',a.id,'payment_method',a.payment_method,
    'provider_order_id',a.provider_order_id,'provider_payment_id',a.provider_payment_id)),'[]'::jsonb)
    into v_superseded from public.billing_payment_attempts a
    join public.billing_invoices i on i.id = a.invoice_id
    where i.company_id = p_company_id and a.status = 'cancelled'
      and a.provider_status_detail = 'invoice_seat_count_changed'
      and a.provider_order_id is not null;
  return jsonb_build_object('ok',true,'invoice',to_jsonb(v_invoice),'superseded_attempts',v_superseded);
end $$;

create or replace function public.prepare_billing_attempt_server(p_user_id uuid,p_invoice_id uuid,p_payment_method text)
returns jsonb language plpgsql security definer set search_path = public as $$
declare v_company uuid; v_invoice public.billing_invoices%rowtype; v_ids uuid[];
begin
  select company_id into v_company from public.billing_invoices where id = p_invoice_id;
  perform 1 from public.company_subscriptions where company_id = v_company for update;
  select * into v_invoice from public.billing_invoices where id = p_invoice_id for update;
  select coalesce(array_agg(id order by id),'{}'::uuid[]) into v_ids from public.installations
    where company_id = v_company and billing_status <> 'removed';
  if v_invoice.installation_ids is null or v_invoice.installation_ids is distinct from v_ids then
    return jsonb_build_object('ok',false,'error','INVOICE_CHANGED');
  end if;
  if exists (select 1 from public.billing_reconciliation_cases where company_id = v_company and resolved_at is null) then
    return jsonb_build_object('ok',false,'error','PAYMENT_RECONCILIATION_REQUIRED');
  end if;
  -- Não permite PIX e boleto ativos simultaneamente para o mesmo período.
  if exists (select 1 from public.billing_payment_attempts where invoice_id = p_invoice_id
    and status = 'pending' and payment_method <> p_payment_method) then
    return jsonb_build_object('ok',false,'error','PAYMENT_METHOD_ALREADY_PENDING');
  end if;
  return public.prepare_billing_attempt_v019(p_user_id,p_invoice_id,p_payment_method);
end $$;

create or replace function public.capture_billing_attempt_snapshot()
returns trigger language plpgsql security definer set search_path = public as $$
declare v_invoice public.billing_invoices%rowtype; v_company uuid; v_ids uuid[];
begin
  if TG_OP = 'UPDATE' then
    if new.invoice_snapshot is distinct from old.invoice_snapshot
      or new.invoice_id is distinct from old.invoice_id
      or new.external_reference is distinct from old.external_reference
      or new.idempotency_key is distinct from old.idempotency_key then
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
  new.invoice_snapshot := jsonb_build_object('installation_ids',v_invoice.installation_ids,
    'total_amount',v_invoice.total_amount,'period_start',v_invoice.period_start,'period_end',v_invoice.period_end);
  return new;
end $$;
drop trigger if exists billing_attempt_snapshot on public.billing_payment_attempts;
create trigger billing_attempt_snapshot before insert or update on public.billing_payment_attempts
for each row execute function public.capture_billing_attempt_snapshot();

create or replace function public.apply_mercado_pago_order_server(
  p_provider_order_id text,p_external_reference text,p_total_amount numeric,
  p_provider_status text,p_provider_status_detail text
) returns jsonb language plpgsql security definer set search_path = public as $$
declare
  v_attempt public.billing_payment_attempts%rowtype;
  v_invoice public.billing_invoices%rowtype;
  v_subscription public.company_subscriptions%rowtype;
  v_company uuid; v_ids uuid[]; v_blocked uuid[]; v_reason text; v_result jsonb;
  v_approved boolean := p_provider_status = 'approved' or
    (p_provider_status = 'processed' and p_provider_status_detail = 'accredited');
begin
  select i.company_id into v_company from public.billing_invoices i
    join public.billing_payment_attempts a on a.invoice_id=i.id where a.provider_order_id=p_provider_order_id;
  if v_company is null then return jsonb_build_object('ok',false,'error','ORDER_NOT_FOUND'); end if;
  select * into v_subscription from public.company_subscriptions where company_id=v_company for update;
  select i.* into v_invoice from public.billing_invoices i join public.billing_payment_attempts a
    on a.invoice_id=i.id where a.provider_order_id=p_provider_order_id for update of i;
  select * into v_attempt from public.billing_payment_attempts where provider_order_id=p_provider_order_id for update;
  if p_external_reference is null or v_attempt.external_reference is distinct from p_external_reference then
    return jsonb_build_object('ok',false,'error','EXTERNAL_REFERENCE_MISMATCH'); end if;
  if p_total_amount is null or p_total_amount <= 0 or p_total_amount::text in ('NaN','Infinity','-Infinity')
    or p_total_amount <> round(p_total_amount,2) then
    return jsonb_build_object('ok',false,'error','AMOUNT_MISMATCH'); end if;
  -- Notificações atrasadas não reabrem uma tentativa encerrada nem repetem a renovação.
  if v_attempt.status = 'approved' and v_invoice.status = 'paid' and v_approved then
    if p_total_amount is distinct from (v_attempt.invoice_snapshot->>'total_amount')::numeric then
      return jsonb_build_object('ok',false,'error','AMOUNT_MISMATCH'); end if;
    return jsonb_build_object('ok',true,'invoice_status','paid','duplicate',true);
  end if;
  if not v_approved then
    if p_provider_status = 'refunded' and v_attempt.status = 'approved' then
      v_reason := 'PAYMENT_REFUNDED';
    elsif v_attempt.status <> 'pending' then
      return jsonb_build_object('ok',true,'ignored',true);
    else
      return public.apply_mercado_pago_order_v019(p_provider_order_id,p_external_reference,p_total_amount,p_provider_status,p_provider_status_detail);
    end if;
  else
    select coalesce(array_agg(id order by id),'{}'::uuid[]) into v_ids from public.installations
      where company_id=v_company and billing_status <> 'removed';
    v_reason := case
      when v_attempt.invoice_snapshot is null then 'LEGACY_PAYMENT_SNAPSHOT_REQUIRED'
      when v_attempt.status <> 'pending' or v_invoice.status <> 'open' then 'ATTEMPT_NOT_PAYABLE'
      when p_total_amount is distinct from (v_attempt.invoice_snapshot->>'total_amount')::numeric
        or p_total_amount is distinct from v_invoice.total_amount then 'AMOUNT_MISMATCH'
      when v_invoice.base_price is distinct from v_subscription.base_price
        or v_invoice.additional_seat_price is distinct from v_subscription.additional_seat_price then 'INVOICE_PRICE_CHANGED'
      when v_attempt.invoice_snapshot->'installation_ids' is distinct from to_jsonb(v_ids)
        or v_invoice.installation_ids is distinct from v_ids then 'SEAT_SNAPSHOT_MISMATCH'
      when v_subscription.status in ('suspended','cancelled') then 'SUBSCRIPTION_NOT_BILLABLE'
      when v_invoice.period_end::timestamptz <= v_subscription.current_period_end then 'STALE_INVOICE_PERIOD'
      else null end;
  end if;
  if v_reason is not null then
    insert into public.billing_reconciliation_cases(attempt_id,company_id,reason,received_amount,provider_status)
      values(v_attempt.id,v_company,v_reason,p_total_amount,p_provider_status)
      on conflict(attempt_id) do nothing;
    -- Recebimento registrado sem liberar máquinas. Webhook recebe ACK para evitar reprocessamento infinito.
    return jsonb_build_object('ok',true,'reconciliation_required',true,'reason',v_reason);
  end if;
  select coalesce(array_agg(id),'{}'::uuid[]) into v_blocked from public.installations
    where company_id=v_company and (status <> 'active' or billing_status='blocked');
  v_result := public.apply_mercado_pago_order_v019(p_provider_order_id,p_external_reference,p_total_amount,p_provider_status,p_provider_status_detail);
  if coalesce((v_result->>'ok')::boolean,false) then
    update public.licenses set status='blocked' where installation_id=any(v_blocked);
  end if;
  return v_result;
end $$;

revoke all on function public.lock_installation_company_billing() from public,anon,authenticated,service_role;
revoke all on function public.capture_billing_attempt_snapshot() from public,anon,authenticated,service_role;
revoke all on function public.prepare_company_invoice_server(uuid,uuid) from public,anon,authenticated;
revoke all on function public.prepare_billing_attempt_server(uuid,uuid,text) from public,anon,authenticated;
revoke all on function public.apply_mercado_pago_order_server(text,text,numeric,text,text) from public,anon,authenticated;
grant execute on function public.prepare_company_invoice_server(uuid,uuid) to service_role;
grant execute on function public.prepare_billing_attempt_server(uuid,uuid,text) to service_role;
grant execute on function public.apply_mercado_pago_order_server(text,text,numeric,text,text) to service_role;

-- Mesmo uma resposta tardia do provedor mantém a associação para conciliação.
create or replace function public.record_provider_order_server(
  p_attempt_id uuid,p_provider_order_id text,p_provider_payment_id text,
  p_provider_status text,p_provider_status_detail text,p_payment_url text,
  p_pix_copy_paste text,p_boleto_barcode text
) returns jsonb language plpgsql security definer set search_path=public as $$
declare v_attempt public.billing_payment_attempts%rowtype;
begin
  if p_provider_order_id is null or length(trim(p_provider_order_id))=0 then
    return jsonb_build_object('ok',false,'error','ATTEMPT_CONFLICT'); end if;
  update public.billing_payment_attempts set
    provider_order_id=coalesce(provider_order_id,p_provider_order_id),
    provider_payment_id=coalesce(provider_payment_id,p_provider_payment_id),
    provider_status=p_provider_status,
    provider_status_detail=case when status='pending' then p_provider_status_detail else provider_status_detail end,
    payment_url=case when status='pending' then p_payment_url else null end,
    pix_copy_paste=case when status='pending' then p_pix_copy_paste else null end,
    boleto_barcode=case when status='pending' then p_boleto_barcode else null end
    where id=p_attempt_id and (provider_order_id is null or provider_order_id=p_provider_order_id)
    returning * into v_attempt;
  if not found then return jsonb_build_object('ok',false,'error','ATTEMPT_CONFLICT'); end if;
  return jsonb_build_object('ok',true,'attempt',to_jsonb(v_attempt));
end $$;
revoke all on function public.record_provider_order_server(uuid,text,text,text,text,text,text,text) from public,anon,authenticated;
grant execute on function public.record_provider_order_server(uuid,text,text,text,text,text,text,text) to service_role;

-- Renovação/edição empresarial não remove bloqueios operacionais individuais.
create or replace function public.preserve_enterprise_license_access()
returns trigger language plpgsql security definer set search_path = public as $$
declare v_installation public.installations%rowtype;
begin
  select * into v_installation from public.installations where id=new.installation_id;
  if v_installation.status <> 'active' or v_installation.billing_status in ('blocked','removed') then
    new.status := 'blocked';
  elsif (TG_OP = 'INSERT' or new.status is distinct from old.status or new.expires_at is distinct from old.expires_at)
    and new.status in ('active','trial')
    and exists(select 1 from public.billing_invoices
      where company_id=v_installation.company_id and status='paid' and period_end::timestamptz > now())
    and not exists(select 1 from public.billing_invoices
      where company_id=v_installation.company_id and status='paid'
      and v_installation.id=any(installation_ids) and period_end::timestamptz >= new.expires_at) then
    -- Computador vinculado após o pagamento não herda um período que não pagou.
    new.status := 'blocked';
    new.expires_at := now();
  end if;
  return new;
end $$;
drop trigger if exists licenses_preserve_enterprise_access on public.licenses;
create trigger licenses_preserve_enterprise_access before insert or update on public.licenses
for each row execute function public.preserve_enterprise_license_access();

create or replace function public.preserve_scheduled_device_removal()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  if old.billing_status='pending_removal' and new.removal_scheduled_for is not null
    and new.billing_status in ('active','blocked') then new.billing_status := 'pending_removal'; end if;
  return new;
end $$;
drop trigger if exists installations_preserve_removal on public.installations;
create trigger installations_preserve_removal before update on public.installations
for each row execute function public.preserve_scheduled_device_removal();
revoke all on function public.preserve_enterprise_license_access() from public,anon,authenticated,service_role;
revoke all on function public.preserve_scheduled_device_removal() from public,anon,authenticated,service_role;

create or replace function public.resolve_billing_refund_server(p_actor_user_id uuid,p_attempt_id uuid)
returns jsonb language plpgsql security definer set search_path=public as $$
declare v_case public.billing_reconciliation_cases%rowtype; v_invoice public.billing_invoices%rowtype;
begin
  select * into v_case from public.billing_reconciliation_cases where attempt_id=p_attempt_id;
  if not found or v_case.resolved_at is not null then
    return jsonb_build_object('ok',false,'error','RECONCILIATION_NOT_PENDING'); end if;
  perform 1 from public.company_subscriptions where company_id=v_case.company_id for update;
  select i.* into v_invoice from public.billing_invoices i join public.billing_payment_attempts a
    on a.invoice_id=i.id where a.id=p_attempt_id for update of i;
  update public.billing_reconciliation_cases set resolved_at=now()
    where attempt_id=p_attempt_id and resolved_at is null;
  if not found then return jsonb_build_object('ok',true,'duplicate',true); end if;
  update public.billing_payment_attempts set status='refunded',provider_status='refunded' where id=p_attempt_id;
  if v_invoice.status='paid' then
    update public.billing_invoices set status='refunded' where id=v_invoice.id;
    update public.company_subscriptions set status='past_due'
      where company_id=v_case.company_id and current_period_end=v_invoice.period_end::timestamptz;
    if found then
      update public.licenses set status='blocked' where installation_id in
        (select id from public.installations where company_id=v_case.company_id);
    end if;
  end if;
  insert into public.audit_events(actor_user_id,action,target_type,target_id,metadata)
    values(p_actor_user_id,'billing.refund_verified','billing_attempt',p_attempt_id::text,
      jsonb_build_object('company_id',v_case.company_id,'provider_status','refunded'));
  return jsonb_build_object('ok',true);
end $$;
revoke all on function public.resolve_billing_refund_server(uuid,uuid) from public,anon,authenticated;
grant execute on function public.resolve_billing_refund_server(uuid,uuid) to service_role;
commit;
