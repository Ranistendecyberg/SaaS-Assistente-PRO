\set ON_ERROR_STOP on
begin;
set local lock_timeout = '5s';
update public.installations
set online = online
where id = (
  select id from public.installations
  where company_id is not null
  order by id limit 1
);
select pg_sleep(2);
commit;
