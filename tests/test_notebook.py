"""O caderno da oficina no Colab: gerado e em dia, e os comandos dele rodam contra as APIs falsas.

As células marcadas `colab` (GPU, instalação do Ollama, `ollama pull`, o painel pelo proxy) só funcionam no Colab e
ficam de fora. A coleta de 2020–2024 também: as fixtures só têm a *Opinião Pública* de 2024, e o corpus sintético
entra no lugar dela, como nas partes 2 a 4 do tutorial.
"""

import importlib.util
import json
import shlex
from pathlib import Path

from corpus_sintetico import corpus_sintetico
from typer.testing import CliRunner

from mapa_da_ciencia import __version__
from mapa_da_ciencia.armazenamento import ARQUIVO, gravar_documentos
from mapa_da_ciencia.cli import app

RAIZ = Path(__file__).parents[1]
runner = CliRunner()


def _gerador():
    spec = importlib.util.spec_from_file_location("gerar_notebook", RAIZ / "scripts" / "gerar_notebook.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_caderno_em_dia_e_na_versao_do_pacote():
    g = _gerador()
    assert g.CADERNO.read_text(encoding="utf-8") == g.gerar(), "rode `uv run python scripts/gerar_notebook.py`"
    assert __version__.startswith(g.versao())
    nb = json.loads(g.CADERNO.read_text(encoding="utf-8"))
    assert nb["nbformat"] == 4 and nb["metadata"]["colab"]["gpuType"] == "T4"
    instalar = "".join(nb["cells"][2]["source"])
    assert f'VERSAO = "{g.versao()}"' in instalar and "releases/download/v{VERSAO}/" in instalar


def test_comandos_do_caderno(tmp_path, apis_falsas, monkeypatch):
    monkeypatch.chdir(tmp_path)
    nb = json.loads(_gerador().CADERNO.read_text(encoding="utf-8"))
    saidas: dict[str, list[str]] = {}
    for celula in nb["cells"]:
        if celula["cell_type"] != "code" or "colab" in celula["metadata"].get("tags", []):
            continue
        for linha in "".join(celula["source"]).splitlines():
            if linha.startswith("%cd "):
                monkeypatch.chdir(Path.cwd() / linha[4:])
                continue
            assert linha.startswith("!mapa "), f"linha que o teste não sabe rodar: {linha}"
            args = shlex.split(linha)[1:]
            if args[0] == "coletar":  # fora do CI: o corpus sintético no lugar da coleta de 2020–2024
                gravar_documentos(corpus_sintetico()[0], Path.cwd() / "dados" / ARQUIVO)
                continue
            r = runner.invoke(app, args, env={"COLUMNS": "120"})
            assert r.exit_code == 0, f"{linha}\n{r.output}"
            saidas.setdefault(args[0], []).append(r.output)

    assert "qwen3.5:9b" in (tmp_path / "oficina" / "mapa.yaml").read_text(encoding="utf-8")  # o perfil padrão
    assert "Amostra sorteada: 30 documentos" in saidas["validar"][0]
    assert "30 de" in " ".join(saidas["classificar"][0].split())
    assert "Classificação" in saidas["status"][0]
