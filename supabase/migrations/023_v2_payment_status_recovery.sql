-- Recovery is a provider GET, never a new charge. Shared DB throttle across workers.
begin;
alter table public.billing_payment_attempts
  add column if not exists last_provider_check_at timestamptz;

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
    'payment_method',v_attempt.payment_method,'external_reference',v_attempt.external_reference);
end;
$$;
revoke all on function public.claim_payment_status_check_server(uuid,uuid,uuid) from public,anon,authenticated;
grant execute on function public.claim_payment_status_check_server(uuid,uuid,uuid) to service_role;
commit;
