"""Casamento das afiliações com as instituições do OpenAlex (ADR 0008).

A ArticleMeta diz a afiliação de cada autor como texto ("Universidade do Estado do Rio de Janeiro", "PUC-Rio",
"Universidade de Maryland"); o OpenAlex diz, para os mesmos autores, quais instituições reconheceu, com
identificador, país e linhagem. O casamento liga cada afiliação da ArticleMeta a uma dessas instituições,
procurando os candidatos do mais próximo ao mais distante:

| Nível | Candidatos | Semelhança mínima |
|---|---|---|
| `apelido` | apelidos do pacote e do `instituicoes.yaml` | texto igual |
| `autoria` | instituições que o OpenAlex deu ao mesmo autor | `LIMIAR_AUTORIA` |
| `obra` | instituições de todos os autores da obra | `LIMIAR_OBRA` |
| `corpus` | o mesmo texto já casado em outros documentos | `APOIO_CORPUS` casamentos concordantes |
| `indice` | todas as instituições conhecidas | `LIMIAR_INDICE`, com margem sobre a segunda |

A semelhança compara conjuntos de palavras sem acentos e sem palavras vazias, com as palavras genéricas traduzidas
para uma forma só ("university", "universidad" → "universidade") e os nomes de UF compostos juntados numa palavra
("Rio Grande do Sul"). Cada palavra pesa pelo inverso da frequência entre as instituições (IDF), e a medida é a de
Dice ponderada. Duas travas evitam os erros mais comuns entre nomes parecidos: palavras **discriminantes**
(federal, estadual, católica, norte, sul…) precisam ser as mesmas nos dois nomes, e um candidato de outro país
(quando a fonte informa o país) é descartado. Uma sigla do registro que aparece no texto ("UFSCar", "PUC-Rio")
casa direto.

Depois do casamento, a instituição **sobe na linhagem** até a organização de ensino "mãe", como faz a `v240`:
um hospital, um centro ou uma escola de uma universidade (EAESP → FGV) contam para a universidade. Uma
universidade de uma federação (King's College London, na University of London) não sobe.

Um autor sem afiliação na ArticleMeta fica com as instituições que o OpenAlex deu a ele (`openalex`), e um documento
sem autores na ArticleMeta usa as autorias do OpenAlex inteiras.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Literal

from ..documento import Afiliacao, Autor, AutoriaOpenAlex, Documento
from . import normalizar
from .instituicoes import Registro

Nivel = Literal["apelido", "autoria", "obra", "corpus", "indice", "openalex", "nenhum"]
NIVEIS: tuple[Nivel, ...] = ("apelido", "autoria", "obra", "corpus", "indice", "openalex", "nenhum")
Fonte = Literal["v240", "v70", "openalex"]

LIMIAR_AUTORIA = 0.5
LIMIAR_OBRA = 0.75
LIMIAR_INDICE = 0.9
MARGEM_INDICE = 0.1
APOIO_CORPUS = 2
CONCORDANCIA_CORPUS = 0.8
SIGLA_MINIMA = 3
SEMELHANCA_PALAVRA = 0.8

# ---------------------------------------------------------------- palavras
_VAZIAS = frozenset(
    "a o as os ao aos de da do das dos e em no na nos nas the of for and at in on y del la las los el en le "
    "les du des et d l al di della delle dei degli von der und zu".split()
)
_EQUIVALENTES = {
    forma: canonica
    for canonica, formas in {
        "universidade": "university universidad universite universitat universita universiteit universitaet "
        "universitet univ",
        "faculdade": "faculty facultad faculte facolta fac",
        "instituto": "institute institut istituto inst",
        "escola": "school escuela ecole scuola",
        "centro": "center centre",
        "departamento": "department departement dipartimento dept depto dep",
        "federal": "fed",
        "estadual": "state estado estatal statale",
        "catolica": "catholic catolico cattolica katholieke catholique",
        "pontificia": "pontifical pontificio pont",
        "nacional": "national nazionale nationale",
        "tecnologica": "tecnologico technological tecnologia technology technologie",
        "fundacao": "foundation fundacion fondation fondazione",
        "conselho": "consejo council conseil consiglio",
        "comissao": "comision commission",
        "corporacao": "corporacion corporation",
        "associacao": "asociacion association",
        "sociedade": "sociedad society societe",
        "universitario": "universitaria universitary",
        "educacao": "education educacion",
        "camara": "chamber camera",
        "deputados": "deputies diputados deputes",
        "senado": "senate senat senato",
        "ministerio": "ministry ministere ministero",
        "secretaria": "secretariat secretary",
        "exercito": "army ejercito",
        "marinha": "navy naval armada",
        "guerra": "war",
        "ciencias": "ciencia science sciences scienze",
        "sociais": "social sociales sociale sociali",
        "politica": "politicas political politics politique politiques politico politicos",
        "estudos": "studies estudios etudes studi",
        "pesquisa": "pesquisas research investigacion investigaciones recherche recherches ricerca",
        "economia": "economics economic economica economie economico",
        "relacoes": "relations relaciones",
        "internacionais": "international internacional internacionales internationales internazionali",
        "nova": "new nueva nouvelle nuovo",
        "livre": "libre free vrije freie libera",
        "aberta": "open abierta ouverte",
        "norte": "north nord",
        "sul": "south sur sud",
        "leste": "east",
        "oeste": "west ouest",
        "nordeste": "northeast northeastern",
        "sudeste": "southeast southeastern",
        "noroeste": "northwest northwestern",
        "sudoeste": "southwest southwestern",
    }.items()
    for forma in formas.split()
}
DISCRIMINANTES = frozenset(
    "federal estadual municipal catolica rural tecnologica nova livre aberta norte sul leste oeste nordeste sudeste "
    "noroeste sudoeste".split()
)
# palavras que dizem o tipo da organização, e não qual é ela: sobrar uma delas não indica outra instituição
GENERICAS = frozenset(
    "universidade faculdade instituto escola centro departamento programa pos graduacao superior educacao ensino "
    "estudos pesquisa nacional universitario".split()
)
_SUBUNIDADES = frozenset(
    "escola faculdade instituto departamento centro nucleo laboratorio programa hospital museu".split()
)
# palavras que começam o nome da organização que contém uma unidade ("… da Universidade de Brasília")
_CONTEM = frozenset("universidade fundacao faculdade escola instituto centro".split())
_LIGACOES = frozenset("da do de das dos na no em pela pelo of the at in del".split())  # não "State University of…"
# um texto de afiliação do OpenAlex sem instituição reconhecida só vale se nomeia uma organização (muitos são
# pedaços do PDF raspado: "O Brasil tem", "tradução de")
_ORGANIZACOES = _SUBUNIDADES | frozenset(
    "universidade universitario fundacao ministerio secretaria conselho comissao observatorio college academia "
    "agencia banco camara senado tribunal assembleia prefeitura governo empresa associacao sociedade corporacao "
    "exercito marinha aeronautica policia embaixada organizacao institutofederal".split()
)
TAMANHO_MAXIMO_AFILIACAO = 200


@lru_cache(maxsize=1)
def _expressoes() -> tuple[tuple[re.Pattern[str], str], ...]:
    """Expressões que viram uma palavra só: os nomes compostos de UF ("rio grande do sul" → "lugarrs", antes de
    "rio grande"; assim o "sul" do estado não se confunde com o de "Universidade Federal do Sul da Bahia", e o
    "federal" do Distrito Federal não conta como o de uma universidade federal) e "instituto federal", uma categoria
    de instituição diferente da universidade federal."""
    nomes = [
        (" ".join(_EQUIVALENTES.get(p, p) for p in normalizar.chave(n).split()), f"lugar{u.sigla.lower()}")
        for u in normalizar.ufs()
        for n in (u.nome, *u.variantes)
        if " " in n or n != u.nome  # os nomes de uma palavra (Bahia, Paraná) já são uma palavra só
    ]
    nomes.sort(key=lambda par: -len(par[0]))
    categorias = (
        # "Instituto Federal de Educação, Ciência e Tecnologia de Goiás" = "Instituto Federal de Goiás"
        (r"\b(?:instituto federal|federal instituto)(?: (?:de|of) educacao ciencias (?:e|and) tecnologica)?\b",
         "institutofederal"),
        (r"\b(?:centro federal de educacao tecnologica|federal centro (?:of|for) tecnologica educacao)\b", "cefet"),
    )  # fmt: skip
    return (
        *((re.compile(padrao), marca) for padrao, marca in categorias),
        *((re.compile(rf"\b{re.escape(nome)}\b"), marca) for nome, marca in nomes),
    )


_MARCAS = ("lugar", "institutofederal")
_LETRAS_SOLTAS = re.compile(r"\b[a-z](?: [a-z]\b)+")


@lru_cache(maxsize=200_000)
def palavras(texto: str) -> frozenset[str]:
    """As palavras que contam na comparação de nomes de instituição."""
    # letras soltas em sequência formam uma palavra ("Texas A&M" → "am"); uma letra sozinha (inicial) não conta
    texto = texto.replace("#TAB#", " ")  # resto de tabulação nos textos do OpenAlex
    base = _LETRAS_SOLTAS.sub(lambda m: m.group().replace(" ", ""), normalizar.chave(texto))
    base = " ".join(_EQUIVALENTES.get(p, p) for p in base.split())
    for padrao, marca in _expressoes():
        base = padrao.sub(marca, base)
    return frozenset(p for p in base.split() if p not in _VAZIAS and (len(p) >= 2 or p.isdigit()))


_ANO = re.compile(r"\b(?:19|20)\d\d\b")
_CIDADE_EDITORA = re.compile(r"^[^\W\d_][\w .'-]{1,30}:\s")  # "Cambridge: Cambridge University Press"


def parece_afiliacao(texto: str) -> bool:
    """Um texto de afiliação, e não um pedaço do artigo raspado pelo OpenAlex: curto, sem ano (as citações têm:
    "Cambridge University Press, 1997") e sem cara de frase (seis palavras ou mais começando em minúscula ou
    pontuação: ". Swanson diz que…", "versão anterior deste artigo foi apresentada…")."""
    texto = texto.strip()
    if not 0 < len(texto) <= TAMANHO_MAXIMO_AFILIACAO or _ANO.search(texto) or _CIDADE_EDITORA.match(texto):
        return False
    return len(texto.split()) < 6 or texto[0].isupper()


def parece_organizacao(texto: str) -> bool:
    """Um texto curto em que alguma parte nomeia uma organização (universidade, instituto, ministério…) ou é uma
    sigla ("CONICET, Argentina")."""
    if not 0 < len(texto) <= TAMANHO_MAXIMO_AFILIACAO:
        return False
    for parte in (p.strip() for p in _PARTES.split(texto)):
        if " " not in parte and sum(c.isupper() for c in parte) >= 2 and len(parte) <= 15:
            return True
        if palavras(parte) & _ORGANIZACOES:
            return True
    return False


def _chave_sigla(texto: str) -> str:
    return normalizar.chave(texto).replace(" ", "")


_PARTES = re.compile(r"[,;()\[\]]| - | – ")
_TOKEN_SIGLA = re.compile(r"[^\W_]+(?:-[^\W_]+)*")


@lru_cache(maxsize=50_000)
def _so_lugar(parte: str) -> bool:
    return bool(normalizar.pais(parte) or normalizar.uf(parte) or normalizar.ufs_da_cidade(parte))


@lru_cache(maxsize=50_000)
def partes(texto: str) -> tuple[frozenset[str], ...]:
    """O texto inteiro e cada parte (separada por vírgula, parênteses, " - "), sem as partes que são só um lugar.

    Assim "Departamento de Ciência Política, Universidade de São Paulo, São Paulo, Brasil" compara a instituição
    sem o endereço e sem o departamento atrapalharem.
    """
    brutas = [p.strip() for p in _PARTES.split(texto) if p.strip()]
    uteis = [p for p in brutas if not _so_lugar(p)] or brutas
    conjuntos = [palavras(" ".join(uteis)), *(palavras(p) for p in uteis)]
    # "Instituto de Ciência Política da Universidade de Brasília": a organização que contém a unidade também é parte
    for p in uteis:
        base = normalizar.chave(p).split()
        conjuntos += [
            palavras(" ".join(base[i:]))
            for i in range(1, len(base))
            if base[i - 1] in _LIGACOES and _EQUIVALENTES.get(base[i], base[i]) in _CONTEM
        ]
    return tuple(dict.fromkeys(c for c in conjuntos if c))


@dataclass(frozen=True)
class Sigla:
    chave: str
    resto: frozenset[str]  # as outras palavras da parte em que a sigla aparece ("Minas", em "PUC Minas")
    inteira: bool  # a palavra toda, e não um pedaço de "IESP-UERJ"


@lru_cache(maxsize=50_000)
def siglas_do_texto(texto: str) -> tuple[Sigla, ...]:
    """Siglas candidatas: palavras com duas maiúsculas ou mais ("UFSCar", "PUC-Rio", "UnB") e partes de uma
    palavra só ("Unicamp"). Num nome composto com hífen, cada pedaço também vale ("IESP-UERJ" → UERJ)."""
    achadas: dict[str, Sigla] = {}
    for parte in (p.strip() for p in _PARTES.split(texto)):
        todas = palavras(parte) if parte else frozenset()
        for m in _TOKEN_SIGLA.finditer(parte):
            s = m.group()
            if sum(c.isupper() for c in s) < 2 and not (s == parte and len(s) <= 15):
                continue
            achadas.setdefault(_chave_sigla(s), Sigla(_chave_sigla(s), todas - palavras(s), True))
            if "-" in s:
                for pedaco in s.split("-"):
                    achadas.setdefault(_chave_sigla(pedaco), Sigla(_chave_sigla(pedaco), frozenset(), False))
    return tuple(sg for sg in achadas.values() if len(sg.chave) >= SIGLA_MINIMA)


@lru_cache(maxsize=200_000)
def _quase_iguais(x: str, y: str) -> bool:
    """Grafias vizinhas da mesma palavra: erro de digitação ("Universtity") ou tradução ("Lisbon" × "Lisboa",
    "Berlim" × "Berlin"). Só palavras de cinco letras ou mais: "Pará" e "Paraná" continuam diferentes."""
    if x.startswith(_MARCAS) or y.startswith(_MARCAS):
        return False  # "lugarrj" e "lugarrs" são estados diferentes
    return min(len(x), len(y)) >= 5 and SequenceMatcher(None, x, y).ratio() >= SEMELHANCA_PALAVRA


def _aproximar(a: frozenset[str], b: frozenset[str]) -> tuple[frozenset[str], frozenset[str]]:
    """Troca, em `a`, as palavras quase iguais a uma de `b` pela de `b`."""
    sobra_b = b - a
    trocas = {x: y for x in a - b for y in sobra_b if _quase_iguais(x, y)}
    return (frozenset(trocas.get(x, x) for x in a), b) if trocas else (a, b)


def _conflito(a: frozenset[str], b: frozenset[str]) -> bool:
    """Os dois nomes têm, cada um, uma palavra distintiva que o outro não tem ("Paraná" × "Pará", "Administração"
    × "Saúde"): são instituições diferentes, por mais que o resto coincida. Sobrar palavras de um lado só
    (o departamento no texto, "College Park" no nome) não é conflito."""
    return bool((a - b) - GENERICAS) and bool((b - a) - GENERICAS)


# ---------------------------------------------------------------- índice das instituições
class Indice:
    """As instituições conhecidas, com os pesos das palavras, as siglas e os apelidos."""

    def __init__(self, registros: dict[str, Registro], apelidos: dict[str, str] | None = None) -> None:
        self.registros = registros
        self._nomes: dict[str, tuple[frozenset[str], ...]] = {}
        frequencia: Counter[str] = Counter()
        self._por_palavra: dict[str, set[str]] = defaultdict(set)
        self._por_sigla: dict[str, set[str]] = defaultdict(set)
        for r in registros.values():
            # cada nome também sem a sigla que ele carrega ("Iscte – Instituto Universitário de Lisboa"), que casa
            # por outro caminho; com ela, para não perder uma palavra que também é sigla ("Nova", da Nova de Lisboa)
            # (a variante sem a sigla precisa continuar nomeando uma organização: "CONACYT México" não vira "México",
            proprias = {_chave_sigla(p) for x in r.siglas for p in (x, *x.split("-"))} - DISCRIMINANTES
            nomes = [palavras(n) for n in (r.nome, *r.nomes) if n]
            sem_sigla = [n - proprias for n in nomes if n & proprias]
            # e dizer qual é ela: "Centro Universitário FEI" sem o FEI é só uma categoria
            sem_sigla = [n for n in sem_sigla if len(n) >= 2 and n & _ORGANIZACOES and n - GENERICAS - _ORGANIZACOES]
            conjuntos = tuple(dict.fromkeys(c for c in (*nomes, *sem_sigla) if c))
            self._nomes[r.id] = conjuntos
            todas = frozenset().union(*conjuntos)
            frequencia.update(todas)
            for p in todas:
                self._por_palavra[p].add(r.id)
            for s in r.siglas:
                if len(k := _chave_sigla(s)) >= SIGLA_MINIMA:
                    self._por_sigla[k].add(r.id)
        # palavras que são lugar: as UFs juntadas, as cidades de uma palavra só das instituições (não o "college" de
        # College Park, nem o "nova" de Nova York) e os nomes de países
        cidades = (palavras(r.cidade) for r in registros.values() if r.cidade)
        self._lugares = (
            frozenset(p for p in frequencia if p.startswith("lugar"))
            | (frozenset(next(iter(c)) for c in cidades if len(c) == 1) - GENERICAS - _ORGANIZACOES - DISCRIMINANTES)
            | frozenset(p for p in frequencia if len(p) >= 4 and normalizar.pais(p))
        )
        total = max(1, len(registros))
        self._peso = {p: math.log(1 + total / n) for p, n in frequencia.items()}
        self._peso_desconhecida = math.log(1 + total)
        self.apelidos = {normalizar.chave(k): v for k, v in (apelidos or {}).items() if v in registros}
        self._mae: dict[str, str] = {}

    def peso(self, palavra: str) -> float:
        return self._peso.get(palavra, self._peso_desconhecida)

    def _dice(self, a: frozenset[str], b: frozenset[str]) -> float:
        if (a & DISCRIMINANTES) != (b & DISCRIMINANTES):
            return 0.0
        a, b = _aproximar(a, b)
        if _conflito(a, b) or (a & b) <= self._lugares:
            return 0.0  # só o lugar em comum ("London" × "SOAS University of London") não é a mesma organização
        comum = sum(self.peso(p) for p in a & b)
        if not comum:
            return 0.0
        return 2 * comum / (sum(self.peso(p) for p in a) + sum(self.peso(p) for p in b))

    def semelhanca(self, texto: str, id_: str) -> float:
        """0 a 1: quanto `texto` parece com algum nome da instituição (1 se uma sigla dela aparece no texto sem
        palavras que contradigam o nome, como em "PUC Minas" para a PUC do Chile)."""
        nomes = self._nomes.get(id_, ())
        for sg in siglas_do_texto(texto):
            if id_ in self._por_sigla.get(sg.chave, ()) and any(not _conflito(sg.resto, n) for n in nomes):
                return 1.0
        return self.pelo_nome(texto, id_)

    def apelido(self, texto: str) -> str | None:
        if id_ := self.apelidos.get(normalizar.chave(texto)):
            return id_
        achados = {self.apelidos.get(normalizar.chave(p)) for p in _PARTES.split(texto) if p.strip()} - {None}
        return achados.pop() if len(achados) == 1 else None

    def compativel(self, id_: str, pais: str | None) -> bool:
        """Falso quando a fonte e o registro informam países diferentes."""
        r = self.registros.get(id_)
        return r is not None and not (pais and r.pais and r.pais != pais)

    def pelo_nome(self, texto: str, id_: str) -> float:
        """A semelhança só pelos nomes, sem as siglas (que se repetem entre países: USP, PUC)."""
        nomes = self._nomes.get(id_, ())
        return max((self._dice(p, n) for p in partes(texto) for n in nomes), default=0.0)

    def melhores(self, texto: str, candidatos: Iterable[str], pais: str | None) -> list[tuple[float, str]]:
        """Candidatos do país da fonte (ou de qualquer um, sem o país) com semelhança positiva, do melhor ao pior.

        O veto pelo país vale mesmo quando a `v70` erra o país ("Universidade de Cambridge, Brasil"): aceitar nomes
        idênticos de outro país casaria a Escola Superior de Guerra com a da Colômbia."""
        notas = [(self.semelhanca(texto, c), c) for c in dict.fromkeys(candidatos) if self.compativel(c, pais)]
        return sorted((n for n in notas if n[0] > 0), key=lambda n: (-n[0], n[1]))

    def candidatos_globais(self, texto: str) -> set[str]:
        """Instituições que dividem com o texto uma sigla ou uma palavra menos comum que "universidade"."""
        ids: set[str] = set()
        for sg in siglas_do_texto(texto):
            if sg.inteira:
                ids |= self._por_sigla.get(sg.chave, set())
        referencia = self.peso("universidade")
        for p in frozenset().union(*partes(texto)):
            if self.peso(p) > referencia:
                ids |= self._por_palavra.get(p, set())
        return ids

    def mae(self, id_: str) -> str:
        """Sobe na linhagem até a organização de ensino "mãe" (a mais próxima), quando há uma só."""
        if id_ in self._mae:
            return self._mae[id_]
        atual, vistos = id_, set()
        while atual not in vistos:
            vistos.add(atual)
            r = self.registros.get(atual)
            if r is None or r.separada:
                break
            primeira = (normalizar.chave(r.nome).split() or [""])[0]
            if r.tipo == "education" and _EQUIVALENTES.get(primeira, primeira) not in _SUBUNIDADES:
                break
            acima = [
                a
                for a in r.linhagem
                if a != atual
                and (x := self.registros.get(a)) is not None
                and x.tipo == "education"
                and not x.super_sistema
            ]
            proximas = [a for a in acima if not any(a in self.registros[b].linhagem for b in acima if b != a)]
            if len(proximas) != 1:
                break
            atual = proximas[0]
        self._mae[id_] = atual
        return atual


# ---------------------------------------------------------------- vínculos
@dataclass
class Vinculo:
    """Um autor (ou uma afiliação sem autor) ligado a uma instituição, ou a nenhuma."""

    autor: int | None  # posição do autor; None = afiliação que nenhum autor cita
    afiliacao: int | None  # posição da afiliação na ArticleMeta; None = veio do OpenAlex
    fonte: Fonte
    texto: str
    casada: str | None = None  # a instituição que casou
    instituicao: str | None = None  # a mesma, depois de subir até a "mãe"
    nivel: Nivel = "nenhum"
    semelhanca: float | None = None
    pais_fonte: str | None = None
    uf_fonte: str | None = None
    cidade_fonte: str | None = None


@dataclass
class Casamento:
    """Os vínculos de um documento e quantos autores ele tem (os sem vínculo contam como "sem afiliação")."""

    doc: str
    n_autores: int
    vinculos: list[Vinculo]


_FORA_DO_SOBRENOME = {"de", "da", "do", "dos", "das", "e", "junior", "jr", "filho", "neto", "sobrinho"}


def _sobrenomes(autor: Autor) -> set[str]:
    return set(normalizar.chave(autor.sobrenome or autor.nome or "").split()) - _FORA_DO_SOBRENOME


def _partes(nome: str | None) -> list[str]:
    return [t for t in normalizar.chave(nome).split() if t not in _FORA_DO_SOBRENOME]


def nomes_compativeis(a: str | None, b: str | None) -> bool:
    """Dois nomes podem ser da mesma pessoa: alguma parte de um, depois da primeira (um sobrenome ou um nome do meio),
    aparece no outro. "Camila Penna de Castro" e "Camila Penna" são; "Juan Jesús Morales" e "Juan Martín" não (só o
    primeiro nome em comum); "Hung Ho-Fung" e "Ho‐fung Hung" são."""
    pa, pb = _partes(a), _partes(b)
    return bool(set(pa[1:]) & set(pb) or set(pb[1:]) & set(pa))


def nome_completo(autor: Autor) -> str:
    return " ".join(x for x in (autor.nome, autor.sobrenome) if x)


def alinhar(autores: list[Autor], autorias: list[AutoriaOpenAlex]) -> dict[int, int]:
    """Autor da ArticleMeta → autoria do OpenAlex: pela posição quando o sobrenome (ou o nome, `nomes_compativeis`)
    confere, depois pelo sobrenome ou pelo nome, se só uma autoria livre servir. Com um autor de cada lado, o par vale
    se os nomes forem compatíveis, ou se um deles não tiver letras latinas para comparar ("Франк Руда")."""
    nomes = [set(normalizar.chave(a.nome).split()) for a in autorias]
    pares: dict[int, int] = {}

    def confere(autor: Autor, j: int) -> bool:
        return bool(_sobrenomes(autor) & nomes[j]) or nomes_compativeis(nome_completo(autor), autorias[j].nome)

    if len(autores) == len(autorias) == 1:
        sem_comparar = not _partes(nome_completo(autores[0])) or not _partes(autorias[0].nome)
        return {0: 0} if sem_comparar or confere(autores[0], 0) else {}
    for i, autor in enumerate(autores):
        if i < len(autorias) and confere(autor, i):
            pares[i] = i
    livres = set(range(len(autorias))) - set(pares.values())
    for i, autor in enumerate(autores):
        if i in pares:
            continue
        candidatas = [j for j in livres if confere(autor, j)]
        if len(candidatas) == 1:
            pares[i] = candidatas[0]
            livres.discard(candidatas[0])
    return pares


def _texto(af: Afiliacao) -> str:
    return (af.instituicao or ", ".join(af.divisoes) or "").strip()


def _vinculo_da_fonte(af: Afiliacao, autor: int | None, posicao: int) -> Vinculo:
    cidade, uf_cidade = normalizar.separar_cidade_uf(af.cidade)
    return Vinculo(
        autor=autor,
        afiliacao=posicao,
        fonte=af.fonte,
        texto=_texto(af),
        pais_fonte=normalizar.pais(af.pais),
        uf_fonte=normalizar.uf(af.uf) or uf_cidade,
        cidade_fonte=cidade,
    )


class Casador:
    """Casa os documentos em duas passadas: primeiro com os candidatos do próprio documento, depois com o que o
    corpus inteiro ensinou (`corpus`) e com o índice global (`indice`)."""

    def __init__(self, indice: Indice) -> None:
        self.indice = indice

    def _decidir(self, v: Vinculo, id_: str, nivel: Nivel, nota: float | None) -> None:
        v.casada, v.instituicao, v.nivel, v.semelhanca = id_, self.indice.mae(id_), nivel, nota

    def _local(self, v: Vinculo, autoria: set[str], obra: set[str]) -> None:
        if not v.texto:
            return
        if id_ := self.indice.apelido(v.texto):
            self._decidir(v, id_, "apelido", None)
            return
        for nivel, candidatos, limiar in (("autoria", autoria, LIMIAR_AUTORIA), ("obra", obra, LIMIAR_OBRA)):
            notas = self.indice.melhores(v.texto, candidatos, v.pais_fonte)
            if notas and notas[0][0] >= limiar:
                if not self._superado(v, notas[0]):
                    self._decidir(v, notas[0][1], nivel, round(notas[0][0], 4))  # type: ignore[arg-type]
                return

    def _superado(self, v: Vinculo, local: tuple[float, str]) -> bool:
        """O OpenAlex às vezes dá ao autor a instituição errada ("Universidade Cidade de São Paulo" para quem
        escreveu "Universidade de São Paulo"): o candidato do documento perde para um do índice que casa bem melhor,
        e o vínculo fica para a segunda passada."""
        nota, id_ = local
        if nota >= 1.0:
            return False
        mae = self.indice.mae(id_)
        globais = self.indice.melhores(v.texto, self.indice.candidatos_globais(v.texto), v.pais_fonte)
        melhor = next((n for n, c in globais if self.indice.mae(c) != mae), 0.0)
        return melhor >= LIMIAR_INDICE and melhor - nota >= MARGEM_INDICE

    def confiaveis(self, autoria: AutoriaOpenAlex) -> dict[str, tuple[str, float | None]]:
        """As instituições do OpenAlex que valem para o autor, com o texto de afiliação que as sustenta.

        Nos artigos antigos, o OpenAlex tira "afiliações" do texto raspado do PDF ("Em maio de 2007 o Ministério
        Público Federal ingressou…", "Falwell, de Susan Harding") e as liga a instituições sem relação com o autor
        (Harding University). Uma instituição só vale quando o texto que a sustenta parece uma afiliação (sem ano,
        sem ser uma frase) e se parece com o nome dela (os vetos da semelhança descartam "Falwell, de Susan
        Harding"); sem nenhum texto de afiliação na autoria, valem todas. Devolve id → (texto, semelhança).
        """
        if not autoria.afiliacoes:
            return {i.id: (i.nome or i.id, None) for i in autoria.instituicoes if i.id in self.indice.registros}
        saida: dict[str, tuple[str, float | None]] = {}
        for af in autoria.afiliacoes:
            for texto in (t.strip() for t in af.texto.split(";")):
                if not parece_afiliacao(texto):
                    continue
                for id_ in af.instituicoes:
                    if id_ not in self.indice.registros or id_ in saida:
                        continue
                    if (nota := self.indice.semelhanca(texto, id_)) >= LIMIAR_AUTORIA:
                        saida[id_] = (texto, nota)
        return saida

    def _do_openalex(
        self, autoria: AutoriaOpenAlex, confiaveis: dict[str, tuple[str, float | None]], posicao: int
    ) -> list[Vinculo]:
        """Os vínculos de um autor que só o OpenAlex descreve: as instituições confiáveis (sem o texto da ArticleMeta
        para conferir, com a mesma exigência do índice global, `LIMIAR_INDICE`) e, para os casamentos da segunda
        passada, os textos de afiliação que não sustentaram nenhuma."""
        vinculos = []
        usados = set()
        for id_, (texto, nota) in confiaveis.items():
            if nota is not None and nota < LIMIAR_INDICE:
                continue
            v = Vinculo(autor=posicao, afiliacao=None, fonte="openalex", texto=texto)
            v.pais_fonte = self.indice.registros[id_].pais
            self._decidir(v, id_, "openalex", None if nota is None else round(nota, 4))
            vinculos.append(v)
            usados.add(texto)
        pais = autoria.paises[0] if len(autoria.paises) == 1 else None
        for af in autoria.afiliacoes:
            for texto in (t.strip() for t in af.texto.split(";")):
                if parece_afiliacao(texto) and parece_organizacao(texto) and texto not in usados:
                    usados.add(texto)
                    vinculos.append(
                        Vinculo(autor=posicao, afiliacao=None, fonte="openalex", texto=texto, pais_fonte=pais)
                    )
        return vinculos

    def documento(self, doc: Documento) -> Casamento:
        autorias = doc.autorias_openalex
        confiaveis = [self.confiaveis(a) for a in autorias]
        obra = set().union(*confiaveis)
        if not doc.autores:
            vinculos = [v for j, a in enumerate(autorias) for v in self._do_openalex(a, confiaveis[j], j)]
            orfas = [_vinculo_da_fonte(af, None, k) for k, af in enumerate(doc.afiliacoes)]
            for v in orfas:
                self._local(v, set(), obra)
            return Casamento(doc.id, len(autorias), vinculos + orfas)

        pares = alinhar(doc.autores, autorias)
        posicao = {af.id: k for k, af in enumerate(doc.afiliacoes) if af.id}
        citadas_por = [
            list(dict.fromkeys(posicao[a] for a in autor.afiliacoes if a in posicao)) for autor in doc.autores
        ]
        orfas = [k for k in range(len(doc.afiliacoes)) if not any(k in ks for ks in citadas_por)]

        def da_autoria(i: int) -> set[str]:
            j = pares.get(i)
            return set(confiaveis[j]) if j is not None else set()

        vinculos: list[Vinculo] = []
        for i, ks in enumerate(citadas_por):
            if not ks:
                # sem afiliação citada: fica com as órfãs (na contagem) ou, sem órfãs, com as do OpenAlex
                if not orfas and (j := pares.get(i)) is not None:
                    vinculos += self._do_openalex(autorias[j], confiaveis[j], i)
                continue
            for k in ks:
                v = _vinculo_da_fonte(doc.afiliacoes[k], i, k)
                self._local(v, da_autoria(i), obra)
                vinculos.append(v)
        # as órfãs vão para os autores sem afiliação citada: os candidatos mais próximos são as instituições deles
        dos_sem_afiliacao = set().union(*(da_autoria(i) for i, ks in enumerate(citadas_por) if not ks))
        for k in orfas:
            v = _vinculo_da_fonte(doc.afiliacoes[k], None, k)
            self._local(v, dos_sem_afiliacao, obra)
            vinculos.append(v)
        return Casamento(doc.id, len(doc.autores), vinculos)

    def aprender(self, casamentos: Iterable[Casamento]) -> dict[str, str]:
        """Texto → instituição, dos casamentos com candidatos do próprio documento que se repetem no corpus."""
        contagem: dict[str, Counter[str]] = defaultdict(Counter)
        for c in casamentos:
            for v in c.vinculos:
                if v.nivel in ("apelido", "autoria", "obra") and v.casada and v.texto:
                    contagem[normalizar.chave(v.texto)][v.casada] += 1
        aprendido = {}
        for texto, votos in contagem.items():
            id_, n = votos.most_common(1)[0]
            if n >= APOIO_CORPUS and n / sum(votos.values()) >= CONCORDANCIA_CORPUS:
                aprendido[texto] = id_
        return aprendido

    def global_(self, v: Vinculo, aprendido: dict[str, str], pais_do_corpus: str | None = None) -> None:
        """Níveis `corpus` e `indice`. Sem o país na fonte, um empate no índice é desfeito a favor do país mais
        comum do corpus ("USP" é a Universidade de São Paulo num corpus brasileiro, não a San Pablo CEU)."""
        if v.nivel != "nenhum" or not v.texto:
            return
        if (id_ := aprendido.get(normalizar.chave(v.texto))) and self.indice.compativel(id_, v.pais_fonte):
            self._decidir(v, id_, "corpus", None)
            return
        if not parece_organizacao(v.texto) and not any(sg.inteira for sg in siglas_do_texto(v.texto)):
            return  # "Estado de São Paulo" não nomeia uma organização: no índice global, casaria com a Unesp
        notas = self.indice.melhores(v.texto, self.indice.candidatos_globais(v.texto), v.pais_fonte)
        escolha = self._sem_empate(notas)
        if escolha is None and v.pais_fonte is None and pais_do_corpus:
            escolha = self._sem_empate([n for n in notas if self.indice.registros[n[1]].pais == pais_do_corpus])
        if escolha:
            self._decidir(v, escolha[1], "indice", round(escolha[0], 4))

    def _sem_empate(self, notas: list[tuple[float, str]]) -> tuple[float, str] | None:
        if not notas or notas[0][0] < LIMIAR_INDICE:
            return None
        melhor = self.indice.mae(notas[0][1])
        segunda = next((n for n, c in notas[1:] if self.indice.mae(c) != melhor), 0.0)
        return notas[0] if notas[0][0] - segunda >= MARGEM_INDICE else None

    def casar(self, documentos: Iterable[Documento]) -> list[Casamento]:
        casamentos = [self.documento(d) for d in documentos]
        aprendido = self.aprender(casamentos)
        paises = Counter(self.indice.registros[v.casada].pais for c in casamentos for v in c.vinculos if v.casada)
        paises.pop(None, None)
        pais_do_corpus = paises.most_common(1)[0][0] if paises else None
        for c in casamentos:
            for v in c.vinculos:
                self.global_(v, aprendido, pais_do_corpus)
        return casamentos
