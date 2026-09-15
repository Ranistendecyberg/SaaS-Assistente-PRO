# SaaS Assistente PRO 2.1.7

## Diagnóstico seguro do envio pelo WhatsApp

- Adicionado um teste controlado na tela do WhatsApp, com número e mensagem definidos pelo responsável.
- O teste fica disponível somente quando o diagnóstico detalhado por 24 horas estiver autorizado na licença.
- O painel permanece completamente oculto no uso normal e só aparece após `Ctrl+Shift+D`, autorização temporária do computador e validação da senha administrativa.
- A senha passou a usar derivação PBKDF2 e comparação em tempo constante; cinco tentativas incorretas bloqueiam o acesso por 15 minutos.
- A mesma autorização temporária e proteção contra tentativas foi aplicada às abas internas dos robôs.
- O teste não utiliza a fila de pesquisas, não marca clientes como enviados e não consome a franquia de mensagens.
- A telemetria técnica registra somente referências anônimas e estados operacionais; número e conteúdo da mensagem não são enviados.

## Confirmação real do disparo

- O sistema deixou de considerar que uma mensagem foi enviada apenas porque o clique foi disparado.
- Depois do clique, o WhatsApp é consultado novamente e o envio somente é confirmado quando o campo de composição fica vazio.
- Se a mensagem permanecer como rascunho, a pesquisa não é marcada como enviada, a reserva de franquia é liberada e a falha fica registrada para diagnóstico.
- A comparação do texto tolera diferenças de espaços, quebras de linha e normalização Unicode.
- A navegação não depende mais da igualdade literal da URL, que pode ser normalizada pelo WhatsApp Web.

## Validação

- Foram adicionados testes para normalização do número de teste, separação completa entre diagnóstico e lote e bloqueio do falso sucesso após o clique.
- Suíte completa aprovada com 212 testes.

Esta versão deve ser validada primeiro com um único envio para número próprio ou autorizado antes de qualquer disparo real em lote.
