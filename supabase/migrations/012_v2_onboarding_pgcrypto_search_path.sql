-- O Supabase instala pgcrypto no schema extensions. A rotina de onboarding
-- precisa enxergar gen_random_bytes() e digest() durante a criacao do trial.

begin;

alter function public.create_company_trial_server(
  uuid, text, text, text, text, text, text
) set search_path = public, auth, extensions;

commit;
