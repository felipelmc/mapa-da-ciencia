"""As redes: pesos fracionários, identidade das pessoas, desenho reprodutível, citações e a etapa de ponta a ponta."""

import json
import re

import pytest
from corpus_sintetico import AFILIACOES, corpus_sintetico

from mapa_da_ciencia.armazenamento import (
    ARQUIVO,
    ARQUIVO_CITADAS,
    ARQUIVO_REFERENCIAS,
    gravar_documentos,
    gravar_tabela,
)
from mapa_da_ciencia.contrato import modelos as m
from mapa_da_ciencia.documento import Afiliacao, Autor, AutoriaOpenAlex, Documento, InstituicaoOpenAlex, Texto
from mapa_da_ciencia.fontes.openalex import COLUNAS_CITADAS, COLUNAS_REFERENCIAS
from mapa_da_ciencia.llm.perfis import PERFIS
from mapa_da_ciencia.projeto import Projeto
from mapa_da_ciencia.redes import citacoes as cit
from mapa_da_ciencia.redes.desenho import desenhar
from mapa_da_ciencia.redes.grafos import grafo, pares_ponderados
from mapa_da_ciencia.redes.pessoas import CorrecoesPessoas, identificar
from mapa_da_ciencia.redes.pipeline import gerar_redes, redes_em_dia

ORCID = re.compile(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]")


def test_pesos_fracionarios():
    arestas = pares_ponderados({"d1": ["a", "b", "c"], "d2": ["a", "b"], "d3": ["a"], "d4": ["b", "b", "c"]})
    assert arestas[("a", "b")] == (1.5, 2) and arestas[("a", "c")] == (0.5, 1) and arestas[("b", "c")] == (1.5, 2)
    # a soma dos pesos é Σ n/2 nos documentos com coautoria (autores distintos)
    assert sum(p for p, _ in arestas.values()) == pytest.approx(3 / 2 + 2 / 2 + 2 / 2)
    forca = {x: sum(p for par, (p, _) in arestas.items() if x in par) for x in "abc"}
    assert forca == {"a": 2, "b": 3, "c": 2}  # documentos com coautor de cada um


def _doc(i: str, autores: list[tuple[str, str | None, str | None]]) -> Documento:
    """autores: (nome completo, id do OpenAlex, ORCID)."""
    return Documento(
        id=i,
        fonte="articlemeta",
        tipo="research-article",
        ano=2020,
        titulos=[Texto(idioma="pt", texto=f"Título {i}")],
        autores=[Autor(nome=n.split()[0], sobrenome=n.split()[-1], orcid=o) for n, _, o in autores],
        autorias_openalex=[AutoriaOpenAlex(nome=n, id=a) for n, a, _ in autores],
    )


def test_identidade_das_pessoas():
    docs = [
        _doc("d1", [("Ana Silva", "A1", "0000-0001-0000-0001"), ("Beto Souza", None, None)]),
        _doc("d2", [("Ana Silva", "A1", None), ("Caio Lima", "A3", None)]),
        # o OpenAlex fundiu duas "Ana Silva" com ORCIDs diferentes: não se juntam
        _doc("d3", [("Ana Silva", "A1", "0000-0002-0000-0002"), ("Dora Reis", None, None)]),
        # sem id nem ORCID: entra na única "Beto Souza" que existe
        _doc("d4", [("Beto Souza", None, None), ("Caio Lima", "A3", None)]),
        # homônimo sem id nem coautor em comum: fica separado e vira candidato
        _doc("d5", [("Eva Nunes", None, None)]),
        _doc("d6", [("Eva Nunes", None, "0000-0003-0000-0003")]),
    ]
    i = identificar(docs)
    pessoa = {(a.doc, a.posicao): i.pessoas[i.pessoa_da_autoria[k]].interno for k, a in enumerate(i.autorias)}
    assert pessoa[("d1", 0)] == pessoa[("d2", 0)] != pessoa[("d3", 0)]
    assert i.conflitos == 1
    assert pessoa[("d1", 1)] == pessoa[("d4", 0)]
    assert pessoa[("d2", 1)] == pessoa[("d4", 1)] == "openalex:A3"
    # a "Eva" de d5 é a mesma da de d6? Sem ORCID em d5, entra na única com o mesmo nome
    assert pessoa[("d5", 0)] == pessoa[("d6", 0)]
    ids = [p.publicado for p in i.pessoas]
    assert len(ids) == len(set(ids)) and all(not ORCID.search(x) for x in ids)
    # correções manuais: fundir força a união; nomes troca o nome exibido
    anas = sorted({pessoa[("d1", 0)], pessoa[("d3", 0)]})
    j = identificar(docs, CorrecoesPessoas(fundir=[anas], nomes={anas[0]: "Ana M. Silva"}))
    pj = {(a.doc, a.posicao): j.pessoas[j.pessoa_da_autoria[k]] for k, a in enumerate(j.autorias)}
    assert pj[("d1", 0)] is pj[("d3", 0)] and pj[("d1", 0)].nome == "Ana M. Silva"


def test_desenho_reprodutivel():
    arestas = pares_ponderados({f"d{k}": [f"p{k}", f"p{k + 1}", f"p{k % 3}"] for k in range(12)} | {"x": ["q", "r"]})
    a, b = desenhar(grafo(arestas)), desenhar(grafo(dict(reversed(list(arestas.items())))))
    assert a == b and len(a) == len({x for par in arestas for x in par})
    assert all(-1 <= x <= 1 and -1 <= y <= 1 for x, y in a.values())


def test_citacoes_e_canone():
    refs = [
        {"obra": "W1", "citada": "W2"},  # interna
        {"obra": "W2", "citada": "W1"},  # anacrônica: W1 é de 2020, W2 de 2012
        {"obra": "W1", "citada": "W9"},
        {"obra": "W2", "citada": "W9"},
        {"obra": "W1", "citada": "W8"},  # outra edição da W9
        {"obra": "W3", "citada": "W7"},
    ]
    citadas = [
        {"id": "W9", "titulo": "O Príncipe", "autores": ["N. Maquiavel"], "citacoes": 900},
        {"id": "W8", "titulo": "O príncipe", "autores": ["Nicolau Maquiavel"], "citacoes": 50},
        {"id": "W7", "titulo": "Outro livro", "autores": ["Alguém"], "citacoes": 10},
    ]
    doc = {"W1": "a", "W2": "b", "W3": "c"}
    c = cit.calcular(refs, citadas, doc, {"a": 2020, "b": 2012, "c": 2015}, {"a": 0, "b": 1, "c": 1}, {0: 0, 1: 1})
    assert c.internas == [("a", "b")] and c.anacronicas == 1
    assert c.fluxo_topicos == {(0, 1): 1} and c.fluxo_macrotemas == {(0, 1): 1}
    primeiro = c.canone[0]
    assert (primeiro.id, primeiro.n, primeiro.edicoes, primeiro.citantes) == ("W9", 2, ["W8"], ["a", "b"])
    assert c.cobertura["com_referencias"] == 3


@pytest.fixture(scope="module")
def projeto(tmp_path_factory):
    import respx
    from conftest import OLLAMA_FALSO, ApisFalsas

    from mapa_da_ciencia.geografia.pipeline import gerar_geografia
    from mapa_da_ciencia.topicos.pipeline import gerar_topicos

    pasta = tmp_path_factory.mktemp("redes")
    mp = pytest.MonkeyPatch()
    mp.setenv("OLLAMA_HOST", OLLAMA_FALSO)
    with respx.mock(assert_all_called=False) as router:
        ApisFalsas(router)
        p = Projeto.criar(pasta / "sintetico", modelo="vazio", perfil=PERFIS["leve"])
        docs, temas = corpus_sintetico()
        pool = {t: [f"Pessoa{t.capitalize()}{k} Sobrenome{t}{k}" for k in range(6)] for t in set(temas.values())}
        novos = []
        for i, d in enumerate(docs):
            coautores = pool[temas[d.id]][: 1 + i % 3]  # 1 a 3 coautores do mesmo tema
            autores = [*d.autores] + [
                Autor(nome=n.split()[0], sobrenome=n.split()[1], afiliacoes=["aff2"]) for n in coautores
            ]
            nome, uf, pais, iid = AFILIACOES[(i + 1) % 4]
            autorias = [*d.autorias_openalex] + [
                AutoriaOpenAlex(
                    nome=n,
                    id=f"A{abs(hash(n)) % 10**6}" if k == 0 else None,
                    instituicoes=[InstituicaoOpenAlex(id=iid, nome=nome, pais=pais, tipo="education")],
                )
                for k, n in enumerate(coautores)
            ]
            afiliacoes = [*d.afiliacoes, Afiliacao(id="aff2", instituicao=nome, uf=uf, pais=pais, fonte="v240")]
            novos.append(
                d.model_copy(
                    update={
                        "autores": autores,
                        "autorias_openalex": autorias if d.autorias_openalex else [],
                        "afiliacoes": afiliacoes,
                        "openalex_id": f"W{i:05d}",
                    }
                )
            )
        gravar_documentos(novos, p.dados / ARQUIVO)
        internas = [(i, j) for i in range(0, len(novos), 3) for j in (i + 1, i + 2) if j < len(novos)]
        refs = [{"obra": f"W{i:05d}", "citada": f"W{j:05d}"} for i, j in internas]
        refs += [{"obra": f"W{i:05d}", "citada": "W99999"} for i in range(0, len(novos), 2)]
        gravar_tabela(refs, COLUNAS_REFERENCIAS, p.dados / ARQUIVO_REFERENCIAS, ordem="obra")
        citada = {"id": "W99999", "titulo": "Um clássico", "ano": 1970, "autores": ["Autor Clássico"], "n_autores": 1}
        gravar_tabela([citada], COLUNAS_CITADAS, p.dados / ARQUIVO_CITADAS)
        gerar_topicos(p)
        gerar_geografia(p)
    mp.undo()
    return p


def test_redes_de_ponta_a_ponta(projeto):
    r = gerar_redes(projeto)
    assert r.com_coautoria > 0 and r.instituicoes and r.citacoes_internas and r.canone == 1
    assert redes_em_dia(projeto) is True
    dados = projeto.saida / "dados"
    texto = (dados / "redes.json").read_text(encoding="utf-8")
    redes = m.Redes.model_validate_json(texto)
    citacoes = m.Citacoes.model_validate_json((dados / "citacoes.json").read_text(encoding="utf-8"))
    documentos = m.Documentos.model_validate_json((dados / "documentos.json").read_text(encoding="utf-8"))
    # cada autoria aponta para um documento e uma pessoa que existem
    n_docs, n_pessoas = len(documentos.colunas.id), len(redes.pessoas.id)
    assert all(0 <= d < n_docs for d in redes.autorias.doc) and all(0 <= x < n_pessoas for x in redes.autorias.pessoa)
    # a força de cada pessoa é o número de documentos em que ela teve coautor
    por_doc: dict[int, set[int]] = {}
    for d, x in zip(redes.autorias.doc, redes.autorias.pessoa, strict=True):
        por_doc.setdefault(d, set()).add(x)
    com_coautor = {x for s in por_doc.values() if len(s) > 1 for x in s}
    assert {i for i, g in enumerate(redes.pessoas.grau) if g > 0} == com_coautor
    assert all(redes.pessoas.x[i] is not None for i in com_coautor)
    # citações: dentro do corpus, sem laços; o cânone tem os citantes
    assert all(a != b for a, b in zip(citacoes.internas.de, citacoes.internas.para, strict=True))
    assert citacoes.canone[0].n == len(set(citacoes.canone_citantes.doc))
    assert sum(map(sum, citacoes.fluxo_macrotemas)) <= len(citacoes.internas.de)
    # nada de e-mail nem ORCID
    assert "@" not in texto and not ORCID.search(texto)
    # reprodutível: de novo, o mesmo arquivo
    gerar_redes(projeto)
    assert (dados / "redes.json").read_text(encoding="utf-8") == texto
    # uma correção no pessoas.yaml deixa as redes desatualizadas
    (projeto.raiz / "pessoas.yaml").write_text("nomes: {}\n", encoding="utf-8")
    assert redes_em_dia(projeto) is False
    agregados = json.loads((dados / "agregados.json").read_text(encoding="utf-8"))
    assert agregados["arestas_coautoria"] > 0 and agregados["canone_n"] == [citacoes.canone[0].n]
