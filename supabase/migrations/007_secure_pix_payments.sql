-- Sessões PIX vinculadas à instalação. O cliente nunca altera a licença.
begin;

create table if not exists public.payment_sessions (
  provider_payment_id text primary key,
  installation_id uuid not null references public.installations(id) on delete cascade,
  amount numeric(10,2) not null check (amount > 0),
  status text not null default 'pending' check (status in ('pending', 'applied', 'expired', 'cancelled')),
  created_at timestamptz not null default now(),
  expires_at timestamptz not null default (now() + interval '24 hours'),
  applied_at timestamptz
);

create index if not exists payment_sessions_installation_idx
  on public.payment_sessions (installation_id, created_at desc);

alter table public.payment_sessions enable row level security;
alter table public.payment_sessions force row level security;
revoke all on table public.payment_sessions from public, anon, authenticated;
grant select, insert, update on table public.payment_sessions to service_role;

create or replace function public.apply_approved_payment_server(
  p_installation_id uuid,
  p_provider_payment_id text
) returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  payment_row public.payment_sessions%rowtype;
  new_expiry timestamptz;
begin
  select * into payment_row
  from public.payment_sessions
  where provider_payment_id = p_provider_payment_id
    and installation_id = p_installation_id
  for update;

  if not found then
    return jsonb_build_object('ok', false, 'error', 'PAYMENT_NOT_FOUND');
  end if;
  if payment_row.status = 'applied' then
    select expires_at into new_expiry from public.licenses
      where installation_id = p_installation_id;
    return jsonb_build_object('ok', true, 'already_applied', true, 'expires_at', new_expiry);
  end if;
  if payment_row.status <> 'pending' or payment_row.expires_at < now() then
    update public.payment_sessions set status = 'expired'
      where provider_payment_id = p_provider_payment_id and status = 'pending';
    return jsonb_build_object('ok', false, 'error', 'PAYMENT_SESSION_EXPIRED');
  end if;

  update public.licenses
  set status = 'active',
      license_type = 'subscription',
      expires_at = greatest(expires_at, now()) + interval '30 days',
      updated_at = now()
  where installation_id = p_installation_id
  returning expires_at into new_expiry;

  if new_expiry is null then
    return jsonb_build_object('ok', false, 'error', 'LICENSE_NOT_FOUND');
  end if;

  update public.payment_sessions
  set status = 'applied', applied_at = now()
  where provider_payment_id = p_provider_payment_id;

  insert into public.audit_events (
    actor_installation_id, action, target_type, target_id, metadata
  ) values (
    p_installation_id, 'license.pix_renewed', 'installation', p_installation_id::text,
    jsonb_build_object('provider_payment_id_hash', encode(extensions.digest(p_provider_payment_id, 'sha256'), 'hex'),
                       'amount', payment_row.amount, 'expires_at', new_expiry)
  );

  return jsonb_build_object('ok', true, 'already_applied', false, 'expires_at', new_expiry);
end;
$$;

revoke all on function public.apply_approved_payment_server(uuid, text)
  from public, anon, authenticated;
grant execute on function public.apply_approved_payment_server(uuid, text)
  to service_role;

commit;
