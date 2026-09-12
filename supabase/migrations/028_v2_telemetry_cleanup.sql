begin;

create index if not exists installations_due_removal_idx
  on public.installations(removal_scheduled_for, id)
  where billing_status = 'pending_removal';

create index if not exists message_reservations_completed_cleanup_idx
  on public.message_send_reservations(completed_at, id)
  where status in ('confirmed', 'released');

-- Operações de manutenção chamadas pelo cron-worker com service_role.
-- Lotes limitados reduzem a duração dos locks e permitem concorrência entre
-- execuções por meio de SKIP LOCKED.
create or replace function public.cleanup_expired_telemetry(p_batch_size integer default 5000)
returns integer
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  deleted_count integer;
begin
  if p_batch_size < 1 or p_batch_size > 10000 then
    raise exception 'INVALID_BATCH_SIZE';
  end if;

  with expired as (
    select id
    from public.telemetry_events
    where expires_at < now()
    order by expires_at
    limit p_batch_size
    for update skip locked
  )
  delete from public.telemetry_events target
  using expired
  where target.id = expired.id;

  get diagnostics deleted_count = row_count;
  return deleted_count;
end;
$$;

create or replace function public.cleanup_completed_message_reservations(
  p_batch_size integer default 5000
)
returns integer
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  deleted_count integer;
begin
  if p_batch_size < 1 or p_batch_size > 10000 then
    raise exception 'INVALID_BATCH_SIZE';
  end if;

  with completed as (
    select id
    from public.message_send_reservations
    where status in ('confirmed', 'released')
      and completed_at < now() - interval '90 days'
    order by completed_at, id
    limit p_batch_size
    for update skip locked
  )
  delete from public.message_send_reservations target
  using completed
  where target.id = completed.id;

  get diagnostics deleted_count = row_count;
  return deleted_count;
end;
$$;

create or replace function public.process_due_device_removals_server(p_batch_size integer default 250)
returns integer
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  processed_count integer;
begin
  if p_batch_size < 1 or p_batch_size > 1000 then
    raise exception 'INVALID_BATCH_SIZE';
  end if;

  with due as (
    select id
    from public.installations
    where billing_status = 'pending_removal'
      and removal_scheduled_for <= now()
    order by removal_scheduled_for, id
    limit p_batch_size
    for update skip locked
  ), updated as (
    update public.installations target
    set billing_status = 'removed', online = false
    from due
    where target.id = due.id
      and target.billing_status = 'pending_removal'
    returning target.id
  ), audited as (
    insert into public.audit_events (
      actor_user_id, action, target_type, target_id, metadata
    )
    select null, 'installation.removal_executed', 'installation', id,
           jsonb_build_object('source', 'cron-worker')
    from updated
    returning 1
  )
  select count(*) into processed_count from audited;

  return processed_count;
end;
$$;

revoke all on function public.cleanup_expired_telemetry(integer)
  from public, anon, authenticated;
revoke all on function public.cleanup_completed_message_reservations(integer)
  from public, anon, authenticated;
revoke all on function public.process_due_device_removals_server(integer)
  from public, anon, authenticated;
grant execute on function public.cleanup_expired_telemetry(integer)
  to service_role;
grant execute on function public.cleanup_completed_message_reservations(integer)
  to service_role;
grant execute on function public.process_due_device_removals_server(integer)
  to service_role;

-- Supabase hospedado agenda tarefas por pg_cron. Quando a extensão já estiver
-- habilitada no projeto, instala/atualiza o job de forma idempotente. Se ainda
-- não estiver habilitada, a migração continua e registra um NOTICE; o mesmo
-- trabalho pode ser disparado pelo cron-worker autenticado até a ativação.
do $$
declare
  existing_job_id bigint;
  scheduled_job_id bigint;
begin
  if to_regnamespace('cron') is null then
    raise notice 'Supabase Cron não habilitado; job saas-hourly-maintenance não agendado';
    return;
  end if;

  execute 'select jobid from cron.job where jobname = $1 limit 1'
    into existing_job_id
    using 'saas-hourly-maintenance';
  if existing_job_id is not null then
    execute 'select cron.unschedule($1)' using existing_job_id;
  end if;

  execute 'select cron.schedule($1, $2, $3)'
    into scheduled_job_id
    using
      'saas-hourly-maintenance',
      '0 * * * *',
      'select public.cleanup_expired_telemetry(5000); '
      'select public.cleanup_completed_message_reservations(5000); '
      'select public.process_due_device_removals_server(250);';
end;
$$;

commit;
