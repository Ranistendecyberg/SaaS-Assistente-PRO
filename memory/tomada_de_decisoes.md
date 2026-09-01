# Tomada de Decisões Técnicas — Desktop

## PyQt6 e QWebEngineView

O sistema utiliza navegadores Chromium incorporados para que o operador faça login e para que a automação compartilhe a sessão autenticada do myHonda e do WhatsApp Web sem depender de navegador externo.

## Perfis separados de navegador

myHonda e WhatsApp usam perfis/cache separados. Isso evita mistura de cookies, armazenamento local e sessões entre os dois serviços.

## Extração por JavaScript injetado

As páginas do Salesforce carregam conteúdo dinamicamente. A extração percorre documento principal, iframes, Shadow DOM e tabelas virtuais, monitorando o carregamento antes de processar os registros.

## Conversão Salesforce 15 → 18

O checksum é calculado localmente para preservar a identificação case-sensitive dos registros em links e integrações externas.

## Persistência local

SQLite armazena registros estruturados e histórico; JSON é usado para configurações e estados auxiliares. Atualizações devem preservar esses arquivos.

## Deduplicação

OS no TSI e proposta/relação de posse no SSI são as chaves operacionais usadas para impedir disparos repetidos.

## Envio individual pelo WhatsApp

O envio em lote foi desativado por decisão de produto. A fila permite somente uma pesquisa marcada por vez, sem a opção "Selecionar Todos", e o envio individual existente no Motor WhatsApp permanece desabilitado para evitar associação com uma conversa diferente. O operador deve conversar com o cliente, obter sua autorização e iniciar o envio pela lista de clientes.

## Distribuição Windows

PyInstaller gera o executável, PyArmor protege o código distribuído e Inno Setup produz o instalador. O atualizador deve substituir somente arquivos da aplicação, preservando dados do usuário.

## Conta empresarial e sublicenças — versão 2.0

Não serão usadas chaves de sublicença livremente transferíveis. A empresa terá um computador principal e computadores adicionais vinculados ao UUID da empresa e a uma unidade/CNPJ. O vínculo exige usuário autenticado e código descartável de 24 horas.

A cobrança será consolidada por empresa: R$ 300,00 pelo primeiro computador e R$ 50,00 por cada computador adicional. Computadores contam individualmente mesmo quando compartilham CNPJ. Valores personalizados antigos serão preservados até alteração explícita.

Permissão de usuário e classificação de computador são conceitos separados. Os papéis serão proprietário, administrador e operador; somente o proprietário poderá transferir a máquina principal.

PIX e boleto representarão tentativas de pagamento de uma fatura empresarial única. A liberação ocorrerá somente após webhook confirmado pelo provedor, nunca pela simples geração do pagamento.

## Isolamento físico da versão 2.0

A versão 1.9.6 permanece congelada em `C:\SaaS - Codex\Saas`. A versão 2.0 será desenvolvida exclusivamente em `C:\SaaS - Codex\SaaS-Desktop-v2`, com Git e Supabase próprios. Não compartilhar `app_data`, bancos, sessões, builds, ambientes Python ou credenciais entre essas pastas.
