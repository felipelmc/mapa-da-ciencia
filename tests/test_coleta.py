import httpx
import pytest
import yaml
from typer.testing import CliRunner

from mapa_da_ciencia.armazenamento import ARQUIVO, ler_documentos
from mapa_da_ciencia.cli import app
from mapa_da_ciencia.coleta import OpcoesColeta, coletar, interpretar_anos
from mapa_da_ciencia.config import ErroConfig
from mapa_da_ciencia.contrato.modelos import Manifesto, Revistas
from mapa_da_ciencia.fontes.base import ErroFonte, FaltaNoCache
from mapa_da_ciencia.llm.perfis import PERFIS
from mapa_da_ciencia.manifesto import ultima_execucao
from mapa_da_ciencia.projeto import Projeto
from mapa_da_ciencia.texto import EMAIL, contem_email

runner = CliRunner()


@pytest.fixture
def projeto(tmp_path):
    return Projeto.criar(
        tmp_path / "op-2024", modelo="vazio", perfil=PERFIS["leve"], revistas=["0104-6276"], anos=(2024, 2024)
    )


def test_interpretar_anos():
    assert interpretar_anos("2024") == (2024, 2024)
    assert interpretar_anos("2010-2025") == (2010, 2025)
    assert interpretar_anos("2010–2025") == (2010, 2025)
    for ruim in ("2025-2010", "abc", "2010-2011-2012"):
        with pytest.raises(ErroConfig):
            interpretar_anos(ruim)


def test_novo_com_revista_e_anos_mantem_comentarios(projeto):
    texto = (projeto.raiz / "mapa.yaml").read_text()
    assert "- 0104-6276           # Opinião Pública" in texto
    assert "anos: [2024, 2024]" in texto
    assert "# Configuração do projeto" in texto  # comentários preservados
    assert projeto.config.fontes.scielo.revistas == ["0104-6276"]
    assert projeto.config.titulo == "Opinião Pública" and projeto.config.descricao == ""


def test_novo_com_varias_revistas_no_modelo_do_piloto(tmp_path):
    p = Projeto.criar(tmp_path / "x", modelo="ciencia-politica", perfil=PERFIS["leve"], revistas=["op", "dados"])
    assert p.config.titulo == "2 revistas do SciELO Brasil" and p.config.descricao == ""
    assert p.config.fontes.scielo.revistas == ["0104-6276", "0011-5258"]
    assert "# Configuração do projeto" in (p.raiz / "mapa.yaml").read_text()


def test_novo_com_revista_desconhecida(tmp_path):
    with pytest.raises(ErroConfig, match="não encontrada"):
        Projeto.criar(tmp_path / "x", modelo="vazio", perfil=PERFIS["leve"], revistas=["9999-9999"])


def test_coleta_opiniao_publica_2024(projeto, apis_falsas):
    resumo = coletar(projeto)
    assert resumo.documentos == 25 and resumo.por_revista == {"op": 25}
    assert resumo.fora_do_periodo == 15 and resumo.nao_encontrados == 0
    assert resumo.requisicoes["articlemeta"] == 26 == apis_falsas.chamadas["articlemeta"]
    docs = ler_documentos(projeto.dados / ARQUIVO)
    assert len(docs) == 25 and all(d.ano == 2024 for d in docs)
    m = ultima_execucao(projeto, "coleta")
    assert m["contagens"]["documentos"] == 25 and m["parametros"]["revistas"] == ["0104-6276"]


def test_exporta_manifesto_e_revistas_para_o_painel(projeto, apis_falsas):
    coletar(projeto)
    dados = projeto.saida / "dados"
    manifesto = Manifesto.model_validate_json((dados / "manifesto.json").read_text())
    assert manifesto.contagens.documentos == 25 and manifesto.contagens.com_afiliacao == 25
    assert manifesto.arquivos == ["manifesto", "revistas"] and not manifesto.api
    assert manifesto.licencas == {"cc-by": 25} and "coleta" in manifesto.execucao.duracao_s
    revistas = Revistas.model_validate_json((dados / "revistas.json").read_text()).revistas
    assert [(r.id, r.issn, r.n) for r in revistas] == [("op", "0104-6276", 25)]
    assert revistas[0].titulo == "Opinião Pública" and revistas[0].areas  # áreas vêm do retrato empacotado


def test_nenhum_email_no_parquet_nem_em_saida(projeto, apis_falsas):
    coletar(projeto)  # as fixtures da ArticleMeta têm e-mails (falsos) em vários campos
    assert not any(contem_email(d.model_dump()) for d in ler_documentos(projeto.dados / ARQUIVO))
    arquivos = list(projeto.saida.rglob("*.json"))
    assert arquivos and not any(EMAIL.search(a.read_text()) for a in arquivos)


def test_segunda_execucao_nao_faz_requisicoes(projeto, apis_falsas):
    coletar(projeto)
    resumo = coletar(projeto)
    assert resumo.total_requisicoes == 0 and resumo.documentos == 25
    assert apis_falsas.chamadas["articlemeta"] == 26


def test_limite(projeto, apis_falsas):
    resumo = coletar(projeto, OpcoesColeta(limite=5))
    assert resumo.documentos == 5 and apis_falsas.chamadas["articlemeta"] == 6


def test_offline(projeto, apis_falsas):
    with pytest.raises(FaltaNoCache):
        coletar(projeto, OpcoesColeta(offline=True))
    coletar(projeto)
    resumo = coletar(projeto, OpcoesColeta(offline=True))
    assert resumo.documentos == 25 and resumo.total_requisicoes == 0


def test_retomada_depois_de_falha_busca_so_o_que_falta(projeto, apis_falsas):
    original = apis_falsas._artigo
    feitos = {"n": 0}

    def cai_depois_de_10(request):
        feitos["n"] += 1
        if feitos["n"] > 10:
            return httpx.Response(404)
        return original(request)

    apis_falsas.router.get("https://articlemeta.scielo.org/api/v1/article/").mock(side_effect=cai_depois_de_10)
    with pytest.raises(ErroFonte):
        coletar(projeto)
    assert not list(projeto.brutos.rglob("*.tmp"))
    guardados = len(list((projeto.brutos / "articlemeta" / "artigos").glob("*.json.gz")))
    assert guardados >= 10
    apis_falsas.router.get("https://articlemeta.scielo.org/api/v1/article/").mock(side_effect=original)
    antes = apis_falsas.chamadas["articlemeta"]
    resumo = coletar(projeto)
    assert resumo.documentos == 25
    assert apis_falsas.chamadas["articlemeta"] - antes == 25 - guardados


def test_revista_so_nesta_execucao_gera_aviso(projeto, apis_falsas):
    resumo = coletar(projeto, OpcoesColeta(revistas=["op"], anos=(2023, 2024)))
    assert any("anos desta execução" in a for a in resumo.avisos)
    assert resumo.plano.anos == (2023, 2024)  # as fixtures só têm registros de 2024
    assert ultima_execucao(projeto, "coleta")["parametros"]["anos"] == [2023, 2024]


def test_cli_novo_coletar_e_status(tmp_path, apis_falsas, monkeypatch):
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(app, ["novo", "op-2024", "--modelo", "vazio", "--revista", "op", "--anos", "2024"])
    assert r.exit_code == 0, r.output
    assert yaml.safe_load((tmp_path / "op-2024" / "mapa.yaml").read_text())["recorte"]["anos"] == [2024, 2024]
    r = runner.invoke(app, ["status", "-P", "op-2024"])
    assert r.exit_code == 0 and "nenhum documento coletado ainda" in r.output
    r = runner.invoke(app, ["coletar", "-P", "op-2024"])
    assert r.exit_code == 0, r.output
    assert "Coleta concluída" in r.output and "25" in r.output
    r = runner.invoke(app, ["status", "-P", "op-2024"])
    assert r.exit_code == 0, r.output
    assert "Corpus: 25 documento(s), 2024" in r.output and "com resumo" in r.output
    assert "25 documentos" in r.output  # resultado da etapa de coleta
    r = runner.invoke(app, ["coletar", "-P", "op-2024"])
    assert "0 requisição(ões), 26 resposta(s) do cache" in r.output
    r = runner.invoke(app, ["coletar", "-P", "op-2024", "--anos", "abc"])
    assert r.exit_code == 1 and "Anos inválidos" in r.output
