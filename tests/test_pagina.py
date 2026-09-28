"""Os dados da abertura do site (scripts/gerar_pagina.py), gerados a partir do exemplo sintético do contrato."""

import base64
import importlib.util
import json
import random
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


def test_historia_da_colaboracao_reconta_a_serie_do_redes_json(pagina, projeto, capsys):
    """A recontagem por artigo (para ter os denominadores) reproduz a série publicada, ano a ano."""
    col = pagina.gerar(projeto)["historias"]["colaboracao"]
    assert "aviso" not in capsys.readouterr().err
    redes = json.loads((projeto / "saida" / "dados" / "redes.json").read_text(encoding="utf-8"))
    serie = {s["ano"]: s for s in redes["colaboracao"]}
    assert col["anos"] == sorted(serie)
    # a série publicada tem 4 casas; a recontagem, a fração exata
    assert col["serie_varios"] == pytest.approx([100 * serie[a]["com_coautoria"] for a in col["anos"]], abs=0.1)
    assert col["serie_ufs"] == pytest.approx([100 * serie[a]["entre_ufs"] for a in col["anos"]], abs=0.1)
    assert col["periodos"] == ["2010–2014", "2021–2025"]
    primeiro = [s["documentos"] for a, s in serie.items() if 2010 <= a <= 2014]
    assert col["autoria"][0] == sum(primeiro)
    assert all(0 < n <= m for n, m in zip(col["localizados"], col["autoria"], strict=True))
    assert isinstance(col["exterior_difere"], bool)


def test_colaboracao_sem_geografia_e_sem_redes(pagina, projeto, capsys):
    (projeto / "saida" / "dados" / "afiliacoes.json").unlink()
    col = pagina.gerar(projeto)["historias"]["colaboracao"]
    assert col["varios"] and col["ufs"] is None and col["serie_ufs"] is None  # só a autoria
    assert "aviso" not in capsys.readouterr().err
    (projeto / "saida" / "dados" / "redes.json").unlink()
    assert pagina.gerar(projeto)["historias"]["colaboracao"] is None


def test_historia_do_canone(pagina, projeto):
    """A parte dos artigos com referências que cita uma das 10 obras mais citadas, sem títulos nem autores."""
    citacoes = json.loads((projeto / "saida" / "dados" / "citacoes.json").read_text(encoding="utf-8"))
    random.Random(3).shuffle(citacoes["canone"])  # o contrato não garante a ordem: o gerador ordena pelos citantes
    (projeto / "saida" / "dados" / "citacoes.json").write_text(json.dumps(citacoes), encoding="utf-8")
    can = pagina.gerar(projeto)["historias"]["canone"]
    base = {i for i, n in enumerate(citacoes["n_referencias"]) if n > 0}
    obras = citacoes["canone"]
    topo = sorted(range(len(obras)), key=lambda k: (-obras[k]["n"], obras[k]["id"]))[:10]
    cc = citacoes["canone_citantes"]
    citantes = {d for d, o in zip(cc["doc"], cc["obra"], strict=True) if o in topo and d in base}
    assert can["base"] == len(base) < can["documentos"]
    assert can["citantes"] == len(citantes) and can["pct"] == round(100 * len(citantes) / len(base))
    assert [d["obras"] for d in can["degraus"]] == [1, 10, len(citacoes["canone"])]  # o exemplo tem menos de 50
    assert [d["pct"] for d in can["degraus"]] == sorted(d["pct"] for d in can["degraus"])
    assert can["antes_2000"] == sum(citacoes["canone"][k]["ano"] < 2000 for k in topo)
    assert can["ingles"] is None  # sem `dados/obras_citadas_openalex.parquet`, sem o idioma
    assert set(can) == {"topo", "citantes", "pct", "degraus", "base", "documentos", "antes_2000", "ingles"}


def test_canone_com_o_idioma_das_obras_e_sem_citacoes(pagina, projeto):
    citacoes = json.loads((projeto / "saida" / "dados" / "citacoes.json").read_text(encoding="utf-8"))
    (projeto / "dados").mkdir()
    linhas = ", ".join(f"('{o['id']}', '{'en' if k % 2 else 'pt'}')" for k, o in enumerate(citacoes["canone"]))
    duckdb.sql(f"SELECT * FROM (VALUES {linhas}) t(id, idioma)").write_parquet(
        str(projeto / "dados" / "obras_citadas_openalex.parquet")
    )
    ingles = {o["id"] for k, o in enumerate(citacoes["canone"]) if k % 2}
    topo = sorted(citacoes["canone"], key=lambda o: (-o["n"], o["id"]))[:10]
    assert pagina.gerar(projeto)["historias"]["canone"]["ingles"] == sum(o["id"] in ingles for o in topo)
    (projeto / "saida" / "dados" / "citacoes.json").unlink()
    assert pagina.gerar(projeto)["historias"]["canone"] is None


def test_diferenca_entre_proporcoes(pagina):
    assert pagina._difere(53, 1100, 94, 1333)  # o exterior no piloto: 4,8% → 7,1% (z ≈ 2,3)
    assert not pagina._difere(50, 1000, 55, 1000)
    assert not pagina._difere(0, 10, 0, 10)


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


def test_citacao_sai_do_citation_cff_e_bate_com_o_readme():
    import yaml

    spec = importlib.util.spec_from_file_location("hooks_docs", RAIZ / "overrides" / "hooks.py")
    hooks = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hooks)
    cff = yaml.safe_load((RAIZ / "CITATION.cff").read_text(encoding="utf-8"))
    citacao = hooks.citacao(cff)
    assert citacao["doi"] == cff["doi"]
    assert f"  doi       = {{{cff['doi']}}}," in citacao["bibtex"]
    # o BibTeX escrito à mão no README e na metodologia é o mesmo que a abertura gera
    for arquivo in ("README.md", "docs/explicacoes/metodologia.md"):
        assert citacao["bibtex"] in (RAIZ / arquivo).read_text(encoding="utf-8"), arquivo
    assert hooks.citacao({**cff, "doi": ""}) == {}
