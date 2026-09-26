"""O resultado da etapa de tópicos, gravado em `dados/topicos/` para o exportador e para consultas.

- `resultado.json`: tópicos (id estável, macrotema, rótulo, cor, palavras-chave, representativos, núcleo,
  posição do rótulo no mapa), macrotemas, parâmetros, estabilidade e a assinatura do corpus usado.
- `atribuicoes.parquet`: uma linha por documento, com o tópico final (−1 = sem tópico), a atribuição (`cluster`
  ou `vizinho`), as coordenadas do mapa, os 5 vizinhos e o texto de análise usado (idioma e fonte).

A assinatura do corpus (hash dos ids) diz se os tópicos estão em dia: depois de uma coleta que mudou o corpus,
eles ficam desatualizados até a próxima execução de `mapa topicos`.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import duckdb

PASTA = "topicos"
ARQUIVO_RESULTADO = "resultado.json"
ARQUIVO_ATRIBUICOES = "atribuicoes.parquet"
_COLUNAS = {
    "id": "VARCHAR",
    "topico": "INTEGER",
    "atribuicao": "VARCHAR",
    "x": "FLOAT",
    "y": "FLOAT",
    "vizinhos": "VARCHAR[]",
    "idioma_analise": "VARCHAR",
    "fonte_analise": "VARCHAR",
}


def assinatura_corpus(ids: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(ids)).encode()).hexdigest()[:20]


@dataclass
class TopicoResultado:
    id: int
    macro: int
    rotulo: str
    descricao: str
    rotulo_fonte: str
    cor: str
    palavras: list[tuple[str, float]]
    representativos: list[str]
    n_nucleo: int
    centroide: tuple[float, float]  # medoide do núcleo no mapa: onde o rótulo fica


@dataclass
class MacroResultado:
    id: int
    rotulo: str
    descricao: str
    rotulo_fonte: str
    cor: str
    topicos: list[int]


@dataclass
class Resultado:
    assinatura: str
    gerado_em: str
    parametros: dict[str, Any]
    estabilidade_ari: float | None
    ruido: int
    reatribuidos: int
    modelos: dict[str, str]
    topicos: list[TopicoResultado] = field(default_factory=list)
    macrotemas: list[MacroResultado] = field(default_factory=list)

    def gravar(self, pasta: Path, atribuicoes: list[dict[str, Any]]) -> None:
        """Grava os dois arquivos, cada um de forma atômica (temporário + rename)."""
        pasta.mkdir(parents=True, exist_ok=True)
        tmp_parquet = pasta / (ARQUIVO_ATRIBUICOES + ".tmp")
        con = duckdb.connect()
        try:
            colunas = ", ".join(f'"{k}" {v}' for k, v in _COLUNAS.items())
            con.execute(f"CREATE TABLE a ({colunas})")
            con.executemany(
                f"INSERT INTO a VALUES ({', '.join('?' * len(_COLUNAS))})",
                [[linha[k] for k in _COLUNAS] for linha in atribuicoes],
            )
            con.execute(f"COPY (SELECT * FROM a ORDER BY id) TO '{tmp_parquet}' (FORMAT parquet, COMPRESSION zstd)")
        finally:
            con.close()
        os.replace(tmp_parquet, pasta / ARQUIVO_ATRIBUICOES)
        tmp_json = pasta / (ARQUIVO_RESULTADO + ".tmp")
        tmp_json.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp_json, pasta / ARQUIVO_RESULTADO)

    @classmethod
    def ler(cls, pasta: Path) -> Resultado | None:
        arquivo = pasta / ARQUIVO_RESULTADO
        if not arquivo.exists() or not (pasta / ARQUIVO_ATRIBUICOES).exists():
            return None
        d = json.loads(arquivo.read_text(encoding="utf-8"))
        return cls(
            **{k: v for k, v in d.items() if k not in ("topicos", "macrotemas")},
            topicos=[
                TopicoResultado(
                    **{**t, "palavras": [tuple(p) for p in t["palavras"]], "centroide": tuple(t["centroide"])}
                )
                for t in d["topicos"]
            ],
            macrotemas=[MacroResultado(**m) for m in d["macrotemas"]],
        )


def ler_atribuicoes(pasta: Path) -> list[dict[str, Any]]:
    con = duckdb.connect()
    try:
        cursor = con.execute(f"SELECT * FROM read_parquet('{pasta / ARQUIVO_ATRIBUICOES}') ORDER BY id")
        nomes = [c[0] for c in cursor.description]
        return [dict(zip(nomes, linha, strict=True)) for linha in cursor.fetchall()]
    finally:
        con.close()
