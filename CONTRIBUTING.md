# Como contribuir

Obrigado pelo interesse! O `mapa-da-ciencia` é um projeto de pesquisa aberto, e contribuições são bem-vindas: correções, documentação, novas fontes de dados, relatos de uso.

## Preparar o ambiente

```bash
git clone https://github.com/felipelmc/mapa-da-ciencia.git
cd mapa-da-ciencia
uv sync --all-groups
uv run pytest
```

Para a interface, veja [`frontend/README.md`](frontend/README.md). A visão geral da arquitetura, os arquivos gerados e como fazer uma release estão em [`docs/desenvolvimento/`](docs/desenvolvimento/index.md), que, como as decisões, fica no repositório e não no site.

## Antes de abrir um pull request

- [ ] `uv run ruff check` e `uv run ruff format --check` passam.
- [ ] `uv run pytest` passa, com testes novos para o que você mudou.
- [ ] Se mudou comandos, configuração ou o contrato de dados: rodou `uv run python scripts/gerar_referencias.py` e `uv run python scripts/gerar_contrato.py`.
- [ ] **A documentação acompanha a mudança.** No projeto, nada está pronto sem documentação: guia, referência ou explicação, conforme o caso.
- [ ] `uv run mkdocs build --strict` passa, sem avisos.

## Convenções

- **Português** na interface, nas mensagens, na documentação e nos identificadores de domínio.
- **Commits pequenos**, um por tarefa, no formato [Conventional Commits](https://www.conventionalcommits.org/pt-br/) com escopo: `feat(coleta): …`, `fix(painel): …`, `docs(guias): …`.
- **Decisões técnicas relevantes** (trocar uma biblioteca, mudar o contrato, escolher um modelo) viram um registro em [`docs/decisoes/`](docs/decisoes/README.md), com a evidência.
- **Mensagens de erro dizem o que fazer.** Quem usa o `mapa` não deve ver traceback por causa de configuração.

## Relatar um problema

Abra uma *issue* com:

- o comando que você rodou;
- a mensagem de erro;
- a saída de `mapa diagnostico`.

Não inclua chaves de API nem o conteúdo do seu `.env`.
