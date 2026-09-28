"""As redes: pesos fracionários, identidade das pessoas, desenho reprodutível, citações e a etapa de ponta a ponta."""

import hashlib
import itertools
import json
import random
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
from mapa_da_ciencia.contrato.exportar import exportar
from mapa_da_ciencia.contrato.redes import fluxo_por_posicao, instituicoes_fora_de_afiliacoes
from mapa_da_ciencia.documento import Afiliacao, Autor, AutoriaOpenAlex, Documento, InstituicaoOpenAlex, Texto
from mapa_da_ciencia.fontes.openalex import COLUNAS_CITADAS, COLUNAS_REFERENCIAS
from mapa_da_ciencia.llm.perfis import PERFIS
from mapa_da_ciencia.projeto import Projeto
from mapa_da_ciencia.redes import citacoes as cit
from mapa_da_ciencia.redes import pessoas as mod_pessoas
from mapa_da_ciencia.redes.desenho import desenhar
from mapa_da_ciencia.redes.grafos import forcas, grafo, pares_ponderados
from mapa_da_ciencia.redes.pessoas import CorrecoesPessoas, id_publicado, identificar
from mapa_da_ciencia.redes.pipeline import gerar_redes, o_que_mudou, redes_em_dia
from mapa_da_ciencia.segredos import segredo

ORCID = re.compile(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]")


def test_pesos_fracionarios():
    arestas = pares_ponderados({"d1": ["a", "b", "c"], "d2": ["a", "b"], "d3": ["a"], "d4": ["b", "b", "c"]})
    assert arestas[("a", "b")] == (1.5, 2) and arestas[("a", "c")] == (0.5, 1) and arestas[("b", "c")] == (1.5, 2)
    # a soma dos pesos é Σ n/2 nos documentos com coautoria (autores distintos)
    assert sum(p for p, _ in arestas.values()) == pytest.approx(3 / 2 + 2 / 2 + 2 / 2)
    forca = {x: sum(p for par, (p, _) in arestas.items() if x in par) for x in "abc"}
    assert forca == {"a": 2, "b": 3, "c": 2}  # documentos com coautor de cada um
    # pesos exatos (sem arredondar a 6 casas) e a força como a contagem inteira de documentos com parceiro
    quatro = pares_ponderados({"d1": ["a", "b", "c", "d"]})
    assert quatro[("a", "b")] == (1 / 3, 1) and forcas({"d1": ["a", "b", "c", "d"], "d2": ["a"]}) == dict.fromkeys(
        "abcd", 1
    )


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


def test_nome_exibido_sem_caixa_alta():
    docs = [
        _doc("d1", [("ARGELINA CHEIBUB FIGUEIREDO", "A1", None)]),
        _doc("d2", [("ARGELINA CHEIBUB FIGUEIREDO", "A1", None)]),
        _doc("d3", [("Argelina Cheibub Figueiredo", "A1", None)]),
        _doc("d4", [("MARTA RODRIGUEZ DE ASSIS MACHADO", "A2", None)]),
    ]
    nomes = sorted(p.nome for p in identificar(docs, segredo=b"t").pessoas)
    assert nomes == ["Argelina Cheibub Figueiredo", "Marta Rodriguez de Assis Machado"]


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
        # uma pessoa com uma grafia abreviada ("J. Feres Jr.") ainda se junta a um homônimo com coautor em comum
        _doc("d12", [("Joao Feres Junior", "A15", None), ("Luiz Campos", "A17", None)]),
        _doc("d13", [("Joao Feres Junior", "A16", None), ("Luiz Campos", "A17", None)]),
        _doc("d14", [("J. Feres Jr.", "A16", None)]),
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
    assert pessoa[("d12", 0)] == pessoa[("d13", 0)] == pessoa[("d14", 0)]
    assert ("openalex:A13", "openalex:A14", "homonimo") in {(c.a, c.b, c.tipo) for c in i.candidatos}
    assert any(c.tipo == "variante" for c in i.candidatos)
    # as instituições da geografia também contam
    j = identificar(docs, segredo=b"teste", instituicoes={("d10", 0): {"I9"}, ("d11", 0): {"I9"}})
    assert _pessoas(j)[("d10", 0)] == _pessoas(j)[("d11", 0)]


def test_grafia_curta_se_junta_quando_um_nome_por_extenso_contem_todos():
    """Uma grafia curta não barra a união quando um nome por extenso contém todos os outros (mr2-02), mas um nome com
    inicial não conta como nome inteiro."""
    docs = [
        # "Francisco Tavares" e "Francisco Mata Machado" não se comparam, mas "... Mata Machado Tavares" contém os dois
        _doc("d1", [("Francisco Mata Machado Tavares", "A1", None, "I1")]),
        _doc("d2", [("Francisco Tavares", "A1", None, "I1")]),
        _doc("d3", [("Francisco Mata Machado", "A2", None, "I1")]),
        # "André M. Cunha" conteria "André Marenco" (o "M."), mas não é um nome por extenso
        _doc("d4", [("André M. Cunha", "A3", None, "I2")]),
        _doc("d5", [("André Moreira Cunha", "A3", None, "I2")]),
        _doc("d6", [("André Marenco", "A4", None, "I2")]),
    ]
    pessoa = _pessoas(identificar(docs, segredo=b"teste"))
    assert pessoa[("d1", 0)] == pessoa[("d2", 0)] == pessoa[("d3", 0)]
    assert pessoa[("d4", 0)] == pessoa[("d5", 0)] != pessoa[("d6", 0)]


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


def test_nao_fundir_de_uma_autoria_nao_parte_o_resto():
    docs = [_doc(f"d{k}", [("Ana Lima", "A1", None)]) for k in range(1, 6)]
    for separada in ("d1#0", "d3#0", "d5#0"):  # a primeira, uma do meio e a última autoria do id
        i = identificar(docs, CorrecoesPessoas(nao_fundir=[["openalex:A1", separada]]), segredo=b"t")
        pessoa = _pessoas(i)
        resto = {pessoa[(f"d{k}", 0)] for k in range(1, 6) if f"d{k}#0" != separada}
        assert len(resto) == 1 and pessoa[(separada.split("#")[0], 0)] not in resto, separada
        assert len(i.pessoas) == 2


def test_regra_dos_nomes_nao_compara_todas_as_marias(monkeypatch):
    """250 "Maria" de sobrenomes diferentes, sem nada em comum, não viram 31 mil comparações de nomes (cr-17)."""
    chamadas = 0
    original = mod_pessoas._comparaveis

    def contar(a: str, b: str) -> bool:
        nonlocal chamadas
        chamadas += 1
        return original(a, b)

    monkeypatch.setattr(mod_pessoas, "_comparaveis", contar)
    sobrenomes = ["".join(t).title() for t in itertools.product("bcfghjklmn", "aeiou", "rstvz")]
    docs = [_doc(f"d{k}", [(f"Maria {s}", f"A{k}", None)]) for k, s in enumerate(sobrenomes)]
    assert len(identificar(docs, segredo=b"t").pessoas) == 250
    assert chamadas < 1000


def test_pares_de_nomes_cobrem_todos_os_comparaveis():
    """Os pares candidatos da regra 3 incluem todo par de nomes comparáveis com o mesmo primeiro nome: com iniciais,
    com "Júnior" e com só o primeiro nome."""
    rng = random.Random(3)
    primeiros, partes = ["maria", "ana", "m"], ["silva", "s", "santos", "souza", "costa", "c", "junior", ""]
    nomes = sorted(
        {" ".join(filter(None, [rng.choice(primeiros), rng.choice(partes), rng.choice(partes)])) for _ in range(600)}
    )
    pares = set(mod_pessoas._pares_de_nomes({k: {n} for k, n in enumerate(nomes)}))
    comparaveis = [
        (a, b)
        for a, b in itertools.combinations(range(len(nomes)), 2)
        if nomes[a].split()[0] == nomes[b].split()[0] and mod_pessoas._comparaveis(nomes[a], nomes[b])
    ]
    assert len(comparaveis) > 50
    assert [(nomes[a], nomes[b]) for a, b in comparaveis if (a, b) not in pares] == []


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


def test_resumo_da_revisao_na_ordem_da_tabela():
    from mapa_da_ciencia.redes.revisao import resumo_por_tipo

    resumo = resumo_por_tipo({"dois_orcids": 17, "variante": 66, "homonimo": 10, "orcid_retirado": 5})
    assert resumo == "10 homônimos, 66 grafias variantes, 17 dois ORCIDs, 5 ORCID de outro nome"


def test_frases_da_documentacao_batem_com_as_contas():
    docs = Path(__file__).resolve().parent.parent / "docs"
    guia = " ".join((docs / "guias" / "ler-as-redes.md").read_text(encoding="utf-8").split())
    explicacao = " ".join((docs / "explicacoes" / "redes.md").read_text(encoding="utf-8").split())
    # dez autores num artigo: 45 pares de peso 1/9 (e não "dez linhas fracas")
    dez = pares_ponderados({"d": [f"a{k}" for k in range(10)]})
    assert len(dez) == 45 and {p for p, _ in dez.values()} == {1 / 9}
    assert "45 linhas fracas, de peso 1/9" in guia and "45 pares de peso 1/9" in explicacao
    # um artigo de n autores soma n/2, e não 1 ("como na geografia, cada documento vale 1")
    assert sum(p for p, _ in dez.values()) == pytest.approx(10 / 2) and "soma, então, `n/2`" in explicacao
    assert "Como na geografia, cada documento vale 1" not in explicacao
    assert "dois nós perto estão ligados" not in explicacao


def test_desenho_reprodutivel():
    arestas = pares_ponderados({f"d{k}": [f"p{k}", f"p{k + 1}", f"p{k % 3}"] for k in range(12)} | {"x": ["q", "r"]})
    a, b = desenhar(grafo(arestas)), desenhar(grafo(dict(reversed(list(arestas.items())))))
    assert a == b and len(a) == len({x for par in arestas for x in par})
    assert all(-1 <= x <= 1 and -1 <= y <= 1 for x, y in a.values())


def test_desenho_com_o_maior_componente_em_cima_e_em_destaque():
    # um componente de 40 nós e 60 duplas isoladas (como o piloto: o gigante e centenas de pares)
    grupos = {f"g{k}": [f"p{k}", f"p{k + 1}", f"p{(k * 7) % 40}"] for k in range(40)}
    grupos |= {f"d{k}": [f"a{k}", f"b{k}"] for k in range(60)}
    pos = desenhar(grafo(pares_ponderados(grupos)))
    gigante = [pos[f"p{k}"] for k in range(40)]
    pares = [pos[x] for k in range(60) for x in (f"a{k}", f"b{k}")]
    # em cima (o y cresce para cima; a vista inverte para a tela), com a maior parte da altura
    assert min(y for _, y in gigante) > max(y for _, y in pares)
    ys = [y for _, y in pos.values()]
    assert max(y for _, y in gigante) - min(y for _, y in gigante) > 0.5 * (max(ys) - min(ys))
    # e o desenho mais largo que alto, como a vista
    xs = [x for x, _ in pos.values()]
    assert 1.2 < (max(xs) - min(xs)) / (max(ys) - min(ys)) < 2.2


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


def _ref(sobrenomes, titulo, ano, prenomes=None, fonte=None):
    """Uma referência da ArticleMeta (como em `referencias_articlemeta.parquet`)."""
    return {"titulo": titulo, "titulo_fonte": fonte, "sobrenomes": sobrenomes, "prenomes": prenomes or [], "ano": ano}


def test_autoria_do_canone_conferida_nas_referencias():
    # o OpenAlex casou a referência com a resenha: o resenhista (Frankel) em primeiro, e o ano da resenha
    waltz = {"titulo": "Theory of International Politics", "ano": 1980, "tipo": "article",
             "autores": ["Joseph Frankel", "Kenneth N. Waltz"]}  # fmt: skip
    refs = [_ref(["WALTZ"], "Theory of international politics", 1979, ["Kenneth"]) for _ in range(5)]
    c = cit.conferir_autoria(waltz, refs, 6)
    assert (c["autores"], c["ano"], c["resenha"], c["autoria_das_referencias"]) == (
        ["Kenneth N. Waltz"],
        1979,
        True,
        True,
    )
    # os dois autores são da obra: só a ordem muda, e o ano fica
    exec_leg = {"titulo": "Executivo e legislativo na nova ordem constitucional", "ano": 1999, "tipo": "article",
                "autores": ["Fernando Limongi", "Argelina Cheibub Figueiredo"]}  # fmt: skip
    refs = [
        _ref(["FIGUEIREDO", "LIMONGI"], None, 1999, fonte="Executivo e legislativo na nova ordem constitucional")
    ] * 4
    c = cit.conferir_autoria(exec_leg, refs, 4)
    assert c["autores"] == ["Argelina Cheibub Figueiredo", "Fernando Limongi"] and c["ano"] == 1999
    assert not c["resenha"]
    # resenha do Choice sem autor: o autor e o ano vêm das referências (o título sem o subtítulo também casa)
    choice = {"titulo": "Parties without partisans: political change in advanced industrial democracies", "ano": 2001,
              "tipo": "book-review", "veiculo": "Choice Reviews Online", "autores": []}  # fmt: skip
    refs = [_ref(["DALTON", "WATTENBERG"], "Parties without partisans", 2000, ["Russell J.", "Martin P."])] * 3
    c = cit.conferir_autoria(choice, refs, 3)
    assert c["autores"] == ["Russell J. Dalton", "Martin P. Wattenberg"] and c["ano"] == 2000 and c["resenha"]
    # pouca evidência: fica como o OpenAlex deu (mas a resenha do Choice continua marcada)
    c = cit.conferir_autoria(choice, refs[:2], 10)
    assert c["autores"] == [] and c["ano"] == 2001 and c["resenha"] and not c["autoria_das_referencias"]


def test_autoria_e_ano_do_canone_pelas_referencias():
    # KKV: o registro (do Choice) sem autor, e as referências trazem os três
    kkv = {"titulo": "Designing social inquiry", "ano": 1994, "tipo": "book-review", "veiculo": "Choice Reviews Online",
           "autores": []}  # fmt: skip
    refs = [_ref(["KING", "KEOHANE", "VERBA"], "Designing social inquiry", 1994, ["Gary", "Robert O.", "Sidney"])] * 5
    assert cit.conferir_autoria(kkv, refs, 5)["autores"] == ["Gary King", "Robert O. Keohane", "Sidney Verba"]
    # referências que abreviam com "et al." não tiram os coautores do OpenAlex
    artigo = {"titulo": "Um artigo a seis mãos", "ano": 2010, "tipo": "article",
              "autores": ["Ana Souza", "Bruno Lima", "Carla Dias"]}  # fmt: skip
    refs = [_ref(["SOUZA"], "Um artigo a seis mãos", 2010, ["Ana"])] * 4
    assert cit.conferir_autoria(artigo, refs, 4)["autores"] == ["Ana Souza", "Bruno Lima", "Carla Dias"]
    # o ano da obra, e não o do capítulo de coletânea de 2015, quando as referências concordam
    young = {"titulo": "Inclusion and Democracy", "ano": 2015, "tipo": "book-chapter", "autores": ["Iris Marion Young"]}
    refs = [_ref(["YOUNG"], "Inclusion and democracy", 2000, ["Iris Marion"])] * 5 + [
        _ref(["YOUNG"], "Inclusion and democracy", 2002, ["Iris Marion"])
    ]
    c = cit.conferir_autoria(young, refs, 6)
    assert (c["ano"], c["resenha"], c["autores"]) == (2000, False, ["Iris Marion Young"])
    # Kingdon: o 1985 do registro nunca aparece; sem um ano com 30%, a primeira edição que várias referências citam
    kingdon = {"titulo": "Agendas, Alternatives, and Public Policies", "ano": 1985, "tipo": "article",
               "autores": ["James L. Perry", "John W. Kingdon"]}  # fmt: skip
    anos = [1984, 1984, 1995, 1995, 2003, 2003, 2011, 2014, 2006, 1999, 1997]
    refs = [_ref(["KINGDON"], "Agendas, alternatives, and public policies", a, ["John"]) for a in anos]
    c = cit.conferir_autoria(kingdon, refs, 11)
    assert (c["autores"], c["ano"], c["resenha"]) == (["John W. Kingdon"], 1984, True)
    # "ZUCCO JR" é o mesmo Zucco do OpenAlex (o sufixo não conta como sobrenome)
    zucco = {"titulo": "Ideology or What? Legislative Behavior", "ano": 2009, "autores": ["César Zucco"]}
    refs = [_ref(["ZUCCO JR"], "Ideology or what? Legislative behavior", 2009, ["Cesar"])] * 4
    assert cit.conferir_autoria(zucco, refs, 4)["autores"] == ["César Zucco"]
    # um artigo com o ano certo no OpenAlex fica com ele
    abranches = {
        "titulo": "Presidencialismo de coalizão",
        "ano": 1988,
        "tipo": "article",
        "autores": ["Sérgio Abranches"],
    }
    refs = [_ref(["ABRANCHES"], "Presidencialismo de coalizão", 1988)] * 3 + [
        _ref(["ABRANCHES"], "Presidencialismo de coalizão", 1998)
    ] * 2
    assert cit.conferir_autoria(abranches, refs, 5)["ano"] == 1988


def test_canone_sem_titulos_genericos_nem_numeracao():
    refs = [{"obra": f"W{k}", "citada": "W91"} for k in range(3)] + [
        {"obra": f"W{k}", "citada": "W92"} for k in range(3)
    ]
    citadas = [
        {"id": "W91", "titulo": "Resumos", "autores": ["Maria Regina Soares de Lima"]},
        {"id": "W92", "titulo": "66. Civil Society and Political Theory", "autores": ["Jean L. Cohen"], "ano": 1992},
    ]
    doc = {f"W{k}": f"d{k}" for k in range(3)}
    c = cit.calcular(refs, citadas, doc, {f"d{k}": 2020 for k in range(3)}, {}, {})
    assert [o.titulo for o in c.canone] == ["Civil Society and Political Theory"]
    assert c.cobertura["titulos_genericos"] == 1
    assert c.sem_metadados == [] and c.cobertura["sem_metadados"] == 0  # "Resumos" tem metadados: saiu de propósito


def test_canone_soma_registros_da_mesma_obra_e_ignora_a_obra_apagada():
    refs = [{"obra": f"W{k}", "citada": "W91"} for k in (1, 2, 3)]
    refs += [{"obra": f"W{k}", "citada": "W92"} for k in (4, 5, 6)]
    refs += [{"obra": "W1", "citada": "W4285719527"}, {"obra": "W2", "citada": "W4285719527"}]
    refs += [{"obra": "W3", "citada": "W3"}]  # autorreferência
    citadas = [
        {"id": "W91", "titulo": "An Economic Theory of Democracy.", "autores": ["Edward C. Banfield", "Anthony Downs"]},
        {"id": "W92", "titulo": "An Economic Theory of Democracy", "autores": ["Dwaine Marvick"]},
        {"id": "W4285719527", "titulo": None, "autores": []},
    ]
    doc = {f"W{k}": f"d{k}" for k in range(1, 7)}
    downs = {f"d{k}": [_ref(["DOWNS"], "An economic theory of democracy", 1957, ["Anthony"])] for k in range(1, 7)}
    anos = {f"d{k}": 2020 for k in range(1, 7)}
    listadas = {"d1": 4, "d2": 2, "d3": 2, "d4": 1, "d5": 1, "d6": 2, "d7": 3}  # d7: casado, nenhuma resolvida
    c = cit.calcular(refs, citadas, doc, anos, {}, {}, referencias_articlemeta=downs, listadas=listadas)
    (obra,) = c.canone
    assert (obra.n, obra.autores, obra.ano, obra.resenha) == (6, ["Anthony Downs"], 1957, True)
    assert obra.edicoes in (["W92"], ["W91"])
    # a obra apagada não conta como referência, nem entra no cânone; a autorreferência é contada à parte
    assert c.cobertura["a_obras_apagadas"] == 2 and c.cobertura["referencias"] == 7
    assert c.cobertura["autorreferencias"] == 1 and c.n_referencias["d1"] == 1
    # cobertura por referência: 7 resolvidas de 15 listadas, com o d7 (casado, nenhuma resolvida) no denominador; por
    # documento, 1/4, 1/2, 2/2, 1, 1, 1/2 e 0: mediana 50%
    assert (c.cobertura["referencias_listadas"], c.cobertura["referencias_resolvidas"]) == (15, 7)
    assert c.cobertura["resolvidas_mediana_pct"] == 50
    assert c.cobertura["resenhas_no_canone"] == 1 and c.cobertura["sem_metadados"] == 0


_CANONE_NUM_PROCESSO = """
import json, sys
from mapa_da_ciencia.redes import citacoes as cit
dados = json.loads(sys.stdin.read())
c = cit.calcular(**dados)
print(json.dumps([[o.id, o.autores, o.ano, o.n, o.edicoes] for o in c.canone]))
"""


def test_canone_nao_depende_da_semente_de_hash():
    import json
    import os
    import subprocess
    import sys

    # "Democratic Brazil Revisited": nenhum primeiro autor tem a maioria, e Kingstone e Power empatam em todas as
    # referências (o desempate dependia da ordem de um set, que muda com a semente de hash)
    refs = [{"obra": f"W{k}", "citada": "W90"} for k in range(8)]
    refs += [{"obra": f"W{k}", "citada": "W91"} for k in range(4)]
    listas = [
        ["KINGSTONE", "POWER"],
        ["POWER", "KINGSTONE"],
        ["SILVA", "KINGSTONE", "POWER"],
        ["SOUZA", "POWER", "KINGSTONE"],
    ]
    am = {f"d{k}": [_ref(listas[k % 4], "Democratic Brazil revisited", 2008)] for k in range(8)}
    citadas = [
        {"id": "W90", "titulo": "Democratic Brazil Revisited", "autores": [], "ano": 2008},
        {"id": "W91", "titulo": "Democratic Brazil Revisited", "autores": ["Peter Kingstone"], "ano": 2008},
    ]
    dados = {
        "referencias": refs,
        "citadas": citadas,
        "doc_da_obra": {f"W{k}": f"d{k}" for k in range(8)},
        "anos": {f"d{k}": 2015 for k in range(8)},
        "topico_do_doc": {},
        "macro_do_topico": {},
        "referencias_articlemeta": am,
    }
    saidas = {
        semente: subprocess.run(
            [sys.executable, "-c", _CANONE_NUM_PROCESSO],
            input=json.dumps(dados),
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, "PYTHONHASHSEED": semente},
        ).stdout
        for semente in ("0", "1", "2", "3", "7", "12345")
    }
    assert len(set(saidas.values())) == 1, saidas
    # o empate vai para o menor sobrenome, e os dois registros da mesma obra somam
    ((_, autores, _, n, edicoes),) = json.loads(saidas["0"])
    assert autores == ["Kingstone", "Power"] and n == 8 and len(edicoes) == 1


def test_registros_da_mesma_obra_com_titulos_quase_iguais():
    citadas = {
        "W1": {"titulo": "Critical citizens: global support for democratic government", "autores": ["Pippa Norris"]},
        "W2": {"titulo": "Critical Citizens. Global Support for Democratic Governance", "autores": ["Pippa Norris"]},
        "W3": {"titulo": "Making Votes Count: Coordination in the World’s Systems", "autores": ["Gary W. Cox"]},
        "W4": {"titulo": "Making votes count: coordination in the world's systems", "autores": ["Gary Cox"]},
        "W5": {"titulo": "Democratic Deficit: Critical Citizens Revisited", "autores": ["Pippa Norris"]},
        "W6": {"titulo": "Critical citizens: global support for democratic government", "autores": ["Outra Pessoa"]},
    }
    conferidas = {w: {"autores": m["autores"]} for w, m in citadas.items()}
    assert sorted(cit._mesma_obra(citadas, conferidas)) == [["W1", "W2"], ["W3", "W4"], ["W5"], ["W6"]]


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
        # dois homônimos de temas e instituições diferentes, sem coautor em comum: ficam para a revisão
        com_oa = [i for i, d in enumerate(novos) if d.autorias_openalex]
        a = com_oa[0]
        par = [a, next(i for i in com_oa if temas[novos[i].id] != temas[novos[a].id] and i % 4 != a % 4)]
        for k, i in enumerate(par):
            d = novos[i]
            autores = [Autor(nome="Celso", sobrenome="Amorim"), *d.autores[1:]]
            oa = [AutoriaOpenAlex(nome="Celso Amorim", id=f"A900000{k}"), *d.autorias_openalex[1:]]
            afiliacoes = [x for x in d.afiliacoes if x.id != "aff1"]
            novos[i] = d.model_copy(update={"autores": autores, "autorias_openalex": oa, "afiliacoes": afiliacoes})
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


def test_erro_do_pessoas_yaml_mostra_o_exemplo_entre_colchetes(projeto):
    from typer.testing import CliRunner

    from mapa_da_ciencia.cli import app

    (projeto.raiz / "pessoas.yaml").write_text("fundir:\n  - openalex:A5034166995\n", encoding="utf-8")
    try:
        r = CliRunner().invoke(app, ["redes", "-P", str(projeto.raiz)], env={"COLUMNS": "200"})
    finally:
        (projeto.raiz / "pessoas.yaml").unlink()
    assert r.exit_code == 1
    assert "como [openalex:A1, openalex:A2]" in " ".join(r.output.split())


def test_consultar_as_redes_de_fora_do_projeto(projeto, tmp_path, monkeypatch):
    import mapa_da_ciencia.api as mapa

    gerar_redes(projeto)
    monkeypatch.chdir(tmp_path)  # o exemplo do guia, rodado de outra pasta
    guia = (Path(__file__).resolve().parent.parent / "docs" / "guias" / "redes.md").read_text(encoding="utf-8")
    sql = re.search(r'mapa\.consultar\(p, "(.*?)"\)', guia).group(1)
    linhas = mapa.consultar(projeto.raiz, sql)
    assert linhas and {"titulo", "ano", "autores", "n"} <= set(linhas[0])
    assert mapa.consultar(projeto.raiz, "SELECT count(*) AS n FROM redes_pessoas")[0]["n"] > 0


def test_revisao_com_evidencias_e_bloco_que_funciona(projeto):
    import yaml
    from typer.testing import CliRunner

    from mapa_da_ciencia.cli import app
    from mapa_da_ciencia.redes.pessoas import ler_correcoes

    gerar_redes(projeto)
    r = CliRunner().invoke(app, ["redes", "--revisar", "-P", str(projeto.raiz)], env={"COLUMNS": "200"})
    assert r.exit_code == 0, r.output
    # as evidências de cada lado, e o bloco inteiro: o Rich não pode engolir os colchetes como marcação
    assert "Celso Amorim" in r.output and "doc(s)" in r.output
    assert "use --limite" not in r.output  # tudo listado: nada a pedir
    curto = CliRunner().invoke(
        app, ["redes", "--revisar", "--limite", "1", "-P", str(projeto.raiz)], env={"COLUMNS": "200"}
    )
    assert "(mostrando 1 de" in curto.output or "Para revisar: 1 " in curto.output
    linha = next(x for x in r.output.splitlines() if "openalex:A9000000" in x and "# - [" in x)
    assert re.search(r"# - \[openalex:A9000000, openalex:A9000001\]  # Celso Amorim", linha)
    bloco = r.output[r.output.index("# Descomente") :]
    # colado como está, não muda nada; com a linha descomentada, funde os dois
    (projeto.raiz / "pessoas.yaml").write_text(bloco, encoding="utf-8")
    assert ler_correcoes(projeto.raiz) == CorrecoesPessoas()
    (projeto.raiz / "pessoas.yaml").write_text(bloco.replace("  # - [openalex:A9000000", "  - [openalex:A9000000"))
    assert ler_correcoes(projeto.raiz).fundir == [["openalex:A9000000", "openalex:A9000001"]]
    assert yaml.safe_load(bloco)["nao_fundir"] is None
    (projeto.raiz / "pessoas.yaml").unlink()


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
    # a força gravada é um inteiro (documentos com coautor), sem resíduo de arredondamento
    assert all(p["forca"] == int(p["forca"]) for p in ler_tabela(projeto.dados / "redes" / "pessoas.parquet"))
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
    # todos os documentos casaram com o OpenAlex: os sem referência resolvida têm 0, e nenhum tem -1
    assert 0 in citacoes.n_referencias and -1 not in citacoes.n_referencias
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
    # refazer a geografia com as mesmas entradas não derruba as redes (a assinatura ignora os carimbos de hora), nem
    # um comentário no pessoas.yaml
    from mapa_da_ciencia.geografia.pipeline import gerar_geografia

    gerar_geografia(projeto)
    (projeto.raiz / "pessoas.yaml").write_text("# nada ainda\nnomes: {}\n", encoding="utf-8")
    assert redes_em_dia(projeto) is True
    # uma correção de verdade deixa as redes desatualizadas: o aviso e o manifesto dizem o que mudou
    (projeto.raiz / "pessoas.yaml").write_text("nomes: {openalex:A9000000: Celso L. Amorim}\n", encoding="utf-8")
    assert redes_em_dia(projeto) is False and o_que_mudou(projeto) == ["o pessoas.yaml"]
    avisos = exportar(projeto)
    manifesto = m.Manifesto.model_validate_json((dados / "manifesto.json").read_text(encoding="utf-8"))
    assert manifesto.desatualizadas == ["redes"] and not (dados / "redes.json").exists()
    assert manifesto.mudancas == {"redes": ["o pessoas.yaml"]}
    # o site publicado fica sem a vista Redes, e o `mapa publicar` diz por quê
    from mapa_da_ciencia.publicar import publicar

    estatico = projeto.raiz.parent / "estatico"
    estatico.mkdir(exist_ok=True)
    (estatico / "index.html").write_text("<!doctype html><title>mapa</title>")
    r = publicar(projeto, projeto.raiz.parent / "site", estatico=estatico)
    assert any("ficaram fora do site" in a and "mudou o pessoas.yaml" in a for a in r.avisos)
    assert not (r.destino / "dados" / "redes.json").exists()
    assert any("mudou o pessoas.yaml" in a for a in avisos)
    from typer.testing import CliRunner

    from mapa_da_ciencia.cli import app

    status = CliRunner().invoke(app, ["status", "-P", str(projeto.raiz)], env={"COLUMNS": "200"}).output
    linha = next(x for x in status.splitlines() if x.strip(" │┃").startswith("redes"))
    assert "desatualizada" in linha and "mudou o pessoas.yaml" in linha
    assert "As redes estão desatualizadas (mudou o pessoas.yaml)" in status
    (projeto.raiz / "pessoas.yaml").unlink()
    assert redes_em_dia(projeto) is True
    exportar(projeto)
    agregados = json.loads((dados / "agregados.json").read_text(encoding="utf-8"))
    assert agregados["arestas_coautoria"] > 0 and agregados["canone_n"] == [citacoes.canone[0].n]
