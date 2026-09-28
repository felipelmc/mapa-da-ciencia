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
    assert manifesto.arquivos == [
        "manifesto",
        "revistas",
        "documentos",
        "topicos",
        "agregados",
        "codebook",
        "detalhes",
    ]
    assert manifesto.execucao.hash_codebook == projeto.codebook.hash() and manifesto.contagens.classificados == 0
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
    identidade = (projeto.saida / "dados").stat().st_ino
    avisos = exportar(projeto)
    assert "mapa topicos" in avisos[0]
    pasta = projeto.saida / "dados"
    manifesto = json.loads((pasta / "manifesto.json").read_text(encoding="utf-8"))
    assert (
        manifesto["arquivos"] == ["manifesto", "revistas", "codebook"] and manifesto["contagens"]["documentos"] == 301
    )
    assert not (pasta / "documentos.json").exists() and not (pasta / "detalhes").exists()
    assert not (projeto.saida / "dados.novo").exists() and not (projeto.saida / "dados.velho").exists()
    # a mesma pasta de antes, com o conteúdo trocado (uma pasta renomeada vira "dados 2" no iCloud Drive)
    assert pasta.stat().st_ino == identidade


MULTIPLA = """
  - id: fontes
    rotulo: Fontes
    tipo: multipla
    pergunta: Quais fontes o estudo usa?
    categorias:
      - valor: surveys
        definicao: Pesquisas de opinião.
      - valor: documentos
        definicao: Documentos e textos.
"""


def test_classificacao_e_validacao_no_contrato(projeto, tmp_path):
    from importlib import resources

    import mapa_da_ciencia.api as mapa
    from mapa_da_ciencia.validacao import amostra as va

    exemplo = resources.files("mapa_da_ciencia.modelos_projeto").joinpath("codebook-exemplo.yaml").read_text("utf-8")
    (projeto.raiz / "codebook.yaml").write_text(exemplo + MULTIPLA, encoding="utf-8")
    cfg = projeto.raiz / "mapa.yaml"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace("n: 200", "n: 20"), encoding="utf-8")
    p = Projeto.abrir(projeto.raiz)
    a = va.sortear(p)
    mapa.classificar(p, limite=30, progresso=False)

    def codificar(nome, tipo, discordar):
        linhas = []
        for d in a.docs:
            r = {}
            for v in p.codebook.variaveis:
                valor = {
                    "booleana": True,
                    "texto": "2010–2020",
                    "multipla": [v.categorias[0].valor] if v.categorias else [],
                }.get(v.tipo, v.categorias[0].valor if v.categorias else None)
                if v.id == "abordagem" and d in discordar:
                    valor = "qualitativa"
                r[v.id] = {"valor": valor}
            linhas.append(json.dumps({"doc": d, "respostas": r}))
        (tmp_path / f"{nome}.jsonl").write_text("\n".join(linhas))
        va.importar(p, tmp_path / f"{nome}.jsonl", nome, tipo=tipo)

    codificar("claude-opus", "referencia", set(a.docs[:4]))
    codificar("maria", "humano", set(a.docs[4:6]))
    exportar(p)

    manifesto = _ler(p, "manifesto", m.Manifesto)
    assert {"codebook", "classificacoes", "validacao"} <= set(manifesto.arquivos)
    assert manifesto.contagens.classificados == 30 and manifesto.contagens.validados == 20
    assert manifesto.execucao.modelos["classificacao"].startswith("qwen3.5:4b@")
    assert "classificacao" in manifesto.execucao.duracao_s

    codebook = _ler(p, "codebook", m.CodebookContrato)
    assert codebook.hash == p.codebook.hash() and codebook.variaveis[-1].tipo == "multipla"
    cls = _ler(p, "classificacoes", m.Classificacoes)
    assert cls.classificados == 30 and cls.parcial and cls.cobertura == pytest.approx(30 / 300)
    assert cls.contagens["abordagem"] == {"quantitativa": 30} and cls.contagens["fontes"] == {"surveys": 30}
    assert "periodo_analisado" not in cls.contagens and cls.por_variavel["abordagem"].n == 30
    assert cls.por_variavel["abordagem"].evidencia == {"literal": 1.0}

    docs = _ler(p, "documentos", m.Documentos)
    assert set(docs.colunas.cls) == {v.id for v in p.codebook.variaveis if v.tipo != "texto"}
    assert docs.dicionarios.cls["brasil_como_caso"] == ["false", "true"]
    assert docs.dicionarios.cls["fontes"] == ['["surveys"]']
    classificados = {d for d, i in zip(docs.colunas.id, docs.colunas.cls["abordagem"], strict=True) if i >= 0}
    assert classificados >= set(a.docs) and len(classificados) == 30

    detalhes = {}
    for arq in (p.saida / "dados" / "detalhes").glob("*.json"):
        detalhes.update(m.Fragmento.model_validate_json(arq.read_text(encoding="utf-8")).documentos)
    com = [detalhes[d] for d in classificados]
    assert all(set(x.evidencias) == {v.id for v in p.codebook.variaveis} for x in com)
    for x in com:  # o trecho está no resumo exibido, nas posições indicadas
        e = x.evidencias["abordagem"]
        assert e.status == "literal" and e.campo == "resumo" and x.resumo[e.inicio : e.fim] == e.evidencia
    assert x.evidencias["fontes"].valor == ["surveys"] and x.evidencias["brasil_como_caso"].valor is True
    assert not any(detalhes[d].evidencias for d in set(detalhes) - classificados)

    val = _ler(p, "validacao", m.Validacao)
    assert [(c.nome, c.tipo) for c in val.codificadores] == [
        ("maria", "humano"),
        ("claude-opus", "referencia"),
        ("qwen3.5:4b", "modelo"),
    ]
    assert val.modelo_principal == "qwen3.5:4b" and val.hash_codebook == p.codebook.hash()
    m_ref = next(x for x in val.metricas if x.comparacao == "claude-opus × qwen3.5:4b" and x.variavel == "abordagem")
    assert m_ref.concordancia == 0.8 and m_ref.referencia == "claude-opus" and m_ref.por_classe
    assert {x.variavel for x in val.metricas} >= {"fontes:surveys", "fontes:documentos"}
    # as divergências de pessoas não saem no contrato; as da referência, sim
    assert {d.codificador for d in val.divergencias} == {"claude-opus"} and len(val.divergencias) == 4
    assert not any(EMAIL.search(a.read_text(encoding="utf-8")) for a in (p.saida / "dados").rglob("*.json"))


def test_so_links_http_viram_url_do_detalhe():
    from mapa_da_ciencia.contrato.exportar import _detalhe, _url_segura
    from mapa_da_ciencia.documento import Documento

    assert _url_segura("javascript:alert(1)") is None and _url_segura("JAVASCRIPT:x") is None
    assert _url_segura("https://www.scielo.br/j/op/a/x") == "https://www.scielo.br/j/op/a/x"
    assert _url_segura(None) is None

    # no cartão do documento: um link que não é http(s) dá lugar ao doi.org, ou a nenhum link
    atrib = {"idioma_analise": "pt", "fonte_analise": "resumo"}

    def url(link, doi):
        doc = Documento(id="S0104-62762024000100200", fonte="articlemeta", tipo=None, ano=2024, url=link, doi=doi)
        return _detalhe(doc, atrib, ["pt"]).url

    assert url("https://www.scielo.br/j/op/a/x", "10.1590/abc") == "https://www.scielo.br/j/op/a/x"
    assert url("javascript:alert(1)", "10.1590/abc") == "https://doi.org/10.1590/abc"
    assert url("javascript:alert(1)", None) is None
