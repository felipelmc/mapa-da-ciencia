"""API para notebooks e scripts: as mesmas etapas da CLI, devolvendo objetos Python.

```python
import mapa_da_ciencia.api as mapa

p = mapa.novo("op-2024", revistas=["op"], anos=2024)
print(mapa.coletar(p))
mapa.consultar(p, "SELECT ano, count(*) AS n FROM documentos GROUP BY ano")
```

Todas as funções que recebem `projeto` aceitam um `Projeto` já aberto ou o caminho da pasta.
Funciona dentro do Jupyter e do Colab: a coleta roda numa thread quando já há um laço de eventos ativo.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import duckdb

from mapa_da_ciencia.armazenamento import ARQUIVO
from mapa_da_ciencia.armazenamento import cobertura as _cobertura
from mapa_da_ciencia.armazenamento import conectar as _conectar
from mapa_da_ciencia.coleta import OpcoesColeta, ResumoColeta, guardar_importacao, interpretar_anos
from mapa_da_ciencia.coleta import coletar as _coletar
from mapa_da_ciencia.config import ErroConfig
from mapa_da_ciencia.documento import Documento
from mapa_da_ciencia.fontes import revistas as _retrato
from mapa_da_ciencia.fontes.importar import Importacao
from mapa_da_ciencia.fontes.revistas import Revista
from mapa_da_ciencia.llm.perfis import PERFIS, sugerir_perfil
from mapa_da_ciencia.manifesto import status_das_etapas
from mapa_da_ciencia.progresso import ProgressoNulo, ProgressoRich
from mapa_da_ciencia.projeto import Projeto

if TYPE_CHECKING:
    from mapa_da_ciencia.classificacao.pipeline import ResumoClassificacao
    from mapa_da_ciencia.embeddings import Embeddings
    from mapa_da_ciencia.geografia.pipeline import ResumoGeografia
    from mapa_da_ciencia.topicos.pipeline import ResumoTopicos
    from mapa_da_ciencia.validacao.amostra import Amostra, ResumoImportacao
    from mapa_da_ciencia.validacao.metricas import Validacao

__all__ = [
    "Projeto",
    "abrir",
    "amostra_de_validacao",
    "classificar",
    "cobertura",
    "codificacoes",
    "coletar",
    "conectar",
    "consultar",
    "documentos",
    "embeddings",
    "etapas",
    "geografia",
    "importar",
    "importar_codificacoes",
    "novo",
    "relatorio_de_validacao",
    "revistas",
    "topicos",
    "validacao",
]

Anos = int | str | tuple[int, int]


def _projeto(projeto: Projeto | str | Path) -> Projeto:
    return projeto if isinstance(projeto, Projeto) else Projeto.abrir(projeto)


def _anos(anos: Anos | None) -> tuple[int, int] | None:
    if anos is None or isinstance(anos, tuple):
        return anos
    return interpretar_anos(str(anos))


def abrir(caminho: str | Path = ".") -> Projeto:
    """Abre o projeto na pasta indicada (ou na primeira pasta acima dela que tenha `mapa.yaml`)."""
    return Projeto.abrir(caminho)


def novo(
    caminho: str | Path,
    *,
    modelo: str = "ciencia-politica",
    perfil: str | None = None,
    revistas: list[str] | None = None,
    anos: Anos | None = None,
) -> Projeto:
    """Cria um projeto, como `mapa novo`.

    Args:
        caminho: pasta a criar.
        modelo: `ciencia-politica` (as 10 revistas do piloto e um codebook de exemplo) ou `vazio`.
        perfil: `leve`, `padrao` ou `forte`. Sem ele, o perfil é sugerido pela memória da máquina.
        revistas: ISSNs ou acrônimos que substituem as revistas do modelo.
        anos: `2024`, `"2010-2025"` ou `(2010, 2025)`.
    """
    if perfil is not None and perfil not in PERFIS:
        raise ErroConfig(f"Perfil desconhecido: {perfil}. Opções: {', '.join(PERFIS)}")
    return Projeto.criar(
        caminho,
        modelo=modelo,
        perfil=PERFIS[perfil] if perfil else sugerir_perfil(),
        revistas=revistas,
        anos=_anos(anos),
    )


def coletar(
    projeto: Projeto | str | Path = ".",
    *,
    revistas: list[str] | None = None,
    anos: Anos | None = None,
    limite: int | None = None,
    atualizar: bool = False,
    offline: bool = False,
    sem_openalex: bool = False,
    consulta: str | None = None,
    progresso: bool = True,
) -> ResumoColeta:
    """Coleta o corpus, como `mapa coletar`, e devolve o resumo da execução (`print(resumo)` mostra os números).

    `revistas` e `anos` valem só para esta execução; o `mapa.yaml` não muda. Os demais argumentos
    correspondem às opções da CLI (`--limite`, `--atualizar`, `--offline`, `--sem-openalex`, `--consulta`).
    """
    p = _projeto(projeto)
    opcoes = OpcoesColeta(
        revistas=revistas,
        anos=_anos(anos),
        limite=limite,
        atualizar=atualizar,
        offline=offline,
        sem_openalex=sem_openalex,
        consulta=consulta,
    )
    if not progresso:
        return _coletar(p, opcoes, ProgressoNulo())
    from rich.console import Console

    return _coletar(p, opcoes, ProgressoRich(Console()))


def importar(projeto: Projeto | str | Path, *arquivos: str | Path) -> list[Importacao]:
    """Guarda exportações do search.scielo.org (RIS, CSV, BibTeX) ou listas de DOIs em `importados/`.

    Diferente de `mapa importar`, não roda a coleta: chame `coletar(projeto)` em seguida.
    Cada `Importacao` diz quantos registros foram reconhecidos (`.resumo()`) e quais foram ignorados.
    """
    p = _projeto(projeto)
    return [guardar_importacao(p, Path(a)) for a in arquivos]


def revistas(busca: str = "", *, area: str = "") -> list[Revista]:
    """Revistas correntes do SciELO Brasil, como `mapa revistas`, filtradas por nome, acrônimo, ISSN ou área."""
    return _retrato.buscar(busca, area)


def _parquet(p: Projeto) -> Path:
    caminho = p.dados / ARQUIVO
    if not caminho.exists():
        raise ErroConfig(f"O projeto {p.raiz.name} ainda não tem documentos. Rode `coletar` antes.")
    return caminho


def documentos(projeto: Projeto | str | Path = ".") -> list[Documento]:
    """Todos os documentos do corpus, com títulos, resumos, autores e afiliações."""
    from mapa_da_ciencia.armazenamento import ler_documentos

    return ler_documentos(_parquet(_projeto(projeto)))


def conectar(projeto: Projeto | str | Path = ".") -> duckdb.DuckDBPyConnection:
    """Conexão DuckDB com as views `documentos`, `textos`, `autores`, `afiliacoes`; depois de `topicos()`,
    `atribuicoes`; depois de `geografia()`, `vinculos`, `pesos` e `instituicoes`; depois de `classificar()`,
    `classificacoes`.

    Use com `with` para fechar ao fim:

    ```python
    with mapa.conectar(p) as con:
        df = con.sql("SELECT * FROM textos WHERE campo = 'resumo'").df()  # .df() pede pandas; .pl(), polars
    ```
    """
    return _conectar(_parquet(_projeto(projeto)))


def consultar(
    projeto: Projeto | str | Path,
    sql: str,
    *,
    como: Literal["dicts", "tuplas", "pandas", "polars"] = "dicts",
) -> Any:
    """Roda uma consulta SQL sobre o corpus e devolve o resultado já materializado.

    Args:
        sql: consulta sobre as views `documentos`, `textos`, `autores` e `afiliacoes`.
        como: `dicts` (lista de dicionários, o padrão), `tuplas`, `pandas` ou `polars`. Os dois últimos
            precisam da biblioteca instalada.
    """
    with conectar(projeto) as con:
        rel = con.sql(sql)
        if como == "pandas":
            return rel.df()
        if como == "polars":
            return rel.pl()
        linhas = rel.fetchall()
        if como == "tuplas":
            return linhas
        return [dict(zip(rel.columns, linha, strict=True)) for linha in linhas]


def cobertura(projeto: Projeto | str | Path = ".") -> dict[str, Any]:
    """Os números da seção Corpus do `mapa status`: por revista, tipo, idioma, DOI, afiliações, licenças..."""
    return _cobertura(_parquet(_projeto(projeto)))


def etapas(projeto: Projeto | str | Path = ".") -> dict[str, dict[str, Any] | None]:
    """Manifesto da última execução de cada etapa (`None` para as pendentes), como na tabela do `mapa status`."""
    return status_das_etapas(_projeto(projeto))


def embeddings(projeto: Projeto | str | Path = ".", *, refazer: bool = False, progresso: bool = True) -> Embeddings:
    """Um vetor por documento (título e resumo no idioma de análise), calculado pelo Ollama e guardado em cache.

    O resultado tem `ids` e `matriz` (numpy, uma linha por documento, normalizada), além da marca de cada texto
    (`textos[i].fonte`: `resumo`, `reserva` ou `so_titulo`). Na segunda vez, vem inteiro do cache.
    """
    from mapa_da_ciencia.embeddings import calcular_embeddings

    p = _projeto(projeto)
    if not progresso:
        return calcular_embeddings(p, refazer=refazer, progresso=ProgressoNulo())
    from rich.console import Console

    return calcular_embeddings(p, refazer=refazer, progresso=ProgressoRich(Console()))


def topicos(
    projeto: Projeto | str | Path = ".",
    *,
    sem_rotulos: bool = False,
    refazer_embeddings: bool = False,
    semente: int | None = None,
    refazer_macrotemas: bool = False,
    progresso: bool = True,
) -> ResumoTopicos:
    """Descobre os tópicos, como `mapa topicos`, e devolve o resumo (`print(resumo)` mostra os números).

    O resultado fica em `dados/topicos/` e pode ser consultado pela view `atribuicoes` (tópico, coordenadas no
    mapa e vizinhos de cada documento), por exemplo: `consultar(p, "SELECT topico, count(*) FROM atribuicoes
    GROUP BY topico")`.
    """
    from mapa_da_ciencia.topicos.pipeline import OpcoesTopicos, gerar_topicos

    p = _projeto(projeto)
    opcoes = OpcoesTopicos(
        sem_rotulos=sem_rotulos,
        refazer_embeddings=refazer_embeddings,
        semente=semente,
        refazer_macrotemas=refazer_macrotemas,
    )
    if not progresso:
        return gerar_topicos(p, opcoes, ProgressoNulo())
    from rich.console import Console

    return gerar_topicos(p, opcoes, ProgressoRich(Console()))


def geografia(projeto: Projeto | str | Path = ".", *, progresso: bool = True) -> ResumoGeografia:
    """Liga as afiliações às instituições, como `mapa geografia`, e devolve o resumo (`print(resumo)` mostra os
    números).

    O resultado fica em `dados/geografia/` e pode ser consultado pelas views `vinculos` (cada autor ligado a uma
    instituição, com o texto da fonte e o nível do casamento), `pesos` (a contagem fracionária) e `instituicoes`,
    por exemplo: `consultar(p, "SELECT uf, sum(peso) FROM pesos GROUP BY uf ORDER BY 2 DESC")`.
    """
    from mapa_da_ciencia.geografia.pipeline import gerar_geografia

    p = _projeto(projeto)
    if not progresso:
        return gerar_geografia(p, ProgressoNulo())
    from rich.console import Console

    return gerar_geografia(p, ProgressoRich(Console()))


def classificar(
    projeto: Projeto | str | Path = ".",
    *,
    estimar: bool = False,
    limite: int | None = None,
    modelo: str | None = None,
    somente_amostra: bool = False,
    progresso: bool = True,
) -> ResumoClassificacao:
    """Classifica os resumos pelo codebook, como `mapa classificar`, e devolve o resumo.

    O resultado fica em `dados/classificacao/` e pode ser consultado pela view `classificacoes` (uma linha por
    documento × variável, com o valor, a evidência e o status da conferência; a coluna `execucao` diz o modelo e o
    codebook), por exemplo: `consultar(p, "SELECT valor, count(*) FROM classificacoes WHERE variavel = 'abordagem'
    GROUP BY valor")`.
    """
    from mapa_da_ciencia.classificacao.pipeline import OpcoesClassificacao
    from mapa_da_ciencia.classificacao.pipeline import classificar as rodar

    p = _projeto(projeto)
    opcoes = OpcoesClassificacao(estimar=estimar, limite=limite, modelo=modelo, somente_amostra=somente_amostra)
    if not progresso:
        return rodar(p, opcoes, ProgressoNulo())
    from rich.console import Console

    return rodar(p, opcoes, ProgressoRich(Console()))


def amostra_de_validacao(
    projeto: Projeto | str | Path = ".", *, refazer: bool = False, n: int | None = None
) -> Amostra:
    """A amostra de validação, como `mapa validar amostra`: sorteada na primeira vez (ou com `refazer=True`) e
    exportada em `validacao/amostra.jsonl`. `amostra.docs` traz os ids na ordem da fila de codificação; `n` troca o
    tamanho de `validacao.n` só neste sorteio."""
    from mapa_da_ciencia.validacao import amostra as va

    p = _projeto(projeto)
    a = va.sortear(p, refazer=refazer, n=n)
    va.exportar(p, a)
    return a


def importar_codificacoes(
    projeto: Projeto | str | Path,
    arquivo: str | Path,
    codificador: str,
    *,
    tipo: Literal["humano", "referencia"] = "humano",
) -> ResumoImportacao:
    """Importa um JSONL de codificações da amostra, como `mapa validar importar`. Linhas inválidas não são
    gravadas e aparecem em `resumo.invalidas`."""
    from mapa_da_ciencia.contrato.exportar import exportar
    from mapa_da_ciencia.validacao import amostra as va

    p = _projeto(projeto)
    resumo = va.importar(p, Path(arquivo), codificador, tipo=tipo)
    if resumo.documentos:
        exportar(p)  # o painel passa a mostrar a concordância
    return resumo


def codificacoes(projeto: Projeto | str | Path = ".", codificador: str | None = None) -> list[dict[str, Any]]:
    """As codificações guardadas (de um codificador, ou de todos), uma por codificador × documento × variável."""
    from mapa_da_ciencia.validacao import amostra as va

    return va.codificacoes(_projeto(projeto), codificador)


def validacao(projeto: Projeto | str | Path = ".") -> Validacao:
    """As métricas de concordância na amostra, como `mapa validar metricas`: por variável e por par de
    participantes (codificadores e modelos), com kappa e IC 95%, PABAK, alfa, matriz de confusão e P/R/F1 por
    classe; McNemar entre modelos e as divergências com o modelo principal."""
    from mapa_da_ciencia.validacao.metricas import calcular

    return calcular(_projeto(projeto))


def relatorio_de_validacao(projeto: Projeto | str | Path = ".") -> dict[str, Path]:
    """Grava o relatório da validação, como `mapa validar relatorio`, e devolve os caminhos: `markdown`
    (`validacao/relatorio.md`), `latex` (`validacao/tabelas.tex`) e `json` (`validacao/metricas.json`)."""
    from mapa_da_ciencia.validacao.relatorio import gerar

    return gerar(_projeto(projeto))[1]
