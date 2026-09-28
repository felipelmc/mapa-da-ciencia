"""Revisão da identidade das pessoas (`mapa redes --revisar`).

Lista o que a etapa deixou para uma pessoa decidir, com as evidências de cada lado (documentos, anos, revistas,
instituições, coautores e um título), a partir de `dados/redes/` da última execução:

- os pares de **homônimos** e de **grafias variantes** que ficaram separados (sem coautor nem instituição em comum);
- as **pessoas com dois ORCIDs** (no piloto, quase sempre a mesma pessoa com dois registros; às vezes, um id do
  OpenAlex que juntou duas pessoas);
- as **autorias que perderam um ORCID** de outro nome (um ORCID trocado na fonte).

O bloco YAML do fim vai para o `pessoas.yaml`: uma linha comentada por par, com ids que a etapa resolve (o id do
OpenAlex ou o ORCID da pessoa, ou o `<documento>#<posição>` de uma autoria dela). Colado como está, não muda nada; cada
linha descomentada em `fundir` ou movida para `nao_fundir` vale na próxima `mapa redes`.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from ..armazenamento import ARQUIVO, ler_tabela
from ..projeto import Projeto
from .pipeline import PASTA

NOMES_DOS_TIPOS = {
    "homonimo": "homônimos",
    "variante": "grafias variantes",
    "dois_orcids": "dois ORCIDs",
    "orcid_retirado": "ORCID de outro nome",
}


@dataclass
class Lado:
    """Uma pessoa (ou uma autoria), com o que ajuda a decidir."""

    id_yaml: str  # um id que o pessoas.yaml resolve
    nome: str
    documentos: int
    anos: str
    revistas: list[str] = field(default_factory=list)
    instituicoes: list[str] = field(default_factory=list)
    coautores: list[str] = field(default_factory=list)
    titulo: str = ""


@dataclass
class ItemRevisao:
    tipo: str
    nome: str
    a: Lado
    b: Lado | None


@dataclass
class Revisao:
    itens: list[ItemRevisao]
    total: int  # itens antes do limite
    por_tipo: dict[str, int]


def _anos(anos: list[int]) -> str:
    if not anos:
        return "—"
    return str(min(anos)) if min(anos) == max(anos) else f"{min(anos)}–{max(anos)}"


def _curto(texto: str, n: int = 70) -> str:
    return texto if len(texto) <= n else texto[: n - 1] + "…"


def revisao(projeto: Projeto, limite: int | None = 40) -> Revisao:
    """Os itens da revisão, na ordem: homônimos, variantes, dois ORCIDs e ORCIDs retirados."""
    pasta = projeto.dados / PASTA
    itens_brutos = ler_tabela(pasta / "candidatos.parquet")
    ordem_tipos = list(NOMES_DOS_TIPOS)
    itens_brutos.sort(key=lambda c: (ordem_tipos.index(c["tipo"]) if c["tipo"] in ordem_tipos else 9, c["nome"]))
    por_tipo = dict(Counter(c["tipo"] for c in itens_brutos))
    total = len(itens_brutos)
    if limite is not None:
        itens_brutos = itens_brutos[:limite]
    if not itens_brutos:
        return Revisao([], total, por_tipo)

    pessoas = {p["interno"]: p for p in ler_tabela(pasta / "pessoas.parquet")}
    publicado = {p["id"]: p for p in pessoas.values()}
    autorias = ler_tabela(pasta / "autorias.parquet")
    da_pessoa: dict[str, list[tuple[str, int]]] = defaultdict(list)
    do_doc: dict[str, list[str]] = defaultdict(list)
    for a in autorias:
        da_pessoa[a["pessoa"]].append((a["doc"], a["posicao"]))
        do_doc[a["doc"]].append(a["pessoa"])
    import duckdb

    con = duckdb.connect()
    try:
        docs = {
            d[0]: {"ano": d[1], "revista": d[2], "titulo": d[3]}
            for d in con.execute(
                "SELECT id, ano, revista_acronimo, list_extract(titulos, 1).texto FROM read_parquet(?)",
                [str(projeto.dados / ARQUIVO)],
            ).fetchall()
        }
    finally:
        con.close()
    insts = _instituicoes_das_autorias(projeto)

    def lado_da_pessoa(interno: str) -> Lado:
        p = pessoas[interno]
        membros = sorted(da_pessoa[p["id"]], key=lambda k: (-(docs.get(k[0], {}).get("ano") or 0), k))
        return _lado(_id_yaml(interno, membros), p["nome"], p["id"], membros)

    def _lado(id_yaml: str, nome: str, pid: str | None, membros: list[tuple[str, int]]) -> Lado:
        ds = sorted({d for d, _ in membros})
        coautores = Counter(
            publicado[x]["nome"] for d in ds for x in do_doc[d] if x != pid and x in publicado
        ).most_common(3)
        titulo = next((docs[d]["titulo"] for d, _ in membros if docs.get(d, {}).get("titulo")), "")
        revistas = Counter(docs[d]["revista"] for d in ds if d in docs and docs[d]["revista"])
        return Lado(
            id_yaml=id_yaml,
            nome=nome,
            documentos=len(ds),
            anos=_anos([docs[d]["ano"] for d in ds if d in docs and docs[d]["ano"]]),
            revistas=[r for r, _ in revistas.most_common(3)],
            instituicoes=[i for i, _ in Counter(i for k in membros for i in insts.get(k, ())).most_common(3)],
            coautores=[n for n, _ in coautores],
            titulo=_curto(titulo or ""),
        )

    itens = []
    for c in itens_brutos:
        if c["tipo"] == "orcid_retirado":
            doc, _, pos = c["a"].rpartition("#")
            autoria = (doc, int(pos))
            dono = next((p["id"] for p in pessoas.values() if autoria in da_pessoa[p["id"]]), None)
            a = _lado(c["a"], c["nome"], dono, [autoria])
            b = lado_da_pessoa(c["b"]) if c["b"] in pessoas else None
        else:
            a = lado_da_pessoa(c["a"])
            b = lado_da_pessoa(c["b"]) if c["b"] in pessoas else None
        itens.append(ItemRevisao(c["tipo"], c["nome"], a, b))
    return Revisao(itens, total, por_tipo)


def _id_yaml(interno: str, membros: list[tuple[str, int]]) -> str:
    """Um id que o `pessoas.yaml` resolve para esta pessoa: o interno, quando é um id do OpenAlex ou um ORCID dela
    (sem o sufixo de desempate); senão, uma autoria dela."""
    if interno.startswith(("openalex:", "orcid:")) and "#" not in interno:
        return interno
    doc, pos = min(membros)
    return f"{doc}#{pos}"


def _instituicoes_das_autorias(projeto: Projeto) -> dict[tuple[str, int], set[str]]:
    """As instituições casadas pela geografia de cada autoria (a sigla, ou o nome), se houver geografia."""
    from ..geografia.resultado import ARQUIVO_VINCULOS, ler_instituicoes, ler_vinculos
    from ..geografia.resultado import PASTA as PASTA_GEO

    pasta = projeto.dados / PASTA_GEO
    if not (pasta / ARQUIVO_VINCULOS).exists():
        return {}
    nomes = {i["id"]: i["sigla"] or i["nome"] for i in ler_instituicoes(pasta)}
    saida: dict[tuple[str, int], set[str]] = defaultdict(set)
    for v in ler_vinculos(pasta):
        if v["autor"] is not None and v["instituicao"] in nomes:
            saida[(v["doc"], v["autor"])].add(nomes[v["instituicao"]])
    return saida


def descrever(lado: Lado | None) -> str:
    """As evidências de um lado, em poucas linhas (sem marcação: o Rich imprime como está)."""
    if lado is None:
        return "—"
    linhas = [
        f"{lado.nome}",
        f"{lado.id_yaml}",
        f"{lado.documentos} doc(s), {lado.anos}" + (f" · {', '.join(lado.revistas)}" if lado.revistas else ""),
    ]
    if lado.instituicoes:
        linhas.append("inst.: " + ", ".join(lado.instituicoes))
    if lado.coautores:
        linhas.append("coautores: " + "; ".join(lado.coautores))
    if lado.titulo:
        linhas.append(f"“{lado.titulo}”")
    return "\n".join(linhas)


def bloco_yaml(itens: list[ItemRevisao]) -> str:
    """O trecho para o `pessoas.yaml`: uma linha comentada por par, em `fundir`. Colado como está, não muda nada."""
    pares = []
    for it in itens:
        if it.b is None:
            continue
        nota = f"{it.nome} ({NOMES_DOS_TIPOS.get(it.tipo, it.tipo)}; {it.a.documentos} e {it.b.documentos} docs)"
        pares.append(f"  # - [{it.a.id_yaml}, {it.b.id_yaml}]  # {nota}")
    linhas = [
        "# Descomente em `fundir` os pares que são a mesma pessoa; mova para `nao_fundir` os que não são.",
        "fundir:",
        *pares,
        "nao_fundir:",
        "nomes:",
    ]
    return "\n".join(linhas) + "\n"


def resumo_por_tipo(por_tipo: dict[str, Any]) -> str:
    """ "10 homônimos, 66 grafias variantes, …", na ordem da tabela da revisão."""
    ordem = list(NOMES_DOS_TIPOS)
    itens = sorted(por_tipo.items(), key=lambda kv: (ordem.index(kv[0]) if kv[0] in ordem else len(ordem), kv[0]))
    return ", ".join(f"{n} {NOMES_DOS_TIPOS.get(t, t)}" for t, n in itens)
