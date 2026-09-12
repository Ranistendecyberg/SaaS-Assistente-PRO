-- Per-installation overrides; existing installations retain their defaults.
alter table public.licenses
  add column if not exists daily_message_limit integer
    check (daily_message_limit between 1 and 1000),
  add column if not exists batch_limit integer not null default 1
    check (batch_limit between 1 and 1000);
