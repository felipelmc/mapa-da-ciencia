"""Um painel por projeto: o segundo `mapa painel` no mesmo projeto não abre e aponta o primeiro."""

import sys

import pytest

from mapa_da_ciencia.llm.perfis import PERFIS
from mapa_da_ciencia.projeto import Projeto
from mapa_da_ciencia.servidor.trava import ARQUIVO, PainelJaAberto, travar

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="sem fcntl no Windows")


def test_um_painel_por_projeto(tmp_path):
    p = Projeto.criar(tmp_path / "p", modelo="vazio", perfil=PERFIS["leve"])
    outro = Projeto.criar(tmp_path / "q", modelo="vazio", perfil=PERFIS["leve"])
    primeiro = travar(p, 8765)
    with pytest.raises(PainelJaAberto, match=r"http://127\.0\.0\.1:8765/"):
        travar(p, 8766)
    # outro projeto abre normalmente, ao mesmo tempo
    segundo = travar(outro, 8767)
    # fechado o primeiro painel, o projeto abre de novo, e o arquivo fica fora do git do projeto
    primeiro.close()
    terceiro = travar(p, 8768)
    assert '"porta": 8768' in (p.raiz / ARQUIVO).read_text(encoding="utf-8")
    assert ARQUIVO in (p.raiz / ".gitignore").read_text(encoding="utf-8")
    terceiro.close()
    segundo.close()


def test_um_projeto_antigo_ganha_a_trava_no_gitignore(tmp_path):
    p = Projeto.criar(tmp_path / "p", modelo="vazio", perfil=PERFIS["leve"])
    ignorar = p.raiz / ".gitignore"
    ignorar.write_text(ignorar.read_text(encoding="utf-8").replace(f"{ARQUIVO}\n", ""), encoding="utf-8")
    travar(p, 8765).close()
    assert ignorar.read_text(encoding="utf-8").split().count(ARQUIVO) == 1
    travar(p, 8765).close()  # e não repete
    assert ignorar.read_text(encoding="utf-8").split().count(ARQUIVO) == 1


def test_o_painel_do_notebook_tambem_trava_o_projeto(tmp_path):
    import mapa_da_ciencia.api as mapa

    p = Projeto.criar(tmp_path / "p", modelo="vazio", perfil=PERFIS["leve"])
    aberto = mapa.painel(p, porta=8797, colab=False)
    try:
        with pytest.raises(PainelJaAberto, match="8797"):
            travar(p, 8798)
    finally:
        aberto.parar()
    travar(p, 8799).close()  # parado o painel, o projeto abre de novo
