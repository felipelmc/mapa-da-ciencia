"""A rede de citação, pelas referências do OpenAlex.

- **Citações internas:** um documento do corpus citando outro. Uma citação a um documento publicado mais de um ano
  depois do que cita (um erro de casamento no OpenAlex) é descartada e contada.
- **Fluxos:** quantas citações internas vão de um tópico (ou macrotema) a outro.
- **Cânone:** as obras de fora do corpus citadas pelo maior número de documentos, com a contagem por macrotema e por
  década de quem cita. Edições da mesma obra (mesmo título normalizado e mesmo primeiro sobrenome) somam.
- **Cobertura:** quantos documentos têm referências no OpenAlex. O cânone é enviesado para obras com DOI e
  indexadas no OpenAlex (livros e capítulos em português ficam de fora com frequência): ver "Limitações e vieses".
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from ..texto import normalizar_titulo

N_CANONE = 200


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


@dataclass
class Citacoes:
    internas: list[tuple[str, str]]  # (cita, citado), ids de documentos
    anacronicas: int
    fluxo_macrotemas: dict[tuple[int, int], int]
    fluxo_topicos: dict[tuple[int, int], int]
    canone: list[ObraCanone]
    n_referencias: dict[str, int]  # doc → referências no OpenAlex (só os documentos casados com o OpenAlex)
    cobertura: dict[str, Any]


def _sobrenome(autores: list[str]) -> str:
    return normalizar_titulo(autores[0]).split()[-1] if autores and normalizar_titulo(autores[0]) else ""


def calcular(
    referencias: list[dict[str, str]],
    citadas: list[dict[str, Any]],
    doc_da_obra: dict[str, str],
    anos: dict[str, int],
    topico_do_doc: dict[str, int],
    macro_do_topico: dict[int, int],
) -> Citacoes:
    """`referencias`: linhas (obra, citada) de `referencias_openalex.parquet`; `doc_da_obra`: W… → id do documento."""
    por_obra: dict[str, list[str]] = defaultdict(list)
    for r in referencias:
        por_obra[r["obra"]].append(r["citada"])
    internas, anacronicas = set(), 0
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
            elif alvo != doc:
                if anos.get(alvo, 0) > anos.get(doc, 0) + 1:
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
    # cânone, com as edições da mesma obra somadas
    meta = {c["id"]: c for c in citadas}
    grupos: dict[tuple[str, str], list[str]] = defaultdict(list)
    for w in meta:
        m = meta[w]
        chave = (
            (normalizar_titulo(m.get("titulo") or ""), _sobrenome(m.get("autores") or []))
            if m.get("titulo")
            else (w, "")
        )
        grupos[chave].append(w)
    canone = []
    for ws in grupos.values():
        citantes = sorted(set().union(*(externas.get(w, set()) for w in ws)))
        if not citantes:
            continue
        principal = max(ws, key=lambda w: (len(externas.get(w, ())), meta[w].get("citacoes") or 0, w))
        m = meta[principal]
        canone.append(
            ObraCanone(
                id=principal,
                titulo=m.get("titulo"),
                ano=m.get("ano"),
                autores=list(m.get("autores") or []),
                veiculo=m.get("veiculo"),
                tipo=m.get("tipo"),
                doi=m.get("doi"),
                n=len(citantes),
                citantes=citantes,
                edicoes=sorted(w for w in ws if w != principal),
            )
        )
    canone.sort(key=lambda o: (-o.n, o.id))
    canone = canone[:N_CANONE]
    com_refs = sum(1 for d in n_referencias if n_referencias[d] > 0)
    total_refs = sum(n_referencias.values())
    return Citacoes(
        internas=sorted(internas),
        anacronicas=anacronicas,
        fluxo_macrotemas=dict(sorted(fluxo_m.items())),
        fluxo_topicos=dict(sorted(fluxo_t.items())),
        canone=canone,
        n_referencias=n_referencias,
        cobertura={
            "documentos": len(anos),
            "com_referencias": com_refs,
            "referencias": total_refs,
            "internas": len(internas),
            "anacronicas": anacronicas,
            "citantes_do_canone": len({d for o in canone for d in o.citantes}),
        },
    )
