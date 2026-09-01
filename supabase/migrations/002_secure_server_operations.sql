-- Operações atômicas usadas exclusivamente pelas Edge Functions.
-- Clientes anon/authenticated não recebem EXECUTE direto.

begin;

create or replace function public.redeem_license_key_server(
  p_installation_id uuid,
  p_code_hash text
) returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  key_row public.license_keys%rowtype;
  license_row public.licenses%rowtype;
  company_name text;
  new_expiry timestamptz;
  new_extra integer;
begin
  if p_installation_id is null or char_length(coalesce(p_code_hash, '')) <> 64 then
    return jsonb_build_object('ok', false, 'error', 'INVALID_KEY');
  end if;

  select * into key_row
  from public.license_keys
  where code_hash = p_code_hash
  for update;

  if not found then
    return jsonb_build_object('ok', false, 'error', 'INVALID_KEY');
  end if;
  if key_row.status <> 'new' then
    return jsonb_build_object('ok', false, 'error', 'KEY_' || upper(key_row.status));
  end if;
  if key_row.usable_until < now() then
    update public.license_keys set status = 'expired' where id = key_row.id;
    return jsonb_build_object('ok', false, 'error', 'KEY_EXPIRED');
  end if;

  select c.name into company_name
  from public.installations i
  join public.companies c on c.id = i.company_id
  where i.id = p_installation_id and i.status = 'active';
  if company_name is null then
    return jsonb_build_object('ok', false, 'error', 'INSTALLATION_NOT_FOUND');
  end if;
  if key_row.intended_company is not null
     and lower(trim(key_row.intended_company)) <> lower(trim(company_name)) then
    return jsonb_build_object('ok', false, 'error', 'KEY_COMPANY_MISMATCH');
  end if;

  select * into license_row
  from public.licenses
  where installation_id = p_installation_id
  for update;
  if not found then
    return jsonb_build_object('ok', false, 'error', 'LICENSE_NOT_FOUND');
  end if;

  if key_row.key_type = 'messages' then
    update public.licenses
    set extra_messages = extra_messages + key_row.messages_to_add
    where id = license_row.id
    returning expires_at, extra_messages into new_expiry, new_extra;
  elsif key_row.key_type = 'days' then
    new_expiry := greatest(license_row.expires_at, now())
      + make_interval(days => key_row.days_to_add);
    update public.licenses
    set status = 'active', license_type = 'subscription', expires_at = new_expiry
    where id = license_row.id
    returning extra_messages into new_extra;
  elsif key_row.key_type = 'fixed_expiry' then
    -- Regra comercial: nunca encurtar uma licença que já vence mais tarde.
    new_expiry := greatest(license_row.expires_at, key_row.fixed_expiry);
    update public.licenses
    set status = 'active', license_type = 'subscription', expires_at = new_expiry
    where id = license_row.id
    returning extra_messages into new_extra;
  else
    return jsonb_build_object('ok', false, 'error', 'INVALID_KEY_TYPE');
  end if;

  update public.license_keys
  set status = 'used', redeemed_by = p_installation_id, redeemed_at = now()
  where id = key_row.id;

  insert into public.audit_events (
    actor_installation_id, action, target_type, target_id, metadata
  ) values (
    p_installation_id, 'license.key_redeemed', 'license_key', key_row.id::text,
    jsonb_build_object('key_type', key_row.key_type, 'expires_at', new_expiry)
  );

  return jsonb_build_object(
    'ok', true, 'key_type', key_row.key_type,
    'expires_at', new_expiry, 'extra_messages', coalesce(new_extra, 0)
  );
end;
$$;

create or replace function public.consume_message_server(
  p_installation_id uuid,
  p_daily_limit integer
) returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  license_row public.licenses%rowtype;
  local_day date := timezone('America/Fortaleza', now())::date;
  current_count integer;
  remaining_extra integer;
begin
  if p_daily_limit < 1 or p_daily_limit > 1000 then
    return jsonb_build_object('ok', false, 'error', 'INVALID_DAILY_LIMIT');
  end if;

  select l.* into license_row
  from public.licenses l
  join public.installations i on i.id = l.installation_id
  where l.installation_id = p_installation_id
    and i.status = 'active'
  for update of l;

  if not found or license_row.status not in ('trial', 'active')
     or license_row.expires_at <= now() then
    return jsonb_build_object('ok', false, 'error', 'LICENSE_NOT_ACTIVE');
  end if;

  if license_row.extra_messages > 0 then
    update public.licenses
    set extra_messages = extra_messages - 1
    where id = license_row.id
    returning extra_messages into remaining_extra;
    return jsonb_build_object(
      'ok', true, 'allowed', true, 'source', 'extra',
      'extra_messages', remaining_extra
    );
  end if;

  insert into public.daily_usage (installation_id, usage_date, sent_count)
  values (p_installation_id, local_day, 0)
  on conflict (installation_id, usage_date) do nothing;

  select sent_count into current_count
  from public.daily_usage
  where installation_id = p_installation_id and usage_date = local_day
  for update;

  if current_count >= p_daily_limit then
    return jsonb_build_object(
      'ok', false, 'allowed', false, 'error', 'DAILY_LIMIT_REACHED',
      'sent_count', current_count, 'daily_limit', p_daily_limit
    );
  end if;

  update public.daily_usage
  set sent_count = sent_count + 1
  where installation_id = p_installation_id and usage_date = local_day
  returning sent_count into current_count;

  return jsonb_build_object(
    'ok', true, 'allowed', true, 'source', 'daily',
    'sent_count', current_count, 'daily_limit', p_daily_limit
  );
end;
$$;

revoke all on function public.redeem_license_key_server(uuid, text)
  from public, anon, authenticated;
revoke all on function public.consume_message_server(uuid, integer)
  from public, anon, authenticated;
grant execute on function public.redeem_license_key_server(uuid, text)
  to service_role;
grant execute on function public.consume_message_server(uuid, integer)
  to service_role;

commit;
