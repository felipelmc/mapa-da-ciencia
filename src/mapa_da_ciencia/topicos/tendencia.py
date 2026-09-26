"""Tendência de um tópico no tempo: está "em alta", "em queda" ou estável? (ADR 0009)

A participação do tópico em cada ano (documentos do tópico ÷ documentos do ano) é modelada por uma regressão
logística com o ano como única variável. A inclinação diz se a participação cresce ou cai; o intervalo de 95%
dela diz se a mudança é distinguível do acaso. Com poucos documentos por ano, a série é ruidosa, e um dossiê
temático faz um pico isolado: por isso o erro-padrão é corrigido pela dispersão (quase-binomial), e um tópico só é
marcado quando o intervalo não inclui zero.

O tamanho da mudança vem das participações ajustadas no primeiro e no último ano: `pp_periodo` pontos percentuais
no período, ou `pp_por_ano` por ano. É o que a sparkline da interface mostra.

Python puro, sem numpy: o mesmo algoritmo roda no navegador (`frontend/src/lib/estatistica/glm.ts`), com os
filtros do painel, e os casos de `contrato/casos/tendencia.json` garantem que as duas versões dão o mesmo número.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

MODELO = "logistica_binomial"
Dispersao = Literal["quase", "binomial"]
DISPERSAO: Dispersao = "quase"
NIVEL = 0.95
Z = 1.959963984540054  # quantil 97,5% da normal
ANOS_MINIMOS = 5
DOCS_MINIMOS = 10
INCLINACAO_MAXIMA = 10.0  # além disso, a estimativa diverge (separação): o tópico está num ano só
ITERACOES_MAXIMAS = 100
TOLERANCIA = 1e-10

Direcao = Literal["alta", "queda", "estavel", "insuficiente"]
Motivo = Literal["poucos_anos", "poucos_documentos", "sem_variacao", "sem_convergencia"]


@dataclass(frozen=True)
class Tendencia:
    """Resultado para um tópico. Com `direcao == "insuficiente"`, só `motivo` e `anos` estão preenchidos."""

    direcao: Direcao
    inclinacao: float | None = None  # na escala logit, por ano
    erro_padrao: float | None = None  # já multiplicado por √dispersão
    ic95: tuple[float, float] | None = None
    dispersao: float | None = None  # φ de Pearson (1 na binomial pura)
    prop_inicio: float | None = None  # participação ajustada no primeiro ano com documentos
    prop_fim: float | None = None
    pp_periodo: float | None = None
    pp_por_ano: float | None = None
    anos: tuple[int, int] | None = None
    motivo: Motivo | None = None


@dataclass(frozen=True)
class Ajuste:
    intercepto: float  # com o ano centrado na média dos anos usados
    inclinacao: float
    erro_padrao: float  # binomial, sem a correção da dispersão
    pearson: float  # X² de Pearson
    media_anos: float


def _expit(eta: float) -> float:
    if eta >= 0:
        return 1.0 / (1.0 + math.exp(-eta))
    e = math.exp(eta)
    return e / (1.0 + e)


def _softplus(eta: float) -> float:
    return eta + math.log1p(math.exp(-eta)) if eta > 0 else math.log1p(math.exp(eta))


def _verossimilhanca(b0: float, b1: float, x: list[float], k: list[int], n: list[int]) -> float:
    return sum(ki * (b0 + b1 * xi) - ni * _softplus(b0 + b1 * xi) for xi, ki, ni in zip(x, k, n, strict=True))


def ajustar_glm(anos: list[float], k: list[int], n: list[int]) -> Ajuste | None:
    """Máxima verossimilhança de logit(p) = b0 + b1·(ano − média), por Newton com meio-passo.

    `None` quando não converge ou a inclinação diverge (separação). Não aplica os mínimos de anos e documentos.
    """
    media = sum(anos) / len(anos)
    x = [a - media for a in anos]
    total_k, total_n = sum(k), sum(n)
    if total_k <= 0 or total_k >= total_n:
        return None
    b0, b1 = math.log(total_k / (total_n - total_k)), 0.0
    atual = _verossimilhanca(b0, b1, x, k, n)
    for _ in range(ITERACOES_MAXIMAS):
        p = [_expit(b0 + b1 * xi) for xi in x]
        g0 = sum(ki - ni * pi for ki, ni, pi in zip(k, n, p, strict=True))
        g1 = sum(xi * (ki - ni * pi) for xi, ki, ni, pi in zip(x, k, n, p, strict=True))
        w = [ni * pi * (1 - pi) for ni, pi in zip(n, p, strict=True)]
        i00, i01 = sum(w), sum(xi * wi for xi, wi in zip(x, w, strict=True))
        i11 = sum(xi * xi * wi for xi, wi in zip(x, w, strict=True))
        det = i00 * i11 - i01 * i01
        if det <= 0:
            return None
        d0, d1 = (i11 * g0 - i01 * g1) / det, (i00 * g1 - i01 * g0) / det
        passo = 1.0
        for _ in range(30):
            nova = _verossimilhanca(b0 + passo * d0, b1 + passo * d1, x, k, n)
            if nova >= atual - 1e-12:
                break
            passo /= 2
        b0, b1, atual = b0 + passo * d0, b1 + passo * d1, nova
        if abs(b1) > INCLINACAO_MAXIMA:
            return None
        if max(abs(passo * d0), abs(passo * d1)) < TOLERANCIA:
            break
    else:
        return None
    p = [_expit(b0 + b1 * xi) for xi in x]
    w = [ni * pi * (1 - pi) for ni, pi in zip(n, p, strict=True)]
    i00, i01 = sum(w), sum(xi * wi for xi, wi in zip(x, w, strict=True))
    i11 = sum(xi * xi * wi for xi, wi in zip(x, w, strict=True))
    det = i00 * i11 - i01 * i01
    if det <= 0:
        return None
    pearson = sum((ki - ni * pi) ** 2 / wi for ki, ni, pi, wi in zip(k, n, p, w, strict=True) if wi > 0)
    return Ajuste(b0, b1, math.sqrt(i00 / det), pearson, media)


def tendencia(n: list[int], total: list[int], anos: list[int], *, dispersao: Dispersao = DISPERSAO) -> Tendencia:
    """Tendência da série `n` (documentos do tópico por ano) sobre `total` (documentos de cada ano)."""
    usados = [(a, ni, ti) for a, ni, ti in zip(anos, n, total, strict=True) if ti > 0]
    periodo = (usados[0][0], usados[-1][0]) if usados else None
    if len(usados) < ANOS_MINIMOS:
        return Tendencia("insuficiente", anos=periodo, motivo="poucos_anos")
    xs, ks, ns = [float(a) for a, _, _ in usados], [ni for _, ni, _ in usados], [ti for _, _, ti in usados]
    if sum(ks) < DOCS_MINIMOS:
        return Tendencia("insuficiente", anos=periodo, motivo="poucos_documentos")
    if sum(ks) >= sum(ns):
        return Tendencia("insuficiente", anos=periodo, motivo="sem_variacao")
    ajuste = ajustar_glm(xs, ks, ns)
    if ajuste is None:
        return Tendencia("insuficiente", anos=periodo, motivo="sem_convergencia")
    phi = max(1.0, ajuste.pearson / (len(usados) - 2)) if dispersao == "quase" else 1.0
    ep = ajuste.erro_padrao * math.sqrt(phi)
    ic = (ajuste.inclinacao - Z * ep, ajuste.inclinacao + Z * ep)
    direcao: Direcao = "alta" if ic[0] > 0 else "queda" if ic[1] < 0 else "estavel"
    primeiro, ultimo = usados[0][0], usados[-1][0]
    p0 = _expit(ajuste.intercepto + ajuste.inclinacao * (primeiro - ajuste.media_anos))
    p1 = _expit(ajuste.intercepto + ajuste.inclinacao * (ultimo - ajuste.media_anos))
    pp = 100 * (p1 - p0)
    return Tendencia(
        direcao=direcao,
        inclinacao=ajuste.inclinacao,
        erro_padrao=ep,
        ic95=ic,
        dispersao=phi,
        prop_inicio=p0,
        prop_fim=p1,
        pp_periodo=pp,
        pp_por_ano=pp / (ultimo - primeiro),
        anos=(primeiro, ultimo),
    )


def casos_de_referencia() -> list[dict]:
    """Casos de entrada e saída para conferir outras implementações (a do navegador) contra esta.

    Gravados em `contrato/casos/tendencia.json` por `scripts/gerar_contrato.py`. Séries fixas, escritas à mão ou
    geradas com semente, cobrindo subida, queda, estabilidade, pico isolado, anos vazios, mínimos e divergência.
    """
    import random

    anos16 = list(range(2010, 2026))

    def binomial(p0: float, p1: float, totais: list[int], semente: int) -> list[int]:
        rng = random.Random(semente)
        lo0, lo1 = math.log(p0 / (1 - p0)), math.log(p1 / (1 - p1))
        return [
            sum(rng.random() < _expit(lo0 + (lo1 - lo0) * i / (len(totais) - 1)) for _ in range(t))
            for i, t in enumerate(totais)
        ]

    totais = [241, 250, 262, 255, 270, 268, 281, 276, 290, 285, 300, 294, 288, 279, 296, 283]
    pico = [4, 5, 3, 4, 6, 4, 5, 3, 4, 5, 6, 5, 7, 44, 6, 5]  # dossiê em 2023
    entradas = [
        ("subida", binomial(0.01, 0.07, totais, 1), totais, anos16, "quase"),
        ("queda", binomial(0.08, 0.02, totais, 2), totais, anos16, "quase"),
        ("estavel", [12] * 16, [300] * 16, anos16, "quase"),
        ("ruidosa_pequena", binomial(0.01, 0.015, totais, 3), totais, anos16, "quase"),
        ("pico_quase", pico, totais, anos16, "quase"),
        ("pico_binomial", pico, totais, anos16, "binomial"),
        (
            "anos_vazios",
            [3, 0, 5, 7, 0, 9, 11, 0],
            [120, 0, 130, 140, 0, 150, 160, 0],
            list(range(2015, 2023)),
            "quase",
        ),
        ("janela", binomial(0.02, 0.06, totais[5:13], 4), totais[5:13], anos16[5:13], "quase"),
        ("poucos_anos", [5, 6, 7, 8], [100] * 4, list(range(2010, 2014)), "quase"),
        ("poucos_documentos", [0, 0, 3, 0, 2, 0, 4, 0, 0, 0], [100] * 10, list(range(2010, 2020)), "quase"),
        ("sem_variacao", [50] * 6, [50] * 6, list(range(2010, 2016)), "quase"),
        ("so_no_fim", [0] * 9 + [40], [100] * 10, list(range(2010, 2020)), "quase"),
        ("sem_ruido", [round(1000 * (0.02 + 0.002 * i)) for i in range(16)], [1000] * 16, anos16, "quase"),
    ]
    casos = []
    for nome, n, total, anos, dispersao in entradas:
        t = tendencia(n, total, anos, dispersao=dispersao)
        casos.append(
            {
                "nome": nome,
                "entrada": {"n": n, "total": total, "anos": anos, "dispersao": dispersao},
                "saida": {
                    "direcao": t.direcao,
                    "inclinacao": t.inclinacao,
                    "erro_padrao": t.erro_padrao,
                    "ic95": list(t.ic95) if t.ic95 else None,
                    "dispersao": t.dispersao,
                    "prop_inicio": t.prop_inicio,
                    "prop_fim": t.prop_fim,
                    "pp_periodo": t.pp_periodo,
                    "pp_por_ano": t.pp_por_ano,
                    "anos": list(t.anos) if t.anos else None,
                    "motivo": t.motivo,
                },
            }
        )
    return casos
