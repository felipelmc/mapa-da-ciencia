"""A etapa de classificação de ponta a ponta: `mapa classificar`, `api.classificar`, status e a view."""

import json
import os
import re
import time

import pytest
from typer.testing import CliRunner

import mapa_da_ciencia.api as mapa
from mapa_da_ciencia.classificacao.pipeline import AMOSTRA_ESTIMATIVA, classificacao_em_dia
from mapa_da_ciencia.classificacao.resultado import PASTA, Resultado
from mapa_da_ciencia.cli import app
from mapa_da_ciencia.coleta import coletar
from mapa_da_ciencia.llm.perfis import PERFIS
from mapa_da_ciencia.manifesto import da_classificacao_principal, ultima_execucao
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

    # depois da rodada completa, só a amostra (ou um limite) não encolhe a classificação: o cache entra inteiro
    mapa.amostra_de_validacao(projeto, n=5)
    for opcoes in ({"somente_amostra": True}, {"limite": 3}):
        r = mapa.classificar(projeto, progresso=False, **opcoes)
        assert r.classificados == r.documentos and not r.parcial and r.novos == 0
        assert classificacao_em_dia(projeto) is True


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


def test_grava_parcial_durante_a_rodada(projeto, monkeypatch):
    import mapa_da_ciencia.classificacao.pipeline as pipeline
    from mapa_da_ciencia.classificacao.executor import Classificador

    gravacoes = []
    original = Resultado.gravar
    monkeypatch.setattr(pipeline, "GRAVAR_A_CADA", 2)
    monkeypatch.setattr(
        Resultado, "gravar", lambda self, *a: (gravacoes.append(self.classificados), original(self, *a))
    )
    exportacoes = []
    monkeypatch.setattr(pipeline, "exportar", lambda p: exportacoes.append(1) or [])
    mapa.classificar(projeto, limite=5, progresso=False)
    assert gravacoes == [2, 4, 5] and len(exportacoes) == 3  # a cada 2 novos e no fim

    # interrompida no meio: o que já foi classificado vai para o resultado, marcado como parcial
    classificar = Classificador.classificar

    def interrompe(self, textos):
        for i, c in enumerate(classificar(self, textos)):
            if i == 7:
                raise KeyboardInterrupt
            yield c

    monkeypatch.setattr(Classificador, "classificar", interrompe)
    with pytest.raises(KeyboardInterrupt):
        mapa.classificar(projeto, progresso=False)
    r = Resultado.ler(projeto.dados / PASTA, "qwen3.5:4b", projeto.codebook.hash())
    assert r.classificados == 7 and r.parcial


def test_rodada_parcial_de_outra_execucao_nao_troca_o_resultado_completo(projeto, apis_falsas):
    """Um --estimar depois de o modelo ser atualizado no Ollama não troca a classificação completa pelos 5 novos."""
    r = mapa.classificar(projeto, progresso=False)
    completo = r.documentos
    time.sleep(1.05)  # o manifesto de cada execução tem o segundo no nome: o próximo não pode sobrescrever este
    apis_falsas.digests["qwen3.5:4b"] = "novo0000000000000"  # o modelo foi atualizado
    r = mapa.classificar(projeto, estimar=True, progresso=False)
    assert any("O resultado anterior (qwen3.5:4b, 25 documentos classificados) foi mantido" in a for a in r.avisos)
    guardado = Resultado.ler(projeto.dados / PASTA, "qwen3.5:4b", projeto.codebook.hash())
    assert guardado.classificados == completo and not guardado.parcial
    # o status e a duração publicada mostram a execução dos dados, e não o --estimar que não gravou
    m = ultima_execucao(projeto, "classificacao", da_classificacao_principal(projeto))
    assert m["modelos"]["classificacao"] == guardado.modelo and m["contagens"]["classificados"] == completo
    # a rodada completa com o modelo novo substitui
    r = mapa.classificar(projeto, progresso=False)
    guardado = Resultado.ler(projeto.dados / PASTA, "qwen3.5:4b", projeto.codebook.hash())
    assert not guardado.parcial and guardado.modelo.endswith("@novo00000000")


def _falhar(apis_falsas, fracao: float):
    """O chat responde algo que não é JSON para a `fracao` dos documentos, sempre os mesmos (pelo texto)."""
    import zlib

    original = apis_falsas.responder_chat

    def responder(corpo):
        documento = next(m["content"] for m in corpo["messages"] if m["role"] == "user")
        return "isto não é JSON" if zlib.crc32(documento.encode()) % 1000 < 1000 * fracao else original(corpo)

    apis_falsas.responder_chat = responder


@pytest.mark.parametrize("fracao", [1.0, 0.5])
def test_rodada_completa_com_falhas_demais_nao_troca_o_resultado_completo(projeto, apis_falsas, fracao):
    """Um modelo atualizado (ou um parâmetro novo) que devolve JSON inválido em tudo, ou na metade, não apaga a
    classificação completa anterior: ela fica, e as respostas da versão nova ficam à parte, com aviso na CLI e no
    `mapa status`."""
    completo = mapa.classificar(projeto, progresso=False)
    pasta, hash_cb = projeto.dados / PASTA, projeto.codebook.hash()
    antes = Resultado.ler(pasta, "qwen3.5:4b", hash_cb)
    time.sleep(1.05)  # o manifesto de cada execução tem o segundo no nome
    apis_falsas.digests["qwen3.5:4b"] = "novo0000000000000"
    _falhar(apis_falsas, fracao)
    r = runner.invoke(app, ["classificar", "-P", str(projeto.raiz)], env={"COLUMNS": "200"})
    saida = " ".join(r.output.split())
    assert r.exit_code == 0, r.output
    assert "mais que o limite para substituí-lo (1, 2% dos documentos)" in saida
    assert '"qwen3.5:4b (versão nova)"' in saida and "Documentos que falham sempre" in saida
    assert Resultado.ler(pasta, "qwen3.5:4b", hash_cb) == antes and classificacao_em_dia(projeto) is True
    a_parte = Resultado.ler(pasta, "qwen3.5:4b", hash_cb, a_parte=True)
    assert a_parte.modelo.endswith("@novo00000000") and len(a_parte.falhas) > 1
    assert a_parte.classificados + len(a_parte.falhas) == completo.documentos
    m = ultima_execucao(projeto, "classificacao")
    assert m["parametros"]["gravado"] is False
    m = ultima_execucao(projeto, "classificacao", da_classificacao_principal(projeto))
    assert m["modelos"]["classificacao"] == antes.modelo
    exportado = json.loads((projeto.saida / "dados" / "manifesto.json").read_text(encoding="utf-8"))
    assert exportado["execucao"]["modelos"]["classificacao"] == antes.modelo
    assert exportado["contagens"]["classificados"] == completo.documentos
    s = runner.invoke(app, ["status", "-P", str(projeto.raiz)], env={"COLUMNS": "200"})
    assert "Uma versão nova (qwen3.5:4b@novo00000000) está à parte e não substituiu esta" in " ".join(s.output.split())


def test_status_explica_o_documento_que_falha_sempre(projeto, apis_falsas):
    """Com uma falha determinística, a classificação fica incompleta: o `mapa status` diz por quê, sem mandar só
    rodar de novo."""
    _falhar_sempre_num_documento(apis_falsas)
    r = mapa.classificar(projeto, progresso=False)
    assert len(r.falhas) == 1 and classificacao_em_dia(projeto) is False
    s = " ".join(runner.invoke(app, ["status", "-P", str(projeto.raiz)], env={"COLUMNS": "200"}).output.split())
    assert f"1 documento(s) sem resposta válida nas duas tentativas (por exemplo {r.falhas[0]})" in s
    assert "Documentos que falham sempre" in s and "para completá-la" not in s


def _falhar_sempre_num_documento(apis_falsas):
    """O chat responde algo que não é JSON para um documento, nas duas tentativas (uma falha determinística, como
    com temperatura 0 e semente fixa)."""
    original, alvo = apis_falsas.responder_chat, []

    def responder(corpo):
        documento = next(m["content"] for m in corpo["messages"] if m["role"] == "user")
        alvo[:] = alvo or [documento]
        return "isto não é JSON" if documento == alvo[0] else original(corpo)

    apis_falsas.responder_chat = responder


def test_rodada_completa_com_falhas_depois_de_atualizar_o_modelo_substitui(projeto, apis_falsas):
    """Uma rodada completa com uma falha pontual não é parcial no sentido da proteção: o resultado do modelo
    atualizado substitui o anterior, e o manifesto, o resultado e o painel falam do mesmo modelo."""
    r = mapa.classificar(projeto, progresso=False)
    total = r.documentos
    apis_falsas.digests["qwen3.5:4b"] = "novo0000000000000"  # `ollama pull` trouxe uma versão nova
    _falhar_sempre_num_documento(apis_falsas)
    r = mapa.classificar(projeto, progresso=False)
    assert (r.classificados, len(r.falhas), r.parcial) == (total - 1, 1, True)
    assert not any("resultado completo anterior" in a for a in r.avisos)
    guardado = Resultado.ler(projeto.dados / PASTA, "qwen3.5:4b", projeto.codebook.hash())
    assert guardado.modelo.endswith("@novo00000000") and guardado.classificados == total - 1 and guardado.parcial
    assert classificacao_em_dia(projeto) is False  # incompleta: o documento que falhou fica para a próxima rodada
    m = ultima_execucao(projeto, "classificacao", da_classificacao_principal(projeto))
    assert m["modelos"]["classificacao"] == guardado.modelo and m["parametros"]["gravado"]
    exportado = json.loads((projeto.saida / "dados" / "manifesto.json").read_text(encoding="utf-8"))
    assert exportado["execucao"]["modelos"]["classificacao"] == guardado.modelo
    assert exportado["contagens"]["classificados"] == total - 1


def test_somente_amostra_com_a_versao_nova_fica_a_parte_e_entra_nas_metricas(projeto, apis_falsas):
    """Medir na amostra um modelo atualizado (ou um parâmetro novo) sem rodar o corpus inteiro e sem trocar o
    resultado completo anterior, que continua no painel."""
    from mapa_da_ciencia.validacao.metricas import calcular

    mapa.classificar(projeto, progresso=False)
    pasta, hash_cb = projeto.dados / PASTA, projeto.codebook.hash()
    completo = Resultado.ler(pasta, "qwen3.5:4b", hash_cb)
    a = mapa.amostra_de_validacao(projeto, n=5)
    apis_falsas.digests["qwen3.5:4b"] = "novo0000000000000"
    r = runner.invoke(app, ["classificar", "-P", str(projeto.raiz), "--somente-amostra"], env={"COLUMNS": "200"})
    assert r.exit_code == 0 and '"qwen3.5:4b (versão nova)"' in " ".join(r.output.split()), r.output
    assert Resultado.ler(pasta, "qwen3.5:4b", hash_cb) == completo and classificacao_em_dia(projeto) is True
    a_parte = Resultado.ler(pasta, "qwen3.5:4b", hash_cb, a_parte=True)
    assert a_parte.modelo.endswith("@novo00000000") and a_parte.parcial and a_parte.classificados == len(a.docs)
    v = calcular(projeto, reamostras=10)
    assert [p.nome for p in v.participantes if p.tipo == "modelo"] == ["qwen3.5:4b", "qwen3.5:4b (versão nova)"]
    assert any(m.comparacao == "qwen3.5:4b × qwen3.5:4b (versão nova)" for m in v.metricas)
    # a rodada completa com a versão nova substitui o completo, e a amostra à parte, agora repetida, sai
    mapa.classificar(projeto, progresso=False)
    assert Resultado.ler(pasta, "qwen3.5:4b", hash_cb).modelo.endswith("@novo00000000")
    assert Resultado.ler(pasta, "qwen3.5:4b", hash_cb, a_parte=True) is None
    assert [p.nome for p in calcular(projeto, reamostras=10).participantes] == ["qwen3.5:4b"]


def test_codebook_editado_no_meio_da_etapa_nao_muda_o_hash_do_manifesto(projeto, monkeypatch):
    """O codebook.yaml salvo no editor enquanto a classificação roda: o manifesto registra o codebook que a etapa
    usou, o mesmo do resultado."""
    import os

    from mapa_da_ciencia.classificacao.executor import Classificador

    antes = projeto.codebook.hash()
    classificar, cb = Classificador.classificar, projeto.raiz / "codebook.yaml"

    def editando(self, textos):
        for i, c in enumerate(classificar(self, textos)):
            if i == 3:
                cb.write_text(
                    cb.read_text(encoding="utf-8").replace('versao: "0.1"', 'versao: "0.2"'), encoding="utf-8"
                )
                os.utime(cb, ns=(cb.stat().st_atime_ns, cb.stat().st_mtime_ns + 10**9))
            yield c

    monkeypatch.setattr(Classificador, "classificar", editando)
    mapa.classificar(projeto, progresso=False)
    assert projeto.codebook.hash() != antes  # a edição chegou ao projeto
    assert Resultado.ler(projeto.dados / PASTA, "qwen3.5:4b", antes).hash_codebook == antes
    assert ultima_execucao(projeto, "classificacao")["hash_codebook"] == antes


def test_gravacoes_periodicas_da_rodada_completa_nao_deixam_aviso_de_parcial(projeto, apis_falsas, monkeypatch):
    """Numa rodada completa longa com a versão nova, as gravações a cada N documentos vão para o resultado à parte;
    no fim, o completo é trocado, e a saída não diz que o anterior foi mantido."""
    import mapa_da_ciencia.classificacao.pipeline as pipeline

    mapa.classificar(projeto, progresso=False)
    apis_falsas.digests["qwen3.5:4b"] = "novo0000000000000"
    monkeypatch.setattr(pipeline, "GRAVAR_A_CADA", 2)
    r = mapa.classificar(projeto, progresso=False)
    assert not r.parcial and not any("foi mantido" in a for a in r.avisos), r.avisos
    pasta, hash_cb = projeto.dados / PASTA, projeto.codebook.hash()
    assert Resultado.ler(pasta, "qwen3.5:4b", hash_cb).modelo.endswith("@novo00000000")
    assert Resultado.ler(pasta, "qwen3.5:4b", hash_cb, a_parte=True) is None


def test_a_versao_a_parte_sai_quando_deixa_de_ser_a_mais_nova(projeto, apis_falsas):
    """Uma versão medida só na amostra e depois abandonada (o modelo foi atualizado de novo, ou o parâmetro voltou)
    não fica para sempre nas métricas."""
    from mapa_da_ciencia.validacao.metricas import calcular

    mapa.classificar(projeto, progresso=False)  # v1, completa
    mapa.amostra_de_validacao(projeto, n=5)
    pasta, hash_cb = projeto.dados / PASTA, projeto.codebook.hash()

    def a_parte():
        return Resultado.ler(pasta, "qwen3.5:4b", hash_cb, a_parte=True)

    def modelos():
        return [p.nome for p in calcular(projeto, reamostras=10).participantes if p.tipo == "modelo"]

    apis_falsas.digests["qwen3.5:4b"] = "v2000000000000000"
    mapa.classificar(projeto, somente_amostra=True, progresso=False)
    assert a_parte().modelo.endswith("@v20000000000")
    apis_falsas.digests["qwen3.5:4b"] = "v3000000000000000"  # outra atualização: a v3 toma o lugar da v2 à parte
    mapa.classificar(projeto, estimar=True, progresso=False)
    assert a_parte().modelo.endswith("@v30000000000")
    apis_falsas.digests["qwen3.5:4b"] = "v4000000000000000"  # e a rodada completa de outra versão ainda
    mapa.classificar(projeto, progresso=False)
    assert Resultado.ler(pasta, "qwen3.5:4b", hash_cb).modelo.endswith("@v40000000000") and a_parte() is None
    assert modelos() == ["qwen3.5:4b"]

    apis_falsas.digests["qwen3.5:4b"] = "v5000000000000000"
    mapa.classificar(projeto, somente_amostra=True, progresso=False)
    assert modelos() == ["qwen3.5:4b", "qwen3.5:4b (versão nova)"]
    apis_falsas.digests["qwen3.5:4b"] = "v4000000000000000"  # a v5 foi abandonada: de volta à v4, que está no cache
    mapa.classificar(projeto, limite=3, progresso=False)
    assert a_parte() is None and modelos() == ["qwen3.5:4b"]


def _interromper_depois_de(apis_falsas, n: int):
    """O chat responde normalmente as primeiras `n` chamadas e depois simula o ++ctrl+c++."""
    original, chamadas = apis_falsas.responder_chat, []

    def responder(corpo):
        chamadas.append(1)
        if len(chamadas) > n:
            raise KeyboardInterrupt
        return original(corpo)

    apis_falsas.responder_chat = responder
    return lambda: setattr(apis_falsas, "responder_chat", original)


@pytest.mark.parametrize("rodada", ["tudo_falha", "interrompida", "somente_amostra"])
def test_resultado_completo_com_uma_falha_continua_protegido(projeto, apis_falsas, monkeypatch, rodada):
    """Um resultado completo com uma falha (aceito dentro do limite, ou com um documento que falha sempre) fica
    marcado como parcial, mas nenhuma rodada da versão seguinte que não cobre o corpus o diminui."""
    import mapa_da_ciencia.classificacao.pipeline as pipeline

    mapa.classificar(projeto, progresso=False)
    mapa.amostra_de_validacao(projeto, n=5)
    pasta, hash_cb = projeto.dados / PASTA, projeto.codebook.hash()
    original = apis_falsas.responder_chat
    apis_falsas.digests["qwen3.5:4b"] = "v2000000000000000"
    _falhar_sempre_num_documento(apis_falsas)
    mapa.classificar(projeto, progresso=False)  # v2 com 1 falha: substitui (dentro do limite) e fica parcial
    v2 = Resultado.ler(pasta, "qwen3.5:4b", hash_cb)
    assert v2.modelo.endswith("@v20000000000") and v2.parcial and len(v2.falhas) == 1
    exportado = (projeto.saida / "dados" / "manifesto.json").read_text(encoding="utf-8")

    apis_falsas.responder_chat = original
    apis_falsas.digests["qwen3.5:4b"] = "v3000000000000000"  # outro `ollama pull`
    if rodada == "tudo_falha":
        _falhar(apis_falsas, 1.0)
        mapa.classificar(projeto, progresso=False)
    elif rodada == "interrompida":
        monkeypatch.setattr(pipeline, "GRAVAR_A_CADA", 3)
        _interromper_depois_de(apis_falsas, 7)
        with pytest.raises(KeyboardInterrupt):
            mapa.classificar(projeto, progresso=False)
    else:
        mapa.classificar(projeto, somente_amostra=True, progresso=False)
    assert Resultado.ler(pasta, "qwen3.5:4b", hash_cb) == v2
    assert (projeto.saida / "dados" / "manifesto.json").read_text(encoding="utf-8") == exportado
    assert Resultado.ler(pasta, "qwen3.5:4b", hash_cb, a_parte=True).modelo.endswith("@v30000000000")


def _resultado_sem_execucao(projeto):
    """O resultado como a versão 1.0.1 o gravava: sem as marcas `execucao` e `a_parte`."""
    arquivo = next((projeto.dados / PASTA).glob("qwen3.5-4b__*.json"))
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    del dados["execucao"], dados["a_parte"]
    arquivo.write_text(json.dumps(dados), encoding="utf-8")
    for manifesto in projeto.execucoes.glob("*-classificacao.json"):  # e os manifestos da 1.0.1, sem as marcas novas
        m = json.loads(manifesto.read_text(encoding="utf-8"))
        for chave in ("execucao", "gravado"):
            m["parametros"].pop(chave, None)
        manifesto.write_text(json.dumps(m), encoding="utf-8")
    return Resultado.ler(projeto.dados / PASTA, "qwen3.5:4b", projeto.codebook.hash())


def test_resultado_de_uma_versao_anterior_do_pacote(projeto, apis_falsas):
    """Um resultado sem `execucao` (como o do piloto, gravado pela 1.0.1): uma rodada parcial com outros parâmetros,
    ou sem as respostas no cache, não o diminui; com o mesmo modelo e os mesmos parâmetros, o cache cobre tudo, e a
    rodada seguinte o regrava normalmente."""
    mapa.classificar(projeto, progresso=False)
    mapa.amostra_de_validacao(projeto, n=5)
    pasta, hash_cb = projeto.dados / PASTA, projeto.codebook.hash()
    antigo = _resultado_sem_execucao(projeto)

    # o mesmo modelo e os mesmos parâmetros: a mesma execução, e o --somente-amostra regrava o completo (do cache)
    r = mapa.classificar(projeto, somente_amostra=True, progresso=False)
    assert not r.a_parte and Resultado.ler(pasta, "qwen3.5:4b", hash_cb).classificados == antigo.classificados

    # outro num_ctx: outra execução, e o completo antigo fica
    antigo = _resultado_sem_execucao(projeto)
    cfg = projeto.raiz / "mapa.yaml"
    cfg.write_text(re.sub(r"(num_ctx:) *\d+", r"\1 16384", cfg.read_text(encoding="utf-8"), count=1), encoding="utf-8")
    os.utime(cfg, ns=(cfg.stat().st_atime_ns, cfg.stat().st_mtime_ns + 10**9))
    assert projeto.config.modelos.classificacao.num_ctx == 16384
    r = mapa.classificar(projeto, somente_amostra=True, progresso=False)
    assert r.a_parte and Resultado.ler(pasta, "qwen3.5:4b", hash_cb) == antigo

    # sem manifesto para conferir os parâmetros (e sem as respostas no cache, como num projeto copiado sem o
    # estado.sqlite): na dúvida, protegido
    import sqlite3

    cfg.write_text(re.sub(r"(num_ctx:) *\d+", r"\1 8192", cfg.read_text(encoding="utf-8"), count=1), encoding="utf-8")
    os.utime(cfg, ns=(cfg.stat().st_atime_ns, cfg.stat().st_mtime_ns + 10**9))
    for manifesto in projeto.execucoes.glob("*-classificacao.json"):
        manifesto.unlink()
    with sqlite3.connect(projeto.estado) as con:
        con.execute("DELETE FROM llm_cache")
    r = mapa.classificar(projeto, somente_amostra=True, progresso=False)
    assert r.a_parte and r.novos == 5 and Resultado.ler(pasta, "qwen3.5:4b", hash_cb) == antigo
