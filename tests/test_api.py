import asyncio

import pytest
from conftest import FIXTURES

import mapa_da_ciencia.api as mapa
from mapa_da_ciencia.config import ErroConfig


@pytest.fixture
def projeto(tmp_path):
    return mapa.novo(tmp_path / "op-2024", modelo="vazio", perfil="leve", revistas=["op"], anos=2024)


def test_novo_coletar_e_consultar(projeto, apis_falsas):
    assert projeto.config.recorte.anos == (2024, 2024)
    with pytest.raises(ErroConfig, match="ainda não tem documentos"):
        mapa.documentos(projeto)
    resumo = mapa.coletar(projeto.raiz, progresso=False)  # também aceita o caminho da pasta
    assert resumo.documentos == 25 and str(resumo).startswith("25 documento(s) de 1 revista(s), 2024, em ")
    assert len(mapa.documentos(projeto)) == 25
    linhas = mapa.consultar(projeto, "SELECT revista_acronimo AS revista, count(*) AS n FROM documentos GROUP BY 1")
    assert linhas == [{"revista": "op", "n": 25}]
    assert mapa.consultar(projeto, "SELECT count(*) FROM autores", como="tuplas")[0][0] > 25
    with mapa.conectar(projeto) as con:
        assert con.sql("SELECT count(DISTINCT id) FROM textos WHERE campo = 'resumo'").fetchone()[0] == 25
    assert mapa.cobertura(projeto)["com_doi"] == 25
    assert mapa.etapas(projeto)["coleta"]["contagens"]["documentos"] == 25
    assert mapa.etapas(projeto)["topicos"] is None


def test_consulta_em_pandas_quando_instalado(projeto, apis_falsas):
    pytest.importorskip("pandas")
    mapa.coletar(projeto, progresso=False)
    df = mapa.consultar(projeto, "SELECT ano, count(*) AS n FROM documentos GROUP BY 1", como="pandas")
    assert df.to_dict("records") == [{"ano": 2024, "n": 25}]


def test_coleta_dentro_de_um_laco_de_eventos_ativo(projeto, apis_falsas):
    async def celula_do_jupyter():
        return mapa.coletar(projeto, progresso=False)

    assert asyncio.run(celula_do_jupyter()).documentos == 25


def test_importar_so_guarda_e_a_coleta_inclui(projeto, apis_falsas):
    leituras = mapa.importar(projeto, FIXTURES / "importar" / "dois.txt")
    assert [imp.resumo() for imp in leituras] == [
        "dois.txt: 4 registro(s): 1 com PID, 2 só com DOI, 1 sem identificador"
    ]
    assert (projeto.raiz / "importados" / "dois.txt").exists()
    assert not (projeto.dados / "documentos.parquet").exists()  # não coleta sozinho
    resumo = mapa.coletar(projeto, progresso=False)
    assert resumo.fundidos == 1 and resumo.importacoes == [leituras[0].resumo()]
    with pytest.raises(ErroConfig, match="nenhum PID ou DOI"):
        vazio = projeto.raiz / "vazio.txt"
        vazio.write_text("# nada aqui\n")
        mapa.importar(projeto, vazio)


def test_revistas_e_perfil_invalido(tmp_path):
    assert [r.acronimo for r in mapa.revistas("opinião pública")] == ["op"]
    assert all("Humanas" in " ".join(r.areas) for r in mapa.revistas(area="humanas"))
    with pytest.raises(ErroConfig, match="Perfil desconhecido"):
        mapa.novo(tmp_path / "x", perfil="enorme")
