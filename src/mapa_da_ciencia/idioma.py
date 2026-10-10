"""O idioma de um texto, pelas palavras funcionais: confere o idioma que as fontes declaram.

As fontes erram o idioma de alguns resumos: no piloto, resumos em francês marcados como espanhol, em espanhol
marcados como português e pares português/inglês trocados. Um detector pequeno e determinístico basta para
conferir: artigos, preposições, conjunções e verbos auxiliares são quase metade das palavras de um resumo, e cada
lista abaixo só tem palavras que não existem (ou são raras) nos outros três idiomas. "que", "de", "a", "se",
"para", "por", "como", "entre", "mais", "ou", "le", "les", "la", "son", "en", "está", "mediante" e "on" ficam de
fora: são de mais de um.

O detector só decide quando o texto tem palavras bastantes e um idioma ganha com folga; senão devolve `None`, e
quem chamou fica com o idioma declarado.
"""

from __future__ import annotations

import re
from collections import Counter


def _palavras(texto: str) -> frozenset[str]:
    return frozenset(texto.split())


PALAVRAS: dict[str, frozenset[str]] = {
    "pt": _palavras(
        "e os do dos das da ao aos à às um uns umas não são também pelo pela pelos pelas isso isto esse essa "
        "esses essas nesse nessa neste nesta deste desta desse dessa num numa foi foram seu sua seus suas já "
        "então através há têm é quando onde com sem pode podem muito ainda nas na bem qual quais estão"
    ),
    "es": _palavras(
        "el los las del y una al lo con es su sus también más pero fue sin hay cuando donde muy ya otro otros "
        "otra otras esto eso ese esa estos tiene tienen puede pueden cual cuales ni dicho dicha sino están cómo "
        "sólo solo"
    ),
    "en": _palavras(
        "the of and to in is are was were this that with for by from which it its be been an at these those "
        "their has have not or but we our how between also more than such can into about while among through "
        "both other who what when where whether"
    ),
    "fr": _palavras(
        "des du et est une dans pour par sur au aux ce cette ces qui pas plus ne sont été être leur leurs avec "
        "nous il elle sa ses comme l d qu c n aussi où dont très"
    ),
}
MINIMO_PALAVRAS = 15  # palavras no texto para tentar decidir
MINIMO_ACERTOS = 5  # palavras funcionais do idioma vencedor
FOLGA = 2.0  # o vencedor precisa de ao menos o dobro de acertos do segundo

_PALAVRA = re.compile(r"[^\W\d_]+")


def acertos(texto: str) -> Counter[str]:
    """Quantas palavras funcionais de cada idioma o texto tem."""
    contagem: Counter[str] = Counter()
    for palavra in _PALAVRA.findall(texto.casefold()):
        for idioma, lista in PALAVRAS.items():
            if palavra in lista:
                contagem[idioma] += 1
    return contagem


def detectar(texto: str) -> str | None:
    """O idioma do texto (`pt`, `es`, `en` ou `fr`), ou `None` se o texto for curto ou ambíguo."""
    if len(_PALAVRA.findall(texto)) < MINIMO_PALAVRAS:
        return None
    contagem = acertos(texto).most_common()
    if not contagem:
        return None
    idioma, n = contagem[0]
    segundo = contagem[1][1] if len(contagem) > 1 else 0
    if n < MINIMO_ACERTOS or n < FOLGA * segundo:
        return None
    return idioma
