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
uv run mapa coletar -P projetos/op-2024      # coleta de verdade (projetos/ fica fora do git)
uv run mapa topicos -P projetos/cp-scielo    # tópicos (use --sem-rotulos se o modelo de rótulos não couber na memória)
uv run python scripts/calibrar_topicos.py projetos/cp-scielo  # grade UMAP × HDBSCAN com 3 sementes (ADR 0007)
```

Os testes nunca acessam a rede: `tests/conftest.py` tem a fixture `apis_falsas` (respx), que responde ArticleMeta e OpenAlex com as fixtures de `tests/fixtures/` e também um Ollama falso (`OLLAMA_HOST=http://ollama.teste:11434`, com embeddings de saco de palavras via `vetor_falso`) (geradas por `scripts/recortar_fixtures.py`, com e-mails trocados por `anonimo@exemplo.invalid`). `tests/test_tutorial.py` roda os comandos do tutorial `docs/tutoriais/primeiro-mapa.md`; linhas com `# fora do CI` são puladas.

Frontend (SvelteKit), em `frontend/`: veja `frontend/README.md`. Depois de mudar os schemas, rode `npm run tipos`.

## Arquitetura

- `cli.py` só orquestra. A lógica fica nos módulos, reusados pelo servidor e por notebooks. Erros de configuração passam por `_erros_amigaveis` (mensagem em português, sem traceback).
- `config.py`: modelos Pydantic do `mapa.yaml` e do `codebook.yaml`. São a fonte da referência gerada, então toda mudança de campo precisa de `description`.
- `projeto.py`: layout da pasta de projeto (`brutos/`, `dados/`, `execucoes/`, `saida/`). `manifesto.py` registra cada execução de etapa.
- `contrato/modelos.py`: **fonte da verdade** do contrato de dados entre pipeline e interface. Deles saem os JSON Schemas e, daí, os tipos TS. Tabelas grandes são colunares, com dicionários, e os detalhes ficam em 64 fragmentos (`fragmento_de`, FNV-1a, espelhado no frontend).
- `servidor/app.py`: FastAPI. Interface em `/`, dados em `/dados`, API em `/api`. O manifesto é servido com `api: true` no painel. O site publicado usa os mesmos arquivos, com `api: false`.
- Coleta: `coleta.py` orquestra, `fontes/` tem os adaptadores (`base.py` com o `Buscador`: cache em `brutos/*.json.gz` gravado de forma atômica, retentativas, contagem de créditos; `articlemeta.py`, `openalex.py`, `importar.py`, `dedup.py`). Tudo vira `documento.Documento`, gravado por `armazenamento.py` em `dados/documentos.parquet` via DuckDB (ADR 0006), com as views `documentos`, `textos`, `autores` e `afiliacoes`. `armazenamento.ESQUEMA` precisa bater com `Documento.model_fields` (há teste). No fim da coleta e dos tópicos, `contrato/exportar.exportar` reconstrói `saida/dados/` inteira a partir de `dados/`, numa pasta nova trocada de uma vez: manifesto e revistas sempre; documentos, tópicos, agregados e detalhes só com tópicos em dia (mesma assinatura de corpus).
- `embeddings.py`: texto de análise (título e resumo no mesmo idioma, com a marca `resumo`/`reserva`/`so_titulo`) e cache incremental em `dados/embeddings/<modelo>@<digest>.npz`. `ler_documentos` sempre devolve na ordem dos ids: o UMAP depende da ordem.
- `topicos/`: `vizinhos.knn_exato` (grafo único, coluna 0 = o próprio documento) → `reducao.reduzir` (UMAP com `precomputed_knn`, cache em `dados/topicos/reducoes/`) → `agrupamento.agrupar` (HDBSCAN) → `agrupamento.reatribuir` (ruído por voto dos vizinhos do núcleo) → `ctfidf` → `macrotemas` (Ward) → `identidade.estabilizar` (ids e cores estáveis por Jaccard dos núcleos; estado em `dados/topicos/identidade.json`, gravado só pela execução principal) → `rotulos.Rotulador` (LLM com conferência de acentos, reaproveitamento, `rotulos.yaml` do projeto com prioridade, cache). `topicos/pipeline.gerar_topicos` orquestra tudo e grava `dados/topicos/{resultado.json,atribuicoes.parquet}` (`topicos/resultado.py`); a assinatura do corpus no resultado diz se os tópicos estão em dia. Com `precomputed_knn`, o umap-learn só aceita exatamente `n_neighbors` colunas quando N < 4.096 (não corta as sobras). Os testes usam `tests/corpus_sintetico.py` (6 temas plantados) com `vetor_falso`, sem Ollama; o UMAP roda uma vez por módulo.
- `api.py`: fachada para notebooks (mesmas etapas da CLI). Mantenha as assinaturas estáveis.
- `llm/`: interface de provedor e adaptador do Ollama (httpx direto, sem SDK). No MVP não há nuvem. `llm/memoria.garantir_modelo` é a checagem que toda etapa faz antes de carregar um modelo (já carregado → segue; senão, instalado e cabendo na memória livre). `Ollama.gerar_estruturado` usa `/api/chat` com `format` (esquema JSON); `llm/cache.CacheLLM` guarda as respostas válidas na tabela `llm_cache` do `estado.sqlite` (uma para todas as tarefas). No `ApisFalsas`, `responder_chat` pode ser trocada para simular respostas.
- Bibliotecas numéricas (numpy, scipy, scikit-learn, umap-learn/numba) só são importadas **dentro** das funções das etapas que as usam: `mapa --help`, a API e o gerador de referências abrem sem elas (`tests/test_importacao.py`). O numba não suporta Python novo logo que sai, por isso o teto em `requires-python`.
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
- Registros da ArticleMeta são grandes (as referências ocupam ~90%) e têm e-mails em muitos campos (`title.v64`, `v70`, `v170`, `citations`). Normalize cada um ao chegar (`buscar_registros(..., tratar=...)`) e extraia por lista branca: guardar os 4.947 brutos levava a coleta a 2,6 GB. PID desconhecido volta como `200 null`.
- A ArticleMeta tem DOIs trocados (*Dados* 2014) e artigos carregados duas vezes (*Dados* e *Lua Nova* 2025). Não relaxe a conferência do casamento (`openalex.conferir`) nem a deduplicação sem rodar o piloto e comparar com o adendo do ADR 0003.
- OpenAlex: `select` só aceita campos de raiz; a lista por revista usa `locations.source.issn` (a location principal às vezes é um repositório); o filtro `doi:` não acha trabalhos recentes, e o endereço direto `/works/doi:…` acha (e não custa créditos). Lista custa 1 crédito por página, busca 10. A `api_key` nunca vai para `brutos/` (`gravar_gz(..., ocultar=...)`).
- Rotas novas do OpenAlex ou da ArticleMeta precisam de rota na `ApisFalsas`, senão os testes falham com "not mocked".
- `ruff format` também formata Python dentro de Markdown: em exemplos com SQL, ponha a consulta numa variável, senão ele quebra a chamada em várias linhas.
- O servidor do painel não sobe pelo `preview_start` do app (sem permissão para ler `~/Desktop`): rode `mapa painel --nao-abrir` pelo terminal e abra `http://localhost:8765` no navegador do app.
- `search.scielo.org` bloqueia scripts (desafio anti-bot). Não tente raspá-lo.
- No frontend, com o router por hash, nunca use `resolve()` para links, e o estado dos filtros fica dentro do hash (ADR 0002).
