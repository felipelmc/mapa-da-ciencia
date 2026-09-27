"""O codebook como contrato da resposta do modelo: o JSON Schema que o Ollama impõe e a validação do que volta.

Para cada variável o modelo devolve `{"evidencia": …, "valor": …}`, com a evidência **antes** do valor: o modelo
primeiro copia o trecho do texto e só então decide, o que ancora a resposta no resumo (ADR 0005). O tipo do valor
segue o tipo da variável:

| Tipo | Valor |
|---|---|
| `categorica` | uma das categorias (`enum`) |
| `multipla` | uma lista de categorias, sem repetição |
| `booleana` | `true` ou `false` |
| `texto` | texto livre curto |

A evidência tem no máximo `EVIDENCIA_MAXIMA` caracteres: cabe numa frase, e o modelo não gasta tempo copiando
parágrafos (a geração da evidência é o que mais custa, ADR 0005). Ela pode ficar vazia quando a resposta é "sem
informação" (`sem_informacao`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..config import Codebook, Variavel

EVIDENCIA_MAXIMA = 200
# respostas que dispensam evidência: não há trecho a citar quando o resumo não diz nada sobre a variável
SEM_INFORMACAO_CATEGORIAS = frozenset({"nao_informado", "nao_se_aplica"})
SEM_INFORMACAO_TEXTOS = frozenset({"", "nao se aplica", "não se aplica", "nao informado", "não informado"})


def _esquema_valor(v: Variavel) -> dict[str, Any]:
    if v.tipo == "categorica":
        return {"type": "string", "enum": [c.valor for c in v.categorias]}
    if v.tipo == "multipla":
        return {
            "type": "array",
            "items": {"type": "string", "enum": [c.valor for c in v.categorias]},
            "uniqueItems": True,
        }
    if v.tipo == "booleana":
        return {"type": "boolean"}
    return {"type": "string"}


def esquema(codebook: Codebook) -> dict[str, Any]:
    """JSON Schema da resposta: um objeto por variável, com a evidência antes do valor."""
    propriedades = {
        v.id: {
            "type": "object",
            "properties": {
                "evidencia": {"type": "string", "maxLength": EVIDENCIA_MAXIMA},
                "valor": _esquema_valor(v),
            },
            "required": ["evidencia", "valor"],
            "additionalProperties": False,
        }
        for v in codebook.variaveis
    }
    return {
        "type": "object",
        "properties": propriedades,
        "required": list(propriedades),
        "additionalProperties": False,
    }


def sem_informacao(v: Variavel, valor: Any) -> bool:
    """A resposta diz que o texto não informa a variável (e aí a evidência pode ficar vazia)."""
    if v.tipo == "booleana":
        return valor is False
    if v.tipo == "categorica":
        return valor in SEM_INFORMACAO_CATEGORIAS
    if v.tipo == "multipla":
        return not valor or set(valor) <= SEM_INFORMACAO_CATEGORIAS
    return str(valor).strip().lower().rstrip(".") in SEM_INFORMACAO_TEXTOS


@dataclass
class Resposta:
    """Uma resposta validada: valor e evidência por variável, e o que estava errado (vazio se nada)."""

    valores: dict[str, Any] = field(default_factory=dict)
    evidencias: dict[str, str] = field(default_factory=dict)
    problemas: list[str] = field(default_factory=list)

    @property
    def valida(self) -> bool:
        return not self.problemas


def conferir_valor(v: Variavel, valor: Any) -> tuple[Any, str | None]:
    """O valor normalizado (listas sem repetição, textos sem espaços sobrando) e o problema dele, se houver."""
    categorias = {c.valor for c in v.categorias}
    if v.tipo == "categorica" and (not isinstance(valor, str) or valor not in categorias):
        return valor, f"{valor!r} não é uma das categorias"
    if v.tipo == "multipla":
        if not isinstance(valor, list) or not all(isinstance(x, str) and x in categorias for x in valor):
            return valor, "o valor precisa ser uma lista de categorias"
        return list(dict.fromkeys(valor)), None
    if v.tipo == "booleana" and not isinstance(valor, bool):
        return valor, "o valor precisa ser verdadeiro ou falso"
    if v.tipo == "texto":
        if not isinstance(valor, str):
            return valor, "o valor precisa ser um texto"
        return " ".join(valor.split()), None
    return valor, None


def validar(resposta: Any, codebook: Codebook) -> Resposta:
    """Confere a resposta do modelo contra o codebook e a normaliza (ver `conferir_valor`). Os problemas vão em
    `problemas`, uma frase por variável, para a mensagem de nova tentativa."""
    saida = Resposta()
    if not isinstance(resposta, dict):
        saida.problemas.append("a resposta não é um objeto JSON")
        return saida
    for v in codebook.variaveis:
        item = resposta.get(v.id)
        if not isinstance(item, dict) or "valor" not in item:
            saida.problemas.append(f"`{v.id}`: faltou a variável")
            continue
        evidencia = item.get("evidencia")
        if not isinstance(evidencia, str):
            saida.problemas.append(f"`{v.id}`: a evidência precisa ser um texto")
            continue
        valor, problema = conferir_valor(v, item["valor"])
        if problema:
            saida.problemas.append(f"`{v.id}`: {problema}")
            continue
        saida.valores[v.id] = valor
        saida.evidencias[v.id] = " ".join(evidencia.split())
    extras = set(resposta) - {v.id for v in codebook.variaveis}
    if extras:
        saida.problemas.append(f"variáveis que não estão no codebook: {', '.join(sorted(extras))}")
    return saida
