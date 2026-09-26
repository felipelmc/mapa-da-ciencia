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
from typing import Any, Literal

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

__all__ = [
    "Projeto",
    "abrir",
    "cobertura",
    "coletar",
    "conectar",
    "consultar",
    "documentos",
    "etapas",
    "importar",
    "novo",
    "revistas",
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
    """Conexão DuckDB com as views `documentos`, `textos`, `autores` e `afiliacoes`.

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
