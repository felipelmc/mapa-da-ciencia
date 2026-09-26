# API Python

O `mapa-da-ciencia` também funciona dentro de um notebook (Jupyter, Colab) ou de um script. A fachada `mapa_da_ciencia.api` reúne as mesmas etapas da CLI e devolve objetos Python, e o corpus pode ser consultado em SQL.

```python
import mapa_da_ciencia.api as mapa

p = mapa.novo("op-2024", revistas=["op"], anos=2024)
resumo = mapa.coletar(p)
print(resumo)
# 25 documento(s) de 1 revista(s), 2024, em 7,2 s. De fora: 544 fora do período, ...

por_idioma = """
    SELECT idioma, count(*) AS n
    FROM textos WHERE campo = 'resumo'
    GROUP BY idioma ORDER BY n DESC
"""
mapa.consultar(p, por_idioma)
# [{'idioma': 'pt', 'n': 25}, {'idioma': 'en', 'n': 25}, ...]
```

Todas as funções que recebem `projeto` aceitam um `Projeto` já aberto ou o caminho da pasta (`mapa.coletar("op-2024")`).

## No Jupyter e no Colab

- A coleta roda dentro do notebook, com barras de progresso na própria célula. Para desligá-las, use `progresso=False`.
- `mapa.importar(p, "export.ris")` só guarda o arquivo em `importados/`. Diferente de `mapa importar` na CLI, ela não roda a coleta: chame `mapa.coletar(p)` em seguida.
- `como="pandas"` e `como="polars"` em `consultar` devolvem um DataFrame, mas precisam da biblioteca instalada (`pip install pandas`). O `mapa-da-ciencia` não depende de nenhuma das duas.

## Tabelas para consulta

O corpus fica em `dados/documentos.parquet`. `consultar` e `conectar` abrem esse arquivo no [DuckDB](https://duckdb.org/docs/stable/sql/introduction) com quatro views:

| View | Uma linha por | Colunas principais |
|---|---|---|
| `documentos` | documento | `id`, `pid`, `doi`, `ano`, `tipo`, `revista_acronimo`, `revista_issn`, `idioma_original`, `citacoes`, `licenca`, `casamento`, `origens`, `possivel_duplicata_de`; listas `titulos`, `resumos`, `palavras_chave`, `autores`, `afiliacoes` |
| `textos` | título ou resumo em um idioma | `id`, `campo` (`titulo` ou `resumo`), `idioma`, `texto`, `origem` (`articlemeta` ou `openalex`) |
| `autores` | autor de um documento | `id`, `ordem`, `nome`, `sobrenome`, `orcid`, `afiliacoes` (ids das afiliações) |
| `afiliacoes` | afiliação de um documento | `id`, `afiliacao`, `instituicao`, `divisoes`, `cidade`, `uf`, `pais`, `fonte` (`v240`, `v70` ou `openalex`) |
| `atribuicoes` | documento, depois de `topicos()` | `id`, `topico` (−1 = sem tópico), `atribuicao` (`cluster` ou `vizinho`), `x`, `y` (posição no mapa), `vizinhos` (5 ids), `idioma_analise`, `fonte_analise` |

A coluna `id` liga as quatro views. Os campos de `documentos` estão descritos em [Fontes de dados](../explicacoes/fontes.md). Para consultas longas, abra uma conexão:

```python
with mapa.conectar(p) as con:
    por_ano = con.sql("SELECT ano, count(*) FROM documentos GROUP BY ano").fetchall()
```

O Parquet também pode ser lido direto pelo pandas ou pelo polars (`pd.read_parquet("op-2024/dados/documentos.parquet")`), inclusive em R com o pacote `arrow`.

## Fachada `mapa_da_ciencia.api`

::: mapa_da_ciencia.api.abrir

::: mapa_da_ciencia.api.novo

::: mapa_da_ciencia.api.coletar

::: mapa_da_ciencia.api.importar

::: mapa_da_ciencia.api.revistas

::: mapa_da_ciencia.api.documentos

::: mapa_da_ciencia.api.embeddings

::: mapa_da_ciencia.api.topicos

::: mapa_da_ciencia.api.consultar

::: mapa_da_ciencia.api.conectar

::: mapa_da_ciencia.api.cobertura

::: mapa_da_ciencia.api.etapas

## Objetos devolvidos

::: mapa_da_ciencia.coleta.ResumoColeta
    options:
      members: false

::: mapa_da_ciencia.topicos.pipeline.ResumoTopicos
    options:
      members: false

::: mapa_da_ciencia.documento.Documento
    options:
      members: [texto_em]

::: mapa_da_ciencia.fontes.importar.Importacao
    options:
      members: [resumo]

::: mapa_da_ciencia.fontes.revistas.Revista
    options:
      members: false

## Módulos internos

As funções abaixo são usadas pela fachada, pela CLI e pelo servidor do painel. Elas podem mudar entre versões menores.

### Projeto

::: mapa_da_ciencia.projeto.Projeto
    options:
      heading_level: 4
      members: [abrir, criar, config, codebook]

### Configuração

::: mapa_da_ciencia.config.carregar_config
    options:
      heading_level: 4

::: mapa_da_ciencia.config.carregar_codebook
    options:
      heading_level: 4

::: mapa_da_ciencia.config.ErroConfig
    options:
      heading_level: 4

### Manifesto de execução

::: mapa_da_ciencia.manifesto.registrar_execucao
    options:
      heading_level: 4

::: mapa_da_ciencia.manifesto.ultima_execucao
    options:
      heading_level: 4

### Recursos da máquina

::: mapa_da_ciencia.recursos.cabe_na_memoria
    options:
      heading_level: 4

::: mapa_da_ciencia.llm.perfis.sugerir_perfil
    options:
      heading_level: 4

### Diagnóstico

::: mapa_da_ciencia.diagnostico.diagnosticar
    options:
      heading_level: 4

### Contrato de dados

::: mapa_da_ciencia.contrato.modelos.fragmento_de
    options:
      heading_level: 4

::: mapa_da_ciencia.contrato.exemplo.gerar_exemplo
    options:
      heading_level: 4
