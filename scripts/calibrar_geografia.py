"""Calibra o casamento das afiliações num projeto: quanto é identificado, por fonte e por nível, e com que precisão.

Três usos:

    # taxas de identificação por fonte (v240, v70, openalex) e por nível do casamento
    uv run python scripts/calibrar_geografia.py projetos/cp-scielo

    # sorteia uma amostra estratificada por nível para rotular à mão (coluna `rotulo`: certo, errado ou ?);
    # com --anteriores, herda os rótulos de uma amostra antiga quando o par texto → instituição não mudou
    uv run python scripts/calibrar_geografia.py projetos/cp-scielo --amostra 200 --saida amostra.csv \
        --anteriores rotulos-antigos.csv

    # precisão por nível (com intervalo de Wilson) e geral (ponderada pelo tamanho de cada nível)
    uv run python scripts/calibrar_geografia.py projetos/cp-scielo --rotulada amostra.csv

Na amostra, o estrato `nenhum` (vínculos com texto que não casaram) traz os três melhores candidatos do índice: o
rótulo `certo` diz que nenhum deles é a instituição (não casar foi o certo), e `errado`, que um deles era.
Não grava nada no projeto. Os números embasam os limiares de `geografia/casamento.py` (ADR 0008).
"""

from __future__ import annotations

import argparse
import csv
import math
import random
from collections import Counter, defaultdict
from pathlib import Path

from mapa_da_ciencia.armazenamento import ARQUIVO, ler_documentos
from mapa_da_ciencia.geografia import instituicoes as inst
from mapa_da_ciencia.geografia.casamento import NIVEIS, Casador, Indice, Vinculo

SEMENTE = 7
# fração da amostra por nível (o `autoria` é o grosso dos vínculos; os outros níveis pesam mais na amostra para a
# precisão deles ter um intervalo útil)
PESOS = {"autoria": 0.3, "obra": 0.1, "corpus": 0.12, "indice": 0.2, "openalex": 0.1, "apelido": 0.03, "nenhum": 0.15}
COLUNAS = [
    "doc", "autor", "fonte", "nivel", "semelhanca", "pais_fonte", "texto", "casada", "casada_nome", "instituicao",
    "instituicao_nome", "instituicao_pais", "candidatos", "rotulo",
]  # fmt: skip


def casar(raiz: Path) -> tuple[Indice, list[tuple[str, Vinculo]]]:
    docs = ler_documentos(raiz / "dados" / ARQUIVO)
    registros = inst.completar(inst.ler_openalex(raiz / "dados"), docs)
    registros, apelidos = inst.combinar(registros, inst.ler_projeto(raiz))
    indice = Indice(registros, apelidos)
    return indice, [(c.doc, v) for c in Casador(indice).casar(docs) for v in c.vinculos]


def taxas(vinculos: list[tuple[str, Vinculo]]) -> None:
    por_fonte: dict[str, Counter[str]] = defaultdict(Counter)
    for _, v in vinculos:
        por_fonte[v.fonte][v.nivel] += 1
    print(f"{'fonte':10}{'vínculos':>10}{'identificados':>15}   por nível")
    total = identificados = 0
    for fonte, niveis in sorted(por_fonte.items()):
        n = sum(niveis.values())
        ok = n - niveis["nenhum"]
        total, identificados = total + n, identificados + ok
        detalhe = ", ".join(f"{k} {niveis[k]}" for k in NIVEIS if niveis[k])
        print(f"{fonte:10}{n:>10}{ok:>9} ({ok / n:5.1%})   {detalhe}")
    print(f"{'total':10}{total:>10}{identificados:>9} ({identificados / total:5.1%})")


def linha(indice: Indice, doc: str, v: Vinculo) -> dict[str, object]:
    def nome(id_: str | None) -> str:
        return indice.registros[id_].nome if id_ in indice.registros else ""

    candidatos = ""
    if v.nivel == "nenhum":
        notas = indice.melhores(v.texto, indice.candidatos_globais(v.texto), None)[:3]
        candidatos = " | ".join(f"{nome(c)} ({indice.registros[c].pais}, {n:.2f})" for n, c in notas)
    return {
        "doc": doc, "autor": v.autor, "fonte": v.fonte, "nivel": v.nivel, "semelhanca": v.semelhanca,
        "pais_fonte": v.pais_fonte, "texto": v.texto, "casada": v.casada, "casada_nome": nome(v.casada),
        "instituicao": v.instituicao, "instituicao_nome": nome(v.instituicao),
        "instituicao_pais": indice.registros[v.instituicao].pais if v.instituicao in indice.registros else "",
        "candidatos": candidatos, "rotulo": "",
    }  # fmt: skip


def _chave(doc: object, fonte: object, texto: object, instituicao: object) -> tuple[str, str, str, str]:
    return (str(doc), str(fonte), str(texto), str(instituicao or ""))


def ler_rotulos(arquivo: Path | None) -> dict[tuple[str, str, str, str], str]:
    if arquivo is None:
        return {}
    with arquivo.open(encoding="utf-8") as f:
        return {_chave(r["doc"], r["fonte"], r["texto"], r["instituicao"]): r["rotulo"] for r in csv.DictReader(f)}


def amostrar(
    indice: Indice,
    vinculos: list[tuple[str, Vinculo]],
    n: int,
    saida: Path,
    anteriores: Path | None = None,
    semente: int = SEMENTE,
) -> None:
    rng = random.Random(semente)
    por_nivel: dict[str, list[tuple[str, Vinculo]]] = defaultdict(list)
    for doc, v in vinculos:
        if v.texto:
            por_nivel[v.nivel].append((doc, v))
    linhas = []
    for nivel, peso in PESOS.items():
        grupo = por_nivel.get(nivel, [])
        linhas += [linha(indice, d, v) for d, v in rng.sample(grupo, min(len(grupo), round(n * peso)))]
    herdados = ler_rotulos(anteriores)
    for r in linhas:
        r["rotulo"] = herdados.get(_chave(r["doc"], r["fonte"], r["texto"], r["instituicao"]), "")
    with saida.open("w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, COLUNAS)
        escritor.writeheader()
        escritor.writerows(linhas)
    faltam = sum(not r["rotulo"] for r in linhas)
    print(f"{len(linhas)} vínculos em {saida} ({faltam} sem rótulo): preencha a coluna `rotulo` (certo, errado ou ?)")


def wilson(certos: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if n == 0:
        return (math.nan, math.nan)
    p = certos / n
    centro = (p + z * z / (2 * n)) / (1 + z * z / n)
    meia = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (centro - meia, centro + meia)


def precisao(vinculos: list[tuple[str, Vinculo]], rotulada: Path) -> None:
    """Precisão na amostra rotulada, conferindo que cada par texto → instituição ainda é o que o casamento dá."""
    atuais = {_chave(d, v.fonte, v.texto, v.instituicao) for d, v in vinculos}
    with rotulada.open(encoding="utf-8") as f:
        todas = list(csv.DictReader(f))
    mudaram = [r for r in todas if _chave(r["doc"], r["fonte"], r["texto"], r["instituicao"]) not in atuais]
    if mudaram:
        print(f"{len(mudaram)} vínculos da amostra mudaram desde a rotulagem e ficam de fora; sorteie de novo com")
        print("--amostra e --anteriores para rotular o que mudou")
    linhas = [r for r in todas if r["rotulo"] in ("certo", "errado") and r not in mudaram]
    tamanho = Counter(v.nivel for _, v in vinculos if v.texto)
    print(f"{'nível':10}{'rotulados':>10}{'certos':>8}{'precisão':>10}   IC 95%        vínculos")
    ponderada = peso_total = 0.0
    for nivel in NIVEIS:
        grupo = [r for r in linhas if r["nivel"] == nivel]
        if not grupo:
            continue
        certos = sum(r["rotulo"] == "certo" for r in grupo)
        a, b = wilson(certos, len(grupo))
        p = certos / len(grupo)
        print(f"{nivel:10}{len(grupo):>10}{certos:>8}{p:>10.1%}   {a:.1%}–{b:.1%}   {tamanho[nivel]:>8}")
        if nivel != "nenhum":
            ponderada += p * tamanho[nivel]
            peso_total += tamanho[nivel]
    print(f"precisão dos identificados, ponderada pelo tamanho de cada nível: {ponderada / peso_total:.1%}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("projeto", type=Path)
    parser.add_argument("--amostra", type=int)
    parser.add_argument("--saida", type=Path, default=Path("amostra-geografia.csv"))
    parser.add_argument("--rotulada", type=Path)
    parser.add_argument("--anteriores", type=Path, help="amostra rotulada antes, para herdar os rótulos")
    parser.add_argument("--semente", type=int, default=SEMENTE, help="outra semente sorteia uma amostra independente")
    args = parser.parse_args()
    indice, vinculos = casar(args.projeto)
    taxas(vinculos)
    if args.amostra:
        amostrar(indice, vinculos, args.amostra, args.saida, args.anteriores, args.semente)
    if args.rotulada:
        precisao(vinculos, args.rotulada)


if __name__ == "__main__":
    main()
