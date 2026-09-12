-- Local clone only; all synthetic fixtures rolled back.
begin;
do $$
declare
 actor uuid := gen_random_uuid(); c jsonb; inv jsonb; attempt jsonb; result jsonb;
 company uuid; aid uuid; before_state jsonb;
begin
 insert into auth.users(id,email_confirmed_at) values(actor,now());
 c := public.create_company_trial_server(actor,'Recovery Test','Test Owner','86999999999','52998224725','recovery-test-'||actor,'test');
 assert (c->>'ok')::boolean;
 company := (c->>'company_id')::uuid;
 inv := public.prepare_company_invoice_server(actor,company);
 assert (inv->>'ok')::boolean;
 attempt := public.prepare_billing_attempt_server(actor,(inv->'invoice'->>'id')::uuid,'pix');
 assert (attempt->>'ok')::boolean;
 aid := (attempt->'attempt'->>'id')::uuid;
 result := public.record_provider_order_server(aid,'fixture-'||actor,'fixture-'||actor,'pending','pending',null,'TEST',null);
 assert (result->>'ok')::boolean;
 select to_jsonb(s) into before_state from company_subscriptions s where company_id=company;
 result := public.claim_payment_status_check_server(gen_random_uuid(),company,aid);
 assert result->>'error'='OWNER_REQUIRED';
 result := public.claim_payment_status_check_server(actor,company,gen_random_uuid());
 assert result->>'error'='PAYMENT_NOT_FOUND';
 result := public.claim_payment_status_check_server(actor,company,aid);
 assert (result->>'ok')::boolean;
 assert result->>'provider_id'='fixture-'||actor;
 result := public.claim_payment_status_check_server(actor,company,aid);
 assert result->>'error'='PAYMENT_RATE_LIMITED';
 assert (select to_jsonb(s)=before_state from company_subscriptions s where company_id=company);
 assert not has_function_privilege('authenticated','public.claim_payment_status_check_server(uuid,uuid,uuid)','EXECUTE');
 assert not has_function_privilege('anon','public.claim_payment_status_check_server(uuid,uuid,uuid)','EXECUTE');
 raise notice 'PASS recovery owner, target, throttle, unchanged subscription and ACL';
end $$;
rollback;
