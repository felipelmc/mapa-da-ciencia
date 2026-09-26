import pytest
from conftest import casos_especiais, registros_articlemeta

from mapa_da_ciencia.documento import Autor, Documento, Texto
from mapa_da_ciencia.fontes import revistas
from mapa_da_ciencia.fontes.articlemeta import RevistaRef, normalizar
from mapa_da_ciencia.fontes.dedup import deduplicar


@pytest.fixture(scope="module")
def docs() -> dict[str, Documento]:
    return {
        p: normalizar(r, RevistaRef.de_revista(revistas.por_issn(p[1:10]))) for p, r in registros_articlemeta().items()
    }


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
