-- Restore a credential only for the owner's existing principal hardware.
-- The Edge endpoint authenticates the user and requires a recent email OTP.
begin;
create index if not exists audit_principal_recovery_idx on public.audit_events(actor_user_id,occurred_at desc)
  where action='installation.principal_recovered';
create or replace function public.recover_principal_access_server(p_user_id uuid, p_hardware_id text)
returns jsonb language plpgsql security definer set search_path = public, extensions
as $$
declare
  v_installation public.installations%rowtype;
  v_company uuid;
  v_token text;
begin
  if p_user_id is null or char_length(coalesce(p_hardware_id,'')) not between 8 and 128 then
    return jsonb_build_object('ok',false,'error','RECOVERY_NOT_ALLOWED');
  end if;
  select i.company_id into v_company from public.installations i
    join public.company_members m on m.company_id=i.company_id
    where i.hardware_id=p_hardware_id and i.device_class='principal'
      and m.user_id=p_user_id and m.role='owner' and m.active=true;
  if v_company is null then
    return jsonb_build_object('ok',false,'error','RECOVERY_NOT_ALLOWED');
  end if;
  -- Same lock ordering used by billing 020.
  perform 1 from public.company_subscriptions where company_id=v_company for update;
  perform 1 from public.company_members where company_id=v_company
    and user_id=p_user_id and role='owner' and active=true for update;
  if not found then return jsonb_build_object('ok',false,'error','RECOVERY_NOT_ALLOWED'); end if;
  select * into v_installation from public.installations
    where hardware_id=p_hardware_id and company_id=v_company and device_class='principal' for update;
  if not found or v_installation.status <> 'active' or v_installation.billing_status='removed' then
    return jsonb_build_object('ok',false,'error','RECOVERY_NOT_ALLOWED');
  end if;
  if exists(select 1 from public.audit_events where actor_user_id=p_user_id
      and action='installation.principal_recovered' and occurred_at > now()-interval '1 minute') then
    return jsonb_build_object('ok',false,'error','RECOVERY_RATE_LIMITED');
  end if;
  v_token := encode(extensions.gen_random_bytes(32),'hex');
  update public.installations set token_hash=encode(extensions.digest(v_token,'sha256'),'hex'),
    token_issued_at=now() where id=v_installation.id;
  insert into public.audit_events(actor_user_id,actor_installation_id,action,target_type,target_id,metadata)
    values(p_user_id,v_installation.id,'installation.principal_recovered','installation',v_installation.id::text,
      jsonb_build_object('company_id',v_company));
  return jsonb_build_object('ok',true,'installation_id',v_installation.id,'installation_token',v_token);
end;
$$;
revoke all on function public.recover_principal_access_server(uuid,text) from public,anon,authenticated;
grant execute on function public.recover_principal_access_server(uuid,text) to service_role;
commit;
