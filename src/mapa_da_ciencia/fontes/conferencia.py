"""Conferência dos resumos que as fontes entregam: fragmentos e idioma declarado.

Dois problemas que o piloto mostrou e que a coleta corrige antes de fundir as duplicatas:

- **Fragmentos.** Parte dos "resumos" não é resumo: um pedaço do meio do texto que o OpenAlex raspou da página
  ("2] Ibid", "na revista Encontros com a…"), o aviso de um repositório ("Made available in DSpace…"), a palavra
  "Resumo" sozinha. Um texto com menos de `PALAVRAS_MINIMAS` palavras, um texto de repositório ou um resumo do OpenAlex
  que começa no meio de uma frase (sem maiúscula nem aspas) sai; o documento fica com os resumos que sobrarem, ou só
  com o título.
- **Idioma declarado.** Quando o detector (`mapa_da_ciencia.idioma`) reconhece com folga um idioma diferente do
  declarado, o resumo passa ao idioma detectado. O título e as palavras-chave da mesma fonte, no mesmo idioma
  declarado, seguem o resumo, a não ser que o próprio título confirme o idioma declarado (na RBPI de 2012, só os
  resumos estão trocados). Depois da troca, fica um texto por idioma, de preferência o que já estava certo.

Os resumos do OpenAlex com frases coladas ("salário.Trad.Iraci") ficam: são o texto do próprio artigo, melhor que
o título sozinho.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from mapa_da_ciencia.documento import Documento, Texto
from mapa_da_ciencia.idioma import acertos, detectar

PALAVRAS_MINIMAS = 15
_PALAVRA = re.compile(r"[^\W\d_]+")
_REPOSITORIO = re.compile(
    r"Made available in DSpace|No\. of bitstreams|DOAJ is a unique|est disponible dans le document"
    r"|^(?:keywords?|palavras-chave|palabras clave)\b",
    re.IGNORECASE,
)
_ABERTURA = "\"'“‘«"


@dataclass
class RelatorioConferencia:
    fragmentos: list[tuple[str, str]] = field(default_factory=list)  # (documento, início do texto)
    idiomas: list[tuple[str, str | None, str]] = field(default_factory=list)  # (documento, declarado, detectado)


def fragmento(resumo: Texto) -> bool:
    """Se o texto não é um resumo, mas um pedaço de outro texto ou um aviso de repositório."""
    texto = resumo.texto.strip()
    if len(_PALAVRA.findall(texto)) < PALAVRAS_MINIMAS or _REPOSITORIO.search(texto):
        return True
    return resumo.origem == "openalex" and not (texto[:1].isupper() or texto[:1] in _ABERTURA)


def _um_por_idioma(textos: list[Texto], certos: set[int]) -> list[Texto]:
    """Um texto por idioma, preferindo os que já estavam certos (pela posição em `textos`), na ordem original."""
    escolhido: dict[str | None, int] = {}
    for k, t in enumerate(textos):
        if t.idioma not in escolhido or (k in certos and escolhido[t.idioma] not in certos):
            escolhido[t.idioma] = k
    return [t for k, t in enumerate(textos) if escolhido[t.idioma] == k]


def _conferir(doc: Documento, relatorio: RelatorioConferencia) -> Documento:
    resumos = []
    for r in doc.resumos:
        if fragmento(r):
            relatorio.fragmentos.append((doc.id, r.texto[:60]))
        else:
            resumos.append(r)

    trocas: dict[tuple[str, str | None], str] = {}  # (origem, declarado) → detectado
    certos: set[int] = set()
    for k, r in enumerate(resumos):
        detectado = detectar(r.texto)
        if detectado is None or detectado == r.idioma:
            certos.add(k)
            continue
        trocas[(r.origem, r.idioma)] = detectado
        relatorio.idiomas.append((doc.id, r.idioma, detectado))
        resumos[k] = r.model_copy(update={"idioma": detectado})
    mudancas: dict = {}
    if trocas:
        mudancas["resumos"] = _um_por_idioma(resumos, certos)
        titulos, certos_t, seguem = list(doc.titulos), set(), set()
        for k, t in enumerate(titulos):
            novo = trocas.get((t.origem, t.idioma))
            contagem = acertos(t.texto)
            if novo is None or contagem[t.idioma or ""] > contagem[novo]:
                certos_t.add(k)
                continue
            seguem.add((t.origem, t.idioma))
            titulos[k] = t.model_copy(update={"idioma": novo})
        mudancas["titulos"] = _um_por_idioma(titulos, certos_t)
        # as palavras-chave seguem o título da mesma fonte e idioma; sem título nesse idioma, seguem o resumo
        com_titulo = {(t.origem, t.idioma) for t in doc.titulos}
        mudam = {chave for chave in trocas if chave in seguem or chave not in com_titulo}
        mudancas["palavras_chave"] = [
            p.model_copy(update={"idioma": trocas[(p.origem, p.idioma)]}) if (p.origem, p.idioma) in mudam else p
            for p in doc.palavras_chave
        ]
    elif len(resumos) != len(doc.resumos):
        mudancas["resumos"] = resumos
    return doc.model_copy(update=mudancas) if mudancas else doc


def conferir_textos(documentos: list[Documento]) -> tuple[list[Documento], RelatorioConferencia]:
    """Tira os resumos que são fragmentos e corrige o idioma declarado dos que o detector reconhece com folga."""
    relatorio = RelatorioConferencia()
    return [_conferir(d, relatorio) for d in documentos], relatorio
