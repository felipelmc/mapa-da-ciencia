"""Contagem fracionária da produção, com a UF e o país de cada vínculo.

**Pesos** (glossário): cada documento vale 1, dividido igualmente entre os autores e, para cada autor, entre as
afiliações dele.

- Um autor sem afiliação fica com as afiliações que nenhum autor cita (as "órfãs", quando a fonte não diz de quem
  é cada uma); sem órfãs, a parte dele vai para **sem afiliação** (não é redistribuída entre os coautores).
- Órfãs que sobram quando todos os autores já têm afiliação entram na lista de cada autor: a fonte diz que o
  documento tem aquela afiliação, só não diz de quem.
- Um documento sem autores divide o 1 entre as afiliações; sem nenhuma, vai todo para sem afiliação.

Assim a soma dos pesos de cada documento é 1, e a do corpus é o número de documentos.

**País** do vínculo: o da instituição identificada (o casamento já vetou os que discordam da fonte) ou, sem ela, o
que a fonte escreveu.

**UF**, só para vínculos no Brasil, na ordem:

1. a UF que a fonte escreveu (ou que veio junto da cidade: "Niterói, RJ");
2. a cidade da fonte, quando o nome do município é único no país ou é capital; senão, a UF que as afiliações `v240`
   do corpus dão a essa cidade ("São Carlos" → SP);
3. a UF que o `instituicoes.yaml` do projeto dá à instituição;
4. a UF mais comum da instituição nas afiliações `v240` do corpus;
5. a região do registro da instituição no OpenAlex;
6. a cidade do registro no OpenAlex, como no passo 2.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from ..contrato.modelos import NAO_IDENTIFICADA
from . import normalizar
from .casamento import Casamento, Indice, Vinculo

CONCORDANCIA_APRENDIDA = 0.9  # fração das afiliações `v240` que precisam concordar na UF de uma cidade ou instituição
APOIO_APRENDIDO = 2


@dataclass(frozen=True)
class Parcela:
    """Uma linha da tabela longa: o peso de um documento numa instituição, UF e país."""

    doc: str
    instituicao: str | None  # id do OpenAlex ou do projeto; NAO_IDENTIFICADA; None = sem afiliação
    uf: str | None
    pais: str | None
    peso: float


def _consenso(votos: dict[str, Counter[str]]) -> dict[str, str]:
    saida = {}
    for chave, contagem in votos.items():
        uf, n = contagem.most_common(1)[0]
        if n >= APOIO_APRENDIDO and n / sum(contagem.values()) >= CONCORDANCIA_APRENDIDA:
            saida[chave] = uf
    return saida


class Lugares:
    """Decide o país e a UF de cada vínculo, com o que o corpus ensina sobre cidades e instituições."""

    def __init__(self, indice: Indice, casamentos: Iterable[Casamento]) -> None:
        self.indice = indice
        por_cidade: dict[str, Counter[str]] = defaultdict(Counter)
        por_instituicao: dict[str, Counter[str]] = defaultdict(Counter)
        for c in casamentos:
            for v in c.vinculos:
                if v.fonte != "v240" or v.pais_fonte != "BR" or not v.uf_fonte:
                    continue
                if v.cidade_fonte:
                    por_cidade[normalizar.chave(v.cidade_fonte)][v.uf_fonte] += 1
                if v.instituicao:
                    por_instituicao[v.instituicao][v.uf_fonte] += 1
        self._cidades = _consenso(por_cidade)
        self._instituicoes = _consenso(por_instituicao)

    def pais(self, v: Vinculo) -> str | None:
        r = self.indice.registros.get(v.instituicao) if v.instituicao else None
        return (r.pais if r else None) or v.pais_fonte

    def _da_cidade(self, cidade: str | None) -> str | None:
        return normalizar.uf_da_cidade(cidade) or (self._cidades.get(normalizar.chave(cidade)) if cidade else None)

    def uf(self, v: Vinculo, pais: str | None) -> str | None:
        if pais != "BR":
            return None
        if v.uf_fonte:
            return v.uf_fonte
        if uf := self._da_cidade(v.cidade_fonte):
            return uf
        r = self.indice.registros.get(v.instituicao) if v.instituicao else None
        if r is None:
            return None
        return r.uf or self._instituicoes.get(r.id) or normalizar.uf(r.regiao) or self._da_cidade(r.cidade)


def contar(casamentos: list[Casamento], indice: Indice, lugares: Lugares | None = None) -> list[Parcela]:
    """A tabela longa, com uma linha por documento × (instituição, UF, país) e os pesos somados."""
    lugares = lugares or Lugares(indice, casamentos)
    somas: dict[tuple[str, str | None, str | None, str | None], float] = defaultdict(float)

    def parcela(doc: str, v: Vinculo | None, peso: float) -> None:
        if v is None:
            somas[(doc, None, None, None)] += peso
            return
        pais = lugares.pais(v)
        somas[(doc, v.instituicao or NAO_IDENTIFICADA, lugares.uf(v, pais), pais)] += peso

    for c in casamentos:
        por_autor: dict[int, list[Vinculo]] = defaultdict(list)
        orfas: list[Vinculo] = []
        for v in c.vinculos:
            (orfas if v.autor is None else por_autor[v.autor]).append(v)
        if c.n_autores == 0:
            for v in orfas or [None]:
                parcela(c.doc, v, 1 / max(1, len(orfas)))
            continue
        sem_afiliacao = [a for a in range(c.n_autores) if not por_autor.get(a)]
        for a in range(c.n_autores):
            proprias = por_autor.get(a, [])
            vinculos = (proprias + orfas) if (proprias and not sem_afiliacao) else (proprias or orfas)
            for v in vinculos or [None]:
                parcela(c.doc, v, 1 / c.n_autores / max(1, len(vinculos)))
    return [Parcela(doc, inst, uf, pais, peso) for (doc, inst, uf, pais), peso in sorted(somas.items(), key=_ordem)]


def _ordem(item: tuple[tuple[str, str | None, str | None, str | None], float]) -> tuple[str, ...]:
    return tuple(x or "" for x in item[0])


@dataclass
class Cobertura:
    """Quanto do peso tem país, UF e instituição conhecidos."""

    documentos: int
    peso_total: float
    sem_afiliacao: float
    pais_conhecido: float  # fração do peso com afiliação
    uf_conhecida: float  # fração do peso brasileiro
    identificada: float  # fração do peso com afiliação


def cobertura(parcelas: list[Parcela]) -> Cobertura:
    total = sum(p.peso for p in parcelas)
    com = [p for p in parcelas if p.instituicao is not None]
    peso_com = sum(p.peso for p in com) or 1.0
    brasil = [p for p in com if p.pais == "BR"]
    peso_br = sum(p.peso for p in brasil) or 1.0
    return Cobertura(
        documentos=len({p.doc for p in parcelas}),
        peso_total=total,
        sem_afiliacao=total - sum(p.peso for p in com),
        pais_conhecido=sum(p.peso for p in com if p.pais) / peso_com,
        uf_conhecida=sum(p.peso for p in brasil if p.uf) / peso_br,
        identificada=sum(p.peso for p in com if p.instituicao != NAO_IDENTIFICADA) / peso_com,
    )
