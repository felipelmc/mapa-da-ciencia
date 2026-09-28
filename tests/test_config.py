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


def _salvar(arquivo, texto):
    """Grava e avança o mtime (no mesmo segundo, o sistema de arquivos pode não mudá-lo)."""
    import os

    arquivo.write_text(texto, encoding="utf-8")
    os.utime(arquivo, ns=(arquivo.stat().st_atime_ns, arquivo.stat().st_mtime_ns + 10**9))


def test_yaml_com_erro_da_erro_em_toda_leitura_ate_ser_corrigido(tmp_path):
    """Um mapa.yaml ou codebook.yaml salvo com erro não volta à versão anterior em silêncio no segundo acesso."""
    from mapa_da_ciencia.config import ErroConfig
    from mapa_da_ciencia.llm.perfis import PERFIS
    from mapa_da_ciencia.projeto import Projeto

    p = Projeto.criar(tmp_path / "p", modelo="ciencia-politica", perfil=PERFIS["leve"])
    titulo, versao = p.config.titulo, p.codebook.versao
    cfg, cb = p.raiz / "mapa.yaml", p.raiz / "codebook.yaml"
    texto_cfg, texto_cb = cfg.read_text(encoding="utf-8"), cb.read_text(encoding="utf-8")

    _salvar(cfg, texto_cfg.replace(f"titulo: {titulo}", "titulo: Novo\nrecorte: ["))
    for _ in range(3):
        with pytest.raises(ErroConfig):
            p.config  # noqa: B018
    _salvar(cfg, texto_cfg.replace(f"titulo: {titulo}", "titulo: Novo"))
    assert p.config.titulo == "Novo"

    _salvar(cb, texto_cb.replace(f'versao: "{versao}"', 'versao: "9.9"\nvariaveis: ['))
    for _ in range(3):
        with pytest.raises(ErroConfig):
            p.codebook  # noqa: B018
    _salvar(cb, texto_cb.replace(f'versao: "{versao}"', 'versao: "9.9"'))
    assert p.codebook.versao == "9.9"


def test_painel_com_mapa_yaml_com_erro_nao_mostra_a_versao_antiga(tmp_path):
    from fastapi.testclient import TestClient

    from mapa_da_ciencia.llm.perfis import PERFIS
    from mapa_da_ciencia.projeto import Projeto
    from mapa_da_ciencia.servidor.app import criar_app

    p = Projeto.criar(tmp_path / "p", modelo="vazio", perfil=PERFIS["leve"], anos=(2010, 2020))
    app = criar_app(pasta_dados=p.saida / "dados", projeto=p, estatico=tmp_path / "x")
    with TestClient(app, base_url="http://127.0.0.1", raise_server_exceptions=False) as c:
        assert c.get("/api/configuracao").json()["recorte"]["anos"] == [2010, 2020]
        arq = p.raiz / "mapa.yaml"
        texto = arq.read_text(encoding="utf-8")
        # a pessoa muda os anos no editor, mas deixa uma chave com erro de digitação
        _salvar(arq, texto.replace("anos: [2010, 2020]", "anos: [2015, 2020]\n  idioma_analise_: en"))
        assert [c.get("/api/configuracao").status_code >= 400 for _ in range(2)] == [True, True]
        _salvar(arq, texto.replace("anos: [2010, 2020]", "anos: [2015, 2020]"))
        assert c.get("/api/configuracao").json()["recorte"]["anos"] == [2015, 2020]
