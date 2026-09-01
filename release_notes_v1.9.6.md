# SaaS Assistente PRO v1.9.6

Atualização corretiva urgente que substitui a v1.9.5.

## Correções

- Corrigido o erro de inicialização `DLL load failed while importing QtWebEngineWidgets`.
- Removidas do pacote DLLs externas de Poppler/libheif que substituíam componentes do Windows durante a carga do Qt WebEngine.
- Adicionado Assistente de Atualização independente: ele espera a instalação terminar e informa quando o usuário já pode abrir o sistema.
- O SaaS continua sem reinicialização automática após atualizar, evitando a falha anterior relacionada ao `python314.dll`.

## Observação

A v1.9.5 não deve mais ser distribuída. Computadores que não conseguem abrir essa versão precisam instalar a v1.9.6 manualmente.
