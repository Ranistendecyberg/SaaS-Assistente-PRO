# Status de Desenvolvimento — Assistente PRO Desktop

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
