# Plano de Implementação — Assistente PRO Desktop

## Escalabilidade — auditoria 11/09/2026

- [x] Corrigir invalidação de caches e índices entre telas/instâncias.
- [x] Tornar conexões lazy de sinais idempotentes.
- [x] Corrigir e testar transferência atômica/owner-only do principal.
- [x] Implementar retenção e remoções vencidas em lotes concorrentes.
- [x] Restringir validação de constraints ao schema e às constraints pendentes.
- [x] Repetir os três testes visuais com Pillow compilado para o runtime Python usado no build.
- [x] Executar concorrência financeira com duas conexões PostgreSQL reais após aplicar a migração 029 no clone.
- [x] Gerar, conferir manifesto/hash e instalar em pasta isolada o instalador oficial 2.1.3.
- [x] Aplicar migrações 024–029 e publicar `account-api`/`cron-worker` no Supabase remoto.
- [x] Habilitar Supabase Cron, confirmar o job `saas-hourly-maintenance` e executar postflight remoto.
- [x] Publicar código e release 2.1.3 no GitHub e ativar OTA opcional com URL/SHA-256 conferidos.
- [x] Atualizar o site público com download direto da 2.1.3 e a identidade visual do ícone oficial.
- [ ] Assinar o instalador com certificado Authenticode antes de uma distribuição sem alerta do SmartScreen.
- [ ] Migrar JSON para SQLite somente após atingir o gatilho e concluir migração reversível.

## Validação PIX — 11/09/2026

- [x] Preparar backend local de recuperação: 023 + refresh_payment_status, owner/conta/ID/referência/throttle; 17 SQL e 13 HTTP simulados aprovados.
- [x] Integrar recuperação manual à tela e validar interface, Deno e PostgreSQL real; publicar 023 e billing-api v14. 93 Desktop, 17 SQL, 13 HTTP aprovados.
- [x] Concluir build e manifesto do instalador 2.0.7, sem instalação automática nem OTA.
- [ ] Aceite do instalador e consulta autenticada pelo proprietário; sem pagamento obrigatório para teste.

- [x] Executar 90 testes v2 e 16 cenários financeiros locais, todos aprovados.
- [x] Acrescentar caso de R$ 350: duas licenças renovadas uma vez e isolamento entre contas.
- [x] Implementar e testar consulta de recuperação de pagamentos sem webhook, com tentativa vinculada à conta, limitação de frequência e confirmação exclusivamente pelo provedor (backend publicado, aceite autenticado real pendente).
- [x] Testar handler HTTP/webhook assinado e falhas de rede com dependências simuladas, sem cobranças reais: nove casos aprovados em 11/09/2026.
- [x] Validar concorrência real e corrigir a ordem de locks Admin/pagamento com a migração 029.
- [ ] Homologar recebimento real do webhook em ambiente separado; testes SQL não substituem esta etapa.


## Revisão Admin/usabilidade — 2.0.6

- [x] Validar em clone PostgreSQL bloqueio/desbloqueio sequencial do adicional sem renovar validade nem afetar o principal; recusar assinatura vencida.
- [x] Corrigir largura zero da identificação da conta e adicionar teste de layout.
- [x] Diferenciar mensagens de cobrança, sem presumir cancelamento remoto.
- [x] Executar regressões: 90 testes v2, 39 direcionados (sobrepostos) e 19 de persistência/métricas/licenciamento/versionamento aprovados.
- [x] Conferir instalador 2.0.6 final e manifesto/hash.
- [ ] Validar as telas 2.0.6 no equipamento real.
- [x] Testar ações simultâneas de instalação/Admin e cobrança com duas conexões PostgreSQL reais; migração 029 aprovada sem deadlock/timeout.

## Recuperação do principal — revisão 2.0.5

- [x] Incluir login com senha e recuperação de senha no primeiro acesso.
- [x] Exigir OTP recente e proprietário ativo para rotacionar somente a credencial do mesmo principal.
- [x] Testar preservação de licença/assinatura e recusa de equipamento adicional/bloqueado ou outro usuário.
- [x] Publicar migração 022 e account-api v9; confirmar permissões RPC e rejeição HTTP sem autenticação.
- [x] Concluir build 2.0.5, conferir manifesto/hash e inspecionar telas com serviços simulados.
- [x] Homologar recuperação com o proprietário no computador principal (confirmações de e-mail e acesso recuperado recebidas em 10/09/2026).
- [x] Confirmar abertura da aplicação após recuperação (proprietário confirmou em 10/09/2026).
- [x] Conferir Conta Empresarial no principal: dois equipamentos ativos, principal 2.0.5 e adicional registrado como 2.0.0-beta.1.
- [x] Confirmar atualização/comunicação do segundo computador em 2.0.5, preservando o vínculo existente (screenshot com ambos ativos e acessos recentes em 10/09/2026).
- [ ] Concluir testes funcionais do adicional e homologação financeira/webhook/concorrência.

## Cadastro CPF/CNPJ — revisão 2.0.4

- [x] Aceitar CPF/CNPJ no cadastro, validação no Desktop/API/banco e preservação de documentos existentes.
- [x] Manter unicidade de documento e serializar cadastro por usuário para impedir repetição do trial pelo mesmo titular autenticado.
- [x] Adaptar cobrança e exibição/busca no Gerador Admin, sem alterar snapshots 020.
- [x] Testar no PostgreSQL real isolado e publicar migração 021/account-api v8/billing-api v13 no projeto v2.
- [x] Confirmar HTTP 401 sem credenciais nas duas funções atualizadas.
- [x] Finalizar build 2.0.4, conferir manifesto/hash e prévia visual com serviços simulados.
- [ ] Homologar cadastro real pelo proprietário (CPF não deve ser enviado no chat).
- [ ] Concluir homologação de pagamento/webhook e dois computadores antes da distribuição geral/OTA.

## Revisão de segurança 2.0.3 — estado local

- [x] Vincular tentativa de pagamento aos IDs dos computadores, valor e período.
- [x] Impedir renovação por PIX antigo após adicionar/substituir máquinas ou alterar preços.
- [x] Preservar bloqueios individuais, remover renovação implícita do formulário de limites e listar conciliações no Admin.
- [x] Corrigir verificação de versão e tratar QR cancelado/expirado/inválido.
- [x] Validar em PostgreSQL isolado (PGlite) e executar testes do Desktop/Admin.
- [x] Implantar migração 020 e publicar billing-api/admin-api/desktop-api coordenadamente; verificar rejeição de chamadas sem autenticação e webhook sem assinatura. O pgcrypto real foi confirmado no schema `extensions`.
- [ ] Homologar evento assinado válido, concorrência entre conexões e fluxo autenticado completo; conferir configuração de gateway da account-api com Conta Empresarial.
- [ ] Homologar os novos executáveis em máquina de teste e depois em um segundo computador.
- [ ] Conferir/cancelar cobranças anteriores sem snapshot no provedor antes de gerar nova cobrança.
- [ ] Consolidar o histórico Git sem incluir dependências, dados privados ou artefatos de build.
- [ ] Implementar fluxo completo de transferência de principal e gestão de membros (não entregue nesta revisão de cobrança).
- [ ] Implementar processamento efetivo das remoções agendadas no vencimento e validar a composição da fatura seguinte.
- [ ] Definir cobrança diferencial/pró-rata se desejada para adicionar máquina durante período já pago.

## Prioridade 1 — Estabilidade operacional

- Validar o fluxo completo de login e extração SSI/TSI.
- Consolidar seletores e parsers dos relatórios myHonda.
- Garantir que timeouts, recargas e relatórios vazios não travem a interface.
- [x] Validar deduplicação, gravação atômica e preservação dos históricos locais diante de JSON interrompido/corrompido.

## Prioridade 2 — Filas e WhatsApp

- [x] Preparar limites por instalação (dia/lote), campos administrativos e correção da seleção de conversa.
- [x] Revisar reservas de consumo e blindar callbacks SSI contra respostas atrasadas de operações anteriores.
- [x] Implantar migração 016 e funções v2 coordenadas.
- [x] Implantar migração 017 e republicar `desktop-api` com reserva/confirmação/liberação atômicas.
- [x] Gerar o Desktop com a proteção nova de reservas e callbacks.
- [x] Validar troca A→B→A com contatos controlados e corrigir o nome/destaque da conversa ativa.
- [x] Exibir quantidade selecionada e exigir confirmação explícita antes de iniciar lotes.
- [ ] Validar um lote real somente quando houver números controlados, incluindo cancelamento e uma falha segura. *(adiado: a base atual contém apenas contatos reais)*

- Revisar a formação das filas de primeiro envio e reenvio.
- Confirmar exclusão automática dos clientes já respondidos.
- Validar templates, variáveis, seleção de clientes e sanitização de telefones.
- Testar disparo, pausas, retomada, cancelamento e registro de falhas no WhatsApp Web.

## Prioridade 3 — Auditores e dashboards

- Validar extrações dos auditores TSI e SSI com páginas reais.
- [x] Conferir por testes controlados cálculos de Top2Box, médias, NPS e tratamento de notas ausentes/inválidas.
- Validar filtros por data, loja, categoria, consultor e vendedor.
- Revisar rankings, gráficos diários e voz do cliente.

## Prioridade 4 — Distribuição

- Executar testes automatizados e testes manuais de regressão.
- Limpar arquivos temporários e separar dados do usuário dos arquivos da aplicação.
- [x] Gerar build protegido, instalador e pacote de atualização 2.0.0 com assistente de reabertura automática.
- [x] Testar instalação pelo assistente, limpeza do instalador temporário e abertura automática do executável atualizado.
- [x] Publicar o instalador 2.0.0 e configurar link HTTPS/SHA-256 no servidor para o teste OTA completo.
- [ ] Confirmar em outro computador que a atualização preserva `app_data`.

## Versão 2.0 — Conta empresarial

- [x] Criar backup físico da base estável 1.9.6.
- [x] Definir hierarquia empresa, unidades, usuários, computadores e assinatura.
- [x] Criar migração local, sem publicação, preservando tabelas da 1.9.6.
- [x] Isolar e testar o cálculo R$ 300,00 + R$ 50,00 por adicional.
- [ ] Revisar a migração em banco de teste e validar o backfill.
- [x] Implementar autenticação do proprietário, administradores e operadores.
- [x] Implementar recuperação de senha por código sem persistir credenciais.
- [x] Substituir TOTP do cliente por confirmação de operações empresariais via código de e-mail, mantendo TOTP no Gerador Admin.
- [x] Configurar SMTP de teste e templates de confirmação/recuperação com código de seis números.
- [ ] Implementar onboarding de clientes existentes sem recadastro integral.
- [x] Implementar vínculo de computador adicional por código descartável.
- [x] Implementar tela Empresa e Computadores no Desktop.
- [x] Implementar gestão correspondente no Gerador Admin. *(camada local, implantação Supabase, executável, login com MFA e validação visual das operações empresariais concluídos)*
- [x] Implementar fatura consolidada e escolha PIX/boleto.
- [x] Integrar Mercado Pago e webhook idempotente em ambiente de teste.
- [ ] Testar remoção, bloqueio e transferência da máquina principal.
- [ ] Gerar e validar 2.0.0-beta em dois computadores.
- [ ] Publicar 2.0.0 somente após aceite formal dos testes.
