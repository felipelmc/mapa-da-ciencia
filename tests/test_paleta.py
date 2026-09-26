import re
from itertools import combinations
from pathlib import Path

import pytest

from mapa_da_ciencia.topicos.paleta import (
    DALTONISMO,
    FUNDOS,
    MAXIMO_MACROTEMAS,
    cores_macrotemas,
    delta_e,
    hex_para_oklch,
    legivel_nos_fundos,
    oklch_para_hex,
    proxima_cor,
)

TOKENS = Path(__file__).parents[1] / "frontend" / "src" / "lib" / "estilos" / "tokens.css"
# Menor diferença aceitável entre dois macrotemas (ΔE OKLab × 100; ≈ 2 é o limiar do perceptível)
MINIMOS = {None: 12, "protanopia": 5, "deuteranopia": 5, "tritanopia": 4}


def test_conversao_oklch():
    assert oklch_para_hex(0.62796, 0.25768, 29.2339) == "#ff0000"
    for cor in ("#0a0e1f", "#f6f2e9", "#398ad6", "#b3385d"):
        assert oklch_para_hex(*hex_para_oklch(cor)) == cor
    fora = oklch_para_hex(0.9, 0.4, 150)  # croma impossível: é reduzido até caber no sRGB
    assert re.fullmatch(r"#[0-9a-f]{6}", fora) and hex_para_oklch(fora)[1] < 0.4


def test_fundos_iguais_aos_da_interface():
    css = TOKENS.read_text(encoding="utf-8")
    for tema, cor in FUNDOS.items():
        bloco = css[css.index(f":root[data-tema='{tema}']") :]
        assert re.search(r"--fundo:\s*(#[0-9a-f]{6})", bloco).group(1) == cor


@pytest.mark.parametrize("n", range(2, MAXIMO_MACROTEMAS + 1))
def test_macrotemas_distintos_inclusive_com_daltonismo(n):
    cores = cores_macrotemas(n)
    assert len(set(cores)) == n and all(legivel_nos_fundos(c) for c in cores)
    for tipo, minimo in MINIMOS.items():
        pior = min(delta_e(a, b, daltonismo=tipo) for a, b in combinations(cores, 2))
        assert pior >= minimo, (tipo, round(pior, 1))


def test_limites_de_macrotemas():
    assert cores_macrotemas(0) == [] and len(cores_macrotemas(1)) == 1
    with pytest.raises(ValueError, match="No máximo"):
        cores_macrotemas(MAXIMO_MACROTEMAS + 1)


def test_cores_dos_topicos_de_um_macrotema():
    for macro in cores_macrotemas(7):
        usadas: list[str] = []
        for _ in range(6):
            usadas.append(proxima_cor(macro, usadas))
        assert len(set(usadas)) == 6 and all(legivel_nos_fundos(c) for c in usadas)
        assert min(delta_e(a, b) for a, b in combinations(usadas, 2)) >= 3
        assert usadas[0] == proxima_cor(macro, [])  # determinística


def test_delta_e():
    assert delta_e("#398ad6", "#398ad6") == 0
    assert delta_e("#398ad6", "#b3385d") == pytest.approx(delta_e("#b3385d", "#398ad6"))
    assert set(DALTONISMO) == {"protanopia", "deuteranopia", "tritanopia"}
