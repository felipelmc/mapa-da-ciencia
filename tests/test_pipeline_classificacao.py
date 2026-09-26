"""A etapa de classificação de ponta a ponta: `mapa classificar`, `api.classificar`, status e a view."""

import pytest
from typer.testing import CliRunner

import mapa_da_ciencia.api as mapa
from mapa_da_ciencia.classificacao.pipeline import AMOSTRA_ESTIMATIVA, classificacao_em_dia
from mapa_da_ciencia.classificacao.resultado import PASTA, Resultado
from mapa_da_ciencia.cli import app
from mapa_da_ciencia.coleta import coletar
from mapa_da_ciencia.llm.perfis import PERFIS
from mapa_da_ciencia.manifesto import ultima_execucao
from mapa_da_ciencia.projeto import Projeto

runner = CliRunner()


@pytest.fixture
def projeto(tmp_path, apis_falsas):
    p = Projeto.criar(
        tmp_path / "op", modelo="ciencia-politica", perfil=PERFIS["leve"], revistas=["0104-6276"], anos=(2024, 2024)
    )
    coletar(p)
    return p


def test_estimar_limite_e_completar(projeto, apis_falsas):
    assert classificacao_em_dia(projeto) is None
    r = mapa.classificar(projeto, estimar=True, progresso=False)
    assert r.classificados == r.novos == AMOSTRA_ESTIMATIVA and r.parcial
    assert r.pendentes == r.documentos - AMOSTRA_ESTIMATIVA and r.estimativa_restante_s is not None
    assert classificacao_em_dia(projeto) is False  # incompleta

    r = mapa.classificar(projeto, limite=10, progresso=False)
    assert (r.classificados, r.do_cache, r.novos) == (10, AMOSTRA_ESTIMATIVA, 5)

    r = mapa.classificar(projeto, progresso=False)
    assert r.classificados == r.documentos and not r.parcial and r.json_valido_na_primeira == 1.0
    assert r.evidencia["literal"] == 1.0 and r.do_cache == 10
    assert classificacao_em_dia(projeto) is True
    chamadas = apis_falsas.chamadas["ollama_chat"]
    r = mapa.classificar(projeto, progresso=False)
    assert r.novos == 0 and apis_falsas.chamadas["ollama_chat"] == chamadas  # tudo do cache

    m = ultima_execucao(projeto, "classificacao")
    assert m["contagens"]["classificados"] == r.documentos and m["hash_codebook"] == projeto.codebook.hash()
    assert m["modelos"]["classificacao"].startswith("qwen3.5:4b@")
    with mapa.conectar(projeto) as con:
        n, variaveis = con.execute("SELECT count(*), count(DISTINCT variavel) FROM classificacoes").fetchone()
    assert variaveis == len(projeto.codebook.variaveis) and n == r.documentos * variaveis


def test_outro_modelo_para_comparar(projeto):
    mapa.classificar(projeto, limite=3, modelo="qwen3.5:9b", progresso=False)
    pasta = projeto.dados / PASTA
    assert Resultado.ler(pasta, "qwen3.5:9b", projeto.codebook.hash()).classificados == 3
    assert classificacao_em_dia(projeto) is None  # o principal (qwen3.5:4b) ainda não rodou


def test_cli_e_status(projeto):
    raiz = str(projeto.raiz)
    s = runner.invoke(app, ["status", "-P", raiz], env={"COLUMNS": "160"})
    assert "Classificação: ainda não feita" in s.output
    r = runner.invoke(app, ["classificar", "-P", raiz, "--estimar"], env={"COLUMNS": "160"})
    assert r.exit_code == 0, r.output
    assert "Classificação pronta" in r.output and "Estimativa:" in r.output and "Abordagem" in r.output
    s = runner.invoke(app, ["status", "-P", raiz], env={"COLUMNS": "160"})
    assert "Classificação: 5 de" in s.output and "incompleta" in s.output
    # um codebook novo deixa a classificação para trás
    cb = projeto.raiz / "codebook.yaml"
    cb.write_text(cb.read_text(encoding="utf-8").replace('versao: "0.1"', 'versao: "0.2"'), encoding="utf-8")
    s = runner.invoke(app, ["status", "-P", raiz], env={"COLUMNS": "160"})
    assert "de outro codebook" in s.output
