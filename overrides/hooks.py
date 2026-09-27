"""Hook do MkDocs: a versão do pacote (do `pyproject.toml`) fica em `config.extra.versao`, para o rodapé da abertura."""

from __future__ import annotations

import tomllib
from pathlib import Path


def on_config(config, **_):
    pyproject = Path(config["config_file_path"]).parent / "pyproject.toml"
    config["extra"]["versao"] = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]
    return config
