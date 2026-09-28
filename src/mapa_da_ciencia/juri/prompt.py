"""As mensagens do júri: a deliberação entre os membros e os pedidos ao supervisor.

Na deliberação, a conversa de cada membro começa igual à da classificação (a mesma mensagem de sistema, com o
codebook inteiro, e o mesmo texto do documento): o Ollama reaproveita o prefixo. Depois vêm a resposta do próprio
membro na primeira rodada, só nas variáveis em disputa, e uma mensagem com as respostas dos outros membros, sem os
nomes ("Modelo A", "Modelo B", na ordem dos valores), cada uma com a evidência e a marca de quando o trecho não está
no texto. O membro pode manter ou mudar a resposta, e precisa copiar a evidência de novo.

O supervisor recebe, para cada pedido, a definição da variável, o título, o resumo e os candidatos numerados, sem
dizer que modelo deu cada um. O texto das instruções é o mesmo no protocolo por arquivos e na API.

Mudou o texto? Suba `VERSAO_PROMPT_JURI`: ela entra na chave do cache da deliberação.
"""

from __future__ import annotations

import json
from typing import Any

from ..classificacao.codebook import EVIDENCIA_MAXIMA
from ..config import Codebook, Variavel
from .agregacao import Voto

VERSAO_PROMPT_JURI = 1


def formatar_valor(variavel: Variavel, valor: Any) -> str:
    if variavel.tipo == "booleana":
        return "sim (true)" if valor else "não (false)"
    if variavel.tipo == "multipla":
        return "[" + ", ".join(f"`{c}`" for c in valor) + "]" if valor else "[] (nenhuma)"
    return f"`{valor}`" if variavel.tipo == "categorica" else f'"{valor}"'


def _evidencia(voto: Voto) -> str:
    if not voto.evidencia:
        return "sem evidência"
    marca = " — trecho não encontrado no texto" if voto.status == "ausente" else ""
    return f'evidência: "{voto.evidencia}"{marca}'


def resposta_propria(disputadas: list[tuple[Variavel, Voto, list[Voto]]]) -> str:
    """A resposta do membro na primeira rodada, só nas variáveis em disputa, como o JSON que ele deu."""
    return json.dumps(
        {v.id: {"evidencia": proprio.evidencia, "valor": proprio.valor} for v, proprio, _ in disputadas},
        ensure_ascii=False,
    )


def mensagem_deliberacao(disputadas: list[tuple[Variavel, Voto, list[Voto]]]) -> str:
    """Para cada variável em disputa: a resposta do membro e as dos pares, anônimas."""
    linhas = [
        "Outros modelos leram o mesmo título e o mesmo resumo e responderam diferente nas variáveis abaixo. "
        "Releia o texto e reveja as suas respostas.",
        "",
    ]
    for v, proprio, pares in disputadas:
        linhas.append(f"### `{v.id}`: {v.rotulo}")
        linhas.append(f"- Sua resposta: {formatar_valor(v, proprio.valor)} ({_evidencia(proprio)})")
        for letra, par in zip("ABCDEFGH", pares, strict=False):
            linhas.append(f"- Modelo {letra}: {formatar_valor(v, par.valor)} ({_evidencia(par)})")
        linhas.append("")
    linhas += [
        "Regras:",
        "- Mantenha a sua resposta se o texto a sustenta. Mude só se a evidência de outro modelo mostrar que a "
        "definição de outra categoria se cumpre melhor.",
        "- Não mude só para concordar com os outros.",
        f"- Copie de novo a evidência, palavra por palavra, do título ou do resumo (até {EVIDENCIA_MAXIMA} "
        "caracteres).",
        "- Responda apenas com o JSON destas variáveis.",
    ]
    return "\n".join(linhas)


# ---------------------------------------------------------------- supervisor
INSTRUCOES_SUPERVISOR = f"""# Instruções ao supervisor do júri

Você supervisiona um júri de modelos de linguagem que classificou títulos e resumos de artigos científicos segundo
um codebook. Cada pedido traz o título, o resumo e a definição de uma variável. Há dois tipos de pedido.

## Arbitragem (`"tarefa": "arbitragem"`)

Os modelos não chegaram a uma maioria nesta variável. Leia o título e o resumo e escolha, **entre os candidatos**, o
que melhor atende à definição da variável. Você só pode escolher um dos candidatos, pelo número (`escolha`). Se
nenhum for adequado, escolha o menos inadequado e marque `"nenhum_adequado": true`.

## Auditoria (`"tarefa": "auditoria"`)

Os modelos concordaram por unanimidade. Diga se a decisão está correta segundo a definição (`"correto"`). Se não
estiver, diga em `"valor_sugerido"` qual categoria (ou valor) seria a correta; se estiver, deixe `null`.

## Em todos os pedidos

- Julgue só pelo título e pelo resumo, com as definições do codebook; não use conhecimento externo sobre o artigo.
- Copie como `"evidencia"` um trecho curto do título ou do resumo (até {EVIDENCIA_MAXIMA} caracteres), palavra por
  palavra, sem parafrasear nem traduzir, que sustente a sua resposta. Ela só pode ficar vazia se a resposta for
  "não informado", "não se aplica" ou falso.
- Justifique em uma ou duas frases (`"justificativa"`, até 300 caracteres).

## Formato das respostas

Um JSON por linha, com o mesmo `"id"` do pedido, num arquivo com o nome do lote terminado em `.respostas.jsonl`
(o lote `arbitragem-01.jsonl` volta como `arbitragem-01.respostas.jsonl`):

    {{"id": "…", "escolha": 2, "evidencia": "…", "justificativa": "…", "nenhum_adequado": false}}
    {{"id": "…", "correto": false, "valor_sugerido": "quantitativa", "evidencia": "…", "justificativa": "…"}}
"""


def descrever_variavel(codebook: Codebook, variavel: Variavel) -> dict[str, Any]:
    """A variável como o supervisor a lê: a pergunta, as categorias com as definições e as instruções gerais."""
    return {
        "id": variavel.id,
        "rotulo": variavel.rotulo,
        "tipo": variavel.tipo,
        "pergunta": variavel.pergunta.strip(),
        "categorias": [{"valor": c.valor, "definicao": c.definicao.strip()} for c in variavel.categorias],
        "instrucoes_do_codebook": codebook.instrucoes.strip(),
    }
