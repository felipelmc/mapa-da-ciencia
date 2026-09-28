"""`mapa status`: o mesmo estado das etapas do painel, a classificação principal e as mensagens de erro."""

import json
import re
import time

import pytest
from typer.testing import CliRunner

import mapa_da_ciencia.api as mapa
from mapa_da_ciencia.cli import app
from mapa_da_ciencia.coleta import coletar
from mapa_da_ciencia.contrato.exportar import exportar
from mapa_da_ciencia.llm.perfis import PERFIS
from mapa_da_ciencia.manifesto import ultima_execucao
from mapa_da_ciencia.projeto import Projeto
from mapa_da_ciencia.validacao import amostra as va

runner = CliRunner()
ENV = {"COLUMNS": "200"}


@pytest.fixture
def projeto(tmp_path, apis_falsas):
    p = Projeto.criar(
        tmp_path / "op", modelo="ciencia-politica", perfil=PERFIS["leve"], revistas=["0104-6276"], anos=(2024, 2024)
    )
    coletar(p)
    cfg = p.raiz / "mapa.yaml"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace("n: 200", "n: 10"), encoding="utf-8")
    return Projeto.abrir(p.raiz)


def _linha(projeto, etapa: str) -> str:
    """A linha da etapa na tabela do `mapa status`, sem as bordas."""
    r = runner.invoke(app, ["status", "-P", str(projeto.raiz)], env=ENV)
    assert r.exit_code == 0, r.output
    linha = next(x for x in r.output.splitlines() if re.search(rf"│ {etapa} +│", x))
    return " ".join(linha.replace("│", " ").split())


def _ficha_completa(projeto) -> dict:
    respostas = {}
    for v in projeto.codebook.variaveis:
        valor = {"booleana": True, "texto": "algum texto"}.get(v.tipo)
        if valor is None:
            valor = [v.categorias[0].valor] if v.tipo == "multipla" else v.categorias[0].valor
        respostas[v.id] = {"valor": valor, "evidencia": ""}
    return respostas


def test_status_mostra_a_validacao_como_o_painel(projeto, tmp_path):
    """A validação não fica "pendente" para sempre: incompleta com a amostra sorteada, em dia com todas as fichas
    completas, e o relatório registra a execução (r1-02, r5-05)."""
    a = va.sortear(projeto)
    assert _linha(projeto, "validacao").startswith("validacao incompleta 0 de 10 codificados")
    arquivo = tmp_path / "fichas.jsonl"
    arquivo.write_text("\n".join(json.dumps({"doc": d, "respostas": _ficha_completa(projeto)}) for d in a.docs))
    mapa.importar_codificacoes(projeto, arquivo, "ana")
    assert _linha(projeto, "validacao").startswith("validacao em dia 10 de 10 codificados")
    r = runner.invoke(app, ["validar", "relatorio", "-P", str(projeto.raiz)], env=ENV)
    assert r.exit_code == 0, r.output
    m = ultima_execucao(projeto, "validacao")
    assert m["contagens"]["codificados"] == 10 and m["hash_codebook"] == projeto.codebook.hash()
    assert _linha(projeto, "validacao").endswith("10 codificados")


def test_status_mostra_a_classificacao_incompleta_e_desatualizada(projeto):
    """A tabela usa o estado da etapa, e não só "concluída" quando há um manifesto (r5-05)."""
    mapa.classificar(projeto, estimar=True, progresso=False)
    assert _linha(projeto, "classificacao").startswith("classificacao incompleta")
    mapa.classificar(projeto, progresso=False)
    assert _linha(projeto, "classificacao").startswith("classificacao em dia")
    cb = projeto.raiz / "codebook.yaml"
    cb.write_text(cb.read_text(encoding="utf-8").replace('versao: "0.1"', 'versao: "0.2"'), encoding="utf-8")
    assert _linha(projeto, "classificacao").startswith("classificacao desatualizada")


def test_comparacao_e_so_a_amostra_nao_viram_a_classificacao_do_projeto(projeto):
    """Uma rodada de comparação (`--modelo X --somente-amostra`) depois da completa não toma o lugar dela no status
    nem na duração publicada (r1-03)."""
    completa = mapa.classificar(projeto, progresso=False)
    va.sortear(projeto)
    time.sleep(1.05)  # o manifesto de cada execução tem o segundo no nome
    mapa.classificar(projeto, modelo="qwen3.5:9b", somente_amostra=True, progresso=False)
    assert ultima_execucao(projeto, "classificacao")["modelos"]["classificacao"].startswith("qwen3.5:9b@")
    assert _linha(projeto, "classificacao").endswith(f"{completa.classificados} classificados")
    from mapa_da_ciencia.manifesto import da_classificacao_principal

    principal = ultima_execucao(projeto, "classificacao", da_classificacao_principal(projeto))
    assert principal["modelos"]["classificacao"].startswith("qwen3.5:4b@")
    exportar(projeto)
    publicado = json.loads((projeto.saida / "dados" / "manifesto.json").read_text(encoding="utf-8"))
    assert publicado["execucao"]["duracao_s"]["classificacao"] == round(principal["duracao_s"], 1)
    assert publicado["execucao"]["modelos"]["classificacao"].startswith("qwen3.5:4b@")


@pytest.mark.parametrize(
    ("anos", "esperado"),
    [("[2025, 2010]", "recorte.anos: use [ano_inicial, ano_final]"), ("2024", "use [ano_inicial, ano_final]")],
)
def test_erro_de_anos_nao_perde_o_que_esta_entre_colchetes(tmp_path, anos, esperado):
    """O Rich não come o "[ano_inicial, ano_final]" da mensagem, e `anos: 2024` ganha a mesma dica (r5-11)."""
    p = Projeto.criar(tmp_path / "p", modelo="vazio", perfil=PERFIS["leve"], anos=(2010, 2020))
    arq = p.raiz / "mapa.yaml"
    arq.write_text(re.sub(r"anos: \[2010, 2020\]", f"anos: {anos}", arq.read_text(encoding="utf-8")), encoding="utf-8")
    r = runner.invoke(app, ["status", "-P", str(p.raiz)], env=ENV)
    assert r.exit_code == 1 and esperado in " ".join(r.output.split()), r.output


def test_o_status_mostra_a_execucao_que_gerou_o_resultado(projeto, apis_falsas):
    """O manifesto mostrado (no status, no painel e na duração publicada) é o da execução do resultado principal:
    um --somente-amostra que gravou o principal conta; um que só repetiu a rodada completa não toma o lugar dela."""
    from mapa_da_ciencia.classificacao.resultado import PASTA, Resultado
    from mapa_da_ciencia.manifesto import estados_das_etapas, ultima_classificacao

    def dados():
        return Resultado.ler(projeto.dados / PASTA, "qwen3.5:4b", projeto.codebook.hash())

    mapa.classificar(projeto, limite=12, progresso=False)  # parcial, versão 1
    va.sortear(projeto)
    time.sleep(1.05)
    apis_falsas.digests["qwen3.5:4b"] = "novo0000000000000"
    mapa.classificar(projeto, somente_amostra=True, progresso=False)  # grava o principal: o anterior era parcial
    m = ultima_classificacao(projeto)
    assert dados().modelo.endswith("@novo00000000") and m["modelos"]["classificacao"] == dados().modelo
    assert estados_das_etapas(projeto)["classificacao"]["ultima"]["contagens"]["classificados"] == dados().classificados
    exportar(projeto)
    publicado = json.loads((projeto.saida / "dados" / "manifesto.json").read_text(encoding="utf-8"))
    assert publicado["execucao"]["duracao_s"]["classificacao"] == round(m["duracao_s"], 1)

    time.sleep(1.05)
    completa = mapa.classificar(projeto, progresso=False)  # a rodada completa da mesma versão
    time.sleep(1.05)
    mapa.classificar(projeto, somente_amostra=True, progresso=False)  # só a amostra, tudo do cache
    m = ultima_classificacao(projeto)
    assert not m["parametros"]["somente_amostra"] and m["contagens"]["novos"] == completa.novos > 0
