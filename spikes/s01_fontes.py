# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.28", "truststore>=0.10"]
# ///
"""Spike M0c + M0e: cobertura das fontes, casamento ArticleMeta↔OpenAlex e licenças.

Perguntas:
- Quantos artigos cada revista do piloto tem em 2010–2025, de que tipos, com
  quais idiomas de resumo, com DOI e com afiliação normalizada (v240)?
- Quanto a cascata DOI → PID na URL → DOI derivado do PID → título+ano recupera
  ao casar cada PID da ArticleMeta com um trabalho do OpenAlex?
- Onde está a licença de cada artigo e qual é a distribuição?

Uso (da raiz do repo):
    uv run spikes/s01_fontes.py                 # as 10 revistas do piloto
    uv run spikes/s01_fontes.py --revistas op   # só a Opinião Pública

As respostas brutas ficam em cache em spikes/saida/brutos/, então rodar de novo
não refaz requisições. Gera spikes/saida/s01_fontes.json (resumo) e
spikes/saida/corpus.jsonl (um documento por linha, sem e-mails), usado pelos
spikes de embeddings e de LLM.
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import gzip
import json
import re
import ssl
import sys
import unicodedata
from pathlib import Path

import httpx
import truststore

RAIZ = Path(__file__).resolve().parent / "saida"
BRUTOS = RAIZ / "brutos"
AM = "https://articlemeta.scielo.org/api/v1"
OA = "https://api.openalex.org"
ANOS = range(2010, 2026)

# acrônimo: (ISSN SciELO, ISSN online, nome curto)
REVISTAS = {
    "rbcpol": ("0103-3352", "2178-4884", "RBCP"),
    "dados": ("0011-5258", "1678-4588", "Dados"),
    "op": ("0104-6276", "1807-0191", "Opinião Pública"),
    "ln": ("0102-6445", "1807-0175", "Lua Nova"),
    "rsocp": ("0104-4478", "1678-9873", "Rev. Sociologia e Política"),
    "bpsr": ("1981-3821", "1981-3821", "BPSR"),
    "cint": ("0102-8529", "1982-0240", "Contexto Internacional"),
    "rbpi": ("0034-7329", "1983-3121", "RBPI"),
    "nec": ("0101-3300", "1980-5403", "Novos Estudos CEBRAP"),
    "rbcsoc": ("0102-6909", "1806-9053", "RBCS"),
}

PID_NA_URL = re.compile(r"pid=(S\d{4}-\d{3}[\dX]\d{13})", re.I)


def cliente() -> httpx.AsyncClient:
    # truststore: usa os certificados do sistema operacional (redes com proxy/CA própria)
    ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    return httpx.AsyncClient(
        verify=ctx,
        timeout=httpx.Timeout(60.0),
        headers={"User-Agent": "mapa-da-ciencia-spike/0.0 (+https://github.com/felipelmc)"},
        follow_redirects=True,
    )


async def obter_json(cli: httpx.AsyncClient, url: str, params: dict, cache: Path) -> dict | list:
    """GET com cache em disco (json.gz) e backoff exponencial."""
    if cache.exists():
        with gzip.open(cache, "rt", encoding="utf-8") as f:
            return json.load(f)
    espera = 1.0
    for tentativa in range(6):
        try:
            r = await cli.get(url, params=params)
            if r.status_code in (429, 500, 502, 503, 504):
                raise httpx.HTTPStatusError(f"status {r.status_code}", request=r.request, response=r)
            r.raise_for_status()
            dados = r.json()
            cache.parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(cache, "wt", encoding="utf-8") as f:
                json.dump(dados, f, ensure_ascii=False)
            return dados
        except (httpx.HTTPError, json.JSONDecodeError) as e:
            if tentativa == 5:
                raise RuntimeError(f"falhou após 6 tentativas: {url} {params}: {e}") from e
            await asyncio.sleep(espera)
            espera *= 2
    raise AssertionError("inalcançável")


def normalizar_titulo(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", t)).strip()


def normalizar_doi(d: str | None) -> str | None:
    if not d:
        return None
    d = d.strip().lower()
    d = re.sub(r"^https?://(dx\.)?doi\.org/", "", d)
    return d or None


async def listar_pids(cli, acron: str, issn: str) -> list[dict]:
    objetos, offset = [], 0
    while True:
        dados = await obter_json(
            cli,
            f"{AM}/article/identifiers/",
            {"collection": "scl", "issn": issn, "limit": 1000, "offset": offset},
            BRUTOS / "articlemeta" / "identificadores" / f"{acron}-{offset}.json.gz",
        )
        objetos += dados["objects"]
        offset += 1000
        if offset >= dados["meta"]["total"]:
            break
    vistos, unicos = set(), []
    for o in objetos:  # a listagem pode repetir PIDs reprocessados
        if o["code"] not in vistos:
            vistos.add(o["code"])
            unicos.append(o)
    return [o for o in unicos if o["code"][10:14].isdigit() and int(o["code"][10:14]) in ANOS]


async def buscar_artigos(cli, pids: list[str]) -> dict[str, dict]:
    sem = asyncio.Semaphore(4)
    feitos = 0

    async def um(pid: str):
        nonlocal feitos
        async with sem:
            d = await obter_json(
                cli,
                f"{AM}/article/",
                {"collection": "scl", "code": pid, "format": "json"},
                BRUTOS / "articlemeta" / "artigos" / f"{pid}.json.gz",
            )
        feitos += 1
        if feitos % 250 == 0:
            print(f"    {feitos}/{len(pids)} registros", file=sys.stderr)
        return pid, d

    return dict(await asyncio.gather(*(um(p) for p in pids)))


async def listar_openalex(cli, acron: str, issns: tuple[str, str]) -> list[dict]:
    filtro = f"primary_location.source.issn:{'|'.join(sorted(set(issns)))},publication_year:2010-2025"
    campos = "id,doi,title,publication_year,language,type,primary_location,locations,abstract_inverted_index"
    trabalhos, cursor, pagina = [], "*", 0
    while cursor:
        dados = await obter_json(
            cli,
            f"{OA}/works",
            {"filter": filtro, "select": campos, "per-page": 200, "cursor": cursor},
            BRUTOS / "openalex" / f"{acron}-{pagina}.json.gz",
        )
        trabalhos += dados["results"]
        cursor = dados["meta"].get("next_cursor") if dados["results"] else None
        pagina += 1
    return trabalhos


def extrair(d: dict) -> dict:
    """Campos normalizados de um registro ArticleMeta, sem e-mails."""
    a = d.get("article", {})
    titulos = {t.get("l"): t.get("_", "") for t in a.get("v12", []) if t.get("_")}
    resumos = {}
    for r in a.get("v83", []):
        texto = re.sub(r"^\s*(resumo|abstract|resumen)\s*[:.\-–]?\s*", "", r.get("a", ""), flags=re.I).strip()
        if texto and r.get("l"):
            resumos[r["l"]] = texto
    doi = normalizar_doi(d.get("doi")) or normalizar_doi(next((x.get("_") for x in a.get("v237", [])), None))
    return {
        "tipo": d.get("document_type"),
        "ano_publicacao": d.get("publication_year"),
        "titulos": titulos,
        "resumos": resumos,
        "palavras_chave": [(k.get("l"), k.get("k")) for k in a.get("v85", []) if k.get("k")],
        "doi": doi,
        "n_v240": len(a.get("v240", []) or []),
        "n_v70": len(a.get("v70", []) or []),
        "ufs_v240": sorted({x.get("s") for x in a.get("v240", []) or [] if x.get("s")}),
        "paises_v240": sorted({x.get("p") for x in a.get("v240", []) or [] if x.get("p")}),
    }


def casar(pid: str, doc: dict, indice: dict) -> tuple[str | None, str]:
    if doc["doi"] and doc["doi"] in indice["doi"]:
        return indice["doi"][doc["doi"]], "1_doi"
    if pid in indice["pid"]:
        return indice["pid"][pid], "2_pid_url"
    derivado = f"10.1590/{pid.lower()}"
    if derivado in indice["doi"]:
        return indice["doi"][derivado], "3_doi_derivado"
    ano = int(pid[10:14])
    for t in doc["titulos"].values():
        chave = (normalizar_titulo(t), ano)
        if chave[0] and chave in indice["titulo"]:
            return indice["titulo"][chave], "4_titulo_ano"
    return None, "sem_casamento"


def indexar(trabalhos: list[dict]) -> dict:
    ind = {"doi": {}, "pid": {}, "titulo": {}}
    for w in trabalhos:
        doi = normalizar_doi(w.get("doi"))
        if doi:
            ind["doi"][doi] = w["id"]
        for loc in w.get("locations") or []:
            m = PID_NA_URL.search(loc.get("landing_page_url") or "")
            if m:
                ind["pid"][m.group(1).upper()] = w["id"]
        if w.get("title") and w.get("publication_year"):
            ind["titulo"][(normalizar_titulo(w["title"]), w["publication_year"])] = w["id"]
    return ind


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--revistas", nargs="*", default=list(REVISTAS), choices=list(REVISTAS))
    args = ap.parse_args()

    resumo, linhas_corpus = {}, []
    async with cliente() as cli:
        for acron in args.revistas:
            issn, issn_online, nome = REVISTAS[acron]
            print(f"== {nome} ({acron})", file=sys.stderr)
            refs = await listar_pids(cli, acron, issn)
            pids = sorted(o["code"] for o in refs)
            print(f"   {len(pids)} PIDs em 2010–2025; buscando registros…", file=sys.stderr)
            registros = await buscar_artigos(cli, pids)
            revista = await obter_json(
                cli,
                f"{AM}/journal/",
                {"collection": "scl", "issn": issn},
                BRUTOS / "articlemeta" / "revistas" / f"{acron}.json.gz",
            )
            revista = revista[0] if isinstance(revista, list) else revista
            licenca_revista = [x.get("_") for x in revista.get("v541", [])]
            trabalhos = await listar_openalex(cli, acron, (issn, issn_online))
            indice = indexar(trabalhos)
            por_id = {w["id"]: w for w in trabalhos}

            c = collections.Counter()
            tipos, passos, idiomas, licencas = (collections.Counter() for _ in range(4))
            casados = set()
            for pid in pids:
                doc = extrair(registros[pid])
                tipos[doc["tipo"]] += 1
                c["pids"] += 1
                c["com_resumo"] += bool(doc["resumos"])
                for lang in doc["resumos"]:
                    idiomas[lang] += 1
                c["com_doi_articlemeta"] += bool(doc["doi"])
                c["com_v240"] += doc["n_v240"] > 0
                c["com_v70"] += doc["n_v70"] > 0
                c["ano_pid_difere_publicacao"] += str(doc["ano_publicacao"]) != pid[10:14]
                oa_id, passo = casar(pid, doc, indice)
                passos[passo] += 1
                w = por_id.get(oa_id) if oa_id else None
                if w:
                    casados.add(oa_id)
                    licencas[(w.get("primary_location") or {}).get("license") or "sem_licenca"] += 1
                    c["oa_com_resumo"] += bool(w.get("abstract_inverted_index"))
                linhas_corpus.append(
                    {
                        "pid": pid,
                        "revista": acron,
                        "ano": int(pid[10:14]),
                        **doc,
                        "openalex_id": oa_id,
                        "casamento": passo,
                        "idioma_openalex": w.get("language") if w else None,
                        "licenca": ((w or {}).get("primary_location") or {}).get("license"),
                        "licenca_revista": licenca_revista,
                    }
                )
            c["openalex_trabalhos"] = len(trabalhos)
            c["openalex_sem_pid"] = len(set(por_id) - casados)
            resumo[acron] = {
                "nome": nome,
                "contagens": dict(c),
                "tipos": dict(tipos),
                "casamento": dict(passos),
                "idiomas_resumo": dict(idiomas),
                "licencas_openalex": dict(licencas),
                "licenca_revista_v541": licenca_revista,
            }

    RAIZ.mkdir(parents=True, exist_ok=True)
    (RAIZ / "s01_fontes.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2))
    with open(RAIZ / "corpus.jsonl", "w", encoding="utf-8") as f:
        for linha in linhas_corpus:
            f.write(json.dumps(linha, ensure_ascii=False) + "\n")
    imprimir_tabelas(resumo)


def imprimir_tabelas(resumo: dict) -> None:
    tot = collections.Counter()
    tipos_tot, passos_tot, idiomas_tot, lic_tot = (collections.Counter() for _ in range(4))
    print("\n| Revista | PIDs | c/ resumo | DOI (AM) | v240 | casados | sem casar | OA sem PID | licença revista |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in resumo.values():
        c, p = r["contagens"], r["casamento"]
        casados = c["pids"] - p.get("sem_casamento", 0)
        print(
            f"| {r['nome']} | {c['pids']} | {c['com_resumo']} | {c['com_doi_articlemeta']} | {c['com_v240']} "
            f"| {casados} | {p.get('sem_casamento', 0)} | {c['openalex_sem_pid']} | {','.join(r['licenca_revista_v541'])} |"
        )
        tot.update(c)
        tipos_tot.update(r["tipos"])
        passos_tot.update(p)
        idiomas_tot.update(r["idiomas_resumo"])
        lic_tot.update(r["licencas_openalex"])
    n = tot["pids"]
    pct = lambda x: f"{x} ({100 * x / n:.1f}%)" if n else str(x)  # noqa: E731
    print(
        f"\n**Total:** {n} PIDs; com resumo {pct(tot['com_resumo'])}; DOI na ArticleMeta {pct(tot['com_doi_articlemeta'])}; "
        f"v240 {pct(tot['com_v240'])}; v70 {pct(tot['com_v70'])}; "
        f"ano do PID ≠ publication_year {pct(tot['ano_pid_difere_publicacao'])}"
    )
    print(
        f"**OpenAlex:** {tot['openalex_trabalhos']} trabalhos listados; {tot['openalex_sem_pid']} sem PID correspondente; "
        f"resumo no OpenAlex entre os casados: {tot['oa_com_resumo']}"
    )
    print("**Casamento por passo:**", dict(sorted(passos_tot.items())))
    print("**Tipos de documento:**", dict(tipos_tot.most_common()))
    print("**Idiomas de resumo:**", dict(idiomas_tot.most_common()))
    print("**Licenças (OpenAlex, casados):**", dict(lic_tot.most_common()))


if __name__ == "__main__":
    asyncio.run(main())
