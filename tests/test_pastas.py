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


def test_recusa_a_mesma_pasta_ou_uma_dentro_da_outra(tmp_path):
    import pytest

    pasta = tmp_path / "dados"
    (pasta / "sub").mkdir(parents=True)
    (pasta / "manifesto.json").write_text("{}")
    for novo, destino in (
        (pasta, pasta),
        (pasta, pasta / "sub"),
        (pasta / "sub", pasta),
        (tmp_path / "nao-existe", pasta),
    ):
        with pytest.raises(ValueError):
            substituir_conteudo(novo, destino)
    assert (pasta / "manifesto.json").exists()  # nada foi apagado


def test_links_simbolicos_e_arquivo_que_vira_pasta(tmp_path):
    fora = tmp_path / "fora"
    fora.mkdir()
    (fora / "importante.json").write_text("não apagar")
    destino, novo = tmp_path / "dados", tmp_path / "dados.novo"
    destino.mkdir()
    (destino / "detalhes").symlink_to(fora, target_is_directory=True)  # um link para uma pasta de fora
    (destino / "outro-link").symlink_to(fora, target_is_directory=True)
    (destino / "era-arquivo").write_text("velho")
    (novo / "detalhes").mkdir(parents=True)
    (novo / "detalhes" / "00.json").write_text("novo")
    (novo / "era-arquivo").mkdir()
    (novo / "era-arquivo" / "x.json").write_text("novo")

    substituir_conteudo(novo, destino)

    assert (fora / "importante.json").read_text() == "não apagar" and not (fora / "00.json").exists()
    assert (destino / "detalhes").is_dir() and not (destino / "detalhes").is_symlink()
    assert (destino / "detalhes" / "00.json").read_text() == "novo"
    assert (destino / "era-arquivo" / "x.json").read_text() == "novo"
    assert not (destino / "outro-link").exists()


def test_arquivo_que_so_muda_de_maiusculas(tmp_path):
    destino, novo = tmp_path / "site", tmp_path / "site.novo"
    destino.mkdir()
    (destino / "Chunk.js").write_text("velho")
    novo.mkdir()
    (novo / "chunk.js").write_text("novo")
    substituir_conteudo(novo, destino)
    # num disco que não diferencia maiúsculas (o padrão do macOS), o arquivo novo não pode sumir na limpeza
    assert [p.read_text() for p in destino.iterdir()] == ["novo"]
