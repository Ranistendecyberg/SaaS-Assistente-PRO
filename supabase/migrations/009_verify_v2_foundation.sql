-- Verificação sem dados pessoais da fundação 2.0.

select
  to_regclass('public.companies') is not null as companies_ok,
  to_regclass('public.business_units') is not null as units_ok,
  to_regclass('public.company_members') is not null as members_ok,
  to_regclass('public.installations') is not null as installations_ok,
  to_regclass('public.company_subscriptions') is not null as subscriptions_ok,
  to_regclass('public.device_link_codes') is not null as link_codes_ok,
  to_regclass('public.billing_profiles') is not null as billing_profiles_ok,
  to_regclass('public.billing_invoices') is not null as invoices_ok,
  to_regclass('public.billing_payment_attempts') is not null as payment_attempts_ok;

select
  count(*) filter (where rowsecurity) as tabelas_com_rls,
  count(*) as total_tabelas_publicas
from pg_tables
where schemaname = 'public';

select
  has_table_privilege('anon', 'public.companies', 'select') as anon_le_empresas,
  has_table_privilege('authenticated', 'public.company_members', 'select') as usuario_le_membros,
  has_table_privilege('service_role', 'public.company_subscriptions', 'select') as servidor_le_assinaturas,
  has_function_privilege(
    'anon', 'public.consume_message_server(uuid,integer)', 'execute'
  ) as anon_consumiria_mensagem,
  has_function_privilege(
    'service_role', 'public.consume_message_server(uuid,integer)', 'execute'
  ) as servidor_consumiria_mensagem;

select current_version, default_monthly_price, maintenance_mode
from public.system_config
where singleton = true;
