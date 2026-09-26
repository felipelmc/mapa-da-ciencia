import pytest
from typer.testing import CliRunner

from mapa_da_ciencia.armazenamento import ARQUIVO, ler_documentos
from mapa_da_ciencia.cli import app
from mapa_da_ciencia.coleta import OpcoesColeta, coletar
from mapa_da_ciencia.config import ErroConfig
from mapa_da_ciencia.llm.perfis import PERFIS
from mapa_da_ciencia.projeto import Projeto

runner = CliRunner()


@pytest.fixture
def projeto(tmp_path):
    return Projeto.criar(
        tmp_path / "busca", modelo="vazio", perfil=PERFIS["leve"], revistas=["0104-6276"], anos=(2024, 2024)
    )


def test_busca_por_termo_nas_revistas_do_recorte(projeto, apis_falsas):
    resumo = coletar(projeto, OpcoesColeta(consulta="eleitoral"))
    docs = ler_documentos(projeto.dados / ARQUIVO)
    assert len(docs) == resumo.documentos == 4
    # os resultados do OpenAlex viram registros completos da ArticleMeta, achados pelo DOI na lista da revista
    assert all(d.fonte == "articlemeta" and d.pid and d.casamento == "1_doi" for d in docs)
    assert all(d.origens == ["consulta:eleitoral"] for d in docs)
    assert all("eleitoral" in " ".join(t.texto.lower() for t in d.titulos) for d in docs)
    assert resumo.creditos_openalex == 11  # uma página de busca e um lote de instituições


def test_busca_ampla_demais_para_antes_de_gastar_creditos(projeto, apis_falsas):
    apis_falsas.total_forcado = 50_000
    with pytest.raises(ErroConfig, match="refine a consulta"):
        coletar(projeto, OpcoesColeta(consulta="política"))


def test_busca_exige_openalex(projeto, apis_falsas):
    with pytest.raises(ErroConfig, match="OpenAlex"):
        coletar(projeto, OpcoesColeta(consulta="eleitoral", sem_openalex=True))


def test_cli_consulta(projeto, apis_falsas):
    r = runner.invoke(app, ["coletar", "-P", str(projeto.raiz), "--consulta", "eleitoral"])
    assert r.exit_code == 0, r.output
    assert "4 documento(s)" in r.output
