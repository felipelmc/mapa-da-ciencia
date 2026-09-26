"""Fixtures compartilhadas: APIs falsas (respx) servindo respostas reais recortadas em tests/fixtures/."""

from __future__ import annotations

import gzip
import json
from collections import Counter
from pathlib import Path

import httpx
import pytest
import respx

FIXTURES = Path(__file__).parent / "fixtures"
AM = "https://articlemeta.scielo.org/api/v1"


def registros_articlemeta() -> dict[str, dict]:
    with gzip.open(FIXTURES / "articlemeta" / "artigos.jsonl.gz", "rt", encoding="utf-8") as f:
        return {linha["pid"]: linha["registro"] for linha in map(json.loads, f)}


def identificadores_op() -> dict:
    return json.loads((FIXTURES / "articlemeta" / "identificadores-op.json").read_text(encoding="utf-8"))


def casos_especiais() -> dict[str, str]:
    return json.loads((FIXTURES / "articlemeta" / "casos.json").read_text(encoding="utf-8"))


class ApisFalsas:
    """Roteador respx com as respostas das fixtures e contagem de chamadas por fonte."""

    def __init__(self, router: respx.MockRouter) -> None:
        self.router = router
        self.chamadas: Counter[str] = Counter()
        self.registros = registros_articlemeta()
        self.identificadores = {"0104-6276": identificadores_op()}
        router.get(f"{AM}/article/identifiers/").mock(side_effect=self._identificadores)
        router.get(f"{AM}/article/").mock(side_effect=self._artigo)

    def _identificadores(self, request: httpx.Request) -> httpx.Response:
        self.chamadas["articlemeta"] += 1
        issn = request.url.params.get("issn")
        offset = int(request.url.params.get("offset", 0))
        dados = self.identificadores.get(issn, {"meta": {"total": 0}, "objects": []})
        return httpx.Response(200, json={"meta": dados["meta"], "objects": dados["objects"][offset : offset + 1000]})

    def _artigo(self, request: httpx.Request) -> httpx.Response:
        self.chamadas["articlemeta"] += 1
        # PID desconhecido: a API real responde 200 com o corpo `null`
        corpo = json.dumps(self.registros.get(request.url.params.get("code"))).encode()
        return httpx.Response(200, content=corpo, headers={"content-type": "application/json"})


@pytest.fixture
def apis_falsas():
    with respx.mock(assert_all_called=False) as router:
        yield ApisFalsas(router)
