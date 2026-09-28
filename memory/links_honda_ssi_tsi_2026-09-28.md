# Links Honda SSI/TSI — 28/09/2026

## Estado vigente

O proprietário homologou a 2.1.11: "Links gerados com sucesso, enviado para os clientes e contabilizados no myhonda". Lançamento e atualização do site autorizados e concluídos em 28/09/2026: GitHub Latest v2.1.11, OTA opcional e site público Sites versão 11. Backup concluído, 253 testes aprovados e executável aprovado no `--build-smoke-test`. Evidências no status de desenvolvimento.

Instalador: `C:\SaaS-Antigravity\dist\Instalador_SaaS_Assistente_PRO_v2.1.11.exe`, 231.858.624 bytes, SHA-256 `131a897f7a3f8b49f537e05c5332b83b5c5bc788563f75fa62a433a2e8ff3868`. Tamanho e hash conferidos contra `dist/release_v2.1.11.json`. Não instalado automaticamente nesta máquina.

## Padrões validados

SSI:

```text
https://cloud.motos.myhonda.com.br/ssi2w?e=BASE64(EMAIL)&Q1=BASE64(ID18)&Q2=BASE64(MODELO)&Q3=CILINDRADA
```

- `EMAIL`: e-mail do cliente, extraído da ficha; comparado à decodificação do exemplo recebido por e-mail oficial Honda.
- `ID18`: ID Salesforce da ficha, prefixo `a0R`; converter ID15 para ID18 com o checksum Salesforce existente.
- `MODELO`: modelo cadastrado, sem espaços e em maiúsculas; exemplo `POP110I ES` → `POP110IES`.
- `CILINDRADA`: numeração comercial do modelo, sem Base64; exemplos BIZ125EX → 125, CG160 FAN → 160, POP110 ES → 110 e XRE 190 ADV → 190. Não usar 160 como padrão e não confundir cilindrada comercial com eventual deslocamento técnico decimal.
- Proprietário confirmou que duas pesquisas SSI montadas manualmente foram respondidas pelos clientes e contabilizadas no myHonda.

TSI:

```text
https://cloud.motos.myhonda.com.br/tsi2w?e=BASE64(EMAIL)&Q1=BASE64(ID18)
```

- `EMAIL`: campo "E-mail do Cliente" na seção "TSI - Informações do Cliente" da ficha.
- `ID18`: ID Salesforce da ficha, prefixo `a0O` (letra O); conversão ID15 → ID18 com checksum.
- Não adicionar modelo, Q2 ou Q3 ao formato TSI observado.
- Exemplo oficial comparado à ficha; proprietário confirmou "Validado os links TSI" após os testes dos novos links.

Base64 é codificação reversível. Codificar os valores da query para preservar caracteres como `+`, `/` e `=`. Não salvar aqui e-mails, IDs ou links personalizados reais.

## Correção implementada — 2.1.11 local

- `src/core/medallia_builder.py` gera diretamente os novos links Honda, sem consultas HTTP à Medallia, feedless ou logs de links pessoais.
- `src/ui/screens/extraction_screen.py` usa um único fluxo de consulta da ficha para SSI e TSI, em envio individual e lote. Cilindrada é derivada da numeração comercial no modelo; não existe fallback 160.
- `src/core/honda_contact_extractor.py` coleta modelo e e-mail dos campos da ficha. SSI aceita e-mails na seção Dados para Contato; TSI usa E-mail do Cliente. E-mails divergentes impedem a geração. Telefone da fila myHonda é preferencial; campo rotulado da ficha supre ausência. Removida busca de número arbitrário no texto livre da página.
- Dados faltantes, ambíguos ou ficha incompatível impedem preparação/envio, sem marcar enviado; lote usa o tratamento de falha que libera a reserva. Callback atrasado/duplicado é ignorado.
- `Ctrl+Shift+D` autorizado e senha administrativa revelam o botão "Gerar link (diagnóstico)". Ele consulta a ficha do cliente destacado e mostra o link selecionável sem abrir pesquisa, abrir WhatsApp, enviar ou consumir cota. Autorização é reconferida ao concluir.
- Dez testes novos com dados fictícios cobrem ID/checksum, Base64/query, modelos/cilindradas, falhas, individual/lote e diagnóstico sem envio. JavaScript executado em Node com fixture DOM derivada de HTML via BeautifulSoup; não equivale ao navegador real. Tentativa de teste WebEngine/setHtml encerrou o processo neste ambiente e foi substituída por fixtures locais. Homologação no myHonda real permanece necessária.
- Não abrir nem responder pesquisas reais em testes automatizados. Não publicar GitHub, OTA ou site sem autorização específica.

## Roteiro de homologação pelo proprietário

1. Instalar o build local 2.1.11 e conferir a versão no título desde a abertura.
2. Autorizar diagnóstico temporário no Gerador Admin, fazer login no myHonda e carregar a fila.
3. Na tela de extração/reenvio, usar Ctrl+Shift+D e senha administrativa. Destacar um cliente e clicar em "Gerar link (diagnóstico)".
4. Copiar o link exibido para comparar com os dados da ficha. SSI: testar modelos 110, 125, 160 e 190; TSI: confirmar somente e/Q1. A geração não responde à pesquisa e não envia mensagem.
5. Se houver bloqueio por e-mail/modelo/ID, registrar o aviso e o formato dos campos para ajustar seletores, sem inventar dados. Não divulgar links personalizados ou dados pessoais em registros públicos.
6. Homologação operacional de geração, envio e contabilização no myHonda concluída pelo proprietário em 28/09/2026, separada dos testes automatizados.

## Histórico da cilindrada fixa (evidência Git)

O commit raiz Desktop `0664fc3721ec8fef03fc12e73331434269474ba5`, de 01/09/2026, já contém as três chamadas com "160" fixo; a instrução documentada em `memory/extracted_doc.md` dizia `Q3={CILINDRADA}`. O histórico disponível não mostra quando a regra foi originalmente introduzida, nem permite atribuir sua autoria. Registrar como divergência antiga, não como regressão recente comprovada.

## Backup pré-correção

Diretório: `C:\SaaS-Antigravity\backups\pre_links_honda_20260928`.

- `desktop_source.zip`: fontes Desktop, memória, instruções e arquivos de build, incluindo alterações locais não commitadas (2.053.857 bytes).
- `git_history.bundle`: histórico Git completo; `git bundle verify` aprovado (6.994.796 bytes).
- `private_app_data.zip`: dados locais de `SaasAssistentePRO-v2\app_data` (152.386.165 bytes). Privado: pode conter sessões/credenciais; não compartilhar/publicar.
- `Instalador_SaaS_Assistente_PRO_v2.1.10.exe`: instalador local pré-correção (231.819.902 bytes).
- `release_v2.1.10.json`: manifesto do instalador (197 bytes).

SHA-256 conferidos em 28/09/2026:

```text
desktop_source.zip  6e02737539b3182cabc663661c781f9a4f088d6f444c6fb6b0c97d152ea57d0c
git_history.bundle  240a588cb31d67e98be4691f283b3a5d5176d9cf862019da6d6ae003ee8641be
private_app_data.zip  e3ef85656dab0542124aec79868fc21da8829ee2d3d45a97473e1fb3c10a394c
Instalador_SaaS_Assistente_PRO_v2.1.10.exe  311c036c8db274743c5608030ed4864b849c68abc0676a3f45358619c06ed1ee
release_v2.1.10.json  2b0d7cd2cb5c1f71481bea8d72db0e6d4c8cbeffb92475322328022e0c61bf64
```

O backup não inclui uma exportação do Supabase remoto ou o projeto Web. O instalador 2.1.10 guardado não contém esta correção; o novo instalador 2.1.11 foi homologado e publicado após autorização do proprietário.
