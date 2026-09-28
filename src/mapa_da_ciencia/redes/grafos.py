"""Os grafos e as métricas: coautoria entre pessoas, colaboração entre instituições e entre estados.

**Pesos (contagem fracionária, como na geografia):** um documento com `n` autores distintos soma 1 para cada autor
repartido entre os `n − 1` coautores: cada par recebe `1/(n − 1)`. Assim a força de uma pessoa (a soma dos pesos
das arestas dela) é o número de documentos em que ela teve coautor, e a soma de todos os pesos é `Σ n/2`. As
instituições seguem a mesma regra, com as instituições identificadas distintas do documento; os estados, com as UFs
brasileiras distintas e `EX` para qualquer vínculo no exterior.

**Comunidades:** Louvain (resolução 1, semente 7), no grafo com pesos. Ficam com número as de pelo menos
`MINIMO_COMUNIDADE` nós, em ordem de tamanho; o resto é `-1`.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from fractions import Fraction
from itertools import combinations

SEMENTE = 7
MINIMO_COMUNIDADE = {"coautoria": 8, "instituicoes": 5}
MAXIMO_COMUNIDADES = 40
EXTERIOR = "EX"


def pares_ponderados(grupos: dict[str, list[str]]) -> dict[tuple[str, str], tuple[float, int]]:
    """(a, b) → (peso, documentos), com 1/(n−1) por par em cada documento com n membros distintos.

    A soma é exata (frações) e só vira `float` no fim, sem arredondar: o peso de um par que escreveu três artigos a
    quatro é 1 exato, e não 0,999999; a partição do Louvain usa esses pesos (arredondá-los a 6 casas mudava a
    comunidade de um terço das pessoas no piloto)."""
    saida: dict[tuple[str, str], list] = defaultdict(lambda: [Fraction(0), 0])
    for membros in grupos.values():
        distintos = sorted(set(membros))
        n = len(distintos)
        if n < 2:
            continue
        for a, b in combinations(distintos, 2):
            saida[(a, b)][0] += Fraction(1, n - 1)
            saida[(a, b)][1] += 1
    return {k: (float(v[0]), v[1]) for k, v in sorted(saida.items())}


def forcas(grupos: dict[str, list[str]]) -> Counter[str]:
    """A força de cada membro (a soma dos pesos das arestas dele): o número de documentos em que ele teve um parceiro,
    contado direto (inteiro), sem somar pesos em ponto flutuante."""
    return Counter(x for membros in grupos.values() if len(set(membros)) > 1 for x in set(membros))


def grafo(arestas: dict[tuple[str, str], tuple[float, int]], nos: list[str] | None = None):
    import networkx as nx

    g = nx.Graph()
    g.add_nodes_from(sorted(set(nos or []) | {x for par in arestas for x in par}))
    for (a, b), (peso, docs) in arestas.items():
        g.add_edge(a, b, peso=peso, documentos=docs)
    return g


@dataclass
class Metricas:
    nos: int
    arestas: int
    componentes: int
    maior_componente: int
    fracao_maior: float
    densidade: float
    grau_medio: float
    agrupamento: float
    modularidade: float | None = None


def metricas(g, particao: list[set[str]] | None = None) -> Metricas:
    import networkx as nx
    from networkx.algorithms.community import modularity

    n = g.number_of_nodes()
    comps = [len(c) for c in nx.connected_components(g)] if n else []
    maior = max(comps, default=0)
    return Metricas(
        nos=n,
        arestas=g.number_of_edges(),
        componentes=len(comps),
        maior_componente=maior,
        fracao_maior=round(maior / n, 4) if n else 0.0,
        densidade=round(nx.density(g), 6) if n > 1 else 0.0,
        grau_medio=round(2 * g.number_of_edges() / n, 3) if n else 0.0,
        agrupamento=round(nx.average_clustering(g), 4) if n else 0.0,
        modularidade=round(modularity(g, particao, weight="peso"), 4) if particao and g.number_of_edges() else None,
    )


def comunidades(g, rede: str) -> tuple[dict[str, int], list[set[str]]]:
    """Nó → comunidade (−1 nas pequenas) e a partição inteira (para a modularidade)."""
    from networkx.algorithms.community import louvain_communities

    if g.number_of_edges() == 0:
        return dict.fromkeys(g.nodes, -1), []
    particao = louvain_communities(g, weight="peso", resolution=1.0, seed=SEMENTE)
    ordenadas = sorted(particao, key=lambda c: (-len(c), min(c)))
    rotulo: dict[str, int] = dict.fromkeys(g.nodes, -1)
    grandes = [c for c in ordenadas if len(c) >= MINIMO_COMUNIDADE[rede]][:MAXIMO_COMUNIDADES]
    for k, c in enumerate(grandes):
        for no in c:
            rotulo[no] = k
    return rotulo, [set(c) for c in particao]


@dataclass
class Colaboracao:
    """A colaboração num ano: frações dos documentos do ano (com autoria conhecida)."""

    ano: int
    documentos: int
    com_coautoria: float
    autores_medio: float
    com_instituicoes: float | None = None  # duas ou mais instituições identificadas
    entre_ufs: float | None = None  # duas ou mais UFs brasileiras
    com_exterior: float | None = None  # Brasil e exterior no mesmo documento
    extras: dict = field(default_factory=dict)


def colaboracao_por_ano(
    anos: dict[str, int],
    autores: dict[str, list[str]],
    instituicoes: dict[str, list[str]] | None = None,
    lugares: dict[str, list[str]] | None = None,
) -> list[Colaboracao]:
    """`lugares`: por documento, as UFs brasileiras e `EX` para o exterior."""
    por_ano: dict[int, list[str]] = defaultdict(list)
    for doc, pessoas in autores.items():
        if pessoas and doc in anos:
            por_ano[anos[doc]].append(doc)
    saida = []
    for ano in sorted(por_ano):
        docs = por_ano[ano]
        n = len(docs)
        c = Colaboracao(
            ano=ano,
            documentos=n,
            com_coautoria=round(sum(len(set(autores[d])) > 1 for d in docs) / n, 4),
            autores_medio=round(sum(len(set(autores[d])) for d in docs) / n, 3),
        )
        if instituicoes is not None:
            com = [d for d in docs if d in instituicoes]
            c.com_instituicoes = round(sum(len(set(instituicoes[d])) > 1 for d in com) / len(com), 4) if com else None
        if lugares is not None:
            com = [d for d in docs if d in lugares]
            if com:
                ufs = [set(lugares[d]) - {EXTERIOR} for d in com]
                c.entre_ufs = round(sum(len(u) > 1 for u in ufs) / len(com), 4)
                c.com_exterior = round(
                    sum(bool(u) and EXTERIOR in lugares[d] for u, d in zip(ufs, com, strict=True)) / len(com), 4
                )
        saida.append(c)
    return saida


def macro_dominante(docs: list[str], macro_do_doc: dict[str, int]) -> int | None:
    contagem = Counter(macro_do_doc[d] for d in docs if macro_do_doc.get(d, -1) >= 0)
    return min(contagem, key=lambda m: (-contagem[m], m)) if contagem else None  # no empate, o de menor id
