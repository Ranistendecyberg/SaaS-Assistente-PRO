-- Local restored clone only. All fixtures rolled back.
begin;
do $$
declare
  u uuid := gen_random_uuid();
  other_user uuid := gen_random_uuid();
  h text := 'recover-test-'||u;
  created jsonb;
  recovered jsonb;
  subscription_before jsonb;
  license_before jsonb;
  installation_before jsonb;
begin
  insert into auth.users(id,email_confirmed_at) values(u,now()),(other_user,now());
  created := public.create_company_trial_server(u,'Recovery Test','Test Owner','86999999999','52998224725',h,'test');
  assert (created->>'ok')::boolean, 'Fixture created';
  -- A blocked license must remain blocked after recovery.
  update public.licenses set status='blocked' where installation_id=(created->>'installation_id')::uuid;
  select to_jsonb(s) into subscription_before from public.company_subscriptions s where company_id=(created->>'company_id')::uuid;
  select to_jsonb(l) into license_before from public.licenses l where installation_id=(created->>'installation_id')::uuid;
  select to_jsonb(i)-'token_hash'-'token_issued_at'-'updated_at' into installation_before from public.installations i where id=(created->>'installation_id')::uuid;
  recovered := public.recover_principal_access_server(other_user,h);
  assert recovered->>'error'='RECOVERY_NOT_ALLOWED', 'Other owner denied';
  recovered := public.recover_principal_access_server(u,'unknown-machine');
  assert recovered->>'error'='RECOVERY_NOT_ALLOWED', 'Unknown machine denied';
  recovered := public.recover_principal_access_server(u,h);
  assert (recovered->>'ok')::boolean, 'Owner recovers same principal';
  assert recovered->>'installation_token' <> created->>'installation_token', 'Credential rotated';
  assert exists(select from public.installations where id=(created->>'installation_id')::uuid and token_hash=encode(extensions.digest(recovered->>'installation_token','sha256'),'hex')), 'Only token hash stored';
  assert (select to_jsonb(s)=subscription_before from public.company_subscriptions s where company_id=(created->>'company_id')::uuid), 'Subscription unchanged';
  assert (select to_jsonb(l)=license_before from public.licenses l where installation_id=(created->>'installation_id')::uuid), 'License and block unchanged';
  assert (select to_jsonb(i)-'token_hash'-'token_issued_at'-'updated_at'=installation_before from public.installations i where id=(created->>'installation_id')::uuid), 'Hardware and device state unchanged';
  recovered := public.recover_principal_access_server(u,h);
  assert recovered->>'error'='RECOVERY_RATE_LIMITED', 'Repeat recovery throttled';
  update public.installations set device_class='additional' where id=(created->>'installation_id')::uuid;
  recovered := public.recover_principal_access_server(u,h);
  assert recovered->>'error'='RECOVERY_NOT_ALLOWED', 'Additional machine cannot recover principal';
  update public.installations set device_class='principal',status='blocked' where id=(created->>'installation_id')::uuid;
  recovered := public.recover_principal_access_server(u,h);
  assert recovered->>'error'='RECOVERY_NOT_ALLOWED', 'Blocked installation cannot recover';
  assert not has_function_privilege('authenticated','public.recover_principal_access_server(uuid,text)','EXECUTE'), 'Client cannot bypass Edge OTP';
  assert not has_function_privilege('anon','public.recover_principal_access_server(uuid,text)','EXECUTE'), 'Anonymous RPC denied';
  raise notice 'PASS: owner/hardware authorization, token rotation, rate limit, unchanged license/subscription and RPC permissions';
end;
$$;
rollback;
