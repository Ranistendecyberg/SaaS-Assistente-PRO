begin;

-- Adiciona suporte a cobrança pro-rata na assinatura
alter table public.company_subscriptions add column if not exists prorated_amount decimal(10,2) default 0.0;
alter table public.company_subscriptions add column if not exists next_billing_date timestamp with time zone;

commit;
