# Homologação de PIX e boleto

O sistema possui dois ensaios diferentes. Eles não devem ser misturados na
mesma empresa nem reutilizar uma tentativa de pagamento pendente.

## 1. Ambiente de teste do Mercado Pago

1. Crie uma empresa/conta exclusiva para homologação no SaaS.
2. Cadastre no Supabase os secrets `MERCADO_PAGO_TEST_ACCESS_TOKEN` e
   `MERCADO_PAGO_TEST_WEBHOOK_SECRET`. Nunca coloque esses valores no código,
   no executável, em SQL ou em mensagens.
3. Aplique a migração `031_v2_payment_test_environment.sql` e publique a
   `billing-api` correspondente.
4. No SQL Editor, substitua apenas o UUID e habilite a empresa por no máximo
   24 horas:

```sql
insert into public.billing_payment_test_companies(company_id, expires_at, reason)
values ('UUID-DA-EMPRESA-DE-TESTE', now() + interval '24 hours',
        'Homologação controlada PIX e boleto 2.1.8')
on conflict (company_id) do update
set expires_at = excluded.expires_at, reason = excluded.reason;
```

5. Configure no aplicativo de teste do Mercado Pago o webhook informado pela
   cobrança. A URL contém `environment=test`. PIX e boleto criados por essa
   empresa usam somente a credencial de teste.
6. Ao terminar, remova a autorização:

```sql
delete from public.billing_payment_test_companies
where company_id = 'UUID-DA-EMPRESA-DE-TESTE';
```

Tentativas já criadas mantêm o ambiente original de forma imutável. Não altere
uma empresa entre teste e produção enquanto existir cobrança pendente.

## 2. Ensaio real de R$ 1,00

Use outra empresa exclusiva, fora de `billing_payment_test_companies`. No
Gerador Admin, defina a mensalidade principal como R$ 1,00 e o adicional como
R$ 0,00 antes de gerar a primeira fatura. Confira que não existe fatura aberta
com o valor anterior.

O pagador deve ser diferente do titular vendedor da conta Mercado Pago. Para
boleto real, use dados verdadeiros e autorizados do pagador. Depois do teste,
confira a renovação, restaure os preços e encerre a conta de homologação. Não
faça esse ensaio em empresa ou licença de cliente.

## Evidências mínimas

- ambiente mostrado na tela (`TESTE` ou produção);
- método, valor, horário e código de suporte, sem registrar documento completo;
- QR/copia e cola do PIX ou linha do boleto exibidos;
- consulta manual reconhecendo o status;
- renovação ocorrendo uma única vez após confirmação;
- webhook inválido recusado e nenhuma credencial presente nos logs.
