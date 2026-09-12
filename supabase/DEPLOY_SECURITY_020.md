# Implantação controlada da revisão 2.0.3

Atualização posterior — revisão 2.0.4 (10/09/2026): suporte CPF/CNPJ publicado com migração 021, account-api v8 e billing-api v13. As proteções 020 e versões admin-api v9/desktop-api v8 permanecem. Postflight 021 e rejeição HTTP 401 nas funções atualizadas aprovados; cadastro autenticado pelo proprietário e homologação de pagamento/duas máquinas ainda pendentes. Ver release_notes_v2.0.4.md e memory/status_de_desenvolvimento.md para artefatos atuais.

Estado atualizado em 10/09/2026: backup lógico com restauração isolada de auth/public aprovado; migração 020 aplicada e funções billing-api (v12), admin-api (v9) e desktop-api (v8) publicadas no projeto v2 autorizado. Testes de rejeição sem credenciais/assinatura aprovados. Homologação autenticada, evento válido do provedor e duas máquinas ainda pendentes. O backend da versão 1.9.6 não foi alterado. Ver evidências em memory/status_de_desenvolvimento.md.

## Ordem

1. Conferir projeto Supabase v2 e obter backup recuperável. Inventariar faturas/tentativas pendentes no banco e pagamentos no provedor. Não exportar tokens para relatórios. Coordenar uma janela sem novas cobranças durante a mudança.
2. Confirmar migrações anteriores, inclusive 015, 018 e 019. Aplicar `migrations/020_v2_payment_snapshot_safety.sql` integralmente e confirmar COMMIT. Não reaplicar 019 depois de 020: os wrappers de segurança dependem dos helpers renomeados. Não usar reset do banco.
3. Publicar `billing-api`, `admin-api` e `desktop-api` a partir desta pasta v2. Utilizar `config.toml`: billing-api recebe webhook sem JWT no gateway, mas mantém validação de assinatura e autenticação das ações de usuário no código. Confirmar secrets existentes sem exibir seus valores.
4. No Mercado Pago, confirmar URL HTTPS terminada em `/functions/v1/billing-api?webhook=mercado_pago`, secret correspondente e eventos Payments (PIX via Payments API) e Orders (boleto via Orders API). O PIX novo envia notification_url explicitamente; cobranças antigas ainda dependem da configuração anterior. Não desativar a validação HMAC para contornar erros.
5. Conferir cobranças legadas antes de orientar novo pagamento. Não há backfill presumido de computadores: pagamento sem snapshot abre conferência e não renova automaticamente. Um QR salvo pelo cliente não deixa de existir apenas porque foi ocultado na tela. Cancelar/devolver valores somente com autorização e confirmação do provedor.
6. Após os critérios abaixo, homologar os executáveis de revisão e só então publicar o instalador/OTA. O Admin novo depende do backend novo para conferência de pagamentos. Guardar hashes e evidências de aceite na memory.

## Critérios de aceite obrigatórios

- Executar em PostgreSQL real com pgcrypto no schema extensions; PGlite usa digest simulado apenas para validar resolução de schema.
- Com duas conexões simultâneas, testar geração/vínculo/pagamento/alteração de preço em ambas as ordens de aquisição do bloqueio; verificar ausência de deadlocks e renovação indevida. Os testes isolados atuais são sequenciais.
- Conta controlada: gerar PIX, adicionar computador, pagar a cobrança anterior. Resultado esperado: conferência, sem liberar computador extra e sem renovar a assinatura por esse pagamento divergente.
- Testar substituição de computador mantendo quantidade, duplicação e atraso de webhook, valor divergente, bloqueio individual, PIX expirado e tentativa de boleto enquanto PIX pendente.
- Confirmar webhook válido aceito e inválido recusado; comparar valor e referência com consulta autenticada ao provedor. Não realizar pagamentos reais de clientes para homologação.
- Testar máquina adicionada após pagamento: vínculo permitido, licença bloqueada sem cobertura. O fluxo não calcula complemento proporcional neste release; não prometer liberação pagando QR antigo.
- Admin: editar cota de envios sem alterar vigência/status financeiro; consultar conferências. A ação de verificar reembolso exige proprietário/MFA e consulta o provedor: não emite reembolso. Quando confirmado, encerra a pendência e bloqueia o período atual devolvido.
- Abrir Desktop/Admin compilados, verificar login, QR, atualização de status e fechamento da janela em operação; concluir teste com máquina secundária. Testes Python não substituem esta homologação visual.

## Recuperação e pendências

Se um critério falhar, suspender distribuição e novas cobranças até análise; não remover snapshots/casos nem restaurar automaticamente funções 019, pois isso reabre a falha. Preparar correção aditiva com evidências e registrar na memory. Reembolsos já executados e pagamentos recebidos não são revertidos por rollback de código.

Pendências funcionais: transferência do computador principal, gestão completa de membros, efetivação de remoções agendadas e decisão comercial sobre complemento proporcional. Ver `memory/plano_de_implementacao.md`. Verificar licenças comerciais das ferramentas de empacotamento: os logs locais indicaram PyArmor trial/non-profits e Inno Setup non-commercial.

Referência primária: [Webhooks do Mercado Pago](https://www.mercadopago.com.br/developers/pt/docs/your-integrations/notifications/webhooks), consultada em 09/09/2026: configuração por pagamento tem prioridade sobre a configuração da aplicação; Payments e Orders possuem tópicos distintos.
