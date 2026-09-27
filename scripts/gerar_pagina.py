"""Gera os dados da página de abertura do site (`docs/assets/pagina/dados.json`) a partir de um projeto.

A página "Céu que se forma" desenha os artigos do piloto como estrelas, que acendem ano a ano e se juntam em
constelações (os macrotemas), e conta algumas histórias do corpus com números e mini-gráficos. Tudo sai daqui, dos
arquivos do contrato do projeto (`saida/dados/`) e do corpus (`dados/documentos.parquet`, para o idioma original
dos artigos). O piloto não está no repositório: a página versiona só o resultado.

Uso (da raiz do repo):
    uv run python scripts/gerar_pagina.py projetos/cp-scielo
"""

from __future__ import annotations

import base64
import json
import math
import statistics
import struct
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DESTINO = RAIZ / "docs" / "assets" / "pagina" / "dados.json"
PERIODOS = ((2010, 2014), (2015, 2020), (2021, 2025))
QUANTOS = 65535


def _ler(pasta: Path, arquivo: str) -> dict:
    return json.loads((pasta / arquivo).read_text(encoding="utf-8"))


def _pct(parte: float, todo: float) -> int:
    return round(100 * parte / todo) if todo else 0


def _arvore(pontos: list[tuple[float, float]]) -> list[tuple[int, int]]:
    """Arestas da árvore geradora mínima (Prim) entre os pontos: as linhas de uma constelação."""
    if len(pontos) < 2:
        return []
    dentro, arestas = {0}, []
    while len(dentro) < len(pontos):
        i, j = min(
            ((a, b) for a in dentro for b in range(len(pontos)) if b not in dentro),
            key=lambda ab: math.dist(pontos[ab[0]], pontos[ab[1]]),
        )
        arestas.append((i, j))
        dentro.add(j)
    return arestas


def ceu(docs: dict, topicos: dict) -> dict:
    """As estrelas (uma por artigo, ordenadas por ano), as estrelas grandes (os tópicos) e as constelações."""
    c = docs["colunas"]
    xs, ys = c["x"], c["y"]
    x0, y0 = min(xs), min(ys)
    escala = max(max(xs) - x0, max(ys) - y0)
    norm = lambda x, y: ((x - x0) / escala, 1 - (y - y0) / escala)  # noqa: E731  (y para cima, como no painel)

    macros = sorted(topicos["macrotemas"], key=lambda m: m["id"])
    indice_macro = {m["id"]: i for i, m in enumerate(macros)}
    macro_do_topico = {t["id"]: indice_macro[t["macro_id"]] for t in topicos["topicos"]}

    ordem = sorted(range(docs["n"]), key=lambda i: (c["ano"][i], c["id"][i]))
    anos = topicos["anos"]
    bytes_ = bytearray()
    por_ano = Counter()
    for i in ordem:
        nx, ny = norm(xs[i], ys[i])
        m = macro_do_topico.get(c["topico"][i], -1) if c["topico"][i] >= 0 else -1
        bytes_ += struct.pack("<HHB", round(nx * QUANTOS), round(ny * QUANTOS), m + 1)
        por_ano[c["ano"][i]] += 1

    estrelas = []
    for t in sorted(topicos["topicos"], key=lambda t: t["id"]):
        nx, ny = norm(*t["centroide"])
        estrelas.append(
            {
                "id": t["id"],
                "macro": macro_do_topico[t["id"]],
                "x": round(nx, 4),
                "y": round(ny, 4),
                "n": t["n"],
                "rotulo": t["rotulo"],
                "palavras": [p[0] if isinstance(p, list) else p for p in t["palavras_chave"][:5]],
                "direcao": t["tendencia"]["direcao"],
            }
        )
    constelacoes = []
    for i, m in enumerate(macros):
        membros = [k for k, e in enumerate(estrelas) if e["macro"] == i]
        pontos = [(estrelas[k]["x"], estrelas[k]["y"]) for k in membros]
        pesos = [estrelas[k]["n"] for k in membros]
        cx = sum(p[0] * w for p, w in zip(pontos, pesos, strict=True)) / sum(pesos)
        cy = sum(p[1] * w for p, w in zip(pontos, pesos, strict=True)) / sum(pesos)
        constelacoes.append(
            {
                "id": m["id"],
                "rotulo": m["rotulo"],
                "cor": m["cor"],
                "x": round(cx, 4),
                "y": round(cy, 4),
                "linhas": [[membros[a], membros[b]] for a, b in _arvore(pontos)],
                "n": sum(pesos),
            }
        )
    return {
        "n": docs["n"],
        "anos": anos,
        "por_ano": [por_ano[a] for a in anos],
        "proporcao": round((max(ys) - y0) / escala, 4),
        "pontos": base64.b64encode(bytes(bytes_)).decode("ascii"),
        "estrelas": estrelas,
        "constelacoes": constelacoes,
    }


def _kappas(validacao: dict) -> list[dict]:
    principal = validacao["modelo_principal"].split("@", 1)[0]
    referencia = next((c["nome"] for c in validacao["codificadores"] if c["tipo"] == "referencia"), None)
    saida = []
    for m in validacao["metricas"]:
        if m.get("kappa") is None or m.get("referencia") != referencia or m.get("comparado") != principal:
            continue
        saida.append({"variavel": m["variavel"], "kappa": round(m["kappa"], 2), "ic95": m["kappa_ic95"]})
    return saida


def _ingles(parquet: Path, anos: list[int]) -> dict | None:
    """A parte dos artigos em inglês por ano, nas revistas de RI (Contexto Internacional e RBPI) e nas outras. Só
    vira história quando as duas passam a publicar tudo em inglês."""
    import duckdb

    if not parquet.exists():
        return None
    con = duckdb.connect()
    linhas = con.execute(
        f"""SELECT ano, revista_acronimo IN ('cint', 'rbpi') AS ri, avg((idioma_original = 'en')::INT) AS en
            FROM '{parquet}' GROUP BY 1, 2"""
    ).fetchall()
    por = {(a, ri): en for a, ri, en in linhas}
    ri = [round(100 * por.get((a, True), 0)) for a in anos]
    outras = [round(100 * por.get((a, False), 0)) for a in anos]
    desde = next((a for k, a in enumerate(anos) if ri[k] == 100 and all(x == 100 for x in ri[k:])), None)
    if desde is None:
        return None
    antes = con.execute(
        f"""SELECT avg((idioma_original = 'en')::INT) FROM '{parquet}'
            WHERE revista_acronimo IN ('cint', 'rbpi') AND ano < {desde}"""
    ).fetchone()[0]
    return {"desde": desde, "pct_antes": round(100 * (antes or 0)), "ri": ri, "outras": outras}


def historias(pasta: Path, docs: dict, topicos: dict, agregados: dict, validacao: dict, codebook: dict) -> dict:
    anos = topicos["anos"]
    rotulo_var = {v["id"]: v["rotulo"] for v in codebook["variaveis"]}
    rotulo_cat = {
        (v["id"], c["valor"]): c.get("rotulo") or c["valor"]
        for v in codebook["variaveis"]
        for c in v.get("categorias", [])
    }
    saida: dict = {}

    # 1. o tópico que mais cresceu
    em_alta = [t for t in topicos["topicos"] if (t.get("tendencia") or {}).get("direcao") == "alta"]
    alta = max(em_alta, key=lambda t: t["tendencia"]["pp_periodo"]) if em_alta else None
    saida["alta"] = alta and {
        "topico": alta["id"],
        "rotulo": alta["rotulo"],
        "pp_periodo": round(alta["tendencia"]["pp_periodo"], 1),
        "pp_por_ano": round(alta["tendencia"]["pp_por_ano"], 2),
        "serie": [round(100 * p, 2) for p in alta["serie"]["prop"]],
        "em_alta": len(em_alta),
        "em_queda": sum((t.get("tendencia") or {}).get("direcao") == "queda" for t in topicos["topicos"]),
        "topicos": len(topicos["topicos"]),
    }

    # 2. o tópico mais recente: a maior parte dos artigos depois de 2018 (entre os com ao menos 40)
    corte = anos.index(2018) if 2018 in anos else len(anos) // 2
    grandes = [t for t in topicos["topicos"] if t["n"] >= 40]
    parte_recente = lambda t: sum(t["serie"]["n"][corte:]) / max(1, sum(t["serie"]["n"]))  # noqa: E731
    recente = max(grandes, key=parte_recente) if grandes else None
    saida["recente"] = recente and {
        "topico": recente["id"],
        "rotulo": recente["rotulo"],
        "desde": anos[corte],
        "depois": sum(recente["serie"]["n"][corte:]),
        "total": sum(recente["serie"]["n"]),
        "serie": recente["serie"]["n"],
    }

    # 3. a concentração geográfica no Brasil
    uf = agregados.get("uf") or {}
    total_br = sum(uf.values())
    tres = sorted(uf, key=lambda k: -uf[k])[:3]
    saida["geografia"] = total_br and {
        "tres": tres,
        "pct_tres": _pct(sum(uf[k] for k in tres), total_br),
        "uf": {k: round(v / total_br, 4) for k, v in sorted(uf.items())},
        "pct_brasil": _pct(agregados["pais"].get("BR", 0), sum(agregados["pais"].values())),
    }

    # 4. o inglês nas revistas de relações internacionais (idioma original, do corpus)
    saida["ingles"] = _ingles(pasta / "dados" / "documentos.parquet", anos)

    # 5. como se pesquisa: a abordagem por período, entre os classificados
    c, dic = docs["colunas"], docs["dicionarios"]
    if "abordagem" in c.get("cls", {}):
        cats = dic["cls"]["abordagem"]
        cont = [Counter() for _ in PERIODOS]
        for ano, i in zip(c["ano"], c["cls"]["abordagem"], strict=True):
            if i < 0 or cats[i] == "nao_informado":
                continue
            p = next(k for k, (a, b) in enumerate(PERIODOS) if a <= ano <= b)
            cont[p][cats[i]] += 1
        principais = [k for k in cats if k not in ("nao_informado", "revisao")]
        partes = [{k: _pct(cc[k], sum(cc.values())) for k in principais} for cc in cont]
        mudou = max(principais, key=lambda k: abs(partes[-1][k] - partes[0][k]))
        saida["abordagem"] = {
            "categorias": [{"valor": k, "rotulo": rotulo_cat.get(("abordagem", k), k)} for k in principais],
            "periodos": [f"{a}–{b}" for a, b in PERIODOS],
            "partes": partes,
            "n": [sum(cc.values()) for cc in cont],
            "destaque": {
                "valor": mudou,
                "rotulo": rotulo_cat.get(("abordagem", mudou), mudou),
                "de": partes[0][mudou],
                "para": partes[-1][mudou],
            },
        }

    # 6. o modelo contra a leitura de referência
    kappas = _kappas(validacao)
    for k in kappas:
        k["rotulo"] = rotulo_var.get(k["variavel"], k["variavel"])
    saida["validacao"] = {
        "n": validacao["amostra"]["n"],
        "kappas": kappas,
        "mediana": round(statistics.median(k["kappa"] for k in kappas), 2) if kappas else None,
        "referencia": next((c["nome"] for c in validacao["codificadores"] if c["tipo"] == "referencia"), None),
        "modelo": validacao["modelo_principal"].split("@", 1)[0],
    }
    return saida


def numeros(manifesto: dict, revistas: dict, topicos: dict, agregados: dict, classificacoes: dict, hist: dict) -> dict:
    especiais = {"nao-identificada", "sem-afiliacao"}
    anos = manifesto["recorte"]["anos"]
    return {
        "artigos": manifesto["contagens"]["documentos"],
        "revistas": len(revistas["revistas"]),
        "anos": anos[1] - anos[0] + 1,
        "periodo": anos,
        "topicos": len(topicos["topicos"]),
        "macrotemas": len(topicos["macrotemas"]),
        "instituicoes": sum(1 for k, v in agregados["instituicao"].items() if k not in especiais and v > 0),
        "classificados": classificacoes.get("classificados"),
        "com_resumo": classificacoes.get("documentos"),
        "evidencia_literal": (
            round(100 * classificacoes["evidencia_literal"], 1) if classificacoes.get("evidencia_literal") else None
        ),
        "kappa_mediano": hist["validacao"]["mediana"],
        "ari": round(topicos["estabilidade_ari"], 2) if topicos.get("estabilidade_ari") is not None else None,
    }


def gerar(projeto: Path) -> dict:
    pasta = projeto / "saida" / "dados"
    docs, topicos = _ler(pasta, "documentos.json"), _ler(pasta, "topicos.json")
    agregados, validacao = _ler(pasta, "agregados.json"), _ler(pasta, "validacao.json")
    manifesto, revistas = _ler(pasta, "manifesto.json"), _ler(pasta, "revistas.json")
    classificacoes, codebook = _ler(pasta, "classificacoes.json"), _ler(pasta, "codebook.json")
    hist = historias(projeto, docs, topicos, agregados, validacao, codebook)
    return {
        "gerado_de": manifesto["projeto"]["titulo"],
        "versao_pacote": manifesto["execucao"]["versao_pacote"],
        "modelos": manifesto["execucao"].get("modelos", {}),
        "numeros": numeros(manifesto, revistas, topicos, agregados, classificacoes, hist),
        "historias": hist,
        "ceu": ceu(docs, topicos),
    }


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("Uso: uv run python scripts/gerar_pagina.py PASTA_DO_PROJETO")
    dados = gerar(Path(sys.argv[1]))
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"{DESTINO.relative_to(RAIZ)}: {DESTINO.stat().st_size / 1024:.0f} KB, {dados['ceu']['n']} estrelas.")


if __name__ == "__main__":
    main()
