-- Run ONLY on the isolated restored clone, after migration 021. No provider calls.
begin;
do $$
declare
  owner_a uuid := gen_random_uuid();
  owner_b uuid := gen_random_uuid();
  result jsonb;
begin
  assert public.valid_tax_document('52998224725'), 'CPF validation';
  assert public.valid_tax_document('11222333000181'), 'CNPJ validation';
  assert not public.valid_tax_document('52998224724'), 'CPF checksum rejection';
  assert not public.valid_tax_document('11222333000182'), 'CNPJ checksum rejection';
  assert not public.valid_tax_document('11111111111'), 'Repeated digits rejection';
  assert not public.valid_tax_document(null), 'NULL rejection';
  insert into auth.users(id,email_confirmed_at) values (owner_a,now()),(owner_b,now());
  result := public.create_company_trial_server(owner_a,'Teste CPF','Titular Teste','86999999999','52998224725','cpf-test-'||owner_a,'test');
  assert (result->>'ok')::boolean, 'CPF onboarding';
  assert exists(select from public.business_units where company_id=(result->>'company_id')::uuid and cnpj='52998224725'), 'CPF stored unchanged';
  insert into public.billing_profiles(company_id,legal_name,billing_cnpj,billing_email,postal_code,street,street_number,neighborhood,city,state)
    values ((result->>'company_id')::uuid,'Titular Teste','52998224725','teste@example.com','64000000','Rua Teste','1','Centro','Teresina','PI');
  begin
    update public.billing_profiles set billing_cnpj='52998224724' where company_id=(result->>'company_id')::uuid;
    raise exception 'Invalid payer document was accepted';
  exception when check_violation then null;
  end;
  result := public.create_company_trial_server(owner_a,'Outra Conta','Titular Teste','86999999999','11222333000181','other-test-'||owner_a,'test');
  assert result->>'error'='USER_ALREADY_HAS_COMPANY', 'Same owner cannot repeat trial with another document';
  result := public.create_company_trial_server(owner_b,'Duplicado','Titular Teste','86999999999','52998224725','cpf-test-'||owner_b,'test');
  assert result->>'error'='CNPJ_ALREADY_REGISTERED', 'Duplicate document prevented (legacy error code)';
  result := public.create_company_trial_server(owner_b,'Teste CNPJ','Titular Teste','86999999999','11222333000181','cnpj-test-'||owner_b,'test');
  assert (result->>'ok')::boolean, 'CNPJ backward compatibility';
  assert not has_function_privilege('anon','public.create_company_trial_server(uuid,text,text,text,text,text,text)','EXECUTE'), 'Anonymous onboarding RPC denied';
  raise notice 'PASS: real CPF/CNPJ validation, onboarding, billing profile, duplicate/owner rejection, CNPJ compatibility and RPC permissions';
end;
$$;
rollback;
