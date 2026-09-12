begin;

-- Índices das consultas empresariais mais frequentes.
create index if not exists idx_billing_reconciliation_cases_company_id
  on public.billing_reconciliation_cases(company_id);
create index if not exists idx_device_link_codes_company_id
  on public.device_link_codes(company_id);
create index if not exists idx_device_link_codes_business_unit_id
  on public.device_link_codes(business_unit_id);
create index if not exists idx_installations_company_billing
  on public.installations(company_id, billing_status);

-- A Edge Function valida proprietário + OTP. Esta RPC permanece restrita ao
-- service_role e serializa a empresa antes de bloquear os computadores, na
-- mesma ordem usada pelos fluxos financeiros.
create or replace function public.transfer_principal_server(
  p_company_id uuid,
  p_new_principal_installation_id uuid
)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  old_principal_id uuid;
  new_device_class text;
begin
  if p_company_id is null or p_new_principal_installation_id is null then
    return jsonb_build_object('ok', false, 'error', 'INVALID_TRANSFER');
  end if;

  perform 1
  from public.company_subscriptions
  where company_id = p_company_id
  for update;
  if not found then
    return jsonb_build_object('ok', false, 'error', 'COMPANY_NOT_FOUND');
  end if;

  -- Ordem determinística evita deadlocks entre duas transferências da mesma
  -- empresa e impede que a composição de computadores mude no meio da troca.
  perform 1
  from public.installations
  where company_id = p_company_id
    and billing_status <> 'removed'
  order by id
  for update;

  select device_class into new_device_class
  from public.installations
  where id = p_new_principal_installation_id
    and company_id = p_company_id
    and billing_status <> 'removed';
  if not found then
    return jsonb_build_object('ok', false, 'error', 'INSTALLATION_NOT_FOUND');
  end if;
  if new_device_class = 'principal' then
    return jsonb_build_object('ok', true, 'already_principal', true);
  end if;

  select id into old_principal_id
  from public.installations
  where company_id = p_company_id
    and device_class = 'principal'
    and billing_status <> 'removed'
  limit 1;

  if old_principal_id is not null then
    update public.installations
    set device_class = 'additional', updated_at = now()
    where id = old_principal_id;
  end if;

  update public.installations
  set device_class = 'principal', updated_at = now()
  where id = p_new_principal_installation_id;

  insert into public.audit_events (
    action, target_type, target_id, metadata
  ) values (
    'enterprise.principal_transferred', 'installation',
    p_new_principal_installation_id::text,
    jsonb_build_object(
      'company_id', p_company_id,
      'old_principal_id', old_principal_id,
      'new_principal_id', p_new_principal_installation_id,
      'source', 'account-api'
    )
  );

  return jsonb_build_object(
    'ok', true,
    'old_principal_id', old_principal_id,
    'new_principal_id', p_new_principal_installation_id
  );
end;
$$;

create or replace function public.admin_transfer_principal_server(
  p_company_id uuid,
  p_new_principal_installation_id uuid
)
returns jsonb
language sql
security definer
set search_path = public, pg_temp
as $$
  select public.transfer_principal_server(
    p_company_id,
    p_new_principal_installation_id
  );
$$;

revoke all on function public.transfer_principal_server(uuid, uuid)
  from public, anon, authenticated;
revoke all on function public.admin_transfer_principal_server(uuid, uuid)
  from public, anon, authenticated;
grant execute on function public.transfer_principal_server(uuid, uuid)
  to service_role;
grant execute on function public.admin_transfer_principal_server(uuid, uuid)
  to service_role;

commit;
