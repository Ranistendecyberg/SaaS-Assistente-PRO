-- Permissoes explicitas para as Edge Functions.
-- anon e authenticated permanecem sem acesso direto.

begin;

grant usage on schema public to service_role;
grant all privileges on all tables in schema public to service_role;
grant all privileges on all sequences in schema public to service_role;
grant execute on all functions in schema public to service_role;

alter default privileges in schema public
  grant all privileges on tables to service_role;
alter default privileges in schema public
  grant all privileges on sequences to service_role;
alter default privileges in schema public
  grant execute on functions to service_role;

-- Reafirma o bloqueio dos clientes depois dos grants do servidor.
revoke all on all tables in schema public from anon, authenticated;
revoke all on all sequences in schema public from anon, authenticated;

commit;

select
  has_schema_privilege('service_role', 'public', 'usage') as servidor_acessa_schema,
  has_table_privilege('service_role', 'public.admin_users', 'select') as servidor_le_admins,
  has_table_privilege('anon', 'public.admin_users', 'select') as anon_le_admins,
  has_table_privilege('authenticated', 'public.admin_users', 'select') as usuario_le_admins;
