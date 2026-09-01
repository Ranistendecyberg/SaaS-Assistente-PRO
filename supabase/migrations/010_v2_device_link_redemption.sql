-- Resgate atômico de código de vínculo da versão 2.0.
-- A função retorna o token uma única vez e armazena somente seu hash.

begin;

create or replace function public.redeem_device_link_code_server(
  p_code_hash text,
  p_hardware_id text,
  p_user_id uuid,
  p_app_version text default null
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_code public.device_link_codes%rowtype;
  v_installation_id uuid;
  v_token text;
  v_device_class text;
begin
  if p_code_hash is null or length(p_code_hash) <> 64 then
    return jsonb_build_object('ok', false, 'error', 'INVALID_LINK_CODE');
  end if;
  if p_hardware_id is null or char_length(p_hardware_id) not between 8 and 128 then
    return jsonb_build_object('ok', false, 'error', 'INVALID_HARDWARE');
  end if;
  if p_user_id is null then
    return jsonb_build_object('ok', false, 'error', 'UNAUTHORIZED');
  end if;

  select * into v_code
  from public.device_link_codes
  where code_hash = p_code_hash
  for update;

  if not found or v_code.status <> 'new' then
    return jsonb_build_object('ok', false, 'error', 'LINK_CODE_NOT_AVAILABLE');
  end if;
  if v_code.expires_at <= now() then
    update public.device_link_codes set status = 'expired' where id = v_code.id;
    return jsonb_build_object('ok', false, 'error', 'LINK_CODE_EXPIRED');
  end if;
  if not exists (
    select 1 from public.company_members m
    where m.company_id = v_code.company_id
      and m.user_id = p_user_id
      and m.active = true
  ) then
    return jsonb_build_object('ok', false, 'error', 'COMPANY_MEMBERSHIP_REQUIRED');
  end if;
  if exists (select 1 from public.installations where hardware_id = p_hardware_id) then
    return jsonb_build_object('ok', false, 'error', 'INSTALLATION_ALREADY_EXISTS');
  end if;

  if exists (
    select 1 from public.installations
    where company_id = v_code.company_id
      and device_class = 'principal'
      and billing_status <> 'removed'
  ) then
    v_device_class := 'additional';
  else
    v_device_class := 'principal';
  end if;

  v_token := encode(gen_random_bytes(32), 'hex');
  insert into public.installations (
    company_id, business_unit_id, hardware_id, token_hash, token_issued_at,
    status, app_version, device_class, billing_status, activated_by, activated_at
  ) values (
    v_code.company_id, v_code.business_unit_id, p_hardware_id,
    encode(digest(v_token, 'sha256'), 'hex'), now(),
    'active', nullif(trim(p_app_version), ''), v_device_class, 'active', p_user_id, now()
  ) returning id into v_installation_id;

  update public.device_link_codes
  set status = 'used', redeemed_by_installation = v_installation_id,
      redeemed_by_user = p_user_id, redeemed_at = now()
  where id = v_code.id;

  insert into public.audit_events (
    actor_user_id, actor_installation_id, action, target_type, target_id, metadata
  ) values (
    p_user_id, v_installation_id, 'installation.device_linked',
    'installation', v_installation_id::text,
    jsonb_build_object('device_class', v_device_class, 'business_unit_id', v_code.business_unit_id)
  );

  return jsonb_build_object(
    'ok', true,
    'installation_id', v_installation_id,
    'installation_token', v_token,
    'device_class', v_device_class,
    'company_id', v_code.company_id,
    'business_unit_id', v_code.business_unit_id
  );
exception
  when unique_violation then
    return jsonb_build_object('ok', false, 'error', 'INSTALLATION_ALREADY_EXISTS');
end;
$$;

revoke all on function public.redeem_device_link_code_server(text, text, uuid, text)
  from public, anon, authenticated;
grant execute on function public.redeem_device_link_code_server(text, text, uuid, text)
  to service_role;

commit;
