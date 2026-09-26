import gzip

import pytest
from conftest import casos_especiais, obras_openalex, registros_articlemeta

from mapa_da_ciencia.coleta import OpcoesColeta, coletar
from mapa_da_ciencia.documento import Documento, Texto
from mapa_da_ciencia.fontes import revistas
from mapa_da_ciencia.fontes.articlemeta import RevistaRef, normalizar
from mapa_da_ciencia.fontes.openalex import casar_todos, conferir, enriquecer, reconstruir_resumo
from mapa_da_ciencia.llm.perfis import PERFIS
from mapa_da_ciencia.projeto import Projeto


@pytest.fixture(scope="module")
def casados() -> dict[str, Documento]:
    docs = [
        normalizar(r, RevistaRef.de_revista(revistas.por_issn(p[1:10]))) for p, r in registros_articlemeta().items()
    ]
    return {d.id: d for d in casar_todos(docs, obras_openalex())}


def _por_motivo() -> dict[str, str]:
    return {motivo: pid for pid, motivo in casos_especiais().items()}


def test_reconstruir_resumo():
    assert reconstruir_resumo({"política": [1], "A": [0], "importa": [2]}) == "A política importa"
    assert reconstruir_resumo(None) == ""


def test_conferir_rejeita_ano_e_titulo_distantes():
    doc = Documento(
        id="S1", fonte="articlemeta", tipo="research-article", ano=2014, titulos=[Texto(idioma="pt", texto="Coalizões")]
    )
    assert conferir(doc, {"publication_year": 2015, "title": "Coalizoes"})
    assert not conferir(doc, {"publication_year": 2017, "title": "Coalizões"})
    assert not conferir(doc, {"publication_year": 2014, "title": "A política externa da China"})


@pytest.mark.parametrize("passo", ["2_pid_url", "3_doi_derivado", "4_titulo_ano", "sem_casamento"])
def test_cada_passo_da_cascata(casados, passo):
    assert casados[_por_motivo()[f"casamento {passo}"]].casamento == passo


def test_doi_repetido_na_articlemeta_so_casa_um_documento(casados):
    par = [pid for pid, m in casos_especiais().items() if m.startswith("DOI repetido")]
    assert sorted(casados[p].casamento for p in par) == ["1_doi", "sem_casamento"]
    ids = [d.openalex_id for d in casados.values() if d.openalex_id]
    assert len(ids) == len(set(ids))  # cada trabalho do OpenAlex casa com um documento só


def test_enriquecimento_traz_citacoes_licenca_e_resumo_de_reserva(casados):
    op = [d for d in casados.values() if d.revista_acronimo == "op"]
    assert {d.casamento for d in op} == {"1_doi"}
    assert all(d.citacoes is not None and d.openalex_id.startswith("W") for d in op)
    resenha = casados[_por_motivo()["resenha"]]
    assert resenha.resumos and resenha.resumos[0].origem == "openalex"  # a ArticleMeta não tinha resumo
    sem = casados[_por_motivo()["casamento sem_casamento"]]
    assert sem.licenca_fonte == "revista" and sem.citacoes is None


def test_licenca_mais_restritiva_vence():
    doc = Documento(id="S1", fonte="articlemeta", tipo=None, ano=2020, licenca_revista="cc-by")
    obra = {"id": "https://openalex.org/W1", "primary_location": {"license": "cc-by-nc"}, "cited_by_count": 3}
    d = enriquecer(doc, obra, "1_doi")
    assert (d.licenca, d.licenca_fonte, d.openalex_id, d.citacoes) == ("cc-by-nc", "openalex", "W1", 3)


@pytest.fixture
def projeto(tmp_path):
    return Projeto.criar(
        tmp_path / "op", modelo="vazio", perfil=PERFIS["leve"], revistas=["0104-6276"], anos=(2024, 2024)
    )


def test_coleta_com_openalex_e_cache(projeto, apis_falsas):
    resumo = coletar(projeto)
    assert resumo.casamento == {"1_doi": 25}
    assert resumo.creditos_openalex == 1 and apis_falsas.chamadas["openalex"] == 1
    assert coletar(projeto).total_requisicoes == 0


def test_sem_openalex(projeto, apis_falsas):
    resumo = coletar(projeto, OpcoesColeta(sem_openalex=True))
    assert resumo.casamento == {"nao_tentado": 25} and apis_falsas.chamadas["openalex"] == 0


def test_chave_do_openalex_vai_na_requisicao_mas_nao_no_disco(projeto, apis_falsas):
    (projeto.raiz / ".env").write_text("OPENALEX_API_KEY=CHAVE-SECRETA-123\n")
    coletar(projeto)
    pedido = next(c.request for c in apis_falsas.router.calls if "openalex" in str(c.request.url))
    assert pedido.url.params["api_key"] == "CHAVE-SECRETA-123"
    for arq in (projeto.brutos / "openalex").rglob("*.json.gz"):
        assert "CHAVE-SECRETA-123" not in gzip.decompress(arq.read_bytes()).decode()
