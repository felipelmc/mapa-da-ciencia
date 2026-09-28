"""Sequências de rodadas da classificação que não podem perder o resultado principal (checagem c4 da revisao-geral).

Cada sequência mistura rodadas completas, parciais (`--somente-amostra`, `--estimar`, `--limite`), interrompidas,
com falhas, com o modelo atualizado (`ollama pull`), com parâmetros ou textos que mudam, e resultados gravados pela
1.0.1. As respostas de uma versão antiga ficam no cache com a chave do digest antigo, que o Ollama não devolve mais:
um principal trocado por um menor depois de um `ollama pull` não tem volta. Por isso valem duas regras, decididas pelo
que a rodada fez: só uma rodada que cobre o corpus atual (com falhas até o limite) substitui o principal; qualquer
outra nunca o diminui.
"""

import json
import re
import time

import pytest

import mapa_da_ciencia.api as mapa
from mapa_da_ciencia.armazenamento import ARQUIVO, gravar_documentos, ler_documentos
from mapa_da_ciencia.classificacao.executor import textos_para_classificar
from mapa_da_ciencia.classificacao.resultado import PASTA, Resultado
from mapa_da_ciencia.coleta import coletar
from mapa_da_ciencia.llm.perfis import PERFIS
from mapa_da_ciencia.projeto import Projeto

MODELO = "qwen3.5:4b"


@pytest.fixture
def proj(tmp_path, apis_falsas):
    p = Projeto.criar(
        tmp_path / "op", modelo="ciencia-politica", perfil=PERFIS["leve"], revistas=["0104-6276"], anos=(2024, 2024)
    )
    coletar(p)
    return p


def _principal(proj):
    return Resultado.ler(proj.dados / PASTA, MODELO, Projeto(proj.raiz).codebook.hash())


def _a_parte(proj):
    return Resultado.ler(proj.dados / PASTA, MODELO, Projeto(proj.raiz).codebook.hash(), a_parte=True)


def _textos(proj):
    cfg = Projeto(proj.raiz).config
    return textos_para_classificar(
        ler_documentos(proj.dados / ARQUIVO), [cfg.recorte.idioma_exibicao, cfg.recorte.idioma_analise]
    )[0]


def _falhar_docs(falsas, proj, ids):
    """O chat devolve algo que não é JSON (sempre) para os documentos `ids`."""
    alvos = [t.resumo[:60] for t in _textos(proj) if t.doc in ids]
    original = falsas.responder_chat

    def responder(corpo):
        doc = next(m["content"] for m in corpo["messages"] if m["role"] == "user")
        return "isto não é JSON" if any(a in doc for a in alvos) else original(corpo)

    falsas.responder_chat = responder
    return lambda: setattr(falsas, "responder_chat", original)


def _interromper_depois(falsas, n):
    original, vistos = falsas.responder_chat, []

    def responder(corpo):
        vistos.append(1)
        if len(vistos) > n:
            raise KeyboardInterrupt
        return original(corpo)

    falsas.responder_chat = responder
    return lambda: setattr(falsas, "responder_chat", original)


def _fora_da_amostra(proj, amostra):
    return next(t.doc for t in _textos(proj) if t.doc not in amostra.docs)


def _num_ctx(texto: str, valor: int) -> str:
    novo = re.sub(r"(classificacao:\n(?:\s+\w+:.*\n)*?\s+num_ctx:) *\d+", rf"\g<1> {valor}", texto, count=1)
    assert novo != texto
    return novo


def _legado(proj):
    """Os resultados e manifestos como a 1.0.1 os gravava, sem as marcas novas."""
    for arq in (proj.dados / PASTA).glob("*.json"):
        d = json.loads(arq.read_text(encoding="utf-8"))
        d.pop("execucao", None), d.pop("a_parte", None)
        arq.write_text(json.dumps(d), encoding="utf-8")
    for arq in proj.execucoes.glob("*-classificacao.json"):
        m = json.loads(arq.read_text(encoding="utf-8"))
        for k in ("execucao", "gravado", "interrompida"):
            m["parametros"].pop(k, None)
        arq.write_text(json.dumps(m), encoding="utf-8")


def s01_completo_com_falha_somente_amostra_mesma_versao_depois_pull(proj, falsas, monkeypatch):
    amostra = mapa.amostra_de_validacao(proj, n=5)
    _falhar_docs(falsas, proj, {_fora_da_amostra(proj, amostra)})  # um documento que falha sempre
    mapa.classificar(proj, progresso=False)
    completo = _principal(proj)
    mapa.classificar(proj, somente_amostra=True, progresso=False)
    falsas.digests[MODELO] = "v2000000000000000"
    mapa.classificar(proj, somente_amostra=True, progresso=False)
    assert _principal(proj).classificados >= completo.classificados


def s02_completo_com_falha_limite_mesma_versao_depois_estimar(proj, falsas, monkeypatch):
    _falhar_docs(falsas, proj, {_textos(proj)[-1].doc})
    mapa.classificar(proj, progresso=False)
    completo = _principal(proj)
    mapa.classificar(proj, limite=10, progresso=False)
    falsas.digests[MODELO] = "v2000000000000000"
    mapa.classificar(proj, estimar=True, progresso=False)
    assert _principal(proj).classificados >= completo.classificados


def s03_v2_aceita_com_falha_somente_amostra_v3(proj, falsas, monkeypatch):
    amostra = mapa.amostra_de_validacao(proj, n=5)
    mapa.classificar(proj, progresso=False)
    falsas.digests[MODELO] = "v2000000000000000"
    desfazer = _falhar_docs(falsas, proj, {_fora_da_amostra(proj, amostra)})
    mapa.classificar(proj, progresso=False)
    completo = _principal(proj)
    mapa.classificar(proj, somente_amostra=True, progresso=False)
    desfazer()
    falsas.digests[MODELO] = "v3000000000000000"
    mapa.classificar(proj, somente_amostra=True, progresso=False)
    assert _principal(proj).classificados >= completo.classificados


def s04_idioma_trocado_estimar(proj, falsas, monkeypatch):
    mapa.classificar(proj, progresso=False)
    completo = _principal(proj)
    cfg = proj.raiz / "mapa.yaml"
    texto = cfg.read_text(encoding="utf-8")
    atual = re.search(r"idioma_exibicao: *(\w+)", texto).group(1)
    novo = "en" if atual != "en" else "pt"
    cfg.write_text(re.sub(r"idioma_exibicao: *\w+", f"idioma_exibicao: {novo}", texto, count=1), encoding="utf-8")
    p = Projeto(proj.raiz)
    mapa.classificar(p, estimar=True, progresso=False)  # os textos mudam; a execução é a mesma
    assert _principal(p).classificados >= completo.classificados


def s05_varias_parciais_da_versao_nova(proj, falsas, monkeypatch):
    import mapa_da_ciencia.classificacao.pipeline as pipeline

    mapa.amostra_de_validacao(proj, n=5)
    mapa.classificar(proj, progresso=False)
    completo = _principal(proj)
    falsas.digests[MODELO] = "v2000000000000000"
    for kw in ({"somente_amostra": True}, {"estimar": True}, {"limite": 12}):
        mapa.classificar(proj, progresso=False, **kw)
        p = _principal(proj)
        assert p.classificados == completo.classificados and p.modelo == completo.modelo, kw
    monkeypatch.setattr(pipeline, "GRAVAR_A_CADA", 2)
    desfazer = _interromper_depois(falsas, 3)
    with pytest.raises(KeyboardInterrupt):
        mapa.classificar(proj, progresso=False)
    desfazer()
    p = _principal(proj)
    assert p.classificados == completo.classificados and p.modelo == completo.modelo
    mapa.classificar(proj, progresso=False)
    p = _principal(proj)
    assert p.modelo.endswith("@v20000000000") and p.classificados == completo.classificados and _a_parte(proj) is None


def s06_falhas_demais_depois_parciais(proj, falsas, monkeypatch):
    mapa.amostra_de_validacao(proj, n=5)
    mapa.classificar(proj, progresso=False)
    completo = _principal(proj)
    falsas.digests[MODELO] = "v2000000000000000"
    desfazer = _falhar_docs(falsas, proj, {t.doc for t in _textos(proj)[-3:]})
    mapa.classificar(proj, progresso=False)  # 3 falhas, com limite 1: à parte
    mapa.classificar(proj, somente_amostra=True, progresso=False)
    desfazer()
    mapa.classificar(proj, limite=3, progresso=False)
    assert _principal(proj).classificados >= completo.classificados


def s07_comparacao_outro_modelo(proj, falsas, monkeypatch):
    mapa.amostra_de_validacao(proj, n=5)
    mapa.classificar(proj, progresso=False)
    completo = _principal(proj)
    mapa.classificar(proj, modelo="qwen3.5:9b", somente_amostra=True, progresso=False)
    assert _principal(proj) == completo


def s08_parametro_vai_e_volta(proj, falsas, monkeypatch):
    mapa.classificar(proj, progresso=False)
    completo = _principal(proj)
    cfg = proj.raiz / "mapa.yaml"
    original = cfg.read_text(encoding="utf-8")
    cfg.write_text(_num_ctx(original, 16384), encoding="utf-8")
    mapa.classificar(Projeto(proj.raiz), limite=12, progresso=False)
    cfg.write_text(original, encoding="utf-8")
    mapa.classificar(Projeto(proj.raiz), estimar=True, progresso=False)
    assert _principal(proj).classificados == completo.classificados and _a_parte(proj) is None


def s09_legado_mesmos_parametros_e_pull(proj, falsas, monkeypatch):
    mapa.amostra_de_validacao(proj, n=5)
    mapa.classificar(proj, progresso=False)
    _legado(proj)
    completo = _principal(proj)
    mapa.classificar(proj, somente_amostra=True, progresso=False)
    assert _principal(proj).classificados == completo.classificados
    _legado(proj)
    time.sleep(1.05)
    falsas.digests[MODELO] = "v2000000000000000"
    mapa.classificar(proj, estimar=True, progresso=False)
    assert _principal(proj).classificados == completo.classificados


def s10_legado_manifesto_de_outro_codebook(proj, falsas, monkeypatch):
    mapa.amostra_de_validacao(proj, n=5)
    mapa.classificar(proj, progresso=False)  # codebook A, num_ctx do perfil
    completo_a = _principal(proj)
    time.sleep(1.05)
    cb = proj.raiz / "codebook.yaml"
    cb_a = cb.read_text(encoding="utf-8")
    cb_b = re.sub(r"(pergunta: *)(.+)", r"\1\2 Leia com atenção.", cb_a, count=1)
    assert cb_b != cb_a
    cfg = proj.raiz / "mapa.yaml"
    cb.write_text(cb_b, encoding="utf-8")
    cfg.write_text(_num_ctx(cfg.read_text(encoding="utf-8"), 16384), encoding="utf-8")
    mapa.classificar(Projeto(proj.raiz), progresso=False)  # codebook B, num_ctx 16384
    _legado(proj)  # as duas rodadas "da 1.0.1"
    cb.write_text(cb_a, encoding="utf-8")  # o codebook volta (git checkout), o num_ctx fica
    pa = Projeto(proj.raiz)
    assert pa.codebook.hash() == completo_a.hash_codebook
    mapa.classificar(pa, somente_amostra=True, progresso=False)
    assert _principal(pa).classificados == completo_a.classificados


def s11_mesma_versao_interrompida(proj, falsas, monkeypatch):
    import mapa_da_ciencia.classificacao.pipeline as pipeline

    _falhar_docs(falsas, proj, {_textos(proj)[0].doc})
    mapa.classificar(proj, progresso=False)
    completo = _principal(proj)
    monkeypatch.setattr(pipeline, "GRAVAR_A_CADA", 1)
    desfazer = _interromper_depois(falsas, 1)
    with pytest.raises(KeyboardInterrupt):
        mapa.classificar(proj, progresso=False)
    desfazer()
    assert _principal(proj).classificados == completo.classificados
    falsas.digests[MODELO] = "v2000000000000000"
    mapa.classificar(proj, estimar=True, progresso=False)
    assert _principal(proj).classificados >= completo.classificados


def s12_corpus_cresce_estimar_pull_estimar(proj, falsas, monkeypatch):
    arq = proj.dados / ARQUIVO
    todos = ler_documentos(arq)
    gravar_documentos(todos[:-10], arq)  # o corpus antes da coleta nova
    mapa.classificar(proj, progresso=False)
    completo = _principal(proj)
    gravar_documentos(todos, arq)  # `mapa coletar` de novo: 10 documentos novos
    mapa.classificar(proj, estimar=True, progresso=False)
    falsas.digests[MODELO] = "v2000000000000000"
    mapa.classificar(proj, estimar=True, progresso=False)
    assert _principal(proj).classificados >= completo.classificados


def s13_sem_manifesto_da_execucao_dos_dados(proj, falsas, monkeypatch):
    """A execução dos dados sem manifesto (processo morto): o status, o painel e a exportação não mostram outra.
    O principal parcial tem menos documentos (3) que a rodada interrompida da v2 (7), que por isso o grava: com mais
    documentos (o `--limite 12` da checagem), a regra 2 mandaria a rodada interrompida para o resultado à parte."""
    import mapa_da_ciencia.classificacao.pipeline as pipeline
    from mapa_da_ciencia.contrato.exportar import exportar
    from mapa_da_ciencia.manifesto import estados_das_etapas, ultima_classificacao

    mapa.classificar(proj, limite=3, progresso=False)
    time.sleep(1.05)
    falsas.digests[MODELO] = "v2000000000000000"
    monkeypatch.setattr(pipeline, "GRAVAR_A_CADA", 3)
    desfazer = _interromper_depois(falsas, 7)
    with pytest.raises(KeyboardInterrupt):
        mapa.classificar(proj, progresso=False)
    desfazer()
    p = _principal(proj)
    ultimo = sorted(proj.execucoes.glob("*-classificacao.json"))[-1]  # o `kill -9`: some o manifesto da interrupção
    assert json.loads(ultimo.read_text(encoding="utf-8"))["parametros"]["interrompida"] is True
    ultimo.unlink()
    exportar(proj)
    assert p.modelo.endswith("@v20000000000") and p.classificados == 7
    assert ultima_classificacao(proj) is None and estados_das_etapas(proj)["classificacao"]["ultima"] is None


SEQUENCIAS = {f.__name__: f for f in (
    s01_completo_com_falha_somente_amostra_mesma_versao_depois_pull,
    s02_completo_com_falha_limite_mesma_versao_depois_estimar,
    s03_v2_aceita_com_falha_somente_amostra_v3,
    s04_idioma_trocado_estimar,
    s05_varias_parciais_da_versao_nova,
    s06_falhas_demais_depois_parciais,
    s07_comparacao_outro_modelo,
    s08_parametro_vai_e_volta,
    s09_legado_mesmos_parametros_e_pull,
    s10_legado_manifesto_de_outro_codebook,
    s11_mesma_versao_interrompida,
    s12_corpus_cresce_estimar_pull_estimar,
    s13_sem_manifesto_da_execucao_dos_dados,
)}  # fmt: skip


@pytest.mark.parametrize("sequencia", list(SEQUENCIAS))
def test_nenhuma_sequencia_perde_o_resultado_principal(proj, apis_falsas, monkeypatch, sequencia):
    SEQUENCIAS[sequencia](proj, apis_falsas, monkeypatch)
