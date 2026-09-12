-- Isolated clone only. All fixture changes rolled back.
begin;
do $$
declare
  actor uuid := gen_random_uuid();
  created jsonb;
  extra uuid;
  result jsonb;
  before_subscription jsonb;
  before_expiry timestamptz;
begin
  insert into auth.users(id,email_confirmed_at) values(actor,now());
  created := public.create_company_trial_server(actor,'Admin Test','Test Owner','86999999999','52998224725','admin-test-'||actor,'test');
  assert (created->>'ok')::boolean;
  insert into public.installations(company_id,business_unit_id,hardware_id,token_hash,status,device_class,billing_status)
    values((created->>'company_id')::uuid,(created->>'business_unit_id')::uuid,'extra-test-'||actor,repeat('a',64),'active','additional','active') returning id into extra;
  insert into public.licenses(installation_id,status,license_type,expires_at,monthly_price)
    values(extra,'trial','trial',now()+interval '2 days',50);
  select to_jsonb(s) into before_subscription from public.company_subscriptions s where company_id=(created->>'company_id')::uuid;
  select expires_at into before_expiry from public.licenses where installation_id=extra;
  result := public.admin_set_enterprise_device_status_server(actor,extra,'blocked');
  assert (result->>'ok')::boolean;
  assert (select status='blocked' from public.installations where id=extra);
  assert (select status='blocked' from public.licenses where installation_id=extra);
  assert (select status='active' from public.installations where id=(created->>'installation_id')::uuid), 'Principal unaffected';
  result := public.admin_set_enterprise_device_status_server(actor,extra,'active');
  assert (result->>'ok')::boolean;
  assert (select status='trial' and expires_at=before_expiry from public.licenses where installation_id=extra), 'No renewal on unblock';
  assert (select to_jsonb(s)=before_subscription from public.company_subscriptions s where company_id=(created->>'company_id')::uuid), 'Subscription unchanged';
  update public.company_subscriptions set current_period_end=now()-interval '1 day',trial_expires_at=now()-interval '1 day' where company_id=(created->>'company_id')::uuid;
  result := public.admin_set_enterprise_device_status_server(actor,extra,'blocked');
  assert (result->>'ok')::boolean;
  result := public.admin_set_enterprise_device_status_server(actor,extra,'active');
  assert result->>'error'='SUBSCRIPTION_NOT_ACTIVE', 'Expired account cannot be activated';
  assert not has_function_privilege('authenticated','public.admin_set_enterprise_device_status_server(uuid,uuid,text)','EXECUTE'), 'RPC grant: restore migration permissions before testing a no-privileges clone';
  raise notice 'PASS: admin block/unblock, principal preserved, expiry unchanged and expired subscription refused';
end;
$$;
rollback;
