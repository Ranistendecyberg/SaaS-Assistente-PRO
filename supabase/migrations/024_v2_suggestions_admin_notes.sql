-- Adiciona coluna admin_notes à tabela suggestions.
-- A admin-api já consulta essa coluna em list_suggestions;
-- sem ela, a listagem retorna erro do PostgREST.
begin;
alter table public.suggestions add column if not exists admin_notes text;
commit;
