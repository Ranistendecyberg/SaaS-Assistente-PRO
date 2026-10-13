# SaaS Assistente PRO 2.1.16

- Corrigido o fechamento do aplicativo ao abrir Relatório/Dashboard quando uma meta de loja está vazia, inválida ou não finita na configuração local. Esses valores passam a ser tratados como zero.
- Protegida também a criação inicial das abas de dashboard. Se ocorrer outra falha durante a abertura, o sistema permanece aberto, mostra um código de diagnóstico e permite tentar novamente.
- Mantém os recursos e correções da versão 2.1.15.

Se o problema persistir, informe o código de diagnóstico e envie `app_data/dashboard_errors.log`.
