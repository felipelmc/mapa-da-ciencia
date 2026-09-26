# Desenvolvimento

Como o `mapa-da-ciencia` é organizado e como contribuir. As regras de colaboração estão no [`CONTRIBUTING.md`](https://github.com/felipelmc/mapa-da-ciencia/blob/main/CONTRIBUTING.md).

## Arquitetura

O pipeline em Python produz os arquivos do **contrato de dados**, e a interface (Svelte) os lê. O painel local e o site publicado são a mesma interface lendo os mesmos arquivos. Só o painel tem a API, que permite rodar etapas e codificar.

```mermaid
flowchart LR
  subgraph fontes[Fontes públicas]
    AM[ArticleMeta<br/>SciELO]
    OA[OpenAlex]
    IMP[CSV/RIS<br/>importados]
  end
  subgraph pipeline[Pipeline Python · CLI mapa]
    C[coletar] --> E[embeddings] --> T[tópicos]
    C --> G[geografia]
    C --> K[classificar<br/>codebook]
    K --> V[validar]
    T & G & K & V --> X[exportar]
  end
  OLL[(Ollama<br/>modelos locais)]
  E -.-> OLL
  T -.-> OLL
  K -.-> OLL
  AM & OA & IMP --> C
  X --> D[/contrato de dados<br/>saida/dados/*.json/]
  D --> P[mapa painel<br/>FastAPI + interface]
  D --> S[mapa publicar<br/>site estático]
```

| Parte | Onde | Papel |
|---|---|---|
| CLI | `src/mapa_da_ciencia/cli.py` | Só orquestra; a lógica fica nos módulos |
| Configuração | `config.py`, `projeto.py` | `mapa.yaml`, `codebook.yaml` e layout da pasta do projeto |
| Reprodutibilidade | `manifesto.py` | Registro de cada execução de etapa |
| Rede e máquina | `rede.py`, `recursos.py` | HTTP com `truststore`; memória, swap e disco |
| Modelos | `llm/` | Interface de provedor e adaptador do Ollama; perfis |
| Contrato | `contrato/` | Modelos Pydantic (a fonte da verdade), exportação, exemplo sintético |
| Painel | `servidor/app.py` | FastAPI: interface em `/`, dados em `/dados`, API em `/api` |
| Interface | `frontend/` | SvelteKit; veja o [`frontend/README.md`](https://github.com/felipelmc/mapa-da-ciencia/blob/main/frontend/README.md) |

## Ambiente

```bash
uv sync --all-groups          # Python, dependências, ferramentas de teste e documentação
uv run pytest                 # testes
uv run ruff check             # lint
uv run ruff format            # formatação
uv run mkdocs serve           # documentação em http://127.0.0.1:8000
```

A interface precisa de Node.js 20 ou mais recente só para desenvolvê-la:

```bash
cd frontend
npm ci
npm run dev                   # com os dados de exemplo; veja o README do frontend
```

## Arquivos gerados a partir do código

Três conjuntos de arquivos são **gerados** e versionados. O CI falha se estiverem desatualizados:

| O quê | Gerado por | Quando regenerar |
|---|---|---|
| `contrato/schema/*.json` e `contrato/exemplo/dados/` | `uv run python scripts/gerar_contrato.py` | Ao mudar `contrato/modelos.py` ou o gerador de exemplo |
| `frontend/src/lib/contrato/tipos.ts` | `npm run tipos` (em `frontend/`) | Depois de regenerar os schemas |
| `docs/referencia/{cli,configuracao,codebook,contrato}.md` | `uv run python scripts/gerar_referencias.py` | Ao mudar comandos, `config.py` ou o contrato |

## Convenções

- **Português** em tudo: interface, documentação, mensagens, identificadores de domínio (`coletar`, `topicos`, `revistas`).
- **Mensagens de erro dizem o que fazer**, sem traceback para o usuário (veja `_erros_amigaveis` em `cli.py`).
- **Commits pequenos**, um por tarefa modular, no formato [Conventional Commits](https://www.conventionalcommits.org/pt-br/) com escopo: `feat(coleta): …`, `docs(guias): …`. Cada commit leva o código, os testes e a documentação da tarefa, e passa no lint e nos testes.
- **Branches por marco** (`m1-esqueleto`, `m2-coleta`…), com merge em `main` e tag ao fim de cada marco.
- **Decisões técnicas relevantes viram ADR** em `docs/decisoes/`, com evidência e o script que a reproduz.

## Marcos

| Marco | Entrega | Estado |
|---|---|---|
| M0 | Spikes: fontes, embeddings, modelo de classificação, frontend ([ADRs 0001–0005](../decisoes/README.md)) | concluído |
| M1 | Esqueleto: pacote, CLI, configuração, diagnóstico, contrato, painel, documentação, CI | concluído (v0.1.0) |
| M2 | Coleta: ArticleMeta, OpenAlex, importação, deduplicação, cache | |
| M3 | Tópicos e mapa de documentos | |
| M4 | Rótulos com LLM, tópicos no tempo, geografia | |
| M5 | Classificação por codebook e validação | |
| M6 | Painel completo: rodar etapas pela interface | |
| M7 | Publicação, figuras, oficina no Colab, release | |

## Armadilhas conhecidas

**`ModuleNotFoundError: No module named 'mapa_da_ciencia'` no macOS.** O `uv` marca a pasta `.venv` como oculta no macOS, e às vezes os arquivos `.pth` da instalação editável herdam a marca. O Python 3.12+ ignora `.pth` ocultos por segurança. Para corrigir:

```bash
chflags nohidden .venv/lib/python3.*/site-packages/*.pth
```

Os testes não dependem disso (o pytest usa `pythonpath = ["src"]`).

**Typer embute o Click.** Desde a 0.27, o Typer traz a própria cópia do Click (`typer._click`). Use `typer.core.TyperGroup` e `TyperArgument` para inspecionar comandos (veja `scripts/gerar_referencias.py`).
