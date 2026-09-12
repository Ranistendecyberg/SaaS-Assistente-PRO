# SaaS Assistente PRO 2.1.3

## Estabilidade e escalabilidade

- Corrige invalidação de históricos e índices de leads quando arquivos mudam em outra tela ou instância.
- Evita callbacks duplicados entre Extração e WhatsApp durante o carregamento sob demanda.
- Reduz risco de crescimento ilimitado no backend com limpeza em lotes de telemetria, reservas concluídas e remoções vencidas.
- Corrige a ordem de locks entre instalações e assinatura para evitar deadlock entre heartbeat/Admin e confirmação de pagamento.

## Conta empresarial e segurança

- Transferência do computador principal passa a ser exclusivamente do proprietário, tanto na interface quanto no servidor.
- Transferência atômica reescrita para o esquema atual, com locks determinísticos e auditoria.
- Rotinas de manutenção ficam restritas à service role; o fallback HTTP exige `CRON_SECRET`.

## Validação

- 198 testes Desktop aprovados.
- 17 cenários financeiros, 13 cenários HTTP/webhook e testes de migração aprovados.
- Migrações 024–029 aplicadas em clone PostgreSQL 17.11.
- Concorrência exercitada com duas conexões reais, sem deadlock nem timeout.
- Instalador verificado por SHA-256 e por instalação silenciosa isolada.
- Migrações 024–029 e funções `account-api`/`cron-worker` publicadas no Supabase de produção.
- Manutenção horária ativada no Supabase Cron; chamadas não autenticadas às funções protegidas retornam 401.

## Integridade do instalador

- Arquivo: `Instalador_SaaS_Assistente_PRO_v2.1.3.exe`
- Tamanho: `201277520` bytes
- SHA-256: `6cc9223ca379cef0736775e708673973a445448c9599d6de6087e439af8d4176`

Observação: esta build ainda não possui assinatura digital Authenticode e pode gerar aviso do Windows SmartScreen. A versão foi publicada no GitHub e disponibilizada via OTA opcional.
