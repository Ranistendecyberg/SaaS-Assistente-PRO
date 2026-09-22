begin;

-- Versões antigas recorriam ao MAC quando o Windows negava acesso ao WMI.
-- Mudanças de Wi-Fi, VPN ou driver podiam alterar esse identificador decimal e
-- impedir a recuperação do próprio principal. O proprietário, já autenticado
-- e com OTP recente exigido pela Edge Function, pode migrar uma única vez esse
-- identificador legado. Licença, assinatura, classe e cobrança são preservadas.
create or replace function public.recover_principal_access_server(
  p_user_id uuid,
  p_hardware_id text
)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions, pg_temp
as $$
declare
  v_installation public.installations%rowtype;
  v_company uuid;
  v_token text;
  v_previous_hardware text;
  v_candidate_count integer := 0;
  v_hardware_rebound boolean := false;
begin
  if p_user_id is null
     or char_length(coalesce(p_hardware_id, '')) not between 8 and 128 then
    return jsonb_build_object('ok', false, 'error', 'RECOVERY_NOT_ALLOWED');
  end if;

  -- Caminho normal: o equipamento ainda possui o mesmo identificador.
  select i.* into v_installation
  from public.installations i
  join public.company_members m on m.company_id = i.company_id
  where i.hardware_id = p_hardware_id
    and i.device_class = 'principal'
    and m.user_id = p_user_id
    and m.role = 'owner'
    and m.active = true;

  if not found then
    -- Migração estritamente limitada a um principal legado, decimal, de uma
    -- única conta pertencente ao usuário autenticado. Não cria novo assento.
    select count(*) into v_candidate_count
    from public.installations i
    join public.company_members m on m.company_id = i.company_id
    where m.user_id = p_user_id
      and m.role = 'owner'
      and m.active = true
      and i.device_class = 'principal'
      and i.status = 'active'
      and i.billing_status <> 'removed'
      and i.hardware_id ~ '^[0-9]{12,20}$';

    if v_candidate_count <> 1
       or p_hardware_id !~ '^(WIN-[A-F0-9]{32}|[0-9]{12,20})$'
       or exists (
         select 1 from public.installations where hardware_id = p_hardware_id
       ) then
      return jsonb_build_object('ok', false, 'error', 'RECOVERY_NOT_ALLOWED');
    end if;

    select i.* into v_installation
    from public.installations i
    join public.company_members m on m.company_id = i.company_id
    where m.user_id = p_user_id
      and m.role = 'owner'
      and m.active = true
      and i.device_class = 'principal'
      and i.status = 'active'
      and i.billing_status <> 'removed'
      and i.hardware_id ~ '^[0-9]{12,20}$';
    v_hardware_rebound := true;
  end if;

  v_company := v_installation.company_id;
  v_previous_hardware := v_installation.hardware_id;

  -- Mantém a mesma ordem global de locks dos fluxos financeiros.
  perform 1 from public.company_subscriptions
  where company_id = v_company for update;
  perform 1 from public.company_members
  where company_id = v_company
    and user_id = p_user_id
    and role = 'owner'
    and active = true
  for update;
  if not found then
    return jsonb_build_object('ok', false, 'error', 'RECOVERY_NOT_ALLOWED');
  end if;

  select * into v_installation
  from public.installations
  where id = v_installation.id
  for update;
  if not found
     or v_installation.status <> 'active'
     or v_installation.billing_status = 'removed'
     or v_installation.device_class <> 'principal' then
    return jsonb_build_object('ok', false, 'error', 'RECOVERY_NOT_ALLOWED');
  end if;

  if exists (
    select 1 from public.audit_events
    where actor_user_id = p_user_id
      and action = 'installation.principal_recovered'
      and occurred_at > now() - interval '1 minute'
  ) then
    return jsonb_build_object('ok', false, 'error', 'RECOVERY_RATE_LIMITED');
  end if;

  v_token := encode(extensions.gen_random_bytes(32), 'hex');
  update public.installations
  set hardware_id = case when v_hardware_rebound then p_hardware_id else hardware_id end,
      token_hash = encode(extensions.digest(v_token, 'sha256'), 'hex'),
      token_issued_at = now()
  where id = v_installation.id;

  insert into public.audit_events(
    actor_user_id, actor_installation_id, action, target_type, target_id, metadata
  ) values (
    p_user_id,
    v_installation.id,
    'installation.principal_recovered',
    'installation',
    v_installation.id::text,
    jsonb_build_object(
      'company_id', v_company,
      'hardware_rebound', v_hardware_rebound,
      'previous_hardware_hash', encode(extensions.digest(v_previous_hardware, 'sha256'), 'hex'),
      'current_hardware_hash', encode(extensions.digest(p_hardware_id, 'sha256'), 'hex')
    )
  );

  return jsonb_build_object(
    'ok', true,
    'installation_id', v_installation.id,
    'installation_token', v_token,
    'hardware_rebound', v_hardware_rebound
  );
end;
$$;

revoke all on function public.recover_principal_access_server(uuid, text)
  from public, anon, authenticated;
grant execute on function public.recover_principal_access_server(uuid, text)
  to service_role;

commit;
