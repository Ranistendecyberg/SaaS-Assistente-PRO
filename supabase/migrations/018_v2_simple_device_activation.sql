-- Ativação simplificada de computador adicional.
-- O computador novo precisa somente de um código curto, descartável e armazenado como hash.

begin;

create table if not exists public.device_link_attempts (
  id bigint generated always as identity primary key,
  hardware_hash text not null check (char_length(hardware_hash) = 64),
  attempted_at timestamptz not null default now(),
  succeeded boolean not null default false
);

create index if not exists device_link_attempts_rate_idx
  on public.device_link_attempts(hardware_hash, attempted_at desc);

alter table public.device_link_attempts enable row level security;
alter table public.device_link_attempts force row level security;
revoke all on table public.device_link_attempts from public, anon, authenticated;
grant select, insert, update, delete on table public.device_link_attempts to service_role;
grant usage, select on sequence public.device_link_attempts_id_seq to service_role;

create or replace function public.redeem_device_link_code_server(
  p_code_hash text,
  p_hardware_id text,
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
  v_attempt_id bigint;
  v_hardware_hash text;
  v_token text;
  v_device_class text;
  v_subscription public.company_subscriptions%rowtype;
  v_expires_at timestamptz;
  v_report_links jsonb := '{}'::jsonb;
  v_adjustment_notice text;
  v_diagnostics_until timestamptz;
begin
  if p_code_hash is null or length(p_code_hash) <> 64 then
    return jsonb_build_object('ok', false, 'error', 'INVALID_LINK_CODE');
  end if;
  if p_hardware_id is null or char_length(p_hardware_id) not between 8 and 128 then
    return jsonb_build_object('ok', false, 'error', 'INVALID_HARDWARE');
  end if;

  v_hardware_hash := encode(extensions.digest(p_hardware_id, 'sha256'), 'hex');
  if (
    select count(*)
    from public.device_link_attempts
    where hardware_hash = v_hardware_hash
      and succeeded = false
      and attempted_at >= now() - interval '15 minutes'
  ) >= 5 then
    return jsonb_build_object('ok', false, 'error', 'LINK_CODE_RATE_LIMITED');
  end if;

  insert into public.device_link_attempts(hardware_hash)
  values (v_hardware_hash)
  returning id into v_attempt_id;

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
  if exists (select 1 from public.installations where hardware_id = p_hardware_id) then
    return jsonb_build_object('ok', false, 'error', 'INSTALLATION_ALREADY_EXISTS');
  end if;

  select * into v_subscription
  from public.company_subscriptions
  where company_id = v_code.company_id
  for share;
  if not found or v_subscription.status not in ('trial', 'active') then
    return jsonb_build_object('ok', false, 'error', 'SUBSCRIPTION_NOT_ACTIVE');
  end if;
  v_expires_at := coalesce(v_subscription.current_period_end, v_subscription.trial_expires_at);
  if v_expires_at is null or v_expires_at <= now() then
    return jsonb_build_object('ok', false, 'error', 'SUBSCRIPTION_EXPIRED');
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

  v_token := encode(extensions.gen_random_bytes(32), 'hex');
  insert into public.installations (
    company_id, business_unit_id, hardware_id, token_hash, token_issued_at,
    status, app_version, device_class, billing_status, activated_by, activated_at
  ) values (
    v_code.company_id, v_code.business_unit_id, p_hardware_id,
    encode(extensions.digest(v_token, 'sha256'), 'hex'), now(),
    'active', nullif(trim(p_app_version), ''), v_device_class, 'active',
    v_code.created_by, now()
  ) returning id into v_installation_id;

  select l.report_links, l.adjustment_notice, l.detailed_diagnostics_until
  into v_report_links, v_adjustment_notice, v_diagnostics_until
  from public.licenses l
  join public.installations i on i.id = l.installation_id
  where i.company_id = v_code.company_id
    and i.device_class = 'principal'
    and i.billing_status <> 'removed'
  order by i.created_at
  limit 1;

  insert into public.licenses (
    installation_id, status, license_type, expires_at, monthly_price,
    report_links, adjustment_notice, detailed_diagnostics_until
  ) values (
    v_installation_id,
    case when v_subscription.status = 'trial' then 'trial' else 'active' end,
    case when v_subscription.status = 'trial' then 'trial' else 'subscription' end,
    v_expires_at,
    v_subscription.additional_seat_price,
    coalesce(v_report_links, '{}'::jsonb),
    v_adjustment_notice,
    v_diagnostics_until
  );

  update public.device_link_codes
  set status = 'used', redeemed_by_installation = v_installation_id,
      redeemed_by_user = v_code.created_by, redeemed_at = now()
  where id = v_code.id;

  update public.device_link_attempts set succeeded = true where id = v_attempt_id;

  insert into public.audit_events (
    actor_user_id, actor_installation_id, action, target_type, target_id, metadata
  ) values (
    v_code.created_by, v_installation_id, 'installation.device_linked',
    'installation', v_installation_id::text,
    jsonb_build_object(
      'activation_mode', 'one_time_code',
      'device_class', v_device_class,
      'business_unit_id', v_code.business_unit_id,
      'hardware_hash', v_hardware_hash
    )
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

revoke all on function public.redeem_device_link_code_server(text, text, text)
  from public, anon, authenticated;
grant execute on function public.redeem_device_link_code_server(text, text, text)
  to service_role;

drop function if exists public.redeem_device_link_code_server(text, text, uuid, text);

commit;
