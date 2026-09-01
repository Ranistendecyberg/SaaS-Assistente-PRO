# Limitações e Restrições Técnicas — Desktop

- Alterações no HTML, seletores, iframes ou fluxo do myHonda/Salesforce podem quebrar os extratores JavaScript.
- Sessões e cookies podem expirar, exigindo novo login do operador.
- QWebEngineView consome memória relevante quando vários navegadores ficam ativos simultaneamente.
- A rolagem virtual dos relatórios pode ocultar registros que ainda não foram renderizados no DOM.
- O WhatsApp Web muda frequentemente e pode exigir atualização dos seletores e rotinas de envio.
- Disparos rápidos ou repetitivos podem causar limitações ou bloqueio da conta usada.
- O cálculo do link SSI depende da extração correta do modelo e do mapeamento da cilindrada.
- Dados locais podem ser perdidos se atualizações ou reinstalações sobrescreverem `app_data`.
- Credenciais, licenças e bancos locais não devem ser incluídos em builds, backups públicos ou pacotes de suporte.
- A aplicação é direcionada ao Windows e depende da compatibilidade entre Python, PyQt6-WebEngine, PyInstaller e a versão do Chromium embarcada.
- A migração 2.0 não pode ser publicada antes de validar o backfill de todas as empresas e licenças existentes.
- Empresas antigas não possuem necessariamente CNPJ ou e-mail de proprietário; esses dados devem ser coletados sem inventar valores.
- A versão 1.9.6 depende das tabelas de licença por instalação e deve continuar funcionando durante a transição.
- Boleto pode levar mais tempo para confirmação; a licença não pode ser liberada antes do webhook aprovado.
- Alterações de quantidade após pagamento valem para o ciclo seguinte; reembolso ou pró-rata não será automático na primeira fase.
