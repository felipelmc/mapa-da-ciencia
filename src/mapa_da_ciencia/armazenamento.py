"""Armazenamento do corpus em Parquet, via DuckDB (ADR 0006).

`dados/documentos.parquet` guarda um `Documento` por linha, com títulos, resumos, autores
e afiliações como listas de structs. É sempre refeito a partir de `brutos/`, então pode ser
apagado sem medo. Para consultar:

- no `mapa`: `conectar(projeto)` abre o DuckDB com as views `documentos`, `textos`,
  `autores` e `afiliacoes`;
- em notebooks: `pandas.read_parquet(...)` ou `polars.read_parquet(...)` leem direto.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

import duckdb

from mapa_da_ciencia.documento import Documento

_TEXTO = "STRUCT(idioma VARCHAR, texto VARCHAR, origem VARCHAR)[]"
ESQUEMA: dict[str, str] = {
    "id": "VARCHAR",
    "pid": "VARCHAR",
    "colecao": "VARCHAR",
    "doi": "VARCHAR",
    "openalex_id": "VARCHAR",
    "fonte": "VARCHAR",
    "origens": "VARCHAR[]",
    "tipo": "VARCHAR",
    "ano": "INTEGER",
    "idioma_original": "VARCHAR",
    "revista_issn": "VARCHAR",
    "revista_acronimo": "VARCHAR",
    "revista_titulo": "VARCHAR",
    "titulos": _TEXTO,
    "resumos": _TEXTO,
    "palavras_chave": _TEXTO,
    "autores": "STRUCT(nome VARCHAR, sobrenome VARCHAR, orcid VARCHAR, afiliacoes VARCHAR[])[]",
    "afiliacoes": (
        "STRUCT(id VARCHAR, instituicao VARCHAR, divisoes VARCHAR[], cidade VARCHAR, uf VARCHAR, "
        "pais VARCHAR, fonte VARCHAR)[]"
    ),
    "afiliacoes_fonte": "VARCHAR",
    "autorias_openalex": (
        "STRUCT(nome VARCHAR, instituicoes STRUCT(id VARCHAR, ror VARCHAR, nome VARCHAR, pais VARCHAR, "
        "tipo VARCHAR, linhagem VARCHAR[])[], paises VARCHAR[], "
        "afiliacoes STRUCT(texto VARCHAR, instituicoes VARCHAR[])[], id VARCHAR, orcid VARCHAR)[]"
    ),
    "url": "VARCHAR",
    "citacoes": "INTEGER",
    "n_referencias": "INTEGER",
    "licenca": "VARCHAR",
    "licenca_fonte": "VARCHAR",
    "licenca_openalex": "VARCHAR",
    "licenca_revista": "VARCHAR",
    "casamento": "VARCHAR",
    "possivel_duplicata_de": "VARCHAR",
}
ARQUIVO = "documentos.parquet"
ARQUIVO_INSTITUICOES = "instituicoes_openalex.parquet"  # registros das instituições do OpenAlex (coleta)
ARQUIVO_REFERENCIAS = "referencias_openalex.parquet"  # obra do corpus → obra citada (coleta)
ARQUIVO_CITADAS = "obras_citadas_openalex.parquet"  # as obras de fora do corpus mais citadas (coleta)


def _colunas_sql() -> str:
    return "{" + ", ".join(f"'{k}': '{v}'" for k, v in ESQUEMA.items()) + "}"


def gravar_documentos(documentos: Iterable[Documento], destino: Path) -> int:
    """Grava os documentos em Parquet (zstd), ordenados por id, de forma atômica. Devolve quantos."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp_parquet = destino.with_name(destino.name + ".tmp")
    n = 0
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
        for doc in documentos:
            f.write(json.dumps(doc.model_dump(mode="json"), ensure_ascii=False) + "\n")
            n += 1
        jsonl = f.name
    try:
        con = duckdb.connect()
        if n:
            origem = f"read_json(?, format='newline_delimited', columns={_colunas_sql()})"
            con.execute(
                f"COPY (SELECT * FROM {origem} ORDER BY id) TO '{tmp_parquet}' (FORMAT parquet, COMPRESSION zstd)",
                [jsonl],
            )
        else:  # corpus vazio: um Parquet com o esquema e nenhuma linha
            colunas = ", ".join(f'"{k}" {v}' for k, v in ESQUEMA.items())
            con.execute(f"CREATE TABLE vazio ({colunas})")
            con.execute(f"COPY vazio TO '{tmp_parquet}' (FORMAT parquet, COMPRESSION zstd)")
        con.close()
        os.replace(tmp_parquet, destino)
    finally:
        Path(jsonl).unlink(missing_ok=True)
        tmp_parquet.unlink(missing_ok=True)
    return n


def _linhas(con: duckdb.DuckDBPyConnection, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
    cursor = con.execute(sql, params or [])
    nomes = [d[0] for d in cursor.description]
    return [dict(zip(nomes, linha, strict=True)) for linha in cursor.fetchall()]


def gravar_tabela(
    linhas: Iterable[dict[str, Any]], colunas: dict[str, str], destino: Path, ordem: str | Sequence[str] = "id"
) -> int:
    """Grava uma tabela qualquer em Parquet (zstd), ordenada por `ordem`, de forma atômica. Devolve quantas linhas.

    Os empates em `ordem` se desfazem pelas outras colunas, na ordem do esquema: o DuckDB não garante a ordem das
    linhas empatadas com várias threads (acima de ~250 mil linhas, o mesmo conteúdo dava arquivos diferentes, e a
    assinatura das entradas das redes mudava a cada coleta)."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp_parquet = destino.with_name(destino.name + ".tmp")
    n = 0
    # via JSON Lines, como em `gravar_documentos`: o `executemany` do DuckDB leva segundos para alguns milhares
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
        for linha in linhas:
            f.write(json.dumps({k: linha.get(k) for k in colunas}, ensure_ascii=False) + "\n")
            n += 1
        jsonl = f.name
    con = duckdb.connect()
    try:
        definicao = ", ".join(f'"{k}" {v}' for k, v in colunas.items())
        con.execute(f"CREATE TABLE t ({definicao})")
        if n:
            tipos = "{" + ", ".join(f"'{k}': '{v}'" for k, v in colunas.items()) + "}"
            con.execute(
                f"INSERT INTO t SELECT * FROM read_json(?, format='newline_delimited', columns={tipos})", [jsonl]
            )
        chaves = [ordem] if isinstance(ordem, str) else list(ordem)
        criterio = ", ".join(f'"{k}"' for k in [*chaves, *(k for k in colunas if k not in chaves)])
        con.execute(f"COPY (SELECT * FROM t ORDER BY {criterio}) TO '{tmp_parquet}' (FORMAT parquet, COMPRESSION zstd)")
    finally:
        con.close()
        Path(jsonl).unlink(missing_ok=True)
    os.replace(tmp_parquet, destino)
    return n


def ler_tabela(caminho: Path) -> list[dict[str, Any]]:
    """As linhas de um Parquet gravado por `gravar_tabela`, como dicionários."""
    con = duckdb.connect()
    try:
        return _linhas(con, "SELECT * FROM read_parquet(?)", [str(caminho)])
    finally:
        con.close()


def tem_coluna(caminho: Path, nome: str) -> bool:
    """`True` se o Parquet tem a coluna: distingue um corpus gravado antes de um campo novo existir."""
    con = duckdb.connect()
    try:
        colunas = [c[0] for c in con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(caminho)]).fetchall()]
    finally:
        con.close()
    return nome in colunas


def ler_documentos(caminho: Path) -> list[Documento]:
    con = duckdb.connect()
    try:
        # sempre na ordem dos ids: o UMAP e os caches dependem da ordem das linhas
        sql = "SELECT * FROM read_parquet(?) ORDER BY id"
        return [Documento.model_validate(d) for d in _linhas(con, sql, [str(caminho)])]
    finally:
        con.close()


def conectar(caminho: Path) -> duckdb.DuckDBPyConnection:
    """DuckDB em memória com as views do corpus: `documentos`, `textos`, `autores`, `afiliacoes`; se a etapa de
    tópicos já rodou, `atribuicoes`; se a de geografia já rodou, `vinculos`, `pesos` e `instituicoes`; se a de
    classificação já rodou, `classificacoes`."""
    con = duckdb.connect()
    con.execute(f"CREATE VIEW documentos AS SELECT * FROM read_parquet('{caminho}')")
    con.execute(
        """CREATE VIEW textos AS
        SELECT id, 'titulo' AS campo, t.idioma, t.texto, t.origem FROM documentos, unnest(titulos) AS u(t)
        UNION ALL
        SELECT id, 'resumo', t.idioma, t.texto, t.origem FROM documentos, unnest(resumos) AS u(t)"""
    )
    con.execute(
        """CREATE VIEW autores AS
        SELECT id, ordem, a.nome, a.sobrenome, a.orcid, a.afiliacoes
        FROM (SELECT id, unnest(autores) AS a, generate_subscripts(autores, 1) AS ordem FROM documentos)"""
    )
    con.execute(
        """CREATE VIEW afiliacoes AS
        SELECT id, f.id AS afiliacao, f.instituicao, f.divisoes, f.cidade, f.uf, f.pais, f.fonte
        FROM documentos, unnest(afiliacoes) AS u(f)"""
    )
    atribuicoes = caminho.parent / "topicos" / "atribuicoes.parquet"
    if atribuicoes.exists():  # depois de `mapa topicos`: tópico, coordenadas e vizinhos de cada documento
        con.execute(f"CREATE VIEW atribuicoes AS SELECT * FROM read_parquet('{atribuicoes}')")
    classificacao = caminho.parent / "classificacao"
    if any(classificacao.glob("*.parquet")):  # depois de `mapa classificar`: uma execução por modelo e codebook
        con.execute(
            "CREATE VIEW classificacoes AS SELECT * EXCLUDE (filename), "
            "regexp_extract(filename, '([^/]+)[.]parquet$', 1) AS execucao "
            f"FROM read_parquet('{classificacao}/*.parquet', filename = true)"
        )
    for nome in ("vinculos", "pesos", "instituicoes"):  # depois de `mapa geografia`
        arquivo = caminho.parent / "geografia" / f"{nome}.parquet"
        if arquivo.exists():
            con.execute(f"CREATE VIEW {nome} AS SELECT * FROM read_parquet('{arquivo}')")
    return con


def cobertura(caminho: Path) -> dict[str, Any]:
    """Números do corpus para o `mapa status` e o manifesto: cobertura de resumos, DOI, afiliações etc."""
    con = conectar(caminho)
    try:
        um = lambda sql: con.execute(sql).fetchone()[0]  # noqa: E731
        contagem = lambda sql: dict(con.execute(sql).fetchall())  # noqa: E731
        return {
            "documentos": um("SELECT count(*) FROM documentos"),
            "por_revista": contagem(
                "SELECT coalesce(revista_acronimo, revista_issn, '?'), count(*) "
                "FROM documentos GROUP BY 1 ORDER BY 2 DESC"
            ),
            "por_tipo": contagem("SELECT tipo, count(*) FROM documentos GROUP BY 1 ORDER BY 2 DESC"),
            "com_resumo": um("SELECT count(*) FROM documentos WHERE len(resumos) > 0"),
            "resumo_por_idioma": contagem(
                "SELECT idioma, count(DISTINCT id) FROM textos WHERE campo = 'resumo' GROUP BY 1 ORDER BY 2 DESC"
            ),
            "com_doi": um("SELECT count(*) FROM documentos WHERE doi IS NOT NULL"),
            "com_afiliacao": um("SELECT count(*) FROM documentos WHERE len(afiliacoes) > 0"),
            "afiliacoes_fonte": contagem(
                "SELECT afiliacoes_fonte, count(*) FROM documentos GROUP BY 1 ORDER BY 2 DESC"
            ),
            "casamento": contagem("SELECT casamento, count(*) FROM documentos GROUP BY 1 ORDER BY 1"),
            "licencas": contagem("SELECT licenca, count(*) FROM documentos GROUP BY 1 ORDER BY 2 DESC"),
            "licenca_fonte": contagem("SELECT licenca_fonte, count(*) FROM documentos GROUP BY 1 ORDER BY 2 DESC"),
            "possiveis_duplicatas": um("SELECT count(*) FROM documentos WHERE possivel_duplicata_de IS NOT NULL"),
            "anos": list(con.execute("SELECT min(ano), max(ano) FROM documentos").fetchone()),
        }
    finally:
        con.close()
