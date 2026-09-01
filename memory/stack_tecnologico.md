# Stack Tecnológico — Assistente PRO Desktop

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
