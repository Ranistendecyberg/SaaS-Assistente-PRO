# SaaS Assistente PRO 2.0.7

- Novo botão na cobrança: **Já paguei — consultar Mercado Pago** (proprietário).
- Consulta o provedor para recuperar status quando a notificação não chegou; não gera outra cobrança e não faz pagamentos.
- Após consultar, recarrega a fatura. Se houver divergência, mantém conferência sem prometer desbloqueio ou renovação.
- Limite compartilhado de uma consulta por cobrança a cada 30 segundos; outra conta não pode consultar essa tentativa.
- Mantidos PIX via Payments e boleto via Orders; nenhum pagamento por cartão adicionado.

Backend: migração 023 e billing-api v14. Admin 2.0.4 preservado.
Testes: 93 Desktop, 17 SQL PGlite e 13 handler simulado aprovados; migração/teste de recuperação aprovados no PostgreSQL real local. ACL e 401 sem autenticação conferidos em produção.

Pendentes: aceite do instalador e consulta autenticada pelo proprietário, entrega externa de webhook e concorrência financeira. Não pagar apenas para testar; não usar QR antigo. Nenhuma publicação OTA automática.
