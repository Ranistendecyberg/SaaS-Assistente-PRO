# Requisitos do Assistente PRO Desktop

## Requisitos funcionais

1. Validar licença por identificador do equipamento, validade, concessionária, quantidade de lojas e módulos autorizados (TSI, SSI ou ambos).
2. Permitir login no myHonda/Salesforce pelo navegador incorporado e conservar a sessão em cache local.
3. Extrair em cadeia as filas SSI, TSI e os respectivos auditores.
4. Detectar tabelas carregadas dinamicamente, incluindo conteúdo em iframes, Shadow DOM e listas com rolagem virtual.
5. Aplicar filtros temporais adequados ao mês vigente, mês anterior e histórico.
6. Extrair dados de clientes, lojas, OSs/propostas, telefones, veículos, consultores/vendedores e links de pesquisa.
7. Sanitizar telefones brasileiros e sinalizar números inválidos ou fixos.
8. Impedir duplicidade de envio para a mesma OS ou proposta.
9. Converter IDs Salesforce de 15 para 18 caracteres.
10. Gerar links Medallia TSI e SSI, incluindo modelo e cilindrada quando exigidos.
11. Obter o link feedless da Medallia quando necessário.
12. Criar filas de envio e reenvio, excluindo clientes que já responderam.
13. Permitir busca, seleção individual e personalização das mensagens com variáveis de cliente e link.
14. Enviar mensagens pelo WhatsApp Web para somente um cliente por operação, sem seleção em massa.
15. Registrar envios, respostas e falhas no armazenamento local.
16. Exibir dashboards TSI e SSI, Top2Box, médias, NPS/CSAT, rankings, comparativos, evolução diária e voz do cliente.
17. Cadastrar concessionárias, lojas, consultores e demais configurações operacionais.
18. Suportar instalação, atualização e backup dos dados locais no Windows.
19. Organizar matriz e filiais em uma única conta empresarial, com CNPJ por unidade.
20. Permitir usuários proprietário, administrador e operador com autorização no servidor.
21. Permitir um computador principal e computadores adicionais vinculados por código descartável.
22. Consolidar a cobrança da empresa em R$ 300,00 pelo primeiro computador e R$ 50,00 por adicional, salvo preço personalizado.
23. Permitir pagamento consolidado por PIX ou boleto e liberar somente após confirmação do provedor.
24. Permitir bloqueio imediato, remoção programada e transferência controlada da máquina principal.
25. Recuperar senha por e-mail verificado sem revelar se uma conta existe e sem expor senhas ao suporte.

## Requisitos não funcionais

- A interface não deve travar durante carregamentos ou extrações.
- Os perfis de navegador do myHonda e WhatsApp devem permanecer isolados.
- Dados e sessões locais devem sobreviver a atualizações do aplicativo.
- Logs de falha devem permitir diagnóstico sem expor credenciais.
- O executável distribuído deve ser protegido e assinado quando possível.
