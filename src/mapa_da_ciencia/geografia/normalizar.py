"""Nomes de lugares como as fontes escrevem → códigos: país (ISO 3166-1 alfa-2), UF (sigla) e municípios.

A `v240` da ArticleMeta traz o país em ISO-2 e a UF por extenso; a `v70` traz o que o autor escreveu ("Brasil",
"USA", "RJ)", "Rio de Janeiro"); o OpenAlex traz o país em ISO-2 e a região em português ou inglês ("Federal
District"). As tabelas ficam em `geografia/dados/`:

- `paises.csv`: nomes em português, inglês e espanhol, gerados do CLDR por `scripts/gerar_paises.ts`;
- `variantes_paises.csv`: o que o CLDR não traz (EUA, Holanda, Inglaterra…), editável à mão;
- `ufs.csv`: as 27 UFs, com código do IBGE, região, capital e variantes;
- `municipios.csv`: os municípios do IBGE (`scripts/gerar_municipios.py`).

As funções comparam por uma chave sem acentos, sem pontuação e em minúsculas. Uma sigla de UF ("PA", "SC") ou um
nome de município ("Santiago", "Barcelona") também existe fora do Brasil: `uf` e `ufs_da_cidade` só devem ser
usadas quando o país é o Brasil (ou ainda desconhecido, com outro indício de que é).
"""

from __future__ import annotations

import csv
import difflib
import re
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from functools import cache
from importlib import resources

from ..texto import normalizar_titulo

SEMELHANCA_PAIS = 0.9  # para erros de digitação ("Brazi"); abaixo disso, Austria ≠ Australia
TAMANHO_MINIMO_APROXIMADO = 5
_PARTES = re.compile(r"[,;/()\[\]]| - ")
_PREFIXO_UF = re.compile(r"^(estado d[eoa]s?|state of|provincia d[eoa]|estado)\s+")
_CODIGO = re.compile(r"^[A-Z]{2}$")


# apóstrofos, aspas e travessões tipográficos viram espaço (senão "King’s" vira "kings", e "Iscte–Instituto",
# uma palavra só)
_TIPOGRAFICOS = str.maketrans({c: " " for c in "’‘`´“”–—"})


def chave(texto: str | None) -> str:
    """Forma de comparação: sem acentos, minúsculas, só letras e números separados por um espaço."""
    return normalizar_titulo(texto.translate(_TIPOGRAFICOS) if texto else texto)


@dataclass(frozen=True)
class UF:
    sigla: str
    nome: str
    codigo: int
    regiao: str
    capital: str
    variantes: tuple[str, ...] = ()


def _linhas(arquivo: str) -> Iterator[dict[str, str]]:
    texto = resources.files("mapa_da_ciencia.geografia").joinpath("dados", arquivo).read_text("utf-8")
    yield from csv.DictReader(linha for linha in texto.splitlines() if not linha.startswith("#"))


def _unicos(pares: Iterator[tuple[str, str]]) -> tuple[dict[str, str], set[str]]:
    """Chave → código, sem as chaves que apontam para códigos diferentes (devolvidas à parte)."""
    candidatos: dict[str, set[str]] = defaultdict(set)
    for texto, codigo in pares:
        if k := chave(texto):
            candidatos[k].add(codigo)
    ambiguas = {k for k, cs in candidatos.items() if len(cs) > 1}
    return {k: next(iter(cs)) for k, cs in candidatos.items() if k not in ambiguas}, ambiguas


@cache
def _paises() -> tuple[dict[str, str], dict[str, str], set[str]]:
    """(chave → ISO-2, ISO-2 → nome em português, chaves ambíguas)."""
    linhas = list(_linhas("paises.csv"))
    variantes = list(_linhas("variantes_paises.csv"))
    pares = [(linha[idioma], linha["iso2"]) for linha in linhas for idioma in ("pt", "en", "es")]
    pares += [(v["variante"], v["iso2"]) for v in variantes]
    indice, ambiguas = _unicos(iter(pares))
    return indice, {linha["iso2"]: linha["pt"] for linha in linhas}, ambiguas


@cache
def _ufs() -> tuple[dict[str, UF], dict[str, str]]:
    """(sigla → UF, chave → sigla)."""
    ufs = {}
    pares = []
    for linha in _linhas("ufs.csv"):
        variantes = tuple(v for v in linha["variantes"].split("|") if v)
        uf = UF(linha["sigla"], linha["nome"], int(linha["codigo"]), linha["regiao"], linha["capital"], variantes)
        ufs[uf.sigla] = uf
        pares += [(uf.sigla, uf.sigla), (uf.nome, uf.sigla)]
        pares += [(v, uf.sigla) for v in variantes]
    indice, ambiguas = _unicos(iter(pares))
    assert not ambiguas, ambiguas
    return ufs, indice


@cache
def _municipios() -> dict[str, frozenset[str]]:
    """Chave do nome → UFs que têm um município com esse nome."""
    ufs: dict[str, set[str]] = defaultdict(set)
    for linha in _linhas("municipios.csv"):
        ufs[chave(linha["nome"])].add(linha["uf"])
    return {k: frozenset(v) for k, v in ufs.items()}


def codigos_de_pais() -> frozenset[str]:
    return frozenset(_paises()[1])


def nome_do_pais(iso2: str) -> str:
    """Nome em português ("BR" → "Brasil"); o próprio código se ele não existir."""
    return _paises()[1].get(iso2, iso2)


def ufs() -> tuple[UF, ...]:
    """As 27 UFs, em ordem alfabética da sigla (a mesma do contrato)."""
    return tuple(_ufs()[0].values())


def _partes(texto: str) -> list[str]:
    return [p.strip() for p in _PARTES.split(texto) if p.strip()]


def _concordante(valores: list[str | None]) -> str | None:
    achados = {v for v in valores if v}
    return achados.pop() if len(achados) == 1 else None


def pais(texto: str | None) -> str | None:
    """Código ISO-2 do país escrito em `texto`, ou None.

    Aceita o código ("BR"), o nome em português, inglês ou espanhol, as variantes (EUA, UK, Holanda), um texto com
    partes ("Brasil (Brazil)", "Porto Alegre, Brasil": vale se as partes reconhecidas concordam) e erros de
    digitação pequenos ("Brazi").
    """
    if not texto or not texto.strip():
        return None
    texto = texto.strip()
    indice, nomes, _ = _paises()
    if _CODIGO.match(texto) and texto in nomes:
        return texto
    if achado := indice.get(chave(texto)):
        return achado
    if achado := _concordante([indice.get(chave(p)) for p in _partes(texto)]):
        return achado
    k = chave(texto)
    if len(k) >= TAMANHO_MINIMO_APROXIMADO:
        proximas = difflib.get_close_matches(k, indice, n=3, cutoff=SEMELHANCA_PAIS)
        return _concordante([indice[p] for p in proximas])
    return None


def uf(texto: str | None) -> str | None:
    """Sigla da UF escrita em `texto` ("São Paulo", "SP", "RJ)", "Federal District", "Estado de Minas Gerais")."""
    if not texto or not texto.strip():
        return None
    indice = _ufs()[1]

    def uma(parte: str) -> str | None:
        k = chave(parte)
        return indice.get(k) or indice.get(_PREFIXO_UF.sub("", k))

    return uma(texto) or _concordante([uma(p) for p in _partes(texto.replace("-", " - "))])


def nome_da_uf(sigla: str) -> str:
    return _ufs()[0][sigla].nome


def separar_cidade_uf(texto: str | None) -> tuple[str | None, str | None]:
    """ "Niterói, RJ" → ("Niterói", "RJ"); "São Paulo - SP" → ("São Paulo", "SP"); sem UF no fim, (texto, None)."""
    if not texto or not texto.strip():
        return None, None
    partes = _partes(texto.replace("-", " - "))
    if len(partes) >= 2 and not uf(partes[-1]) and pais(partes[-1]) == "BR":
        partes = partes[:-1]  # "Recife, PE, Brasil"
    if len(partes) >= 2 and (sigla := uf(partes[-1])):
        return ", ".join(partes[:-1]), sigla
    return ", ".join(partes) if partes else texto.strip(), None


def ufs_da_cidade(texto: str | None) -> frozenset[str]:
    """UFs que têm um município com esse nome (vazio se nenhuma). "Santiago" → {RS}: confira o país antes."""
    cidade, sigla = separar_cidade_uf(texto)
    candidatas = _municipios().get(chave(cidade), frozenset())
    if sigla:
        return frozenset({sigla}) if sigla in candidatas or not candidatas else frozenset()
    return candidatas


def uf_da_cidade(texto: str | None) -> str | None:
    """A UF de um município brasileiro quando o nome é único no país, ou quando um dos homônimos é capital.

    "Juiz de Fora" → MG; "Belém" → PA (há Belém na Paraíba e em Alagoas, mas a capital do Pará pesa mais);
    "São Carlos" → None (SP e SC, nenhuma capital).
    """
    candidatas = ufs_da_cidade(texto)
    if len(candidatas) == 1:
        return next(iter(candidatas))
    cidade = chave(separar_cidade_uf(texto)[0])
    capitais = [s for s in candidatas if chave(_ufs()[0][s].capital) == cidade]
    return capitais[0] if len(capitais) == 1 else None
