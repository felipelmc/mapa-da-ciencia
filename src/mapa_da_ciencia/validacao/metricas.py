"""Métricas de concordância da validação, por variável e por par de participantes.

Um **participante** é um codificador (`humano` ou `referencia`, ver `amostra.py`) ou um modelo que classificou a
amostra (`modelo`, um por resultado em `dados/classificacao/` com o codebook atual). Para cada variável e cada par
(codificador × modelo, codificador × codificador, modelo × modelo), sobre os documentos da amostra que os dois
responderam:

- **concordância**: a fração de respostas iguais;
- **kappa de Cohen**, com intervalo de 95% por *bootstrap* percentil (reamostrando documentos, semente fixa);
- **PABAK** (kappa ajustado para prevalência e viés): `(k·p_o − 1) / (k − 1)`, com `k` categorias no codebook;
- **alfa de Krippendorff** nominal;
- **matriz de confusão** e **precisão, revocação e F1 por classe**, tomando o primeiro do par como referência.

Nas variáveis de múltipla escolha, cada categoria vira uma variável sim/não (`variavel:categoria`). Nas de texto,
só a concordância, depois de normalizar maiúsculas e espaços.

Entre dois modelos comparados com a mesma referência, o **teste de McNemar exato** diz se a diferença de acertos
é maior que o acaso: conta só os documentos em que um acertou e o outro errou.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any, Literal

import numpy as np

from ..classificacao.resultado import PASTA as PASTA_CLASSIFICACAO
from ..classificacao.resultado import ler_linhas, resultados
from ..config import ErroConfig
from ..projeto import Projeto
from . import amostra as va

REAMOSTRAS = 1000
TipoParticipante = Literal["humano", "referencia", "modelo"]


# ---------------------------------------------------------------- métricas de um par
def _indices(a: Sequence[str], b: Sequence[str], rotulos: Sequence[str] = ()) -> tuple[np.ndarray, np.ndarray, list]:
    """Os valores como índices em `rotulos` (os do codebook primeiro, depois os que aparecerem a mais)."""
    todos = list(dict.fromkeys([*rotulos, *a, *b]))
    pos = {r: i for i, r in enumerate(todos)}
    return np.array([pos[x] for x in a], dtype=np.int64), np.array([pos[x] for x in b], dtype=np.int64), todos


def concordancia(a: Sequence[str], b: Sequence[str]) -> float | None:
    if not a:
        return None
    return sum(x == y for x, y in zip(a, b, strict=True)) / len(a)


def _kappa_de(ia: np.ndarray, ib: np.ndarray, k: int) -> np.ndarray:
    """Kappa de Cohen de cada linha de `ia` × `ib` (matrizes reamostras × n); NaN quando indefinido."""
    po = (ia == ib).mean(axis=-1)
    pa = np.stack([(ia == c).mean(axis=-1) for c in range(k)], axis=-1)
    pb = np.stack([(ib == c).mean(axis=-1) for c in range(k)], axis=-1)
    pe = (pa * pb).sum(axis=-1)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(np.isclose(pe, 1.0), np.nan, (po - pe) / (1.0 - pe))


def kappa(a: Sequence[str], b: Sequence[str]) -> float | None:
    """Kappa de Cohen; `None` quando indefinido (os dois deram sempre a mesma resposta)."""
    if not a:
        return None
    ia, ib, rotulos = _indices(a, b)
    valor = float(_kappa_de(ia, ib, len(rotulos)))
    return None if math.isnan(valor) else valor


def kappa_ic95(
    a: Sequence[str], b: Sequence[str], *, reamostras: int = REAMOSTRAS, semente: int = 7
) -> tuple[float, float] | None:
    """Intervalo de 95% do kappa por *bootstrap* percentil, reamostrando os documentos; `None` com menos de 10
    documentos ou quando o kappa fica indefinido em mais da metade das reamostras."""
    n = len(a)
    if n < 10:
        return None
    ia, ib, rotulos = _indices(a, b)
    idx = np.random.default_rng(semente).integers(0, n, size=(reamostras, n))
    valores = _kappa_de(ia[idx], ib[idx], len(rotulos))
    valores = valores[~np.isnan(valores)]
    if len(valores) < reamostras / 2:
        return None
    baixo, alto = np.percentile(valores, [2.5, 97.5])
    return float(baixo), float(alto)


def pabak(a: Sequence[str], b: Sequence[str], k: int) -> float | None:
    po = concordancia(a, b)
    if po is None or k < 2:
        return None
    return (k * po - 1) / (k - 1)


def alfa_nominal(unidades: Sequence[Sequence[str | None]]) -> float | None:
    """Alfa de Krippendorff nominal. `unidades` tem uma lista por documento, com a resposta de cada participante
    (`None` quando ele não respondeu). Documentos com menos de duas respostas não contam. `None` quando não há
    variação nenhuma (o alfa fica indefinido)."""
    valores = [[v for v in u if v is not None] for u in unidades]
    valores = [u for u in valores if len(u) >= 2]
    rotulos = sorted({v for u in valores for v in u})
    if not valores:
        return None
    pos = {r: i for i, r in enumerate(rotulos)}
    k = len(rotulos)
    coincid = np.zeros((k, k))
    for u in valores:
        contagem = np.bincount([pos[v] for v in u], minlength=k).astype(float)
        coincid += (np.outer(contagem, contagem) - np.diag(contagem)) / (len(u) - 1)
    n_c = coincid.sum(axis=1)
    n = n_c.sum()
    fora = ~np.eye(k, dtype=bool)
    esperado = (np.outer(n_c, n_c)[fora]).sum()
    if esperado == 0:
        return None
    return float(1 - (n - 1) * coincid[fora].sum() / esperado)


def matriz_confusao(referencia: Sequence[str], outro: Sequence[str], rotulos: Sequence[str]) -> list[list[int]]:
    """Linhas = a referência; colunas = o outro participante."""
    pos = {r: i for i, r in enumerate(rotulos)}
    m = np.zeros((len(rotulos), len(rotulos)), dtype=np.int64)
    for x, y in zip(referencia, outro, strict=True):
        m[pos[x], pos[y]] += 1
    return m.tolist()


@dataclass
class Classe:
    """Precisão, revocação e F1 de uma categoria, tomando o primeiro do par como referência."""

    rotulo: str
    suporte: int  # quantas vezes a referência deu esta categoria
    precisao: float | None  # None quando o outro nunca deu esta categoria
    revocacao: float | None  # None quando a referência nunca deu esta categoria
    f1: float | None


def por_classe(matriz: list[list[int]], rotulos: Sequence[str]) -> list[Classe]:
    m = np.array(matriz)
    saida = []
    for i, rotulo in enumerate(rotulos):
        acertos, linha, coluna = int(m[i, i]), int(m[i].sum()), int(m[:, i].sum())
        p = acertos / coluna if coluna else None
        r = acertos / linha if linha else None
        f1 = 2 * acertos / (linha + coluna) if linha + coluna else None
        saida.append(Classe(rotulo, linha, p, r, f1))
    return saida


def mcnemar_exato(so_a: int, so_b: int) -> float:
    """Valor-p bicaudal do teste de McNemar exato: `so_a` documentos em que só o primeiro modelo acertou, `so_b`
    em que só o segundo acertou."""
    n = so_a + so_b
    if n == 0:
        return 1.0
    cauda = sum(math.comb(n, i) for i in range(min(so_a, so_b) + 1)) / 2**n
    return min(1.0, 2 * cauda)


# ---------------------------------------------------------------- variáveis
@dataclass(frozen=True)
class VariavelMedida:
    """Uma variável do codebook como é medida: as de múltipla escolha viram uma por categoria."""

    id: str
    variavel: str  # id no codebook
    rotulos: tuple[str, ...]  # vazio nas de texto
    extrair: Callable[[str], str]

    @property
    def texto(self) -> bool:
        return not self.rotulos


def _normalizar_texto(valor: str) -> str:
    return " ".join(valor.casefold().split())


_COMPARAR: dict[str, Callable[[str], str]] = {
    "texto": _normalizar_texto,
    "multipla": lambda valor: json.dumps(sorted(json.loads(valor))),
}


def _tem(categoria: str) -> Callable[[str], str]:
    return lambda valor: "true" if categoria in json.loads(valor) else "false"


def variaveis_medidas(codebook) -> list[VariavelMedida]:
    saida = []
    for v in codebook.variaveis:
        if v.tipo == "categorica":
            saida.append(VariavelMedida(v.id, v.id, tuple(c.valor for c in v.categorias), str))
        elif v.tipo == "booleana":
            saida.append(VariavelMedida(v.id, v.id, ("true", "false"), str))
        elif v.tipo == "multipla":
            for c in v.categorias:
                saida.append(VariavelMedida(f"{v.id}:{c.valor}", v.id, ("true", "false"), _tem(c.valor)))
        else:
            saida.append(VariavelMedida(v.id, v.id, (), _normalizar_texto))
    return saida


# ---------------------------------------------------------------- validação do projeto
@dataclass(frozen=True)
class Participante:
    nome: str
    tipo: TipoParticipante
    n: int  # documentos da amostra com resposta


@dataclass
class Metrica:
    """A concordância de um par de participantes numa variável."""

    variavel: str
    referencia: str
    comparado: str
    n: int
    concordancia: float | None
    kappa: float | None = None
    kappa_ic95: tuple[float, float] | None = None
    pabak: float | None = None
    alfa: float | None = None
    rotulos: list[str] = field(default_factory=list)
    matriz: list[list[int]] = field(default_factory=list)
    por_classe: list[Classe] = field(default_factory=list)

    @property
    def comparacao(self) -> str:
        return f"{self.referencia} × {self.comparado}"


@dataclass
class ComparacaoModelos:
    """McNemar exato entre dois modelos, contra a mesma referência, numa variável."""

    variavel: str
    referencia: str
    modelo_a: str
    modelo_b: str
    n: int
    acertos_a: int
    acertos_b: int
    so_a: int
    so_b: int
    p: float


@dataclass
class Divergencia:
    """Um documento em que um codificador e o modelo principal discordam."""

    doc: str
    variavel: str
    codificador: str
    valor_codificador: str
    valor_modelo: str
    evidencia_modelo: str
    status_evidencia: str
    evidencia_codificador: str = ""
    incerto: bool = False


@dataclass
class Validacao:
    amostra: dict[str, Any]
    codebook: str
    hash_codebook: str
    modelo_principal: str | None
    participantes: list[Participante]
    metricas: list[Metrica]
    comparacoes_modelos: list[ComparacaoModelos]
    divergencias: list[Divergencia]
    evidencia_literal: dict[str, float]  # modelo → fração literal na amostra, sem as dispensadas

    def metrica(self, variavel: str, referencia: str, comparado: str) -> Metrica | None:
        return next(
            (
                m
                for m in self.metricas
                if m.variavel == variavel and {m.referencia, m.comparado} == {referencia, comparado}
            ),
            None,
        )


def medir(
    a: Sequence[str],
    b: Sequence[str],
    v: VariavelMedida,
    referencia: str,
    comparado: str,
    *,
    reamostras: int = REAMOSTRAS,
    semente: int = 7,
) -> Metrica:
    m = Metrica(v.id, referencia, comparado, len(a), concordancia(a, b))
    if v.texto or not a:
        return m
    _, _, rotulos = _indices(a, b, v.rotulos)
    m.kappa = kappa(a, b)
    m.kappa_ic95 = kappa_ic95(a, b, reamostras=reamostras, semente=semente) if m.kappa is not None else None
    m.pabak = pabak(a, b, len(v.rotulos))
    m.alfa = alfa_nominal(list(zip(a, b, strict=True)))
    m.rotulos = rotulos
    m.matriz = matriz_confusao(a, b, rotulos)
    m.por_classe = por_classe(m.matriz, rotulos)
    return m


def _nome_modelo(modelo: str) -> str:
    return modelo.split("@", 1)[0].removesuffix(":latest")


def calcular(projeto: Projeto, *, reamostras: int = REAMOSTRAS) -> Validacao:
    """As métricas da validação do projeto: a amostra guardada, as codificações e os modelos com o codebook atual."""
    amostra = va.ler(projeto)
    if amostra is None:
        raise ErroConfig("O projeto ainda não tem amostra. Rode `mapa validar amostra` primeiro.")
    codebook = projeto.codebook
    hash_cb = codebook.hash()
    na_amostra = set(amostra.docs)
    semente = projeto.config.validacao.semente

    # respostas: participante → (doc, variável) → valor em texto
    respostas: dict[str, dict[tuple[str, str], str]] = {}
    tipos: dict[str, TipoParticipante] = {}
    extras: dict[str, dict[tuple[str, str], dict[str, Any]]] = {}  # evidência, status, incerto
    for nome, tipo in va.codificadores(projeto).items():
        tipos[nome] = tipo
        linhas = [c for c in va.codificacoes(projeto, nome) if c["doc"] in na_amostra]
        respostas[nome] = {(c["doc"], c["variavel"]): c["valor"] for c in linhas}
        extras[nome] = {(c["doc"], c["variavel"]): c for c in linhas}
    pasta = projeto.dados / PASTA_CLASSIFICACAO
    principal = _nome_modelo(projeto.config.modelos.classificacao.modelo)
    evidencia_literal = {}
    modelos = []
    for r in resultados(pasta):
        nome = _nome_modelo(r.modelo)
        if r.hash_codebook != hash_cb or nome in tipos:
            continue
        linhas = [linha for linha in ler_linhas(pasta, r.modelo, hash_cb) if linha["doc"] in na_amostra]
        if not linhas:
            continue
        modelos.append(nome)
        tipos[nome] = "modelo"
        respostas[nome] = {(linha["doc"], linha["variavel"]): linha["valor"] for linha in linhas}
        extras[nome] = {(linha["doc"], linha["variavel"]): linha for linha in linhas}
        status = [linha["status"] for linha in linhas if linha["status"] != "dispensada"]
        if status:
            evidencia_literal[nome] = round(status.count("literal") / len(status), 4)
    modelos.sort(key=lambda m: (m != principal, m))
    codificadores = sorted((n for n, t in tipos.items() if t != "modelo"), key=lambda n: (tipos[n] != "humano", n))

    participantes = [
        Participante(nome, tipos[nome], len({doc for doc, _ in respostas[nome]})) for nome in [*codificadores, *modelos]
    ]
    pares = (
        [(c, m) for c in codificadores for m in modelos]
        + list(combinations(codificadores, 2))
        + list(combinations(modelos, 2))
    )
    medidas = variaveis_medidas(codebook)

    def valores(nome: str, v: VariavelMedida, docs: Sequence[str]) -> list[str]:
        return [v.extrair(respostas[nome][(d, v.variavel)]) for d in docs]

    def comuns(v: VariavelMedida, *nomes: str) -> list[str]:
        return [d for d in amostra.docs if all((d, v.variavel) in respostas[n] for n in nomes)]

    metricas = []
    for v in medidas:
        for a, b in pares:
            docs = comuns(v, a, b)
            metricas.append(
                medir(valores(a, v, docs), valores(b, v, docs), v, a, b, reamostras=reamostras, semente=semente)
            )

    comparacoes = []
    for ref in codificadores:
        for m1, m2 in combinations(modelos, 2):
            for v in medidas:
                if v.texto:
                    continue
                docs = comuns(v, ref, m1, m2)
                certo = valores(ref, v, docs)
                a1 = [x == y for x, y in zip(certo, valores(m1, v, docs), strict=True)]
                a2 = [x == y for x, y in zip(certo, valores(m2, v, docs), strict=True)]
                so_a = sum(x and not y for x, y in zip(a1, a2, strict=True))
                so_b = sum(y and not x for x, y in zip(a1, a2, strict=True))
                comparacoes.append(
                    ComparacaoModelos(
                        v.id, ref, m1, m2, len(docs), sum(a1), sum(a2), so_a, so_b, mcnemar_exato(so_a, so_b)
                    )
                )

    divergencias = []
    if principal in modelos:
        for c in codificadores:
            for v in codebook.variaveis:
                chave_v = VariavelMedida(v.id, v.id, (), _COMPARAR.get(v.tipo, str))
                for d in comuns(chave_v, c, principal):
                    vc, vm = respostas[c][(d, v.id)], respostas[principal][(d, v.id)]
                    if chave_v.extrair(vc) == chave_v.extrair(vm):
                        continue
                    ec, em = extras[c][(d, v.id)], extras[principal][(d, v.id)]
                    divergencias.append(
                        Divergencia(
                            d, v.id, c, vc, vm, em["evidencia"], em["status"], ec["evidencia"], bool(ec["incerto"])
                        )
                    )

    return Validacao(
        amostra={
            "n": len(amostra.docs),
            "estratificar_por": amostra.estratificar_por,
            "semente": amostra.semente,
            "sorteada_em": amostra.sorteada_em,
        },
        codebook=f"{codebook.nome} {codebook.versao}",
        hash_codebook=hash_cb,
        modelo_principal=principal if principal in modelos else None,
        participantes=participantes,
        metricas=metricas,
        comparacoes_modelos=comparacoes,
        divergencias=divergencias,
        evidencia_literal=evidencia_literal,
    )
