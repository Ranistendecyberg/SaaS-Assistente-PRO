# Regras de Negócio Consolidadas — Assistente PRO Desktop

## Objetivo

Automatizar no Windows a extração de clientes do myHonda/Salesforce, a geração de pesquisas Medallia TSI e SSI, o envio pelo WhatsApp Web e o acompanhamento das respostas e indicadores.

## TSI — Oficina/Pós-Venda

O relatório fornece dados como ID Salesforce, código da concessionária, ordem de serviço, chassi, cliente, e-mail e telefone.

Estrutura de referência do link:

`https://survey3.medallia.com/?tsi2&q1={ID_18}&w=2W`

A OS identifica o atendimento e deve ser usada no controle de duplicidade e no cruzamento com o auditor.

## SSI — Vendas

A fila fornece a relação de posse/proposta, data de início, cliente e chassi. Quando telefone, e-mail, modelo ou outros dados não estiverem presentes na tabela, o sistema deve abrir a ficha correspondente e extrair os campos adicionais.

Estrutura de referência do link:

`https://survey3.medallia.com/?SSI-2Wv2&Q1={ID_18}&Q2={MODELO_SEM_ESPACOS}&Q3={CILINDRADA}`

O link bruto deve ser aberto para obtenção da URL feedless da Medallia, que é a versão enviada ao cliente.

## Conversão do ID Salesforce

IDs de 15 caracteres recebem um sufixo de checksum de três caracteres, calculado a partir das letras maiúsculas de cada bloco de cinco posições. O resultado de 18 caracteres evita perda de diferenciação entre maiúsculas e minúsculas.

## Auditores e reenvio

Os auditores TSI e SSI informam quais clientes responderam. A fila de reenvio deve cruzar o histórico de disparos com essas respostas e incluir somente clientes ainda não respondentes dentro da janela configurada.

## Métricas TSI

Os cinco blocos principais são:

1. Infraestrutura.
2. Consultor.
3. Qualidade.
4. Entrega.
5. Custo/Benefício.

Top2Box representa a proporção de avaliações de excelência (notas 9 e 10). A média TSI considera a pontuação obtida em relação à pontuação máxima dos blocos. O sistema também mantém taxa de resposta, rankings, comparativos e voz do cliente.

## Interface Desktop

A aplicação possui menu lateral e telas para extração/fila, WhatsApp, dashboards, configurações de lojas e equipe, licença, tutorial e demais módulos operacionais. A interface deve exibir claramente o estado de login, sincronização, seleção, envio e auditoria.

## Persistência e segurança

O histórico de envios, configurações, licenças e dados dos dashboards é local. Builds, atualizações e reinstalações devem preservar `app_data` e os perfis de navegador necessários, sem expor credenciais ou dados de clientes.
