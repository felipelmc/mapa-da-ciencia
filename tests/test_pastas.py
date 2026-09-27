"""Trocar o conteúdo de uma pasta gerada sem trocar a pasta (pastas.substituir_conteudo)."""

from mapa_da_ciencia.pastas import substituir_conteudo


def test_substitui_arquivo_por_arquivo_e_apaga_as_sobras(tmp_path):
    destino, novo = tmp_path / "dados", tmp_path / "dados.novo"
    for caminho, texto in {"manifesto.json": "velho", "detalhes/00.json": "velho", "detalhes/ff.json": "sobra"}.items():
        (destino / caminho).parent.mkdir(parents=True, exist_ok=True)
        (destino / caminho).write_text(texto)
    (destino / "vazia").mkdir()
    (destino / "era-pasta").mkdir()
    (destino / "era-pasta" / "x.json").write_text("sobra")
    for caminho, texto in {"manifesto.json": "novo", "detalhes/00.json": "novo", "era-pasta": "agora arquivo"}.items():
        (novo / caminho).parent.mkdir(parents=True, exist_ok=True)
        (novo / caminho).write_text(texto)
    identidade = destino.stat().st_ino

    substituir_conteudo(novo, destino)

    assert destino.stat().st_ino == identidade  # a mesma pasta: nada de "dados 2" no iCloud
    assert sorted(str(p.relative_to(destino)) for p in destino.rglob("*")) == [
        "detalhes",
        "detalhes/00.json",
        "era-pasta",
        "manifesto.json",
    ]
    assert (destino / "manifesto.json").read_text() == "novo" and (destino / "era-pasta").read_text() == "agora arquivo"
    assert not novo.exists()


def test_destino_novo(tmp_path):
    novo = tmp_path / "site.novo"
    (novo / "dados").mkdir(parents=True)
    (novo / "index.html").write_text("<html>")
    (novo / "dados" / "manifesto.json").write_text("{}")
    substituir_conteudo(novo, tmp_path / "site")
    assert (tmp_path / "site" / "dados" / "manifesto.json").exists() and not novo.exists()
