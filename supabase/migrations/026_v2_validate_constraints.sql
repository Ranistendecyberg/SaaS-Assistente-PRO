begin;

-- Valida somente constraints pendentes do schema da aplicação. A versão
-- anterior percorria todos os schemas e tentava validar até constraints já
-- válidas, aumentando locks e podendo atingir objetos de extensões.
do $$
declare
  rec record;
begin
  for rec in
    select ns.nspname as schema_name,
           cls.relname as table_name,
           con.conname as constraint_name
    from pg_constraint con
    join pg_class cls on cls.oid = con.conrelid
    join pg_namespace ns on ns.oid = cls.relnamespace
    where ns.nspname = 'public'
      and con.contype = 'c'
      and not con.convalidated
    order by cls.relname, con.conname
  loop
    execute format(
      'alter table %I.%I validate constraint %I',
      rec.schema_name, rec.table_name, rec.constraint_name
    );
  end loop;
end;
$$;

commit;
