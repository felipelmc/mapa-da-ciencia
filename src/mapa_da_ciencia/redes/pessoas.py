"""Quem é quem: as autorias do corpus agrupadas em pessoas.

Cada autoria (um autor num documento) junta o nome da ArticleMeta com a autoria do OpenAlex alinhada a ele (pela
posição e pelo nome, como na geografia), de onde vêm o id do autor no OpenAlex, o ORCID e as instituições. As
autorias viram pessoas num *union-find*, em ordem de confiança (o raciocínio e as taxas medidas no piloto estão no
ADR 0014):

0. o ORCID é conferido antes: quando a ArticleMeta e o OpenAlex dão ORCIDs diferentes à mesma autoria, nenhum dos
   dois vale; e um ORCID que aparece em autorias de nomes incompatíveis fica só com o maior grupo de nomes
   compatíveis (um ORCID trocado na fonte juntava pessoas diferentes);
1. o mesmo id do OpenAlex, e depois o mesmo ORCID. Dois ORCIDs diferentes não separam uma pessoa: no piloto, os ids
   do OpenAlex com dois ORCIDs eram a mesma pessoa com dois registros no ORCID, ou um ORCID trocado. Esses casos vão
   para a revisão, e um id do OpenAlex nunca fica em duas pessoas (salvo um `nao_fundir` explícito);
2. uma autoria sem id nem ORCID entra na pessoa com o mesmo nome, se houver exatamente uma;
3. duas pessoas com o mesmo nome, ou com grafias variantes (o mesmo primeiro nome, e as partes de um nome contidas
   nas do outro: "Marjorie Marona" e "Marjorie Corrêa Marona"), se juntam quando têm um coautor ou uma instituição
   em comum, e desde que todo nome de uma seja comparável com todo nome da outra, aceitas as iniciais (assim "Ana
   Silva" não emenda "Ana Maria Silva" com "Ana Paula Silva", e "J. Feres Jr." continua comparável com "João Feres
   Júnior").

O resto dos homônimos e das grafias variantes vira `candidatos`, que `mapa redes --revisar` lista com as evidências
para o `pessoas.yaml` do projeto: `fundir` junta, `nao_fundir` separa (e desfaz uma fusão automática) e `nomes` troca
o nome exibido. Ali vale o id de qualquer autoria da pessoa: `openalex:A…`, `orcid:…`, `nome:…` (o nome na forma de
comparação) ou `<documento>#<posição>` (uma autoria só, para tirá-la de uma pessoa). Um id que não existe no corpus
vira aviso.

O id interno de uma pessoa é o menor id do OpenAlex dela, senão o ORCID, senão o nome; o id publicado é um HMAC curto
dele, com o segredo do projeto (`segredos.segredo`): o site não publica ORCIDs nem ids do OpenAlex, e o id publicado
não se liga a eles sem o segredo.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from ..config import ErroConfig
from ..documento import Documento
from ..geografia import normalizar
from ..geografia.casamento import alinhar, nomes_compativeis

ARQUIVO_PESSOAS = "pessoas.yaml"
_PARTICULAS = {"de", "da", "do", "dos", "das", "e", "d"}
_ORCID = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$", re.IGNORECASE)


_SUFIXOS = {"jr": "junior"}


def chave_nome(nome: str | None) -> str:
    """Nome na forma de comparação: sem acentos, minúsculas, sem partículas, com "Jr." como "Júnior"."""
    return " ".join(_SUFIXOS.get(p, p) for p in normalizar.chave(nome or "").split() if p not in _PARTICULAS)


def variantes(a: str, b: str) -> bool:
    """Duas chaves de nome diferentes que podem ser grafias da mesma pessoa: o mesmo primeiro nome, pelo menos duas
    partes cada, e as partes de uma contidas nas da outra ("marjorie marona" e "marjorie correa marona")."""
    pa, pb = a.split(), b.split()
    if a == b or len(pa) < 2 or len(pb) < 2 or pa[0] != pb[0]:
        return False
    return set(pa) <= set(pb) or set(pb) <= set(pa)


def _mesma_parte(p: str, q: str) -> bool:
    """Duas partes de nome iguais, ou uma inicial da outra ("j" e "joao")."""
    return p == q or (len(p) == 1 and q.startswith(p)) or (len(q) == 1 and p.startswith(q))


def _contido(menor: list[str], maior: list[str]) -> bool:
    livres = list(maior)
    for p in menor:
        achada = next((q for q in livres if _mesma_parte(p, q)), None)
        if achada is None:
            return False
        livres.remove(achada)
    return True


def _comparaveis(a: str, b: str) -> bool:
    """Dois nomes que podem ser da mesma pessoa: o mesmo primeiro nome (ou a inicial dele), e as partes de um contidas
    nas do outro, aceitando iniciais ("j feres junior" e "joao feres junior"). "ana maria silva" e "ana paula silva"
    não são: cada um tem uma parte que o outro não tem."""
    pa, pb = a.split(), b.split()
    if not pa or not pb or not _mesma_parte(pa[0], pb[0]):
        return False
    return _contido(pa, pb) or _contido(pb, pa)


def id_publicado(interno: str, segredo: bytes) -> str:
    """ "p" e 10 dígitos hexadecimais do HMAC-SHA256 do id interno. Estável enquanto a pessoa tiver o mesmo id interno
    e o projeto o mesmo segredo; uma fusão ou uma separação no `pessoas.yaml` pode mudá-lo."""
    return "p" + hmac.new(segredo, interno.encode("utf-8"), hashlib.sha256).hexdigest()[:10]


@dataclass(frozen=True)
class Autoria:
    doc: str
    posicao: int
    nome: str
    openalex: str | None
    orcid: str | None
    instituicoes: frozenset[str] = frozenset()

    @property
    def chave(self) -> str:
        return chave_nome(self.nome)

    @property
    def id(self) -> str:
        """O id desta autoria no `pessoas.yaml`."""
        return f"{self.doc}#{self.posicao}"


def _mesmo_orcid(a: str | None, b: str | None) -> bool:
    return (a or "").upper() == (b or "").upper()


def _insts(oa) -> frozenset[str]:
    return frozenset(x for i in (oa.instituicoes if oa else []) for x in (i.id, *i.linhagem))


def autorias_do_corpus(documentos: list[Documento]) -> tuple[list[Autoria], int]:
    """Uma autoria por autor de cada documento, com o id do OpenAlex, o ORCID e as instituições do OpenAlex (com as de
    cima na linhagem) quando se sabe. Devolve também quantas autorias tinham ORCIDs diferentes na ArticleMeta e no
    OpenAlex (e ficaram sem nenhum)."""
    saida, divergentes = [], 0
    for d in documentos:
        if d.autores:
            pares = alinhar(d.autores, d.autorias_openalex) if d.autorias_openalex else {}
            for i, a in enumerate(d.autores):
                oa = d.autorias_openalex[pares[i]] if i in pares else None
                nome = " ".join(x for x in (a.nome, a.sobrenome) if x).strip() or (oa.nome if oa else "") or ""
                if not nome:
                    continue
                orcid = a.orcid or (oa.orcid if oa else None)
                if a.orcid and oa and oa.orcid and not _mesmo_orcid(a.orcid, oa.orcid):
                    orcid, divergentes = None, divergentes + 1
                saida.append(Autoria(d.id, i, nome, oa.id if oa else None, orcid, _insts(oa)))
        else:
            for j, oa in enumerate(d.autorias_openalex):
                if oa.nome:
                    saida.append(Autoria(d.id, j, oa.nome, oa.id, oa.orcid, _insts(oa)))
    return saida, divergentes


class CorrecoesPessoas(BaseModel):
    """O `pessoas.yaml` do projeto: correções manuais da identidade das pessoas."""

    model_config = ConfigDict(extra="forbid")
    fundir: list[list[str]] = Field(
        default_factory=list,
        description="Grupos de ids que são a mesma pessoa: `openalex:A…`, `orcid:…`, `nome:…` ou "
        "`<documento>#<posição>`.",
    )
    nao_fundir: list[list[str]] = Field(
        default_factory=list,
        description="Pares de ids que são pessoas diferentes (separa até o que a etapa juntou sozinha).",
    )
    nomes: dict[str, str] = Field(default_factory=dict, description="Id de uma autoria da pessoa → nome a exibir.")

    @model_validator(mode="before")
    @classmethod
    def _vazios(cls, dados: Any) -> Any:
        """Uma lista sem itens (`fundir:` só com linhas comentadas, como sai da revisão) vale como vazia."""
        if isinstance(dados, dict):
            return {k: v for k, v in dados.items() if v is not None}
        return dados


def _erro_legivel(e: ValidationError) -> str:
    partes = []
    for erro in e.errors():
        onde = ".".join(str(x) for x in erro["loc"])
        if erro["type"] == "extra_forbidden":
            partes.append(f"`{onde}` não é um campo do pessoas.yaml (use fundir, nao_fundir e nomes)")
        elif erro["loc"] and erro["loc"][0] in ("fundir", "nao_fundir"):
            partes.append(f"em `{onde}`, cada item é uma lista de ids entre colchetes, como [openalex:A1, openalex:A2]")
        else:
            partes.append(f"em `{onde}`, o valor não serve ({erro['msg']})")
    return "; ".join(dict.fromkeys(partes))


def ler_correcoes(raiz: Path) -> CorrecoesPessoas:
    arquivo = raiz / ARQUIVO_PESSOAS
    if not arquivo.exists():
        return CorrecoesPessoas()
    try:
        return CorrecoesPessoas.model_validate(yaml.safe_load(arquivo.read_text(encoding="utf-8")) or {})
    except yaml.YAMLError as e:
        raise ErroConfig(f"{ARQUIVO_PESSOAS} não é um YAML válido: {e}") from e
    except ValidationError as e:
        raise ErroConfig(f"{ARQUIVO_PESSOAS}: {_erro_legivel(e)}.") from e


class _Grupos:
    """Union-find com as marcas das restrições do `nao_fundir` (os dois lados de uma restrição nunca se juntam, salvo
    num `fundir`) e as chaves de nome de cada grupo."""

    def __init__(self, autorias: list[Autoria]) -> None:
        self.pai = list(range(len(autorias)))
        self.marcas: list[set[tuple[int, int]]] = [set() for _ in autorias]
        self.chaves: list[set[str]] = [{a.chave} if a.chave else set() for a in autorias]

    def achar(self, i: int) -> int:
        while self.pai[i] != i:
            self.pai[i] = self.pai[self.pai[i]]
            i = self.pai[i]
        return i

    def pode(self, a: int, b: int) -> bool:
        m = self.marcas[self.achar(a)] | self.marcas[self.achar(b)]
        return not any((k, 1 - lado) in m for k, lado in m)

    def unir(self, a: int, b: int, *, forcar: bool = False) -> bool:
        ra, rb = self.achar(a), self.achar(b)
        if ra == rb:
            return True
        if not forcar and not self.pode(ra, rb):
            return False
        ra, rb = min(ra, rb), max(ra, rb)
        self.pai[rb] = ra
        self.marcas[ra] |= self.marcas[rb]
        self.chaves[ra] |= self.chaves[rb]
        return True


@dataclass
class Pessoa:
    interno: str
    publicado: str
    nome: str
    autorias: list[int]  # índices em `Identidade.autorias`
    openalex: list[str]
    orcids: list[str]
    via: str  # openalex | orcid | nome


@dataclass
class Candidato:
    """Duas pessoas que podem ser a mesma: homônimos ou grafias variantes que a etapa deixou separados."""

    a: str  # ids internos
    b: str
    nome: str
    tipo: str  # homonimo | variante


@dataclass
class Identidade:
    autorias: list[Autoria]
    pessoas: list[Pessoa]
    pessoa_da_autoria: list[int]  # autoria → índice da pessoa
    candidatos: list[Candidato] = field(default_factory=list)
    conflitos: int = 0  # pessoas com mais de um ORCID (vão para a revisão)
    orcids_retirados: list[tuple[int, str]] = field(default_factory=list)  # (autoria, ORCID de outro nome)
    orcids_divergentes: int = 0  # autorias com ORCIDs diferentes na ArticleMeta e no OpenAlex
    avisos: list[str] = field(default_factory=list)


def _limpar_orcids(autorias: list[Autoria]) -> tuple[list[Autoria], list[tuple[int, str]]]:
    """Cada ORCID fica só com o maior grupo de autorias de nomes compatíveis entre si (no empate, o da autoria de menor
    id); as outras perdem o ORCID. Um ORCID trocado na fonte ("Marcelo Kunrath Silva" com o ORCID de "Matheus
    Mazzilli Pereira") não junta mais duas pessoas."""
    por_orcid: dict[str, list[int]] = defaultdict(list)
    for i, a in enumerate(autorias):
        if a.orcid:
            por_orcid[a.orcid.upper()].append(i)
    retirados: list[tuple[int, str]] = []
    saida = list(autorias)
    for orcid, idx in sorted(por_orcid.items()):
        nomes = sorted({autorias[i].nome for i in idx})
        if len(nomes) == 1:
            continue
        pai = {n: n for n in nomes}

        def raiz(n: str, pai: dict[str, str] = pai) -> str:
            while pai[n] != n:
                n = pai[n]
            return n

        for x in range(len(nomes)):
            for y in range(x + 1, len(nomes)):
                if chave_nome(nomes[x]) == chave_nome(nomes[y]) or nomes_compativeis(nomes[x], nomes[y]):
                    pai[raiz(nomes[y])] = raiz(nomes[x])
        grupos: dict[str, list[int]] = defaultdict(list)
        for i in idx:
            grupos[raiz(autorias[i].nome)].append(i)
        if len(grupos) == 1:
            continue
        fica = min(grupos.values(), key=lambda g: (-len(g), min(autorias[i].id for i in g)))
        for g in grupos.values():
            if g is fica:
                continue
            for i in g:
                retirados.append((i, orcid))
                a = autorias[i]
                saida[i] = Autoria(a.doc, a.posicao, a.nome, a.openalex, None, a.instituicoes)
    return saida, retirados


def _resolver(autorias: list[Autoria]) -> dict[str, set[int]]:
    """Id do `pessoas.yaml` → autorias: o id do OpenAlex, o ORCID, a chave do nome e o id da autoria."""
    ids: dict[str, set[int]] = defaultdict(set)
    for i, a in enumerate(autorias):
        ids[a.id].add(i)
        if a.openalex:
            ids[f"openalex:{a.openalex}"].add(i)
        if a.orcid:
            ids[f"orcid:{a.orcid.upper()}"].add(i)
        if a.chave:
            ids[f"nome:{a.chave}"].add(i)
    return ids


def _normalizar_id(x: str) -> str:
    x = str(x).strip()
    if x.lower().startswith("orcid:"):
        return "orcid:" + x[6:].strip().upper()
    return x.removeprefix("autoria:")


def _dica(x: str, conhecidos: dict[str, set[int]]) -> str:
    if re.fullmatch(r"A\d+", x) and f"openalex:{x}" in conhecidos:
        return f"{x} (falta o prefixo: openalex:{x})"
    if _ORCID.match(x) and f"orcid:{x.upper()}" in conhecidos:
        return f"{x} (falta o prefixo: orcid:{x})"
    if x.startswith("nome:") and f"nome:{chave_nome(x[5:])}" in conhecidos:
        return f"{x} (escreva nome:{chave_nome(x[5:])}, sem acentos nem partículas)"
    return x


def identificar(
    documentos: list[Documento],
    correcoes: CorrecoesPessoas | None = None,
    *,
    segredo: bytes,
    instituicoes: dict[tuple[str, int], set[str]] | None = None,
) -> Identidade:
    """As pessoas do corpus. `instituicoes`: (documento, posição do autor) → instituições casadas pela geografia, que
    se somam às do OpenAlex na regra 3."""
    correcoes = correcoes or CorrecoesPessoas()
    brutas, divergentes = autorias_do_corpus(documentos)
    if instituicoes:
        brutas = [
            Autoria(a.doc, a.posicao, a.nome, a.openalex, a.orcid, a.instituicoes | instituicoes[(a.doc, a.posicao)])
            if (a.doc, a.posicao) in instituicoes
            else a
            for a in brutas
        ]
    autorias, retirados = _limpar_orcids(brutas)
    conhecidos = _resolver(brutas)
    avisos: list[str] = []
    desconhecidos: list[str] = []

    def lado(x: str) -> set[int]:
        achados = conhecidos.get(_normalizar_id(x))
        if not achados:
            desconhecidos.append(_dica(str(x), conhecidos))
            return set()
        return set(achados)

    g = _Grupos(autorias)
    # as restrições do nao_fundir; o lado mais específico ganha (uma autoria sai do id do OpenAlex que a contém)
    for k, par in enumerate(correcoes.nao_fundir):
        if len(par) != 2:
            avisos.append(f"{ARQUIVO_PESSOAS}: cada item de nao_fundir é um par de ids ({par} tem {len(par)}).")
            continue
        x, y = lado(par[0]), lado(par[1])
        if not x or not y:
            continue
        if comum := x & y:
            if x == y:
                avisos.append(f"{ARQUIVO_PESSOAS}: nao_fundir {par} aponta as mesmas autorias dos dois lados.")
                continue
            if len(x) >= len(y):
                x -= comum
            else:
                y -= comum
        for i in x:
            g.marcas[i].add((k, 0))
        for i in y:
            g.marcas[i].add((k, 1))

    # 1. o mesmo id do OpenAlex e o mesmo ORCID (já conferido pelo nome)
    for atributo in ("openalex", "orcid"):
        primeiro: dict[str, int] = {}
        for i, a in enumerate(autorias):
            valor = getattr(a, atributo)
            if not valor:
                continue
            valor = valor.upper() if atributo == "orcid" else valor
            if valor in primeiro:
                g.unir(primeiro[valor], i)
            else:
                primeiro[valor] = i

    # 2. sem id nem ORCID: a pessoa com o mesmo nome, se houver só uma
    por_nome: dict[str, set[int]] = defaultdict(set)
    for i, a in enumerate(autorias):
        if a.openalex or a.orcid:
            por_nome[a.chave].add(g.achar(i))
    for i, a in enumerate(autorias):
        if a.openalex or a.orcid or not a.chave:
            continue
        grupos = {g.achar(j) for j in por_nome.get(a.chave, set())}
        if len(grupos) == 1 and g.unir(next(iter(grupos)), i):
            continue
        por_nome[a.chave].add(g.achar(i))

    # 3. homônimos e grafias variantes com um coautor ou uma instituição em comum
    _regra_dos_nomes(autorias, g)

    # correções manuais: `fundir` junta (mesmo contra um nao_fundir, com aviso)
    for grupo in correcoes.fundir:
        membros = [m for m in (lado(x) for x in grupo) if m]
        if len(membros) < 2:
            continue
        base = next(iter(membros[0]))
        contrariou = False
        for m in membros[1:]:
            for i in m:
                contrariou |= not g.pode(base, i)
                g.unir(base, i, forcar=True)
        if contrariou:
            avisos.append(f"{ARQUIVO_PESSOAS}: fundir {grupo} contraria um nao_fundir; valeu o fundir.")

    grupos_finais: dict[int, list[int]] = defaultdict(list)
    for i in range(len(autorias)):
        grupos_finais[g.achar(i)].append(i)
    internos = _internos(autorias, grupos_finais)
    nomes_manuais: dict[int, str] = {}
    for x, nome in correcoes.nomes.items():
        raizes = {g.achar(i) for i in lado(x)}
        if len(raizes) > 1:
            avisos.append(
                f"{ARQUIVO_PESSOAS}: o id {x} de `nomes` está em {len(raizes)} pessoas; use o id de uma autoria."
            )
        for r in raizes:
            nomes_manuais[r] = nome
    if desconhecidos:
        lista = "; ".join(dict.fromkeys(desconhecidos))
        avisos.append(
            f"{ARQUIVO_PESSOAS}: {len(dict.fromkeys(desconhecidos))} id(s) não existem no corpus e ficaram sem "
            f"efeito: {lista}."
        )

    pessoas: list[Pessoa] = []
    pessoa_da_autoria = [0] * len(autorias)
    for raiz, membros in sorted(grupos_finais.items(), key=lambda kv: internos[kv[0]][0]):
        interno, via = internos[raiz]
        nome = nomes_manuais.get(raiz) or _nome_exibido(Counter(autorias[i].nome for i in membros))
        for i in membros:
            pessoa_da_autoria[i] = len(pessoas)
        pessoas.append(
            Pessoa(
                interno,
                id_publicado(interno, segredo),
                nome,
                sorted(membros),
                sorted({autorias[i].openalex for i in membros if autorias[i].openalex}),
                sorted({autorias[i].orcid.upper() for i in membros if autorias[i].orcid}),
                via,
            )
        )
    candidatos = _candidatos(pessoas, autorias, correcoes, conhecidos, pessoa_da_autoria)
    return Identidade(
        autorias,
        pessoas,
        pessoa_da_autoria,
        candidatos,
        conflitos=sum(1 for p in pessoas if len(p.orcids) > 1),
        orcids_retirados=retirados,
        orcids_divergentes=divergentes,
        avisos=avisos,
    )


def _nome_exibido(contagem: Counter[str]) -> str:
    """O nome mais frequente; no empate, o que não está todo em maiúsculas, e depois a ordem alfabética."""
    return sorted(contagem.items(), key=lambda kv: (-kv[1], kv[0].isupper(), kv[0]))[0][0]


def _regra_dos_nomes(autorias: list[Autoria], g: _Grupos) -> None:
    """Regra 3, até não mudar mais: pares de grupos com um nome igual ou variante e um coautor ou uma instituição em
    comum, desde que todos os nomes de um sejam comparáveis com todos os do outro."""
    mudou = True
    while mudou:
        mudou = False
        docs: dict[int, set[str]] = defaultdict(set)
        insts: dict[int, set[str]] = defaultdict(set)
        grupos_do_doc: dict[str, set[int]] = defaultdict(set)
        for i, a in enumerate(autorias):
            r = g.achar(i)
            docs[r].add(a.doc)
            insts[r] |= a.instituicoes
            grupos_do_doc[a.doc].add(r)
        por_primeiro: dict[str, set[int]] = defaultdict(set)
        for r in docs:
            for chave in g.chaves[r]:
                por_primeiro[chave.split()[0]].add(r)
        for primeiro in sorted(por_primeiro):
            lista = sorted(por_primeiro[primeiro])
            for x in range(len(lista)):
                for y in range(x + 1, len(lista)):
                    ra, rb = g.achar(lista[x]), g.achar(lista[y])
                    if ra == rb:
                        continue
                    ca, cb = g.chaves[ra], g.chaves[rb]
                    if not all(_comparaveis(p, q) for p in ca for q in cb):
                        continue
                    coautores_a = {g.achar(h) for d in docs[ra] for h in grupos_do_doc[d]} - {ra}
                    coautores_b = {g.achar(h) for d in docs[rb] for h in grupos_do_doc[d]} - {rb}
                    if (coautores_a & coautores_b or insts[ra] & insts[rb]) and g.unir(ra, rb):
                        raiz = g.achar(ra)
                        docs[raiz] = docs[ra] | docs[rb]
                        insts[raiz] = insts[ra] | insts[rb]
                        for d in docs[raiz]:
                            grupos_do_doc[d] = {g.achar(h) for h in grupos_do_doc[d]}
                        mudou = True


def _opcoes_de_interno(membros: list[Autoria]) -> list[tuple[str, str]]:
    """Os ids internos possíveis de um grupo, do preferido ao último: os ids do OpenAlex, os ORCIDs e o nome."""
    saida = [(f"openalex:{x}", "openalex") for x in sorted({a.openalex for a in membros if a.openalex})]
    saida += [(f"orcid:{x}", "orcid") for x in sorted({a.orcid.upper() for a in membros if a.orcid})]
    return saida or [(f"nome:{membros[0].chave}", "nome")]


def _internos(autorias: list[Autoria], grupos: dict[int, list[int]]) -> dict[int, tuple[str, str]]:
    """O id interno de cada grupo, único: quando o preferido já é de outro grupo (um id do OpenAlex separado por um
    `nao_fundir`, dois homônimos só com o nome), vale o próximo, ou o preferido com o documento mais antigo."""
    opcoes = {raiz: _opcoes_de_interno([autorias[i] for i in membros]) for raiz, membros in grupos.items()}
    usados: set[str] = set()
    saida: dict[int, tuple[str, str]] = {}
    # os grupos maiores escolhem primeiro: o id do OpenAlex fica com quem tem mais autorias
    for raiz in sorted(grupos, key=lambda r: (-len(grupos[r]), min(autorias[i].id for i in grupos[r]))):
        escolhido = next((o for o in opcoes[raiz] if o[0] not in usados), None)
        if escolhido is None:
            interno, via = opcoes[raiz][0]
            escolhido = (f"{interno}#{min(autorias[i].doc for i in grupos[raiz])}", via)
        usados.add(escolhido[0])
        saida[raiz] = escolhido
    return saida


def _candidatos(
    pessoas: list[Pessoa],
    autorias: list[Autoria],
    correcoes: CorrecoesPessoas,
    conhecidos: dict[str, set[int]],
    pessoa_da_autoria: list[int],
) -> list[Candidato]:
    """Pares de pessoas com um nome igual (homônimos) ou variante que ficaram separadas, fora os do `nao_fundir`."""
    nao: set[frozenset[int]] = set()
    for par in correcoes.nao_fundir:
        if len(par) == 2:
            a = {pessoa_da_autoria[i] for i in conhecidos.get(_normalizar_id(par[0]), ())}
            b = {pessoa_da_autoria[i] for i in conhecidos.get(_normalizar_id(par[1]), ())}
            nao |= {frozenset((x, y)) for x in a for y in b if x != y}
    chaves = [{autorias[i].chave for i in p.autorias if autorias[i].chave} for p in pessoas]
    por_primeiro: dict[str, set[int]] = defaultdict(set)
    for k, cs in enumerate(chaves):
        for c in cs:
            por_primeiro[c.split()[0]].add(k)
    vistos: set[frozenset[int]] = set()
    saida: list[Candidato] = []
    for primeiro in sorted(por_primeiro):
        lista = sorted(por_primeiro[primeiro])
        for x in range(len(lista)):
            for y in range(x + 1, len(lista)):
                a, b = lista[x], lista[y]
                par = frozenset((a, b))
                if par in vistos or par in nao:
                    continue
                if chaves[a] & chaves[b]:
                    tipo = "homonimo"
                elif any(variantes(p, q) for p in chaves[a] for q in chaves[b]):
                    tipo = "variante"
                else:
                    continue
                vistos.add(par)
                saida.append(Candidato(pessoas[a].interno, pessoas[b].interno, pessoas[a].nome, tipo))
    return sorted(saida, key=lambda c: (c.tipo != "homonimo", chave_nome(c.nome), c.a, c.b))
