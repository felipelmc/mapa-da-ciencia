import pytest
from conftest import casos_especiais, registros_articlemeta

from mapa_da_ciencia.documento import Autor, Documento, Texto
from mapa_da_ciencia.fontes.articlemeta import normalizar, revista_do_registro
from mapa_da_ciencia.fontes.dedup import deduplicar


@pytest.fixture(scope="module")
def docs() -> dict[str, Documento]:
    return {p: normalizar(r, revista_do_registro(r)) for p, r in registros_articlemeta().items()}


def _doc(id_, fonte="articlemeta", **kw) -> Documento:
    base = {
        "id": id_,
        "fonte": fonte,
        "tipo": "research-article",
        "ano": 2020,
        "titulos": [Texto(idioma="pt", texto="Coalizões e agenda legislativa no presidencialismo")],
        "autores": [Autor(nome="Ana", sobrenome="Limongi")],
    }
    return Documento(**(base | kw))


def test_artigo_carregado_duas_vezes_na_articlemeta_e_fundido(docs):
    # mesmo DOI, mesmo título, mesmo autor, PIDs diferentes (Dados e Lua Nova, 2025)
    saida, rel = deduplicar(list(docs.values()))
    assert len(saida) == len(docs) - 2
    assert sorted(rel.fundidos) == [
        ("S0011-52582025000400230", "S0011-52582025000400225"),
        ("S0102-64452025000200312", "S0102-64452025000200303"),
    ]


def test_mesmo_titulo_ano_autor_sem_doi_na_mesma_fonte_vira_suspeita():
    a, b = _doc("S0011-52582020000100001"), _doc("S0011-52582020000100009")
    saida, rel = deduplicar([b, a])
    assert len(saida) == 2 and rel.suspeitas == [("S0011-52582020000100009", "S0011-52582020000100001")]
    assert next(d for d in saida if d.id.endswith("09")).possivel_duplicata_de == "S0011-52582020000100001"


def test_titulo_generico_nao_e_duplicata(docs):
    genericos = [p for p, m in casos_especiais().items() if "genérico" in m]
    saida, _ = deduplicar([docs[p] for p in genericos])
    assert all(d.possivel_duplicata_de is None for d in saida)


def test_doi_trocado_na_articlemeta_nao_funde(docs):
    par = [p for p, m in casos_especiais().items() if m.startswith("DOI repetido")]
    saida, rel = deduplicar([docs[p] for p in par])
    assert len(saida) == 2 and not rel.fundidos
    assert not rel.dois_removidos  # sem o OpenAlex, não dá para saber de quem é o DOI


def test_doi_repetido_fica_com_o_documento_confirmado_pelo_openalex(docs):
    dono, outro = sorted(p for p, m in casos_especiais().items() if m.startswith("DOI repetido"))
    doi = docs[dono].doi
    casado = docs[dono].model_copy(update={"casamento": "1_doi", "openalex_id": "W1"})
    sem = docs[outro].model_copy(update={"casamento": "sem_casamento"})
    saida, rel = deduplicar([sem, casado])
    por_id = {d.id: d for d in saida}
    assert por_id[dono].doi == doi and por_id[outro].doi is None
    assert rel.dois_removidos == [(outro, doi, dono)]


def test_mesmo_pid_de_fontes_diferentes_funde_e_soma_origens():
    am = _doc("S0011-52582020000100001", pid="S0011-52582020000100001", origens=["scielo:0011-5258"])
    imp = _doc("doi:10.1590/x", fonte="openalex", pid="S0011-52582020000100001", origens=["importar:busca.ris"],
               openalex_id="W9", citacoes=4)  # fmt: skip
    saida, rel = deduplicar([imp, am])
    assert len(saida) == 1 and rel.fundidos == [("doi:10.1590/x", "S0011-52582020000100001")]
    d = saida[0]
    assert d.fonte == "articlemeta" and d.origens == ["scielo:0011-5258", "importar:busca.ris"]
    assert (d.openalex_id, d.citacoes) == ("W9", 4)  # completado com o que faltava


def test_mesmo_doi_titulos_compativeis_funde():
    a = _doc("S1", doi="10.1590/abc")
    b = _doc("openalex:W1", fonte="openalex", doi="10.1590/abc",
             titulos=[Texto(idioma="pt", texto="Coalizoes e a agenda legislativa no presidencialismo")])  # fmt: skip
    saida, rel = deduplicar([a, b])
    assert [d.id for d in saida] == ["S1"] and rel.fundidos == [("openalex:W1", "S1")]


def test_sem_doi_mesmo_titulo_ano_autor_em_fontes_diferentes_funde():
    saida, rel = deduplicar([_doc("S1"), _doc("openalex:W2", fonte="openalex")])
    assert len(saida) == 1 and rel.fundidos == [("openalex:W2", "S1")]


def _com_resumo(id_, texto, origem="articlemeta", titulo=None) -> Documento:
    return _doc(
        id_,
        doi=f"10.1590/{id_}",
        titulos=[Texto(idioma="pt", texto=titulo or f"Um título bem diferente para o documento {id_}")],
        resumos=[
            Texto(idioma="pt", texto="Resumo próprio do artigo " + id_),
            Texto(idioma="es", texto=texto, origem=origem),
        ],
    )


def test_resumo_padrao_do_openalex_em_varios_documentos_e_descartado():
    padrao = "Americanae nace como un proyecto conjunto de la Red Europea de Información y Documentación."
    docs = [_com_resumo(f"S{i}", padrao, "openalex") for i in range(2)] + [_com_resumo("S9", "Outro resumo.")]
    mantidos, rel = deduplicar(docs)
    assert [len(d.resumos) for d in mantidos] == [1, 1, 2]
    assert all("Americanae" not in r.texto for d in mantidos for r in d.resumos)
    assert sorted(i for i, _ in rel.resumos_descartados) == ["S0", "S1"]


def test_resumo_da_articlemeta_repetido_em_duas_partes_fica_e_em_tres_sai():
    duas = [_com_resumo(f"P{i}", "O conceito de público foi posto na agenda por Habermas.") for i in (1, 2)]
    mantidos, rel = deduplicar(duas)
    assert [len(d.resumos) for d in mantidos] == [2, 2] and not rel.resumos_descartados
    tres = [_com_resumo(f"P{i}", "Texto de apresentação do número especial.") for i in (1, 2, 3)]
    mantidos, rel = deduplicar(tres)
    assert [len(d.resumos) for d in mantidos] == [1, 1, 1] and len(rel.resumos_descartados) == 3


def test_resumo_do_openalex_igual_ao_de_outro_artigo_sai_so_do_openalex():
    texto = "Este artigo discute a coordenação federativa das políticas de saúde."
    docs = [_com_resumo("A", texto, "articlemeta"), _com_resumo("B", texto.upper(), "openalex")]
    mantidos, rel = deduplicar(docs)
    assert {d.id: len(d.resumos) for d in mantidos} == {"A": 2, "B": 1}
    assert [i for i, _ in rel.resumos_descartados] == ["B"]
