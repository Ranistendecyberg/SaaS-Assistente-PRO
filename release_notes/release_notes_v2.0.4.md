# Revisão 2.0.4 — CPF e CNPJ

- Nova conta para pessoa física ou jurídica: nome do titular/empresa e CPF ou CNPJ.
- Verificação de dígitos no Desktop, nas funções e no banco; documento duplicado não gera outro cadastro de teste.
- Perfil de cobrança aceita ambos os documentos; boleto informa CPF ou CNPJ ao provedor.
- Conta Empresarial e Gerador Admin exibem CPF/CNPJ; busca Admin aceita CPF.
- Compatibilidade com cadastros CNPJ preservada. Nomes técnicos de campos legados mantidos.
- Requer migração 021 e account-api/billing-api atualizadas, publicadas em 10/09/2026.
- Sem mudança na proteção PIX/snapshot da migração 020, nos preços ou na confirmação de e-mail.

Validação matemática não comprova titularidade ou situação cadastral. Pagamento real, fluxo autenticado e homologação com dois computadores ainda precisam de aceite; não houve distribuição OTA.
