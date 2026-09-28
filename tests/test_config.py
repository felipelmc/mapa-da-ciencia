"""Leitura dos arquivos do projeto: chaves repetidas e edições com o painel aberto."""

import pytest


def test_yaml_com_chave_repetida_e_recusado():
    from mapa_da_ciencia.config import ErroConfig, ler_yaml

    with pytest.raises(ErroConfig, match="chave repetida"):
        ler_yaml("apelidos:\n  a: b\napelidos:\n  c: d\n", "instituicoes.yaml")


def test_projeto_rele_o_mapa_yaml_editado(tmp_path):
    """Com o painel aberto, uma edição do mapa.yaml no disco chega às etapas."""
    import os

    from mapa_da_ciencia.llm.perfis import PERFIS
    from mapa_da_ciencia.projeto import Projeto

    p = Projeto.criar(tmp_path / "p", modelo="vazio", perfil=PERFIS["leve"])
    assert p.config.titulo
    arquivo = p.raiz / "mapa.yaml"
    arquivo.write_text(
        arquivo.read_text(encoding="utf-8").replace(f"titulo: {p.config.titulo}", "titulo: Outro"), encoding="utf-8"
    )
    os.utime(arquivo, ns=(arquivo.stat().st_atime_ns, arquivo.stat().st_mtime_ns + 10**9))
    assert p.config.titulo == "Outro"
