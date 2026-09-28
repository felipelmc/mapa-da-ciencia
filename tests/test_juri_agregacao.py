"""A decisão do júri a partir dos votos: maioria estrita por tipo de variável, com a condição da evidência."""

from mapa_da_ciencia.config import Categoria, Variavel
from mapa_da_ciencia.juri.agregacao import Voto, agregar, candidatos, chave


def _cat(*valores: str) -> list[Categoria]:
    return [Categoria(valor=v, definicao=v) for v in valores]


CATEGORICA = Variavel(id="abordagem", rotulo="A", tipo="categorica", pergunta="?", categorias=_cat("a", "b", "c"))
MULTIPLA = Variavel(id="tecnicas", rotulo="T", tipo="multipla", pergunta="?", categorias=_cat("x", "y", "z"))
BOOLEANA = Variavel(id="brasil", rotulo="B", tipo="booleana", pergunta="?")
TEXTO = Variavel(id="periodo", rotulo="P", tipo="texto", pergunta="?")


def v(membro: str, valor, status: str = "literal", evidencia: str = "trecho") -> Voto:
    return Voto(membro, valor, evidencia, status)


def test_unanimidade_e_maioria_estrita():
    d = agregar(CATEGORICA, [v("m1", "a"), v("m2", "a"), v("m3", "a")])
    assert (d.etapa, d.valor) == ("unanime", "a")
    d = agregar(CATEGORICA, [v("m1", "b"), v("m2", "a"), v("m3", "a")])
    assert (d.etapa, d.valor) == ("maioria", "a")
    d = agregar(CATEGORICA, [v("m1", "a"), v("m2", "b"), v("m3", "c")])
    assert (d.etapa, d.valor) == ("sem_maioria", None)
    assert [c.valor for c in d.candidatos] == ["a", "b", "c"]


def test_juri_de_dois_so_decide_com_unanimidade():
    assert agregar(BOOLEANA, [v("m1", True), v("m2", False)]).etapa == "sem_maioria"
    assert agregar(BOOLEANA, [v("m1", True), v("m2", True)]).etapa == "unanime"


def test_maioria_sem_evidencia_no_texto_nao_decide():
    d = agregar(CATEGORICA, [v("m1", "b"), v("m2", "a", "ausente"), v("m3", "a", "ausente")])
    assert d.etapa == "sem_maioria"
    d = agregar(CATEGORICA, [v("m1", "b"), v("m2", "a", "ausente"), v("m3", "a", "aproximada")])
    assert (d.etapa, d.voto.membro) == ("maioria", "m3")


def test_unanimidade_sem_evidencia_decide_e_nao_vira_disputa():
    from mapa_da_ciencia.config import Codebook
    from mapa_da_ciencia.juri.deliberacao import em_disputa

    votos = [v(m, "a", "ausente", "trecho inventado") for m in ("m1", "m2", "m3")]
    d = agregar(CATEGORICA, votos)
    assert (d.etapa, d.valor, d.voto.status, len(d.candidatos)) == ("unanime", "a", "ausente", 1)
    codebook = Codebook(nome="t", versao="1", instrucoes="-", variaveis=[CATEGORICA])
    assert em_disputa(codebook, {"abordagem": votos}) == []  # nada a deliberar


def test_evidencia_da_decisao_e_a_de_melhor_status_e_o_empate_fica_com_a_ordem():
    d = agregar(CATEGORICA, [v("m1", "a", "aproximada"), v("m2", "a", "literal"), v("m3", "a", "literal")])
    assert d.voto.membro == "m2"
    d = agregar(CATEGORICA, [v("m1", "a", "dispensada", ""), v("m2", "a", "aproximada"), v("m3", "c")])
    assert d.voto.membro == "m2"


def test_multipla_categoria_a_categoria():
    d = agregar(MULTIPLA, [v("m1", ["x", "y"]), v("m2", ["y", "x"]), v("m3", ["x"])])
    assert (d.etapa, d.valor) == ("maioria", ["x", "y"])
    d = agregar(MULTIPLA, [v("m1", ["x"]), v("m2", ["y"]), v("m3", ["z"])])
    assert d.etapa == "sem_maioria"  # nenhuma categoria tem maioria, e ninguém votou no conjunto vazio
    d = agregar(MULTIPLA, [v("m1", []), v("m2", []), v("m3", ["z"])])
    assert (d.etapa, d.valor) == ("maioria", [])
    d = agregar(MULTIPLA, [v("m1", ["x"]), v("m2", ["x", "y"])])
    assert d.etapa == "sem_maioria"  # empate em `y` num júri de dois


def test_multipla_sem_ninguem_com_o_conjunto_vencedor():
    # x: 2 de 3, y: 2 de 3 → {x, y}, mas ninguém votou exatamente {x, y}
    d = agregar(MULTIPLA, [v("m1", ["x"]), v("m2", ["x", "y", "z"]), v("m3", ["y"])])
    assert d.etapa == "sem_maioria"


def test_texto_compara_a_forma_normalizada():
    d = agregar(TEXTO, [v("m1", "1994 - 2018"), v("m2", "1994–2018"), v("m3", "Não informado")])
    assert (d.etapa, d.valor) == ("maioria", "1994 - 2018")
    assert chave(TEXTO, "  Década de 1990 ") == chave(TEXTO, "década de 1990")


def test_candidatos_trazem_quem_votou_e_o_melhor_voto():
    votos = [v("m1", "a", "ausente"), v("m2", "b"), v("m3", "a", "literal")]
    cs = candidatos(CATEGORICA, votos)
    assert [(c.valor, c.membros, c.voto.membro) for c in cs] == [("a", ("m1", "m3"), "m3"), ("b", ("m2",), "m2")]


def test_sem_votos():
    assert agregar(CATEGORICA, []).etapa == "sem_maioria"


def test_chave_da_deliberacao_muda_com_o_prompt_da_classificacao(monkeypatch):
    from mapa_da_ciencia.classificacao.executor import Texto
    from mapa_da_ciencia.juri import deliberacao

    texto = Texto(doc="d1", titulo="T", resumo="R", idioma="pt")
    antes = deliberacao.chave_deliberacao("a", "m@1", (1, 0.0, 7, False), texto, "ctx")
    monkeypatch.setattr(deliberacao, "VERSAO_PROMPT", 999)
    assert deliberacao.chave_deliberacao("a", "m@1", (1, 0.0, 7, False), texto, "ctx") != antes
