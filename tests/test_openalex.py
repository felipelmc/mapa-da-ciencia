import gzip

import pytest
from conftest import casos_especiais, obras_openalex, registros_articlemeta

from mapa_da_ciencia.coleta import OpcoesColeta, coletar
from mapa_da_ciencia.documento import Documento, Texto
from mapa_da_ciencia.fontes.articlemeta import normalizar, revista_do_registro
from mapa_da_ciencia.fontes.openalex import (
    casar_todos,
    conferir,
    documento_de_obra,
    enriquecer,
    issns_da_obra,
    licenca_da_obra,
    local_da_revista,
    reconstruir_resumo,
)
from mapa_da_ciencia.llm.perfis import PERFIS
from mapa_da_ciencia.projeto import Projeto


@pytest.fixture(scope="module")
def casados() -> dict[str, Documento]:
    docs = [normalizar(r, revista_do_registro(r)) for p, r in registros_articlemeta().items()]
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


def test_conferir_aceita_ano_errado_no_openalex_com_titulo_longo_igual():
    # Novos Estudos 2025: o OpenAlex registra 2005
    titulo = "Análise comparativa do perfil da população internada em estabelecimentos de custódia"
    doc = Documento(
        id="S1", fonte="articlemeta", tipo="research-article", ano=2025, titulos=[Texto(idioma="pt", texto=titulo)]
    )
    assert conferir(doc, {"publication_year": 2005, "title": titulo.upper()})
    assert not conferir(doc, {"publication_year": 2005, "title": "Análise comparativa de outra coisa"})


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


def test_titulo_do_openalex_quando_a_articlemeta_nao_tem():
    # Opinião Pública e Novos Estudos, 2010–2013: seis artigos sem título na ArticleMeta
    doc = Documento(id="S1", fonte="articlemeta", tipo=None, ano=2011)
    obra = {"id": "https://openalex.org/W1", "title": "Cidade &amp; política", "language": "pt"}
    d = enriquecer(doc, obra, "3_doi_derivado")
    assert [(t.idioma, t.texto, t.origem) for t in d.titulos] == [("pt", "Cidade & política", "openalex")]
    com_titulo = doc.model_copy(update={"titulos": [Texto(idioma="en", texto="City")]})
    assert enriquecer(com_titulo, obra, "1_doi").titulos == com_titulo.titulos


@pytest.fixture
def projeto(tmp_path):
    return Projeto.criar(
        tmp_path / "op", modelo="vazio", perfil=PERFIS["leve"], revistas=["0104-6276"], anos=(2024, 2024)
    )


def test_coleta_com_openalex_e_cache(projeto, apis_falsas):
    resumo = coletar(projeto)
    assert resumo.casamento == {"1_doi": 25}
    # uma página da lista da revista, um lote de instituições, um de referências e um de obras citadas
    assert resumo.creditos_openalex == 4 and apis_falsas.chamadas["openalex"] == 1
    assert apis_falsas.chamadas["openalex_instituicoes"] == 1 and apis_falsas.chamadas["openalex_obras_por_id"] == 2
    assert coletar(projeto).total_requisicoes == 0


def test_quem_sobra_e_procurado_pelo_doi(projeto, apis_falsas):
    # O OpenAlex às vezes só liga o trabalho a um repositório (DOAJ): ele some da lista da revista
    alvo = next(o for o in apis_falsas.obras if (o.get("doi") or "").endswith("1807-019120243011"))
    repositorio = {"type": "repository", "issn": None, "display_name": "DOAJ"}
    alvo["primary_location"] = {**alvo["primary_location"], "source": repositorio}
    alvo["locations"] = [{**local, "source": repositorio} for local in alvo.get("locations") or []]
    resumo = coletar(projeto)
    assert resumo.casamento == {"1_doi": 25}
    # lista, DOIs, instituições, referências e obras citadas
    assert apis_falsas.chamadas["openalex"] == 2 and resumo.creditos_openalex == 5


def test_endereco_direto_acha_o_que_os_filtros_nao_acham(projeto, apis_falsas):
    # Trabalho novo do OpenAlex, fora do índice de filtros e ligado só a um repositório
    alvo = next(o for o in apis_falsas.obras if (o.get("doi") or "").endswith("1807-019120243011"))
    alvo["primary_location"] = {**alvo["primary_location"], "source": {"type": "repository", "issn": None}}
    alvo["locations"] = [{**lc, "source": {"type": "repository", "issn": None}} for lc in alvo.get("locations") or []]
    apis_falsas.fora_dos_filtros.add("10.1590/1807-019120243011")
    resumo = coletar(projeto)
    assert resumo.casamento == {"1_doi": 25}
    # lista, DOIs, endereço direto (grátis), instituições, referências e obras citadas
    assert resumo.requisicoes["openalex"] == 6 and resumo.creditos_openalex == 5
    assert coletar(projeto).total_requisicoes == 0  # a obra achada pelo endereço direto fica no cache


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


def _obra_com_repositorio_principal(licenca_revista: str | None) -> dict:
    """Como o OpenAlex guarda alguns artigos da Novos Estudos: a location principal é um repositório."""
    repositorio = {
        "source": {"type": "repository", "issn": None, "display_name": "LA Referencia"},
        "license": "other-oa",
    }
    revista = {
        "source": {"type": "journal", "issn": ["0101-3300", "1980-5403"], "display_name": "Novos Estudos - CEBRAP"},
        "license": licenca_revista,
        "landing_page_url": "http://www.scielo.br/pdf/nec/n102/1980-5403-nec-102-39.pdf",
    }
    return {
        "id": "https://openalex.org/W2605550100",
        "doi": "https://doi.org/10.25091/s0101-3300201500020004",
        "title": "Cutucando onças com varas curtas",
        "publication_year": 2015,
        "type": "article",
        "primary_location": repositorio,
        "locations": [repositorio, revista],
    }


def test_location_da_revista_quando_a_principal_e_um_repositorio():
    obra = _obra_com_repositorio_principal("cc-by-nc")
    assert local_da_revista(obra, {"0101-3300"})["source"]["type"] == "journal"
    assert local_da_revista(obra)["source"]["display_name"] == "Novos Estudos - CEBRAP"  # sem ISSN: a 1ª revista
    assert licenca_da_obra(obra) == "cc-by-nc"
    assert licenca_da_obra(_obra_com_repositorio_principal(None)) == "other-oa"  # a revista não informa
    assert issns_da_obra(obra) == ["0101-3300", "1980-5403"]
    doc = documento_de_obra(obra, "importar:x.txt")
    assert doc.revista_issn == "0101-3300" and doc.url.startswith("http://www.scielo.br/")


def test_autorias_da_obra_sem_prefixos_sem_emails_e_com_linhagem():
    from mapa_da_ciencia.fontes.openalex import autorias_da_obra

    obra = {
        "authorships": [
            {
                "author": {"display_name": "Ana Souza"},
                "institutions": [
                    {
                        "id": "https://openalex.org/I2",
                        "display_name": "Hospital Universitário da USP",
                        "ror": "https://ror.org/0abc",
                        "country_code": "BR",
                        "type": "healthcare",
                        "lineage": ["https://openalex.org/I1", "https://openalex.org/I2"],
                    }
                ],
                "countries": ["BR"],
                "affiliations": [
                    {
                        "raw_affiliation_string": "HU-USP, São Paulo; ana@usp.br",
                        "institution_ids": ["https://openalex.org/I2"],
                    }
                ],
            },
            {"author": {}, "raw_author_name": "B. Lima", "raw_affiliation_strings": ["Cebrap"], "institutions": []},
        ]
    }
    a, b = autorias_da_obra(obra)
    inst = a.instituicoes[0]
    assert (inst.id, inst.ror, inst.pais, inst.tipo, inst.linhagem) == ("I2", "0abc", "BR", "healthcare", ["I1"])
    assert a.afiliacoes[0].instituicoes == ["I2"] and "@" not in a.afiliacoes[0].texto
    assert b.nome == "B. Lima" and [f.texto for f in b.afiliacoes] == ["Cebrap"] and b.instituicoes == []


def test_enriquecer_guarda_as_autorias(casados):
    com = [d for d in casados.values() if d.openalex_id]
    assert com and all(d.autorias_openalex for d in com if d.autores)


def test_referencias_e_obras_citadas(projeto, apis_falsas):
    """As referências de cada obra (as redes de citação) e as obras de fora mais citadas (o cânone), por lista
    branca: sem os textos de afiliação, e portanto sem e-mails."""
    import json

    from mapa_da_ciencia.armazenamento import ARQUIVO, ARQUIVO_CITADAS, ARQUIVO_REFERENCIAS, ler_documentos, ler_tabela

    coletar(projeto)
    refs = ler_tabela(projeto.dados / ARQUIVO_REFERENCIAS)
    citadas = ler_tabela(projeto.dados / ARQUIVO_CITADAS)
    assert len({r["obra"] for r in refs}) == 25 and all(r["citada"].startswith("W") for r in refs)
    assert {c["id"] for c in citadas} >= {"W900000001", "W900000002"}
    classicas = [c for c in citadas if c["id"].startswith("W9")]
    assert classicas and all(c["autores"] == ["Autora Clássica"] and c["veiculo"] == "Editora Y" for c in classicas)
    assert "@" not in json.dumps(citadas, default=str)
    docs = ler_documentos(projeto.dados / ARQUIVO)
    assert any(a.id and a.id.startswith("A") for d in docs for a in d.autorias_openalex)


def test_resumo_e_titulo_do_openalex_sem_emails():
    from mapa_da_ciencia.fontes.openalex import documento_de_obra, reconstruir_resumo

    indice = {"Contato:": [0], "fulana": [1], "@": [2], "exemplo.br.": [3], "Resultados": [4]}
    assert "exemplo" not in reconstruir_resumo(indice)
    obra = {"id": "https://openalex.org/W1", "title": "Um título fulana@exemplo.br", "publication_year": 2020,
            "type": "article", "abstract_inverted_index": indice}  # fmt: skip
    doc = documento_de_obra(obra, "teste")
    assert "@" not in doc.titulos[0].texto and all("exemplo" not in r.texto for r in doc.resumos)
