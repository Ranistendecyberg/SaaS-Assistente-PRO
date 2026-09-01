# Plano de Implementação — Assistente PRO Desktop

## Prioridade 1 — Estabilidade operacional

- Validar o fluxo completo de login e extração SSI/TSI.
- Consolidar seletores e parsers dos relatórios myHonda.
- Garantir que timeouts, recargas e relatórios vazios não travem a interface.
- Validar deduplicação, histórico e preservação dos dados locais.

## Prioridade 2 — Filas e WhatsApp

- Revisar a formação das filas de primeiro envio e reenvio.
- Confirmar exclusão automática dos clientes já respondidos.
- Validar templates, variáveis, seleção de clientes e sanitização de telefones.
- Testar disparo, pausas, retomada, cancelamento e registro de falhas no WhatsApp Web.

## Prioridade 3 — Auditores e dashboards

- Validar extrações dos auditores TSI e SSI com páginas reais.
- Conferir cálculos de Top2Box, médias, NPS/CSAT e taxa de resposta.
- Validar filtros por data, loja, categoria, consultor e vendedor.
- Revisar rankings, gráficos diários e voz do cliente.

## Prioridade 4 — Distribuição

- Executar testes automatizados e testes manuais de regressão.
- Limpar arquivos temporários e separar dados do usuário dos arquivos da aplicação.
- Gerar build protegido, instalador e pacote de atualização.
- Testar instalação limpa e atualização preservando `app_data`.

## Versão 2.0 — Conta empresarial

- [x] Criar backup físico da base estável 1.9.6.
- [x] Definir hierarquia empresa, unidades, usuários, computadores e assinatura.
- [x] Criar migração local, sem publicação, preservando tabelas da 1.9.6.
- [x] Isolar e testar o cálculo R$ 300,00 + R$ 50,00 por adicional.
- [ ] Revisar a migração em banco de teste e validar o backfill.
- [ ] Implementar autenticação do proprietário, administradores e operadores.
- [ ] Implementar onboarding de clientes existentes sem recadastro integral.
- [ ] Implementar vínculo de computador adicional por código descartável.
- [ ] Implementar tela Empresa e Computadores no Desktop.
- [ ] Implementar gestão correspondente no Gerador Admin.
- [ ] Implementar fatura consolidada e escolha PIX/boleto.
- [ ] Integrar Mercado Pago e webhook idempotente em ambiente de teste.
- [ ] Testar remoção, bloqueio e transferência da máquina principal.
- [ ] Gerar e validar 2.0.0-beta em dois computadores.
- [ ] Publicar 2.0.0 somente após aceite formal dos testes.
