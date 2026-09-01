# Regras Globais do Workspace SaaS

## 1. Segregação de Projetos (Regra Estrita de Palavras-Chave)
Este repositório contém dois projetos totalmente isolados:
1. **"SaaS Desktop":** Refere-se ao aplicativo executável local em PyQt6. Código em `src/`, `main.py`, `build.bat` e memória em `/memory/`.
2. **"SaaS Web":** Refere-se ao novo sistema em nuvem (FastAPI + PostgreSQL + React). Código e memória estritamente dentro de `web_saas/` (`web_saas/memory/` e `ESPECIFICACAO_SAAS_WEB.md`).

## 2. Memória de Projeto Obrigatória:
- **Ao trabalhar no Desktop:** Consultar e atualizar a pasta `/memory/`.
- **Ao trabalhar no Web SaaS:** Consultar e atualizar a pasta `web_saas/memory/`.
- **Categorias Obrigatórias na Memória:**
  1. `visao_geral.md`: Resumo detalhado do projeto.
  2. `tomada_de_decisoes.md`: Registros de escolhas arquiteturais.
  3. `plano_de_implementacao.md`: Checklist passo a passo.
  4. `status_de_desenvolvimento.md`: Status real das tarefas.
  5. `limitacoes.md`: Restrições e pontos de atenção.
  6. `stack_tecnologico.md`: Tecnologias e versões.
  7. `requisitos.md`: Requisitos funcionais e não funcionais.

## 3. Regra de Não-Interferência:
Ao desenvolver o sistema Web SaaS em uma nova conversa, NUNCA alterar, renomear ou remover arquivos do aplicativo Desktop (pasta raiz e `src/`). Toda a construção do SaaS Web ocorre exclusivamente dentro de `web_saas/`.
