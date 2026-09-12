# Revisão 2.0.5 — Entrar na conta existente

- Primeiro acesso oferece "Já tenho conta — Entrar", com e-mail, senha e recuperação de senha.
- Para recuperar a credencial do principal, exige também código por e-mail (OTP recente, até 10 minutos).
- Apenas o proprietário ativo pode recuperar o mesmo hardware já cadastrado como principal ativo. Outro computador precisa de vínculo autorizado; não há transferência automática.
- A recuperação troca somente o token da instalação. Não cria empresa, reinicia trial, renova prazo, remove bloqueios ou altera cobranças.
- Token anterior deixa de funcionar; limite de uma recuperação bem-sucedida por minuto e auditoria sem senha/OTP/token.
- Requer migração 022 e account-api v9, publicadas em 10/09/2026. Gerador Admin 2.0.4 permanece compatível e não requer recompilação nesta revisão.

Testes: 87 testes v2, Deno check/test e SQL no clone PostgreSQL real aprovados; HTTP de recuperação sem credenciais rejeitado com 401. Confirmação autenticada pelo proprietário ainda necessária. Não enviar senha/OTP no chat; não realizar pagamentos durante esta homologação.
