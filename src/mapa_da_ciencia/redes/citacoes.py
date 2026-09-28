"""A rede de citação, pelas referências do OpenAlex.

- **Citações internas:** um documento do corpus citando outro. Uma citação a um documento publicado mais de um ano
  depois do que cita (um erro de casamento no OpenAlex) é descartada e contada; a de um documento a si mesmo também.
- **Fluxos:** quantas citações internas vão de um tópico (ou macrotema) a outro.
- **Cânone:** as obras de fora do corpus citadas pelo maior número de documentos. O OpenAlex casa muitas referências
  a livros com o registro de uma **resenha** do livro (a do Choice Reviews, ou a de uma revista), com o resenhista
  como primeiro autor e o ano da resenha. Por isso a autoria e o ano de cada obra são conferidos nas referências da
  ArticleMeta dos documentos que a citam (o que os próprios autores escreveram, `conferir_autoria`): o autor do
  OpenAlex que não aparece nelas sai, e, se nenhum aparece, o autor e o ano vêm delas. Registros da mesma obra (o
  mesmo título normalizado e o mesmo primeiro sobrenome, depois da conferência) somam.
- **Cobertura:** quantos documentos têm referências no OpenAlex e quantas das referências que a ArticleMeta lista
  o OpenAlex resolveu (cerca de metade, no piloto). O cânone é enviesado para obras indexadas no OpenAlex: ver
  "Limitações e vieses".
"""

from __future__ import annotations

import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

from ..texto import normalizar_titulo

N_CANONE = 200
N_BUSCADAS = 500  # as obras de fora mais citadas cujos metadados a coleta busca (`fontes.openalex.N_CITADAS`)
# ids que o OpenAlex usa no lugar de obras apagadas ou fundidas: não são obras, e ficam fora das contagens
OBRAS_APAGADAS = frozenset({"W4285719527"})
EVIDENCIA_MINIMA = 3  # referências da ArticleMeta com o mesmo título, no mínimo, para conferir a autoria
_FONTES_DE_RESENHAS = ("choice reviews",)


@dataclass
class ObraCanone:
    id: str
    titulo: str | None
    ano: int | None
    autores: list[str]
    veiculo: str | None
    tipo: str | None
    doi: str | None
    n: int  # documentos do corpus que citam
    citantes: list[str]  # ids dos documentos
    edicoes: list[str] = field(default_factory=list)
    resenha: bool = False  # o registro do OpenAlex é uma resenha da obra
    autoria_das_referencias: bool = False  # autores (e ano) conferidos e corrigidos pelas referências da ArticleMeta
    autores_openalex: list[str] = field(default_factory=list)
    ano_openalex: int | None = None


@dataclass
class Citacoes:
    internas: list[tuple[str, str]]  # (cita, citado), ids de documentos
    anacronicas: int
    fluxo_macrotemas: dict[tuple[int, int], int]
    fluxo_topicos: dict[tuple[int, int], int]
    canone: list[ObraCanone]
    n_referencias: dict[str, int]  # doc → referências no OpenAlex (só os documentos casados com o OpenAlex)
    cobertura: dict[str, Any]
    sem_metadados: list[str] = field(default_factory=list)  # obras entre as mais citadas sem metadados no OpenAlex


def _sobrenome(autores: list[str]) -> str:
    partes = normalizar_titulo(autores[0]).split() if autores else []
    return partes[-1] if partes else ""


def _mesmo_titulo(a: str, b: str) -> bool:
    """Títulos normalizados iguais, ou um começo do outro (o título sem o subtítulo), com pelo menos 15 letras."""
    if not a or not b:
        return False
    return a == b or (min(len(a), len(b)) >= 15 and (a.startswith(b) or b.startswith(a)))


def _nome_legivel(prenome: str, sobrenome: str) -> str:
    """ "Kenneth" e "WALTZ" viram "Kenneth Waltz" (as referências costumam trazer o sobrenome em maiúsculas)."""
    partes = [p.title() if p.isupper() else p for p in (prenome.strip(), sobrenome.strip()) if p]
    return " ".join(partes)


def _eh_resenha(meta: dict[str, Any]) -> bool:
    veiculo = normalizar_titulo(meta.get("veiculo") or "")
    return meta.get("tipo") == "book-review" or any(f in veiculo for f in _FONTES_DE_RESENHAS)


def _partes(nome: str) -> set[str]:
    return set(normalizar_titulo(nome).split())


_SUFIXOS = {"jr", "junior", "filho", "neto", "sobrinho"}


def _ultimo_sobrenome(nome: str) -> str | None:
    """O último pedaço do sobrenome que não é um sufixo ("cheibub figueiredo" → "figueiredo"; "ZUCCO JR" → "zucco")."""
    partes = [p for p in normalizar_titulo(nome).split() if p not in _SUFIXOS]
    return partes[-1] if partes else None


def _mais_comum(contagem: Counter) -> tuple[Any, int]:
    """O item mais frequente, com o empate decidido pelo menor valor (e não pela ordem de inserção, que num `set`
    muda com a semente de hash do Python e mudava o cânone de uma execução para outra)."""
    return min(contagem.items(), key=lambda kv: (-kv[1], kv[0]))


def conferir_autoria(meta: dict[str, Any], referencias: list[dict[str, Any]], n_citantes: int) -> dict[str, Any]:
    """Autores e ano de uma obra conferidos nas referências da ArticleMeta que a citam pelo mesmo título.

    Com evidência bastante (`EVIDENCIA_MINIMA` referências e ao menos 20% dos citantes), o autor principal é o primeiro
    autor da maioria das referências, ou, num livro organizado (citado por capítulos de autores diferentes), o
    sobrenome presente em 60% delas. Os autores são os sobrenomes que metade das referências traz, na ordem delas
    (com o nome do OpenAlex quando ele os tem), seguidos dos outros do OpenAlex; se o primeiro autor do OpenAlex não
    aparece nas referências (o resenhista), só ficam os do OpenAlex que elas citam. O ano segue
    `_ano_das_referencias`. Devolve `autores`, `ano`, `resenha` e `autoria_das_referencias`."""
    titulo = normalizar_titulo(limpar_titulo(meta.get("titulo")) or "")
    autores_oa = list(meta.get("autores") or [])
    resenha = _eh_resenha(meta)
    saida = {"autores": autores_oa, "ano": meta.get("ano"), "resenha": resenha, "autoria_das_referencias": False}
    achadas = [
        r
        for r in referencias
        if r.get("sobrenomes")
        and (
            _mesmo_titulo(titulo, normalizar_titulo(r.get("titulo") or ""))
            or _mesmo_titulo(titulo, normalizar_titulo(r.get("titulo_fonte") or ""))
        )
    ]
    n = len(achadas)
    if n < max(EVIDENCIA_MINIMA, 0.2 * n_citantes):
        return saida
    # o último pedaço de cada sobrenome, na ordem da referência ("cheibub figueiredo" → "figueiredo")
    ultimos = [[p for nome in r["sobrenomes"] if (p := _ultimo_sobrenome(nome))] for r in achadas]
    primeiros = Counter(u[0] for u in ultimos if u)
    todos = Counter(x for u in ultimos for x in dict.fromkeys(u))
    if primeiros and _mais_comum(primeiros)[1] >= 0.5 * n:
        principal = _mais_comum(primeiros)[0]
    elif todos and _mais_comum(todos)[1] >= 0.6 * n:
        principal = _mais_comum(todos)[0]
    else:
        return saida
    presentes = {x for x, k in todos.items() if k >= max(2, 0.1 * n)}
    # os autores da obra segundo as referências: os sobrenomes presentes em metade delas ou mais (os três de King,
    # Keohane e Verba), na posição média em que aparecem, o principal primeiro
    posicao = {x: statistics.mean(u.index(x) for u in ultimos if x in u) for x in todos}
    da_obra = sorted((x for x, k in todos.items() if k >= 0.5 * n or x == principal),
                     key=lambda x: (x != principal, posicao[x], x))  # fmt: skip
    # do OpenAlex, ficam todos se o primeiro está nas referências (as que abreviam com "et al." não tiram ninguém);
    # senão, só os que elas citam (sai o resenhista)
    primeiro_saiu = bool(autores_oa) and not (_partes(autores_oa[0]) & presentes)
    base = [a for a in autores_oa if _partes(a) & presentes] if primeiro_saiu else list(autores_oa)
    ordenados: list[str] = []
    for x in da_obra:
        achado = next((a for a in base if x in _partes(a) and a not in ordenados), None)
        ordenados.append(achado or _das_referencias(achadas, x))
    mantidos = (ordenados + [a for a in base if a not in ordenados])[:3]
    saida["autores"] = mantidos
    saida["autoria_das_referencias"] = [normalizar_titulo(a) for a in mantidos] != [
        normalizar_titulo(a) for a in autores_oa[:3]
    ]
    saida["resenha"] = resenha or primeiro_saiu
    saida["ano"] = _ano_das_referencias(meta.get("ano"), [r["ano"] for r in achadas if r.get("ano")], saida["resenha"])
    return saida


def _ano_das_referencias(ano_oa: int | None, anos_refs: list[int], resenha: bool) -> int | None:
    """O ano da obra: o das referências quando a maioria concorda (a edição original de um livro que o OpenAlex casou
    com um capítulo de coletânea de 2015, ou com uma reimpressão); quando o registro é uma resenha, ou o ano do
    OpenAlex quase não aparece nas referências (Kingdon, 1985, que elas nunca citam), o mais citado, ou, sem um
    mais citado claro, a primeira edição que várias citam. Senão, o do OpenAlex."""
    if not anos_refs:
        return ano_oa
    n = len(anos_refs)
    anos = Counter(anos_refs)
    ano, vezes = _mais_comum(anos)
    if vezes >= 0.5 * n:
        return ano
    if resenha or ano_oa is None or anos.get(ano_oa, 0) < 0.1 * n:
        if vezes >= 0.3 * n:
            return ano
        varias = sorted(a for a, k in anos.items() if k >= max(2, 0.1 * n))
        return varias[0] if varias else ano_oa
    return ano_oa


def _das_referencias(achadas: list[dict[str, Any]], sobrenome: str) -> str:
    """O nome de um autor como as referências o escrevem: o prenome mais completo entre os que aparecem ao menos
    duas vezes ("André", e não "A."), senão o mais frequente."""
    nomes: Counter[tuple[str, str]] = Counter()
    for r in achadas:
        prenomes = list(r.get("prenomes") or [])
        for k, nome in enumerate(r["sobrenomes"]):
            if _ultimo_sobrenome(nome) == sobrenome:
                nomes[(prenomes[k] if k < len(prenomes) else "", nome)] += 1
    repetidos = [kv for kv in nomes.items() if kv[1] >= 2] or list(nomes.items())
    (prenome, nome), _ = max(repetidos, key=lambda kv: (len(kv[0][0].replace(".", "")), kv[1], kv[0]))
    return _nome_legivel(prenome, nome)


_NUMERACAO = re.compile(r"^\s*\d{1,3}\s*[.)–-]\s+")
# títulos que não são de uma obra ("Resumos", "Introdução"): registros espúrios, que ficam fora do cânone
TITULOS_GENERICOS = frozenset(
    {
        "resumo", "resumos", "abstract", "abstracts", "introducao", "introduction", "apresentacao", "editorial",
        "prefacio", "preface", "conclusao", "conclusion", "conclusoes", "resenha", "resenhas", "book reviews",
        "reviews", "notas", "notes", "errata", "erratum", "indice", "index", "sumario", "contents", "referencias",
        "references", "bibliografia", "bibliography", "comentarios", "comments", "entrevista", "interview",
    }
)  # fmt: skip


def limpar_titulo(titulo: str | None) -> str | None:
    """O título sem a numeração de capítulo no começo ("66. Civil Society…" → "Civil Society…")."""
    return _NUMERACAO.sub("", titulo).strip() or titulo if titulo else titulo


def _chave_do_titulo(titulo: str | None) -> str:
    """O título sem acentos, pontuação nem espaços ("World’s" e "World's" davam "worlds" e "world s")."""
    return normalizar_titulo(limpar_titulo(titulo)).replace(" ", "")


def _mesmo_texto(a: str, b: str) -> bool:
    """Chaves de título da mesma obra: iguais, uma o começo da outra (sem o subtítulo), ou quase iguais em títulos
    longos ("…Democratic Government" e "…Democratic Governance")."""
    if a == b:
        return True
    if min(len(a), len(b)) >= 20 and (a.startswith(b) or b.startswith(a)):
        return True
    return min(len(a), len(b)) >= 25 and SequenceMatcher(None, a, b, autojunk=False).ratio() >= 0.92


def _mesma_obra(meta: dict[str, dict[str, Any]], conferidas: dict[str, dict[str, Any]]) -> list[list[str]]:
    """Os registros agrupados por obra: o mesmo primeiro sobrenome (depois da conferência) e o mesmo título (iguais,
    um sem o subtítulo, ou quase iguais). Registros sem título ficam sozinhos."""
    pai = {w: w for w in meta}

    def raiz(w: str) -> str:
        while pai[w] != w:
            pai[w] = pai[pai[w]]
            w = pai[w]
        return w

    por_sobrenome: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for w in sorted(meta):
        chave = _chave_do_titulo(meta[w].get("titulo"))
        if chave:
            por_sobrenome[_sobrenome(conferidas[w]["autores"])].append((chave, w))
    for lista in por_sobrenome.values():
        for x in range(len(lista)):
            for y in range(x + 1, len(lista)):
                if _mesmo_texto(lista[x][0], lista[y][0]):
                    a, b = raiz(lista[x][1]), raiz(lista[y][1])
                    pai[max(a, b)] = min(a, b)
    grupos: dict[str, list[str]] = defaultdict(list)
    for w in sorted(meta):
        grupos[raiz(w)].append(w)
    return list(grupos.values())


def calcular(
    referencias: list[dict[str, str]],
    citadas: list[dict[str, Any]],
    doc_da_obra: dict[str, str],
    anos: dict[str, int],
    topico_do_doc: dict[str, int],
    macro_do_topico: dict[int, int],
    referencias_articlemeta: dict[str, list[dict[str, Any]]] | None = None,
    listadas: dict[str, int] | None = None,
) -> Citacoes:
    """`referencias`: linhas (obra, citada) de `referencias_openalex.parquet`; `doc_da_obra`: W… → id do documento;
    `referencias_articlemeta`: documento → as referências que a ArticleMeta lista (para conferir a autoria do
    cânone); `listadas`: documento → quantas referências a ArticleMeta lista (para a cobertura por referência)."""
    referencias_articlemeta = referencias_articlemeta or {}
    por_obra: dict[str, list[str]] = defaultdict(list)
    apagadas = 0
    for r in referencias:
        if r["citada"] in OBRAS_APAGADAS:
            apagadas += 1
            continue
        por_obra[r["obra"]].append(r["citada"])
    internas, anacronicas, autorreferencias = set(), 0, 0
    externas: dict[str, set[str]] = defaultdict(set)
    n_referencias = {}
    for obra, citadas_da_obra in por_obra.items():
        doc = doc_da_obra.get(obra)
        if doc is None:
            continue
        n_referencias[doc] = len(citadas_da_obra)
        for w in citadas_da_obra:
            alvo = doc_da_obra.get(w)
            if alvo is None:
                externas[w].add(doc)
            elif alvo == doc:
                autorreferencias += 1
            elif anos.get(alvo, 0) > anos.get(doc, 0) + 1:
                anacronicas += 1
            else:
                internas.add((doc, alvo))
    fluxo_t: Counter[tuple[int, int]] = Counter()
    fluxo_m: Counter[tuple[int, int]] = Counter()
    for de, para in internas:
        ta, tb = topico_do_doc.get(de, -1), topico_do_doc.get(para, -1)
        if ta >= 0 and tb >= 0:
            fluxo_t[(ta, tb)] += 1
            fluxo_m[(macro_do_topico[ta], macro_do_topico[tb])] += 1

    # cânone: cada registro conferido nas referências da ArticleMeta, e os registros da mesma obra somados
    genericos = {c["id"] for c in citadas if normalizar_titulo(c.get("titulo") or "") in TITULOS_GENERICOS}
    meta = {c["id"]: c for c in citadas if c["id"] not in OBRAS_APAGADAS | genericos}
    conferidas: dict[str, dict[str, Any]] = {}
    for w, m in meta.items():
        citantes = externas.get(w, set())
        refs = [r for d in sorted(citantes) for r in referencias_articlemeta.get(d, ())]
        conferidas[w] = conferir_autoria(m, refs, len(citantes))
    canone = []
    for ws in _mesma_obra(meta, conferidas):
        citantes = sorted(set().union(*(externas.get(w, set()) for w in ws)))
        if not citantes:
            continue
        principal = max(ws, key=lambda w: (len(externas.get(w, ())), meta[w].get("citacoes") or 0, w))
        m, c = meta[principal], conferidas[principal]
        canone.append(
            ObraCanone(
                id=principal,
                titulo=limpar_titulo(m.get("titulo")),
                ano=c["ano"],
                autores=list(c["autores"])[:3],
                veiculo=m.get("veiculo"),
                tipo=m.get("tipo"),
                doi=m.get("doi"),
                n=len(citantes),
                citantes=citantes,
                edicoes=sorted(w for w in ws if w != principal),
                resenha=c["resenha"],
                autoria_das_referencias=c["autoria_das_referencias"],
                autores_openalex=list(m.get("autores") or []),
                ano_openalex=m.get("ano"),
            )
        )
    canone.sort(key=lambda o: (-o.n, o.id))
    canone = canone[:N_CANONE]
    # as obras que a coleta buscou e o OpenAlex não descreveu, com citantes para entrar no cânone
    corte = canone[-1].n if len(canone) == N_CANONE else 1
    buscadas = sorted(externas, key=lambda w: (-len(externas[w]), w))[:N_BUSCADAS]
    sem_metadados = [w for w in buscadas if w not in meta and len(externas[w]) >= corte]

    # a cobertura por referência sobre todos os documentos casados com referências listadas na ArticleMeta, também os
    # que não têm nenhuma resolvida (contam 0%)
    listadas = {d: k for d, k in (listadas or {}).items() if k}
    com_as_duas = sorted(listadas)
    razoes = [min(1.0, n_referencias.get(d, 0) / listadas[d]) for d in com_as_duas]
    return Citacoes(
        internas=sorted(internas),
        anacronicas=anacronicas,
        fluxo_macrotemas=dict(sorted(fluxo_m.items())),
        fluxo_topicos=dict(sorted(fluxo_t.items())),
        canone=canone,
        n_referencias=n_referencias,
        cobertura={
            "documentos": len(anos),
            "com_referencias": sum(1 for d in n_referencias if n_referencias[d] > 0),
            "referencias": sum(n_referencias.values()),
            # as referências que a ArticleMeta lista nos documentos casados com o OpenAlex, quantas delas o OpenAlex
            # resolveu, e a mediana por documento dessa fração (em pontos percentuais)
            "referencias_listadas": sum(listadas[d] for d in com_as_duas),
            "referencias_resolvidas": sum(n_referencias.get(d, 0) for d in com_as_duas),
            "resolvidas_mediana_pct": round(100 * statistics.median(razoes)) if razoes else 0,
            "internas": len(internas),
            "anacronicas": anacronicas,
            "autorreferencias": autorreferencias,
            "a_obras_apagadas": apagadas,
            "citantes_do_canone": len({d for o in canone for d in o.citantes}),
            "resenhas_no_canone": sum(o.resenha for o in canone),
            "autoria_das_referencias": sum(o.autoria_das_referencias for o in canone),
            "sem_metadados": len(sem_metadados),
            "titulos_genericos": len(genericos & set(externas)),
        },
        sem_metadados=sem_metadados,
    )
