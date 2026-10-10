from mapa_da_ciencia.documento import Documento, Texto
from mapa_da_ciencia.fontes.conferencia import conferir_textos, fragmento

PT = (
    "O artigo analisa as coalizões de governo no Brasil e mostra que os partidos não recebem ministérios na "
    "proporção das cadeiras, o que também afeta a disciplina das bancadas."
)
EN = (
    "This article analyzes government coalitions in Brazil and shows that parties do not receive ministries in "
    "proportion to their seats, which also affects the discipline of the delegations."
)
ES = (
    "El artículo analiza las coaliciones de gobierno en Brasil y muestra que los partidos no reciben ministerios "
    "en proporción a sus escaños, lo que también afecta la disciplina de las bancadas."
)
FR = (
    "Cet article analyse les coalitions de gouvernement au Brésil et montre que les partis ne reçoivent pas des "
    "ministères en proportion de leurs sièges, ce qui affecte aussi la discipline des groupes."
)


def _doc(resumos, titulos=(), palavras=(), id_="S0000-00002020000100001"):
    return Documento(
        id=id_,
        fonte="articlemeta",
        tipo="research-article",
        ano=2020,
        resumos=[Texto(idioma=i, texto=t, origem=o) for i, t, o in resumos],
        titulos=[Texto(idioma=i, texto=t) for i, t in titulos],
        palavras_chave=[Texto(idioma=i, texto=t) for i, t in palavras],
    )


def test_frances_declarado_espanhol_vira_frances_com_o_titulo():
    doc = _doc(
        [("pt", PT, "articlemeta"), ("es", FR, "articlemeta")],
        titulos=[("pt", "Coalizões no Brasil"), ("es", "Les coalitions au Brésil")],
        palavras=[("es", "coalitions"), ("pt", "coalizões")],
    )
    (novo,), relatorio = conferir_textos([doc])
    assert [r.idioma for r in novo.resumos] == ["pt", "fr"]
    assert [t.idioma for t in novo.titulos] == ["pt", "fr"]
    assert [p.idioma for p in novo.palavras_chave] == ["fr", "pt"]
    assert relatorio.idiomas == [(doc.id, "es", "fr")]
    assert relatorio.fragmentos == []


def test_resumos_trocados_voltam_ao_lugar_e_os_titulos_certos_ficam():
    # na RBPI de 2012, só os resumos estão trocados: os títulos confirmam o idioma declarado
    doc = _doc(
        [("pt", EN, "articlemeta"), ("en", PT, "articlemeta")],
        titulos=[("pt", "O papel da União Europeia na governança do clima"), ("en", "The role of the European Union")],
        palavras=[("pt", "clima"), ("en", "climate")],
    )
    (novo,), _ = conferir_textos([doc])
    assert {r.idioma: r.texto for r in novo.resumos} == {"en": EN, "pt": PT}
    assert [t.idioma for t in novo.titulos] == ["pt", "en"]
    assert [p.idioma for p in novo.palavras_chave] == ["pt", "en"]


def test_um_resumo_por_idioma_fica_o_que_ja_estava_certo():
    # um resumo em espanhol declarado português, num documento que já tem o resumo em espanhol
    outro_es = ES.replace("El artículo", "Este trabajo")
    doc = _doc([("pt", outro_es, "articlemeta"), ("es", ES, "articlemeta"), ("en", EN, "articlemeta")])
    (novo,), relatorio = conferir_textos([doc])
    assert [(r.idioma, r.texto) for r in novo.resumos] == [("es", ES), ("en", EN)]
    assert relatorio.idiomas == [(doc.id, "pt", "es")]


def test_fragmentos_saem_e_o_resto_fica():
    doc = _doc(
        [
            ("pt", "Resumo", "articlemeta"),  # curto
            ("en", "Keywords Factions; socio-educational system; Crime; Northeastern Brazil.", "articlemeta"),
            ("es", "na revista Encontros com a Civilização Brasileira, o ensaio " + PT, "openalex"),  # no meio
            ("en", EN, "articlemeta"),
        ]
    )
    (novo,), relatorio = conferir_textos([doc])
    assert [(r.idioma, r.texto) for r in novo.resumos] == [("en", EN)]
    assert len(relatorio.fragmentos) == 3


def test_regras_de_fragmento():
    def r(texto, origem="openalex"):
        return Texto(idioma="pt", texto=texto, origem=origem)

    assert fragmento(r("Made available in DSpace on 2013-11-04 (GMT). No. of bitstreams: 1 " + PT))
    assert fragmento(r("DOAJ is a unique and extensive index of diverse open access journals " + EN))
    assert fragmento(r("2] Todas as passagens do livro citadas foram traduzidas pelo autor. " + PT))
    assert not fragmento(r(PT))
    assert not fragmento(r("“Democracia como valor universal”: " + PT))
    # da ArticleMeta, um resumo que começa em minúscula é do próprio artigo
    assert not fragmento(r("este estudo trata das " + PT, origem="articlemeta"))


def test_sem_nada_a_corrigir_o_documento_e_o_mesmo():
    doc = _doc([("pt", PT, "articlemeta"), ("en", EN, "articlemeta")], titulos=[("pt", "Título")])
    (novo,), relatorio = conferir_textos([doc])
    assert novo is doc
    assert relatorio.fragmentos == relatorio.idiomas == []
