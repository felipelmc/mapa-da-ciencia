"""O resultado da classificação, gravado em `dados/classificacao/`, um par de arquivos por modelo e codebook:

- `<modelo>__<hash do codebook>.parquet`: uma linha por documento × variável, com o valor, a evidência, o status
  da conferência, os *offsets* no resumo, as tentativas e o tempo;
- `<modelo>__<hash do codebook>.json`: o resumo da execução (cobertura, JSON válido na primeira tentativa, taxas
  de evidência, tempo por documento) e a assinatura do corpus.

Guardar um par por modelo permite comparar modelos na amostra de validação (`mapa classificar --modelo`). O
modelo principal, que vai para o painel, é o de `modelos.classificacao.modelo`.

Uma rodada que não pode gravar no resultado principal (ver `classificacao.pipeline.classificar`: só uma rodada que
cobre o corpus o substitui, e nenhuma outra o diminui) grava as respostas num terceiro par,
`<modelo>__<hash do codebook>__a-parte`, que só as métricas da validação leem (como `<modelo> (versão nova)`).

O `valor` fica como texto: a categoria, `true`/`false` nas booleanas, o texto livre, ou uma lista JSON nas de
múltipla escolha.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..armazenamento import gravar_tabela, ler_tabela

PASTA = "classificacao"
COLUNAS = {
    "doc": "VARCHAR",
    "variavel": "VARCHAR",
    "valor": "VARCHAR",
    "evidencia": "VARCHAR",
    "status": "VARCHAR",
    "campo": "VARCHAR",
    "inicio": "INTEGER",
    "fim": "INTEGER",
    "tentativas": "INTEGER",
    "valida_na_primeira": "BOOLEAN",
    "segundos": "DOUBLE",
}


def nome_do_arquivo(modelo: str, hash_codebook: str, *, a_parte: bool = False) -> str:
    """`qwen3.5:9b` e `fd011aa28377255d` → `qwen3.5-9b__fd011aa28377255d` (sem o digest do modelo), com `__a-parte`
    no fim no resultado à parte da versão nova."""
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", modelo.split("@", 1)[0]).strip("-")
    return f"{base}__{hash_codebook}" + ("__a-parte" if a_parte else "")


def valor_como_texto(valor: Any) -> str:
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if isinstance(valor, list):
        return json.dumps(valor, ensure_ascii=False)
    return str(valor)


def valor_do_texto(texto: str, tipo: str) -> Any:
    if tipo == "booleana":
        return texto == "true"
    if tipo == "multipla":
        return json.loads(texto)
    return texto


@dataclass
class Resultado:
    modelo: str  # nome@digest
    codebook: str  # nome e versão
    hash_codebook: str
    assinatura: str  # dos ids do corpus
    gerado_em: str
    documentos: int  # com resumo, que podiam ser classificados
    classificados: int
    sem_resumo: int
    falhas: list[str] = field(default_factory=list)
    json_valido_na_primeira: float | None = None
    evidencia: dict[str, float] = field(default_factory=dict)  # fração por status, sem as dispensadas
    evidencia_por_variavel: dict[str, float] = field(default_factory=dict)  # fração literal
    segundos_por_documento: float | None = None  # mediana das chamadas novas desta execução
    parcial: bool = False  # com --limite, --somente-amostra ou --estimar
    execucao: str = ""  # hash de modelo@digest, versão do prompt e parâmetros (vazio nos resultados antigos)
    a_parte: bool = False  # o resultado à parte da versão nova (ver o começo do módulo)

    def gravar(self, pasta: Path, linhas: list[dict[str, Any]]) -> None:
        pasta.mkdir(parents=True, exist_ok=True)
        nome = nome_do_arquivo(self.modelo, self.hash_codebook, a_parte=self.a_parte)
        (pasta / f"{nome}.json").unlink(missing_ok=True)
        gravar_tabela(linhas, COLUNAS, pasta / f"{nome}.parquet", ordem="doc")
        tmp = pasta / f"{nome}.json.tmp"
        tmp.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, pasta / f"{nome}.json")

    @classmethod
    def ler(cls, pasta: Path, modelo: str, hash_codebook: str, *, a_parte: bool = False) -> Resultado | None:
        arquivo = pasta / f"{nome_do_arquivo(modelo, hash_codebook, a_parte=a_parte)}.json"
        if not arquivo.exists():
            return None
        return cls(**json.loads(arquivo.read_text(encoding="utf-8")))

    def apagar(self, pasta: Path) -> None:
        nome = nome_do_arquivo(self.modelo, self.hash_codebook, a_parte=self.a_parte)
        for sufixo in (".json", ".parquet"):
            (pasta / f"{nome}{sufixo}").unlink(missing_ok=True)


def ler_linhas(pasta: Path, modelo: str, hash_codebook: str, *, a_parte: bool = False) -> list[dict[str, Any]]:
    arquivo = pasta / f"{nome_do_arquivo(modelo, hash_codebook, a_parte=a_parte)}.parquet"
    return ler_tabela(arquivo) if arquivo.exists() else []


def documentos_classificados(pasta: Path, modelo: str, hash_codebook: str) -> set[str] | None:
    """Os documentos com classificação no resultado principal (a coluna `doc` do Parquet), ou `None` se ele não
    existe. Vale também para um Parquet que ficou sem o JSON."""
    arquivo = pasta / f"{nome_do_arquivo(modelo, hash_codebook)}.parquet"
    return {linha["doc"] for linha in ler_tabela(arquivo)} if arquivo.exists() else None


def resultados(pasta: Path) -> list[Resultado]:
    """Todas as execuções gravadas (um modelo e um codebook cada, e os resultados à parte da versão nova), da mais
    recente à mais antiga."""
    saida = []
    for arquivo in pasta.glob("*.json") if pasta.exists() else []:
        saida.append(Resultado(**json.loads(arquivo.read_text(encoding="utf-8"))))
    return sorted(saida, key=lambda r: r.gerado_em, reverse=True)
