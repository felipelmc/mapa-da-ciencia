"""Casamento das afiliações com as instituições do OpenAlex (geografia/casamento.py e instituicoes.py)."""

import pytest

from mapa_da_ciencia.armazenamento import ARQUIVO, ARQUIVO_INSTITUICOES, gravar_tabela, ler_documentos
from mapa_da_ciencia.coleta import coletar
from mapa_da_ciencia.config import ErroConfig
from mapa_da_ciencia.documento import (
    Afiliacao,
    AfiliacaoOpenAlex,
    Autor,
    AutoriaOpenAlex,
    Documento,
    InstituicaoOpenAlex,
)
from mapa_da_ciencia.fontes.openalex import COLUNAS_INSTITUICOES
from mapa_da_ciencia.geografia import instituicoes as inst
from mapa_da_ciencia.geografia.casamento import (
    Casador,
    Indice,
    alinhar,
    palavras,
    parece_afiliacao,
    parece_organizacao,
)
from mapa_da_ciencia.geografia.instituicoes import Registro
from mapa_da_ciencia.llm.perfis import PERFIS
from mapa_da_ciencia.projeto import Projeto

R = [
    Registro("I1", "Universidade de São Paulo", siglas=("USP",), nomes=("University of São Paulo",), pais="BR",
             tipo="education"),
    Registro("I2", "Universidade Federal do Paraná", siglas=("UFPR",), pais="BR", tipo="education"),
    Registro("I3", "Universidade Federal do Pará", siglas=("UFPA",), pais="BR", tipo="education"),
    Registro("I4", "Universidade Estadual de Campinas", siglas=("UNICAMP",), pais="BR", tipo="education"),
    Registro("I5", "Hospital de Clínicas da Unicamp", pais="BR", tipo="healthcare", linhagem=("I4",)),
    Registro("I6", "Universidade Cidade de São Paulo", pais="BR", tipo="education"),
    Registro("I7", "Fundação Getulio Vargas", siglas=("FGV",), pais="BR", tipo="education"),
    Registro("I8", "Escola de Administração de Empresas de São Paulo", siglas=("FGV EAESP",), pais="BR",
             tipo="education", linhagem=("I7",)),
    Registro("I9", "University of London", pais="GB", tipo="education"),
    Registro("I10", "King's College London", siglas=("KCL",), pais="GB", tipo="education", linhagem=("I9",)),
    Registro("I11", "Pontificia Universidad Católica de Chile", siglas=("PUC", "UC"), pais="CL", tipo="education"),
    Registro("I12", "Universidade do Estado do Rio de Janeiro", siglas=("UERJ",), pais="BR", tipo="education"),
    Registro("I13", "Universidade Federal do Rio de Janeiro", siglas=("UFRJ",), pais="BR", tipo="education"),
    Registro("I14", "Universidad San Pablo CEU", siglas=("USP",), pais="ES", tipo="education"),
    Registro("I15", "Universidade Federal do Rio Grande do Sul", siglas=("UFRGS",), pais="BR", tipo="education"),
    Registro("I16", "Universidade Federal do Rio Grande", siglas=("FURG",), pais="BR", tipo="education"),
    Registro("I17", "Laboratório Conjunto", pais="FR", tipo="facility", linhagem=("I18", "I19")),
    Registro("I18", "Université Paris 8", pais="FR", tipo="education"),
    Registro("I19", "Université Paris Nanterre", pais="FR", tipo="education"),
    Registro("I20", "Instituto Federal do Rio de Janeiro", siglas=("IFRJ",), pais="BR", tipo="education"),
    Registro("I21", "Universidade Nova de Lisboa", siglas=("NOVA",), pais="PT", tipo="education"),
]  # fmt: skip
REGISTROS = {r.id: r for r in R}


@pytest.fixture
def indice():
    return Indice(REGISTROS, {"IESP": "I12"})


# ---------------------------------------------------------------- palavras e semelhança
def test_palavras():
    assert palavras("University of São Paulo") == palavras("Universidade de São Paulo") == {"universidade", "lugarsp"}
    assert palavras("Universidade Federal do Rio Grande do Sul") == {"universidade", "federal", "lugarrs"}
    assert palavras("Universidade Federal do Rio Grande") == {"universidade", "federal", "rio", "grande"}
    assert palavras("Universidade de Brasília, Distrito Federal") == {"universidade", "brasilia", "lugardf"}
    assert palavras("Instituto Federal do Rio de Janeiro") == {"institutofederal", "lugarrj"}
    assert palavras("Texas A&M University") == {"texas", "am", "universidade"}
    assert palavras("King’s College London") == palavras("King's College London")
    assert palavras("PUC Minas") == {"puc", "lugarmg"}


def test_semelhanca(indice):
    s = indice.semelhanca
    assert s("Universidade de São Paulo", "I1") == 1.0
    assert s("Universidade Federal do Paraná", "I3") == 0.0  # Paraná × Pará: conflito
    assert s("Universidade do Estado do Rio de Janeiro", "I13") == 0.0  # estadual × federal
    assert s("Universidade Federal do Rio Grande do Sul", "I16") == 0.0  # o "sul" é do estado
    assert s("Instituto Federal do Rio de Janeiro", "I13") == 0.0
    assert s("Departamento de Ciência Política, Universidade de São Paulo, São Paulo, Brasil", "I1") == 1.0
    assert s("Instituto de Ciência Política da Universidade de São Paulo", "I1") == 1.0
    assert s("Faculdade de Filosofia (USP)", "I1") == s("FFLCH-USP", "I1") == 1.0  # sigla
    assert s("PUC Minas", "I11") < 1.0  # a sigla "PUC" é da PUC do Chile, mas "Minas" contradiz o nome
    assert s("Universidade Nova de Lisboa", "I21") == 1.0  # "Nova" é sigla e também palavra do nome
    assert s("NOVA University of Lisbon", "I21") > 0.9  # Lisbon ≈ Lisboa


def test_parece_organizacao():
    assert parece_organizacao("Universidade de Buenos Aires")
    assert parece_organizacao("Câmara dos Deputados")
    assert not parece_organizacao("O Brasil tem")
    assert not parece_organizacao("tradução de")


def test_parece_afiliacao():
    assert parece_afiliacao("Universidade Federal Fluminense")
    assert parece_afiliacao("universidade Federal Fluminense")  # curto: vale mesmo em minúscula
    assert not parece_afiliacao("Cambridge: Cambridge University Press, 1997")  # citação
    assert not parece_afiliacao("Cambridge: Cambridge University")
    assert not parece_afiliacao("versão anterior deste artigo foi apresentada na Universidade de São Paulo")


def test_so_o_lugar_em_comum_nao_casa():
    indice = Indice({**REGISTROS, "I30": Registro("I30", "SOAS University of London", pais="GB", cidade="London")})
    assert indice.semelhanca("Womankind Worldwide, London", "I30") == 0.0
    assert indice.semelhanca("SOAS University of London", "I30") == 1.0


def test_instituicao_do_openalex_precisa_do_texto(indice):
    lixo = AutoriaOpenAlex(
        nome="Clara Mafra",
        instituicoes=[InstituicaoOpenAlex(id="I10", nome="King's College London")],
        afiliacoes=[AfiliacaoOpenAlex(texto="Falwell, de Susan Harding", instituicoes=["I10"])],
    )
    assert Casador(indice).confiaveis(lixo) == {}
    boa = autoria("Ana Souza", "I10", textos=["King's College London, Reino Unido"])
    assert set(Casador(indice).confiaveis(boa)) == {"I10"}
    sem_texto = autoria("Ana Souza", "I10")
    assert set(Casador(indice).confiaveis(sem_texto)) == {"I10"}


def test_mae(indice):
    assert indice.mae("I5") == "I4"  # hospital → universidade
    assert indice.mae("I8") == "I7"  # EAESP → FGV
    assert indice.mae("I10") == "I10"  # King's College não sobe para a University of London
    assert indice.mae("I17") == "I17"  # laboratório de duas universidades: fica
    separada = Indice({**REGISTROS, "I8": Registro("I8", "Escola X", tipo="education", linhagem=("I7",),
                                                    separada=True)})  # fmt: skip
    assert separada.mae("I8") == "I8"


# ---------------------------------------------------------------- documentos
def autoria(nome, *ids, textos=()):
    return AutoriaOpenAlex(
        nome=nome,
        instituicoes=[InstituicaoOpenAlex(id=i, nome=REGISTROS[i].nome, pais=REGISTROS[i].pais) for i in ids],
        paises=sorted({REGISTROS[i].pais for i in ids}),
        afiliacoes=[AfiliacaoOpenAlex(texto=t, instituicoes=list(ids)) for t in textos],
    )


def doc(id_, autores, afiliacoes, autorias):
    return Documento(
        id=id_, fonte="articlemeta", origens=["teste"], revista_issn="0000-0000", ano=2020, tipo="research-article",
        autores=autores, afiliacoes=afiliacoes, autorias_openalex=autorias,
    )  # fmt: skip


def af(id_, texto, pais="BR", fonte="v240"):
    return Afiliacao(id=id_, instituicao=texto, pais=pais, fonte=fonte)


def test_alinhar():
    autores = [Autor(nome="Ana", sobrenome="Souza"), Autor(nome="Bruno", sobrenome="Lima")]
    assert alinhar(autores, [autoria("Ana Souza"), autoria("Bruno Lima")]) == {0: 0, 1: 1}
    assert alinhar(autores, [autoria("B. Lima"), autoria("Ana P. Souza")]) == {0: 1, 1: 0}
    assert alinhar(autores[:1], [autoria("Outro Nome")]) == {0: 0}  # autor único
    assert alinhar(autores, [autoria("Carla Dias")]) == {}


def test_documento_com_autoria_do_openalex(indice):
    d = doc(
        "d1",
        [Autor(nome="Ana", sobrenome="Souza", afiliacoes=["aff1"]), Autor(nome="Bruno", sobrenome="Lima")],
        [af("aff1", "Unicamp"), af("aff2", "Universidade de São Paulo")],
        [autoria("Ana Souza", "I5"), autoria("Bruno Lima", "I6")],
    )
    c = Casador(indice).casar([d])[0]
    assert c.n_autores == 2
    ana, orfa = c.vinculos
    assert (ana.autor, ana.casada, ana.instituicao, ana.nivel) == (0, "I5", "I4", "autoria")  # sobe ao HC → Unicamp
    # aff2 ninguém cita: vai para quem ficou sem afiliação (Bruno); o OpenAlex deu a ele a Cidade de São Paulo, mas
    # o texto casa bem melhor com a USP do índice
    assert orfa.autor is None and orfa.instituicao == "I1" and orfa.nivel == "indice"


def test_sem_afiliacao_na_articlemeta_usa_o_openalex_e_ignora_lixo(indice):
    d = doc(
        "d2",
        [Autor(nome="Ana", sobrenome="Souza"), Autor(nome="Bruno", sobrenome="Lima")],
        [],
        [autoria("Ana Souza", "I1"), AutoriaOpenAlex(nome="Bruno Lima", afiliacoes=[
            AfiliacaoOpenAlex(texto="O Brasil tem; Universidade Federal do Rio Grande do Sul")])],
    )  # fmt: skip
    c = Casador(indice).casar([d])[0]
    assert [(v.autor, v.fonte, v.instituicao, v.nivel) for v in c.vinculos] == [
        (0, "openalex", "I1", "openalex"),
        (1, "openalex", "I15", "indice"),  # "O Brasil tem" não é afiliação
    ]


def test_documento_so_do_openalex(indice):
    d = doc("d3", [], [], [autoria("Ana Souza", "I10"), AutoriaOpenAlex(nome="Sem Nada")])
    c = Casador(indice).casar([d])[0]
    assert c.n_autores == 2 and [(v.autor, v.instituicao) for v in c.vinculos] == [(0, "I10")]


def test_apelido_corpus_e_veto_por_pais(indice):
    def com(texto, *ids, pais="BR"):
        return doc(texto + str(ids), [Autor(nome="A", sobrenome="Souza", afiliacoes=["aff1"])],
                   [af("aff1", texto, pais=pais)], [autoria("A Souza", *ids)])  # fmt: skip

    docs = [
        com("IESP"),  # apelido do projeto
        com("Instituto X de Estudos", "I13"),  # o OpenAlex diz UFRJ, mas o texto não parece: fica sem
        com("Univ. Fed. Paraná", "I2"),
        com("Univ. Fed. Paraná", "I2"),
        com("Univ. Fed. Paraná"),  # sem candidato no documento: o corpus ensinou que é a UFPR
        com("USP", pais=None),  # a sigla é também da San Pablo CEU; o corpus é brasileiro
        com("Universidade de São Paulo", pais="ES"),  # o país da fonte veta a USP
    ]
    cs = Casador(indice).casar(docs)
    assert [(c.vinculos[0].instituicao, c.vinculos[0].nivel) for c in cs] == [
        ("I12", "apelido"),
        (None, "nenhum"),
        ("I2", "autoria"),
        ("I2", "autoria"),
        ("I2", "corpus"),
        ("I1", "indice"),
        (None, "nenhum"),
    ]


def test_estado_de_sao_paulo_nao_e_organizacao(indice):
    d = doc("d4", [Autor(nome="A", sobrenome="B", afiliacoes=["a"])], [af("a", "Estado de São Paulo")], [])
    assert Casador(indice).casar([d])[0].vinculos[0].instituicao is None


# ---------------------------------------------------------------- instituicoes.yaml
def test_correcoes_do_projeto(tmp_path):
    (tmp_path / "instituicoes.yaml").write_text(
        "apelidos:\n  Centro Brasileiro de Análise e Planejamento: cebrap\n  EAESP: I8\n"
        "instituicoes:\n  cebrap: {nome: Centro Brasileiro de Análise e Planejamento, sigla: CEBRAP, pais: Brasil,"
        " uf: São Paulo}\n  I8: {separada: true, uf: SP}\n",
        encoding="utf-8",
    )
    registros, apelidos = inst.combinar(REGISTROS, inst.ler_projeto(tmp_path))
    assert registros["cebrap"].pais == "BR" and registros["cebrap"].uf == "SP" and registros["cebrap"].separada
    assert registros["I8"].separada and registros["I8"].uf == "SP" and registros["I8"].nome == REGISTROS["I8"].nome
    assert apelidos["EAESP"] == "I8"
    indice = Indice(registros, apelidos)
    d = doc("d", [Autor(nome="A", sobrenome="B", afiliacoes=["a"])],
            [af("a", "Centro Brasileiro de Análise e Planejamento")], [])  # fmt: skip
    assert Casador(indice).casar([d])[0].vinculos[0].instituicao == "cebrap"


@pytest.mark.parametrize(
    ("yaml", "erro"),
    [
        ("apelidos: {X: I999}\n", "não é uma instituição conhecida"),
        ("instituicoes: {nova: {nome: Nova}}\n", "informe ao menos"),
        ("instituicoes: {nova: {nome: Nova, pais: Atlântida}}\n", "país desconhecido"),
        ("outra: 1\n", "inválido"),
    ],
)
def test_correcoes_invalidas(tmp_path, yaml, erro):
    (tmp_path / "instituicoes.yaml").write_text(yaml, encoding="utf-8")
    with pytest.raises(ErroConfig, match=erro):
        inst.combinar(REGISTROS, inst.ler_projeto(tmp_path))


def test_ler_openalex_e_completar(tmp_path):
    linha = {c: None for c in COLUNAS_INSTITUICOES} | {
        "id": "I1", "nome": "Universidade de São Paulo", "nome_pt": "Universidade de São Paulo", "siglas": ["USP"],
        "nomes": ["University of São Paulo"], "pais": "BR", "linhagem": [], "super_sistema": False,
    }  # fmt: skip
    gravar_tabela([linha], COLUNAS_INSTITUICOES, tmp_path / ARQUIVO_INSTITUICOES)
    registros = inst.ler_openalex(tmp_path)
    assert registros["I1"].siglas == ("USP",) and registros["I1"].nomes == ("University of São Paulo",
                                                                            "Universidade de São Paulo")  # fmt: skip
    assert inst.ler_openalex(tmp_path / "vazio") == {}
    d = doc("d", [], [], [autoria("A", "I10")])
    assert set(inst.completar(registros, [d])) == {"I1", "I10"}


# ---------------------------------------------------------------- com as fixtures reais
def test_casamento_na_opiniao_publica_2024(tmp_path, apis_falsas):
    projeto = Projeto.criar(
        tmp_path / "op", modelo="vazio", perfil=PERFIS["leve"], revistas=["0104-6276"], anos=(2024, 2024)
    )
    coletar(projeto)
    docs = ler_documentos(projeto.dados / ARQUIVO)
    registros = inst.completar(inst.ler_openalex(projeto.dados), docs)
    cs = Casador(Indice(registros)).casar(docs)
    com_texto = [v for c in cs for v in c.vinculos if v.fonte != "openalex" and v.texto]
    assert len(com_texto) >= 70
    # o índice das fixtures é pequeno (89 instituições): UFV e UFRJ, por exemplo, não estão nele
    assert sum(v.instituicao is not None for v in com_texto) / len(com_texto) >= 0.8
    # o OpenAlex deu "Funai Electric (Japan)" à Funai e um sítio arqueológico português à Câmara dos Deputados:
    # o veto pelo país descarta os dois
    por_texto = {v.texto: v for v in com_texto}
    assert por_texto["Funai"].instituicao is None and por_texto["Câmara dos Deputados"].instituicao is None


def test_id_de_instituicao_propria_no_padrao_da_interface(tmp_path):
    (tmp_path / "instituicoes.yaml").write_text(
        "instituicoes:\n  fundação-x: {nome: Fundação X, pais: BR}\n", encoding="utf-8"
    )
    with pytest.raises(ErroConfig, match="id de instituição inválido"):
        inst.ler_projeto(tmp_path)
