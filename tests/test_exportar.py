"""Exportação do contrato (saida/dados) depois da etapa de tópicos, no corpus sintético."""

import json

import pytest
from corpus_sintetico import corpus_sintetico

from mapa_da_ciencia.armazenamento import ARQUIVO, gravar_documentos
from mapa_da_ciencia.contrato import modelos as m
from mapa_da_ciencia.contrato.exportar import exportar, tendencia_contrato
from mapa_da_ciencia.llm.perfis import PERFIS
from mapa_da_ciencia.projeto import Projeto
from mapa_da_ciencia.texto import EMAIL
from mapa_da_ciencia.topicos.pipeline import gerar_topicos


@pytest.fixture
def projeto(tmp_path, apis_falsas):
    p = Projeto.criar(tmp_path / "sintetico", modelo="vazio", perfil=PERFIS["leve"])
    docs, _ = corpus_sintetico()
    # uma revista importada sem acrônimo: a chave é o ISSN em todos os arquivos
    docs = [d.model_copy(update={"revista_acronimo": None}) if d.revista_acronimo == "op" else d for d in docs]
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

    # tendências e séries dos macrotemas (contrato 1.2)
    assert topicos.metodo_tendencia == m.MetodoTendencia()
    for t in [*topicos.topicos, *topicos.macrotemas]:
        assert t.tendencia == tendencia_contrato(t.serie.n, topicos.total_por_ano, topicos.anos)
    assert topicos.outliers.sem_topico_por_ano == [
        topicos.total_por_ano[i] - sum(t.serie.n[i] for t in topicos.topicos) for i in range(len(topicos.anos))
    ]

    # a mesma chave de revista em revistas.json, no dicionário dos documentos, em por_revista e nos agregados
    ids_revistas = {r.id for r in _ler(projeto, "revistas", m.Revistas).revistas}
    assert "0000-0001" in ids_revistas and "op" not in ids_revistas
    assert set(docs.dicionarios.revista) == ids_revistas
    assert {r for t in topicos.topicos for r in t.por_revista} <= ids_revistas
    assert {r for *_, r, _ in agregados.topico_ano_revista} <= ids_revistas


def test_afiliacoes_e_agregados_depois_da_geografia(projeto):
    from collections import defaultdict

    from mapa_da_ciencia.contrato.exportar import agregados_geograficos
    from mapa_da_ciencia.geografia.pipeline import gerar_geografia

    gerar_geografia(projeto)
    manifesto = _ler(projeto, "manifesto", m.Manifesto)
    assert "afiliacoes" in manifesto.arquivos and "geografia" in manifesto.execucao.duracao_s
    af = _ler(projeto, "afiliacoes", m.Afiliacoes)
    c, dic = af.colunas, af.dicionarios
    assert dic.uf == list(m.SIGLAS_UF) and dic.pais == ["AR", "BR"]
    ids = [i.id for i in dic.instituicao]
    assert ids[-1] == m.NAO_IDENTIFICADA and set(ids[:-1]) == {f"openalex:I100{k}" for k in range(1, 5)}
    por_doc: dict[int, float] = defaultdict(float)
    for doc, peso in zip(c.doc, c.peso, strict=True):
        por_doc[doc] += peso
    assert len(por_doc) == 300 and all(v == pytest.approx(1) for v in por_doc.values())
    # a cada 6 documentos, um sem afiliação (-1); a "não identificada" tem país e UF da fonte
    sem = sum(p for i, p in zip(c.instituicao, c.peso, strict=True) if i == -1)
    assert sem == pytest.approx(50)
    nao = [(u, pa) for i, u, pa in zip(c.instituicao, c.uf, c.pais, strict=True) if i == len(ids) - 1]
    assert nao and all(dic.uf[u] == "RJ" and dic.pais[pa] == "BR" for u, pa in nao)
    # o gabarito de agregados.json sai da própria tabela longa
    agregados = _ler(projeto, "agregados", m.Agregados)
    assert agregados.model_dump(include=set(agregados_geograficos(af))) == agregados_geograficos(af)
    assert agregados.uf["SP"] > 0 and agregados.sem_afiliacao == pytest.approx(50)
    assert manifesto.contagens.com_instituicao == 300 - 50 - len(
        {d for d, i in zip(c.doc, c.instituicao, strict=True) if i == len(ids) - 1}
    )

    # correções novas deixam a geografia para trás: o painel fica sem ela até `mapa geografia` rodar de novo
    (projeto.raiz / "instituicoes.yaml").write_text("apelidos: {}\n", encoding="utf-8")
    avisos = exportar(projeto)
    assert any("mapa geografia" in a for a in avisos)
    assert "afiliacoes" not in _ler(projeto, "manifesto", m.Manifesto).arquivos
    assert _ler(projeto, "agregados", m.Agregados).uf == {}


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
