"""Contagem fracionária e lugar de cada vínculo (geografia/contagem.py)."""

from collections import defaultdict

import pytest

from mapa_da_ciencia.armazenamento import ARQUIVO, ler_documentos
from mapa_da_ciencia.coleta import coletar
from mapa_da_ciencia.contrato.modelos import NAO_IDENTIFICADA
from mapa_da_ciencia.geografia import instituicoes as inst
from mapa_da_ciencia.geografia.casamento import Casador, Casamento, Indice, Vinculo
from mapa_da_ciencia.geografia.contagem import cobertura, contar
from mapa_da_ciencia.geografia.instituicoes import Registro
from mapa_da_ciencia.llm.perfis import PERFIS
from mapa_da_ciencia.projeto import Projeto

REGISTROS = {
    r.id: r
    for r in [
        Registro("USP", "Universidade de São Paulo", pais="BR", regiao="São Paulo", cidade="São Paulo"),
        Registro("UFSCAR", "Universidade Federal de São Carlos", pais="BR", cidade="São Carlos"),
        Registro("UNB", "Universidade de Brasília", pais="BR", cidade="Brasília"),
        Registro("PROJ", "Instituto do Projeto", pais="BR", uf="RJ"),
        Registro("MIT", "Massachusetts Institute of Technology", pais="US", regiao="Massachusetts"),
    ]
}


def v(autor, instituicao=None, *, fonte="v240", pais=None, uf=None, cidade=None, texto="x"):
    return Vinculo(
        autor=autor, afiliacao=0, fonte=fonte, texto=texto, casada=instituicao, instituicao=instituicao,
        nivel="autoria" if instituicao else "nenhum", pais_fonte=pais, uf_fonte=uf, cidade_fonte=cidade,
    )  # fmt: skip


def pesos(casamentos):
    return {(p.doc, p.instituicao): round(p.peso, 6) for p in contar(casamentos, Indice(REGISTROS))}


def test_pesos_pela_regra_do_glossario():
    c = Casamento("d", 2, [v(0, "USP"), v(0, "UNB"), v(1, "MIT")])
    assert pesos([c]) == {("d", "USP"): 0.25, ("d", "UNB"): 0.25, ("d", "MIT"): 0.5}


def test_autor_sem_afiliacao_fica_com_as_orfas_ou_sem_afiliacao():
    com_orfa = Casamento("a", 2, [v(0, "USP"), v(None, "UNB")])
    assert pesos([com_orfa]) == {("a", "USP"): 0.5, ("a", "UNB"): 0.5}
    sem_orfa = Casamento("b", 3, [v(0, "USP")])
    assert pesos([sem_orfa]) == {("b", "USP"): round(1 / 3, 6), ("b", None): round(2 / 3, 6)}


def test_orfas_que_sobram_entram_para_todos_os_autores():
    c = Casamento("d", 2, [v(0, "USP"), v(1, "UNB"), v(None, "MIT")])
    assert pesos([c]) == {("d", "USP"): 0.25, ("d", "UNB"): 0.25, ("d", "MIT"): 0.5}


def test_documento_sem_autores():
    assert pesos([Casamento("d", 0, [v(None, "USP"), v(None, None, pais="AR")])]) == {
        ("d", "USP"): 0.5,
        ("d", NAO_IDENTIFICADA): 0.5,
    }
    assert pesos([Casamento("e", 0, [])]) == {("e", None): 1.0}


def test_pais_e_uf_de_cada_vinculo():
    indice = Indice(REGISTROS)
    corpus = [
        # a v240 ensina que São Carlos é SP e que a UFSCar é de SP
        Casamento("v1", 1, [v(0, "UFSCAR", pais="BR", uf="SP", cidade="São Carlos")]),
        Casamento("v2", 1, [v(0, "UFSCAR", pais="BR", uf="SP", cidade="São Carlos")]),
        Casamento("a", 1, [v(0, None, fonte="v70", pais="BR", uf="MG")]),  # 1. UF da fonte
        Casamento("b", 1, [v(0, None, fonte="v70", pais="BR", cidade="Juiz de Fora")]),  # 2. município único
        Casamento("c", 1, [v(0, None, fonte="v70", pais="BR", cidade="São Carlos")]),  # 2. cidade aprendida
        Casamento("d", 1, [v(0, "PROJ", fonte="v70")]),  # 3. UF do projeto; o país vem do registro
        Casamento("e", 1, [v(0, "UFSCAR", fonte="openalex")]),  # 4. UF da instituição no corpus
        Casamento("f", 1, [v(0, "USP", fonte="openalex")]),  # 5. região do OpenAlex
        Casamento("g", 1, [v(0, "UNB", fonte="openalex")]),  # 6. cidade do OpenAlex
        Casamento("h", 1, [v(0, "MIT", fonte="openalex", uf="SP")]),  # fora do Brasil, sem UF
        Casamento("i", 1, [v(0, None, fonte="v70", pais="AR")]),
    ]
    lugar = {p.doc: (p.uf, p.pais) for p in contar(corpus, indice)}
    assert lugar == {
        "v1": ("SP", "BR"), "v2": ("SP", "BR"), "a": ("MG", "BR"), "b": ("MG", "BR"), "c": ("SP", "BR"),
        "d": ("RJ", "BR"), "e": ("SP", "BR"), "f": ("SP", "BR"), "g": ("DF", "BR"), "h": (None, "US"),
        "i": (None, "AR"),
    }  # fmt: skip


def test_invariantes_na_opiniao_publica_2024(tmp_path, apis_falsas):
    projeto = Projeto.criar(
        tmp_path / "op", modelo="vazio", perfil=PERFIS["leve"], revistas=["0104-6276"], anos=(2024, 2024)
    )
    coletar(projeto)
    docs = ler_documentos(projeto.dados / ARQUIVO)
    indice = Indice(inst.completar(inst.ler_openalex(projeto.dados), docs))
    parcelas = contar(Casador(indice).casar(docs), indice)
    por_doc: dict[str, float] = defaultdict(float)
    for p in parcelas:
        por_doc[p.doc] += p.peso
    assert set(por_doc) == {d.id for d in docs}
    assert all(s == pytest.approx(1) for s in por_doc.values())
    assert sum(p.peso for p in parcelas) == pytest.approx(len(docs))
    # a fracionária nunca passa da inteira (documentos com alguma afiliação na chave)
    for chave in ("instituicao", "uf", "pais"):
        frac: dict[str, float] = defaultdict(float)
        inteira: dict[str, set[str]] = defaultdict(set)
        for p in parcelas:
            if (k := getattr(p, chave)) is not None:
                frac[k] += p.peso
                inteira[k].add(p.doc)
        assert all(frac[k] <= len(inteira[k]) + 1e-9 for k in frac)
    c = cobertura(parcelas)
    assert c.documentos == len(docs) and c.pais_conhecido > 0.9 and c.uf_conhecida > 0.9


def test_uf_da_unidade_que_casou_antes_da_mae():
    registros = {
        "FGV": Registro("FGV", "Fundação Getulio Vargas", pais="BR", regiao="Rio de Janeiro", tipo="education"),
        "EAESP": Registro("EAESP", "Escola de Administração de Empresas de São Paulo", pais="BR",
                          regiao="São Paulo", tipo="education", linhagem=("FGV",)),
    }  # fmt: skip
    v = Vinculo(autor=0, afiliacao=None, fonte="openalex", texto="EAESP", casada="EAESP", instituicao="FGV",
                nivel="openalex")  # fmt: skip
    (p,) = contar([Casamento("d", 1, [v])], Indice(registros))
    assert (p.instituicao, p.uf) == ("FGV", "SP")
