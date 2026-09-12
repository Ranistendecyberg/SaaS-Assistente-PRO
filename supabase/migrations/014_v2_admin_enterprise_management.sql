-- Operações atômicas do Gerador Admin para contas empresariais 2.0.
-- Somente a service_role pode executar estas funções; a admin-api valida
-- o administrador, MFA e registra a identidade do autor.

begin;

create or replace function public.admin_update_company_subscription_server(
  p_actor_user_id uuid,
  p_company_id uuid,
  p_status text,
  p_base_price numeric,
  p_additional_seat_price numeric,
  p_current_period_end timestamptz
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_subscription public.company_subscriptions%rowtype;
  v_license_status text;
  v_license_type text;
begin
  if p_actor_user_id is null or p_company_id is null then
    return jsonb_build_object('ok', false, 'error', 'INVALID_ENTERPRISE_UPDATE');
  end if;
  if p_status not in ('trial', 'active', 'past_due', 'suspended', 'cancelled')
     or p_base_price is null or p_base_price < 0 or p_base_price > 1000000
     or p_additional_seat_price is null or p_additional_seat_price < 0
     or p_additional_seat_price > 1000000 then
    return jsonb_build_object('ok', false, 'error', 'INVALID_ENTERPRISE_UPDATE');
  end if;
  if p_current_period_end is null then
    return jsonb_build_object('ok', false, 'error', 'INVALID_ENTERPRISE_EXPIRY');
  end if;
  if p_status in ('trial', 'active') and p_current_period_end <= now() then
    return jsonb_build_object('ok', false, 'error', 'INVALID_ENTERPRISE_EXPIRY');
  end if;

  update public.company_subscriptions
  set status = p_status,
      pricing_origin = case when pricing_origin = 'legacy_preserved' then pricing_origin else 'custom' end,
      base_price = round(p_base_price, 2),
      additional_seat_price = round(p_additional_seat_price, 2),
      current_period_start = coalesce(current_period_start, now()),
      current_period_end = p_current_period_end,
      trial_expires_at = case when p_status = 'trial' then p_current_period_end else trial_expires_at end,
      updated_at = now()
  where company_id = p_company_id
  returning * into v_subscription;

  if not found then
    return jsonb_build_object('ok', false, 'error', 'ENTERPRISE_NOT_FOUND');
  end if;

  v_license_status := case
    when p_status = 'trial' then 'trial'
    when p_status = 'active' then 'active'
    when p_status in ('past_due', 'suspended') then 'blocked'
    else 'cancelled'
  end;
  v_license_type := case when p_status = 'trial' then 'trial' else 'subscription' end;

  update public.licenses l
  set status = v_license_status,
      license_type = v_license_type,
      expires_at = p_current_period_end,
      monthly_price = case
        when i.device_class = 'principal' then round(p_base_price, 2)
        else round(p_additional_seat_price, 2)
      end,
      updated_at = now()
  from public.installations i
  where l.installation_id = i.id
    and i.company_id = p_company_id
    and i.billing_status <> 'removed';

  insert into public.audit_events (
    actor_user_id, action, target_type, target_id, metadata
  ) values (
    p_actor_user_id, 'enterprise.subscription_updated', 'company', p_company_id::text,
    jsonb_build_object(
      'status', p_status,
      'base_price', round(p_base_price, 2),
      'additional_seat_price', round(p_additional_seat_price, 2),
      'current_period_end', p_current_period_end
    )
  );

  return jsonb_build_object(
    'ok', true,
    'company_id', p_company_id,
    'status', v_subscription.status,
    'base_price', v_subscription.base_price,
    'additional_seat_price', v_subscription.additional_seat_price,
    'current_period_end', v_subscription.current_period_end
  );
end;
$$;

create or replace function public.admin_set_enterprise_device_status_server(
  p_actor_user_id uuid,
  p_installation_id uuid,
  p_status text
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_installation public.installations%rowtype;
  v_subscription public.company_subscriptions%rowtype;
  v_license_status text;
begin
  if p_actor_user_id is null or p_installation_id is null
     or p_status not in ('active', 'blocked') then
    return jsonb_build_object('ok', false, 'error', 'INVALID_DEVICE_STATUS');
  end if;

  select * into v_installation
  from public.installations
  where id = p_installation_id and billing_status <> 'removed'
  for update;
  if not found then
    return jsonb_build_object('ok', false, 'error', 'ENTERPRISE_DEVICE_NOT_FOUND');
  end if;

  select * into v_subscription
  from public.company_subscriptions
  where company_id = v_installation.company_id;
  if not found then
    return jsonb_build_object('ok', false, 'error', 'ENTERPRISE_NOT_FOUND');
  end if;
  if p_status = 'active' and (
    v_subscription.status not in ('trial', 'active')
    or coalesce(v_subscription.current_period_end, v_subscription.trial_expires_at) is null
    or coalesce(v_subscription.current_period_end, v_subscription.trial_expires_at) <= now()
  ) then
    return jsonb_build_object('ok', false, 'error', 'SUBSCRIPTION_NOT_ACTIVE');
  end if;

  update public.installations
  set status = p_status,
      billing_status = case
        when p_status = 'blocked' and billing_status = 'pending_removal' then 'pending_removal'
        else p_status
      end,
      updated_at = now()
  where id = p_installation_id;

  v_license_status := case
    when p_status = 'blocked' then 'blocked'
    when v_subscription.status = 'trial' then 'trial'
    when v_subscription.status = 'active' then 'active'
    when v_subscription.status in ('past_due', 'suspended') then 'blocked'
    else 'cancelled'
  end;
  update public.licenses
  set status = v_license_status, updated_at = now()
  where installation_id = p_installation_id;

  insert into public.audit_events (
    actor_user_id, actor_installation_id, action, target_type, target_id, metadata
  ) values (
    p_actor_user_id, p_installation_id, 'enterprise.device_status_changed',
    'installation', p_installation_id::text,
    jsonb_build_object('status', p_status, 'device_class', v_installation.device_class)
  );

  return jsonb_build_object(
    'ok', true,
    'installation_id', p_installation_id,
    'status', p_status,
    'license_status', v_license_status
  );
end;
$$;

revoke all on function public.admin_update_company_subscription_server(
  uuid, uuid, text, numeric, numeric, timestamptz
) from public, anon, authenticated;
grant execute on function public.admin_update_company_subscription_server(
  uuid, uuid, text, numeric, numeric, timestamptz
) to service_role;

revoke all on function public.admin_set_enterprise_device_status_server(
  uuid, uuid, text
) from public, anon, authenticated;
grant execute on function public.admin_set_enterprise_device_status_server(
  uuid, uuid, text
) to service_role;

commit;
