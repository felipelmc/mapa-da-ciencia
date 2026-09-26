"""A etapa de geografia de ponta a ponta: `mapa geografia`, `api.geografia`, status e views."""

import pytest
from typer.testing import CliRunner

import mapa_da_ciencia.api as mapa
from mapa_da_ciencia.armazenamento import ARQUIVO, ler_documentos
from mapa_da_ciencia.cli import app
from mapa_da_ciencia.coleta import coletar
from mapa_da_ciencia.geografia.pipeline import geografia_em_dia
from mapa_da_ciencia.geografia.resultado import PASTA, Resultado, ler_instituicoes, ler_pesos
from mapa_da_ciencia.llm.perfis import PERFIS
from mapa_da_ciencia.manifesto import ultima_execucao
from mapa_da_ciencia.projeto import Projeto

runner = CliRunner()


@pytest.fixture
def projeto(tmp_path, apis_falsas):
    p = Projeto.criar(tmp_path / "op", modelo="vazio", perfil=PERFIS["leve"], revistas=["0104-6276"], anos=(2024, 2024))
    coletar(p)
    return p


def test_mapa_geografia_e_status(projeto):
    raiz = str(projeto.raiz)
    antes = runner.invoke(app, ["status", "-P", raiz], env={"COLUMNS": "160"})
    assert "Geografia: ainda não gerada" in antes.output
    r = runner.invoke(app, ["geografia", "-P", raiz], env={"COLUMNS": "160"})
    assert r.exit_code == 0, r.output
    assert "Geografia pronta" in r.output and "Fonte das afiliações" in r.output and "Instituição" in r.output
    s = runner.invoke(app, ["status", "-P", raiz], env={"COLUMNS": "160"})
    assert "vínculos ligados a uma de" in s.output and "geografia" in s.output
    assert geografia_em_dia(projeto) is True
    assert ultima_execucao(projeto, "geografia")["contagens"]["documentos"] == 25


def test_resultado_em_disco_e_invariantes(projeto):
    resumo = mapa.geografia(projeto, progresso=False)
    pasta = projeto.dados / PASTA
    resultado = Resultado.ler(pasta)
    assert resultado is not None and resultado.contagens["vinculos"] == resumo.vinculos
    pesos = ler_pesos(pasta)
    assert sum(p["peso"] for p in pesos) == pytest.approx(25)
    instituicoes = {i["id"]: i for i in ler_instituicoes(pasta)}
    usadas = {p["instituicao"] for p in pesos} - {None, "nao-identificada"}
    assert usadas == set(instituicoes)
    assert all(i["documentos"] >= i["peso"] - 1e-9 for i in instituicoes.values())
    assert "vínculos de 25 documentos" in str(resumo)
    with mapa.conectar(projeto) as con:
        n = con.execute("SELECT count(*) FROM vinculos").fetchone()[0]
        total = con.execute("SELECT sum(peso) FROM pesos").fetchone()[0]
        nomes = con.execute("SELECT count(*) FROM instituicoes WHERE nome IS NOT NULL").fetchone()[0]
    assert n == resumo.vinculos and total == pytest.approx(25) and nomes == len(instituicoes)


def test_desatualizada_depois_de_mudar_o_corpus_ou_as_correcoes(projeto):
    mapa.geografia(projeto, progresso=False)
    assert geografia_em_dia(projeto) is True
    (projeto.raiz / "instituicoes.yaml").write_text("apelidos: {}\n", encoding="utf-8")
    assert geografia_em_dia(projeto) is False
    mapa.geografia(projeto, progresso=False)
    assert geografia_em_dia(projeto) is True
    from mapa_da_ciencia.armazenamento import gravar_documentos

    docs = ler_documentos(projeto.dados / ARQUIVO)
    gravar_documentos(docs[:-1], projeto.dados / ARQUIVO)
    assert geografia_em_dia(projeto) is False
    s = runner.invoke(app, ["status", "-P", str(projeto.raiz)], env={"COLUMNS": "160"})
    assert "A geografia é de antes" in s.output


def test_sem_corpus(tmp_path):
    p = Projeto.criar(tmp_path / "vazio", modelo="vazio", perfil=PERFIS["leve"])
    r = runner.invoke(app, ["geografia", "-P", str(p.raiz)])
    assert r.exit_code != 0 and "mapa coletar" in r.output
