"""As redes: pesos fracionários, identidade das pessoas, desenho reprodutível, citações e a etapa de ponta a ponta."""

import hashlib
import json
import re
from pathlib import Path

import pytest
from corpus_sintetico import AFILIACOES, corpus_sintetico

from mapa_da_ciencia.armazenamento import (
    ARQUIVO,
    ARQUIVO_CITADAS,
    ARQUIVO_REFERENCIAS,
    gravar_documentos,
    gravar_tabela,
    ler_tabela,
)
from mapa_da_ciencia.contrato import modelos as m
from mapa_da_ciencia.contrato.redes import fluxo_por_posicao, instituicoes_fora_de_afiliacoes
from mapa_da_ciencia.documento import Afiliacao, Autor, AutoriaOpenAlex, Documento, InstituicaoOpenAlex, Texto
from mapa_da_ciencia.fontes.openalex import COLUNAS_CITADAS, COLUNAS_REFERENCIAS
from mapa_da_ciencia.llm.perfis import PERFIS
from mapa_da_ciencia.projeto import Projeto
from mapa_da_ciencia.redes import citacoes as cit
from mapa_da_ciencia.redes.desenho import desenhar
from mapa_da_ciencia.redes.grafos import grafo, pares_ponderados
from mapa_da_ciencia.redes.pessoas import CorrecoesPessoas, id_publicado, identificar
from mapa_da_ciencia.redes.pipeline import gerar_redes, redes_em_dia
from mapa_da_ciencia.segredos import segredo

ORCID = re.compile(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]")


def test_pesos_fracionarios():
    arestas = pares_ponderados({"d1": ["a", "b", "c"], "d2": ["a", "b"], "d3": ["a"], "d4": ["b", "b", "c"]})
    assert arestas[("a", "b")] == (1.5, 2) and arestas[("a", "c")] == (0.5, 1) and arestas[("b", "c")] == (1.5, 2)
    # a soma dos pesos é Σ n/2 nos documentos com coautoria (autores distintos)
    assert sum(p for p, _ in arestas.values()) == pytest.approx(3 / 2 + 2 / 2 + 2 / 2)
    forca = {x: sum(p for par, (p, _) in arestas.items() if x in par) for x in "abc"}
    assert forca == {"a": 2, "b": 3, "c": 2}  # documentos com coautor de cada um


def _doc(i: str, autores: list[tuple]) -> Documento:
    """autores: (nome, id do OpenAlex, ORCID da ArticleMeta[, instituição do OpenAlex[, ORCID do OpenAlex]])."""
    completos = [(*a, None, None)[:5] for a in autores]
    return Documento(
        id=i,
        fonte="articlemeta",
        tipo="research-article",
        ano=2020,
        titulos=[Texto(idioma="pt", texto=f"Título {i}")],
        autores=[Autor(nome=" ".join(n.split()[:-1]), sobrenome=n.split()[-1], orcid=o) for n, _, o, _, _ in completos],
        autorias_openalex=[
            AutoriaOpenAlex(
                nome=n, id=a, orcid=o_oa, instituicoes=[InstituicaoOpenAlex(id=inst, nome=inst)] if inst else []
            )
            for n, a, _, inst, o_oa in completos
        ],
    )


def _pessoas(ident) -> dict[tuple[str, int], str]:
    return {(a.doc, a.posicao): ident.pessoas[ident.pessoa_da_autoria[k]].interno for k, a in enumerate(ident.autorias)}


ORCID_1, ORCID_2, ORCID_3 = "0000-0001-0000-0001", "0000-0002-0000-0002", "0000-0003-0000-0003"


def test_identidade_das_pessoas():
    docs = [
        _doc("d1", [("Ana Silva", "A1", ORCID_1), ("Beto Souza", None, None)]),
        _doc("d2", [("Ana Silva", "A1", None), ("Caio Lima", "A3", None)]),
        # o mesmo id do OpenAlex com outro ORCID: no piloto, era a mesma pessoa com dois registros no ORCID; junta, e
        # a pessoa vai para a revisão (dois ORCIDs)
        _doc("d3", [("Ana Silva", "A1", ORCID_2), ("Dora Reis", None, None)]),
        # sem id nem ORCID: entra na única "Beto Souza" que existe
        _doc("d4", [("Beto Souza", None, None), ("Caio Lima", "A3", None)]),
        # homônimo sem id, sem coautor e sem instituição em comum: entra na única "Eva Nunes" com id (regra 2)
        _doc("d5", [("Eva Nunes", None, None)]),
        _doc("d6", [("Eva Nunes", None, ORCID_3)]),
    ]
    i = identificar(docs, segredo=b"teste")
    pessoa = _pessoas(i)
    assert pessoa[("d1", 0)] == pessoa[("d2", 0)] == pessoa[("d3", 0)] == "openalex:A1"
    assert i.conflitos == 1  # uma pessoa com dois ORCIDs
    assert pessoa[("d1", 1)] == pessoa[("d4", 0)]
    assert pessoa[("d2", 1)] == pessoa[("d4", 1)] == "openalex:A3"
    assert pessoa[("d5", 0)] == pessoa[("d6", 0)]
    ids = [p.publicado for p in i.pessoas]
    assert len(ids) == len(set(ids)) and all(not ORCID.search(x) for x in ids)
    # nenhum id do OpenAlex em duas pessoas
    por_id = {}
    for k, a in enumerate(i.autorias):
        if a.openalex:
            por_id.setdefault(a.openalex, set()).add(i.pessoa_da_autoria[k])
    assert all(len(x) == 1 for x in por_id.values())


def test_orcid_conferido_pelo_nome():
    docs = [
        _doc("d1", [("Matheus Mazzilli Pereira", "A2", ORCID_2), ("Ana Lima", "A9", None)]),
        _doc("d2", [("Matheus Mazzilli Pereira", "A2", ORCID_2)]),
        _doc("d3", [("Marcelo Kunrath Silva", "A1", ORCID_1)]),
        # um ORCID trocado na fonte: o de Matheus na autoria de Marcelo (que tem o id do OpenAlex dele)
        _doc("d4", [("Marcelo Kunrath Silva", "A1", ORCID_2), ("Rui Dias", "A8", None)]),
        # ArticleMeta e OpenAlex discordam do ORCID de Rui: nenhum dos dois vale
        _doc("d5", [("Rui Dias", "A8", ORCID_1, None, ORCID_3)]),
    ]
    i = identificar(docs, segredo=b"teste")
    pessoa = _pessoas(i)
    assert pessoa[("d1", 0)] == pessoa[("d2", 0)] != pessoa[("d4", 0)]
    assert pessoa[("d3", 0)] == pessoa[("d4", 0)] == "openalex:A1"
    assert [(i.autorias[k].id, o) for k, o in i.orcids_retirados] == [("d4#0", ORCID_2)]
    assert i.orcids_divergentes == 1 and i.autorias[[a.id for a in i.autorias].index("d5#0")].orcid is None
    matheus = next(p for p in i.pessoas if p.interno == "openalex:A2")
    assert matheus.nome == "Matheus Mazzilli Pereira" and len(matheus.autorias) == 2


def test_homonimos_e_variantes_com_instituicao_ou_coautor_em_comum():
    docs = [
        # dois ids do OpenAlex para o mesmo "Fabiano Santos", com a mesma instituição
        _doc("d1", [("Fabiano Santos", "A1", None, "I1")]),
        _doc("d2", [("Fabiano Santos", "A2", ORCID_1, "I1")]),
        # grafia variante com a mesma instituição
        _doc("d3", [("Marjorie Marona", "A3", None, "I2")]),
        _doc("d4", [("Marjorie Correa Marona", "A4", None, "I2")]),
        # homônimos com um coautor em comum (e ORCIDs diferentes, que não impedem mais)
        _doc("d5", [("Tiago Lopes", "A5", ORCID_2), ("Marcos Maio", "A7", None)]),
        _doc("d6", [("Tiago Lopes", "A6", ORCID_3), ("Marcos Maio", "A7", None)]),
        # "Ana Silva" não emenda "Ana Maria Silva" com "Ana Paula Silva", ainda que as três dividam a instituição
        _doc("d7", [("Ana Silva", "A10", None, "I3")]),
        _doc("d8", [("Ana Maria Silva", "A11", None, "I3")]),
        _doc("d9", [("Ana Paula Silva", "A12", None, "I3")]),
        # homônimos sem nada em comum: ficam separados e vão para a revisão
        _doc("d10", [("Luis Fernandes", "A13", None, "I4")]),
        _doc("d11", [("Luis Fernandes", "A14", None, "I5")]),
    ]
    i = identificar(docs, segredo=b"teste")
    pessoa = _pessoas(i)
    assert pessoa[("d1", 0)] == pessoa[("d2", 0)]
    assert pessoa[("d3", 0)] == pessoa[("d4", 0)]
    assert pessoa[("d5", 0)] == pessoa[("d6", 0)]
    assert pessoa[("d8", 0)] != pessoa[("d9", 0)]
    assert pessoa[("d10", 0)] != pessoa[("d11", 0)]
    assert ("openalex:A13", "openalex:A14", "homonimo") in {(c.a, c.b, c.tipo) for c in i.candidatos}
    assert any(c.tipo == "variante" for c in i.candidatos)
    # as instituições da geografia também contam
    j = identificar(docs, segredo=b"teste", instituicoes={("d10", 0): {"I9"}, ("d11", 0): {"I9"}})
    assert _pessoas(j)[("d10", 0)] == _pessoas(j)[("d11", 0)]


def test_pessoas_yaml_com_ids_de_qualquer_autoria():
    docs = [
        _doc("d1", [("Ana Silva", "A1", ORCID_1, "I1"), ("Beto Souza", "A5", None)]),
        _doc("d2", [("Ana Silva", "A2", None, "I1")]),  # juntada pela instituição
        _doc("d3", [("Ana Silva", "A1", None)]),  # uma autoria que o OpenAlex pôs no id A1 por engano
        _doc("d4", [("Eva Nunes", "A3", None)]),
        _doc("d5", [("Eva Nunes", "A4", None)]),
    ]
    assert _pessoas(identificar(docs, segredo=b"t"))[("d1", 0)] == _pessoas(identificar(docs, segredo=b"t"))[("d2", 0)]
    correcoes = CorrecoesPessoas(
        # nao_fundir desfaz a fusão automática e tira uma autoria do id do OpenAlex
        nao_fundir=[["openalex:A1", "openalex:A2"], ["orcid:0000-0001-0000-0001", "d3#0"]],
        # fundir aceita o id de qualquer autoria (aqui, pelo nome e pelo id que não é o menor)
        fundir=[["nome:eva nunes", "openalex:A4"]],
        nomes={"openalex:A4": "Eva M. Nunes", "A5": "Ninguém", "openalex:A999": "Ninguém"},
    )
    i = identificar(docs, correcoes, segredo=b"t")
    pessoa = _pessoas(i)
    assert len({pessoa[("d1", 0)], pessoa[("d2", 0)], pessoa[("d3", 0)]}) == 3
    assert pessoa[("d4", 0)] == pessoa[("d5", 0)]
    eva = i.pessoas[i.pessoa_da_autoria[[a.id for a in i.autorias].index("d4#0")]]
    assert eva.nome == "Eva M. Nunes"
    # o id do OpenAlex separado explicitamente fica em duas pessoas, com ids internos distintos
    assert len({p.interno for p in i.pessoas}) == len(i.pessoas)
    # ids desconhecidos viram aviso, com a dica do prefixo
    (aviso,) = i.avisos
    assert "2 id(s) não existem" in aviso and "A5 (falta o prefixo: openalex:A5)" in aviso and "openalex:A999" in aviso


def test_exemplo_do_guia_funciona():
    import yaml

    guia = (Path(__file__).resolve().parent.parent / "docs" / "guias" / "redes.md").read_text(encoding="utf-8")
    bloco = next(b for b in re.findall(r"```yaml\n(.*?)```", guia, re.S) if "fundir:" in b)
    correcoes = CorrecoesPessoas.model_validate(yaml.safe_load(bloco))
    docs = [
        _doc("d1", [("Maria Silva", "A1111111111", None, "I1")]),
        _doc("d2", [("Maria S. Silva", "A2222222222", None, "I2")]),
        _doc("d3", [("Rui Lima", "A3333333333", None, "I3")]),
        _doc("d4", [("Rui Lima", "A4444444444", None, "I3")]),  # a instituição juntaria; o nao_fundir separa
        _doc("S0011-52582020000100201", [("Ana Souza", "A6666666666", None), ("Eva Dias", "A5555555555", None)]),
        _doc("d6", [("Eva Dias", "A5555555555", None)]),
    ]
    i = identificar(docs, correcoes, segredo=b"t")
    pessoa = _pessoas(i)
    assert not i.avisos
    assert pessoa[("d1", 0)] == pessoa[("d2", 0)] and pessoa[("d3", 0)] != pessoa[("d4", 0)]
    assert pessoa[("S0011-52582020000100201", 1)] != pessoa[("d6", 0)]
    maria = i.pessoas[i.pessoa_da_autoria[[a.id for a in i.autorias].index("d1#0")]]
    assert maria.nome == "Maria da Silva"


def test_pessoas_yaml_com_erro_de_formato(tmp_path):
    from mapa_da_ciencia.config import ErroConfig
    from mapa_da_ciencia.redes.pessoas import ler_correcoes

    (tmp_path / "pessoas.yaml").write_text("fundir:\n  - openalex:A1, openalex:A2\n", encoding="utf-8")
    with pytest.raises(ErroConfig, match=r"cada item é uma lista de ids entre colchetes") as erro:
        ler_correcoes(tmp_path)
    assert "pydantic" not in str(erro.value)


def test_id_publicado_nao_se_liga_ao_orcid():
    # sem o segredo do projeto, o id publicado não se liga ao ORCID nem ao id do OpenAlex (cr-03: o SHA-256 sem
    # chave de "orcid:…" se quebrava por força bruta em minutos)
    orcid = "orcid:0000-0002-1825-0097"
    publicado = id_publicado(orcid, b"segredo do projeto")
    assert publicado != "p" + hashlib.sha256(orcid.encode()).hexdigest()[:10]
    assert publicado == id_publicado(orcid, b"segredo do projeto") != id_publicado(orcid, b"outro segredo")
    assert re.fullmatch(r"p[0-9a-f]{10}", publicado)


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


def test_fluxo_pela_posicao_dos_macrotemas():
    # ids não contíguos, como os do piloto: o 7 e o 8 não somem, e não aparece um "macrotema 3" vazio
    fluxo = {(0, 7): 2, (7, 7): 5, (8, 2): 1, (5, 0): 3, (-1, 0): 4}
    matriz = fluxo_por_posicao(fluxo, [0, 1, 2, 5, 6, 7, 8])
    assert len(matriz) == 7 and all(len(linha) == 7 for linha in matriz) and sum(map(sum, matriz)) == 11
    assert (matriz[0][5], matriz[5][5], matriz[6][2], matriz[3][0]) == (2, 5, 1, 3)


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
                    # a USP com ROR (o id do contrato vira `ror:…`), as outras com o id do OpenAlex (`openalex:I…`)
                    instituicoes=[
                        InstituicaoOpenAlex(
                            id=iid, ror="036rp1748" if iid == "I1001" else None, nome=nome, pais=pais, tipo="education"
                        )
                    ],
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
    # as instituições da rede têm os ids de afiliacoes.json (o navegador acha nome, sigla e documentos por eles)
    afiliacoes = m.Afiliacoes.model_validate_json((dados / "afiliacoes.json").read_text(encoding="utf-8"))
    assert redes.instituicoes and instituicoes_fora_de_afiliacoes(redes, afiliacoes) == []
    assert {"ror:036rp1748", "openalex:I1002"} <= set(redes.instituicoes.id)
    # citações: dentro do corpus, sem laços; o cânone tem os citantes
    assert all(a != b for a, b in zip(citacoes.internas.de, citacoes.internas.para, strict=True))
    assert citacoes.canone[0].n == len(set(citacoes.canone_citantes.doc))
    topicos = m.Topicos.model_validate_json((dados / "topicos.json").read_text(encoding="utf-8"))
    com_topico = [
        (a, b)
        for a, b in zip(citacoes.internas.de, citacoes.internas.para, strict=True)
        if documentos.colunas.topico[a] >= 0 and documentos.colunas.topico[b] >= 0
    ]
    assert len(citacoes.fluxo_macrotemas) == len(topicos.macrotemas)
    assert sum(map(sum, citacoes.fluxo_macrotemas)) == len(com_topico)
    # nada de e-mail nem ORCID, e nenhum id publicado que seja o hash sem chave do id interno
    assert "@" not in texto and not ORCID.search(texto)
    internos = {p["id"]: p["interno"] for p in ler_tabela(projeto.dados / "redes" / "pessoas.parquet")}
    sem_chave = {"p" + hashlib.sha256(i.encode()).hexdigest()[:10] for i in internos.values()}
    assert set(redes.pessoas.id) == set(internos) and not sem_chave & set(redes.pessoas.id)
    assert segredo(projeto, "redes") == segredo(projeto, "redes")  # guardado no estado.sqlite, fora de saida/
    # reprodutível: de novo, o mesmo arquivo
    gerar_redes(projeto)
    assert (dados / "redes.json").read_text(encoding="utf-8") == texto
    # uma correção no pessoas.yaml deixa as redes desatualizadas
    (projeto.raiz / "pessoas.yaml").write_text("nomes: {}\n", encoding="utf-8")
    assert redes_em_dia(projeto) is False
    agregados = json.loads((dados / "agregados.json").read_text(encoding="utf-8"))
    assert agregados["arestas_coautoria"] > 0 and agregados["canone_n"] == [citacoes.canone[0].n]
