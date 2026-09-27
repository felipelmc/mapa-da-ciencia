"""Métricas de concordância, conferidas com o sklearn, o scipy e o exemplo publicado de Krippendorff."""

import json

import numpy as np
import pytest
from scipy.stats import binomtest
from sklearn.metrics import cohen_kappa_score, confusion_matrix, precision_recall_fscore_support

import mapa_da_ciencia.api as mapa
from mapa_da_ciencia.coleta import coletar
from mapa_da_ciencia.config import ErroConfig
from mapa_da_ciencia.llm.perfis import PERFIS
from mapa_da_ciencia.projeto import Projeto
from mapa_da_ciencia.validacao import amostra as va
from mapa_da_ciencia.validacao import metricas as vm


def _pares(semente: int, n: int, k: int, acerto: float) -> tuple[list[str], list[str]]:
    rng = np.random.default_rng(semente)
    a = rng.integers(0, k, n)
    b = np.where(rng.random(n) < acerto, a, rng.integers(0, k, n))
    return [f"c{x}" for x in a], [f"c{x}" for x in b]


@pytest.mark.parametrize(("semente", "n", "k", "acerto"), [(1, 200, 2, 0.8), (2, 50, 4, 0.6), (3, 300, 6, 0.9)])
def test_kappa_igual_ao_do_sklearn(semente, n, k, acerto):
    a, b = _pares(semente, n, k, acerto)
    assert vm.kappa(a, b) == pytest.approx(cohen_kappa_score(a, b), abs=1e-12)
    assert vm.concordancia(a, b) == pytest.approx(np.mean(np.array(a) == np.array(b)))
    baixo, alto = vm.kappa_ic95(a, b, semente=semente)
    assert baixo < vm.kappa(a, b) < alto and alto - baixo < 0.5
    assert vm.kappa_ic95(a, b, semente=semente) == (baixo, alto)  # determinístico


def test_casos_de_borda():
    assert vm.kappa(["x"] * 20, ["x"] * 20) is None  # sem variação: indefinido
    assert vm.kappa(["a", "b"] * 10, ["a", "b"] * 10) == 1.0
    assert vm.kappa([], []) is None and vm.concordancia([], []) is None
    assert vm.kappa_ic95(["a", "b"] * 4, ["a", "b"] * 4) is None  # menos de 10 documentos
    assert vm.pabak(["a", "b", "a", "a"], ["a", "b", "b", "a"], 2) == pytest.approx(2 * 0.75 - 1)
    assert vm.pabak(["a"] * 10, ["a"] * 10, 5) == 1.0
    assert vm.alfa_nominal([["x", "x"], ["x", "x"]]) is None


def test_alfa_do_exemplo_de_krippendorff():
    """Krippendorff (2011), "Computing Krippendorff's Alpha-Reliability": 4 observadores, 12 unidades, com
    respostas faltando; alfa nominal = 0,743."""
    n = None
    observadores = [
        [1, 2, 3, 3, 2, 1, 4, 1, 2, n, n, n],
        [1, 2, 3, 3, 2, 2, 4, 1, 2, 5, n, 3],
        [n, 3, 3, 3, 2, 3, 4, 2, 2, 5, 1, n],
        [1, 2, 3, 3, 2, 4, 4, 1, 2, 5, 1, n],
    ]
    unidades = [[None if o[u] is None else str(o[u]) for o in observadores] for u in range(12)]
    assert round(vm.alfa_nominal(unidades), 3) == 0.743


def test_alfa_de_dois_codificadores_sem_faltas():
    """Com dois codificadores e sem faltas, α = 1 − (2n − 1)·D_o / D_e, perto do pi de Scott para n grande."""
    a, b = _pares(4, 400, 3, 0.7)
    po = vm.concordancia(a, b)
    p = np.array([(np.array(a + b) == c).mean() for c in sorted(set(a + b))])
    pi_scott = (po - (p**2).sum()) / (1 - (p**2).sum())
    assert vm.alfa_nominal(list(zip(a, b, strict=True))) == pytest.approx(pi_scott, abs=0.005)


def test_matriz_e_por_classe_iguais_ao_sklearn():
    a, b = _pares(5, 120, 4, 0.5)
    b = [x if x != "c3" else "c2" for x in b]  # o segundo nunca dá c3: precisão indefinida
    rotulos = ["c0", "c1", "c2", "c3"]
    m = vm.matriz_confusao(a, b, rotulos)
    assert m == confusion_matrix(a, b, labels=rotulos).tolist()
    p, r, f, s = precision_recall_fscore_support(a, b, labels=rotulos, zero_division=0)
    for i, c in enumerate(vm.por_classe(m, rotulos)):
        assert c.suporte == s[i] and c.revocacao == pytest.approx(r[i]) and c.f1 == pytest.approx(f[i])
        assert c.precisao == (None if c.rotulo == "c3" else pytest.approx(p[i]))


@pytest.mark.parametrize(("so_a", "so_b"), [(0, 0), (3, 12), (10, 10), (1, 0), (25, 9)])
def test_mcnemar_igual_ao_binomial_do_scipy(so_a, so_b):
    esperado = 1.0 if so_a + so_b == 0 else binomtest(min(so_a, so_b), so_a + so_b, 0.5).pvalue
    assert vm.mcnemar_exato(so_a, so_b) == pytest.approx(esperado)


# ---------------------------------------------------------------- o projeto
@pytest.fixture
def projeto(tmp_path, apis_falsas):
    p = Projeto.criar(
        tmp_path / "op", modelo="ciencia-politica", perfil=PERFIS["leve"], revistas=["0104-6276"], anos=(2024, 2024)
    )
    coletar(p)
    cfg = p.raiz / "mapa.yaml"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace("n: 200", "n: 12"), encoding="utf-8")
    return Projeto.abrir(p.raiz)


def _codificar(p: Projeto, docs: list[str], tmp_path, nome: str, discordar: set[str]) -> None:
    """Codifica como o modelo falso (a primeira categoria, verdadeiro, um período), exceto a `abordagem` dos
    documentos em `discordar`."""
    linhas = []
    for d in docs:
        respostas = {}
        for v in p.codebook.variaveis:
            if v.tipo == "booleana":
                valor: object = True
            elif v.tipo == "texto":
                valor = "2010–2020"
            elif v.tipo == "multipla":
                valor = [v.categorias[0].valor]
            else:
                valor = v.categorias[0].valor
            if v.id == "abordagem" and d in discordar:
                valor = v.categorias[-2].valor
            respostas[v.id] = {"valor": valor, "evidencia": "", "incerto": d in discordar}
        linhas.append(json.dumps({"doc": d, "respostas": respostas}))
    arquivo = tmp_path / f"{nome}.jsonl"
    arquivo.write_text("\n".join(linhas))
    va.importar(p, arquivo, nome, tipo="referencia" if nome.startswith("claude") else "humano")


def test_validacao_do_projeto(projeto, tmp_path):
    with pytest.raises(ErroConfig, match="validar amostra"):
        vm.calcular(projeto)
    a = va.sortear(projeto)
    _codificar(projeto, a.docs, tmp_path, "claude-opus", set(a.docs[:3]))
    _codificar(projeto, a.docs[:6], tmp_path, "maria", set(a.docs[1:2]))
    mapa.classificar(projeto, somente_amostra=True, progresso=False)
    mapa.classificar(projeto, somente_amostra=True, modelo="qwen3.5:9b", progresso=False)

    r = vm.calcular(projeto, reamostras=200)
    assert r.modelo_principal == "qwen3.5:4b"
    assert [(x.nome, x.tipo, x.n) for x in r.participantes] == [
        ("maria", "humano", 6),
        ("claude-opus", "referencia", 12),
        ("qwen3.5:4b", "modelo", 12),
        ("qwen3.5:9b", "modelo", 12),
    ]
    assert r.evidencia_literal == {"qwen3.5:4b": 1.0, "qwen3.5:9b": 1.0}

    m = r.metrica("abordagem", "claude-opus", "qwen3.5:4b")
    assert m.n == 12 and m.concordancia == pytest.approx(9 / 12)
    assert m.rotulos[0] == "quantitativa" and sum(map(sum, m.matriz)) == 12
    assert m.pabak == pytest.approx((6 * 9 / 12 - 1) / 5)
    assert r.metrica("abordagem", "maria", "claude-opus").n == 6  # só os documentos dos dois
    assert r.metrica("abordagem", "maria", "qwen3.5:4b").concordancia == pytest.approx(5 / 6)
    # sem variação nenhuma: concordância 1, kappa indefinido
    rec = r.metrica("brasil_como_caso", "claude-opus", "qwen3.5:4b")
    assert rec.concordancia == 1.0 and rec.kappa is None and rec.pabak == 1.0

    comparacoes = [c for c in r.comparacoes_modelos if c.variavel == "abordagem"]
    assert {(c.referencia, c.modelo_a, c.modelo_b) for c in comparacoes} == {
        ("maria", "qwen3.5:4b", "qwen3.5:9b"),
        ("claude-opus", "qwen3.5:4b", "qwen3.5:9b"),
    }
    assert all(c.so_a == c.so_b == 0 and c.p == 1.0 for c in comparacoes)  # o modelo falso responde igual

    div = [d for d in r.divergencias if d.codificador == "claude-opus"]
    assert {d.doc for d in div} == set(a.docs[:3]) and all(d.variavel == "abordagem" and d.incerto for d in div)
    assert div[0].valor_modelo == "quantitativa" and div[0].evidencia_modelo and div[0].status_evidencia == "literal"


def test_cli_validar_metricas(projeto, tmp_path):
    from typer.testing import CliRunner

    from mapa_da_ciencia.cli import app

    a = va.sortear(projeto)
    raiz = str(projeto.raiz)
    r = CliRunner().invoke(app, ["validar", "metricas", "-P", raiz], env={"COLUMNS": "160"})
    assert r.exit_code == 0 and "Nada a comparar" in r.output
    _codificar(projeto, a.docs, tmp_path, "claude-opus", set(a.docs[:3]))
    mapa.classificar(projeto, somente_amostra=True, progresso=False)
    r = CliRunner().invoke(app, ["validar", "metricas", "-P", raiz], env={"COLUMNS": "160"})
    assert r.exit_code == 0, r.output
    assert "claude-opus × qwen3.5:4b" in r.output and "referência, não humano" in r.output
    assert "75%" in r.output and "3 divergência(s)" in r.output
    assert mapa.validacao(projeto).metrica("abordagem", "claude-opus", "qwen3.5:4b").n == 12


def test_texto_normalizado():
    n = vm._normalizar_texto
    assert n("1994 - 2018") == n("1994–2018") == n("1994—2018")
    assert n("Não se aplica") == n("nao  se aplica")


def test_relatorio(projeto, tmp_path):
    from typer.testing import CliRunner

    from mapa_da_ciencia.cli import app
    from mapa_da_ciencia.validacao.relatorio import gerar

    a = va.sortear(projeto)
    _codificar(projeto, a.docs, tmp_path, "claude-opus", set(a.docs[:3]))
    mapa.classificar(projeto, somente_amostra=True, progresso=False)
    mapa.classificar(projeto, somente_amostra=True, modelo="qwen3.5:9b", progresso=False)
    _, arquivos = gerar(projeto)
    md = arquivos["markdown"].read_text(encoding="utf-8")
    assert "`claude-opus` | referência (não humano) | 12" in md and "**Atenção:**" in md
    assert "### `claude-opus` × `qwen3.5:4b`" in md and "| `abordagem` | 12 | 75% |" in md
    assert "## Por classe: `claude-opus` (referência) × `qwen3.5:4b`" in md
    assert "## Comparação entre modelos" in md and "## Divergências com `qwen3.5:4b`" in md
    assert md.count("(marcado como incerto)") == 3 and "citando «" in md
    tex = arquivos["latex"].read_text(encoding="utf-8")
    assert tex.count(r"\begin{table}") == 3 and r"tecnica\_principal & 12 & 100\% &" in tex
    assert r"\label{tab:concordancia-claude-opus-qwen3-5-4b}" in tex
    dados = json.loads(arquivos["json"].read_text(encoding="utf-8"))
    assert dados["modelo_principal"] == "qwen3.5:4b" and len(dados["divergencias"]) == 3
    assert {a.parent.name for a in arquivos.values()} == {"validacao"}

    r = CliRunner().invoke(app, ["validar", "relatorio", "-P", str(projeto.raiz)], env={"COLUMNS": "160"})
    assert r.exit_code == 0, r.output
    assert "Relatório gravado" in r.output and "validacao/relatorio.md" in r.output
