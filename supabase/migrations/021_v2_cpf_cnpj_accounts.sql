-- CPF/CNPJ support. Legacy column/RPC names retained for older clients.
-- Does not change invoices, payment snapshots or existing documents.
begin;
create or replace function public.valid_tax_document(p_document text)
returns boolean language plpgsql immutable set search_path = public as $$
declare
  n integer := char_length(p_document);
  base text;
  total integer;
  digit integer;
  weights integer[];
  step integer;
  i integer;
begin
  if p_document is null or p_document !~ '^[0-9]+$' or n not in (11,14)
     or p_document = repeat(substr(p_document,1,1),n) then return false; end if;
  base := substr(p_document,1,n-2);
  for step in 1..2 loop
    if n = 11 then
      total := 0;
      for i in 1..char_length(base) loop
        total := total + substr(base,i,1)::integer * (char_length(base)+2-i);
      end loop;
    else
      weights := case when step=1 then array[5,4,3,2,9,8,7,6,5,4,3,2]
        else array[6,5,4,3,2,9,8,7,6,5,4,3,2] end;
      total := 0;
      for i in 1..char_length(base) loop
        total := total + substr(base,i,1)::integer * weights[i];
      end loop;
    end if;
    digit := total % 11;
    base := base || (case when digit < 2 then 0 else 11-digit end)::text;
  end loop;
  return base = p_document;
end;
$$;
alter table public.business_units drop constraint if exists business_units_cnpj_check;
alter table public.business_units add constraint business_units_cnpj_check
  check (cnpj is null or public.valid_tax_document(cnpj)) not valid;
alter table public.billing_profiles drop constraint if exists billing_profiles_billing_cnpj_check;
alter table public.billing_profiles add constraint billing_profiles_billing_cnpj_check
  check (public.valid_tax_document(billing_cnpj)) not valid;
comment on column public.business_units.cnpj is 'CPF (11 digits) or CNPJ (14 digits); legacy name retained for compatibility.';
comment on column public.billing_profiles.billing_cnpj is 'Payer CPF or CNPJ; legacy name retained for compatibility.';
create or replace function public.create_company_trial_server(
  p_user_id uuid,
  p_company_name text,
  p_owner_name text,
  p_phone text,
  p_cnpj text,
  p_hardware_id text,
  p_app_version text default null
)
returns jsonb
language plpgsql
security definer
set search_path = public, auth, extensions
as $$
declare
  v_company_id uuid;
  v_unit_id uuid;
  v_installation_id uuid;
  v_installation_token text;
  v_trial_expires_at timestamptz := now() + interval '2 days';
begin
  -- Serialize onboarding for the same owner; the document unique index handles different owners.
  perform 1 from auth.users where id = p_user_id for update;
  if p_user_id is null or not exists (
    select 1 from auth.users
    where id = p_user_id and email_confirmed_at is not null
  ) then
    return jsonb_build_object('ok', false, 'error', 'EMAIL_CONFIRMATION_REQUIRED');
  end if;
  if exists (
    select 1 from public.company_members
    where user_id = p_user_id and active = true
  ) then
    return jsonb_build_object('ok', false, 'error', 'USER_ALREADY_HAS_COMPANY');
  end if;
  if char_length(trim(coalesce(p_company_name, ''))) not between 2 and 160
     or char_length(trim(coalesce(p_owner_name, ''))) not between 2 and 160
     or coalesce(p_phone, '') !~ '^[0-9]{10,15}$'
     or not public.valid_tax_document(p_cnpj)
     or char_length(trim(coalesce(p_hardware_id, ''))) not between 8 and 128 then
    return jsonb_build_object('ok', false, 'error', 'INVALID_ONBOARDING');
  end if;
  if exists (select 1 from public.business_units where cnpj = p_cnpj) then
    return jsonb_build_object('ok', false, 'error', 'CNPJ_ALREADY_REGISTERED');
  end if;
  if exists (select 1 from public.installations where hardware_id = p_hardware_id) then
    return jsonb_build_object('ok', false, 'error', 'INSTALLATION_ALREADY_EXISTS');
  end if;

  insert into public.companies (name, manager_name, phone, active)
  values (trim(p_company_name), trim(p_owner_name), p_phone, true)
  returning id into v_company_id;

  insert into public.business_units (
    company_id, unit_type, display_name, cnpj, active
  ) values (
    v_company_id, 'headquarters', trim(p_company_name), p_cnpj, true
  ) returning id into v_unit_id;

  insert into public.company_members (company_id, user_id, role, active)
  values (v_company_id, p_user_id, 'owner', true);

  v_installation_token := encode(gen_random_bytes(32), 'hex');
  insert into public.installations (
    company_id, business_unit_id, hardware_id, token_hash, token_issued_at,
    status, app_version, device_class, billing_status, activated_by, activated_at
  ) values (
    v_company_id, v_unit_id, trim(p_hardware_id),
    encode(digest(v_installation_token, 'sha256'), 'hex'), now(),
    'active', nullif(trim(p_app_version), ''), 'principal', 'active', p_user_id, now()
  ) returning id into v_installation_id;

  insert into public.company_subscriptions (
    company_id, status, pricing_origin, base_price, additional_seat_price,
    trial_expires_at, current_period_start, current_period_end
  ) values (
    v_company_id, 'trial', 'v2_standard', 300.00, 50.00,
    v_trial_expires_at, now(), v_trial_expires_at
  );

  -- Compatibilidade temporária com os consumidores de licença da 1.9.6.
  -- Será removida quando todas as telas consultarem company_subscriptions.
  insert into public.licenses (
    installation_id, status, license_type, expires_at, monthly_price
  ) values (
    v_installation_id, 'trial', 'trial', v_trial_expires_at, 300.00
  );

  insert into public.audit_events (
    actor_user_id, actor_installation_id, action, target_type, target_id, metadata
  ) values (
    p_user_id, v_installation_id, 'company.trial_created',
    'company', v_company_id::text,
    jsonb_build_object('business_unit_id', v_unit_id, 'trial_expires_at', v_trial_expires_at)
  );

  return jsonb_build_object(
    'ok', true,
    'company_id', v_company_id,
    'business_unit_id', v_unit_id,
    'installation_id', v_installation_id,
    'installation_token', v_installation_token,
    'device_class', 'principal',
    'trial_expires_at', v_trial_expires_at
  );
exception
  when unique_violation then
    return jsonb_build_object('ok', false, 'error', 'ONBOARDING_ALREADY_USED');
end;
$$;

revoke all on function public.create_company_trial_server(
  uuid, text, text, text, text, text, text
) from public, anon, authenticated;
grant execute on function public.create_company_trial_server(
  uuid, text, text, text, text, text, text
) to service_role;


commit;
