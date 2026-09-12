begin;

-- UPDATE já possui lock da linha de installations antes de executar o trigger.
-- Tentar obter o lock da assinatura nesse ponto cria a ordem inversa do fluxo
-- financeiro (assinatura -> instalações) e pode causar deadlock. Atualizações
-- ficam serializadas pelo próprio row lock; as RPCs de pagamento reavaliam o
-- snapshot depois de obter as linhas. INSERT ainda bloqueia a assinatura antes
-- de tornar a nova máquina visível. DELETE empresarial continua proibido.
create or replace function public.lock_installation_company_billing()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  if TG_OP = 'UPDATE' then
    if new.company_id is distinct from old.company_id then
      raise exception 'COMPANY_TRANSFER_NOT_ALLOWED';
    end if;
    return new;
  end if;

  if TG_OP = 'DELETE' then
    if exists (
      select 1 from public.company_subscriptions
      where company_id = old.company_id
    ) then
      raise exception 'ENTERPRISE_DEVICE_DELETE_FORBIDDEN';
    end if;
    return old;
  end if;

  perform 1
  from public.company_subscriptions
  where company_id = new.company_id
  for update;
  return new;
end;
$$;

revoke all on function public.lock_installation_company_billing()
  from public, anon, authenticated, service_role;

commit;
