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


def test_corpus_vazio_na_cli(tmp_path, apis_falsas):
    """Uma revista sem artigos no período: os tópicos e a amostra explicam o que fazer, sem traceback (r1-09)."""
    from mapa_da_ciencia.coleta import coletar

    p = Projeto.criar(
        tmp_path / "vazio", modelo="ciencia-politica", perfil=PERFIS["leve"], revistas=["0104-6276"], anos=(1990, 1991)
    )
    coletar(p)
    for comando, mensagem in (
        (["topicos", "--sem-rotulos"], "O corpus tem 0 documento(s) com texto"),
        (["validar", "amostra"], "Nenhum documento com resumo para sortear"),
    ):
        r = runner.invoke(app, [*comando, "-P", str(p.raiz)], env={"COLUMNS": "200"})
        assert r.exit_code == 1 and mensagem in " ".join(r.output.split()), (comando, r.output)
        assert r.exception is None or isinstance(r.exception, SystemExit), comando


def test_rotulos_do_cache_nao_exigem_memoria(projeto, apis_falsas, monkeypatch):
    """Rodar os tópicos de novo com todos os rótulos no cache não checa a memória do modelo de rótulos (r1-07)."""
    from mapa_da_ciencia import recursos

    mapa.topicos(projeto, progresso=False)
    chats = apis_falsas.chamadas["ollama_chat"]
    # outro processo ocupa a máquina: só 1 GB livre, pouco para carregar o modelo de rótulos (0,5 GB e a margem)
    monkeypatch.setattr(recursos, "memoria", lambda: recursos.Memoria(24.0, 1.0, 0.0, 8.0))
    r = runner.invoke(app, ["topicos", "-P", str(projeto.raiz)], env={"COLUMNS": "200"})
    assert r.exit_code == 0, r.output
    saida = " ".join(r.output.split())
    assert apis_falsas.chamadas["ollama_chat"] == chats and "): 0 chamada(s) ao modelo" in saida
