"""Codebook → esquema da resposta, validação e mensagens do prompt (classificacao/codebook.py e prompt.py)."""

from importlib import resources
from pathlib import Path

import pytest

from mapa_da_ciencia.classificacao.codebook import EVIDENCIA_MAXIMA, esquema, sem_informacao, validar
from mapa_da_ciencia.classificacao.prompt import mensagem_correcao, mensagem_documento, mensagem_sistema
from mapa_da_ciencia.config import Codebook, carregar_codebook


@pytest.fixture
def exemplo() -> Codebook:
    caminho = resources.files("mapa_da_ciencia.modelos_projeto").joinpath("codebook-exemplo.yaml")
    return carregar_codebook(Path(str(caminho)))


@pytest.fixture
def com_multipla() -> Codebook:
    return Codebook.model_validate(
        {
            "nome": "teste",
            "versao": "1",
            "instrucoes": "Classifique.",
            "variaveis": [
                {"id": "metodos", "rotulo": "Métodos", "tipo": "multipla", "pergunta": "Quais métodos?",
                 "categorias": [{"valor": "survey", "definicao": "Questionário."},
                                {"valor": "entrevista", "definicao": "Entrevistas.", "exemplos": ["entrevistamos 20"]},
                                {"valor": "nao_informado", "definicao": "Não diz."}]},
                {"id": "periodo", "rotulo": "Período", "tipo": "texto", "pergunta": "Qual período?"},
            ],
        }
    )  # fmt: skip


def resposta_valida(cb: Codebook) -> dict:
    valores = {"categorica": lambda v: v.categorias[0].valor, "booleana": lambda v: True,
               "texto": lambda v: "1994–2018", "multipla": lambda v: [v.categorias[0].valor]}  # fmt: skip
    return {v.id: {"evidencia": "um trecho", "valor": valores[v.tipo](v)} for v in cb.variaveis}


def test_esquema_do_codebook_de_exemplo(exemplo):
    e = esquema(exemplo)
    assert e["required"] == [v.id for v in exemplo.variaveis] and e["additionalProperties"] is False
    abordagem = e["properties"]["abordagem"]
    assert list(abordagem["properties"]) == ["evidencia", "valor"]  # a evidência vem antes
    assert abordagem["properties"]["evidencia"]["maxLength"] == EVIDENCIA_MAXIMA
    assert "nao_informado" in abordagem["properties"]["valor"]["enum"]
    assert e["properties"]["brasil_como_caso"]["properties"]["valor"] == {"type": "boolean"}
    assert e["properties"]["periodo_analisado"]["properties"]["valor"] == {"type": "string"}


def test_esquema_multipla(com_multipla):
    valor = esquema(com_multipla)["properties"]["metodos"]["properties"]["valor"]
    assert valor["type"] == "array" and valor["uniqueItems"] and valor["items"]["enum"][0] == "survey"


def test_validar(exemplo, com_multipla):
    ok = validar(resposta_valida(exemplo), exemplo)
    assert ok.valida and ok.valores["brasil_como_caso"] is True and ok.evidencias["abordagem"] == "um trecho"

    r = resposta_valida(exemplo)
    r["abordagem"]["valor"] = "etnografica"
    del r["subarea"]
    r["extra"] = {}
    erros = validar(r, exemplo).problemas
    assert any("abordagem" in p for p in erros) and any("subarea" in p for p in erros)
    assert any("extra" in p for p in erros)
    assert validar("não é JSON", exemplo).problemas

    r = resposta_valida(com_multipla)
    r["metodos"]["valor"] = ["survey", "survey", "entrevista"]
    r["periodo"]["valor"] = "  1994 –   2018 "
    v = validar(r, com_multipla)
    assert v.valores == {"metodos": ["survey", "entrevista"], "periodo": "1994 – 2018"}
    r["metodos"]["valor"] = "survey"
    assert not validar(r, com_multipla).valida
    # valores do tipo errado viram problema, não exceção (uma lista não entra num conjunto)
    for errado in ({"a": 1}, [["survey"]], [{"a": 1}]):
        r["metodos"]["valor"] = errado
        assert not validar(r, com_multipla).valida
    r = resposta_valida(exemplo)
    r["abordagem"]["valor"] = ["quantitativa"]
    assert any("abordagem" in p for p in validar(r, exemplo).problemas)


def test_sem_informacao(exemplo, com_multipla):
    var = {v.id: v for v in [*exemplo.variaveis, *com_multipla.variaveis]}
    assert sem_informacao(var["abordagem"], "nao_informado") and not sem_informacao(var["abordagem"], "mista")
    assert sem_informacao(var["brasil_como_caso"], False) and not sem_informacao(var["brasil_como_caso"], True)
    assert sem_informacao(var["periodo"], "Não se aplica.") and not sem_informacao(var["periodo"], "1994–2018")
    assert sem_informacao(var["metodos"], []) and sem_informacao(var["metodos"], ["nao_informado"])
    assert not sem_informacao(var["metodos"], ["survey", "nao_informado"])


def test_mensagens(exemplo, com_multipla):
    sistema = mensagem_sistema(exemplo)
    assert sistema == mensagem_sistema(exemplo)  # o mesmo prefixo em todas as chamadas
    assert sistema.startswith(exemplo.instrucoes.strip()[:40]) and "Regras da evidência" in sistema
    for v in exemplo.variaveis:
        assert f"`{v.id}`" in sistema
        assert all(c.definicao.strip() in sistema for c in v.categorias)
    assert "exemplo: entrevistamos 20" in mensagem_sistema(com_multipla)
    assert "todas as categorias que se aplicam" in mensagem_sistema(com_multipla)
    assert mensagem_documento(" Título ", "Resumo.") == "Título: Título\n\nResumo: Resumo."
    correcao = mensagem_correcao(["`x`: faltou a variável"], ["abordagem"])
    assert "`x`: faltou" in correcao and "`abordagem`" in correcao and "JSON completo" in correcao
