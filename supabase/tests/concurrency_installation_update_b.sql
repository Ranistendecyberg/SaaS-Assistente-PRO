\set ON_ERROR_STOP on
begin;
set local lock_timeout = '5s';
select 1
from public.company_subscriptions
where company_id = (
  select company_id from public.installations
  where company_id is not null
  order by id limit 1
)
for update;
select pg_sleep(1);
update public.installations
set online = online
where id = (
  select id from public.installations
  where company_id is not null
  order by id limit 1
);
commit;
