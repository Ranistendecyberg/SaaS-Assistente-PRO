-- Vinculacao segura e de uso unico para instalacoes migradas do Firebase.

begin;

alter table public.installations
  add column if not exists migration_claim_hash text,
  add column if not exists migration_claim_until timestamptz,
  add column if not exists migration_claimed_at timestamptz,
  add column if not exists legacy_imported_at timestamptz;

create unique index if not exists idx_installations_migration_claim_hash
  on public.installations(migration_claim_hash)
  where migration_claim_hash is not null;

alter table public.installations
  drop constraint if exists installations_migration_claim_consistency;
alter table public.installations
  add constraint installations_migration_claim_consistency check (
    (migration_claim_hash is null and migration_claim_until is null)
    or
    (migration_claim_hash is not null and migration_claim_until is not null)
  );

grant all privileges on table public.installations to service_role;
revoke all on table public.installations from anon, authenticated;

commit;
