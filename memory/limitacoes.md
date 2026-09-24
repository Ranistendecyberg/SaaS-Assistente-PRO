# Limitações e Restrições Técnicas — Desktop

- A distribuição pública 2.1.3 não deve mais ser indicada para download: ela foi empacotada sem `PyQt6.sip` e falha antes da interface. Como não inicia, essa versão não consegue se autocorrigir por OTA; usuários que a baixaram precisam instalar manualmente a 2.1.4 ou posterior.
- A partir da 2.1.4, o pipeline impede a geração do instalador quando o executável empacotado falha no teste de importações essenciais. Esse teste reduz falhas de dependência, mas não substitui homologação visual, login real, myHonda, WhatsApp e pagamento em ambiente controlado.

- Auditoria 11/09/2026: caches e manutenção em lote foram corrigidos, mas JSON/pandas continuam limitando históricos grandes; considerar SQLite acima de 25 MB ou 50 mil registros.
- Os testes visuais foram desbloqueados com Pillow compatível e a suíte completa de 198 testes passou em Python 3.14.
- Migrações 024–029 e `account-api`/`cron-worker` foram publicados no Supabase remoto após validação local/PGlite e em clone PostgreSQL 17.11.
- Supabase Cron 1.6.4 está habilitado e o job `saas-hourly-maintenance` está ativo. O `cron-worker` permanece como fallback protegido por `CRON_SECRET`; sem esse segredo, responde 401 e não executa manutenção.
- O instalador 2.1.3 tem hash/manifeste e smoke test aprovados, porém não possui assinatura Authenticode; o Windows SmartScreen pode exibir aviso até a assinatura com certificado de editor.
- O binário 2.1.3 foi publicado no GitHub e anunciado via OTA opcional após aceite explícito do possível aviso do SmartScreen. `minimum_version=0.0.0` e `update_required=false`, portanto versões antigas não foram bloqueadas.

- Entrega 2.0.7 compilada; substitui pendência de build abaixo. Permanece aceite em máquina real, consulta autenticada com provedor, concorrência e entrega externa de webhook. Não confundir testes isolados com esses aceites.

- Atualização 11/09/2026: recuperação manual publicada em 023/billing-api v14 e integrada ao cliente 2.0.7 em compilação. Registros abaixo sobre ausência total do recurso são históricos. Não há polling automático do provedor: o proprietário usa o novo botão. Build/aceite real ainda pendentes neste registro; concorrência e entrega externa de webhook não homologadas.

- Recuperação 023 implementada localmente em 11/09/2026, sem publicação nem integração da tela. A limitação de ausência de recuperação continua válida para o aplicativo instalado. Throttle sequencial aprovado; concorrência entre conexões ainda não exercitada. Falhas/IDs não registrados no provedor não são recuperados por busca neste endpoint.

- 11/09/2026: 16 cenários PGlite e 90 testes v2 aprovados; não equivalem a teste ponta a ponta do Mercado Pago. Recuperação de aprovação sem webhook ainda pendente: leitura normal da cobrança consulta banco local e reconcileProvider é acionado pelo webhook. Não afirmar que atualizar a tela consulta automaticamente o provedor.


- Revisão 2.0.6 (histórico): o risco de ordem de locks então pendente foi corrigido pela migração 029 e exercitado posteriormente com duas conexões PostgreSQL reais. Isso não substitui a homologação ponta a ponta do provedor.
- Relatórios/métricas e persistência passaram em testes isolados; isso não substitui extração real autorizada e comparação de resultados nas duas máquinas. Não usar contatos reais para teste de disparo.

- Recuperação 2.0.5 exige o proprietário, OTP recente e o mesmo identificador de hardware do principal ativo. Mudança de hardware, vínculo removido ou principal bloqueado não são contornados por senha; exigem suporte/vínculo autorizado.
- A recuperação invalida o token anterior. Se a gravação local falhar, aguardar um minuto e repetir; nenhum prazo financeiro será prorrogado por isso. O Gerador Admin 2.0.4 continua compatível.

- CPF/CNPJ (2.0.4): validação de dígitos não verifica titularidade/situação cadastral em serviço externo. Não coletar documentos reais no chat, logs ou screenshots de suporte.
- As colunas legadas `cnpj`/`billing_cnpj` armazenam CPF ou CNPJ; integrações futuras não devem assumir 14 dígitos. Constraints 021 novas são NOT VALID para preservar legados; postflight de produção em 10/09/2026 encontrou zero documentos inválidos, mas VALIDATE CONSTRAINT não foi executado.
- Cadastro CPF foi testado com dados fictícios apenas no clone (rollback). Aceite de cadastro real, pagamento e duas máquinas ainda depende da homologação controlada pelo proprietário; não houve distribuição geral/OTA.

- Alterações no HTML, seletores, iframes ou fluxo do myHonda/Salesforce podem quebrar os extratores JavaScript.
- Sessões e cookies podem expirar, exigindo novo login do operador.
- QWebEngineView consome memória relevante quando vários navegadores ficam ativos simultaneamente.
- A rolagem virtual dos relatórios pode ocultar registros que ainda não foram renderizados no DOM.
- O WhatsApp Web muda frequentemente e pode exigir atualização dos seletores e rotinas de envio.
- Na 2.1.9, a exclusão de números confirmados sem WhatsApp é local ao computador, sem sincronização. Testes automatizados aprovados; validação operacional com WhatsApp real a cargo dos clientes, conforme autorizado pelo proprietário. O mesmo número não é reavaliado automaticamente se passar a ter WhatsApp posteriormente.
- Disparos rápidos ou repetitivos podem causar limitações ou bloqueio da conta usada.
- Limites configuráveis não eliminam as políticas antispam do WhatsApp. Lotes são sequenciais e devem ser usados somente com autorização dos destinatários; o teste real de lote está adiado porque a base disponível contém apenas contatos reais.
- O cálculo do link SSI depende da extração correta do modelo e do mapeamento da cilindrada.
- Atualizações ou reinstalações ainda devem preservar `app_data`. Os históricos JSON já usam gravação atômica e recusam sobrescrever arquivos inválidos, mas isso não substitui backup periódico.
- Credenciais, licenças e bancos locais não devem ser incluídos em builds, backups públicos ou pacotes de suporte.
- A aplicação é direcionada ao Windows e depende da compatibilidade entre Python, PyQt6-WebEngine, PyInstaller e a versão do Chromium embarcada.
- A migração 2.0 não pode ser publicada antes de validar o backfill de todas as empresas e licenças existentes.
- Empresas antigas não possuem necessariamente CNPJ ou e-mail de proprietário; esses dados devem ser coletados sem inventar valores.
- A versão 1.9.6 depende das tabelas de licença por instalação e deve continuar funcionando durante a transição.
- Boleto pode levar mais tempo para confirmação; a licença não pode ser liberada antes do webhook aprovado.
- Alterações de quantidade após pagamento valem para o ciclo seguinte; reembolso ou pró-rata não será automático na primeira fase.
- A confirmação empresarial por e-mail pressupõe que a caixa postal do usuário esteja protegida. Códigos devem expirar, ser de uso único e obedecer aos limites de reenvio do Supabase.
