"""Os dados da abertura do site (scripts/gerar_pagina.py), gerados a partir do exemplo sintético do contrato."""

import base64
import importlib.util
import json
import shutil
import struct
from pathlib import Path

import duckdb
import pytest

RAIZ = Path(__file__).parents[1]


@pytest.fixture(scope="module")
def pagina():
    spec = importlib.util.spec_from_file_location("gerar_pagina", RAIZ / "scripts" / "gerar_pagina.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture
def projeto(tmp_path):
    shutil.copytree(RAIZ / "contrato" / "exemplo" / "dados", tmp_path / "saida" / "dados")
    return tmp_path


def test_o_ceu_tem_uma_estrela_por_artigo_e_constelacoes_em_arvore(pagina, projeto):
    dados = pagina.gerar(projeto)
    docs = json.loads((projeto / "saida" / "dados" / "documentos.json").read_text(encoding="utf-8"))
    topicos = json.loads((projeto / "saida" / "dados" / "topicos.json").read_text(encoding="utf-8"))
    ceu = dados["ceu"]
    assert ceu["n"] == docs["n"] and sum(ceu["por_ano"]) == docs["n"]
    bruto = base64.b64decode(ceu["pontos"])
    assert len(bruto) == 5 * docs["n"]
    pontos = [struct.unpack_from("<HHB", bruto, 5 * i) for i in range(docs["n"])]
    assert all(m <= len(topicos["macrotemas"]) for _, _, m in pontos)  # 0 = sem tópico
    assert 0 < ceu["proporcao"] <= 1
    assert len(ceu["estrelas"]) == len(topicos["topicos"])
    for c in ceu["constelacoes"]:
        membros = {i for i, e in enumerate(ceu["estrelas"]) if e["macro"] == ceu["constelacoes"].index(c)}
        assert len(c["linhas"]) == len(membros) - 1  # a árvore liga todos os tópicos do macrotema
        assert {i for linha in c["linhas"] for i in linha} <= membros


def test_numeros_e_historias(pagina, projeto):
    dados = pagina.gerar(projeto)
    n = dados["numeros"]
    assert n["artigos"] > 0 and n["topicos"] == len(dados["ceu"]["estrelas"]) and n["macrotemas"] > 0
    h = dados["historias"]
    assert h["validacao"]["kappas"] and h["validacao"]["mediana"] is not None
    assert h["geografia"]["pct_tres"] > 0 and len(h["geografia"]["tres"]) == 3
    assert h["ingles"] is None  # sem o corpus (Parquet), não há a história do idioma


def test_arvore_geradora_minima(pagina):
    assert sorted(pagina._arvore([(0, 0), (3, 0), (1, 0), (2, 0)])) == [(0, 2), (2, 3), (3, 1)]
    assert pagina._arvore([(0, 0)]) == []


def test_historia_do_ingles(pagina, tmp_path):
    parquet = tmp_path / "documentos.parquet"
    linhas = [
        (ano, rev, "en" if rev == "cint" and ano >= 2016 else "pt")
        for ano in range(2010, 2026)
        for rev in ("cint", "op")
    ]
    duckdb.sql(
        "SELECT * FROM (VALUES "
        + ", ".join(f"({a}, '{r}', '{i}')" for a, r, i in linhas)
        + ") t(ano, revista_acronimo, idioma_original)"
    ).write_parquet(str(parquet))
    en = pagina._ingles(parquet, list(range(2010, 2026)))
    assert en["desde"] == 2016 and en["pct_antes"] == 0 and en["ri"][-1] == 100 and en["outras"][-1] == 0


def test_sem_classificacao_validacao_nem_geografia(pagina, projeto):
    """Um projeto só com os tópicos: as histórias que dependem do resto somem, sem erro."""
    for arquivo in ("validacao.json", "classificacoes.json", "codebook.json", "agregados.json"):
        (projeto / "saida" / "dados" / arquivo).unlink()
    dados = pagina.gerar(projeto)
    h = dados["historias"]
    assert h["validacao"] is None and h["geografia"] is None  # a classificação continua nas colunas de documentos
    assert dados["numeros"]["kappa_mediano"] is None and dados["numeros"]["instituicoes"] is None
    assert dados["ceu"]["n"] > 0
