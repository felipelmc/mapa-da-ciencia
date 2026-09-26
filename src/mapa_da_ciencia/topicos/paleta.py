"""Cores dos macrotemas e dos tópicos, geradas no espaço OKLCH.

No OKLCH, distâncias iguais parecem diferenças iguais: os matizes dos macrotemas são espaçados por igual,
e os tópicos de um macrotema são variações (matiz e luminosidade) da cor dele. Cada cor precisa:

- aparecer sobre os dois fundos da interface (contraste ≥ 3:1, o mínimo da WCAG para elementos gráficos);
- distinguir-se das outras mesmo com daltonismo (simulação de Machado, Oliveira e Fernandes, 2009).

As cores ficam gravadas por id de tópico (`topicos/identidade.py`): um tópico mantém a cor entre execuções,
e só um tópico novo ganha cor nova. Tudo em Python puro, sem dependências.
"""

from __future__ import annotations

import math

FUNDOS = {"observatorio": "#0a0e1f", "prancha": "#f6f2e9"}  # --fundo em frontend/src/lib/estilos/tokens.css
CONTRASTE_MINIMO = 3.0

# Para cada número de macrotemas: matiz inicial, luminosidades alternadas e croma. Escolhidos por busca em grade
# (matiz de 5 em 5°) para maximizar a menor diferença entre pares com visão normal e com os três tipos de
# daltonismo. O contraste com os dois fundos (um escuro, um claro) prende a luminosidade numa faixa estreita,
# por isso a alternância de luminosidade ajuda tanto. `tests/test_paleta.py` confere os mínimos.
_PARAMETROS: dict[int, tuple[float, tuple[float, ...], float]] = {
    2: (325, (0.66, 0.52, 0.59), 0.16),
    3: (10, (0.64, 0.53), 0.16),
    4: (305, (0.64, 0.53), 0.16),
    5: (225, (0.66, 0.52, 0.59), 0.16),
    6: (115, (0.64, 0.53), 0.16),
    7: (315, (0.64, 0.53), 0.16),
    8: (60, (0.64, 0.53), 0.14),
}
MAXIMO_MACROTEMAS = max(_PARAMETROS)

# Matrizes de Machado et al. (2009), severidade 1, aplicadas em RGB linear.
DALTONISMO = {
    "protanopia": ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216), (-0.003882, -0.048116, 1.051998)),
    "deuteranopia": ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413), (-0.011820, 0.042940, 0.968881)),
    "tritanopia": ((1.255528, -0.076749, -0.178779), (-0.078411, 0.930809, 0.147602), (0.004733, 0.691367, 0.303900)),
}


# ---------------------------------------------------------------- conversões
def _linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _gama(c: float) -> float:
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def _oklab_para_rgb_linear(l: float, a: float, b: float) -> tuple[float, float, float]:  # noqa: E741
    l_ = (l + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (l - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (l - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (
        4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
        -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
        -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_,
    )


def _rgb_linear_para_oklab(r: float, g: float, b: float) -> tuple[float, float, float]:
    l_ = math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
    m_ = math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
    s_ = math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


def _no_gamut(rgb: tuple[float, float, float]) -> bool:
    return all(-1e-6 <= c <= 1 + 1e-6 for c in rgb)


def _hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{round(min(1.0, max(0.0, _gama(c))) * 255):02x}" for c in rgb)


def _rgb_linear(cor: str) -> tuple[float, float, float]:
    return tuple(_linear(int(cor[i : i + 2], 16) / 255) for i in (1, 3, 5))  # type: ignore[return-value]


def oklch_para_hex(l: float, c: float, h: float) -> str:  # noqa: E741
    """Cor OKLCH (luminosidade 0–1, croma, matiz em graus) em hex sRGB. Fora do gamut, reduz o croma."""
    rad = math.radians(h)
    rgb = _oklab_para_rgb_linear(l, c * math.cos(rad), c * math.sin(rad))
    if not _no_gamut(rgb):
        baixo, alto = 0.0, c
        for _ in range(30):
            meio = (baixo + alto) / 2
            teste = _oklab_para_rgb_linear(l, meio * math.cos(rad), meio * math.sin(rad))
            baixo, alto = (meio, alto) if _no_gamut(teste) else (baixo, meio)
        rgb = _oklab_para_rgb_linear(l, baixo * math.cos(rad), baixo * math.sin(rad))
    return _hex(rgb)


def hex_para_oklch(cor: str) -> tuple[float, float, float]:
    l, a, b = _rgb_linear_para_oklab(*_rgb_linear(cor))  # noqa: E741
    return l, math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360


# ---------------------------------------------------------------- medidas
def delta_e(a: str, b: str, *, daltonismo: str | None = None) -> float:
    """Diferença perceptual ΔE no OKLab, em escala 0–100 (≈ 2 é o limiar do perceptível).

    Com `daltonismo` ("protanopia", "deuteranopia" ou "tritanopia"), compara as cores como essa pessoa as vê.
    """
    ca, cb = _rgb_linear(a), _rgb_linear(b)
    if daltonismo:
        m = DALTONISMO[daltonismo]
        ca, cb = (tuple(max(0.0, sum(m[i][j] * c[j] for j in range(3))) for i in range(3)) for c in (ca, cb))
    la, lb = _rgb_linear_para_oklab(*ca), _rgb_linear_para_oklab(*cb)
    return 100 * math.dist(la, lb)


def contraste(a: str, b: str) -> float:
    """Razão de contraste da WCAG 2.x entre duas cores."""

    def luminancia(cor: str) -> float:
        r, g, b_ = _rgb_linear(cor)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b_

    claro, escuro = sorted((luminancia(a), luminancia(b)), reverse=True)
    return (claro + 0.05) / (escuro + 0.05)


def legivel_nos_fundos(cor: str) -> bool:
    return all(contraste(cor, fundo) >= CONTRASTE_MINIMO for fundo in FUNDOS.values())


# ---------------------------------------------------------------- paletas
def _ajustar_luminosidade(l: float, c: float, h: float) -> str:  # noqa: E741
    """A cor mais próxima de `l` que ainda tem contraste suficiente com os dois fundos."""
    for passo in range(0, 30):
        for candidato in (l - 0.01 * passo, l + 0.01 * passo):
            cor = oklch_para_hex(candidato, c, h)
            if legivel_nos_fundos(cor):
                return cor
    return oklch_para_hex(l, c, h)


def cores_macrotemas(n: int) -> list[str]:
    """`n` cores bem separadas para os macrotemas (até 8): matizes espaçados por igual e luminosidade alternada."""
    if n < 1:
        return []
    if n > MAXIMO_MACROTEMAS:
        raise ValueError(f"No máximo {MAXIMO_MACROTEMAS} macrotemas: acima disso as cores deixam de se distinguir.")
    matiz, luminosidades, croma = _PARAMETROS.get(n, (250, (0.60,), 0.14))
    return [
        _ajustar_luminosidade(luminosidades[i % len(luminosidades)], croma, (matiz + i * 360 / n) % 360)
        for i in range(n)
    ]


def variantes(cor_macro: str) -> list[str]:
    """Candidatas para os tópicos de um macrotema: a cor dele com matiz (±18°), luminosidade e croma variados."""
    l, c, h = hex_para_oklch(cor_macro)  # noqa: E741
    saida = []
    for desvio_l in (0.0, -0.06, 0.05):
        for desvio_h in (0, -18, 18, -9, 9):
            for croma in (c, c * 0.65):
                cor = _ajustar_luminosidade(l + desvio_l, max(croma, 0.07), (h + desvio_h) % 360)
                if cor not in saida:
                    saida.append(cor)
    return saida


def proxima_cor(cor_macro: str, usadas: list[str]) -> str:
    """A variante do macrotema mais distante das cores já usadas por outros tópicos dele."""
    candidatas = variantes(cor_macro)
    if not usadas:
        return candidatas[0]
    return max(candidatas, key=lambda cor: min(delta_e(cor, u) for u in usadas))
