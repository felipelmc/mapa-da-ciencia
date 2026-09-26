"""Gera o retrato das revistas do SciELO Brasil empacotado com o `mapa` (`mapa revistas`).

Uma única requisição à ArticleMeta traz todas as revistas correntes da coleção. O
retrato guarda só o necessário para montar recortes (títulos, ISSNs, áreas, licença),
sem os e-mails que o registro da revista traz.

Uso (da raiz do repo):
    uv run python scripts/gerar_revistas.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from mapa_da_ciencia import rede
from mapa_da_ciencia.documento import normalizar_licenca
from mapa_da_ciencia.texto import contem_email

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "src" / "mapa_da_ciencia" / "fontes" / "scielo-revistas.json"
URL = "https://articlemeta.scielo.org/api/v1/journal/"

AREAS = {
    "Health Sciences": "Ciências da Saúde",
    "Human Sciences": "Ciências Humanas",
    "Applied Social Sciences": "Ciências Sociais Aplicadas",
    "Agricultural Sciences": "Ciências Agrárias",
    "Biological Sciences": "Ciências Biológicas",
    "Engineering": "Engenharias",
    "Exact and Earth Sciences": "Ciências Exatas e da Terra",
    "Linguistics, Letters and Arts": "Linguística, Letras e Artes",
}


def _primeiro(registro: dict, campo: str) -> str | None:
    valores = registro.get(campo) or []
    return valores[0].get("_") if valores else None


def extrair(r: dict) -> dict:
    return {
        "acronimo": _primeiro(r, "v68"),
        "titulo": _primeiro(r, "v100"),
        "titulo_abreviado": _primeiro(r, "v150"),
        "issn": _primeiro(r, "v400") or r.get("code"),
        "issns": [{"tipo": i.get("t", "").lower(), "issn": i.get("_")} for i in r.get("v435", []) if i.get("_")],
        "areas": sorted({AREAS.get(a.get("_"), a.get("_")) for a in r.get("v441", []) if a.get("_")}),
        "categorias": sorted({a.get("_", "").title() for a in r.get("v854", []) if a.get("_")}),
        "licenca": normalizar_licenca(_primeiro(r, "v541")),
        "editora": _primeiro(r, "v480"),
        "uf": _primeiro(r, "v320"),
    }


def main() -> None:
    with rede.cliente(timeout=120) as http:
        r = http.get(URL, params={"collection": "scl"})
        r.raise_for_status()
        registros = r.json()
    revistas = sorted((extrair(x) for x in registros), key=lambda x: x["acronimo"] or "")
    assert not contem_email(revistas), "o retrato não pode conter e-mails"
    retrato = {
        "colecao": "scl",
        "fonte": f"{URL}?collection=scl",
        "gerado_em": datetime.now(UTC).date().isoformat(),
        "n": len(revistas),
        "revistas": revistas,
    }
    DESTINO.write_text(json.dumps(retrato, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(revistas)} revistas gravadas em {DESTINO.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
