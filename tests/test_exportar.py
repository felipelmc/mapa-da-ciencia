"""Exportação do contrato (saida/dados) depois da etapa de tópicos, no corpus sintético."""

import json

import pytest
from corpus_sintetico import corpus_sintetico

from mapa_da_ciencia.armazenamento import ARQUIVO, gravar_documentos
from mapa_da_ciencia.contrato import modelos as m
from mapa_da_ciencia.contrato.exportar import exportar
from mapa_da_ciencia.llm.perfis import PERFIS
from mapa_da_ciencia.projeto import Projeto
from mapa_da_ciencia.texto import EMAIL
from mapa_da_ciencia.topicos.pipeline import gerar_topicos


@pytest.fixture
def projeto(tmp_path, apis_falsas):
    p = Projeto.criar(tmp_path / "sintetico", modelo="vazio", perfil=PERFIS["leve"])
    docs, _ = corpus_sintetico()
    gravar_documentos(docs, p.dados / ARQUIVO)
    gerar_topicos(p)
    return p


def _ler(p, nome, modelo):
    return modelo.model_validate_json((p.saida / "dados" / f"{nome}.json").read_text(encoding="utf-8"))


def test_contrato_completo_depois_dos_topicos(projeto):
    manifesto = _ler(projeto, "manifesto", m.Manifesto)
    assert manifesto.arquivos == ["manifesto", "revistas", "documentos", "topicos", "agregados", "detalhes"]
    assert manifesto.versao_contrato == m.VERSAO_CONTRATO and manifesto.contagens.documentos == 300
    assert manifesto.execucao.modelos["embeddings"].startswith("qwen3-embedding:0.6b@")
    assert manifesto.execucao.modelos["rotulos"].startswith("qwen3.5:4b@") and manifesto.execucao.sementes == {
        "umap": 42
    }
    assert {"embeddings", "topicos"} <= set(manifesto.execucao.duracao_s)

    docs = _ler(projeto, "documentos", m.Documentos)
    topicos = _ler(projeto, "topicos", m.Topicos)
    assert docs.n == 300 and manifesto.contagens.topicos == len(topicos.topicos)
    c = docs.colunas
    assert all(len(v) == 5 and i not in v and all(0 <= j < docs.n for j in v) for i, v in enumerate(c.vizinhos))
    ids_topicos = {t.id for t in topicos.topicos}
    assert set(c.topico) <= ids_topicos | {-1}
    assert sum(t.n for t in topicos.topicos) + c.topico.count(-1) == docs.n
    assert topicos.outliers.n == sum(topicos.outliers.por_ano) == c.atribuicao.count(1)
    assert all(t.rotulo_fonte == "llm" and t.n_nucleo <= t.n for t in topicos.topicos)
    assert sorted(t for mt in topicos.macrotemas for t in mt.topicos) == sorted(ids_topicos)
    assert all(sum(t.serie.n) == t.n for t in topicos.topicos)

    agregados = _ler(projeto, "agregados", m.Agregados)
    assert sum(n for *_, n in agregados.topico_ano_revista) == docs.n and agregados.uf == {} == agregados.pais


def test_detalhes_sem_o_texto_de_analise_e_sem_emails(projeto):
    pasta = projeto.saida / "dados"
    ids = _ler(projeto, "documentos", m.Documentos).colunas.id
    detalhes = {}
    for arq in (pasta / "detalhes").glob("*.json"):
        frag = m.Fragmento.model_validate_json(arq.read_text(encoding="utf-8"))
        detalhes.update(frag.documentos)
        assert "texto_analise" not in arq.read_text(encoding="utf-8")
    assert set(detalhes) == set(ids)
    assert {d.fonte_analise for d in detalhes.values()} == {"resumo", "reserva", "so_titulo"}
    so_titulo = next(d for d in detalhes.values() if d.fonte_analise == "so_titulo")
    assert so_titulo.resumo is None
    com_resumo = next(d for d in detalhes.values() if d.fonte_analise == "resumo")
    assert com_resumo.idioma == "pt" and com_resumo.idioma_analise == "en"  # exibe em português, analisa em inglês
    assert not any(EMAIL.search(a.read_text(encoding="utf-8")) for a in pasta.rglob("*.json"))


def test_topicos_de_outro_corpus_nao_sao_exportados(projeto):
    docs, _ = corpus_sintetico()
    docs.append(docs[0].model_copy(update={"id": "S0000-00002030000100999", "pid": "S0000-00002030000100999"}))
    gravar_documentos(docs, projeto.dados / ARQUIVO)  # uma coleta nova mudou o corpus
    avisos = exportar(projeto)
    assert "mapa topicos" in avisos[0]
    pasta = projeto.saida / "dados"
    manifesto = json.loads((pasta / "manifesto.json").read_text(encoding="utf-8"))
    assert manifesto["arquivos"] == ["manifesto", "revistas"] and manifesto["contagens"]["documentos"] == 301
    assert not (pasta / "documentos.json").exists() and not (pasta / "detalhes").exists()
    assert not (projeto.saida / "dados.novo").exists() and not (projeto.saida / "dados.velho").exists()
