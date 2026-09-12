# Análise de arquitetura e escalabilidade — 11/09/2026

## Arquitetura observada

O produto é um Desktop Windows local-first. A interface PyQt6 mantém navegadores
QWebEngine isolados para myHonda/Salesforce e WhatsApp; extração e automação são
feitas por JavaScript injetado. Históricos operacionais permanecem em JSON local,
enquanto identidade, licenciamento, contas empresariais, cotas, auditoria e
cobrança são centralizados em PostgreSQL/Supabase por Edge Functions.

Fluxo resumido:

1. Desktop autentica instalação/usuário nas Edge Functions.
2. PostgreSQL executa regras críticas em RPCs transacionais e aplica RLS/ACL.
3. QWebEngine extrai os relatórios e mantém sessões locais separadas.
4. Python normaliza, deduplica e persiste históricos locais.
5. Dashboards processam os históricos com pandas e renderizam ECharts.
6. Envios reservam cota no servidor, usam WhatsApp Web e confirmam/liberam a reserva.
7. Telemetria sanitizada é enviada em lotes e expira no backend.

## Problemas encontrados e tratamento

| Prioridade | Problema | Impacto | Tratamento |
|---|---|---|---|
| Crítica | O `cron-worker` referenciava `client` antes da criação, continha TypeScript inválido, usava uma API de agendamento não documentada pelo Supabase e expunha execução manual sem autenticação | Worker não iniciava; remoções e retenção não eram processadas | Agendamento transferido para Supabase Cron/`pg_cron`; fallback manual protegido por `CRON_SECRET` |
| Crítica | Migração 028 usava delimitador inválido e tabela inexistente `telemetry` | Migração não aplicava e telemetria crescia sem retenção | RPC de limpeza em lotes sobre `telemetry_events`, `SKIP LOCKED`, índice e ACL service-role |
| Alta | Migração 025 usava `role` e `telemetry`, inexistentes no esquema atual | Transferência do principal falhava em produção | RPC atômica reescrita com `device_class`, auditoria e locks determinísticos |
| Alta | API/tela permitiam administrador transferir o principal, apesar da regra exigir proprietário | Divergência de autorização e risco contratual | `ownerOnly` no servidor e `can_transfer_principal` na interface |
| Alta | Lazy loading conectava sinais Extração↔WhatsApp duas vezes dependendo da ordem de abertura | Callback duplicado, avanço duplo da fila e possível envio duplicado | Conexão única e idempotente após as duas telas existirem |
| Alta | Cache de leads mantinha índice tipado antigo após gravação | Cliente/telefone antigos podiam ser associados a uma pesquisa | Invalidação conjunta do mapa e de todos os índices derivados |
| Alta | Caches TSI/SSI eram locais a cada `DatabaseManager` | Dashboard aberto por outra instância podia ficar desatualizado indefinidamente | Assinatura `(mtime_ns, tamanho)` invalida o cache entre instâncias |
| Média | Remoções vencidas eram buscadas integralmente e atualizadas uma a uma pela Edge Function | Muitas viagens ao banco, memória crescente e concorrência frágil | RPC set-based em lotes de 250 com `SKIP LOCKED`, auditoria na mesma transação e índice parcial |
| Média | Reservas concluídas de mensagens não tinham retenção | Crescimento contínuo da tabela por envio | Exclusão em lotes após 90 dias, preservando reservas abertas |
| Média | Migração 026 tentava validar checks de todos os schemas, inclusive já válidos | Locks desnecessários e possível interferência em extensões | Restrição a checks `NOT VALID` do schema `public` |
| Crítica | Trigger de `installations` bloqueava a máquina e depois a assinatura; pagamentos faziam assinatura e depois máquina | Deadlock possível entre heartbeat/Admin e confirmação financeira | Migração 029 remove lock cruzado em UPDATE; row lock e revalidação de snapshot preservam consistência |

## Capacidade após as alterações

- Leituras repetidas dos históricos e buscas de leads deixam de refazer parsing e
  varreduras quando os arquivos não mudaram.
- A abertura inicial não instancia os quatro maiores conjuntos de widgets/QWebEngine.
- Remoções e retenção são bounded: cada chamada possui lote máximo, ordem estável
  e pode coexistir com outro worker sem processar a mesma linha.
- Quando Supabase Cron está habilitado, o job horário é criado pela migração;
  caso contrário, a migração emite `NOTICE` e o endpoint autenticado é o fallback.
- Operações financeiras existentes continuam transacionais e idempotentes; as
  novas rotinas de manutenção não alteram faturas ou pagamentos.

## Limites arquiteturais restantes

1. JSON local ainda exige leitura e regravação O(n) a cada importação. Migrar os
   históricos para SQLite somente quando houver migração reversível, backup e
   testes comparativos. Gatilho recomendado: arquivo acima de 25 MB ou 50 mil
   registros em uma instalação.
2. pandas materializa todo o histórico para os dashboards. Para bases grandes,
   pré-agregar por mês/loja no SQLite e carregar detalhes apenas sob demanda.
3. QWebEngine continua sendo o maior consumidor de RAM. Lazy loading reduz o pico
   inicial, mas telas já abertas permanecem residentes para preservar sessões.
4. A consulta de conta limita faturas a 24, porém unidades e computadores ainda
   são retornados de uma vez. Introduzir paginação quando uma conta puder exceder
   aproximadamente 100 computadores.
5. Seletores de myHonda/Salesforce e WhatsApp são dependências externas mutáveis;
   exigem smoke tests autorizados nas páginas reais.
6. `AppCache` e `QueueManager` existem, mas não estão integrados ao fluxo principal;
   não devem ser considerados ganho de produção até existir adoção e cobertura.
7. O instalador Windows ainda não possui assinatura Authenticode. A integridade é
   protegida pelo SHA-256 do manifesto, mas o SmartScreen pode alertar o usuário até
   que seja usado um certificado de assinatura de código com reputação.

## Evidência de regressão

- 198 de 198 testes Python executados com sucesso usando Python 3.14 e dependências
  nativas compatíveis, incluindo os três testes visuais anteriormente bloqueados.
- 17 cenários de segurança financeira aprovados em PGlite.
- 13 cenários do webhook/recovery aprovados com mocks de rede e HMAC real.
- Migrações 024 a 029 aplicadas em clone PostgreSQL 17.11. Duas sessões reais
  concorrentes confirmaram a mesma ordem de locks e encerraram com `COMMIT`, sem
  deadlock nem timeout.
- Migrações 025, 026, 028 e 029 também foram exercitadas em PGlite, incluindo troca
  do principal, retenção, lotes, remoção vencida e o contrato do trigger corrigido.
- Instalador 2.1.3 compilado e instalado silenciosamente em pasta isolada; a
  instalação terminou sem reinício e o executável instalado teve SHA-256 idêntico
  ao executável de origem.

As migrações 024–029 foram aplicadas no Supabase remoto e as Edge Functions
`account-api` e `cron-worker` foram publicadas. O postflight confirmou objetos,
ACLs e respostas 401 sem autenticação. Supabase Cron 1.6.4 foi habilitado e o job
`saas-hourly-maintenance` ficou ativo com execução horária. Não houve operação
sobre contas ou pagamentos reais nesta revisão.
