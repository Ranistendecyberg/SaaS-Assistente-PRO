# Visão Geral do Sistema Desktop — Assistente PRO

O Assistente PRO é uma aplicação Desktop para Windows voltada às concessionárias Honda. Seu objetivo é automatizar a extração de dados do myHonda/Salesforce, organizar pesquisas de satisfação TSI (Oficina/Pós-Venda) e SSI (Vendas), gerar os links Medallia correspondentes e realizar os disparos pelo WhatsApp Web.

## Fluxo principal

1. Validar a licença vinculada ao equipamento.
2. Abrir o myHonda em navegadores Chromium incorporados à aplicação.
3. Manter a sessão autenticada por cookies locais.
4. Extrair filas e auditores SSI e TSI dos relatórios Salesforce.
5. Sanitizar e deduplicar clientes, telefones, OSs e propostas.
6. Converter IDs Salesforce de 15 para 18 caracteres e gerar links Medallia.
7. Montar filas de primeiro envio e de reenvio para não respondentes.
8. Enviar mensagens personalizadas pelo WhatsApp Web.
9. Persistir histórico local e alimentar os dashboards de satisfação.

## Arquitetura

- Interface Desktop em PyQt6.
- Navegadores embutidos com QWebEngineView.
- Extração por JavaScript injetado nas páginas do myHonda.
- Persistência local em SQLite e JSON.
- Dashboards e relatórios executados localmente.
- Empacotamento para Windows com PyInstaller e proteção por PyArmor.
- Instalador e mecanismo próprio de atualização.

Todo o desenvolvimento e as decisões futuras devem considerar exclusivamente esta versão Desktop.
