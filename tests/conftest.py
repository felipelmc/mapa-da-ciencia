"""Fixtures compartilhadas: APIs falsas (respx) servindo respostas reais recortadas em tests/fixtures/."""

from __future__ import annotations

import gzip
import json
import re
from collections import Counter
from pathlib import Path

import httpx
import pytest
import respx

FIXTURES = Path(__file__).parent / "fixtures"
AM = "https://articlemeta.scielo.org/api/v1"
OA = "https://api.openalex.org"


def obras_openalex() -> list[dict]:
    with gzip.open(FIXTURES / "openalex" / "obras.jsonl.gz", "rt", encoding="utf-8") as f:
        return [json.loads(linha) for linha in f]


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
        self.obras = obras_openalex()
        self.total_forcado: int | None = None  # para simular buscas enormes
        self.fora_dos_filtros: set[str] = set()  # DOIs que só o endereço direto /works/doi:… acha
        router.get(url__regex=rf"^{re.escape(OA)}/works/doi:").mock(side_effect=self._obra)
        router.get(f"{OA}/works").mock(side_effect=self._obras)

    def _obra(self, request: httpx.Request) -> httpx.Response:
        self.chamadas["openalex"] += 1
        doi = request.url.path.split("/works/doi:", 1)[1].lower()
        obra = next((o for o in self.obras if (o.get("doi") or "").lower().endswith(doi)), None)
        return httpx.Response(200, json=obra) if obra else httpx.Response(404, json={"error": "not found"})

    def _obras(self, request: httpx.Request) -> httpx.Response:
        """Entende os filtros usados pelo mapa: ISSN (com |), intervalo de anos e lista de DOIs."""
        self.chamadas["openalex"] += 1
        filtros = dict(f.split(":", 1) for f in request.url.params.get("filter", "").split(",") if ":" in f)
        obras = [o for o in self.obras if (o.get("doi") or "").lower().removeprefix("https://doi.org/")
                 not in self.fora_dos_filtros]  # fmt: skip
        if "locations.source.issn" in filtros:
            issns = set(filtros["locations.source.issn"].split("|"))
            obras = [o for o in obras if issns & set(_issns_da_fonte(o))]
        if "publication_year" in filtros:
            a, _, b = filtros["publication_year"].partition("-")
            obras = [o for o in obras if int(a) <= (o.get("publication_year") or 0) <= int(b or a)]
        if "title_and_abstract.search" in filtros:
            termo = filtros["title_and_abstract.search"].lower()
            obras = [o for o in obras if termo in (o.get("title") or "").lower()]
        if "doi" in filtros:
            dois = {d.lower().removeprefix("https://doi.org/") for d in filtros["doi"].split("|")}
            obras = [o for o in obras if (o.get("doi") or "").lower().removeprefix("https://doi.org/") in dois]
        return httpx.Response(
            200,
            json={"meta": {"count": self.total_forcado or len(obras), "next_cursor": None}, "results": obras},
            headers={"x-ratelimit-remaining": "990"},
        )

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


def _issns_da_fonte(obra: dict) -> list[str]:
    locais = [obra.get("primary_location") or {}, *(obra.get("locations") or [])]
    return [i for lc in locais for i in ((lc.get("source") or {}).get("issn") or [])]
