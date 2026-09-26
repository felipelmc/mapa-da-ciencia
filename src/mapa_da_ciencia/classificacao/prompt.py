"""As mensagens enviadas ao modelo na classificação.

A mensagem de sistema é a mesma para todos os documentos (instruções do codebook, regras da evidência e as
variáveis com as definições): o Ollama reaproveita o processamento desse prefixo de uma chamada para a outra, e só o
texto do documento, na mensagem do usuário, é processado de novo.

Mudou o texto das mensagens? Suba `VERSAO_PROMPT`: ela entra na chave do cache, e as classificações antigas deixam
de valer.
"""

from __future__ import annotations

import hashlib
import json

from ..config import Codebook
from .codebook import EVIDENCIA_MAXIMA

VERSAO_PROMPT = 1

REGRAS_EVIDENCIA = (
    "Regras da evidência:\n"
    "- Para cada variável, copie primeiro, como evidência, um trecho curto do título ou do resumo (até 20 "
    f"palavras, no máximo {EVIDENCIA_MAXIMA} caracteres), exatamente como está escrito: palavra por palavra, sem "
    "parafrasear, resumir nem traduzir.\n"
    "- Escolha o trecho que mais justifica o valor. Não junte pedaços de frases diferentes.\n"
    "- Quando o valor for `nao_informado`, `nao_se_aplica` ou falso, a evidência pode ficar vazia.\n"
    "- Responda apenas com o JSON pedido."
)


def mensagem_sistema(codebook: Codebook) -> str:
    """As instruções fixas: o codebook inteiro, na ordem das variáveis."""
    linhas = [codebook.instrucoes.strip(), "", REGRAS_EVIDENCIA, "", "## Variáveis", ""]
    for v in codebook.variaveis:
        linhas.append(f"### `{v.id}`: {v.rotulo} ({v.tipo})")
        linhas.append(v.pergunta.strip())
        if v.tipo == "multipla":
            linhas.append("Escolha todas as categorias que se aplicam.")
        for c in v.categorias:
            linhas.append(f"- `{c.valor}`: {c.definicao.strip()}")
            linhas += [f"  - exemplo: {e.strip()}" for e in c.exemplos]
        linhas.append("")
    return "\n".join(linhas).strip()


def assinatura(codebook: Codebook) -> str:
    """Hash do que o modelo lê: a mensagem de sistema e o esquema da resposta. É o que entra na chave do cache: os
    rótulos de exibição das categorias ficam de fora, e mudá-los não refaz a classificação."""
    from .codebook import esquema

    conteudo = json.dumps(
        {"sistema": mensagem_sistema(codebook), "esquema": esquema(codebook)}, sort_keys=True, ensure_ascii=False
    )
    return hashlib.sha256(conteudo.encode("utf-8")).hexdigest()[:16]


def mensagem_documento(titulo: str | None, resumo: str) -> str:
    """O texto a classificar: o título e o resumo, no idioma em que o painel os mostra."""
    return f"Título: {(titulo or '').strip()}\n\nResumo: {resumo.strip()}"


def mensagem_correcao(problemas: list[str], sem_evidencia: list[str]) -> str:
    """Segunda tentativa: aponta o que estava errado na primeira resposta."""
    partes = []
    if problemas:
        partes.append("A resposta anterior tem problemas: " + "; ".join(problemas) + ".")
    if sem_evidencia:
        nomes = ", ".join(f"`{v}`" for v in sem_evidencia)
        partes.append(
            f"As evidências de {nomes} não foram encontradas no título nem no resumo. Copie, para cada uma, um "
            "trecho que esteja no texto, palavra por palavra."
        )
    partes.append("Responda de novo, com o JSON completo.")
    return " ".join(partes)
