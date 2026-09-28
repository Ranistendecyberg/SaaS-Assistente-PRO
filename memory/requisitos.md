# Requisitos do Assistente PRO Desktop

- Desde a primeira janela visível da inicialização, mostrar a versão instalada no título para identificação em chamados de suporte, inclusive em primeiro acesso, licença vencida e erros de conexão.
- Na 2.1.10, usar uma única tela de ativação: a verificação passa a mostrar "Acesso liberado!", dias restantes e botão OK na própria janela, sem mensagem modal separada. Manter o primeiro acesso e as demais rotas como antes.

## Requisitos funcionais

- Recuperar acesso do principal já cadastrado mediante senha e OTP recente do proprietário; nunca criar licença, renovar validade, remover bloqueios ou transferir o principal por esse fluxo. Equipamento diferente usa vínculo autorizado de adicional.

1. Validar licença por identificador do equipamento, validade, concessionária, quantidade de lojas e módulos autorizados (TSI, SSI ou ambos).
2. Permitir login no myHonda/Salesforce pelo navegador incorporado e conservar a sessão em cache local.
3. Extrair em cadeia as filas SSI, TSI e os respectivos auditores.
4. Detectar tabelas carregadas dinamicamente, incluindo conteúdo em iframes, Shadow DOM e listas com rolagem virtual.
5. Aplicar filtros temporais adequados ao mês vigente, mês anterior e histórico. Nos dias 1, 2 e 3 de cada mês, os auditores SSI e TSI devem consultar o mês atual e o anterior; a partir do dia 4, devem consultar somente o mês atual.
6. Extrair dados de clientes, lojas, OSs/propostas, telefones, veículos, consultores/vendedores e links de pesquisa.
7. Sanitizar telefones brasileiros e sinalizar números inválidos ou fixos.
8. Impedir duplicidade de envio para a mesma OS ou proposta.
9. Converter IDs Salesforce de 15 para 18 caracteres.
10. Gerar links Honda SSI/TSI no formato validado em 28/09/2026: SSI em `cloud.motos.myhonda.com.br/ssi2w` com `e`, `Q1`, `Q2` em Base64 e `Q3` como cilindrada comercial do modelo; TSI em `cloud.motos.myhonda.com.br/tsi2w` com `e` e `Q1` em Base64. Usar e-mail da ficha, ID Salesforce de 18 caracteres e modelo SSI sem espaços em maiúsculas. Não fixar cilindrada em 160.
11. Substituir a montagem legada Medallia/feedless; não inventar e-mail, modelo ou cilindrada quando os dados estiverem ausentes ou ambíguos. A regra nova vale para envio individual e lote, sem permitir edição manual dos dados extraídos do myHonda. Implementada na 2.1.11 local, homologação real pendente; ver `links_honda_ssi_tsi_2026-09-28.md`. Diagnóstico autorizado permite gerar/copiar o link sem envio nem consumo de cota.
12. Criar filas de envio e reenvio, excluindo clientes que já responderam.
13. Permitir busca, seleção individual e personalização das mensagens com variáveis de cliente e link.
14. Permitir lotes sequenciais conforme limite por computador definido no Gerador Admin, mantendo um cliente por vez no navegador e respeitando a cota diária.
15. Registrar envios, respostas e falhas no armazenamento local.
16. Exibir dashboards TSI e SSI, Top2Box, médias, NPS/CSAT, rankings, comparativos, evolução diária e voz do cliente.
17. Cadastrar concessionárias, lojas, consultores e demais configurações operacionais.
18. Suportar instalação, atualização e backup dos dados locais no Windows.
19. Permitir conta de pessoa física (CPF) ou jurídica (CNPJ), com dígitos verificadores validados no cliente e servidor e documento único por unidade; manter computadores adicionais na mesma conta e cobrança consolidada.
20. Permitir usuários proprietário, administrador e operador com autorização no servidor.
21. Permitir um computador principal e computadores adicionais vinculados por código descartável.
22. Consolidar a cobrança da empresa em R$ 300,00 pelo primeiro computador e R$ 50,00 por adicional, salvo preço personalizado.
23. Permitir pagamento consolidado por PIX ou boleto e liberar somente após confirmação do provedor.
24. Permitir bloqueio imediato, remoção programada e transferência controlada da máquina principal.
25. Recuperar senha por e-mail verificado sem revelar se uma conta existe e sem expor senhas ao suporte.
26. Confirmar alterações empresariais sensíveis pelo código OTP enviado ao e-mail do usuário, sem exigir aplicativo autenticador no Desktop; manter TOTP nas mutações do Gerador Admin.

## Requisitos não funcionais

- A interface não deve travar durante carregamentos ou extrações.
- Os perfis de navegador do myHonda e WhatsApp devem permanecer isolados.
- Dados e sessões locais devem sobreviver a atualizações do aplicativo.
- Logs de falha devem permitir diagnóstico sem expor credenciais.
- O executável distribuído deve ser protegido e assinado quando possível.
- O Gerador Admin deve oferecer navegação agrupada por finalidade, rótulos autoexplicativos, hierarquia visual clara e contexto suficiente para que um administrador não técnico identifique a função de cada tela sem treinamento prévio.
