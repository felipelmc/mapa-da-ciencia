# CLAUDE.md

Este arquivo orienta o Claude Code (claude.ai/code) ao trabalhar neste repositório.

## Visão geral

O `mapa-da-ciencia` é um observatório da literatura científica, sucessor do SciELO-Summarizer (SICSS Brasil 2024). Ele coleta artigos (ArticleMeta do SciELO + OpenAlex), gera tópicos com embeddings, classifica resumos segundo um codebook com evidência textual e validação humana, e mostra a geografia da produção. Os modelos rodam localmente via Ollama.

Tudo é em **português**: interface, mensagens, documentação, identificadores de domínio e mensagens de commit.

O desenvolvimento segue marcos M0–M7, listados em `docs/desenvolvimento/index.md`. As decisões técnicas estão em `docs/decisoes/`. Leia o ADR relevante antes de mudar algo que ele decidiu.

## Comandos

```bash
uv sync --all-groups                         # ambiente completo (dev + docs)
uv run pytest                                # testes (pythonpath=src)
uv run pytest tests/test_projeto.py -k novo  # um teste
uv run ruff check && uv run ruff format      # lint e formatação (formata também Python em Markdown)
uv run mkdocs build --strict                 # documentação, sem avisos
uv run python scripts/gerar_contrato.py      # regenera contrato/schema e contrato/exemplo (--checar no CI)
uv run python scripts/gerar_referencias.py   # regenera docs/referencia/{cli,configuracao,codebook,contrato}.md
uv run mapa diagnostico                      # memória, Ollama, modelos, rede
uv run mapa painel --exemplo                 # painel com dados sintéticos
```

Frontend (SvelteKit), em `frontend/`: veja `frontend/README.md`. Depois de mudar os schemas, rode `npm run tipos`.

## Arquitetura

- `cli.py` só orquestra. A lógica fica nos módulos, reusados pelo servidor e por notebooks. Erros de configuração passam por `_erros_amigaveis` (mensagem em português, sem traceback).
- `config.py`: modelos Pydantic do `mapa.yaml` e do `codebook.yaml`. São a fonte da referência gerada, então toda mudança de campo precisa de `description`.
- `projeto.py`: layout da pasta de projeto (`brutos/`, `dados/`, `execucoes/`, `saida/`). `manifesto.py` registra cada execução de etapa.
- `contrato/modelos.py`: **fonte da verdade** do contrato de dados entre pipeline e interface. Deles saem os JSON Schemas e, daí, os tipos TS. Tabelas grandes são colunares, com dicionários, e os detalhes ficam em 64 fragmentos (`fragmento_de`, FNV-1a, espelhado no frontend).
- `servidor/app.py`: FastAPI. Interface em `/`, dados em `/dados`, API em `/api`. O manifesto é servido com `api: true` no painel. O site publicado usa os mesmos arquivos, com `api: false`.
- `llm/`: interface de provedor e adaptador do Ollama (httpx direto, sem SDK). No MVP não há nuvem.
- `rede.py`: **todo** HTTP externo passa por aqui (truststore, ADR 0001). `recursos.py`: memória, swap e disco.

## Regras do projeto

- **Documentação faz parte do critério de pronto.** Cada mudança leva a documentação correspondente no mesmo commit (guia, explicação ou referência). Não descreva no presente funcionalidades que ainda não existem: indique o marco.
- **Commits pequenos, um por tarefa modular**, em Conventional Commits com escopo (`feat(coleta): …`). Cada commit passa em lint, testes e `mkdocs build --strict`. Uma branch por marco, com merge em `main` e tag no fim. Push e criação do repositório remoto só com confirmação do Felipe.
- **Memória da máquina de desenvolvimento** (M4 Pro, 24 GB, pouco disco): o Felipe roda jobs pesados em paralelo. Confira `memory_pressure`, `sysctl vm.swapusage` e `ollama ps` antes de carregar modelos e de tempos em tempos. Descarregue modelos ao terminar (`keep_alive: 0`). A checagem de memória deve ignorar modelos já carregados. Nunca mexa em processos que não sejam seus.
- Nunca exporte e-mails (`v70.e` da ArticleMeta), codificações humanas individuais nem chaves.

## Armadilhas conhecidas

- O `uv` marca `.venv` como oculta no macOS, e às vezes os `.pth` herdam a marca. O Python 3.12+ os ignora e o import falha. Correção: `chflags nohidden .venv/lib/python3.*/site-packages/*.pth`.
- Desde a 0.27, o Typer embute o Click (`typer._click`). Inspecione comandos com `typer.core.TyperGroup` e `TyperArgument`.
- A ArticleMeta não filtra por ano de publicação (`from/until` é a data de processamento). Use o ano do PID (`pid[10:14]`).
- `search.scielo.org` bloqueia scripts (desafio anti-bot). Não tente raspá-lo.
- No frontend, com o router por hash, nunca use `resolve()` para links, e o estado dos filtros fica dentro do hash (ADR 0002).
