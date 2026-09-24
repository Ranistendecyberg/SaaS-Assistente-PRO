# SaaS Assistente PRO 2.1.9

## Fila de reenvio: números sem WhatsApp

- Quando o WhatsApp confirma que um número é inválido ou não possui conta, o contato deixa de aparecer na fila de reenvio deste computador, inclusive após atualizar a lista ou reiniciar o sistema.
- Os dados extraídos do myHonda permanecem intactos. Não foi adicionada edição manual de telefone.
- A tentativa não é marcada como envio concluído e não consome a franquia de mensagens.
- Falhas temporárias de conexão ou de carregamento não excluem o contato da fila.
- Se uma nova extração do myHonda trouxer outro telefone, esse novo número poderá ser usado normalmente.
- Ajustada a normalização dos números nacionais com DDD 55.

## Validação

- Suíte automatizada aprovada: 239 testes.
- A validação operacional com o WhatsApp real será realizada pelos clientes após a atualização. Alterações futuras na interface do WhatsApp podem exigir novos ajustes.
- O registro de números indisponíveis é local a cada computador; não é sincronizado entre computadores.
