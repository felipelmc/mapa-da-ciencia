"""Compara duas rodadas de um projeto: o que uma coleta ou um recálculo mudou no corpus, na geografia e nos tópicos.

Feito para refazer o piloto com segurança: copie o projeto (`antes`), rode as etapas numa segunda cópia (`depois`) e
leia o relatório antes de tocar no original. Escreve Markdown com:

- os documentos que entraram e os que saíram;
- os resumos que saíram e os que mudaram de idioma;
- os documentos cujo texto de análise (tópicos) ou texto a classificar mudou;
- os totais por UF e os vínculos que mudaram de UF;
- os tópicos: para cada tópico novo, o de mesmo número na rodada anterior (a identidade dos tópicos casa os números
  pelos núcleos), o Jaccard dos núcleos, os tamanhos, as palavras-chave, títulos, o rótulo antigo, o novo e a
  entrada do `rotulos.yaml`. "rever" marca um tópico que mudou muito (Jaccard abaixo de 0,5) ou uma entrada do
  `rotulos.yaml` cujo tópico sumiu.

Uso (da raiz do repo):
    uv run python scripts/comparar_rodadas.py ANTES DEPOIS [--rotulos ARQUIVO] > comparacao.md
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import yaml

from mapa_da_ciencia.armazenamento import ARQUIVO, ler_documentos, ler_tabela
from mapa_da_ciencia.classificacao.executor import textos_para_classificar
from mapa_da_ciencia.config import carregar_config
from mapa_da_ciencia.documento import Documento
from mapa_da_ciencia.embeddings import texto_de_analise

JACCARD_MINIMO = 0.5
_SIGLAS = re.compile(r"\b(?:EUA|Estados Unidos|RI|Relações Internacionais|covid-19|Covid-19|COVID-19)\b")


def jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a | b else 1.0


def _resumos(doc: Documento) -> dict[str, str]:
    return {f"{r.origem}:{r.texto[:80]}": r.idioma or "?" for r in doc.resumos}


def secao_documentos(antes: dict[str, Documento], depois: dict[str, Documento], idiomas: tuple[str, str]) -> list[str]:
    linhas = ["## Documentos", ""]
    saiu, entrou = sorted(set(antes) - set(depois)), sorted(set(depois) - set(antes))
    linhas.append(f"{len(antes)} → {len(depois)} documentos; saíram {len(saiu)}, entraram {len(entrou)}.")
    linhas += [f"- saiu: {i} ({_titulo(antes[i])})" for i in saiu] + [f"- entrou: {i}" for i in entrou]
    tirados, trocados = [], []
    for i in sorted(set(antes) & set(depois)):
        a, d = _resumos(antes[i]), _resumos(depois[i])
        tirados += [f"- {i} ({a[k]}): {k.split(':', 1)[1]}" for k in a if k not in d]
        trocados += [f"- {i}: {a[k]} → {d[k]}" for k in a if k in d and a[k] != d[k]]
    linhas += ["", f"### Resumos que saíram ({len(tirados)})", "", *tirados]
    linhas += ["", f"### Resumos que mudaram de idioma ({len(trocados)})", "", *trocados]
    comuns = sorted(set(antes) & set(depois))
    analise = [i for i in comuns if _analise(antes[i], idiomas[1]) != _analise(depois[i], idiomas[1])]
    classes_a = {t.doc: t for t in textos_para_classificar([antes[i] for i in comuns], list(idiomas))[0]}
    classes_d = {t.doc: t for t in textos_para_classificar([depois[i] for i in comuns], list(idiomas))[0]}
    classificar = [i for i in comuns if classes_a.get(i) != classes_d.get(i)]
    linhas += ["", f"### Texto de análise mudou ({len(analise)})", "", ", ".join(analise) or "—"]
    linhas += ["", f"### Texto a classificar mudou ({len(classificar)})", "", ", ".join(classificar) or "—"]
    return linhas


def _titulo(doc: Documento) -> str:
    return doc.titulos[0].texto[:70] if doc.titulos else "sem título"


def _analise(doc: Documento, idioma: str) -> tuple[str, str] | None:
    t = texto_de_analise(doc, idioma)
    return (t.texto, t.fonte) if t else None


def secao_geografia(antes: Path, depois: Path) -> list[str]:
    pa, pd = antes / "dados" / "geografia", depois / "dados" / "geografia"
    if not (pa / "pesos.parquet").exists() or not (pd / "pesos.parquet").exists():
        return ["## Geografia", "", "Uma das rodadas não tem a geografia."]
    totais: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for k, pasta in enumerate((pa, pd)):
        for p in ler_tabela(pasta / "pesos.parquet"):
            if p["pais"] == "BR":
                totais[p["uf"] or "sem UF"][k] += p["peso"]
    linhas = ["## Geografia", "", "| UF | antes | depois | diferença |", "|---|---|---|---|"]
    for uf, (a, d) in sorted(totais.items(), key=lambda kv: -abs(kv[1][1] - kv[1][0])):
        if abs(d - a) >= 0.05:
            linhas.append(f"| {uf} | {a:.1f} | {d:.1f} | {d - a:+.1f} |")

    def por_chave(pasta: Path) -> dict[tuple, dict[str, Any]]:
        """Os vínculos pela origem (documento, autor, afiliação, fonte e texto), com a ordem entre os repetidos."""
        saida: dict[tuple, dict[str, Any]] = {}
        vistos: Counter[tuple] = Counter()
        for v in ler_tabela(pasta / "vinculos.parquet"):
            base = (v["doc"], v["autor"], v["afiliacao"], v["fonte"], v["texto"])
            saida[(*base, vistos[base])] = v
            vistos[base] += 1
        return saida

    va, vd = por_chave(pa), por_chave(pd)
    mudaram = [(va[k], v) for k, v in vd.items() if k in va and va[k]["uf"] != v["uf"]]
    linhas += ["", f"### Vínculos que mudaram de UF ({len(mudaram)})", ""]
    linhas += [f"- {d['doc']}: {a['uf']} → {d['uf']} ({d['instituicao']}; {d['texto'][:60]})" for a, d in mudaram]
    return linhas


def _topicos(projeto: Path) -> tuple[dict[int, dict], dict[int, set[str]]]:
    resultado = json.loads((projeto / "dados" / "topicos" / "resultado.json").read_text(encoding="utf-8"))
    nucleos: dict[int, set[str]] = defaultdict(set)
    for linha in ler_tabela(projeto / "dados" / "topicos" / "atribuicoes.parquet"):
        if linha["atribuicao"] == "cluster":
            nucleos[linha["topico"]].add(linha["id"])
    return {t["id"]: t for t in resultado["topicos"]}, nucleos


def _palavras(topico: dict) -> str:
    return ", ".join(p[0] if isinstance(p, list) else p for p in topico["palavras"][:10])  # (termo, peso)


def secao_topicos(antes: Path, depois: Path, rotulos: Path | None, docs: dict[str, Documento]) -> list[str]:
    ta, na = _topicos(antes)
    td, nd = _topicos(depois)
    manuais = {}
    if rotulos and rotulos.exists():
        manuais = (yaml.safe_load(rotulos.read_text(encoding="utf-8")) or {}).get("topicos") or {}
    linhas = ["## Tópicos", "", f"{len(ta)} → {len(td)} tópicos.", ""]
    rever = 0
    for tid in sorted(td):
        t, velho = td[tid], ta.get(tid)
        j = jaccard(na.get(tid, set()), nd[tid]) if velho else 0.0
        marca = "rever" if j < JACCARD_MINIMO else "ok"
        rever += marca == "rever"
        linhas.append(f"### {tid} [{marca}] Jaccard {j:.2f}, núcleo {len(na.get(tid, ()))} → {len(nd[tid])}")
        linhas.append("")
        if velho:
            linhas.append(f"- antes ({velho['rotulo_fonte']}): {velho['rotulo']}")
            linhas.append(f"- palavras antes: {_palavras(velho)}")
        linhas.append(f"- agora ({t['rotulo_fonte']}): {t['rotulo']}")
        linhas.append(f"- palavras agora: {_palavras(t)}")
        if tid in manuais:
            linhas.append(f"- rotulos.yaml: {manuais[tid].get('rotulo')}")
        titulos = [_titulo(docs[i]) for i in t["representativos"][:5] if i in docs]
        linhas += [f"    - {x}" for x in titulos]
        linhas.append("")
    orfaos = sorted(set(manuais) - set(td))
    linhas.append(f"{rever} tópico(s) para rever; entradas do rotulos.yaml sem tópico: {orfaos or 'nenhuma'}.")
    siglas = [f"- {tid}: {t['rotulo']}" for tid, t in sorted(td.items()) if _SIGLAS.search(t["rotulo"])]
    linhas += ["", "### Rótulos com siglas a uniformizar", "", *(siglas or ["—"])]
    return linhas


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("antes", type=Path)
    parser.add_argument("depois", type=Path)
    parser.add_argument("--rotulos", type=Path, help="o rotulos.yaml a conferir (padrão: o do projeto `antes`)")
    args = parser.parse_args()
    cfg = carregar_config(args.depois / "mapa.yaml")
    idiomas = (cfg.recorte.idioma_exibicao, cfg.recorte.idioma_analise)
    antes = {d.id: d for d in ler_documentos(args.antes / "dados" / ARQUIVO)}
    depois = {d.id: d for d in ler_documentos(args.depois / "dados" / ARQUIVO)}
    linhas = [f"# {args.antes.name} → {args.depois.name}", ""]
    linhas += [*secao_documentos(antes, depois, idiomas), "", *secao_geografia(args.antes, args.depois), ""]
    if (args.depois / "dados" / "topicos" / "resultado.json").exists():
        linhas += secao_topicos(args.antes, args.depois, args.rotulos or args.antes / "rotulos.yaml", depois)
    print("\n".join(linhas))


if __name__ == "__main__":
    main()
