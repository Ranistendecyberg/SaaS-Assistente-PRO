begin;

create table if not exists public.message_send_reservations (
  id uuid primary key,
  installation_id uuid not null
    references public.installations(id) on delete cascade,
  usage_date date,
  source text not null check (source in ('daily', 'extra')),
  status text not null default 'reserved'
    check (status in ('reserved', 'confirmed', 'released')),
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

create index if not exists message_send_reservations_installation_idx
  on public.message_send_reservations (installation_id, created_at desc);

alter table public.message_send_reservations enable row level security;
revoke all on table public.message_send_reservations from public, anon, authenticated;
grant all on table public.message_send_reservations to service_role;

create or replace function public.reserve_message_send_server(
  p_installation_id uuid,
  p_daily_limit integer,
  p_reservation_id uuid
) returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  license_row public.licenses%rowtype;
  reservation_row public.message_send_reservations%rowtype;
  local_day date := timezone('America/Fortaleza', now())::date;
  current_count integer;
  remaining_extra integer;
  source_value text;
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

  select * into reservation_row
  from public.message_send_reservations
  where id = p_reservation_id
  for update;

  if found then
    if reservation_row.installation_id <> p_installation_id then
      return jsonb_build_object('ok', false, 'error', 'RESERVATION_MISMATCH');
    end if;
    return jsonb_build_object(
      'ok', reservation_row.status in ('reserved', 'confirmed'),
      'allowed', reservation_row.status in ('reserved', 'confirmed'),
      'reservation_id', reservation_row.id,
      'reservation_status', reservation_row.status,
      'source', reservation_row.source
    );
  end if;

  if license_row.extra_messages > 0 then
    update public.licenses
    set extra_messages = extra_messages - 1
    where id = license_row.id
    returning extra_messages into remaining_extra;
    source_value := 'extra';
  else
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
    set sent_count = sent_count + 1, updated_at = now()
    where installation_id = p_installation_id and usage_date = local_day
    returning sent_count into current_count;
    source_value := 'daily';
  end if;

  insert into public.message_send_reservations (
    id, installation_id, usage_date, source, status
  ) values (
    p_reservation_id, p_installation_id,
    case when source_value = 'daily' then local_day else null end,
    source_value, 'reserved'
  );

  return jsonb_build_object(
    'ok', true, 'allowed', true, 'reservation_id', p_reservation_id,
    'reservation_status', 'reserved', 'source', source_value,
    'sent_count', current_count, 'daily_limit', p_daily_limit,
    'extra_messages', remaining_extra
  );
end;
$$;

create or replace function public.confirm_message_send_server(
  p_installation_id uuid,
  p_reservation_id uuid
) returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  reservation_row public.message_send_reservations%rowtype;
begin
  select * into reservation_row
  from public.message_send_reservations
  where id = p_reservation_id and installation_id = p_installation_id
  for update;

  if not found then
    return jsonb_build_object('ok', false, 'error', 'RESERVATION_NOT_FOUND');
  end if;
  if reservation_row.status = 'confirmed' then
    return jsonb_build_object('ok', true, 'reservation_status', 'confirmed');
  end if;
  if reservation_row.status <> 'reserved' then
    return jsonb_build_object('ok', false, 'error', 'RESERVATION_ALREADY_RELEASED');
  end if;

  update public.message_send_reservations
  set status = 'confirmed', completed_at = now()
  where id = p_reservation_id;
  return jsonb_build_object('ok', true, 'reservation_status', 'confirmed');
end;
$$;

create or replace function public.release_message_send_server(
  p_installation_id uuid,
  p_reservation_id uuid
) returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  license_row public.licenses%rowtype;
  reservation_row public.message_send_reservations%rowtype;
  current_count integer;
  remaining_extra integer;
begin
  select l.* into license_row
  from public.licenses l
  where l.installation_id = p_installation_id
  for update;

  if not found then
    return jsonb_build_object('ok', false, 'error', 'LICENSE_NOT_FOUND');
  end if;

  select * into reservation_row
  from public.message_send_reservations
  where id = p_reservation_id and installation_id = p_installation_id
  for update;

  if not found then
    return jsonb_build_object('ok', false, 'error', 'RESERVATION_NOT_FOUND');
  end if;
  if reservation_row.status = 'released' then
    return jsonb_build_object('ok', true, 'reservation_status', 'released');
  end if;
  if reservation_row.status = 'confirmed' then
    return jsonb_build_object('ok', false, 'error', 'RESERVATION_ALREADY_CONFIRMED');
  end if;

  if reservation_row.source = 'extra' then
    update public.licenses
    set extra_messages = extra_messages + 1
    where id = license_row.id
    returning extra_messages into remaining_extra;
  else
    update public.daily_usage
    set sent_count = greatest(0, sent_count - 1), updated_at = now()
    where installation_id = p_installation_id
      and usage_date = reservation_row.usage_date
    returning sent_count into current_count;
  end if;

  update public.message_send_reservations
  set status = 'released', completed_at = now()
  where id = p_reservation_id;

  return jsonb_build_object(
    'ok', true, 'reservation_status', 'released',
    'sent_count', current_count, 'extra_messages', remaining_extra
  );
end;
$$;

revoke all on function public.reserve_message_send_server(uuid, integer, uuid)
  from public, anon, authenticated;
revoke all on function public.confirm_message_send_server(uuid, uuid)
  from public, anon, authenticated;
revoke all on function public.release_message_send_server(uuid, uuid)
  from public, anon, authenticated;
grant execute on function public.reserve_message_send_server(uuid, integer, uuid)
  to service_role;
grant execute on function public.confirm_message_send_server(uuid, uuid)
  to service_role;
grant execute on function public.release_message_send_server(uuid, uuid)
  to service_role;

commit;
