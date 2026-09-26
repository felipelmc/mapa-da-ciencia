# Registros de decisão

Cada decisão técnica relevante do projeto vira um registro curto (ADR, *architecture decision record*) nesta pasta. O registro explica o que foi decidido, por quê e com base em que evidência. Assim, quem chegar depois, inclusive o autor daqui a um ano, entende as escolhas sem precisar reconstruí-las.

As decisões do marco M0 vêm de **spikes**: experimentos pequenos e descartáveis que respondem a uma pergunta específica. Os scripts ficam em `spikes/` e podem ser rodados de novo para reproduzir os números.

## Índice

| Nº | Decisão | Status |
|---|---|---|
| [0001](0001-certificados-do-sistema-com-truststore.md) | Certificados do sistema operacional com `truststore` | aceita |
| [0002](0002-frontend-router-hash-e-regl-scatterplot.md) | Frontend: router por hash do SvelteKit, estado no hash e regl-scatterplot | aceita |
| [0003](0003-fontes-casamento-e-licencas.md) | Fontes do corpus, casamento ArticleMeta↔OpenAlex e licença por artigo | aceita |
| [0004](0004-embeddings-e-idioma-de-analise.md) | Embeddings com `qwen3-embedding:0.6b`, análise em inglês e exibição em português | aceita |
| [0005](0005-modelo-de-classificacao.md) | Classificação com `qwen3.5:9b`, sem raciocínio, concorrência 1 e checagem de memória contínua | aceita |
| [0006](0006-armazenamento-parquet-duckdb.md) | Corpus em Parquet via DuckDB, refeito a partir de `brutos/` | aceita |
| [0007](0007-parametros-dos-topicos.md) | Parâmetros do agrupamento em tópicos, calibrados no piloto | aceita |
| [0009](0009-tendencia-dos-topicos.md) | Tendência dos tópicos por regressão logística quase-binomial | proposta |

## Modelo

Copie o bloco abaixo para um arquivo `NNNN-titulo-curto.md`, com o número seguinte da lista.

```markdown
# NNNN. Título da decisão

- **Status:** proposta | aceita | substituída por NNNN
- **Data:** AAAA-MM-DD
- **Marco:** M0

## Contexto

Qual pergunta precisava de resposta e por que ela importa.

## Opções consideradas

- Opção A: ...
- Opção B: ...

## Evidência

Números do spike, com tabela quando couber. Diga como foram medidos.

## Decisão

O que foi escolhido.

## Consequências

O que muda no projeto e quais riscos continuam abertos.

## Como reproduzir

    uv run spikes/<script>.py
```
