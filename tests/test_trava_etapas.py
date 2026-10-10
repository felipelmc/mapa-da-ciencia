"""Uma etapa por vez em cada projeto, entre a linha de comando, o notebook e o painel (trava_etapas.py)."""

import json
import subprocess
import sys
import textwrap
import threading

import pytest
from typer.testing import CliRunner

from mapa_da_ciencia.cli import app
from mapa_da_ciencia.llm.perfis import PERFIS
from mapa_da_ciencia.projeto import Projeto
from mapa_da_ciencia.trava_etapas import ARQUIVO, EtapaEmAndamento, origem, quem_roda, uma_etapa_por_vez

pytest.importorskip("fcntl")  # sem fcntl (Windows), não há trava


@pytest.fixture
def projeto(tmp_path):
    return Projeto.criar(tmp_path / "p", modelo="vazio", perfil=PERFIS["leve"], revistas=["0104-6276"])


def _em_outra_thread(projeto, etapa="topicos"):
    """Tenta a trava numa thread nova e devolve o erro (ou None)."""
    resultado = {}

    def tentar():
        try:
            with uma_etapa_por_vez(projeto, etapa):
                resultado["erro"] = None
        except EtapaEmAndamento as e:
            resultado["erro"] = e

    t = threading.Thread(target=tentar)
    t.start()
    t.join()
    return resultado["erro"]


def test_outra_thread_nao_comeca_e_a_mesma_thread_reentra(projeto):
    assert quem_roda(projeto) is None
    with uma_etapa_por_vez(projeto, "coleta"):
        dono = quem_roda(projeto)
        assert dono["etapa"] == "coleta" and dono["origem"] == "terminal"
        erro = _em_outra_thread(projeto)
        assert erro is not None and "coleta" in str(erro) and "outro terminal ou notebook" in str(erro)
        with uma_etapa_por_vez(projeto, "classificacao"):  # a votação do júri chama a classificação
            assert quem_roda(projeto)["etapa"] == "coleta"
        assert quem_roda(projeto)["etapa"] == "coleta"
    assert quem_roda(projeto) is None and _em_outra_thread(projeto) is None
    assert ARQUIVO in (projeto.raiz / ".gitignore").read_text().split()


def test_a_etapa_do_painel_diz_o_endereco(projeto):
    (projeto.raiz / ".painel.lock").write_text(json.dumps({"pid": 1, "porta": 8765}))
    with origem("painel"), uma_etapa_por_vez(projeto, "topicos"):
        erro = _em_outra_thread(projeto, "coleta")
    assert "pelo painel (http://127.0.0.1:8765/)" in str(erro) and "topicos" in str(erro)


def test_a_trava_de_um_processo_que_morreu_fica_livre(projeto):
    # um processo segura a trava; o mapa geografia no terminal não começa; morto o processo, a trava está livre
    segurar = textwrap.dedent(
        f"""
        import sys
        from mapa_da_ciencia.projeto import Projeto
        from mapa_da_ciencia.trava_etapas import uma_etapa_por_vez
        with uma_etapa_por_vez(Projeto.abrir({str(projeto.raiz)!r}), "classificacao"):
            print("pronto", flush=True)
            sys.stdin.read()
        """
    )
    proc = subprocess.Popen([sys.executable, "-c", segurar], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert proc.stdout.readline().strip() == "pronto"
        assert quem_roda(projeto)["pid"] == proc.pid
        r = CliRunner().invoke(app, ["geografia", "-P", str(projeto.raiz)], env={"COLUMNS": "200"})
        assert r.exit_code == 1 and "classificacao" in r.output and "outro terminal ou notebook" in r.output
    finally:
        proc.kill()
        proc.wait()
    assert quem_roda(projeto) is None  # o arquivo ainda tem o PID, mas o processo não existe mais
    assert _em_outra_thread(projeto) is None


def test_as_etapas_que_escrevem_no_projeto_sao_travadas():
    from mapa_da_ciencia import coleta, publicar
    from mapa_da_ciencia.classificacao import pipeline as classificacao
    from mapa_da_ciencia.geografia import pipeline as geografia
    from mapa_da_ciencia.juri import pipeline as juri
    from mapa_da_ciencia.juri import relatorio as relatorio_juri
    from mapa_da_ciencia.juri import supervisor, votacao
    from mapa_da_ciencia.redes import pipeline as redes
    from mapa_da_ciencia.topicos import pipeline as topicos
    from mapa_da_ciencia.validacao import amostra
    from mapa_da_ciencia.validacao import relatorio as relatorio_validacao

    travadas = [
        coleta.coletar,
        topicos.gerar_topicos,
        geografia.gerar_geografia,
        redes.gerar_redes,
        classificacao.classificar,
        amostra.sortear,
        amostra.importar,
        relatorio_validacao.gerar,
        votacao.votar,
        juri.deliberar_juri,
        supervisor.exportar_pedidos,
        supervisor.importar_respostas,
        supervisor.supervisionar,
        relatorio_juri.gerar,
        publicar.publicar,
    ]
    assert all(getattr(f, "__etapa__", None) for f in travadas), [
        f.__name__ for f in travadas if not hasattr(f, "__etapa__")
    ]
