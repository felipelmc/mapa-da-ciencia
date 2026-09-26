"""Roda os comandos do tutorial "Seu primeiro mapa" contra as APIs falsas, para o passo a passo não quebrar.

Os blocos `bash` viram chamadas da CLI (sem o `uv run`), e `cd` muda a pasta do teste. Os blocos `python`
rodam com `exec`. Linhas marcadas com `# fora do CI` são puladas (o painel, que não termina sozinho, e o
piloto inteiro, que não está nas fixtures).
"""

import re
import shlex
from pathlib import Path

from typer.testing import CliRunner

from mapa_da_ciencia.cli import app

TUTORIAL = Path(__file__).parents[1] / "docs" / "tutoriais" / "primeiro-mapa.md"
FORA_DO_CI = "# fora do CI"
runner = CliRunner()


def _blocos(texto: str) -> list[tuple[str, str]]:
    """Blocos de código `bash` e `python`, na ordem, inclusive os indentados (dentro de listas e avisos)."""
    blocos = []
    for m in re.finditer(r"^( *)```(bash|python)\n(.*?)^\1```", texto, flags=re.M | re.S):
        recuo = len(m.group(1))
        codigo = "\n".join(linha[recuo:] for linha in m.group(3).splitlines())
        blocos.append((m.group(2), codigo))
    return blocos


def _comandos(bloco: str) -> list[str]:
    linhas = [linha.strip() for linha in bloco.splitlines()]
    return [linha for linha in linhas if linha and not linha.startswith("#") and FORA_DO_CI not in linha]


def test_tutorial_primeiro_mapa(tmp_path, apis_falsas, monkeypatch):
    monkeypatch.chdir(tmp_path)
    saidas: dict[str, list[str]] = {}
    blocos = _blocos(TUTORIAL.read_text(encoding="utf-8"))
    assert [lingua for lingua, _ in blocos].count("python") == 1
    for lingua, codigo in blocos:
        if lingua == "python":
            exec(compile(codigo, str(TUTORIAL), "exec"), {})
            continue
        for linha in _comandos(codigo):
            if linha.startswith("cd "):
                monkeypatch.chdir(Path.cwd() / linha[3:])
                continue
            assert linha.startswith("uv run mapa "), f"comando que o teste não sabe rodar: {linha}"
            args = shlex.split(linha.split("#", 1)[0])[3:]
            r = runner.invoke(app, args, env={"COLUMNS": "120"})
            assert r.exit_code == 0, f"{linha}\n{r.output}"
            saidas.setdefault(args[0], []).append(r.output)

    # o que o tutorial promete em cada passo
    assert "0104-6276" in saidas["revistas"][0]
    primeira, segunda = saidas["coletar"]
    assert "25 documento(s) de 1 revista(s), 2024" in primeira and "OpenAlex: 25 de 25 casados" in primeira
    assert "ArticleMeta: 0 requisição(ões)" in segunda and "0 crédito(s)" in segunda
    assert "Corpus: 25 documento(s), 2024" in saidas["status"][0]
    assert (tmp_path / "projetos" / "op-2024" / "saida" / "dados" / "manifesto.json").exists()
