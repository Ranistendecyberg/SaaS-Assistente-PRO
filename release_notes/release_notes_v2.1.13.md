# SaaS Assistente PRO 2.1.13

- Corrigido o Top2Box do Relatório Gerencial Geral TSI para usar a pontuação oficial do myHonda, incluindo total, lojas, segmentos e consultores.
- Distribuição das respostas por loja e segmento apresenta respostas, TSI e Top2Box na tela e no relatório PDF.
- Corrigida a falha que podia encerrar o Relatório Gerencial Geral SSI ao receber uma nota ausente representada como NaN. Valores ausentes ou inválidos permanecem classificados como sem nota.
- Pagamento no aplicativo dos clientes exclusivamente por PIX. Boleto e dados do pagador são administrados pelo Gerador Admin; o servidor já aplica a separação.
- Uma fatura com boleto pendente mantém acompanhamento de confirmação e orientação de suporte, sem disponibilizar link/linha digitável nem permitir pagamento duplicado no aplicativo.

Os relatos de encerramento sem causa identificada ainda exigem o registro de erro do computador afetado. A correção de NaN resolve a condição reproduzida, sem garantir a eliminação de outras possíveis causas.

A emissão automática de NF e o campo de referência da NF no boleto não fazem parte desta atualização.
