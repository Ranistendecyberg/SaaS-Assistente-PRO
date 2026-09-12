# Revisão 2.0.6 — Identificação da conta e mensagens de cobrança

- Corrige nome e identificação invisíveis no banner da Conta Empresarial.
- Diferencia avisos de cobrança paga, cancelada no sistema, expirada, recusada, devolvida e indisponível sem motivo específico.
- Não afirma cancelamento no Mercado Pago apenas porque o servidor ocultou o código.
- Sem alteração de preços, licenças, vínculos, snapshots ou rotinas financeiras. Não requer nova migração ou publicação Edge.
- Gerador Admin 2.0.4 permanece compatível. Testes sequenciais em clone confirmaram bloqueio/desbloqueio do adicional sem renovar validade, com principal preservado e recusa de assinatura vencida.

Ainda pendentes: teste financeiro com evento válido do provedor, concorrência real e homologação funcional das operações diárias. Não pagar o PIX antigo durante a conferência.
