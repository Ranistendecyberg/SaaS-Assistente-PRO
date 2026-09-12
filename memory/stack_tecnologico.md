# Stack Tecnológico — Assistente PRO Desktop

- Recuperação do principal 2.0.5: migração PLpgSQL 022 e account-api v9; autenticação Supabase Auth mais AMR OTP recente. Token aleatório de 32 bytes, hash SHA-256 no banco, credencial local protegida com DPAPI. Gerador Admin 2.0.4 compatível.

- Revisão CPF/CNPJ 2.0.4: validadores Python/TypeScript/PLpgSQL, PostgreSQL 17.11 para testes reais e migração 021; Deno check/test das funções. Backend publicado: account-api v8 e billing-api v13, com autenticação do usuário no código.

- **Linguagem:** Python 3.11+
- **Interface gráfica:** PyQt6
- **Navegador incorporado:** PyQt6-WebEngine / QWebEngineView (Chromium)
- **Automação do myHonda e WhatsApp:** JavaScript injetado com `runJavaScript`
- **Persistência local:** SQLite e arquivos JSON
- **Dashboards:** HTML/JavaScript e ECharts incorporados à interface
- **Documentos e relatórios:** geração e exportação local conforme os módulos existentes
- **Empacotamento:** PyInstaller
- **Proteção do executável:** PyArmor
- **Instalador Windows:** Inno Setup
- **Atualização:** atualizador Desktop próprio
- **Backend seguro/licenciamento:** Supabase PostgreSQL, Auth e Edge Functions
- **Cobrança 2.0 planejada:** Mercado Pago via servidor, com PIX, boleto e webhook idempotente

O sistema deve continuar operando localmente no Windows, preservando sessões dos navegadores, banco de dados e configurações do usuário.

O `venv` existente foi criado em outro perfil do Windows (`C:\Users\Berg`) e está inválido no ambiente atual. A versão 2.0 deve recriar um ambiente limpo usando o Python 3.14.5 instalado no perfil `WINDOWS`, sem incorporar DLLs dos runtimes auxiliares do Codex.
