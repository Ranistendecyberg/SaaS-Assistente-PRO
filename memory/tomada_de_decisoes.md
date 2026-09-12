# Tomada de Decisões Técnicas — Desktop

## Escopo de pagamento confirmado — 11/09/2026

- Manter PIX em Payments API, sem cartão e sem migrar para Orders apenas para pontuação. Boleto permanece separado, sem autorização de remoção.
- Teste Orders realizado pelo usuário com credencial de teste aprovou pagamento simulado e recebeu nota 14/100; não representa o fluxo PIX do SaaS nem homologação completa. Não registrar credenciais, senha ou OTP na memória.
- Manter principal e adicional; não remover máquinas para alterar cobrança. Priorizar recuperação segura de status, idempotência e composição imutável da fatura.


## Segurança de cobrança — revisão 09/09/2026

Cada tentativa guarda uma cópia imutável dos IDs de máquinas, valor e período. Mudanças de composição ou preço impedem renovar usando a cobrança antiga, inclusive substituições com a mesma quantidade. Emissão, resgate e confirmação usam o bloqueio da assinatura no banco. Código de vínculo é revalidado contra o papel atual do emissor.

Máquinas adicionadas após um período pago ficam sem acesso até cobertura por cobrança empresarial. Não foi implementado pró-rata nem cobrança diferencial automática; esta regra evita herdar acesso pago por outras máquinas. Trial sem pagamento anterior conserva a regra existente.

Recebimentos divergentes ficam registrados para conciliação; nunca são transformados em renovação silenciosa. O Admin pode confirmar um reembolso integral já realizado, consultando o provedor com MFA e papel owner. A ação não solicita reembolso. Se o período atual foi reembolsado, a assinatura fica pendente e as licenças são bloqueadas. Crédito manual/reembolso parcial não são automatizados.

Alterações individuais de envios e comunicação não enviam status, tipo, preço ou vencimento. Assinaturas empresariais são ajustadas na área Por empresa. Bloqueios operacionais e agendamento de remoção são preservados. A exclusão física da máquina empresarial foi impedida para preservar o histórico financeiro.

## PyQt6 e QWebEngineView

O sistema utiliza navegadores Chromium incorporados para que o operador faça login e para que a automação compartilhe a sessão autenticada do myHonda e do WhatsApp Web sem depender de navegador externo.

## Perfis separados de navegador

myHonda e WhatsApp usam perfis/cache separados. Isso evita mistura de cookies, armazenamento local e sessões entre os dois serviços.

## Extração por JavaScript injetado

As páginas do Salesforce carregam conteúdo dinamicamente. A extração percorre documento principal, iframes, Shadow DOM e tabelas virtuais, monitorando o carregamento antes de processar os registros.

## Conversão Salesforce 15 → 18

O checksum é calculado localmente para preservar a identificação case-sensitive dos registros em links e integrações externas.

## Persistência local

SQLite armazena registros estruturados e histórico; JSON é usado para configurações e estados auxiliares. Atualizações devem preservar esses arquivos.

## Deduplicação

OS no TSI e proposta/relação de posse no SSI são as chaves operacionais usadas para impedir disparos repetidos.

## Envio individual pelo WhatsApp

Em 04/09/2026 o proprietário autorizou lotes configuráveis por licença. O padrão continua sendo um cliente; o Gerador Admin define `batch_limit` e `daily_message_limit`. Lotes são sequenciais, preservando intervalos e a autorização do cliente, nunca envios simultâneos no mesmo navegador. Mensagens extras mantêm a regra legada e não são confundidas com a cota diária recorrente.

## Distribuição Windows

PyInstaller gera o executável, PyArmor protege o código distribuído e Inno Setup produz o instalador. O atualizador deve substituir somente arquivos da aplicação, preservando dados do usuário.

## Conta empresarial e sublicenças — versão 2.0

Não serão usadas chaves de sublicença livremente transferíveis. A empresa terá um computador principal e computadores adicionais vinculados ao UUID da empresa e a uma unidade/CNPJ. O vínculo exige usuário autenticado e código descartável de 24 horas.

A cobrança será consolidada por empresa: R$ 300,00 pelo primeiro computador e R$ 50,00 por cada computador adicional. Computadores contam individualmente mesmo quando compartilham CNPJ. Valores personalizados antigos serão preservados até alteração explícita.

Permissão de usuário e classificação de computador são conceitos separados. Os papéis serão proprietário, administrador e operador; somente o proprietário poderá transferir a máquina principal.

PIX e boleto representarão tentativas de pagamento de uma fatura empresarial única. A liberação ocorrerá somente após webhook confirmado pelo provedor, nunca pela simples geração do pagamento.

## Escalabilidade incremental sem migração destrutiva — 11/09/2026

Preservar JSON como formato local nesta revisão para não arriscar históricos instalados. Caches passam a observar alterações entre instâncias por assinatura de arquivo, e índices derivados são invalidados junto com a origem. A futura migração para SQLite exige importação reversível e comparação de métricas.

Rotinas recorrentes do backend pertencem a RPCs set-based, transacionais, limitadas por lote e restritas a service-role. A Edge Function apenas agenda/orquestra. Transferência do principal mantém ordem de locks assinatura → instalações e continua owner-only no fluxo do cliente.

## Isolamento de dados locais da versão 2.0

A versão 2.0 utiliza `%APPDATA%\\SaasAssistentePRO-v2`, separada de `%APPDATA%\\SaasAssistentePRO` da versão 1.9.6. Sessões Supabase, tokens de instalação, configurações e dados de teste do beta não podem sobrescrever o ambiente estável. A transferência inicial de dados deve ocorrer por cópia/migração explícita e nunca por compartilhamento permanente da mesma pasta.

## Isolamento físico da versão 2.0

A versão 1.9.6 permanece congelada em `C:\SaaS - Codex\Saas`. A versão 2.0 será desenvolvida exclusivamente em `C:\SaaS - Codex\SaaS-Desktop-v2`, com Git e Supabase próprios. Não compartilhar `app_data`, bancos, sessões, builds, ambientes Python ou credenciais entre essas pastas.

## Confirmação de operações empresariais por e-mail

Usuários do Desktop não serão obrigados a instalar aplicativo autenticador. Alterações empresariais protegidas exigem um código OTP enviado ao e-mail da própria sessão autenticada. O código é de uso único, não cria usuários, não é persistido localmente e autoriza a sessão por até 12 horas.

Gerar PIX ou boleto não exige uma nova confirmação, pois a tentativa é idempotente e a renovação depende exclusivamente do webhook validado do Mercado Pago. O proprietário continua sendo o único perfil autorizado a salvar dados de cobrança e gerar pagamentos. O TOTP permanece obrigatório somente nas mutações do Gerador Admin.

## Experiência visual do Gerador Admin 2.0

O Gerador Admin adota a mesma linguagem visual clara e baseada em cartões da Conta Empresarial. A navegação deve ser organizada pelo objetivo do administrador, com nomes autoexplicativos e separação entre gestão de clientes e ferramentas do sistema. Indicadores gerais aparecem apenas quando oferecem contexto útil para a área aberta; telas operacionais não devem repetir painéis que desviem a atenção da tarefa principal.

As gestões por computador e por empresa permanecem separadas porque possuem alcances diferentes, mas devem funcionar como fluxos conectados. A primeira concentra ajustes individuais; a segunda concentra assinatura e cobrança consolidadas. Funções rápidas sobre um computador podem continuar na visão empresarial, desde que o alcance seja informado e exista um atalho que preserve a seleção ao abrir os ajustes completos da máquina.

## Reserva atômica da cota de mensagens

Cada envio automático reserva uma unidade no servidor antes de abrir/clicar no WhatsApp. Sucesso confirma a reserva; falhas normais de navegação, validação ou envio a liberam e devolvem a cota. Uma interrupção ambígua exatamente após o clique permanece contabilizada por segurança, pois o Desktop não consegue provar que o WhatsApp deixou de enviar. O fluxo legado `consume_message` permanece temporariamente disponível apenas para compatibilidade com builds antigos.

## Ativação de computador adicional sem credenciais

O computador principal autoriza o novo equipamento por um código curto, temporário e de uso único. O computador adicional não recebe nem solicita e-mail, senha ou MFA do proprietário. A segurança fica concentrada no servidor: autorização de proprietário/administrador na geração, prazo de 15 minutos, hash do código, limitação de geração e tentativas, vínculo ao hardware e auditoria. Ações empresariais mais sensíveis continuam usando confirmação por e-mail.

Como nenhuma instalação da versão 2.0 foi distribuída, o contrato antigo de vínculo da própria 2.0 não será mantido em paralelo. O lançamento usa somente o fluxo simplificado; a versão 1.9.6 continua isolada e inalterada.

## Atualização com reabertura automática

Após a confirmação do usuário, o Desktop baixa o instalador por HTTPS, valida o SHA-256 e encerra. Um assistente independente aguarda a saída, instala silenciosamente, abre a nova versão automaticamente e termina. O caminho de sucesso não cria uma caixa de confirmação adicional; somente falhas exigem intervenção do usuário.
# Cadastro CPF/CNPJ — 10/09/2026

- Suporte solicitado pelo proprietário. Identificação automática pelo documento (11 dígitos CPF, 14 CNPJ), sem exigir empresa de pessoa física. Nomes legados `cnpj`, `billing_cnpj` e argumento RPC mantidos por compatibilidade; não são documentos fictícios ou preenchidos com zeros.
- Migração aditiva 021 mantém índices únicos, valida checksum no banco e serializa onboarding pelo usuário Auth. Constraints novas NOT VALID preservam documentos legados sem reescrita; novas inserções/atualizações são verificadas. Auditoria dos legados antes de VALIDATE CONSTRAINT permanece necessária.
- Pagador de boleto recebe tipo CPF/CNPJ correto conforme documento; referência oficial consultada: https://www.mercadopago.com.br/developers/pt/docs/checkout-api-orders/payment-integration/boleto (10/09/2026). Nenhuma cobrança real de teste.
- Validação matemática não verifica identidade/titularidade nem situação cadastral. Regras de licença e snapshots 020 permanecem inalteradas.
# Recuperação do principal — 10/09/2026

- Recuperação autentica proprietário com senha e OTP recente (10 minutos), verifica hardware existente e rotaciona exclusivamente credencial da instalação. O token antigo deixa de funcionar; em falha de gravação local, permitir nova tentativa após 1 minuto, sem voltar ao token antigo.
- Fingerprint de hardware é identificador de software, não atestação física; por isso não substitui autenticação e confirmação de e-mail. Troca de hardware/conta ou principal bloqueado requer suporte, sem reassociação automática.
- Ordem de locks: assinatura, membro e instalação. Não toca nas rotinas financeiras 020/021. Logs de auditoria não armazenam senha, OTP nem token recuperado.
# Revisão Admin/usabilidade — 10/09/2026

- Operações de bloqueio/desbloqueio testadas somente em fixtures revertidas no clone para não interromper os dois equipamentos ativos do proprietário.
- Banner passa a reservar largura expansível para o nome/metadados; testes reproduziram largura 0 no layout anterior.
- UI distingue estado local de confirmação do provedor: ocultar QR ou payable=false não prova cancelamento no Mercado Pago. Fatura paga também não implica que a vigência atual acabou de ser renovada.
- Revisão 2.0.6 contém apenas alterações Desktop; sem migração, nova publicação Edge ou mudança do executável Admin. Testes de concorrência e validação funcional real permanecem separados dos testes unitários/sequenciais.
