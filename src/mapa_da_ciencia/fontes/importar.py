"""Leitura de listas de artigos: exportações do search.scielo.org (RIS, CSV, BibTeX) e listas de DOIs/PIDs.

Os leitores só extraem **identificadores** (PID do SciELO com a coleção, DOI) e, quando há,
título e ano. Os metadados completos vêm depois, da ArticleMeta ou do OpenAlex ("hidratação"),
com as mesmas regras e o mesmo cache da coleta por revista.

Detalhes das exportações do SciELO (conferidos em 2026-09-26):
- o `ID` traz o PID com a coleção no sufixo (`S0101-28002026000202001-scl`) ou `preprint_NNNN`;
- o CSV tem cabeçalho com espaço sobrando (`Fulltext URL `), linhas com espaço antes ou depois das
  aspas e não traz o DOI (o dos preprints é derivado do id: `preprint_17844` → `10.1590/scielopreprints.17844`);
- a exportação "todos os registros" vai até 2.000 itens.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from pathlib import Path

from mapa_da_ciencia.config import ErroConfig
from mapa_da_ciencia.texto import normalizar_doi, normalizar_titulo

PID = re.compile(r"(S\d{4}-\d{3}[\dX]\d{13})(?:-([a-z]{3})\b)?", re.IGNORECASE)
_DOMINIO_COLECAO = {
    "scielo.br": "scl",
    "scielo.org.ar": "arg",
    "scielo.org.co": "col",
    "scielo.cl": "chl",
    "scielo.sld.cu": "cub",
    "scielo.org.mx": "mex",
    "scielo.pt": "prt",
    "scielo.isciii.es": "esp",
    "scielo.org.pe": "per",
    "scielo.edu.uy": "ury",
    "scielo.org.ve": "ven",
    "scielo.sa.cr": "cri",
    "scielo.org.bo": "bol",
    "scielo.senescyt.gob.ec": "ecu",
    "scielo.iics.una.py": "pry",
    "scielo.org.za": "sza",
    "pepsic.bvsalud.org": "psi",
    "scielosp.org": "spa",
}
FORMATOS = {".ris": "ris", ".csv": "csv", ".bib": "bibtex", ".bibtex": "bibtex", ".txt": "txt"}


@dataclass(frozen=True)
class Identificador:
    """Um artigo da lista, como o arquivo o descreve."""

    pid: str | None
    colecao: str | None
    doi: str | None
    titulo: str | None = None
    ano: int | None = None
    origem: str = ""


@dataclass
class Importacao:
    arquivo: str
    formato: str
    itens: list[Identificador] = field(default_factory=list)
    ignorados: list[str] = field(default_factory=list)

    @property
    def com_pid(self) -> int:
        return sum(1 for i in self.itens if i.pid)

    @property
    def so_doi(self) -> int:
        return sum(1 for i in self.itens if not i.pid and i.doi)

    def resumo(self) -> str:
        return (
            f"{self.arquivo}: {len(self.itens) + len(self.ignorados)} registro(s): {self.com_pid} com PID, "
            f"{self.so_doi} só com DOI, {len(self.ignorados)} sem identificador"
        )


def colecao_da_url(url: str | None) -> str | None:
    """Código da coleção do SciELO a partir do domínio de um link (`scielo.org.ar` → `arg`)."""
    if not url:
        return None
    return next((c for dominio, c in _DOMINIO_COLECAO.items() if dominio in url), None)


def _identificar(textos_id: list[str], url: str | None, doi: str | None, titulo: str | None, ano: str | None,
                 origem: str) -> Identificador | None:  # fmt: skip
    pid = colecao = None
    for texto in [*textos_id, url or ""]:
        if m := PID.search(texto or ""):
            pid, colecao = m.group(1).upper(), (m.group(2) or "").lower() or None
            break
    colecao = colecao or colecao_da_url(url) or ("scl" if pid else None)
    doi = normalizar_doi(doi)
    if not doi and (m := re.search(r"preprint_(\d+)", " ".join(textos_id))):  # SciELO Preprints: DOI previsível
        doi = f"10.1590/scielopreprints.{m.group(1)}"
    if not pid and doi and (m := PID.search(doi.upper())):  # DOIs antigos do SciELO: 10.1590/S{PID}
        pid, colecao = m.group(1), "scl"
    if not pid and not doi:
        return None
    ano_int = int(ano) if ano and ano.strip()[:4].isdigit() else None
    return Identificador(pid, colecao, doi, (titulo or "").strip() or None, ano_int, origem)


# ---------------------------------------------------------------- formatos
def ler_ris(texto: str, nome: str = "arquivo.ris") -> Importacao:
    imp = Importacao(nome, "ris")
    for n, bloco in enumerate(re.split(r"^ER  -.*$", texto, flags=re.MULTILINE), start=1):
        campos: dict[str, list[str]] = {}
        for linha in bloco.splitlines():
            if m := re.match(r"^([A-Z][A-Z0-9])  - ?(.*)$", linha):
                campos.setdefault(m.group(1), []).append(m.group(2).strip())
        if not campos:
            continue
        ident = _identificar(
            campos.get("ID", []),
            next(iter(campos.get("UR", [])), None),
            next((d for d in campos.get("DO", []) if d), None),
            next(iter(campos.get("TI", [])), None),
            next(iter(campos.get("PY", [])), None),
            f"{nome}#{n}",
        )
        if ident:
            imp.itens.append(ident)
        else:
            imp.ignorados.append(f"registro {n}: {next(iter(campos.get('TI', [])), '(sem título)')}")
    return imp


_SINONIMOS = {
    "id": {"id", "pid", "codigo", "code"},
    "doi": {"doi"},
    "url": {"url", "link", "fulltexturl", "fulltext"},
    "titulo": {"titulo", "title", "ti"},
    "ano": {"ano", "year", "publicationyear", "py"},
}


def _coluna(cabecalho: list[str], papel: str) -> int | None:
    normalizados = [normalizar_titulo(c).replace(" ", "") for c in cabecalho]
    return next((i for i, c in enumerate(normalizados) if c in _SINONIMOS[papel]), None)


def ler_csv(texto: str, nome: str = "arquivo.csv") -> Importacao:
    imp = Importacao(nome, "csv")
    amostra = texto[:4096]
    try:
        dialeto = csv.Sniffer().sniff(amostra, delimiters=",;\t")
    except csv.Error:
        dialeto = csv.excel
    leitor = csv.reader(io.StringIO(texto), dialeto, skipinitialspace=True)
    linhas = [[c.strip().strip('"').strip() for c in linha] for linha in leitor if any(c.strip() for c in linha)]
    if not linhas:
        return imp
    cabecalho, dados = linhas[0], linhas[1:]
    col = {papel: _coluna(cabecalho, papel) for papel in _SINONIMOS}

    def celula(linha: list[str], papel: str) -> str | None:
        i = col[papel]
        return linha[i] if i is not None and i < len(linha) else None

    for n, linha in enumerate(dados, start=2):
        doi = celula(linha, "doi") or next((d for c in linha if (d := normalizar_doi(c))), None)
        ids = [celula(linha, "id") or "", *linha]
        ident = _identificar(
            ids, celula(linha, "url"), doi, celula(linha, "titulo"), celula(linha, "ano"), f"{nome}:{n}"
        )
        if ident:
            imp.itens.append(ident)
        else:
            imp.ignorados.append(f"linha {n}: {celula(linha, 'titulo') or linha[0][:60]}")
    return imp


def ler_bibtex(texto: str, nome: str = "arquivo.bib") -> Importacao:
    imp = Importacao(nome, "bibtex")
    for n, entrada in enumerate(re.split(r"^@", texto, flags=re.MULTILINE)[1:], start=1):
        campos = {
            m.group(1).lower(): m.group(2).strip().strip("{}").strip()
            for m in re.finditer(r"^\s*(\w+)\s*=\s*\{(.*)\},?\s*$", entrada, flags=re.MULTILINE)
        }
        ident = _identificar(
            [campos.get("pid", "")],
            campos.get("url"),
            campos.get("doi") or campos.get("crossref"),
            campos.get("title"),
            campos.get("year"),
            f"{nome}#{n}",
        )
        if ident:
            imp.itens.append(ident)
        else:
            imp.ignorados.append(f"entrada {n}: {campos.get('title', '(sem título)')[:60]}")
    return imp


def ler_txt(texto: str, nome: str = "arquivo.txt") -> Importacao:
    """Um identificador por linha: DOI (com ou sem `https://doi.org/`), PID ou link do SciELO. `#` comenta."""
    imp = Importacao(nome, "txt")
    for n, linha in enumerate(texto.splitlines(), start=1):
        linha = linha.split("#", 1)[0].strip()
        if not linha:
            continue
        ident = _identificar([linha], linha if "://" in linha else None, linha, None, None, f"{nome}:{n}")
        if ident:
            imp.itens.append(ident)
        else:
            imp.ignorados.append(f"linha {n}: {linha[:60]}")
    return imp


def ler_arquivo(caminho: Path) -> Importacao:
    formato = FORMATOS.get(caminho.suffix.lower())
    if formato is None:
        raise ErroConfig(
            f"Formato não reconhecido: {caminho.name}. Use RIS (.ris), CSV (.csv), BibTeX (.bib) ou uma lista (.txt)."
        )
    dados = caminho.read_bytes()
    try:
        texto = dados.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = dados.decode("cp1252")  # CSV salvo pelo Excel no Windows
    leitor = {"ris": ler_ris, "csv": ler_csv, "bibtex": ler_bibtex, "txt": ler_txt}[formato]
    return leitor(texto, caminho.name)
