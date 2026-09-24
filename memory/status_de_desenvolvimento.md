# Status de Desenvolvimento — Assistente PRO Desktop

## Auditoria de arquitetura e escalabilidade — 11/09/2026

- Corrigidos cache TSI/SSI entre instâncias, índice de leads obsoleto e conexão duplicada de sinais nas telas lazy.
- Migrações 025/026/028 tornadas executáveis e compatíveis com o esquema real. Transferência de principal agora é atômica; manutenção usa lotes, `SKIP LOCKED`, índices parciais e ACL service-role.
- Transferência do principal alinhada à regra owner-only na tela e account-api.
- Regressão final: 198 testes Python aprovados com Pillow compatível. Backend: 17 financeiros, 13 HTTP e suíte de migrações de escalabilidade aprovados.
- Migrações 024–029 aprovadas em clone PostgreSQL 17.11; duas conexões reais confirmaram a correção da ordem de locks sem deadlock/timeout. Clone encerrado após o teste.
- Release oficial 2.1.3 compilada. Instalador com 201.277.520 bytes e SHA-256 `6cc9223ca379cef0736775e708673973a445448c9599d6de6087e439af8d4176`; manifesto confere em hash, tamanho e versão.
- Smoke test instalou silenciosamente em pasta isolada, confirmou binário idêntico e foi removido sem reinício. A instalação oficial existente foi preservada e seu atalho do Menu Iniciar restaurado após o teste.
- Migrações 024–029 aplicadas no Supabase de produção. `account-api` e `cron-worker` publicados; postflight confirmou as ACLs, endpoint sem autenticação respondeu 401 e nenhuma conta/pagamento real foi alterada.
- `pg_cron` 1.6.4 habilitado e job `saas-hourly-maintenance` ativo a cada hora para as três rotinas de limpeza em lote.
- Código publicado na `main` e release pública `v2.1.3` criada no GitHub. O asset remoto confirmou 201.277.520 bytes e SHA-256 `6cc9223ca379cef0736775e708673973a445448c9599d6de6087e439af8d4176`.
- OTA ativado no Supabase como opcional: `current_version=2.1.3`, `minimum_version=0.0.0`, `update_required=false`, com URL pública e SHA-256 conferidos no postflight.
- Site público atualizado no mesmo endereço: botões apontam diretamente para o instalador 2.1.3 e a marca do cabeçalho/rodapé usa o ícone oficial do aplicativo. Publicação Sites versão 2 concluída com sucesso.
- Análise completa e limites residuais registrados em `memory/analise_escalabilidade_2026-09-11.md`. O instalador ainda não está assinado digitalmente, repetindo o modelo de distribuição da 1.9.6 com possível aviso do SmartScreen.

## Otimizações de escalabilidade — 11/09/2026

- **8 grupos de melhorias implementados** sem quebrar funcionalidades existentes. 69 testes unitários aprovados após as mudanças. Ponto de restauração criado em `backups/restore_point_pre_scalability_20260911_201300.zip` (SHA-256: C06B59D67F305CF7E19478ACE92F8845167ABB9CD1AA470DF4D5DC42FEE0B11D).
- **Versão 2.1.1 gerada com sucesso!** Instalador compilado em `dist/Instalador_SaaS_Assistente_PRO_v2.1.1.exe`. Manifesto em `release_v2.1.1.json`. SHA-256 do instalador: `da4259587323266eb09dc533dbf4fb312f93cefb56d92ca58ca798208c2c71b6`.
- **Novo:** `src/core/app_cache.py` — Cache singleton thread-safe com TTL. Centraliza armazenamento temporário em memória.
- **Novo:** `src/ui/lazy_screen.py` — Proxy que instancia telas PyQt6 somente na primeira exibição. Sinais reconectados via callbacks `on_ready()`.
- **Modificado:** `src/core/database.py` — Cache em memória (`_records_cache`, `_ssi_cache`, `_leads_index_cache`), invalidado em escritas. `find_lead()` usa índice pré-computado O(1). `import re` movido ao topo. Compatível com testes que usam `__new__` via `_ensure_cache_attrs()`.
- **Modificado:** `src/core/license_manager.py` — Singleton via `LicenseManager.get_instance()`. Hardware ID cacheado como variável de classe (powershell apenas uma vez por processo). `LicenseManager()` legado preservado para compatibilidade com testes.
- **Modificado:** `src/core/dashboard_engine.py` — `_rebuild_indexes()` pré-computa dicionários de lojas e consultores. Lookups O(1) substituem loops O(n×m). `import re`/`unicodedata` no topo.
- **Modificado:** `src/core/queue_manager.py` — Persistência JSON atômica opcional (`persist=False` por padrão — retrocompatível).
- **Modificado:** `src/core/backup_manager.py` — `criar_backup()` executa em thread daemon, não bloqueia inicialização.
- **Modificado:** `src/core/telemetry.py` — `_save_queue()` usa escrita atômica (`os.replace`). `_machine_id()` reutiliza `LicenseManager._cached_chassi` sem novo subprocess.
- **Modificado:** `src/ui/main_window.py` — `ExtractionScreen`, `WhatsAppScreen`, `DashboardTabsScreen`, `CompanyAccountScreen` carregadas sob demanda via `LazyScreen`. `LicenseManager` acessado via `get_instance()`.


- Instalador dist/Instalador_SaaS_Assistente_PRO_v2.0.7.exe compilado com sucesso; manifesto release_v2.0.7.json. SHA-256 98eb2d9e35223cd340600fa990f786ad47fcf9e451b85f4cbde76d1f6dc45e2b. Versões anteriores preservadas; não instalado automaticamente nem publicado OTA.
- 023 publicada e billing-api v14 ACTIVE. Postflight: função existe, anon/authenticated sem EXECUTE, service_role autorizado; endpoint refresh_payment_status sem autenticação respondeu 401 UNAUTHORIZED. Demais funções/Admin preservados.
- Prévia offscreen com dados fictícios inspecionada: botão de consulta visível, sem corte. Regressão final: 93 Desktop, 17 SQL PGlite e 13 handler simulados aprovados. PostgreSQL real local e Deno check aprovados.
- Uso: proprietário abre cobrança e escolhe Já paguei — consultar Mercado Pago; não cria novo PIX. Não exige pagar para teste. Aceite do instalador/consulta autenticada real ainda pendente, assim como concorrência financeira e entrega externa do webhook. Esta entrega não significa homologação financeira integral.


## Recuperação publicada / Desktop 2.0.7 em preparação — 11/09/2026

- Migração 023 aplicada com Success pelo painel do projeto hnwvtoiiuqagzmuqygkw; billing-api publicada por CLI após Deno check aprovado. Nenhuma cobrança foi consultada/paga/cancelada nesta publicação.
- Migração e teste payment_recovery_real_postgres.sql aprovados no clone PostgreSQL real: proprietário, alvo, throttle, assinatura preservada e ACL. Fixtures revertidas e servidor local parado.
- Tela agora oferece consulta manual pelo proprietário, mesmo quando a tentativa pendente não está pagável. Usa refresh_payment_status e depois recarrega resumo; não altera polling local de 15 segundos nem cria pagamentos. Mensagem de confirmação não promete desbloqueio de licença suspensa.
- 93 testes v2 aprovados. Teste estático ajustado para incluir nova ação na lista ownerOnly. 17 testes SQL e 13 HTTP simulados aprovados na etapa anterior. Preparando instalador 2.0.7; ainda não distribuído.


## Recuperação de status — backend local em preparação — 11/09/2026

- Migração 023_v2_payment_status_recovery.sql e endpoint refresh_payment_status implementados somente localmente. Exigem proprietário ativo e tentativa ligada à conta; ID do provedor vem do banco, nunca do cliente. Conferência de ID e referência externa da resposta antes de aplicar a RPC financeira 020.
- Campo last_provider_check_at e claim com bloqueio de linha limitam a consulta a uma por 30 segundos/tentativa entre workers; falha de consulta também consome intervalo. RPC restrita a service_role. Consulta GET não cria/cancela cobranças nem libera licença por declaração do cliente.
- 17 cenários SQL PGlite aprovados, incluindo isolamento entre contas, acesso de proprietário, throttle sequencial e licença inalterada pelo claim. 13 testes VM do handler aprovados, incluindo recuperação, throttle, recusa de papel e identidade divergente. Dependências de autenticação/provedor/RPC simuladas no teste HTTP.
- Trabalho incompleto: falta integração da tela, testes dessa interface, Deno check, validação da migração em PostgreSQL real e concorrência. NÃO publicado, NÃO ligado ao aplicativo instalado. Aplicar 023 antes de publicar endpoint; não apresentar como recurso já disponível.


## Handler de webhook testado localmente — 11/09/2026

- Nova suíte supabase/tests/billing_webhook.test.mjs: 9 testes aprovados. Executa o código atual do handler e helpers HTTP em VM Node 24, removendo tipos TypeScript; captura Deno.serve, sem abrir servidor. Fetch, autenticação e RPC simulados, HMAC-SHA256 real com segredo fictício.
- Verificados: assinatura inválida/ID adulterado sem acesso ao provedor/banco; assinatura válida; valor/status/referência obtidos do provedor em vez do corpo não confiável; repetição encaminhada à RPC; falhas de rede, HTTP 503, banco e recusa da RPC retornam erro; autenticação ausente recusada.
- Primeira execução: oito casos passaram e o caso de autenticação retornou 500 por diferença entre objetos Error da VM e do mock. Corrigido exclusivamente o harness compartilhando Error; repetição com nove casos aprovada. Nenhum código de produção modificado.
- Limites: autenticação real e persistência SQL não são exercitadas nesta suíte; idempotência de licenças está na suíte PGlite separada (16 cenários aprovados anteriormente). Não comprova entrega externa do Mercado Pago, comportamento sob concorrência ou recuperação sem webhook.
- Recuperação sem webhook ainda não implementada. Nenhuma cobrança real consultada, criada, paga ou cancelada. Sem publicação remota/novo instalador.


## Testes financeiros locais — 11/09/2026

- Executados 90 testes Python v2: todos aprovados. Executados 16 cenários financeiros em PGlite descartável: todos aprovados; suíte anterior tinha 15 cenários.
- Novo cenário verifica PIX de R$ 350 com principal e adicional: ambos renovados, duplicata não altera novamente as licenças e licença de outra conta permanece integralmente preservada.
- Também aprovados: cobrança antiga com máquina nova, substituição com mesma quantidade/preço, evento atrasado, valor inválido, bloqueio individual, snapshot imutável, tentativa legada e máquina adicionada após pagamento.
- Limite: PGlite usa esquema reduzido e digest simulado; testes sequenciais das funções SQL, não entrega HTTP de webhook, criptografia real, concorrência ou homologação integral do provedor. Nenhuma chamada financeira remota, publicação ou alteração de licença real nesta execução.
- Inspeção identificou pendência concreta: reconcileProvider consulta o provedor e aplica a RPC, mas é chamado pelo webhook. A consulta da tela carrega registros locais; não foi encontrado fluxo normal de recuperação de aprovação quando o webhook não chega. A consulta feita ao cancelar cobranças antigas não substitui essa recuperação.
- Dependência de teste instalada por npm com ignore-scripts; package-lock gerado para repetibilidade. Teste ampliado em supabase/tests/payment_safety.test.mjs.
- Relatos do usuário (não verificados remotamente nesta etapa): PIX antigo cancelado às 16:54; mantém principal e adicional; novo QR de R$ 350 gerado, sem confirmação de pagamento.


## Entrega 2.0.6 — revisão Admin/interface — 10/09/2026

- Instalador `dist/Instalador_SaaS_Assistente_PRO_v2.0.6.exe` compilado e manifesto conferido. SHA-256 `e1c5046824a844d0b890e30e3fcaca464299650ffa3dbe9717b5c338b1eb7ebc`. Não instalado automaticamente nem distribuído via OTA; instaladores anteriores preservados.
- Cabeçalho corrigido e prévia visual inspecionada com dados fictícios. Avisos financeiros mais específicos sem mudança da lógica de pagamento. Admin 2.0.4 preservado/compatível, nenhuma função remota ou migração de produção alterada nesta etapa.
- 90 testes v2, 39 testes direcionados sobrepostos e 19 testes de persistência/métricas/licenciamento/versionamento aprovados. Logs de erro nos testes de histórico corrompido eram esperados e usaram somente arquivos temporários.
- Teste sequencial Admin em PostgreSQL real isolado aprovado. Nenhuma máquina real bloqueada/desbloqueada, nenhum PIX gerado/cancelado/pago. Usuário está verificando a cobrança no provedor.
- Pendentes: aceite das telas 2.0.6, fechar/reabrir nos dois equipamentos, uso funcional real autorizado e concorrência (incluindo risco de ordem de locks documentado). Não apresentar esta revisão como homologação financeira completa.

## Revisão Admin e usabilidade — 10/09/2026 — 2.0.6 em preparação

- 39 testes direcionados Admin/MFA/interface aprovados. Teste PostgreSQL real no clone confirmou bloqueio/desbloqueio do adicional, principal preservado, mesma validade/assinatura e recusa de desbloqueio após vencimento. Fixtures desfeitas e servidor local encerrado; sem operação em equipamentos/cobranças reais.
- Primeira execução falhou apenas na asserção de privilégio: o clone fora restaurado com --no-privileges. Migração 014 reaplicada exclusivamente no clone para reconstruir funções/permissões do Admin; teste seguinte aprovado. Isso não evidencia falha de permissões em produção.
- Corrigido banner da Conta Empresarial: layout de texto tinha QSizePolicy Ignored sem stretch e perdia largura para um espaçador. Reprodução controlada mostrou largura anterior 0 e corrigida 870 pixels. Novo teste impede regressão.
- Avisos de pagamento agora distinguem fatura paga, cancelamento registrado no sistema, expiração, rejeição e devolução. Tentativa não pagável sem motivo específico não afirma cancelamento no provedor. Nenhuma lógica de liberação ou geração de cobrança alterada.
- Estes testes do Admin são sequenciais. Concorrência real permanece pendente; revisar especialmente ordem de locks da função admin_set_enterprise_device_status_server (instalação antes do trigger que bloqueia assinatura), em relação ao fluxo de pagamento 020 (assinatura antes de instalações).
- Extração/relatórios/envios e fechamento/reabertura reais das duas máquinas ainda requerem aceite controlado. Não disparar mensagens para clientes reais.

## Dois computadores na versão 2.0.5 — confirmação visual em 10/09/2026

- Screenshot enviado pelo proprietário mostra principal e adicional com situação Ativo e versão 2.0.5. Últimos acessos exibidos: 16:50 e 16:52, respectivamente. Atualização e comunicação do adicional com o servidor confirmadas pela tela, mantendo dois vínculos.
- Esta evidência não valida ainda operações funcionais completas no adicional, pagamento, webhook assinado ou concorrência financeira. Próximo passo: consultar a tela de cobrança sem gerar ou pagar nova cobrança, verificando a tentativa legada e os dados apresentados.

## Conta Empresarial conferida pelo proprietário — 10/09/2026

- Screenshots confirmam Conta Empresarial carregada com papel Proprietário, assinatura em teste gratuito, vigência exibida 11/09/2026, dois computadores e estimativa consolidada R$ 350,00.
- Lista mostra principal ativo na versão 2.0.5 e adicional ativo, ainda registrado na versão 2.0.0-beta.1, com último acesso anterior. Isso confirma o cadastro do adicional, não seu funcionamento atual com a versão nova.
- Próximo passo: atualizar o adicional para 2.0.5 preservando dados/credencial local, abrir e conferir atualização da versão/último acesso no principal. Não gerar vínculo duplicado nem remover instalação. Se pedir primeiro acesso, interromper para diagnóstico; recuperação 022 é exclusiva do principal.
- Banner superior aparece sem identificação legível da conta nas imagens; registrar para revisão visual, sem causa confirmada. Nenhum pagamento autorizado/efetuado nesta conferência.

## Abertura após recuperação confirmada — 10/09/2026

- Proprietário confirmou: "Sistema abriu normal" após recuperar o principal na versão 2.0.5. Abertura da aplicação no equipamento real validada pelo usuário.
- Próximo passo: conferir Conta Empresarial e vínculo do segundo computador. Abertura normal não comprova ainda cobrança, webhook ou concorrência; não orientar pagamento do QR antigo.

## Recuperação do principal confirmada pelo proprietário — 10/09/2026

- Proprietário informou "Deu certo" e enviou telas de confirmação do e-mail e "Acesso recuperado" na revisão 2.0.5. Fluxo autenticado de recuperação no equipamento real confirmado; abertura da tela principal/Conta Empresarial após fechar os avisos ainda não foi confirmada nesta etapa.
- Antes da confirmação, diagnóstico somente leitura mostrou o equipamento correspondente cadastrado como principal, status active, billing_status active e proprietário ativo correspondente ao e-mail anteriormente informado. Nenhum vínculo, licença ou permissão foi alterado durante o diagnóstico.
- Esclarecimento posterior do proprietário: na tentativa recusada, havia utilizado o login da outra máquina. O relato é consistente com a exigência de proprietário do principal; não comprova por si só o papel/permissão daquele outro usuário. A recuperação posterior foi realizada pelo usuário no aplicativo, não por intervenção direta no banco.
- Permanecem pendentes homologação do segundo computador, concorrência financeira e confirmação válida do provedor. Não orientar pagamento de PIX antigo.

## Entrega 2.0.5 — login e recuperação do principal — 10/09/2026

- Instalador final `dist/Instalador_SaaS_Assistente_PRO_v2.0.5.exe` compilado com sucesso. SHA-256 `819ad327b5526ce80b7f1b40e85f2bcfb158652306fcab8bb0e925f64ee938a4`, manifesto `dist/release_v2.0.5.json` conferido. Versões anteriores preservadas; Admin 2.0.4 continua compatível.
- Backend já publicado: migração 022/account-api v9. Testes locais (87 v2, Deno e SQL real) aprovados; postflight de permissões e HTTP 401 em produção aprovados. Telas inicial e login inspecionadas com serviços simulados; nenhuma credencial real fornecida/registrada nos testes.
- Próximo passo do proprietário: instalar 2.0.5 no principal, escolher "Já tenho conta — Entrar", usar e-mail/senha existentes e confirmar OTP no aplicativo. Não criar outra conta nem informar senha/OTP no chat. Ainda falta aceite autenticado nesse hardware real; não afirmar recuperação concluída antes disso.
- Não houve rotação de token de cliente real, nova licença, alteração de prazo, pagamento, instalação automática ou publicação OTA nesta etapa. Mantidas pendências anteriores de concorrência financeira e homologação com dois computadores.

## Recuperação publicada — 10/09/2026

- Migração 022 aplicada com conteúdo integral conferido no editor, retorno Success. Hash `e9c63542c9c68bae743718a0eea3a4061e1742cd73fdb0e8051112865defc5d3`. account-api v9 ACTIVE publicada pela CLI com dependências compartilhadas; demais funções preservadas.
- Postflight: RPC existe, anon/authenticated sem EXECUTE e service_role autorizado. Endpoint recover_principal_access sem credenciais respondeu HTTP 401 UNAUTHORIZED. Nenhuma recuperação de cliente real foi executada.
- Tela com botão de login inspecionada em renderização offscreen/serviços simulados. Regressão final 87 testes aprovada. Instalador 2.0.5 em compilação neste registro; Admin 2.0.4 não foi alterado nem recompilado.

## Recuperação do computador principal — implementação 2.0.5 em andamento

- Incluída entrada "Já tenho conta — Entrar" no primeiro acesso, reutilizando login com senha/recuperação de senha e confirmação OTP por e-mail. Novo endpoint account-api exige usuário autenticado e OTP de até 10 minutos.
- Migração 022: RPC restrita a service_role, exige proprietário ativo e hardware já cadastrado como principal ativo; apenas rotaciona hash/token_issued_at, preservando licença, validade, assinatura, cobrança e bloqueios. Auditoria sem token e limite de uma recuperação bem-sucedida por minuto.
- 87 testes v2, Deno check e teste OTP aprovados. PostgreSQL real isolado aprovou titular/hardware, recusa de outra conta, máquina adicional/bloqueada, rotação e preservação integral de licença/assinatura. Primeiro teste detectou campo created_at inexistente; corrigido para occurred_at antes de publicação. Fixtures revertidas e servidor local encerrado.
- Ainda não publicado neste registro; próximo passo gerar 2.0.5 e publicar 022/account-api. Não instruir usuário a excluir conta, mudar e-mail ou reiniciar trial.

## Entrega 2.0.4 CPF/CNPJ — 10/09/2026

- Build final concluído após revisar os textos de pessoa física também na cobrança. Instalador `dist/Instalador_SaaS_Assistente_PRO_v2.0.4.exe`, SHA-256 `f73f28358f5648c2b74867ac3e3c2e7896a124185d23651c725a20ad4cac8f0b`; manifesto `dist/release_v2.0.4.json` conferido. Build intermediário 2.0.4 substituído; instalador 2.0.3 preservado.
- Admin `dist_admin_v204/Gerador Admin - SaaS Assistente PRO.exe`, SHA-256 `37f1c9634b64497c4140ee6d4b7d90c4c055e22de9c7efcb5b955e969f6dd282`.
- Migração 021 publicada com hash `3f07243db5275ec13110896f5a9acf46ac22dba0fcfb4bd6412e0930343736ef`; account-api v8/billing-api v13 ACTIVE, sem credenciais retornam HTTP 401 UNAUTHORIZED. Proteções 020 preservadas.
- 83 testes v2 e 16 de Admin/versionamento aprovados; teste Deno de documentos e check das duas funções aprovados. SQL real ampliado passou para perfil de cobrança CPF, checksum inválido e proibição de repetir trial pelo mesmo usuário. Dados fictícios revertidos; PostgreSQL local encerrado.
- Prévia offscreen da tela gerada com serviços simulados e fonte Segoe UI explícita, inspecionada sem corte dos campos CPF/nome. Isso não equivale a executar instalador/login reais; homologação de cadastro pelo proprietário é o próximo passo. CPF real deve ser informado somente no aplicativo, nunca no chat.
- Nenhum pagamento, cadastro fictício de produção, atualização OTA ou instalação automática foi realizado. Homologação de pagamento/concorrência/duas máquinas e licenças comerciais de empacotamento continuam pendentes antes de distribuição geral.

## CPF/CNPJ publicado no servidor — 10/09/2026

- Migração 021 aplicada pelo SQL Editor, com conteúdo integral comparado ao arquivo local antes de executar. Retorno `Success. No rows returned`. Prévia: uma conta, nenhuma tentativa aprovada; nenhuma exclusão de dados.
- account-api v8 e billing-api v13 publicadas pela CLI com módulos compartilhados. Ambas ACTIVE; account-api agora alinhada ao config.toml (verify_jwt=false no gateway, autenticação requireUser mantida no código). admin-api v9 e desktop-api v8 preservadas.
- Postflight: validadores CPF/CNPJ verdadeiros, checksum inválido rejeitado, anon sem EXECUTE de onboarding; zero documentos legados inválidos nas unidades e perfis. Testes locais: 83 testes v2, 38 direcionados (sobrepostos), 1 teste Deno e check de duas funções aprovados; testes reais no clone aprovados. Um teste estático antigo exigia somente validCnpj e foi atualizado para o requisito CPF/CNPJ.
- Revisão 2.0.4 em compilação para Desktop e Gerador Admin. Não confundir com o 2.0.3 anterior: ainda não usar o instalador antigo para CPF. Homologação autenticada pelo proprietário e em duas máquinas continua pendente.

## Suporte CPF/CNPJ — 10/09/2026 — implementação local

- Cadastro, validações Python/TypeScript/SQL, cobrança e exibição/busca Admin adaptados para CPF e CNPJ. A interface identifica automaticamente o tipo pelo documento; nomes técnicos legados preservados.
- Migração 021 aplicada exclusivamente no clone `backup_verify2`: testes reais aprovados de CPF, CNPJ, checksum inválido, duplicidade entre usuários e bloqueio de RPC anônimo. Usuários e contas fictícios desfeitos com ROLLBACK; servidor local encerrado.
- 38 testes direcionados aprovados. Regressão v2 e checagem Deno em andamento. Nenhuma alteração CPF/CNPJ publicada em produção e nenhum executável recompilado neste registro; instalador 2.0.3 ainda exige CNPJ.
- Antes da disponibilização: concluir testes, aplicar 021 em produção, publicar account-api/billing-api e gerar nova revisão Desktop/Admin. Não orientar cadastro CPF pelo executável antigo.

## Validação no clone PostgreSQL e preparação de duas máquinas — 10/09/2026

- Migração 020 aplicada com ON_ERROR_STOP na base local `backup_verify2`, restaurada do backup pré-020, em PostgreSQL 17.11. Roles locais anon/authenticated/service_role preparadas como NOLOGIN; nenhuma alteração remota nesta etapa.
- Verificações aprovadas: digest SHA-256 real de pgcrypto/extensions com vetor conhecido `abc`, presença da tabela de conciliação e negação de EXECUTE para anon na rotina de confirmação de pagamento. Isso não comprova ainda concorrência nem webhook válido.
- PostgreSQL iniciado somente em 127.0.0.1:55432 e encerrado no finally. Primeira preparação de roles teve erro de sintaxe antes da migração; corrigida e execução seguinte concluída com COMMIT.
- Proprietário confirmou segundo computador disponível. Próxima interação: abrir a versão 2.0.3 no principal e validar login/Conta Empresarial antes de gerar código e vincular o secundário. Não pagar PIX legado nem efetuar cobrança real para esse primeiro teste.
- Mantidas pendências: comportamento autenticado de account-api (gateway difere da configuração local), testes concorrentes com duas conexões, webhook válido e homologação visual. Instalador continua restrito a teste controlado, sem distribuição geral/OTA.

## Publicação coordenada concluída — 10/09/2026

- Login oficial da CLI concluído pelo proprietário. Projeto confirmado pelo nome `saas-assistente-desktop-v2-prod` e referência `hnwvtoiiuqagzmuqygkw`.
- CLI publicou `admin-api` versão 9 e `desktop-api` versão 8, incluindo `http.ts` e `security.ts`. `billing-api` republicada como versão 12 com `http.ts`, `security.ts` e `v2.ts` locais. As três constam ACTIVE e usam autenticação/verificação de assinatura no código, conforme config.toml.
- Verificações HTTP em produção aprovadas: admin-api, desktop-api e billing-api responderam 401/UNAUTHORIZED sem credenciais; webhook sem assinatura respondeu 401/INVALID_SIGNATURE. Esses testes comprovam inicialização e rejeição de chamadas não autenticadas; não comprovam pagamento real ou fluxo autenticado completo.
- Migração 020 e três funções da revisão implantadas. O bloqueio anterior de publicação foi resolvido. A hipótese de dependências ausentes no editor web não teve mensagem explícita do provedor; a CLI incluiu as dependências e confirmou sucesso.
- Pendências de homologação: login nos executáveis 2.0.3, conta controlada/duas máquinas, webhook válido do Mercado Pago, conciliação da tentativa legada e concorrência real. Nenhum pagamento, cancelamento ou reembolso foi efetuado nesta etapa. Não anunciar homologação completa antes desses testes.
- Observação de configuração: account-api versão 7 permanece com verify_jwt=true no gateway, diferente do config.toml local. Não foi alterada nesta publicação; validar o fluxo autenticado de Conta Empresarial antes da distribuição.

## Implantacao parcial da seguranca 020 — 10/09/2026

- Preflight de producao: 1 empresa, 1 assinatura, 1 fatura aberta, 1 tentativa pendente, nenhuma tentativa aprovada; migrations 018/019 presentes e pgcrypto no schema `extensions`.
- Migração local exata `020_v2_payment_snapshot_safety.sql` (SHA-256 `96462C726CD149BFE7D354CCD29729902F5A02C73B4E22BD8F5F8D5A30DC0E79`) aplicada pelo SQL Editor ao projeto `hnwvtoiiuqagzmuqygkw`; painel retornou `Success. No rows returned`.
- Postflight aprovado: tabela de conciliacao e duas colunas novas presentes; wrappers e helpers internos presentes; `anon` sem execução do webhook RPC e `service_role` sem execução do helper 019. Zero casos de conciliacao abertos.
- Existe 1 tentativa pendente legada sem snapshot. Ela permanece registrada, mas o wrapper 020 impede renovacao automatica por pagamento legado e encaminha recebimento para conciliacao. Nenhum cancelamento ou reembolso foi efetuado.
- `billing-api` publicada pelo painel e confirmada com `Successfully updated edge function`; inclui snapshot, ocultacao de QR nao pagavel e notification_url do PIX.
- `admin-api` e `desktop-api` foram carregadas e comparadas byte a byte com os arquivos locais (desconsiderando CRLF), mas o editor web nao publicou. Causa operacional: seus bundles atuais exibem apenas `index.ts`, enquanto o codigo local importa `../_shared/http.ts` e `../_shared/security.ts`; a billing-api ja possuia esses arquivos no bundle.
- Proximo passo: autenticar a CLI local pelo fluxo oficial do Supabase e publicar `admin-api` e `desktop-api` a partir da pasta v2, preservando os modulos compartilhados. Até isso ocorrer, o Desktop/Admin 2.0.3 nao deve ser distribuido e o backend deve ser considerado em implantacao parcial.

## Backup pre-020 validado — 10/09/2026

- Backup logico finalizado em `private_db_backups/pre020_20260910_064805_823dfc54/database.dump`: 433.846 bytes, 749 linhas de catalogo, SHA-256 `37A93AEA415AC16CFDB1B64B80EE5D9696489DD5E3A90989E2632511CFAA8071`.
- O arquivo foi restaurado em PostgreSQL 17.11 local e isolado com schemas `auth` e `public`: 23 e 21 tabelas, respectivamente; 1 empresa, 1 assinatura, 2 usuarios Auth e zero FKs publicas nao validadas. O servidor local de teste foi encerrado.
- O dump cobre banco logico, mas nao arquivos fisicos do Storage, secrets, configuracoes do painel ou codigo Edge. Esses itens permanecem protegidos pelo codigo local/versionamento e inventario de configuracao; nenhuma credencial foi gravada.
- Pre-condicao de backup para a migracao 020 atendida. Proximo passo autorizado: inventario agregado de cobrancas pendentes, aplicacao da migracao e publicacao coordenada das funcoes.

## Correcao da validacao local do arquivo — 10/09/2026

- A nova tentativa superou TLS e autenticacao e concluiu o pg_dump, mas o script passou `--file=(Join-Path ...)` incorretamente ao pg_restore; a falha foi posterior ao backup e nao alterou o servidor.
- Argumentos nativos de pg_dump/pg_restore agora sao arrays explicitos e o arquivo de catalogo tem caminho calculado previamente. A copia `pre020_20260910_064805_823dfc54` sera validada e finalizada, se integra, sem pedir novamente a senha.

## Correcao TLS do backup manual — 10/09/2026

- Duas tentativas do proprietario falharam antes da leitura com `SSL: certificate verify failed`; os arquivos `database.partial.dump` resultantes nao sao backups validos.
- Causa confirmada na documentacao oficial: `sslmode=verify-full` requer o CA do Supabase, e `sslrootcert=system` nao validou a cadeia neste cliente Windows.
- Certificado publico `prod-ca-2021.crt` obtido do link exibido em Database Settings do projeto, inspecionado como `Supabase Root 2021 CA`, valido ate 26/04/2031. SHA-256 do arquivo: `700723581420DD1AC98FD7E9AC529F0EF210EADCAF87FC868A3AD7D114C2F3B7`.
- Script corrigido para exigir esse certificado e seu hash, continuar em `verify-full` e desabilitar apenas negociacao GSS (nao TLS). Nova execucao interativa ainda necessaria; migracao e funcoes continuam nao publicadas.

## Preparacao do backup manual — 10/09/2026

- Proprietario confirmou conhecer a senha do banco; nao foi solicitada nem recebida no chat.
- Parametros do session pooler conferidos no painel Connect do projeto v2. Preparado `supabase/backup_v2_interactive.ps1`, com prompt nativo oculto de senha, TLS verify-full e destino local `private_db_backups/` excluido do Git e com ACL restrita ao usuario/SYSTEM.
- O script executa somente pg_dump e verificacao de catalogo/hash, sem migracao ou restauracao remota. Qualquer erro deixa arquivo marcado como parcial e interrompe o fluxo.
- Sintaxe PowerShell validada; modo `-CheckTools` aprovado com pg_dump/pg_restore 17.11 oficiais da EDB. Exclusao de `private_db_backups/` confirmada por git check-ignore.
- Backup ainda depende da execucao interativa pelo proprietario e de teste posterior de restauracao isolada. Dump logico nao inclui arquivos fisicos do Storage, secrets ou configuracoes Edge. Implantacao permanece pendente.

## Início da implantação autorizada — 09/09/2026

- Proprietário autorizou aplicar a revisão 2.0.3 em produção.
- Painel autenticado confirmou projeto `saas-assistente-desktop-v2-prod`, referência `hnwvtoiiuqagzmuqygkw`, status Healthy.
- Verificação prévia encontrou impedimento: painel Database Backups informa que o plano Free não inclui backups; não há backup disponível no painel. CLI também está sem autenticação (`Access token not provided`).
- Nenhuma migração ou função foi publicada nesta etapa. É necessário obter backup lógico recuperável por conexão PostgreSQL autorizada ou comprovar backup externo recente antes de alterar o banco. Não foi contratado upgrade nem criada credencial.

## Revisão de segurança da cobrança e do Admin — 09/09/2026 — concluída localmente; implantação pendente

Registro final desta revisão (substitui os estados intermediários abaixo):

- Desktop 2.0.3 e Gerador Admin compilados com sucesso. Instalador em `dist/Instalador_SaaS_Assistente_PRO_v2.0.3.exe`; Admin em `dist_admin_v203/Gerador Admin - SaaS Assistente PRO.exe`. Não foram instalados, publicados nem homologados com duas máquinas reais.
- SHA-256 instalador: `baaf3701b1c8328680770ad8ac7358d03f616042e6bb543a533b32626dc89246` (confere com `dist/release_v2.0.3.json`). Admin: `5c3f5bc49cc03988876021b38ee3262e370b151f415476cdc85240b31e36fb89`.
- 179 testes Python aprovados; 15 grupos de cenários PostgreSQL/PGlite aprovados, incluindo confirmação de reembolso que bloqueia o período devolvido; as três funções Edge alteradas passaram no Deno check final.
- PIX novo informa explicitamente a URL de webhook da billing-api. Conferir eventos Payments e Orders e assinatura no provedor durante implantação; nenhum ajuste remoto foi realizado.
- Roteiro de implantação e critérios de aceite em `supabase/DEPLOY_SECURITY_020.md`. A proteção no servidor depende da migração 020 e publicação das funções. Não distribuir como versão homologada antes dessas etapas.
- O build reportou PyArmor trial/non-profits e Inno Setup non-commercial. Verificar licenças adequadas ao uso comercial antes de distribuir; compilação bem-sucedida não comprova conformidade dessas ferramentas.

- Base local identificada como 2.0.2; instalador existente confere com o manifesto. As mudanças desta revisão ainda não estão nesse instalador nem foram publicadas.
- Migração 020 preparada com identidade dos computadores por cobrança, snapshot imutável por tentativa, bloqueio transacional por empresa, proteção contra notificações atrasadas e fila de conciliação sem renovação automática de pagamentos divergentes.
- Cobranças antigas sem snapshot não recebem uma composição presumida: pagamentos nessas condições exigem conferência. Atualização de código local não modifica QR codes já emitidos no provedor.
- Configuração local da billing-api explicitada. Testes de versão deixaram de exigir o beta antigo. Tela de cobrança em revisão para ocultar resultados inválidos e consultar status.
- Validação em banco isolado e revisão das ações do Gerador Admin em andamento. Não considerar estas mudanças homologadas ou implantadas até o registro final desta seção.
- Primeira validação local: 175 testes Python aprovados e 11 cenários executados em PostgreSQL/PGlite descartável. Incluem QR antigo com nova máquina, substituição mantendo quantidade, evento repetido/atrasado, reembolso, preservação de bloqueio, snapshot imutável, restrição de permissões e ativação posterior ao pagamento. A fixture simula digest apenas para verificar resolução do schema; não substitui o teste do pgcrypto e de concorrência no Supabase.
- Admin revisado: ajuste individual de envios deixa de enviar renovação automática; preço/vigência empresariais são alterados na conta; erros de salvamento liberam o botão para tentar novamente; valores zero preservados; painel de pagamentos em conferência preparado.
- PIX legado por instalação bloqueado na desktop-api v2. A cobrança empresarial permanece o caminho autorizado. A versão 1.9.6 tem backend próprio e não foi alterada.
- Validação ampliada: 179 testes Python aprovados e 15 cenários PostgreSQL/PGlite aprovados; Deno validou billing-api/admin-api/desktop-api. Proteções adicionais cobrem alteração de preço, registro tardio de cobrança e revalidação do emissor de código.
- Build de revisão 2.0.3 em preparação. Migração, funções e distribuição continuam pendentes; nenhum PIX de produção foi cancelado nem pagamento real efetuado nesta revisão.

## Limites por máquina e conversa correta — 04/09/2026

- Gerador Admin existente iniciado para o proprietário renovar a assinatura; nenhuma licença foi alterada pelo agente.
- Identificado defeito na lista: linhas sem `ItemIsSelectable`, embora a conversa usasse `currentItem()`. Corrigido localmente. Relato da 1.9.4 não foi reproduzido nessa versão histórica.
- Navegação de conversa agora usa `setUrl`, interrompe timer anterior e invalida callbacks antigos de envio. O envio exige carregamento da URL esperada e texto esperado no compositor; seletores restritos ao rodapé do chat. Ainda exige teste real de troca A/B, mesma conversa e SSI antes da distribuição.
- Migração local 016 adiciona `daily_message_limit` opcional (padrão 6 trial/30 demais) e `batch_limit` padrão 1, ambos limitados a 1–1000. Admin valida e edita os valores por instalação. Desktop lê as cotas do servidor, valida o tamanho da seleção antes de iniciar e mantém envio sequencial.
- 15 testes direcionados aprovados (licenciamento, contratos Edge, navegação e callbacks). Sem teste real de mensagens e sem novo build nesta etapa.
- Pendente: aplicar migração 016, publicar admin-api/desktop-api e gerar novos executáveis coordenadamente no projeto v2. Não publicar antes de revisar contagem pós-envio (legada), callbacks SSI pendentes e validação real do destinatário. A conferência da URL/texto não prova isoladamente a identidade do chat se o WhatsApp mantiver estado inesperado.
- Template Magic link or OTP salvo e conferido após recarregar o Supabase; teste integrado de salvamento de cobrança com OTP ainda pendente.
- Teste integrado de confirmação empresarial por e-mail concluído pelo proprietário em 04/09/2026: o OTP foi aceito, a sessão autorizou a operação protegida e os dados de cobrança permaneceram salvos após o fluxo. Etapa aprovada.
- Migração 016 aplicada no projeto v2 com `Success. No rows returned`. `admin-api` e `desktop-api` foram republicadas; o painel mostrou atualização recente e ambas recusaram requisição sem autenticação com HTTP 401.
- Suíte completa após limites e correção de conversa: **126 testes aprovados**. Builds isolados gerados: Gerador Admin com 32.803.009 bytes, SHA-256 `B86020E4C0F5594FDCFE456B778C7215202A7C31ACA33CC6494B3BF45E9DAC6A`; Desktop com 193.217.350 bytes, SHA-256 `FBD5A1C396D15B6059FD1DCC034EB685E4E409467DEC1E2B072E7E70F08E75DC`.
- Pendente somente validação integrada: fechar o Gerador/Desk antigo antes de abrir os novos builds, definir cotas numa licença e testar troca A→B→A e lote com contatos controlados. Não usar clientes reais nessa validação.
- Revisão visual da Conta Empresarial: o banner azul estava absorvendo espaço vertical livre e esticando o selo de perfil. Banner fixado em 112 px, conteúdo centralizado e selo com política vertical fixa. 13 testes direcionados aprovados. Novo Desktop de teste: 193.216.309 bytes, SHA-256 `8E6717C1C8C3ECD1BAA4347ED8E372D6BEF389DB2F6D2D0D29F7D4368602EA56`.
- Revisão da contagem de envios concluída em 05/09/2026: a migração 017 cria reservas atômicas por mensagem, desconta a cota antes do clique no WhatsApp e confirma ou devolve o consumo conforme o callback. Isso impede estouro de limite entre instâncias simultâneas.
- Migração 017 aplicada no projeto Supabase v2 com sucesso e `desktop-api` republicada com as ações `reserve_message`, `confirm_message` e `release_message`. O painel confirmou `Successfully updated edge function`; a chamada sem autenticação retornou HTTP 401, comprovando inicialização e proteção do endpoint.
- Suíte completa após as reservas: **134 testes aprovados**. Ainda falta o teste visual A→B→A e o lote com números controlados antes de liberar esta beta.
- Beta com reservas gerado em `dist_desktop_v2_reservation_test/SaaS Assistente PRO 2.0 - Teste.exe`, com **193.219.627 bytes** e SHA-256 `715A0A8E8D01FD378FB7D433F9A83B154EB20A482E1F0CB64303C0C0C815E5F1`.
- Na primeira abertura imediatamente após o deploy, o Desktop exibiu vínculo não autorizado. A consulta diagnóstica subsequente confirmou o mesmo hardware, sessão local presente e licença `active`; na segunda abertura o aplicativo permaneceu em execução normalmente. Tratar como evento transitório pós-publicação, sem recriar ou apagar o vínculo.
- Validação real A→B→A aprovada pelo proprietário em 05/09/2026: o WhatsApp passou a trocar corretamente entre Janete e Francisco. Foi detectada uma inconsistência apenas no indicador superior, que ainda exibia o nome anterior.
- A lista agora usa azul forte, borda e texto branco para a linha ativa, explica a diferença entre destaque e caixas marcadas e renomeia a ação para `Conversar com o Destacado`. O indicador superior é atualizado em todos os caminhos TSI/SSI e callbacks atrasados de fichas SSI antigas são ignorados por geração.
- Suíte completa: **137 testes aprovados**. Prévia conjunta em `dist_desktop_v2_selection_status_test/SaaS Assistente PRO 2.0 - Teste.exe`, com **193.220.935 bytes** e SHA-256 `99FD16352B987E72FAC285DBAA3C15C2811ECAC97CCB3F1A10DB127A7FD58324`.
- Segurança do lote revisada: a legenda e o botão mostram a quantidade efetivamente marcada; lotes com mais de um destinatário exigem confirmação com quantidade e nomes antes de consultar o WhatsApp. Cancelar limpa a fila temporária, não abre o motor e não reserva/consome mensagens.
- Suíte completa após a confirmação do lote: **139 testes aprovados**. Prévia em `dist_desktop_v2_batch_confirmation_test/SaaS Assistente PRO 2.0 - Teste.exe`, com **193.221.328 bytes** e SHA-256 `F1CA6D4CFD2CB810002A2114131503DF98CE218CFADB7B21030B79363F6BE4D9`.

## Sistema principal

O projeto Desktop possui implementação funcional em PyQt6, com módulos para interface, extração myHonda, processamento local, dashboards, WhatsApp Web, licenciamento, atualização e geração de instaladores.

## Recursos existentes

- Navegadores incorporados para myHonda e WhatsApp Web.
- Extratores JavaScript SSI e TSI.
- Persistência local em SQLite/JSON.
- Conversão de IDs Salesforce e geração de links Medallia.
- Telas de extração, dashboards, configuração, licença, tutorial e WhatsApp.
- Histórico e processamento de dados TSI e SSI.
- Scripts de build, proteção, instalador e atualização.

## Melhorias recentes — Dashboards

- Aba e relatório executivo consolidados sob o nome **Relatório Gerencial Geral**.
- Filtro de Consultor/Vendedor aplicado aos indicadores TSI e SSI.
- Identificação robusta de vendedor por CPF ou nome, com cruzamento no cadastro local.
- Ranking SSI de vendedores adaptado aos filtros de loja, mês, modalidade e vendedor.
- Histórico anual SSI alinhado ao vendedor selecionado.
- Participação de respostas vinculadas ao WhatsApp calculada dentro do recorte ativo, sem percentuais fixos.
- Histórico Anual monitorado por mudança e estabilização real do DOM, sem espera fixa de 35 segundos.
- Auditores TSI/SSI extraem diretamente no fluxo normal; a espera por mudança de tabela é exclusiva do botão Histórico Anual.
- Nomes e telefones TSI cruzados por O.S. normalizada e persistidos no histórico quando disponíveis.

## Estado de manutenção

O repositório contém múltiplas versões, backups, scripts de correção, arquivos temporários e artefatos de build. Antes de mudanças estruturais, é necessário identificar o código-fonte canônico em `src/` e evitar alterações nas cópias de backup.

## Próximo foco

Estabilizar e validar o Desktop de ponta a ponta: extração real, auditores, filas, disparos, dashboards, persistência, atualização e instalação.

## Segurança operacional do WhatsApp

- Removida a seleção de todos os clientes.
- A fila aceita somente uma pesquisa marcada por vez e valida novamente essa restrição antes do envio.
- O comando passou a se chamar **Enviar Pesquisa Selecionada**.
- O botão **Enviar Link de Pesquisa** do Motor WhatsApp permanece desabilitado; o envio deve ser iniciado pela lista.
- Versão **1.9.0** gerada e validada em 13/08/2026, publicada como pré-lançamento no GitHub.
- Supabase configurado para oferecer a 1.9.0 como atualização opcional (`minimum_version=0.0.0` e `update_required=false`).
- Instalador 1.9.0: SHA-256 `1559f8a190b434848acdd4773a4f28446f83ef7fa9e93ea28345016612e1ecb3`.
- Versão **1.9.1** em preparação em 13/08/2026: corrigido o contraste da janela de download da atualização, neutralizando o fundo branco herdado do tema global nos textos de título e progresso e adicionando um quadro informativo escuro legível. A confirmação final deixou de usar o `QMessageBox` afetado pelo tema global e passou a ser uma janela própria, escura e compacta (560 × 300), eliminando a largura excessiva e a área branca vazia.
- Instalador 1.9.1 gerado em 13/08/2026: SHA-256 `05ed6cb8c2df486b613b6e3a25d13f6288df18158c37e271b991224a76155334`.
- Versão **1.9.1** publicada como pré-lançamento no GitHub em 13/08/2026, com o instalador validado publicamente (HTTP 200 e 243.420.583 bytes).
- Supabase atualizado para oferecer a 1.9.1 como atualização opcional: `current_version=1.9.1`, `minimum_version=0.0.0`, `update_required=false`, URL do instalador e SHA-256 conferidos pela linha retornada no SQL Editor.

## Correção do Histórico Anual SSI — 13/08/2026

- Corrigido o monitor que mantinha o SSI indefinidamente como **Relatório em processamento**, mesmo após o myHonda informar **Concluído**.
- A validação do intervalo `cury` permanece exclusiva do TSI. O SSI pode concluir com intervalo personalizado porque seu histórico utiliza o filtro próprio de data do relatório.
- O monitor SSI agora lê o estado oficial `Status da geração do relatório`, acompanha um identificador da execução e exige duas leituras estáveis antes da importação.
- Ao concluir o Histórico Anual, o SSI passa a informar a quantidade total de respostas e de meses importados.
- Backup anterior à correção: `backups/pre_fix_ssi_historico_20260813_135017`.
- Testes direcionados do monitor TSI/SSI: **5 aprovados**; sintaxe dos arquivos alterados validada com Python 3.14.
- Versão **1.9.2** e instalador oficial gerados após a correção. Instalador com 243.421.118 bytes e SHA-256 `7c73d42551d4554007c7c2d714a79c92e00d8f06803cdea31e4d682e6f3d58ec`; manifesto e hash recalculado conferem.
- Release **v1.9.2** publicada como pré-lançamento no GitHub, com o instalador anexado e o digest exibido pelo GitHub igual ao hash local.
- Supabase atualizado para oferecer a **1.9.2** como atualização opcional: `current_version=1.9.2`, `minimum_version=0.0.0`, `update_required=false`, URL e SHA-256 confirmados pela linha retornada no SQL Editor.

## Correção do primeiro acesso — v1.9.3 (20/08/2026)

> **Substituída pela v1.9.4.** A exigência de chave de licença durante o primeiro cadastro não corresponde ao fluxo comercial definido e foi removida na correção posterior.

- Corrigida a decisão que tratava todo computador sem sessão local como instalação legada.
- O backend agora responde `legacy` somente quando o hardware foi importado do Firebase e possui Código de Migração pendente; hardware desconhecido responde `new`; cadastro existente sem token local responde `recovery_required`.
- Computadores novos recebem a tela **Ativar novo computador**, com dados da concessionária e chave de licença. Não existe cadastro automático nem trial aberto.
- A ativação nova aceita somente chave válida de dias ou data de vencimento, dentro das 24 horas, destinada à concessionária informada. Chaves de mensagens não ativam computadores.
- Edge Function `desktop-api` publicada no Supabase e validada com hardware fictício: resposta `{"ok":true,"mode":"new"}` sem gravação.
- Testes: 9 testes automatizados aprovados no Python 3.14.5.
- Backup anterior: `backups/pre_fix_new_installation_20260820_110000/original_files.zip`.
- Build local **v1.9.3** concluído. Instalador: `dist/Instalador_SaaS_Assistente_PRO_v1.9.3.exe`, 243.425.005 bytes, SHA-256 `46f42f790e7186fc29a043aefa3e1b4f17a00960a997a8d34529e0083fc9408b`.
- Release **v1.9.3** publicada como pré-lançamento no GitHub com o instalador anexado. O digest exibido pelo GitHub coincide com o SHA-256 local.
- Supabase atualizado para oferecer **1.9.3** como atualização opcional: `current_version=1.9.3`, `minimum_version=0.0.0`, `update_required=false`, URL e SHA-256 confirmados pelo retorno do SQL Editor.
- URL do instalador validada por requisição sem download: HTTP 200, `application/octet-stream`, 243.425.005 bytes.

## Cadastro inicial com trial automático — v1.9.4 (20/08/2026)

- Restaurado o fluxo comercial correto para computadores novos: o usuário informa concessionária, responsável e WhatsApp, conclui o cadastro e recebe automaticamente **2 dias de teste**.
- A chave de licença não é solicitada no primeiro acesso. Depois do cadastro, a instalação aparece no Gerador Admin com o nome informado; o administrador pode então gerar e enviar a licença definitiva.
- O Código de Migração permanece exclusivo para instalações antigas importadas do Firebase que ainda possuam uma migração pendente.
- O backend cria a empresa, a instalação ativa, a sessão segura e a licença `trial`, com vencimento às 22h do segundo dia.
- Edge Function `desktop-api` publicada no Supabase e validada com hardware fictício: resposta `{"ok":true,"mode":"new"}` sem gravação.
- Backup anterior à correção: `backups/pre_fix_trial_registration_v193_20260820/original_files.zip`.
- Testes automatizados direcionados: **7 aprovados** no Python 3.14.5.
- Build local **v1.9.4** concluído. Instalador: `dist/Instalador_SaaS_Assistente_PRO_v1.9.4.exe`, 243.426.780 bytes, SHA-256 `2169060a7493ae2b89941f2b658c1346196651ff5ee723971b17e1c3f879dde0`.
- Release **v1.9.4** publicada no GitHub com o instalador anexado; URL validada com HTTP 200, `application/octet-stream` e 243.426.780 bytes.
- Supabase atualizado para oferecer **1.9.4** como atualização opcional: `current_version=1.9.4`, `minimum_version=0.0.0`, `update_required=false`, URL e SHA-256 confirmados pela linha retornada no SQL Editor.

## Correção do Gerador Admin — links dos relatórios — 20/08/2026

- A ação **Mais ações → Configurar links dos relatórios** deixou de abrir a janela extensa de edição completa da licença.
- Criada janela compacta e redimensionável, exclusiva para os quatro links: auditor TSI, auditor SSI, fila TSI e fila SSI.
- O botão **Salvar links** permanece fixo e visível no rodapé, inclusive em telas menores.
- Links são validados como HTTPS e persistidos no Supabase pelo comando `update_license`, sem modificar os demais campos da licença.
- Ao fechar com alterações pendentes, o gerador pergunta se deve salvar, descartar ou cancelar o fechamento.
- Backup: `backups/pre_fix_admin_report_links_20260820_091704`.
- Executável recompilado em `dist/Gerador Admin - SaaS Assistente PRO.exe`; SHA-256 `BE17F6003A72B1FA7C2E36BB6E88217AA8B49DB42EEDB57B22FD95F5CB5F7384`.

## Correção do Gerador Admin — IDs dos relatórios myHonda — 20/08/2026

- Confirmado que o Desktop espera somente o ID Salesforce `00O...` e monta internamente `https://myhonda.my.site.com/concessionaria/{ID}`.
- Removida do Gerador Admin a exigência incorreta de que os quatro campos começassem com `https://`.
- O Gerador agora aceita um ID de 15 ou 18 caracteres, um link completo do myHonda ou um link em formato Markdown, mas persiste sempre somente o ID normalizado.
- A normalização foi aplicada tanto em **Configurar links dos relatórios** quanto na edição completa da licença.
- Valores completos já gravados são apresentados como ID ao reabrir a configuração e são corrigidos no Supabase ao clicar em **Salvar links**.
- Backup: `backups/pre_fix_admin_report_ids_20260820_164500/supabase_admin_app.py`.
- Testes direcionados: **9 aprovados**; sintaxe validada no Python 3.14.5.
- Como havia duas instâncias instaladas do Gerador em execução, a compilação foi produzida separadamente em `dist_admin_report_id_fix/Gerador Admin - SaaS Assistente PRO.exe`, SHA-256 `302A441EE1A115E062012F190A53703F021495397E64C0FD2EDFAF499A34D86A`.

## Correção do Gerador Admin — mensalidade padrão — 31/08/2026

- Diagnóstico: a tela Distribuição & Preços não possuía rolagem e o botão geral de salvar podia ficar fora da janela. Além disso, alterar o preço dependia da validação de versão, URL e SHA do instalador.
- Adicionado **Salvar mensalidade** junto ao campo de preço, usando o `update_system_config` existente com apenas `default_monthly_price`. Mensalidades individuais não são alteradas.
- Confirmação de sucesso exige retorno do Supabase com o preço solicitado. Falhas preservam o texto digitado; cliques repetidos durante o salvamento são bloqueados.
- Valores aceitos incluem `300`, `300,00`, `300.00` e `R$ 1.300,50`; valores inválidos, negativos ou fora da capacidade do banco são rejeitados.
- Atualizar dados não sobrescreve uma mensalidade com edição pendente. O valor zero também é exibido corretamente.
- Conteúdo com rolagem e botão geral fixo no rodapé. Conferência visual em prévia offline, tema escuro, janela 1280x800; prévia usa dados fictícios e callbacks locais, não valida persistência remota.
- Testes: **19 aprovados** (`test_admin_pricing`, `test_admin_report_ids`, `test_admin_supabase`).
- Backup: `backups/pre_fix_admin_pricing_20260831/supabase_admin_app.py`.
- Executável separado: `dist_admin_pricing_fix/Gerador Admin - SaaS Assistente PRO.exe`, 32.947.285 bytes, SHA-256 `EFAD20CFC6655206BFF3CCD588AD1DE3A69C674743405D0AC7867383490F9FDB`.
- Não houve alteração de preços reais, publicação de Edge Functions, alteração do Desktop ou distribuição de atualização aos clientes. O administrador deve abrir este executável, informar 300 e clicar em Salvar mensalidade para gravar no Supabase.
- Ideia comercial de licença principal a R$300 e adicionais a R$50 registrada para discussão posterior; sublicenças NÃO implementadas.

## Correção do SaaS Desktop — valor exibido no PIX — 31/08/2026

- O `create_pix` do servidor já consulta `licenses.monthly_price ?? system_config.default_monthly_price ?? 250` a cada nova cobrança e retorna `amount`. A tela ignorava esse retorno, mostrando o preço antigo recebido no status da licença.
- Corrigido `src/ui/screens/license_screen.py`: o botão informa **Consultar valor e gerar PIX** (sem anunciar preço possivelmente desatualizado); durante a geração aparece **Consultando valor atualizado…**. Após a resposta, o valor é obtido exclusivamente de `amount`, com duas casas e formatação brasileira.
- Mantida a precedência da mensalidade individual definida no servidor. Nenhuma alteração em regras comerciais, banco ou Edge Functions.
- Valor ausente, não finito, não positivo ou com precisão inválida impede exibir o QR/copia-e-cola. Nova geração limpa os dados anteriores, interrompe a consulta do PIX anterior e impede geração duplicada enquanto estiver processando.
- Backup: `backups/pre_fix_pix_display_20260831/license_screen.py`.
- Testes: **33 aprovados**, incluindo 7 da tela PIX em Qt offscreen com servidor simulado, 7 do cliente Supabase e 19 regressões do Admin. Nenhuma cobrança real gerada.
- **Entrega somente no código local por enquanto:** não foi compilado/publicado um novo instalador, nem alterada a versão instalada dos clientes. Versão registrada permanece 1.9.4. Para distribuir esta correção será necessário preparar e publicar uma nova versão.

## Preparação da versão 1.9.5 — 31/08/2026

- Usuário solicitou gerar e publicar a correção do PIX no GitHub.
- Versão local atualizada para **1.9.5**, com backup de `src/version.py`, `criador_instalador.iss` e entrada ofuscada anterior em `backups/pre_release_v195_20260831`.
- Build concluído com PyArmor 9.2.5, PyInstaller 6.21.0 e Inno Setup 6.7.3. Bibliotecas essenciais, versão e presença da correção verificadas no pacote; **33 testes aprovados** sem cobranças reais.
- Instalador: `dist/Instalador_SaaS_Assistente_PRO_v1.9.5.exe`, **260.307.205 bytes**.
- SHA-256: `149a4582f69f56ceac08407e25305321accf81203c042cc0c0f9690c61697340`.
- Manifesto: `dist/release_v1.9.5.json`; notas: `release_notes_v1.9.5.md`. Tamanho e hash recalculados conferem.
- Upload concluído no navegador conectado ao GitHub: anexo **Instalador_SaaS_Assistente_PRO_v1.9.5.exe (248.25 MB)** confirmado no formulário, como pré-lançamento, seguindo o padrão anterior. O usuário confirmou que clicou em **Publish release** e a página pública passou a ser `https://github.com/Ranistendecyberg/SaaS-Assistente-PRO/releases/tag/v1.9.5`.
- Supabase NÃO alterado nesta etapa; a oferta automática da versão nova é uma etapa separada.

## Correção do Gerador Admin — edição de licença e revogação de chaves — 31/08/2026

- Corrigida a janela **Editar licença**: o formulário agora possui rolagem e os botões **Cancelar** e **Salvar alterações** permanecem fixos no rodapé, inclusive em telas menores.
- Ao fechar com alterações pendentes, o Gerador pergunta se deve salvar, descartar ou cancelar. Cliques repetidos durante o salvamento são bloqueados.
- Validação da mensalidade passou a usar o mesmo parser monetário seguro da tela de preços; mensagens extras negativas são recusadas.
- O estado do diagnóstico detalhado ativo é preservado ao abrir a janela, evitando que uma simples edição o desative sem intenção.
- Chaves `used`, `expired` e `revoked` recebem explicações específicas no Gerador. Chave utilizada não é revertida: o benefício deve ser corrigido diretamente em **Clientes & Máquinas → Editar licença**.
- A `admin-api` agora consulta a chave antes da revogação, diferencia chave inexistente, utilizada, expirada e já revogada, e revoga somente uma chave ainda `new`.
- Edge Function `admin-api` publicada pelo editor do Supabase; o painel confirmou **Successfully updated edge function**. Nenhuma chave existente foi revogada durante a implantação.
- Backup: `backups/pre_fix_admin_license_keys_20260831`.
- Testes direcionados do Gerador Admin: **13 aprovados**; sintaxe validada no Python 3.14.5.
- Novo executável separado: `dist_admin_license_fix/Gerador Admin - SaaS Assistente PRO.exe`, **32.950.860 bytes**, SHA-256 `F952339CE9CF0F73C2578C88042B6058A0A0193238DA890FDAD94EB85C7B635B`.

## Correção crítica do empacotamento e conclusão da atualização — v1.9.6 — 31/08/2026

- Após atualizar/reinstalar a v1.9.5, o Desktop podia falhar antes da interface com `DLL load failed while importing QtWebEngineWidgets`; portanto, a causa não era somente abertura antecipada.
- Comparação interna entre a v1.9.4 funcional e a v1.9.5 revelou que a 1.9.5 incorporou indevidamente DLLs nativas do runtime auxiliar do ambiente (`Poppler/libheif`), incluindo `ucrtbase.dll`, `api-ms-win-*`, ICU e OpenSSL externos. Essas bibliotecas podiam substituir as versões corretas durante a carga do Qt.
- O build agora remove do `PATH` qualquer pasta `.cache/codex-runtimes` e filtra defensivamente qualquer binário cuja origem seja esse runtime antes da montagem do pacote.
- Criado `update_completion_helper.py`, empacotado como **SaaS Update Assistant.exe** dentro do Desktop. Ele espera o processo anterior encerrar, executa o Inno Setup até o fim e só então exibe que o usuário já pode abrir o SaaS. Ele nunca reinicia o Desktop automaticamente.
- Backup anterior: `backups/pre_update_completion_helper_20260831`.
- Testes do atualizador: **8 aprovados**; sintaxe validada no Python 3.14.5.
- Build estrutural da v1.9.6: Qt6WebEngineCore, Qt6WebEngineWidgets, QtWebEngineProcess, python314.dll e o novo assistente presentes; **zero** ocorrências das DLLs externas proibidas.
- Teste controlado de inicialização em modo offscreen por 15 segundos: processos principal e filho permaneceram ativos, sem janela de exceção; toda a árvore criada no teste foi encerrada em seguida.
- Executável: `dist/SaaS Assistente PRO v1.9.6.exe`, **253.129.052 bytes**.
- Instalador: `dist/Instalador_SaaS_Assistente_PRO_v1.9.6.exe`, **246.978.741 bytes**, SHA-256 `d4fb0c5cb1ce992a2601edb306475b428ae54e8b756d31fe3edbd9ef4717f916`.
- Manifesto: `dist/release_v1.9.6.json`; notas: `release_notes_v1.9.6.md`.
- A v1.9.5 deve deixar de ser distribuída. A v1.9.6 ainda precisa ser publicada no GitHub e depois configurada no Supabase/Gerador Admin; máquinas travadas na 1.9.5 precisarão do instalador manual porque não conseguem abrir o Desktop para usar o OTA.

## Publicação da versão corretiva v1.9.6 — 31/08/2026

- Release pública criada no GitHub como **v1.9.6**, marcada como **Latest**.
- Instalador publicado e conferido na página da release: `Instalador_SaaS_Assistente_PRO_v1.9.6.exe` (236 MB no GitHub), SHA-256 `d4fb0c5cb1ce992a2601edb306475b428ae54e8b756d31fe3edbd9ef4717f916`.
- Link direto: `https://github.com/Ranistendecyberg/SaaS-Assistente-PRO/releases/download/v1.9.6/Instalador_SaaS_Assistente_PRO_v1.9.6.exe`.
- A configuração OTA no Supabase/Gerador Admin permanece pendente e deve usar exatamente esse link e SHA; assim a divulgação automática só ocorrerá quando for explicitamente publicada no painel.

## Início da versão 2.0 — 01/09/2026

- A 1.9.6 foi congelada como base estável; nenhuma alteração da 2.0 foi publicada no Supabase ou oferecida aos clientes.
- Backup físico dos fontes canônicos criado em `backups/pre_v2_foundation_20260901_0001` (206 arquivos, aproximadamente 3,4 MB), sem copiar bancos e credenciais operacionais.
- Arquitetura definida em `memory/arquitetura_v2.md`: empresa, matriz/filiais, usuários, computadores e assinatura consolidada.
- Criado `src/core/v2_business_rules.py` com cálculo puro de vagas faturáveis, preços, permissões e validação de CNPJ.
- Criados testes da fundação em `src/tests/test_v2_business_rules.py`.
- Criada a migração local `supabase/migrations/008_v2_enterprise_accounts.sql`. Ela preserva `licenses` e `payment_sessions` da 1.9.6, cria as estruturas empresariais e faz backfill sem inventar CNPJ ou alterar preços personalizados.
- Testes da fundação e regressões de licenciamento, sessão Supabase, PIX e Gerador Admin: **43 aprovados** no Python 3.14.5.
- O ambiente virtual `venv` da pasta continua inválido porque referencia o usuário antigo `C:\Users\Berg`; os testes foram executados com o Python 3.14.5 atual em `C:\Users\WINDOWS`. O `venv` não deve ser usado no build 2.0 sem ser recriado.
- A migração **não foi executada em produção**. Próxima etapa: validar SQL/backfill em ambiente de teste e implementar autenticação/onboarding 2.0.
- Após aprovação do isolamento, foi criada a pasta independente `C:\SaaS - Codex\SaaS-Desktop-v2` com 206 arquivos canônicos do código, Supabase, Gerador Admin, testes e memória.
- O novo workspace possui repositório Git próprio no branch `main`. Não foram copiados `app_data`, bancos locais, `dist`, builds, caches ou o `venv` antigo.
- A pasta `C:\SaaS - Codex\Saas` passa a ser referência congelada da 1.9.6. Toda nova alteração funcional da 2.0 deve ocorrer somente na pasta `SaaS-Desktop-v2`.

## Supabase v2 e autenticação administrativa — 01/09/2026

- Projeto isolado criado no Supabase: `saas-assistente-desktop-v2-prod`; a versão 1.9.6 e seu projeto permanecem sem alterações.
- Fundação do banco v2 aplicada com preço padrão de R$ 300,00 e modo manutenção desativado.
- Cadastro público, login anônimo e vínculo manual foram desativados. O provedor de e-mail e TOTP permanecem habilitados.
- Primeiro usuário administrativo criado, vinculado como `owner` ativo e protegido por MFA TOTP.
- Verificação direta em `auth.mfa_factors` confirmou o fator `Gerador Admin - Computador Principal` com status `verified`.
- O modo auxiliar `--enroll-only` do Gerador foi corrigido para exibir uma confirmação persistente de sucesso e aguardar o clique em **Concluir**, sem tentar acessar funções administrativas ainda não implantadas.
- Validação local: sintaxe aprovada e **68 testes automatizados aprovados**.
- Commit da correção: `1da8164 fix: confirmar ativacao MFA antes de fechar` no repositório isolado da v2.
- Nenhuma Edge Function nova da v2 foi implantada e nenhum instalador foi distribuído nesta etapa.

## Supabase exclusivo da versão 2.0 — 01/09/2026

- Projeto criado: `saas-assistente-desktop-v2-prod`, referência pública `hnwvtoiiuqagzmuqygkw`, região São Paulo, estado Healthy.
- Removido da cópia 2.0 o vínculo temporário do projeto Supabase da 1.9.6 e alterado `supabase/config.toml` para a referência nova.
- O cliente Supabase do Desktop 2.0 e o Gerador 2.0 apontam para a URL nova e receberam a chave publicável própria do projeto. Nenhuma chave secreta ou `service_role` foi colocada no código.
- A antiga camada `license_manager.py` ainda existe como código legado copiado, mas não deve integrar a entrega 2.0. Sua substituição completa pelo fluxo Supabase v2 permanece obrigatória antes do primeiro instalador beta.
- Ferramentas e dados específicos da antiga importação Firebase foram removidos da pasta 2.0. O original continua preservado na pasta 1.9.6.
- Criado SQL consolidado e limpo em `supabase/bootstrap/FOUNDATION_V2_SQL_EDITOR.sql`; varredura confirmou ausência de IDs de máquinas, chaves ou referência ao projeto antigo.
- Fundação executada com sucesso no novo Supabase. Verificação final retornou `current_version=0.0.0`, `default_monthly_price=300.00` e `maintenance_mode=false`.
- Autenticação endurecida no projeto v2: cadastro público, login anônimo e vinculação manual desativados; e-mail confirmado e TOTP habilitados; SMS MFA desabilitado.
- Primeiro usuário administrativo criado no Supabase Auth e vinculado em `public.admin_users` como `owner`, com estado ativo. E-mail, senha e identificador do usuário não são registrados nesta memória.
- Regressões locais na pasta 2.0: **63 testes aprovados**; o teste exclusivo do importador Firebase antigo foi removido junto com esse componente legado de migração.

## Primeira camada empresarial v2 — 01/09/2026

- Criada localmente a `account-api`, autenticada por usuário e associação ativa à empresa. Alterações exigem papel `owner`/`admin` e sessão MFA `aal2`.
- Implementados resumo empresarial, cadastro validado de matriz/filial, código descartável de vínculo com validade de 24 horas e agendamento/cancelamento da remoção de computador adicional.
- Criado resgate atômico do código de vínculo: bloqueio transacional, validação da associação do usuário, classificação principal/adicional e armazenamento exclusivo do hash do token.
- O Desktop passou a reconhecer o contrato de resgate do código por usuário autenticado. A interface e o fluxo de login ainda não foram conectados.
- **Nada desta camada foi implantado no Supabase.** Antes do deploy ainda será necessário remover os endpoints legados e adaptar o onboarding.
- Regressões locais após esta camada: **66 testes aprovados** e as três Edge Functions aprovadas no `deno check` com as dependências oficiais do Supabase.

## Onboarding empresarial e trial automático v2 — 01/09/2026

- Implementado localmente o primeiro acesso da versão 2.0: criação da conta por e-mail e senha, confirmação por código, validação de CNPJ e liberação automática do computador principal em trial de 2 dias.
- A criação de empresa, matriz, proprietário, instalação principal, assinatura e licença de compatibilidade é atômica no servidor. O token bruto do computador é devolvido uma única vez; o banco mantém somente seu hash.
- Criado controle de tentativas com hash do hardware e limite de cinco tentativas por usuário a cada hora. CNPJ e computador não podem reutilizar o trial.
- A nova tela também contempla computador adicional por login e código descartável de vínculo, além da solicitação de recuperação de senha. A confirmação do primeiro e-mail aceita código de 6 números ou o link padrão do Supabase, sem exigir SMTP personalizado nesta fase.
- O fluxo novo não contém Firebase, código de migração nem solicitação de licença no cadastro inicial. Telas antigas de cadastro/migração e testes Firebase obsoletos foram removidos somente da pasta isolada da v2.
- A janela de primeiro acesso é adaptável a notebooks com menor altura e mantém o formulário em área rolável.
- Validação local: **68 testes automatizados aprovados**, compilação Python aprovada e `deno check` aprovado nas Edge Functions `account-api`, `desktop-api` e `admin-api`.
- **Nada desta etapa foi implantado no Supabase.** Antes do teste integrado será necessário aplicar as migrações 010 e 011, publicar as funções e habilitar deliberadamente novos cadastros. O e-mail padrão por link já é compatível com a tela.

## Implantação controlada do onboarding no Supabase v2 — 01/09/2026

- As migrações `010_v2_device_link_redemption.sql` e `011_v2_company_trial_onboarding.sql` foram aplicadas com sucesso no projeto isolado `saas-assistente-desktop-v2-prod` pelo SQL Editor.
- As Edge Functions `account-api`, `desktop-api` e `admin-api` foram publicadas pelo editor do Supabase a partir dos fontes locais validados. Todas mantêm a verificação JWT da plataforma e as validações próprias de usuário/instalação/MFA.
- O cadastro de novos usuários foi habilitado. Confirmação de e-mail permanece ligada; cadastro anônimo e vínculo manual externo permanecem desligados.
- O Desktop passou a enviar a chave publicável também no cabeçalho `Authorization`, conforme o contrato da plataforma. Nenhuma chave secreta foi adicionada.
- Teste remoto negativo nas três funções retornou `401 UNAUTHORIZED`, confirmando que estão online e recusam requisições sem credenciais válidas.
- Validação local final: **69 testes aprovados**, compilação Python aprovada e as três funções aprovadas no `deno check`.
- Ainda não foi criado usuário/empresa de teste nem consumido trial real. O próximo passo deve usar um e-mail e CNPJ destinados ao teste integrado para validar todo o fluxo do primeiro acesso.

## Correção de conta já existente no primeiro acesso — 01/09/2026

- O primeiro teste integrado utilizou o mesmo e-mail já cadastrado e confirmado como administrador do projeto v2. Nesse cenário, por proteção contra enumeração de usuários, o Supabase não cria outra conta nem envia uma nova confirmação.
- O onboarding foi corrigido para tentar autenticar imediatamente após o cadastro sem sessão. Se o e-mail já estiver confirmado e a senha corresponder, o fluxo continua para a criação da empresa e do trial; se for uma conta realmente nova e ainda não confirmada, a tela de confirmação continua sendo exibida.
- Credencial incorreta agora informa que o e-mail pode já possuir conta e orienta usar a senha existente ou a recuperação disponível em **Computador adicional**.
- Validação local final após a correção: **71 testes automatizados aprovados** e compilação Python aprovada.

## Correção da sessão após confirmação do e-mail — 01/09/2026

- O teste com um e-mail novo confirmou que o envio e a confirmação do Supabase Auth funcionam. O erro visual em `localhost:3000` ocorre somente no redirecionamento padrão posterior à confirmação; a conta já fica confirmada no servidor.
- O Desktop recusava a sessão autenticada por impor comprimentos mínimos arbitrários ao `access_token` e ao `refresh_token`. Tokens do Supabase são opacos e não possuem tamanho contratual fixo.
- A validação local agora exige a presença dos tokens e do identificador do usuário; a autenticidade continua sendo verificada pelo próprio Supabase em cada chamada. Nenhuma senha ou token é exibido ou gravado sem DPAPI.
- Validação após a correção: **72 testes automatizados aprovados** e compilação Python aprovada.

## Primeiro onboarding empresarial integrado concluído — 01/09/2026

- O primeiro cadastro real da versão 2.0 confirmou o envio e a validação de e-mail, o login e a persistência das sessões protegidas pelo DPAPI.
- A primeira tentativa de criação do trial retornou erro 500 porque o `pgcrypto` do Supabase está no schema `extensions`, enquanto a função `create_company_trial_server` enxergava somente `public` e `auth`.
- Criada a migração corretiva `012_v2_onboarding_pgcrypto_search_path.sql` e atualizado o SQL-base da migração 011. O ajuste foi aplicado com sucesso no projeto v2 sem remover ou alterar cadastros existentes.
- Após repetir a operação, o servidor criou a empresa e o computador principal com trial. A verificação somente leitura confirmou sessão do usuário, token de instalação protegido, uma associação empresarial e papel `owner`.
- O redirecionamento visual para `localhost:3000` após clicar no e-mail ainda deve ser substituído por uma experiência de confirmação mais amigável antes do beta público.

## Painel empresarial, MFA e computador adicional — 02/09/2026

- Criada a tela **Conta Empresarial** no Desktop 2.0, com empresa, papel do usuário, assinatura, quantidade de computadores, valor consolidado, vigência, unidades/CNPJs e instalações vinculadas.
- O painel é responsivo e utiliza rolagem vertical própria. Em janela de 900 × 560 o conteúdo completo permanece acessível, sem corte ou rolagem horizontal.
- Proprietários e administradores podem gerar código descartável de computador adicional e programar/cancelar remoção. Operadores possuem somente leitura.
- Integrado o fluxo TOTP oficial do Supabase: listagem de fatores verificados, cadastro por QR code, desafio de seis dígitos e persistência DPAPI da nova sessão AAL2. Senha, código e segredo MFA não são gravados pelo Desktop.
- As mutações do painel repetem a operação somente depois da confirmação MFA bem-sucedida; o servidor continua validando o `aal` diretamente no JWT.
- Identificada e corrigida localmente uma lacuna no resgate do código: o computador adicional agora recebe licença de compatibilidade com a vigência e o preço adicional da assinatura, herdando links/avisos do computador principal. Assinaturas inativas ou vencidas não podem gerar nem resgatar novos vínculos.
- Criada a migração idempotente `013_v2_additional_device_license.sql`; a migração 010 e a `account-api` também foram atualizadas para instalações limpas.
- Validação local final desta etapa: **80 testes automatizados aprovados** e compilação Python aprovada.
- Migração 013 aplicada com sucesso no projeto Supabase v2 `saas-assistente-desktop-v2-prod` (`hnwvtoiiuqagzmuqygkw`) em 02/09/2026; o SQL Editor confirmou `Success. No rows returned`.
- `account-api` republicada no mesmo projeto com a validação de assinatura ativa antes de gerar código de vínculo; o Supabase confirmou `Successfully updated edge function`.
- O teste físico em um segundo computador foi adiado por indisponibilidade de outra máquina. Ele permanece obrigatório antes do beta público, mas não bloqueia as etapas locais seguintes.

## Recuperação segura de senha — 02/09/2026

- O botão **Esqueci minha senha** agora abre uma janela completa, em vez de apenas solicitar o e-mail e encerrar o fluxo.
- O usuário solicita o código, informa os seis números recebidos e cadastra/confirma a nova senha dentro do Desktop.
- A sessão de recuperação é temporária e não libera o sistema automaticamente. Código, senha e token temporário não são persistidos; os campos sensíveis são apagados ao concluir ou falhar.
- A troca é feita diretamente pelos endpoints oficiais do Supabase Auth, e a sessão local anterior é removida após a alteração.
- Validação local: **85 testes automatizados aprovados** e compilação Python aprovada.
- O projeto Supabase v2 passou a usar SMTP personalizado da Brevo no plano gratuito, com remetente individual verificado. A credencial SMTP foi informada diretamente no painel pelo proprietário e não foi compartilhada nem registrada no repositório ou nesta memória.
- Os templates **Confirm signup** e **Reset password** foram personalizados para exibir `{{ .Token }}` como código de seis números, eliminando a dependência do redirecionamento visual para `localhost:3000` nesses fluxos.
- O teste real de recebimento e consumo do código de recuperação permanece pendente e deve ser executado no Desktop 2.0 antes do beta.
- A configuração sem domínio próprio é provisória para desenvolvimento. Antes da distribuição pública, deve-se adquirir e autenticar um domínio de envio com SPF, DKIM e DMARC para melhorar identidade e entregabilidade.
- A primeira tentativa real foi aceita pelo Supabase, porém não chegou ao destinatário. No chamado **#5540512**, a Brevo confirmou que a plataforma transacional já estava ativa e identificou divergência de grafia entre o remetente verificado e o campo `Sender email` do Supabase. O proprietário corrigiu o remetente copiando o endereço validado; o código passou a ser entregue.
- O projeto Supabase v2 emitiu OTP de **8 dígitos**. O Desktop deixou de presumir tamanho fixo e agora aceita códigos numéricos de 6 a 10 dígitos, faixa suportada pelo Supabase, tanto na confirmação do cadastro quanto na recuperação de senha.
- O teste com uma conta protegida por TOTP retornou corretamente `INSUFFICIENT_AAL`: o código recebido por e-mail cria uma sessão AAL1 e o Supabase exige AAL2 para trocar a senha de quem possui MFA. A recuperação agora detecta fatores TOTP verificados, solicita o código atual do aplicativo autenticador, eleva apenas a sessão transitória e então altera a senha. Contas sem MFA mantêm o fluxo em uma etapa.
- Código de e-mail, código TOTP, senha e sessão transitória não são persistidos. Falhas registram somente o código técnico sanitizado para diagnóstico.
- Após as correções de OTP e MFA: **17 testes direcionados** e **90 testes automatizados completos** aprovados; compilação dos módulos alterados aprovada.
- Teste integrado real concluído em 02/09/2026: solicitação pelo Desktop, entrega via Supabase/Brevo, validação do OTP de 8 dígitos, detecção de MFA, desafio TOTP, elevação transitória para AAL2 e alteração da senha confirmada pelo servidor. O usuário recebeu a mensagem **Senha alterada**.

## Gestão empresarial no Gerador Admin 2.0 — 02/09/2026

- Criada localmente a área independente **Empresas 2.0** no Gerador Admin, sem substituir as telas legadas necessárias durante a transição.
- A nova grade apresenta empresa, unidade/CNPJ, computador, classificação principal/adicional, acesso, assinatura, vigência, total consolidado e quantidade de usuários ativos. A busca aceita empresa, CNPJ ou identificador do computador.
- A edição da assinatura possui botão fixo **Salvar alterações** e permite ajustar status, mensalidade principal, valor por computador adicional e vigência. O total segue a regra já aprovada: R$ 300,00 pela primeira vaga faturável e R$ 50,00 por vaga adicional; bloqueio operacional continua faturável até a remoção efetiva.
- Criada a migração local `014_v2_admin_enterprise_management.sql`. Ela atualiza assinatura e licenças de compatibilidade numa única transação, sem alterar tokens, e registra a operação em `audit_events`.
- O Gerador pode bloquear ou liberar somente o computador selecionado. A operação não altera os demais computadores nem cancela uma remoção adicional já programada. Uma assinatura inativa ou vencida impede a liberação indevida.
- As novas mutações da `admin-api` permanecem protegidas pela validação administrativa e MFA já existente. As funções SQL revogam acesso de `public`, `anon` e `authenticated`, concedendo execução apenas à `service_role`.
- Validação local: sintaxe Python aprovada, `git diff --check` sem erros e **36 testes administrativos/contratuais aprovados**, incluindo cálculo consolidado, proteção das RPCs, auditoria e mensagens de erro.
- **Ainda não implantado:** a migração 014 não foi executada e a `admin-api` não foi republicada no projeto Supabase v2. O Gerador novo não deve ser aberto contra a função antiga antes dessas duas publicações coordenadas.

### Implantação e executável de teste — 02/09/2026

- Migração 014 aplicada no projeto isolado `saas-assistente-desktop-v2-prod`; o SQL Editor confirmou **Success. No rows returned**.
- Verificação somente leitura encontrou as duas RPCs empresariais. `service_role_execute=true`, `authenticated_execute=false` e `anon_execute=false` em ambas.
- `admin-api` republicada pelo editor do Supabase como pacote autônomo; o painel confirmou **Successfully updated edge function**. A publicação não alterou empresas, assinaturas ou computadores.
- Criado ambiente de compilação isolado em `.admin_build_deps`, sem usar nem alterar o ambiente da versão 1.9.6.
- Testes administrativos/contratuais repetidos antes do build: **36 aprovados**.
- Executável de teste gerado em `dist_admin_v2/Gerador Admin - SaaS Assistente PRO.exe`, com **32.443.122 bytes** e SHA-256 `5B788C97CD3C0680A73225976F66B26C0170C485A60057E9FFB3EDBCF76D336D`.
- O executável foi iniciado para o teste integrado. O usuário ainda precisa concluir o login com senha e MFA e confirmar que a área **Empresas 2.0** carregou corretamente.
- Na primeira tentativa, o Supabase retornou `BOOT_ERROR`. O editor havia anexado o pacote novo ao código anterior, criando três imports e três chamadas `Deno.serve`; portanto, a falha não estava nas credenciais nem no MFA.
- O conteúdo foi substituído integralmente e republicado com uma única importação e uma única chamada `Deno.serve`. Teste HTTP sem credenciais passou de `503 BOOT_ERROR` para `401 {"error":"UNAUTHORIZED"}`, comprovando que a função inicia e rejeita corretamente acesso não autenticado.
- O usuário repetiu a validação pelo executável e confirmou que o login administrativo com senha e MFA foi concluído com sucesso. A integração Gerador → Auth → MFA → `admin-api` está aprovada.
- A área **Empresas 2.0** foi validada visualmente no executável corrigido: CNPJ completo, estados em português, total consolidado e rodapé singular/plural foram exibidos corretamente.
- A janela **Editar assinatura** apresentou status, mensalidade principal, valor por computador adicional, vigência e os botões fixos **Salvar alterações** e **Cancelar**, sem cortes.
- A confirmação de bloqueio identificou o computador selecionado e informou que a assinatura e as demais máquinas não seriam alteradas. O bloqueio não foi confirmado, preservando a única máquina ativa do teste.
- Com essa conferência, a implementação e a validação visual da gestão empresarial no Gerador Admin 2.0 estão concluídas. O próximo bloco funcional é a fatura consolidada com PIX e boleto em ambiente de teste.

## Cobrança consolidada PIX e boleto — 02/09/2026

- Criada a migração `015_v2_consolidated_billing.sql`, com preparação atômica da fatura empresarial, tentativa idempotente por meio de pagamento, registro da Order do Mercado Pago e aplicação transacional do pagamento confirmado.
- O valor da fatura é congelado por período com a regra da assinatura empresarial. PIX e boleto são tentativas da mesma fatura, e cliques repetidos reutilizam a tentativa pendente do mesmo método.
- A renovação ocorre somente para Order com `status=processed` e `status_detail=accredited`, após conferência do identificador externo e do valor exato. A operação atualiza fatura, assinatura e licenças de compatibilidade numa única transação e é idempotente.
- Criada a Edge Function `billing-api`, baseada na API de Orders atual do Mercado Pago. O Access Token é lido exclusivamente do segredo `MERCADO_PAGO_ACCESS_TOKEN`; nenhuma credencial foi incluída no código ou no executável.
- O webhook valida HMAC SHA-256 pelos cabeçalhos `x-signature` e `x-request-id`, consulta a Order diretamente no Mercado Pago e somente então chama a RPC de conciliação. A chave `MERCADO_PAGO_WEBHOOK_SECRET` foi cadastrada diretamente nos segredos da função, sem ser exibida ou registrada no repositório.
- A Conta Empresarial recebeu acesso à janela de cobrança, com dados fiscais/endereço, geração de PIX ou boleto, código copiável, abertura da página de pagamento e botões fixos. Somente o proprietário pode salvar dados ou gerar cobrança; demais perfis podem consultar.
- Migração 015 aplicada com sucesso no projeto Supabase v2; o SQL Editor respondeu **Success. No rows returned**. A `billing-api` foi publicada e a verificação JWT legada foi desativada apenas nessa função, mantendo autenticação própria para usuários e HMAC para o webhook.
- A URL do webhook foi cadastrada no Mercado Pago para eventos de **Orders**. A etapa guiada do portal do provedor já havia sido marcada manualmente como testada; isso não substitui nem bloqueia o teste integrado pelo Desktop.
- Foi criado um runtime de teste isolado em `.desktop_test_deps`, sem alterar o ambiente da versão 1.9.6. Os **37 testes direcionados** de autenticação, Conta Empresarial, janela de cobrança, contratos Edge, regras empresariais e isolamento de armazenamento foram aprovados; `deno check` também foi aprovado. O webhook sem assinatura retornou HTTP 401.
- Corrigido o caminho de dados locais da versão 2.0 para `%APPDATA%\\SaasAssistentePRO-v2`. Os dados necessários foram copiados uma única vez de `%APPDATA%\\SaasAssistentePRO`, preservando integralmente a pasta da versão estável.
- A primeira tentativa de abertura do executável revelou que `beautifulsoup4`, já usada pela tela de extração, não constava em `requirements.txt`. A dependência foi declarada e instalada somente no runtime isolado; a importação do módulo principal foi verificada antes de um novo build limpo.
- Executável corrigido para o teste integrado gerado em `dist_desktop_v2_billing_test/SaaS Assistente PRO 2.0 - Teste.exe`, com **192.287.773 bytes** e SHA-256 `92B9F2B4FC71454B581DDCE224C927FA9CB781B93FEA84733214A56C4FC45F54`.
- O executável corrigido foi iniciado e permaneceu em execução após a verificação inicial. Pendente: validar visualmente a janela de cobrança e depois gerar uma Order de teste, sem pagamento real, para confirmar a integração ponta a ponta.
- A validação visual seguinte encontrou três heranças da versão estável: título ainda em `1.9.6`, atalho legado **Loja PIX (Recarga)** e erro genérico da Conta Empresarial quando não havia sessão de usuário após uma recuperação de senha.
- A identidade do beta foi atualizada para `2.0.0-beta.1`; o atalho e a instrução do PIX legado foram removidos. PIX e boleto permanecem somente no fluxo novo de cobrança consolidada da Conta Empresarial.
- A ausência de `supabase_user.dat` na pasta isolada confirmou a causa do erro da Conta Empresarial. A tela agora abre um diálogo seguro de login quando necessário, permite recuperação de senha e volta a carregar a empresa após autenticar. A senha é mascarada, nunca persistida e apagada do diálogo ao concluir ou falhar.
- Após a correção, sintaxe Python e **43 testes direcionados** foram aprovados. Novo executável: **192.294.461 bytes**, SHA-256 `89684C322C00BE94E30AAE353031DDB77A81C989B354C45CAB73B478882018A7`. Ele foi iniciado e permaneceu em execução para nova validação visual.
- A validação seguinte autenticou `berg.suportetr@gmail.com`, mas a `account-api` devolveu zero vínculos. Consulta somente leitura no projeto confirmou que esse usuário existe sem empresa e que **Grupo Ipe Motos** pertence ao usuário proprietário `berg.araujo.ice@gmail.com`; nenhum cadastro foi modificado.
- Quando o login existe, mas não possui vínculo empresarial, a tela agora informa explicitamente que o e-mail não está cadastrado em nenhuma conta empresarial e oferece entrar com outro e-mail. A troca remove somente a sessão local daquele login e reabre o diálogo seguro.
- A revisão passou em **44 testes direcionados**. Executável aberto para reteste: **192.293.958 bytes**, SHA-256 `550C4C6D14B35898D3EAC3301755C870CD115D6E9ECCC953652264D7C8EA70EE`.
- O proprietário recuperou/acessou a conta correta e a Conta Empresarial foi validada visualmente no beta: Grupo Ipe Motos, papel Proprietário, CNPJ formatado, uma máquina principal ativa, mensalidade consolidada de R$ 300,00, vigência e versão `2.0.0-beta.1` carregaram corretamente. A rolagem vertical expôs toda a página e o botão **Abrir cobrança e pagamentos** permaneceu acessível.
- A primeira inspeção da janela de cobrança confirmou rolagem e rodapé fixo, mas mostrou ausência do valor antes da geração, campos sem reaproveitar empresa/CNPJ, rótulos com borda herdada e ações de resultado pouco claras.
- A janela revisada agora exibe **Valor previsto da próxima fatura**, pré-preenche nome empresarial e CNPJ a partir do resumo já autorizado, mantém os demais dados fiscais para confirmação do proprietário, remove bordas indevidas dos rótulos e apresenta **Copiar código**/**Abrir pagamento** com estado desativado visível até existir uma cobrança.
- Sintaxe e **46 testes direcionados** aprovados após a revisão visual. Executável aberto: **192.295.933 bytes**, SHA-256 `E106DFBA8ACBEB8684A697A7F9C1D2B2B936125AD0196023073D967872E22F57`.
- No primeiro salvamento real do perfil de cobrança, a conta proprietária ainda não possuía fator MFA verificado. O cadastro tentou renderizar o novo QR TOTP por `PIL.ImageQt` e gerou `AssertionError` somente no executável empacotado, encerrando o aplicativo.
- A renderização do QR foi substituída por PNG em memória carregado diretamente pelo `QPixmap`, removendo a ponte incompatível do Pillow. Callbacks de apresentação do MFA agora capturam falhas e exibem mensagem, sem deixar a exceção encerrar o processo.
- O teste automatizado renderizou um QR TOTP válido e a suíte direcionada passou com **47 testes**. Executável corrigido aberto: **192.294.405 bytes**, SHA-256 `DA682E6923A438A450165F02FAE0FED92B0C2E23322B7E51CAE7CE8C1D241055`.
- Após decisão de produto, o TOTP foi removido das operações empresariais do cliente. Alterações protegidas agora solicitam OTP ao e-mail da própria sessão, recusam troca de identidade e aceitam somente autenticação `otp` emitida nas últimas 12 horas. Códigos e e-mails não são persistidos localmente.
- Salvar perfil de cobrança exige confirmação recente por e-mail; gerar PIX ou boleto permanece restrito ao proprietário, mas não pede novo código. A renovação continua condicionada ao webhook validado do Mercado Pago.
- `account-api` e `billing-api` foram republicadas no projeto Supabase v2 e o painel confirmou **Successfully updated edge function** para ambas. O `admin-api` não foi alterado e continua exigindo MFA por aplicativo.
- Testes direcionados de autenticação, identidade, interface, contratos Edge, cobrança e isolamento: **47 aprovados**. Pendente apenas salvar o modelo **Magic link or OTP** com `{{ .Token }}` e gerar o novo executável de teste.
- Novo executável beta gerado em `dist_desktop_v2_email_otp_test/SaaS Assistente PRO 2.0 - Teste.exe`, com **192.296.571 bytes** e SHA-256 `4E5C4BE18278F88F564DEEF6BD71F97ADED0F8B97DDAC5642A499B6DD655C641`. Pendente: salvar o modelo de e-mail já preparado no painel e realizar a validação integrada pelo proprietário.

## Redesenho visual do Gerador Admin 2.0 — 04/09/2026

- A interface administrativa foi reorganizada para reduzir a sensação de telas técnicas e facilitar a localização das funções por usuários não técnicos.
- O tema principal passou a usar fundo claro, cartões brancos, hierarquia tipográfica mais nítida e azul como cor primária, mantendo a barra lateral em azul-marinho para orientação constante.
- A navegação foi agrupada em **Gestão de clientes** e **Sistema e suporte**, com rótulos mais descritivos: computadores e licenças, empresas e assinaturas, versões/preços/avisos, chaves temporárias e auditoria/diagnósticos.
- O cabeçalho de cada área agora explica a finalidade da tela. Os indicadores gerais aparecem somente nas áreas em que ajudam a decisão e são ocultados nas telas operacionais em que causavam excesso de informação.
- A tela de acesso administrativo recebeu campos explicitamente rotulados, texto de segurança mais claro e identidade visual alinhada ao restante do Gerador.
- Validação automatizada completa: **130 testes aprovados**. Executável de prévia gerado em `dist_admin_v2_redesign_test/Gerador Admin - SaaS Assistente PRO.exe`, com **32.803.746 bytes** e SHA-256 `C1C6D002A8CBF79B6C97A95D432F1464141CA69AF9299C5C7DEBC7FD11EF7AA8`.
- Pendente: validação visual do proprietário em resolução real antes de considerar o novo desenho aprovado.
- Revisão de intuitividade em 05/09/2026: as áreas sobrepostas foram preservadas, mas reorganizadas como **Por computador** e **Por empresa**. Cartões de contexto explicam se a alteração afeta uma máquina ou a conta inteira; há atalhos entre os fluxos e o atalho da empresa mantém o computador selecionado ao abrir seus ajustes individuais.
- Nenhuma função foi removida: edição de licença, limites diários e por lote, relatórios, avisos, assinatura, preços, vigência, bloqueio, chaves e auditoria permanecem disponíveis.
- A janela principal deixou de forçar maximização depois de calcular sua posição. Login, painel e modais agora são centralizados após o layout, respeitando a área útil do monitor atual e a barra de tarefas.
- Suíte completa após a revisão: **132 testes aprovados**. Nova prévia em `dist_admin_v2_intuitive_test/Gerador Admin - SaaS Assistente PRO.exe`, com **32.805.618 bytes** e SHA-256 `402C37AFECDA2594A8E22EBFFBAAB3414F288DF8EEE4108915CBB483160AA2A8`.
- A validação visual revelou estouro lateral em monitores com escala do Windows acima de 100%. A causa era o CustomTkinter aplicar o DPI ao tamanho da janela, mas manter a posição em pixels físicos. O centralizador agora converte o limite físico para a escala lógica, calcula a posição pelo tamanho já escalado e preserva margem em relação à área útil do monitor.
- A correção de DPI manteve os **132 testes aprovados**. Prévia corrigida em `dist_admin_v2_dpi_test/Gerador Admin - SaaS Assistente PRO.exe`, com **32.807.712 bytes** e SHA-256 `4632811A06546D1BC7A06EDD1AA017C7DC4E1B82897848CE63A77766E03B6FB4`.

## Estabilidade SSI/TSI e preservação local — 06/09/2026

- O teste visual A→B→A foi realizado pelo proprietário com registros reais e confirmou que o WhatsApp abre o destinatário escolhido. O nome exibido no topo também foi corrigido para sempre refletir a conversa iniciada por último.
- Como não existem números controlados na base atual, nenhum lote real foi executado. A validação de lote permanece adiada para evitar contato indevido com clientes reais.
- A abertura assíncrona da ficha SSI agora possui um identificador exclusivo por operação. Respostas atrasadas de uma ficha anterior são ignoradas e não podem preencher, abrir conversa ou avançar a fila do cliente seguinte.
- As gravações dos históricos TSI, SSI, pesquisas enviadas, mapeamento de clientes e comunicados passaram a usar arquivo temporário, sincronização e substituição atômica.
- Um histórico existente com JSON inválido deixa de ser interpretado como vazio durante atualizações: a operação é cancelada e o arquivo original é preservado para diagnóstico/recuperação.
- Foram adicionados testes para callbacks SSI obsoletos, interrupção de arquivos, preservação de conteúdo inválido e manutenção da deduplicação. Suíte completa: **145 testes aprovados**.
- Nova prévia gerada em `dist_desktop_v2_extraction_stability_test/SaaS Assistente PRO 2.0 - Teste.exe`, com **193.221.955 bytes** e SHA-256 `4773AA9E76155EAD7693CC22DB86B4AF08DADB69F2A00E6685185406776233A2`. A prévia anterior foi encerrada pelo caminho exato e esta compilação foi iniciada para avaliação, sem afetar o Gerador Admin nem a versão 1.9.6.

## Integridade dos indicadores SSI/TSI — 08/09/2026

- A revisão dos dashboards identificou que uma pesquisa sem nota válida de recomendação podia ser apresentada como detratora. TSI e SSI agora classificam esse caso separadamente como **Sem nota de recomendação**, com filtro e identidade visual próprios.
- Os percentuais de Promotores, Neutros e Detratores do TSI passaram a usar somente respostas válidas de 0 a 10 como denominador. Valores ausentes, negativos ou acima de 10 não distorcem a classificação ou o NPS.
- O período TSI agora reconhece datas brasileiras, mês/ano e timestamps ISO com horário, evitando que respostas válidas caiam em **Desconhecido**.
- Dez cenários históricos de métricas que dependiam de `pytest` foram incorporados à suíte padrão `unittest`, sem adicionar dependência ao executável.
- Suíte completa após a revisão: **159 testes aprovados**. A fila de enviados/respondidos e o relatório personalizado permaneceram intocados, conforme decisão do proprietário.
- Prévia gerada em `dist_desktop_v2_dashboard_integrity_test/SaaS Assistente PRO 2.0 - Teste.exe`, com **193.224.628 bytes** e SHA-256 `17F3BB55F9DFA09AEC53748055CDCAAD01CC7F5681E7219A032669E5EED8C980`. O executável foi iniciado para conferência visual dos dashboards.

## Ativação simplificada de computador adicional — 08/09/2026

- O primeiro acesso de um computador adicional deixou de solicitar e-mail e senha. A tela agora pede somente o código de ativação gerado no computador principal.
- O código adotado tem formato curto `PC-ABCD-1234`, validade de 15 minutos e uso único. O banco armazena somente seu hash, limita tentativas por hardware, vincula empresa/unidade/hardware e registra auditoria.
- A geração continua restrita a proprietário ou administrador autenticado, mas não exige uma segunda confirmação por e-mail. As demais alterações empresariais sensíveis preservam o OTP.
- A Conta Empresarial mostra o acréscimo mensal antes da geração. Assinatura ou teste vencido desabilita o botão e informa claramente a data e a necessidade de renovação.
- A migração `018_v2_simple_device_activation.sql` foi aplicada no projeto Supabase. Como nenhuma instalação 2.0 está em uso, o overload antigo de resgate foi removido e permanece somente o contrato novo, sem e-mail, senha ou MFA no computador adicional.
- `account-api` e `desktop-api` foram publicadas pelo editor web; o painel confirmou **Successfully updated edge function** para ambas. A migração foi corrigida para chamar `extensions.digest`, conforme o schema real do `pgcrypto` no projeto.
- Teste remoto com código fictício bem-formado retornou `409 {"ok":false,"error":"LINK_CODE_NOT_AVAILABLE"}`. Isso comprova que o endpoint novo está online, aceita a solicitação sem sessão de usuário e rejeita códigos inexistentes sem criar vínculo.
- O primeiro resgate de um código real revelou que a segunda chamada criptográfica da função ainda usava `gen_random_bytes` sem o schema do `pgcrypto`. A migração 018 foi corrigida para `extensions.gen_random_bytes` e reaplicada no Supabase.
- Um teste transacional completo criou código, instalação e licença e terminou em `ROLLBACK`; o SQL Editor respondeu **Success. No rows returned**, confirmando o fluxo sem deixar dados de teste no projeto. O código real que falhou antes da correção não foi consumido pela transação abortada e pode ser reutilizado enquanto estiver dentro dos 15 minutos.
- A previsão do próximo computador na Conta Empresarial passou a exibir separadamente o valor atual e o total após a próxima ativação, eliminando a aparente divergência com a cobrança consolidada.
- No Gerador Admin, o acesso individual foi renomeado para **Licença e envios**. O formulário agora separa **Licença e cobrança**, **Limites de envio** e **Comunicação**, usando os rótulos **Limite diário de mensagens** e **Clientes permitidos por disparo**. A ajuda esclarece que o lote é selecionado de uma vez, mas enviado sequencialmente.
- Validação desta melhoria: 10 testes da Conta Empresarial, 9 testes de visual/ações do Gerador e 12 testes dos limites de mensagens aprovados. Desktop recompilado em `dist_desktop_v2_price_hint_test` (193.225.456 bytes; SHA-256 `CBBD747FDCB7F136C3349995B98C131E08088BC65AF2EA57D5EE7DAE83CBADDF`). Gerador recompilado em `dist_admin_v2_limits_test` (32.828.107 bytes; SHA-256 `2EE103AB84D8C6CBB96F4452688D0F74282E4F0B6BC2359DFE2DC7746C796884`).
- Suíte completa: **165 testes aprovados**. Prévia local gerada em `dist_desktop_v2_simple_activation_test/SaaS Assistente PRO 2.0 - Teste.exe`, com **193.225.018 bytes** e SHA-256 `92AA67E370BCAB37CB2F9232815CFE63665390B5E111C17424586426C45B45C0`.

## Atualizador automático e build oficial 2.0.0 — 08/09/2026

- O Assistente de Atualização deixou de exigir reabertura manual. Depois que o Desktop fecha, ele aguarda o processo terminar, executa o Inno Setup silenciosamente, abre o executável instalado e encerra sozinho. Em caso de falha de instalação ou abertura, exibe uma orientação segura ao usuário.
- O comparador de versões passou a compreender pré-lançamentos; `2.0.0` é reconhecida corretamente como posterior a `2.0.0-beta.1`.
- O comando enviado ao assistente contém explicitamente o caminho oficial por usuário `%LOCALAPPDATA%\\Programs\\SaaS Assistente PRO\\SaaS Assistente PRO.exe`.
- Foi restaurado no projeto 2.0 o script coordenado `update_version.py`, que atualiza `src/version.py`, a versão do Inno Setup, o nome do executável de origem e o nome do instalador.
- Regressão completa após a alteração: **171 testes aprovados**. Os 13 testes específicos cobrem comparação beta/final, validação SHA-256/PE, parâmetros silenciosos, caminho de reabertura, acionamento do novo executável e versionamento coordenado.
- Build oficial protegido concluído: `dist/Instalador_SaaS_Assistente_PRO_v2.0.0.exe`, **247.066.250 bytes**, SHA-256 `ad54831034219d4dd5b6609dda6b32424fc6ce49ec2e85d8a3cf3bd64a8ba8df`. Manifesto: `dist/release_v2.0.0.json`.
- A inspeção interna confirmou `SaaS Update Assistant.exe` incorporado ao executável principal. O teste integrado do assistente instalou silenciosamente no caminho oficial, removeu a cópia temporária e abriu automaticamente o Desktop instalado.
- Release `v2.0.0` publicada no GitHub como **Latest**, com o instalador de 236 MB e digest exibido pelo próprio GitHub idêntico ao manifesto local.
- O Supabase v2 foi configurado com `current_version=2.0.0`, `minimum_version=0.0.0` e `update_required=false`, mantendo a primeira distribuição opcional. A consulta de confirmação retornou o link público e o SHA-256 corretos.
- O cliente real do Desktop, simulando `2.0.0-beta.1`, recebeu os cinco parâmetros corretos do `desktop-api`.
- Teste OTA remoto concluído em 09/09/2026: o `DownloadWorker` baixou o instalador público, validou PE/SHA-256 sem erros; o assistente instalou, removeu o arquivo temporário e reabriu automaticamente `%LOCALAPPDATA%\\Programs\\SaaS Assistente PRO\\SaaS Assistente PRO.exe`.
# Hotfix de distribuição 2.1.4 — 14/09/2026

- A versão pública 2.1.3 falhava antes de abrir a interface com `ModuleNotFoundError: PyQt6.sip`; o arquivo existia no ambiente de build, mas não havia sido coletado pelo PyInstaller.
- O build 2.1.4 declara `PyQt6.sip` como importação obrigatória e executa um teste do executável empacotado antes de permitir que o Inno Setup gere o instalador.
- O botão de cópia do PIX deixou de depender de `pyperclip`, ausente no ambiente de distribuição, e passou a usar a área de transferência nativa do Qt.
- Dependências de build alinhadas ao ambiente Python 3.14: PyQt6/PyQt6-WebEngine 6.11.0 e PyQt6-sip 13.11.1.
- Validação local concluída: executável empacotado aprovado, instalação limpa isolada aprovada com código 0 e suíte completa com **199 testes aprovados**.
- Instalador gerado em `dist/Instalador_SaaS_Assistente_PRO_v2.1.4.exe`, SHA-256 `BE3C51ECCE51930C7048F680713603E7558AE4B1A96E3976CCD145607D922811`.
- Commit `e601731` enviado à `main`; release pública `v2.1.4` criada como a versão mais recente. O asset remoto confirmou 247.066.480 bytes e digest idêntico ao manifesto local.
- OTA atualizado como opcional (`current_version=2.1.4`, `minimum_version=0.0.0`, `update_required=false`) com URL e SHA-256 confirmados pelo retorno do Supabase.
- Site público publicado como versão Sites 5 no mesmo endereço. Resposta HTTPS 200 confirmou o texto 2.1.4 e o novo instalador, sem referência ao instalador 2.1.3.
- E-mail público de suporte atualizado em 14/09/2026 para `berg.suportetr@gmail.com` em todos os links de contato e condições. Sites versão 6 publicada; conferência HTTPS confirmou o novo endereço e ausência do e-mail anterior.

## Manual do usuário 2.1.4 — 14/09/2026

- Manual operacional completo criado em `docs/Manual_do_Usuario_SaaS_Assistente_PRO_2.1.4.docx`, com 23 páginas sobre primeiro acesso, licenças, limites, cobrança, menus, myHonda, auditores SSI/TSI, fila, disparos, modelos, dashboards, configurações, conta empresarial, computadores, segurança, suporte e solução de problemas.
- Regra temporal confirmada pelo proprietário e mantida sem mudança no código: dias 1, 2 e 3 consultam mês atual e anterior; a partir do dia 4, somente o mês atual. O texto anterior de cinco dias foi reconhecido como informação incorreta.
- Documento renderizado pelo Microsoft Word e todas as 23 páginas inspecionadas visualmente após correção de numeração e remoção de página em branco.

## Correção da busca de clientes — 14/09/2026

- Corrigido o campo de busca da fila, que herdava texto branco sobre fundo branco e tornava a digitação invisível.
- A filtragem agora recebe explicitamente o texto emitido pelo campo, converte valores de cliente com segurança e normaliza maiúsculas, acentos e espaços; por exemplo, `jose` encontra `JOSÉ`.
- Teste funcional novo confirmou o recorte por nome e pelo tipo ativo SSI/TSI. Suíte completa aprovada com **203 testes**.
- A correção está no código-fonte e ainda precisa ser empacotada/publicada em uma versão posterior à 2.1.4 para chegar às instalações existentes.

## Atualização 2.1.5 para teste OTA — 14/09/2026

- Versão coordenada atualizada para 2.1.5 e notas de lançamento criadas.
- Build oficial concluído após teste obrigatório do executável empacotado.
- Instalador gerado em `dist/Instalador_SaaS_Assistente_PRO_v2.1.5.exe`, com 247.066.662 bytes e SHA-256 `bf1b4bc16172609224f6ace61bf0297db8aa3a6a04c9155de36c0db27fae8e9e`.
- Manifesto `dist/release_v2.1.5.json` conferido contra tamanho e hash reais.
- Instalação silenciosa em diretório isolado e teste de abertura do executável instalado aprovados.
- Commit `583b9f3` enviado à `main`; release pública `v2.1.5` criada como **Latest** e ligada ao mesmo commit.
- Asset remoto confirmado com 236 MB e digest SHA-256 `bf1b4bc16172609224f6ace61bf0297db8aa3a6a04c9155de36c0db27fae8e9e`, idêntico ao manifesto local.
- Supabase atualizado e confirmado com `current_version=2.1.5`, `minimum_version=0.0.0`, `update_required=false`, URL pública do instalador e o mesmo SHA-256.
- A consulta de simulação pelo cliente local não pôde concluir o teste autenticado porque a sessão de instalação desta máquina retornou `UNAUTHORIZED`. O teste físico 2.1.4 → 2.1.5 permanece pronto para uma instalação com licença ativa.

## Hotfix do encerramento OTA 2.1.6 — 14/09/2026

- No teste físico 2.1.4 → 2.1.5, a instalação foi seguida pelo aviso do bootloader `Failed to remove temporary directory: _MEI...`.
- Causa corrigida: o assistente independente era iniciado diretamente de dentro de `_MEIPASS`, mantendo a pasta temporária do executável antigo bloqueada; além disso, `os._exit(0)` interrompia a limpeza normal do Qt/WebEngine.
- O assistente agora é copiado para `%TEMP%\SaaS_Intelligence_Update` antes da execução, e o encerramento usa `QApplication.quit()` sem saída forçada.
- A checagem OTA passou a ser agendada após o início do loop principal do Qt, permitindo encerramento normal durante a atualização.
- Testes específicos do atualizador e suíte completa aprovados: **206 testes**.
- Build oficial e instalação limpa isolada aprovados. Instalador: `dist/Instalador_SaaS_Assistente_PRO_v2.1.6.exe`, 247.066.764 bytes, SHA-256 `c831f60bd5b28c3569d0b10b26a046b73f321cd0f63ed9e6ecf7e736e66ccc06`.
- Manifesto conferido contra tamanho e hash reais; o executável instalado também passou no `--build-smoke-test`.
- Release `v2.1.6` publicada no GitHub como **Latest**, ligada ao commit `25dfb36`. O asset público confirmou 236 MB e SHA-256 `c831f60bd5b28c3569d0b10b26a046b73f321cd0f63ed9e6ecf7e736e66ccc06`, idêntico ao instalador local.
- Supabase atualizado e confirmado com `current_version=2.1.6`, `minimum_version=0.0.0` e `update_required=false`. A atualização 2.1.5 → 2.1.6 está disponível como opcional para repetir o teste físico.

## Limpeza dos vínculos de teste — 14/09/2026

- Removida do Supabase a empresa de teste **Grupo Ipe Motos**, incluindo sua unidade, vínculo empresarial, assinatura/cobrança associada e os dois computadores cadastrados.
- A operação foi protegida por validações transacionais: somente prosseguiu após confirmar exatamente uma empresa, dois computadores e um usuário vinculado. A conferência final retornou zero empresa, zero CNPJ, zero computadores e zero vínculos restantes.
- A identidade do usuário em `auth.users` foi preservada, permitindo que o mesmo e-mail seja reutilizado futuramente em um novo cadastro.
- Nesta máquina, o Desktop em execução foi encerrado e somente `supabase_installation.dat` e `supabase_user.dat` foram removidos. Históricos, configurações e dados operacionais locais permaneceram preservados.

## Diagnóstico do envio WhatsApp 2.1.7 — 15/09/2026

- Identificado falso positivo no disparo: o Desktop considerava a mensagem enviada imediatamente após disparar eventos de mouse por JavaScript, sem confirmar se o WhatsApp havia aceitado o clique. Em lote, isso podia marcar a pesquisa como enviada e confirmar o consumo mesmo com a mensagem ainda no rascunho.
- O fluxo agora separa `SEND_CLICK_ATTEMPTED` de `SEND_CONFIRMED`. A fila somente recebe sucesso depois que uma segunda verificação constata que o campo de composição foi limpo; rascunho persistente termina como falha e libera a reserva de envio.
- A procura do botão passou a registrar o seletor encontrado e motivos sanitizados como campo ausente, texto divergente, botão ausente ou rascunho persistente. Número e conteúdo da mensagem não são enviados pela telemetria.
- A tela do WhatsApp ganhou um teste controlado com número e mensagem livres. O botão só é habilitado quando a licença está com diagnóstico detalhado por 24 horas ativo; esse modo não emite sinais para a fila, não marca pesquisa e não consome franquia.
- A igualdade literal da URL deixou de bloquear o envio, e o texto passou a ser comparado com normalização de Unicode e espaços.
- O diagnóstico e as abas fantasmas agora ficam completamente ocultos fora do modo desenvolvedor. O atalho `Ctrl+Shift+D` exige autorização por equipamento válida por 24 horas, senha derivada com PBKDF2, comparação em tempo constante e bloqueio de 15 minutos após cinco erros.
- Suíte completa aprovada com **212 testes**. A instalação silenciosa isolada e o executável instalado passaram no `--build-smoke-test`.
- Instalador definitivo: `dist/Instalador_SaaS_Assistente_PRO_v2.1.7.exe`, 247.075.800 bytes, SHA-256 `1765a6e5f92b8a6e68162a525484caaf40b11b914d903a0f83d387476987b58d`.
- Commit `bbbf836` enviado à `main`; release pública `v2.1.7` criada como **Latest**. O asset remoto confirmou o mesmo SHA-256 do instalador local.
- Supabase atualizado e confirmado com `current_version=2.1.7`, `minimum_version=0.0.0`, `update_required=false`, URL pública do instalador e SHA-256 correto. A atualização foi disponibilizada como opcional.
- Site público atualizado para a versão Sites 8. A conferência da página publicada confirmou os três botões apontando para o instalador 2.1.7 e os textos de versão atualizados.

## Release 2.1.8 e homologação OTA — 21/09/2026

- Corrigidos o download HTTPS em redes corporativas, a recuperação segura do computador principal e os fluxos de homologação de PIX e boleto.
- O modo desenvolvedor passou a distinguir ausência de autorização temporária de falha de conexão; atalho, senha, abas ocultas e envio controlado para número definido foram homologados.
- Suíte completa aprovada com **227 testes**, testes de segurança/idempotência financeira e migrações de escala aprovados, além do `--build-smoke-test` do executável empacotado.
- Instalador definitivo: `dist/Instalador_SaaS_Assistente_PRO_v2.1.8.exe`, 231.855.861 bytes, SHA-256 `a3dd76e5fbb9ae0f6b7a8a868f4372067328b49674bfc9f60588090b5292683f`.
- Commit `db31199` enviado à `main`; release pública `v2.1.8` criada como **Latest** com instalador e manifesto, ambos conferidos no GitHub.
- Supabase atualizado e confirmado pelo endpoint do Desktop com `current_version=2.1.8`, `minimum_version=0.0.0`, `update_required=false`, URL pública e SHA-256 corretos.
- Teste físico OTA **2.1.7 → 2.1.8** aprovado: a versão antiga reconheceu a atualização, baixou e validou o instalador, encerrou, instalou silenciosamente e reabriu automaticamente já na v2.1.8.

## Release 2.1.9 — números sem WhatsApp — 23/09/2026

- Confirmação explícita de número indisponível persistida localmente em `unavailable_whatsapp.json`; fila atualizada, reinício e lote em andamento respeitam essa exclusão.
- Telefones extraídos do myHonda não são editáveis nem alterados. Um novo telefone extraído é elegível; falhas transitórias não excluem clientes.
- Tentativa indisponível libera a reserva, sem marcar envio ou consumir franquia. Diagnóstico não altera a fila.
- Suíte completa aprovada: 239 testes. Publicação autorizada pelo proprietário; validação real com WhatsApp será feita pelos clientes.
- Build oficial concluído após `--build-smoke-test`. Instalador: `dist/Instalador_SaaS_Assistente_PRO_v2.1.9.exe`, 231.785.454 bytes, SHA-256 `78a3b8ecb1446fa10cdb179b8347579584e96dceae095008633af1394ca1bcfb` (conferido contra o manifesto).
- Publicação GitHub e ativação OTA em andamento; não considerar disponível até confirmação abaixo.
