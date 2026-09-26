import math
import random

import numpy as np
import pytest

from mapa_da_ciencia.topicos.tendencia import (
    ANOS_MINIMOS,
    DOCS_MINIMOS,
    ajustar_glm,
    tendencia,
)


def _logit(p):
    return math.log(p / (1 - p))


def _serie(p_inicio, p_fim, totais, semente=1):
    """Série binomial com participação que vai linearmente (no logit) de p_inicio a p_fim."""
    rng = random.Random(semente)
    t = len(totais)
    n = []
    for i, total in enumerate(totais):
        eta = _logit(p_inicio) + (_logit(p_fim) - _logit(p_inicio)) * i / (t - 1)
        p = 1 / (1 + math.exp(-eta))
        n.append(sum(rng.random() < p for _ in range(total)))
    return n


def test_dois_anos_bate_com_a_forma_fechada():
    k, n = [12, 30], [200, 220]
    a = ajustar_glm([2010.0, 2014.0], k, n)
    b1 = (_logit(30 / 220) - _logit(12 / 200)) / 4
    ep = math.sqrt(1 / 12 + 1 / 188 + 1 / 30 + 1 / 190) / 4
    assert a.inclinacao == pytest.approx(b1, abs=1e-9) and a.erro_padrao == pytest.approx(ep, rel=1e-6)


@pytest.mark.parametrize("semente", [1, 2, 3])
def test_inclinacao_bate_com_o_sklearn(semente):
    from sklearn.linear_model import LogisticRegression

    anos = list(range(2010, 2026))
    rng = random.Random(semente)
    totais = [rng.randint(150, 320) for _ in anos]
    k = _serie(0.02, 0.06, totais, semente)
    a = ajustar_glm([float(x) for x in anos], k, totais)
    media = sum(anos) / len(anos)
    x = np.array([[ano - media] for ano in anos] * 2)
    y = np.array([1] * len(anos) + [0] * len(anos))
    peso = np.array(k + [t - ki for t, ki in zip(totais, k, strict=True)], dtype=float)
    ref = LogisticRegression(C=np.inf, tol=1e-12, max_iter=10_000).fit(x, y, sample_weight=peso)
    assert a.inclinacao == pytest.approx(ref.coef_[0][0], abs=1e-5)
    assert a.intercepto == pytest.approx(ref.intercept_[0], abs=1e-5)


def test_erro_padrao_bate_com_a_hessiana_numerica():
    anos = [float(a) for a in range(2010, 2026)]
    totais = [250] * 16
    k = _serie(0.05, 0.03, totais, 7)
    a = ajustar_glm(anos, k, totais)
    x = [ano - a.media_anos for ano in anos]

    def ll(b0, b1):
        return sum(
            ki * (b0 + b1 * xi) - ni * math.log1p(math.exp(b0 + b1 * xi))
            for xi, ki, ni in zip(x, k, totais, strict=True)
        )

    h = 1e-4
    b0, b1 = a.intercepto, a.inclinacao
    d00 = (ll(b0 + h, b1) - 2 * ll(b0, b1) + ll(b0 - h, b1)) / h**2
    d11 = (ll(b0, b1 + h) - 2 * ll(b0, b1) + ll(b0, b1 - h)) / h**2
    d01 = (ll(b0 + h, b1 + h) - ll(b0 + h, b1 - h) - ll(b0 - h, b1 + h) + ll(b0 - h, b1 - h)) / (4 * h**2)
    info = np.array([[-d00, -d01], [-d01, -d11]])
    assert a.erro_padrao == pytest.approx(math.sqrt(np.linalg.inv(info)[1, 1]), rel=1e-3)


def test_centralizar_o_ano_nao_muda_a_inclinacao():
    totais = [200] * 10
    k = _serie(0.04, 0.08, totais, 3)
    a = ajustar_glm([float(x) for x in range(2010, 2020)], k, totais)
    b = ajustar_glm([float(x) for x in range(0, 10)], k, totais)
    assert a.inclinacao == pytest.approx(b.inclinacao) and a.erro_padrao == pytest.approx(b.erro_padrao)


def test_anos_sem_documentos_sao_ignorados():
    anos = list(range(2010, 2022))
    totais = [200] * 12
    n = _serie(0.03, 0.09, totais, 5)
    com_buracos = tendencia([*n, 0, 0], [*totais, 0, 0], [*anos, 2022, 2023])
    assert com_buracos == tendencia(n, totais, anos) and com_buracos.anos == (2010, 2021)


def test_direcoes():
    anos, totais = list(range(2010, 2026)), [300] * 16
    assert tendencia(_serie(0.01, 0.08, totais), totais, anos).direcao == "alta"
    assert tendencia(_serie(0.08, 0.01, totais), totais, anos).direcao == "queda"
    plano = tendencia([12] * 16, totais, anos)
    assert plano.direcao == "estavel" and plano.pp_periodo == pytest.approx(0, abs=1e-6)
    t = tendencia(_serie(0.01, 0.08, totais), totais, anos)
    assert t.pp_periodo > 0 and t.pp_por_ano == pytest.approx(t.pp_periodo / 15) and t.anos == (2010, 2025)
    assert t.ic95[0] < t.inclinacao < t.ic95[1]


def test_minimos_e_casos_degenerados():
    anos = list(range(2010, 2010 + ANOS_MINIMOS - 1))
    assert tendencia([5] * len(anos), [100] * len(anos), anos).motivo == "poucos_anos"
    anos = list(range(2010, 2020))
    poucos = [0] * 10
    poucos[3] = DOCS_MINIMOS - 1
    assert tendencia(poucos, [100] * 10, anos).motivo == "poucos_documentos"
    assert tendencia([100] * 10, [100] * 10, anos).motivo == "sem_variacao"
    so_no_fim = [0] * 9 + [40]  # o tópico só existe no último ano: a inclinação diverge
    assert tendencia(so_no_fim, [100] * 10, anos).motivo == "sem_convergencia"


def test_dispersao_quase_alarga_o_intervalo_de_um_pico_isolado():
    anos, totais = list(range(2010, 2026)), [250] * 16
    n = [4] * 16
    n[10] = 45  # um dossiê temático num ano só
    binomial = tendencia(n, totais, anos, dispersao="binomial")
    quase = tendencia(n, totais, anos)
    assert binomial.dispersao == 1 and quase.dispersao > 5
    assert quase.erro_padrao == pytest.approx(binomial.erro_padrao * math.sqrt(quase.dispersao))
    assert quase.direcao == "estavel"


def test_dispersao_nunca_abaixo_de_1():
    anos, totais = list(range(2010, 2026)), [1000] * 16
    exato = [round(1000 * (0.02 + 0.002 * i)) for i in range(16)]  # sem ruído nenhum: X² ≈ 0
    assert tendencia(exato, totais, anos).dispersao == 1
