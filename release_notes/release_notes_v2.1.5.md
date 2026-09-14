# SaaS Assistente PRO 2.1.5

## Correção

- Corrigida a busca na fila de clientes, que podia aparentar não aceitar digitação por exibir texto branco sobre fundo branco.
- O filtro passa a atualizar a lista imediatamente ao receber o texto digitado.
- A pesquisa por nome agora ignora diferenças entre letras maiúsculas, minúsculas, acentos e espaços repetidos.
- Mantida a separação da fila pelo tipo de pesquisa selecionado, SSI ou TSI.

## Validação

- Testes funcionais confirmam que uma busca sem acento, como `jose`, encontra nomes acentuados, como `JOSÉ`.
- Suíte completa aprovada com 203 testes.
- O executável empacotado e o instalador são submetidos ao teste de abertura e instalação limpa antes da publicação.

Esta atualização permanece opcional e foi preparada para validar o fluxo automático da versão 2.1.4 para a 2.1.5.
