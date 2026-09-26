"""Roda os comandos do tutorial "Seu primeiro mapa" contra as APIs falsas, para o passo a passo não quebrar.

Os blocos `bash` viram chamadas da CLI (sem o `uv run`), e `cd` muda a pasta do teste. Os blocos `python`
rodam com `exec`. Linhas marcadas com `# fora do CI` são puladas (o painel, que não termina sozinho, o
`ollama pull` e as coletas que não estão nas fixtures). Nas partes 2 e 3, o corpus sintético faz o papel da coleta
da *Opinião Pública* de 2010 a 2025.
"""

import re
import shlex
from collections.abc import Callable
from pathlib import Path

from corpus_sintetico import corpus_sintetico
from typer.testing import CliRunner

from mapa_da_ciencia.armazenamento import ARQUIVO, gravar_documentos
from mapa_da_ciencia.cli import app

TUTORIAIS = Path(__file__).parents[1] / "docs" / "tutoriais"
PARTE_1 = TUTORIAIS / "primeiro-mapa.md"
PARTE_2 = TUTORIAIS / "primeiro-mapa-topicos.md"
PARTE_3 = TUTORIAIS / "primeiro-mapa-tempo-e-geografia.md"
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


def _rodar(tutorial: Path, monkeypatch, antes: Callable[[list[str]], None] | None = None) -> dict[str, list[str]]:
    """Roda os blocos do tutorial na ordem e devolve a saída de cada comando `mapa`, por subcomando."""
    saidas: dict[str, list[str]] = {}
    blocos = _blocos(tutorial.read_text(encoding="utf-8"))
    assert [lingua for lingua, _ in blocos].count("python") == 1
    for lingua, codigo in blocos:
        if lingua == "python":
            exec(compile(codigo, str(tutorial), "exec"), {})
            continue
        for linha in _comandos(codigo):
            if linha.startswith("cd "):
                monkeypatch.chdir(Path.cwd() / linha[3:])
                continue
            assert linha.startswith("uv run mapa "), f"comando que o teste não sabe rodar: {linha}"
            args = shlex.split(linha.split("#", 1)[0])[3:]
            if antes:
                antes(args)
            r = runner.invoke(app, args, env={"COLUMNS": "120"})
            assert r.exit_code == 0, f"{linha}\n{r.output}"
            saidas.setdefault(args[0], []).append(r.output)
    return saidas


def _semear(args: list[str]) -> None:
    """A coleta de 2010–2025 fica fora do CI: antes dos tópicos, o corpus sintético entra no lugar dela."""
    corpus = Path.cwd() / "dados" / ARQUIVO
    if args[0] == "topicos" and not corpus.exists():
        gravar_documentos(corpus_sintetico()[0], corpus)


def test_parte_1_coleta(tmp_path, apis_falsas, monkeypatch):
    monkeypatch.chdir(tmp_path)
    saidas = _rodar(PARTE_1, monkeypatch)

    # o que o tutorial promete em cada passo
    assert "0104-6276" in saidas["revistas"][0]
    primeira, segunda = saidas["coletar"]
    assert "25 documento(s) de 1 revista(s), 2024" in primeira and "OpenAlex: 25 de 25 casados" in primeira
    assert "ArticleMeta: 0 requisição(ões)" in segunda and "0 crédito(s)" in segunda
    assert "Corpus: 25 documento(s), 2024" in saidas["status"][0]
    assert (tmp_path / "projetos" / "op-2024" / "saida" / "dados" / "manifesto.json").exists()


def test_parte_2_topicos(tmp_path, apis_falsas, monkeypatch):
    monkeypatch.chdir(tmp_path)

    saidas = _rodar(PARTE_2, monkeypatch, antes=_semear)

    assert "Modelos do perfil" in saidas["diagnostico"][0]
    primeira, segunda = saidas["topicos"]
    assert "Tópicos prontos" in primeira and "Macrotema" in primeira and "Rótulos (" in primeira
    assert "mantiveram o número e a cor" in segunda and "Embeddings novos: 0" in segunda
    assert "Tópicos:" in saidas["status"][0] and "rótulos: llm" in saidas["status"][0]
    assert (tmp_path / "projetos" / "op" / "saida" / "dados" / "topicos.json").exists()


def test_parte_3_tempo_e_geografia(tmp_path, apis_falsas, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _rodar(PARTE_2, monkeypatch, antes=_semear)  # a parte 3 continua o projeto da parte 2
    saidas = _rodar(PARTE_3, monkeypatch)

    primeira, segunda = saidas["geografia"][0], saidas["geografia"][-1]
    assert "Geografia pronta" in primeira and "Fonte das afiliações" in primeira
    revisao = next(s for s in saidas["geografia"] if "sem instituição mais frequentes" in s)
    assert "apelidos:" in revisao and "Geografia pronta" in segunda
    assert "Geografia:" in saidas["status"][0] and "vínculos ligados a uma de" in saidas["status"][0]
    assert (tmp_path / "projetos" / "op" / "saida" / "dados" / "afiliacoes.json").exists()
