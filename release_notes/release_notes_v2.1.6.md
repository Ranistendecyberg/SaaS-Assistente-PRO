# SaaS Assistente PRO 2.1.6

## Correção do atualizador

- Corrigido o aviso `Failed to remove temporary directory: _MEI...` exibido após a atualização automática.
- O Assistente de Atualização agora é copiado para uma pasta independente antes de ser executado, evitando bloquear a pasta temporária do aplicativo antigo.
- O encerramento passa pelo fluxo normal do Qt e do navegador incorporado, permitindo liberar processos e bibliotecas antes da limpeza do PyInstaller.
- A verificação OTA agora começa com o loop principal da interface já ativo, garantindo que o fechamento solicitado pelo atualizador realmente encerre o aplicativo.

## Validação

- Testes novos verificam que o assistente não é executado de dentro da pasta `_MEI` e que o encerramento não usa mais saída forçada.
- Suíte completa aprovada com 206 testes.
- O hotfix mantém a correção da busca de clientes entregue na versão 2.1.5.

Esta atualização permanece opcional e foi preparada para validar novamente o processo automático, agora da versão 2.1.5 para a 2.1.6.
