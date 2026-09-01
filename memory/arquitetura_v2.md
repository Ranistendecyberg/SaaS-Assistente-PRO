# Arquitetura da versão 2.0 — Conta Empresarial

## Objetivo

A versão 2.0 substitui gradualmente a cobrança isolada por computador por uma conta empresarial consolidada, sem interromper a versão 1.9.6 nem apagar licenças existentes.

## Hierarquia

1. **Empresa:** contrato e cobrança consolidados.
2. **Unidades:** matriz e filiais, cada uma identificada por CNPJ.
3. **Usuários:** proprietário, administrador e operador.
4. **Computadores:** um principal e zero ou mais adicionais, associados a uma unidade.
5. **Assinatura:** uma cobrança por empresa, calculada pela quantidade de computadores faturáveis.

## Regras comerciais aprovadas

- Novo contrato: computador principal por R$ 300,00 ao mês.
- Cada computador adicional: R$ 50,00 ao mês, inclusive quando usa o mesmo CNPJ.
- Matriz e filiais fazem parte da mesma cobrança consolidada.
- Preços personalizados já existentes serão preservados na migração e só mudarão por uma ação administrativa explícita.
- Computador bloqueado ou com remoção agendada continua faturável até o encerramento do período já contratado.
- Computador removido deixa a fatura seguinte.
- A máquina principal só pode ser transferida pelo proprietário da conta.

## Segurança e acesso

- A identidade do grupo é o UUID da empresa; nomes e CNPJs não são usados sozinhos para autorizar vínculos.
- Códigos para vincular computador são descartáveis, válidos por 24 horas e armazenados somente como hash.
- Permissões pertencem ao usuário, não ao computador.
- Proprietário: faturamento, usuários, unidades, computadores e transferência da máquina principal.
- Administrador: gestão operacional de usuários, unidades e computadores, sem transferência de propriedade.
- Operador: uso operacional do Desktop, sem gestão contratual.
- Toda autorização sensível deve ser verificada nas Edge Functions, mesmo quando o botão estiver oculto na interface.
- Recuperação de senha será feita pelo Supabase Auth por e-mail verificado; o administrador nunca terá acesso à senha do cliente.

## Cobrança

- Uma fatura por empresa e período.
- O valor é congelado na fatura: preço base + quantidade adicional × preço adicional.
- PIX e boleto são tentativas de pagamento da mesma fatura, evitando cobranças duplicadas.
- Confirmação somente por webhook validado do provedor.
- Token do Mercado Pago permanece exclusivamente no servidor.
- Alteração de computadores antes do pagamento cancela e recalcula a fatura aberta; depois do pagamento, vale para o ciclo seguinte.

## Compatibilidade

- `licenses` e `payment_sessions` permanecem disponíveis para a versão 1.9.6 durante a transição.
- A migração 2.0 cria assinaturas empresariais sem remover registros antigos.
- Empresas antigas recebem uma unidade matriz provisória sem CNPJ inventado.
- O primeiro computador existente de cada empresa é classificado como principal.
- O onboarding 2.0 solicitará dados ausentes e criação do proprietário, sem refazer o cadastro inteiro.

## Sequência de implantação

1. Validar a migração e regras comerciais localmente.
2. Implementar autenticação e onboarding 2.0 nas Edge Functions.
3. Implementar telas Empresa e Computadores no Desktop.
4. Implementar gestão e suporte no Gerador Admin.
5. Integrar Mercado Pago em ambiente de teste.
6. Testar migração com cópia anonimizada da estrutura.
7. Gerar 2.0.0-beta para os computadores de teste.
8. Somente após aceite, migrar produção e publicar 2.0.0.
