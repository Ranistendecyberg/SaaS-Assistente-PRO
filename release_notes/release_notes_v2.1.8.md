# SaaS Assistente PRO 2.1.8

## Correção do atualizador em redes corporativas

- Corrigida a falha `CERTIFICATE_VERIFY_FAILED` que podia impedir o download da atualização em computadores de concessionárias e outras redes corporativas.
- O atualizador agora usa o conjunto público de autoridades certificadoras incluído no aplicativo e também os certificados confiáveis instalados no Windows.
- Redes que utilizam inspeção HTTPS com uma autoridade corporativa reconhecida pelo Windows passam a ser atendidas sem desativar a segurança da conexão.
- A validação do certificado HTTPS, do nome do servidor e do SHA-256 oficial do instalador permanece obrigatória.

## Correção do reconhecimento do computador principal

- Corrigida a leitura do UUID do Windows, que em versões anteriores podia recorrer indevidamente ao endereço de rede e deixar de reconhecer o mesmo computador após mudança de Wi-Fi, VPN ou driver.
- O vínculo já protegido no Windows passa a ser preservado mesmo quando a detecção do equipamento varia.
- Contas afetadas podem recuperar o computador principal com o login do proprietário e a confirmação por e-mail; o servidor migra apenas identificadores legados e mantém a mesma licença, validade, cobrança e quantidade de computadores.
- A migração é auditada, não cria um novo teste ou licença e não libera computadores bloqueados.

## Homologação segura de PIX e boleto

- Adicionado ambiente financeiro de teste selecionado exclusivamente pelo servidor e autorizado por empresa por prazo limitado.
- Tentativas de teste e de produção ficam identificadas de forma imutável e usam credenciais e assinaturas de webhook separadas.
- A tela informa claramente quando uma cobrança não movimenta dinheiro real.
- A consulta de pagamento agora informa o estado da operação e diferencia corretamente PIX de boleto nas mensagens e ações disponíveis.
- O boleto de teste usa um pagador fictício próprio do ambiente de homologação e apresenta a linha digitável e o documento emitido pelo Mercado Pago.
- Cobranças de homologação podem ser canceladas com segurança sem afetar pagamentos ou licenças de produção.
- Recusas do Mercado Pago passam a fornecer um motivo técnico e um código seguro para o suporte, sem expor credenciais ou dados pessoais.
- O modo desenvolvedor agora distingue corretamente a ausência de autorização temporária de uma falha real de conexão.

## Validação

- Conexão HTTPS real com o instalador oficial no GitHub aprovada, incluindo o redirecionamento para o servidor de arquivos da release.
- O arquivo remoto respondeu como executável Windows válido (`MZ`).
- Fluxo PIX homologado de ponta a ponta: geração do QR Code, confirmação, processamento idempotente e renovação da licença.
- Fluxo de boleto homologado até a emissão, consulta pendente e cancelamento seguro da cobrança de teste.
- Suíte completa aprovada com 227 testes.

Quem estiver na versão 2.1.7 e receber o erro de certificado deverá instalar esta versão manualmente uma única vez. Usuários da 2.1.6 que perderam o reconhecimento do principal também devem instalar esta versão e escolher **Já tenho conta — Entrar**. As próximas atualizações voltarão a funcionar pelo próprio sistema.
