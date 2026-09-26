"""O resultado da etapa de geografia, gravado em `dados/geografia/` para o exportador e para consultas.

- `vinculos.parquet`: cada autor (ou afiliação sem autor) ligado a uma instituição, com o texto da fonte, o nível
  do casamento, a semelhança e o país e a UF decididos;
- `pesos.parquet`: a contagem fracionária, uma linha por documento × (instituição, UF, país);
- `instituicoes.parquet`: as instituições que aparecem nos vínculos, com o nome para exibir, a sigla, o país, a UF
  e os totais (fracionário e de documentos);
- `resultado.json`: a assinatura do corpus e das entradas, as contagens e a cobertura.

A geografia fica desatualizada quando o corpus muda (outra coleta) ou quando mudam as entradas do casamento: os
registros das instituições, o `instituicoes.yaml`, os apelidos do pacote ou a versão do algoritmo.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

from ..armazenamento import ARQUIVO, ARQUIVO_INSTITUICOES, gravar_tabela, ler_tabela
from .instituicoes import ARQUIVO_PROJETO

PASTA = "geografia"
ARQUIVO_RESULTADO = "resultado.json"
ARQUIVO_VINCULOS = "vinculos.parquet"
ARQUIVO_PESOS = "pesos.parquet"
ARQUIVO_INSTITUICOES_USADAS = "instituicoes.parquet"
VERSAO = 1  # suba quando o casamento ou a contagem mudarem de um jeito que mude os resultados

COLUNAS_VINCULOS = {
    "doc": "VARCHAR",
    "autor": "INTEGER",
    "afiliacao": "INTEGER",
    "fonte": "VARCHAR",
    "texto": "VARCHAR",
    "casada": "VARCHAR",
    "instituicao": "VARCHAR",
    "nivel": "VARCHAR",
    "semelhanca": "DOUBLE",
    "pais_fonte": "VARCHAR",
    "uf_fonte": "VARCHAR",
    "cidade_fonte": "VARCHAR",
    "pais": "VARCHAR",
    "uf": "VARCHAR",
}
COLUNAS_PESOS = {"doc": "VARCHAR", "instituicao": "VARCHAR", "uf": "VARCHAR", "pais": "VARCHAR", "peso": "DOUBLE"}
COLUNAS_INSTITUICOES = {
    "id": "VARCHAR",
    "nome": "VARCHAR",
    "sigla": "VARCHAR",
    "pais": "VARCHAR",
    "uf": "VARCHAR",
    "tipo": "VARCHAR",
    "ror": "VARCHAR",
    "peso": "DOUBLE",
    "documentos": "INTEGER",
}


def _hash_arquivo(caminho: Path, h: Any) -> None:
    h.update(caminho.name.encode())
    if caminho.exists():
        h.update(caminho.read_bytes())


def assinatura_entradas(raiz: Path, dados: Path) -> str:
    """Hash do que o casamento lê: o corpus, os registros das instituições, as correções, as tabelas do pacote
    (países, UFs, municípios, apelidos) e a versão."""
    h = hashlib.sha256(f"versao={VERSAO}".encode())
    for caminho in (dados / ARQUIVO, dados / ARQUIVO_INSTITUICOES, raiz / ARQUIVO_PROJETO):
        _hash_arquivo(caminho, h)
    tabelas = resources.files("mapa_da_ciencia.geografia").joinpath("dados")
    for tabela in sorted(tabelas.iterdir(), key=lambda t: t.name):  # apelidos, variantes de países, UFs…
        if tabela.name.endswith(".csv"):
            h.update(tabela.name.encode())
            h.update(tabela.read_bytes())
    return h.hexdigest()[:20]


@dataclass
class Resultado:
    versao: int
    assinatura: str  # dos ids do corpus, como a dos tópicos
    entradas: str
    gerado_em: str
    contagens: dict[str, Any] = field(default_factory=dict)
    cobertura: dict[str, float] = field(default_factory=dict)

    def gravar(
        self,
        pasta: Path,
        vinculos: list[dict[str, Any]],
        pesos: list[dict[str, Any]],
        instituicoes: list[dict[str, Any]],
    ) -> None:
        """Grava as tabelas e, por último, o `resultado.json` (sem ele, a etapa conta como não feita)."""
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / ARQUIVO_RESULTADO).unlink(missing_ok=True)
        gravar_tabela(vinculos, COLUNAS_VINCULOS, pasta / ARQUIVO_VINCULOS, ordem="doc")
        gravar_tabela(pesos, COLUNAS_PESOS, pasta / ARQUIVO_PESOS, ordem="doc")
        gravar_tabela(instituicoes, COLUNAS_INSTITUICOES, pasta / ARQUIVO_INSTITUICOES_USADAS)
        tmp = pasta / (ARQUIVO_RESULTADO + ".tmp")
        tmp.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, pasta / ARQUIVO_RESULTADO)

    @classmethod
    def ler(cls, pasta: Path) -> Resultado | None:
        arquivo = pasta / ARQUIVO_RESULTADO
        if not arquivo.exists():
            return None
        return cls(**json.loads(arquivo.read_text(encoding="utf-8")))


def ler_pesos(pasta: Path) -> list[dict[str, Any]]:
    return ler_tabela(pasta / ARQUIVO_PESOS)


def ler_instituicoes(pasta: Path) -> list[dict[str, Any]]:
    return ler_tabela(pasta / ARQUIVO_INSTITUICOES_USADAS)


def ler_vinculos(pasta: Path) -> list[dict[str, Any]]:
    return ler_tabela(pasta / ARQUIVO_VINCULOS)
