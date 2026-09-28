import pytest
from corpus_sintetico import corpus_sintetico
from typer.testing import CliRunner

import mapa_da_ciencia.api as mapa
from mapa_da_ciencia.armazenamento import ARQUIVO, gravar_documentos
from mapa_da_ciencia.cli import app
from mapa_da_ciencia.llm.perfis import PERFIS
from mapa_da_ciencia.projeto import Projeto

runner = CliRunner()


@pytest.fixture
def projeto(tmp_path, apis_falsas):
    p = Projeto.criar(tmp_path / "sintetico", modelo="vazio", perfil=PERFIS["leve"])
    docs, _ = corpus_sintetico()
    gravar_documentos(docs, p.dados / ARQUIVO)
    return p


def test_mapa_topicos_e_status(projeto):
    raiz = str(projeto.raiz)
    antes = runner.invoke(app, ["status", "-P", raiz], env={"COLUMNS": "140"})
    assert "Tópicos: ainda não gerados" in antes.output
    r = runner.invoke(app, ["topicos", "-P", raiz], env={"COLUMNS": "140"})
    assert r.exit_code == 0, r.output
    assert "Tópicos prontos" in r.output and "Macrotema" in r.output and "chamada(s) ao modelo" in r.output
    s = runner.invoke(app, ["status", "-P", raiz], env={"COLUMNS": "140"})
    assert s.exit_code == 0 and "macrotemas (ARI" in s.output and "rótulos: llm" in s.output
    assert "embeddings" in s.output and "topicos" in s.output
    r = runner.invoke(app, ["topicos", "-P", raiz, "--sem-rotulos"], env={"COLUMNS": "140"})
    assert r.exit_code == 0 and "Rótulos: palavras-chave" in r.output


def test_status_avisa_topicos_desatualizados(projeto):
    runner.invoke(app, ["topicos", "-P", str(projeto.raiz), "--sem-rotulos"])
    docs, _ = corpus_sintetico()
    gravar_documentos(docs[:-1], projeto.dados / ARQUIVO)  # uma coleta nova mudou o corpus
    s = runner.invoke(app, ["status", "-P", str(projeto.raiz)], env={"COLUMNS": "140"})
    assert "antes da última coleta" in s.output


def test_modelo_de_rotulos_ausente_na_cli(projeto, apis_falsas):
    del apis_falsas.modelos_ollama["qwen3.5:4b"]
    r = runner.invoke(app, ["topicos", "-P", str(projeto.raiz)])
    assert r.exit_code == 1 and "--sem-rotulos" in r.output


def test_api_topicos_e_view_atribuicoes(projeto):
    resumo = mapa.topicos(projeto, progresso=False)
    assert "tópicos em" in str(resumo) and resumo.documentos == 300
    linhas = mapa.consultar(projeto, "SELECT count(*) AS n, count(DISTINCT topico) AS t FROM atribuicoes")
    assert linhas[0]["n"] == 300 and linhas[0]["t"] >= resumo.topicos


def test_topicos_num_projeto_sem_coleta(tmp_path, apis_falsas):
    """Rodar os tópicos antes da coleta é um erro comum de quem começa: a mensagem diz o que fazer."""
    p = Projeto.criar(tmp_path / "novo", modelo="vazio", perfil=PERFIS["leve"])
    r = runner.invoke(app, ["topicos", "-P", str(p.raiz), "--sem-rotulos"], env={"COLUMNS": "200"})
    assert r.exit_code == 1 and "Rode `mapa coletar` antes" in r.output, r.output
    assert r.exception is None or isinstance(r.exception, SystemExit)
