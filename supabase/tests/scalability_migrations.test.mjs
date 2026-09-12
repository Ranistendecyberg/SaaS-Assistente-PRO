import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { PGlite } from "@electric-sql/pglite";

const here = dirname(fileURLToPath(import.meta.url));
const db = new PGlite();

await db.exec(`
  create schema auth;
  create schema cron;
  create role anon;
  create role authenticated;
  create role service_role;
  create table auth.users(id uuid primary key);
  create table public.companies(id uuid primary key);
  create table public.business_units(id uuid primary key);
  create table public.company_subscriptions(
    id uuid primary key,
    company_id uuid not null unique references public.companies(id)
  );
  create table public.installations(
    id uuid primary key,
    company_id uuid references public.companies(id),
    business_unit_id uuid references public.business_units(id),
    device_class text not null,
    billing_status text not null,
    removal_scheduled_for timestamptz,
    online boolean not null default false,
    updated_at timestamptz not null default now()
  );
  create unique index installations_single_principal
    on public.installations(company_id)
    where device_class='principal' and billing_status <> 'removed';
  create table public.billing_reconciliation_cases(company_id uuid);
  create table public.device_link_codes(company_id uuid, business_unit_id uuid);
  create table public.telemetry_events(
    id bigint generated always as identity primary key,
    expires_at timestamptz not null
  );
  create table public.message_send_reservations(
    id uuid primary key,
    status text not null,
    completed_at timestamptz
  );
  create table public.audit_events(
    id bigint generated always as identity primary key,
    actor_user_id uuid,
    action text not null,
    target_type text not null,
    target_id text,
    metadata jsonb not null default '{}'::jsonb
  );
  create table cron.job(
    jobid bigint generated always as identity primary key,
    jobname text not null,
    schedule text not null,
    command text not null
  );
  create function cron.schedule(text,text,text) returns bigint language plpgsql as $$
  declare new_id bigint;
  begin
    insert into cron.job(jobname,schedule,command) values ($1,$2,$3)
      returning jobid into new_id;
    return new_id;
  end;
  $$;
  create function cron.unschedule(bigint) returns boolean language plpgsql as $$
  begin
    delete from cron.job where jobid=$1;
    return found;
  end;
  $$;
`);

for (const migration of [
  "025_v2_transfer_principal.sql",
  "026_v2_validate_constraints.sql",
  "028_v2_telemetry_cleanup.sql",
  "029_v2_installation_lock_order.sql",
]) {
  await db.exec(await readFile(join(here, "..", "migrations", migration), "utf8"));
}

const scheduled = await db.query(
  "select jobname,schedule,command from cron.job where jobname='saas-hourly-maintenance'",
);
assert.equal(scheduled.rows.length, 1);
assert.equal(scheduled.rows[0].schedule, "0 * * * *");
assert.match(scheduled.rows[0].command, /process_due_device_removals_server/);

const company = "00000000-0000-4000-8000-000000000001";
const principal = "00000000-0000-4000-8000-000000000002";
const additional = "00000000-0000-4000-8000-000000000003";
await db.query("insert into public.companies(id) values ($1)", [company]);
await db.query(
  "insert into public.company_subscriptions(id,company_id) values ($1,$2)",
  ["00000000-0000-4000-8000-000000000004", company],
);
await db.query(
  `insert into public.installations(id,company_id,device_class,billing_status)
   values ($1,$2,'principal','active'),($3,$2,'additional','active')`,
  [principal, company, additional],
);

const transfer = await db.query(
  "select public.transfer_principal_server($1,$2) result",
  [company, additional],
);
assert.equal(transfer.rows[0].result.ok, true);
const devices = await db.query(
  "select id,device_class from public.installations order by id",
);
assert.deepEqual(devices.rows.map((row) => row.device_class), ["additional", "principal"]);

await db.exec(`
  insert into public.telemetry_events(expires_at)
  values (now()-interval '1 day'),(now()-interval '1 hour'),(now()+interval '1 day');
`);
const cleanup = await db.query("select public.cleanup_expired_telemetry(1) count");
assert.equal(cleanup.rows[0].count, 1);
assert.equal((await db.query("select count(*)::int count from public.telemetry_events")).rows[0].count, 2);

await db.exec(`
  insert into public.message_send_reservations(id,status,completed_at) values
  ('00000000-0000-4000-8000-000000000010','confirmed',now()-interval '100 days'),
  ('00000000-0000-4000-8000-000000000011','released',now()-interval '10 days'),
  ('00000000-0000-4000-8000-000000000012','reserved',null);
`);
const reservationCleanup = await db.query(
  "select public.cleanup_completed_message_reservations(10) count",
);
assert.equal(reservationCleanup.rows[0].count, 1);
assert.equal(
  (await db.query("select count(*)::int count from public.message_send_reservations")).rows[0].count,
  2,
);

await db.query(
  `update public.installations set billing_status='pending_removal',
   removal_scheduled_for=now()-interval '1 hour',online=true where id=$1`,
  [principal],
);
const removals = await db.query(
  "select public.process_due_device_removals_server(10) count",
);
assert.equal(removals.rows[0].count, 1);
const removed = await db.query(
  "select billing_status,online from public.installations where id=$1",
  [principal],
);
assert.deepEqual(removed.rows[0], { billing_status: "removed", online: false });

console.log("scalability migrations: ok");
await db.close();
