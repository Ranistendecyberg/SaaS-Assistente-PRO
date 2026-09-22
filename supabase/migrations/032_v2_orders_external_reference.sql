-- Referencia externa compativel com a API Orders do Mercado Pago.
-- Maximo de 64 caracteres; somente letras, numeros, hifen e sublinhado.
begin;

create or replace function public.prepare_billing_attempt_v019(
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

  select * into v_invoice
  from public.billing_invoices
  where id = p_invoice_id
  for update;
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

  select * into v_attempt
  from public.billing_payment_attempts
  where invoice_id = p_invoice_id and payment_method = p_payment_method
    and status = 'pending'
  order by created_at desc
  limit 1;

  if not found then
    -- 61 caracteres: inv_ + UUID sem hifens + _ + 12 bytes hexadecimais.
    v_external_reference := 'inv_' || replace(p_invoice_id::text, '-', '')
      || '_' || encode(gen_random_bytes(12), 'hex');
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

revoke all on function public.prepare_billing_attempt_v019(uuid,uuid,text)
  from public,anon,authenticated,service_role;

commit;
