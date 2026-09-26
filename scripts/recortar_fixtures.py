"""Recorta respostas reais do cache do spike (spikes/saida/brutos/) em fixtures pequenas para os testes.

Só funciona onde o cache do spike existe (a máquina de desenvolvimento). O resultado,
em tests/fixtures/, é versionado. Todo e-mail real é trocado por `anonimo@exemplo.invalid`:
os testes provam que a normalização descarta até esse endereço falso.

Uso (da raiz do repo):
    uv run python scripts/recortar_fixtures.py
"""

from __future__ import annotations

import gzip
import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CACHE = RAIZ / "spikes" / "saida" / "brutos"
DESTINO = RAIZ / "tests" / "fixtures"
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
FALSO = "anonimo@exemplo.invalid"

# Casos especiais, escolhidos no corpus do spike (ver ADR 0003 e o plano do M2)
ESPECIAIS = {
    "S0011-52582014000200007": "DOI repetido na ArticleMeta (par com ...008)",
    "S0011-52582014000200008": "DOI repetido na ArticleMeta (par com ...007)",
    "S0011-52582025000400225": "duplicata real na ArticleMeta (par com ...230)",
    "S0011-52582025000400230": "duplicata real na ArticleMeta (par com ...225)",
    "S0102-64452025000200303": "duplicata real na ArticleMeta (par com ...312)",
    "S0102-64452025000200312": "duplicata real na ArticleMeta (par com ...303)",
    "S0102-64452011000300001": "título genérico 'Apresentação' (não é duplicata)",
    "S0103-33522011000100001": "título genérico 'Apresentação' (não é duplicata)",
}


def ler(caminho: Path):
    with gzip.open(caminho, "rt", encoding="utf-8") as f:
        return json.load(f)


def anonimizar(valor):
    texto = json.dumps(valor, ensure_ascii=False)
    return json.loads(EMAIL.sub(FALSO, texto))


def enxugar(registro: dict) -> dict:
    """Tira o que os testes não usam: referências (90% do registro) e a maior parte do registro da revista."""
    r = dict(registro)
    r["citations"] = (r.get("citations") or [])[:2]
    titulo = r.get("title") or {}
    r["title"] = {k: titulo[k] for k in ("v68", "v100", "v400", "v435", "v541", "v64") if k in titulo}
    return anonimizar(r)


def escolher_casos(artigos: Path) -> dict[str, str]:
    """Acrescenta casos encontrados por varredura: só v70, entidades HTML, resenha."""
    casos = dict(ESPECIAIS)
    precisa = {"so_v70": None, "html": None, "resenha": None}
    for arq in sorted(artigos.glob("S0104-4478201*.json.gz")):  # Rev. Sociologia e Política
        d = ler(arq)
        a = d.get("article", {})
        pid = arq.name.removesuffix(".json.gz")
        if (
            precisa["so_v70"] is None
            and a.get("v70")
            and not a.get("v240")
            and d.get("document_type") == "research-article"
        ):
            precisa["so_v70"] = pid
        if precisa["html"] is None and any("&amp;" in (x.get("a") or "") for x in a.get("v83") or []):
            precisa["html"] = pid
        if precisa["resenha"] is None and d.get("document_type") == "book-review":
            precisa["resenha"] = pid
    if precisa["resenha"] is None:  # nenhuma resenha nessa revista: procura em todo o cache
        for arq in sorted(artigos.glob("*.json.gz")):
            if ler(arq).get("document_type") == "book-review":
                precisa["resenha"] = arq.name.removesuffix(".json.gz")
                break
    for motivo, pid in precisa.items():
        if pid:
            casos[pid] = motivo
    # um artigo por passo da cascata de casamento (e um sem casamento), a partir do corpus do spike
    corpus = [json.loads(linha) for linha in (CACHE.parent / "corpus.jsonl").open(encoding="utf-8")]
    for passo in ("2_pid_url", "3_doi_derivado", "4_titulo_ano", "sem_casamento"):
        achado = next(
            (d for d in corpus if d["casamento"] == passo and d["tipo"] == "research-article" and d["resumos"]), None
        )
        if achado:
            casos[achado["pid"]] = f"casamento {passo}"
    return casos


def recortar_openalex(casos: dict[str, str], pids_op: list[str]) -> None:
    """Busca no OpenAlex (1 crédito por revista-ano) só as páginas que os testes usam, e guarda as obras."""
    import sys

    sys.path.insert(0, str(RAIZ / "src"))
    from mapa_da_ciencia import rede
    from mapa_da_ciencia.fontes import revistas
    from mapa_da_ciencia.fontes.openalex import CAMPOS

    corpus = {json.loads(linha)["pid"]: json.loads(linha) for linha in (CACHE.parent / "corpus.jsonl").open()}
    pares = {("0104-6276", 2024)} | {(pid[1:10], int(pid[10:14])) for pid in casos}
    obras = {}
    with rede.cliente(timeout=60) as http:
        for issn, ano in sorted(pares):
            issns = "|".join(sorted(set(revistas.por_issn(issn).issns)))
            filtro = f"primary_location.source.issn:{issns},publication_year:{ano}-{ano}"
            r = http.get("https://api.openalex.org/works", params={"filter": filtro, "select": CAMPOS, "per-page": 200})
            r.raise_for_status()
            resultados = r.json()["results"]
            alvo = {corpus[p]["openalex_id"] for p in casos if p[1:10] == issn and corpus.get(p, {}).get("openalex_id")}
            for o in resultados:
                if (issn == "0104-6276" and ano == 2024) or o["id"] in alvo:
                    obras[o["id"]] = anonimizar(o)
            for o in [o for o in resultados if o["id"] not in alvo][:3]:  # distratores
                obras.setdefault(o["id"], anonimizar(o))
    with gzip.open(DESTINO / "openalex" / "obras.jsonl.gz", "wt", encoding="utf-8") as f:
        for oid in sorted(obras):
            f.write(json.dumps(obras[oid], ensure_ascii=False) + "\n")
    print(f"{len(obras)} obras do OpenAlex ({len(pares)} revistas-ano, {len(pares)} créditos)")


def main() -> None:
    artigos = CACHE / "articlemeta" / "artigos"
    assert artigos.exists(), "cache do spike não encontrado: rode spikes/s01_fontes.py antes"
    saida = DESTINO / "articlemeta"
    saida.mkdir(parents=True, exist_ok=True)

    # Opinião Pública: lista de identificadores reduzida a 2024 (25) + alguns de outros anos
    ids = ler(CACHE / "articlemeta" / "identificadores" / "op-0.json.gz")
    objetos = ids["objects"]
    de_2024 = [o for o in objetos if o["code"][10:14] == "2024"]
    outros = [o for o in objetos if o["code"][10:14] in ("2010", "2023")][:15]
    lista = sorted(de_2024 + outros, key=lambda o: o["code"])
    (saida / "identificadores-op.json").write_text(
        json.dumps({"meta": {**ids["meta"], "total": len(lista)}, "objects": lista}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )

    casos = escolher_casos(artigos)
    registros = {o["code"]: enxugar(ler(artigos / f"{o['code']}.json.gz")) for o in de_2024}
    for pid in casos:
        registros[pid] = enxugar(ler(artigos / f"{pid}.json.gz"))
    with gzip.open(saida / "artigos.jsonl.gz", "wt", encoding="utf-8") as f:
        for pid in sorted(registros):
            f.write(json.dumps({"pid": pid, "registro": registros[pid]}, ensure_ascii=False) + "\n")
    (saida / "casos.json").write_text(json.dumps(casos, ensure_ascii=False, indent=1), encoding="utf-8")
    (DESTINO / "openalex").mkdir(parents=True, exist_ok=True)
    recortar_openalex(casos, [o["code"] for o in de_2024])
    tamanho = sum(p.stat().st_size for p in saida.iterdir())
    print(
        f"{len(lista)} identificadores, {len(registros)} registros ({len(casos)} casos especiais), {tamanho // 1024} KB"
    )
    print(json.dumps(casos, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
