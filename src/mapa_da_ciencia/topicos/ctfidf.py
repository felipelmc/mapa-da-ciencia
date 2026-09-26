"""Palavras-chave de cada tópico (c-TF-IDF) e documentos representativos.

O c-TF-IDF (de *class-based* TF-IDF, como no BERTopic) trata cada tópico como um grande documento: um termo pesa
mais quanto mais frequente é no tópico e mais raro no resto do corpus. As palavras-chave saem dos textos no
**idioma de exibição** (`recorte.idioma_exibicao`, português por padrão), com o de análise como reserva, e só
dos documentos do **núcleo** de cada tópico (ADR 0004 e 0007).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mapa_da_ciencia.documento import Documento

if TYPE_CHECKING:
    import numpy as np

STOP_PT = set(
    """a à ao aos as às até com como da das de dela dele deles demais do dos e é ela elas ele eles em entre era
essa essas esse esses esta está estas este estes eu foi foram há isso isto já la lhe mais mas me mesmo meu minha
muito na nas nem no nos nós num numa o os ou para pela pelas pelo pelos por qual quais quando que quem se sem ser
seu seus sua suas só também te tem têm ter um uma umas uns vez são sobre partir através bem assim ainda cada onde
após neste nesta nesse nessa desse dessa deste desta daquele daquela aquele aquela aquilo não sim nosso nossa
nossos nossas dois duas três primeiro segunda segundo bem outro outra outros outras sendo sido pode podem possa
seja sejam deve devem aqui além apenas tanto quanto tal tais qualquer todo toda todos todas grande grandes novo
nova novos novas meio fim forma modo caso partir diante perante sob contra durante mediante conforme segundo
enquanto porque pois porém contudo embora então logo desde hoje""".split()
)
STOP_EN = set(
    """a an and are as at be been but by for from has have in into is it its of on or that the their this to was
were which with we our these those than then also between based can may how what whether not no its itself they
them there here such other others more most much many one two three first second new well within without over
under upon about after before during through while where when who whom whose why would could should will shall
do does did done being having""".split()
)
STOP_ES = set(
    """el la los las un una unos unas y o de del al en con por para como que se su sus es son fue fueron lo le les
más pero entre sobre este esta estos estas ese esa esos esas muy también sin hasta desde""".split()
)
# Palavras de "gênero acadêmico": aparecem em quase todo resumo e não dizem nada sobre o assunto
STOP_ACADEMICO = set(
    """artigo artigos trabalho estudo estudos análise analisa analisar analisamos busca buscamos discute discutir
discutimos objetivo objetivos presente texto resultado resultados pesquisa pesquisas apresenta apresentamos
argumenta argumentamos propõe propomos mostra mostram demonstra examina examinamos investiga investigamos
paper article articles study studies analysis analyze analyzes analyses research results result findings argue
argues show shows examine examines investigate investigates propose proposes aims aim discuss discusses
estudio análisis artículo resultados""".split()
)
STOPWORDS = sorted(STOP_PT | STOP_EN | STOP_ES | STOP_ACADEMICO)
_PADRAO = r"(?u)\b[^\W\d_]{3,}\b"  # palavras de 3 letras ou mais, sem números


def texto_de_exibicao(doc: Documento, idioma_exibicao: str, idioma_analise: str) -> str:
    """Título e resumo no idioma de exibição (senão no de análise, senão no que houver), para as palavras-chave."""
    titulo = doc.texto_em("titulos", [idioma_exibicao, idioma_analise])
    resumo = doc.texto_em("resumos", [idioma_exibicao, idioma_analise])
    return " ".join(t.texto for t in (titulo, resumo) if t)


def _acrescentar(termo: str, escolhidos: list[str]) -> None:
    """Acrescenta o termo sem repetir: uma palavra já contida num par escolhido fica de fora, e um par novo
    substitui as palavras soltas que ele contém ("rio janeiro" substitui "janeiro")."""
    palavras = termo.split()
    if len(palavras) == 1:
        if not any(termo in e.split() for e in escolhidos if " " in e):
            escolhidos.append(termo)
        return
    escolhidos[:] = [e for e in escolhidos if e not in palavras]
    escolhidos.append(termo)


def palavras_chave(
    textos: list[str], topicos: np.ndarray, *, n: int = 15, min_df: int = 3
) -> dict[int, list[tuple[str, float]]]:
    """Os `n` termos (palavras e pares de palavras) mais característicos de cada tópico, com o peso c-TF-IDF.

    `topicos` tem o tópico de cada texto (−1 fica de fora). Um termo precisa aparecer em ao menos `min_df`
    documentos do corpus: termos raríssimos costumam ser nomes próprios ou erros de digitação.
    """
    import numpy as np
    from sklearn.feature_extraction.text import CountVectorizer

    ids = sorted(int(t) for t in set(topicos.tolist()) - {-1})
    if not ids:
        return {}
    contador = CountVectorizer(
        ngram_range=(1, 2), stop_words=STOPWORDS, min_df=min(min_df, len(textos)), token_pattern=_PADRAO
    )
    contagens = contador.fit_transform(textos)
    frequencias = np.vstack([np.asarray(contagens[topicos == t].sum(axis=0)).ravel() for t in ids]).astype(float)
    tf = frequencias / np.maximum(frequencias.sum(axis=1, keepdims=True), 1)
    idf = np.log(1 + frequencias.sum(axis=1).mean() / np.maximum(frequencias.sum(axis=0), 1))
    pesos = tf * idf
    termos = contador.get_feature_names_out()
    saida: dict[int, list[tuple[str, float]]] = {}
    for linha, t in enumerate(ids):
        escolhidos: list[str] = []
        for j in np.argsort(-pesos[linha], kind="stable"):
            if pesos[linha, j] <= 0 or len(escolhidos) == n:
                break
            _acrescentar(str(termos[j]), escolhidos)
        com_peso = [(termo, round(float(pesos[linha, contador.vocabulary_[termo]]), 5)) for termo in escolhidos]
        saida[t] = sorted(com_peso, key=lambda par: -par[1])
    return saida


def representativos(matriz: np.ndarray, topicos: np.ndarray, ids: list[str], *, n: int = 5) -> dict[int, list[str]]:
    """Os `n` documentos de cada tópico mais próximos do centro dele (média dos embeddings do núcleo)."""
    import numpy as np

    saida = {}
    for t in sorted(int(x) for x in set(topicos.tolist()) - {-1}):
        membros = np.flatnonzero(topicos == t)
        centro = matriz[membros].mean(axis=0)
        centro /= np.linalg.norm(centro) or 1.0
        ordem = np.argsort(-(matriz[membros] @ centro), kind="stable")[:n]
        saida[t] = [ids[i] for i in membros[ordem]]
    return saida
