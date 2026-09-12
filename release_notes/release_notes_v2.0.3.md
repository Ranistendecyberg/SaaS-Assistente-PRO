# Assistente PRO 2.0.3 — revisão de segurança

- Cobranças vinculadas aos computadores da emissão. PIX antigo não renova máquinas adicionadas ou substituídas.
- Máquinas vinculadas depois do pagamento aguardam cobertura na cobrança empresarial; não herdam um período já pago.
- Pagamentos divergentes e reembolsos aparecem em uma lista de conferência no Admin, sem liberação automática.
- Bloqueios individuais e remoções agendadas preservados nos ajustes empresariais.
- Ajustar limites de mensagens não renova nem ativa a licença. Preço e vigência empresariais têm local único de edição.
- QR expirado, cancelado ou inválido é ocultado. Consulta periódica de status e mensagens de orientação.
- Geração de PIX legada por instalação desativada no backend v2.

## Implantação necessária

Aplicar `supabase/migrations/020_v2_payment_snapshot_safety.sql` após a 019, depois publicar `billing-api`, `admin-api` e `desktop-api` usando a pasta v2. A configuração `verify_jwt=false` da billing-api é necessária para o webhook HMAC.

Cobranças anteriores sem snapshot não podem ser consideradas automaticamente seguras. Conferir recebimentos existentes e cancelar no provedor as cobranças antigas ainda pagáveis antes de orientar nova emissão. Um recebimento divergente bloqueia novas cobranças até sua conciliação.

Ainda exige homologação no Supabase, webhook real de teste, concorrência entre conexões e teste físico em dois computadores. Não publicado nem oferecido via OTA por esta revisão.
