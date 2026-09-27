"""Hook do MkDocs: a versão do pacote (do `pyproject.toml`) e a citação (do `CITATION.cff`) ficam em `config.extra`,
para o rodapé e a seção "Como citar" da abertura."""

from __future__ import annotations

import tomllib
from pathlib import Path

import yaml


def citacao(cff: dict) -> dict:
    """Referência e BibTeX a partir do `CITATION.cff`; vazio enquanto não houver DOI."""
    doi = cff.get("doi", "")
    if not doi:
        return {}
    autores = [f"{a['family-names']}, {a['given-names']}" for a in cff["authors"]]
    ano = str(cff["date-released"])[:4] if "date-released" in cff else ""
    chave = cff["authors"][0]["family-names"].lower() + "_mapa_da_ciencia"
    campos = {
        "author": " and ".join(autores),
        "title": cff["title"],
        "year": ano,
        "publisher": "Zenodo",
        "doi": doi,
        "url": f"https://doi.org/{doi}",
    }
    largura = max(len(c) for c in campos)
    corpo = ",\n".join(f"  {c.ljust(largura)} = {{{v}}}" for c, v in campos.items())
    return {
        "doi": doi,
        "autores": "; ".join(autores),
        "titulo": cff["title"],
        "ano": ano,
        "bibtex": f"@software{{{chave},\n{corpo}\n}}",
    }


def on_config(config, **_):
    raiz = Path(config["config_file_path"]).parent
    pyproject = tomllib.loads((raiz / "pyproject.toml").read_text(encoding="utf-8"))
    config["extra"]["versao"] = pyproject["project"]["version"]
    cff = yaml.safe_load((raiz / "CITATION.cff").read_text(encoding="utf-8"))
    config["extra"]["doi"] = cff.get("doi", "")
    config["extra"]["citacao"] = citacao(cff)
    return config
