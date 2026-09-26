"""A amostra de validação (sorteio estratificado, exportação) e as codificações (importação, gravação)."""

import json

import duckdb
import pytest
from typer.testing import CliRunner

import mapa_da_ciencia.api as mapa
from mapa_da_ciencia.cli import app
from mapa_da_ciencia.coleta import coletar
from mapa_da_ciencia.config import ErroConfig
from mapa_da_ciencia.llm.perfis import PERFIS
from mapa_da_ciencia.projeto import Projeto
from mapa_da_ciencia.topicos.resultado import ARQUIVO_ATRIBUICOES
from mapa_da_ciencia.topicos.resultado import PASTA as PASTA_TOPICOS
from mapa_da_ciencia.validacao import amostra as va
from mapa_da_ciencia.validacao.amostra import _alocar

runner = CliRunner()
ENV = {"COLUMNS": "160"}


@pytest.fixture
def projeto(tmp_path, apis_falsas):
    p = Projeto.criar(
        tmp_path / "op", modelo="ciencia-politica", perfil=PERFIS["leve"], revistas=["0104-6276"], anos=(2024, 2024)
    )
    coletar(p)
    cfg = p.raiz / "mapa.yaml"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace("n: 200", "n: 10"), encoding="utf-8")
    return Projeto.abrir(p.raiz)


def _topicos_falsos(p: Projeto) -> dict[str, int]:
    """Um `atribuicoes.parquet` com três tópicos e alguns documentos sem tópico, sem rodar o UMAP."""
    ids = [t.doc for t in va.textos_do_projeto(p)]
    topico = {doc: (i % 4) - 1 for i, doc in enumerate(ids)}  # −1, 0, 1, 2
    pasta = p.dados / PASTA_TOPICOS
    pasta.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("CREATE TABLE a (id VARCHAR, topico INTEGER)")
    con.executemany("INSERT INTO a VALUES (?, ?)", list(topico.items()))
    con.execute(f"COPY a TO '{pasta / ARQUIVO_ATRIBUICOES}' (FORMAT parquet)")
    con.close()
    return topico


def _respostas(p: Projeto, *, primeira: bool = True) -> dict:
    """Uma resposta válida para cada variável do codebook (a primeira categoria, ou a última)."""
    saida = {}
    for v in p.codebook.variaveis:
        if v.tipo == "booleana":
            valor: object = primeira
        elif v.tipo == "multipla":
            valor = [v.categorias[0 if primeira else -1].valor]
        elif v.tipo == "texto":
            valor = "algum texto"
        else:
            valor = v.categorias[0 if primeira else -1].valor
        saida[v.id] = {"valor": valor, "evidencia": ""}
    return saida


@pytest.mark.parametrize(
    ("tamanhos", "n"),
    [({"a": 10, "b": 5, "c": 1}, 8), ({"a": 3, "b": 3}, 10), ({"a": 50, "b": 30, "c": 20, "d": 1}, 3)],
)
def test_alocacao_proporcional(tamanhos, n):
    alocado = _alocar(tamanhos, n)
    assert sum(alocado.values()) == min(n, sum(tamanhos.values()))
    assert all(alocado[e] <= tamanhos[e] for e in tamanhos)
    if n >= len(tamanhos):  # ao menos um de cada estrato, quando cabe
        assert all(alocado[e] >= 1 for e in tamanhos)
    assert _alocar({"a": 10, "b": 5, "c": 1}, 8) == {"a": 4, "b": 3, "c": 1}


def test_sem_topicos_estratifica_pela_revista(projeto):
    a = va.sortear(projeto)
    assert len(a.docs) == len(set(a.docs)) == 10
    assert a.estratificar_por == "revista" and any("tópicos" in aviso for aviso in a.avisos)
    assert va.ler(projeto).docs == a.docs  # guardada
    assert va.sortear(projeto).docs == a.docs  # sem --refazer, a mesma
    assert va.sortear(projeto, refazer=True).docs == a.docs  # mesma semente, mesmo sorteio


def test_estratificada_por_topico(projeto):
    topico = _topicos_falsos(projeto)
    a = va.sortear(projeto, refazer=True)
    assert a.estratificar_por == "topico" and not a.avisos
    assert set(a.por_estrato()) == {"sem tópico", "topico 0", "topico 1", "topico 2"}
    for doc in a.docs:
        esperado = "sem tópico" if topico[doc] < 0 else f"topico {topico[doc]}"
        assert a.estratos[doc] == esperado
    # outra semente, outro sorteio
    cfg = projeto.raiz / "mapa.yaml"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace("semente: 7", "semente: 8", 1), encoding="utf-8")
    outra = va.sortear(Projeto.abrir(projeto.raiz), refazer=True)
    assert outra.semente == 8 and outra.docs != a.docs and len(outra.docs) == 10


def test_exporta_so_o_texto(projeto):
    a = va.sortear(projeto)
    arquivo = va.exportar(projeto, a)
    linhas = [json.loads(linha) for linha in arquivo.read_text(encoding="utf-8").splitlines()]
    assert [linha["doc"] for linha in linhas] == a.docs
    assert all(set(linha) == {"doc", "titulo", "resumo", "idioma"} for linha in linhas)
    assert all(linha["resumo"] and linha["idioma"] == "pt" for linha in linhas)
    assert "@" not in arquivo.read_text(encoding="utf-8")


def test_importar_codificacoes(projeto, tmp_path):
    a = va.sortear(projeto)
    arquivo = tmp_path / "claude.jsonl"
    linhas = [
        {"doc": a.docs[0], "respostas": _respostas(projeto)},
        {"doc": a.docs[1], **_respostas(projeto, primeira=False)},  # forma plana, sem "respostas"
        {"doc": "S0000-00000000000000", "respostas": _respostas(projeto)},  # fora da amostra
        {"doc": a.docs[2], "respostas": {**_respostas(projeto), "abordagem": {"valor": "inventada"}}},
    ]
    arquivo.write_text("\n".join(json.dumps(linha) for linha in linhas) + "\nnão é json\n", encoding="utf-8")
    r = va.importar(projeto, arquivo, "claude-opus", tipo="referencia")
    assert r.documentos == 2 and r.fora_da_amostra == ["S0000-00000000000000"]
    assert len(r.invalidas) == 2 and "inventada" in r.invalidas[0] and "não é JSON" in r.invalidas[1]
    assert va.codificadores(projeto) == {"claude-opus": "referencia"}
    cod = va.codificacoes(projeto, "claude-opus")
    n_var = len(projeto.codebook.variaveis)
    assert len(cod) == 2 * n_var and {c["doc"] for c in cod} == set(a.docs[:2])
    booleana = next(c for c in cod if c["doc"] == a.docs[1] and c["variavel"] == "brasil_como_caso")
    assert booleana["valor"] == "false"

    # reimportar substitui, não duplica
    arquivo.write_text(json.dumps({"doc": a.docs[0], "respostas": _respostas(projeto, primeira=False)}))
    va.importar(projeto, arquivo, "claude-opus", tipo="referencia")
    cod = va.codificacoes(projeto, "claude-opus")
    assert len(cod) == 2 * n_var
    assert next(c for c in cod if c["doc"] == a.docs[0] and c["variavel"] == "brasil_como_caso")["valor"] == "false"


def test_salvar_parcial_e_nome(projeto):
    a = va.sortear(projeto)
    so_uma = {"abordagem": {"valor": "qualitativa", "incerto": True, "nota": "difícil"}}
    assert va.salvar(projeto, "felipe", a.docs[0], so_uma)  # completa: falta o resto
    assert va.salvar(projeto, "felipe", a.docs[0], so_uma, completa=False) == []
    (c,) = va.codificacoes(projeto, "felipe")
    assert (c["valor"], c["incerto"], c["nota"]) == ("qualitativa", 1, "difícil")
    with pytest.raises(ErroConfig, match="Nome de codificador"):
        va.salvar(projeto, "Fe lipe!", a.docs[0], so_uma)


def test_importar_sem_amostra(projeto, tmp_path):
    arquivo = tmp_path / "x.jsonl"
    arquivo.write_text("")
    with pytest.raises(ErroConfig, match="validar amostra"):
        va.importar(projeto, arquivo, "felipe")


def test_classificar_amostra_primeiro(projeto):
    with pytest.raises(ErroConfig, match="amostra de validação"):
        mapa.classificar(projeto, somente_amostra=True, progresso=False)
    a = va.sortear(projeto)
    r = mapa.classificar(projeto, limite=3, progresso=False)
    with mapa.conectar(projeto) as con:
        docs = {d for (d,) in con.execute("SELECT DISTINCT doc FROM classificacoes").fetchall()}
    assert docs == set(a.docs[:3])  # a fila começa pela amostra, na ordem dela
    r = mapa.classificar(projeto, somente_amostra=True, progresso=False)
    assert r.classificados == 10 and r.novos == 7 and r.parcial
    with mapa.conectar(projeto) as con:
        docs = {d for (d,) in con.execute("SELECT DISTINCT doc FROM classificacoes").fetchall()}
    assert docs == set(a.docs)


def test_cli_validar(projeto, tmp_path):
    raiz = str(projeto.raiz)
    r = runner.invoke(app, ["validar", "amostra", "-P", raiz], env=ENV)
    assert r.exit_code == 0, r.output
    assert "Amostra sorteada" in r.output and "10 documentos" in r.output and "validacao/amostra.jsonl" in r.output
    r = runner.invoke(app, ["validar", "amostra", "-P", raiz], env=ENV)
    assert "Amostra já sorteada" in r.output

    docs = va.ler(projeto).docs
    arquivo = tmp_path / "cod.jsonl"
    arquivo.write_text("\n".join(json.dumps({"doc": d, "respostas": _respostas(projeto)}) for d in docs))
    r = runner.invoke(
        app,
        ["validar", "importar", str(arquivo), "-P", raiz, "--codificador", "claude-opus", "--tipo", "referencia"],
        env=ENV,
    )
    assert r.exit_code == 0, r.output
    assert "10 de 10 documentos" in r.output and "claude-opus" in r.output

    arquivo.write_text(json.dumps({"doc": docs[0], "respostas": {"abordagem": {"valor": "x"}}}))
    r = runner.invoke(app, ["validar", "importar", str(arquivo), "-P", raiz, "-c", "felipe"], env=ENV)
    assert r.exit_code == 1 and "Inválida" in r.output
    r = runner.invoke(app, ["validar", "importar", str(arquivo), "-P", raiz, "-c", "felipe", "--tipo", "robo"], env=ENV)
    assert r.exit_code == 1 and "Tipo de codificador" in r.output
