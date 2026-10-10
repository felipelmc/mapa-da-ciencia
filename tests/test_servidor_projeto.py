"""Rotas do projeto no painel: estado das etapas, modelos e download, estimativa, configuração e codebook."""

import threading

import pytest
import yaml
from fastapi.testclient import TestClient
from test_servidor_jobs import LOCAL, esperar_estado, ler_sse

import mapa_da_ciencia.api as mapa
from mapa_da_ciencia.coleta import coletar
from mapa_da_ciencia.llm.perfis import PERFIS
from mapa_da_ciencia.projeto import Projeto
from mapa_da_ciencia.servidor.app import criar_app


@pytest.fixture
def projeto(tmp_path, apis_falsas):
    return Projeto.criar(
        tmp_path / "op", modelo="ciencia-politica", perfil=PERFIS["leve"], revistas=["0104-6276"], anos=(2024, 2024)
    )


@pytest.fixture
def cliente(projeto, tmp_path):
    with TestClient(criar_app(pasta_dados=projeto.saida / "dados", projeto=projeto, estatico=tmp_path / "x"),
                    base_url=LOCAL) as c:  # fmt: skip
        yield c


def test_estado_das_etapas(cliente, projeto):
    e = cliente.get("/api/projeto/etapas").json()
    assert {k: v["estado"] for k, v in e.items()} == dict.fromkeys(
        ["coleta", "topicos", "geografia", "redes", "classificacao", "validacao"], "pendente"
    )
    coletar(projeto)
    mapa.classificar(projeto, limite=3, progresso=False)
    e = cliente.get("/api/projeto/etapas").json()
    assert e["coleta"]["estado"] == "em_dia" and e["coleta"]["ultima"]["contagens"]["documentos"] == 25
    assert e["topicos"]["estado"] == "pendente" and e["classificacao"]["estado"] == "incompleta"  # parcial
    mapa.amostra_de_validacao(projeto, n=10)
    e = cliente.get("/api/projeto/etapas").json()
    assert e["validacao"] == {"estado": "incompleta", "ultima": None, "amostra": {"n": 10, "codificados": 0}}
    # um codebook novo deixa a classificação desatualizada, não só incompleta
    cb = projeto.raiz / "codebook.yaml"
    cb.write_text(cb.read_text(encoding="utf-8").replace('versao: "0.1"', 'versao: "0.2"'), encoding="utf-8")
    projeto._codebook = None
    assert cliente.get("/api/projeto/etapas").json()["classificacao"]["estado"] == "desatualizada"


def test_modelos_e_download(cliente, projeto, apis_falsas):
    m = cliente.get("/api/modelos").json()
    assert m["ollama"]["no_ar"] and {x["nome"] for x in m["instalados"]} >= {"qwen3.5:4b", "qwen3-embedding:0.6b"}
    assert [p["nome"] for p in m["perfis"]] == ["leve", "padrao", "forte"] and m["perfil_sugerido"] in PERFIS
    assert m["projeto"]["classificacao"] == {"modelo": "qwen3.5:4b", "instalado": True, "download_gb": 3.4}

    assert cliente.post("/api/modelos/baixar", json={"modelo": "rm -rf /"}).status_code == 422
    job = cliente.post("/api/modelos/baixar", json={"modelo": "gemma4:26b"}).json()["id"]
    eventos = ler_sse(cliente, job)
    etapas = [d["nome"] for _, t, d in eventos if t == "etapa"]
    assert etapas == ["Baixando gemma4:26b (aaaaaaaaaaaa)", "Baixando gemma4:26b (bbbbbbbbbbbb)"]
    avancos = [(d["etapa"], d["feito"], d["total"]) for _, t, d in eventos if t == "avanco"]
    assert avancos[-1] == ("Baixando gemma4:26b (bbbbbbbbbbbb)", 2, 2)
    assert cliente.get(f"/api/jobs/{job}").json()["resumo"]["frase"] == "gemma4:26b baixado (1,5 GB)."
    assert "gemma4:26b" in {x["nome"] for x in cliente.get("/api/modelos").json()["instalados"]}

    job = cliente.post("/api/modelos/baixar", json={"modelo": "nao-existe:1b"}).json()["id"]
    j = esperar_estado(cliente, job, {"falhou"})
    assert "file does not exist" in j["erro"]


def test_estimativa_da_classificacao(cliente, projeto):
    assert cliente.get("/api/estimativa/classificacao").json()["documentos"] == 0
    coletar(projeto)
    e = cliente.get("/api/estimativa/classificacao").json()
    assert e["documentos"] == 25 and e["pendentes"] == 25 and e["estimativa_s"] is None
    mapa.classificar(projeto, limite=5, progresso=False)
    e = cliente.get("/api/estimativa/classificacao").json()
    assert (e["classificados"], e["pendentes"]) == (5, 20) and e["estimativa_s"] is not None


def test_configuracao_sem_perder_comentarios(cliente, projeto):
    arquivo = projeto.raiz / "mapa.yaml"
    assert cliente.get("/api/configuracao").json()["recorte"]["anos"] == [2024, 2024]
    r = cliente.patch("/api/configuracao", json={"recorte": {"anos": [2020, 2024]}, "titulo": "OP, 2020–2024"})
    assert r.status_code == 200 and r.json()["recorte"]["anos"] == [2020, 2024]
    texto = arquivo.read_text(encoding="utf-8")
    assert "# SciELO Brasil" in texto and "OP, 2020–2024" in texto and "# Opinião Pública" in texto
    assert yaml.safe_load(texto)["recorte"]["anos"] == [2020, 2024]
    assert projeto.config.recorte.anos == (2020, 2024)  # o projeto aberto no painel já vê a mudança

    antes = arquivo.read_text(encoding="utf-8")
    r = cliente.patch("/api/configuracao", json={"recorte": {"anos": ["dois mil"]}})
    assert r.status_code == 422 and "mapa.yaml ficaria inválido" in r.json()["detail"]
    assert arquivo.read_text(encoding="utf-8") == antes
    r = cliente.patch("/api/configuracao", json={"titulo": "x"}, headers={"Origin": "https://malicioso.example"})
    assert r.status_code == 403


def test_codebook(cliente, projeto):
    cb = cliente.get("/api/codebook").json()
    assert cb["hash"] == projeto.codebook.hash() and cb["variaveis"][0]["id"] == "abordagem"
    cb["variaveis"][0]["categorias"][0]["definicao"] = "Números e estatística."
    novo = cliente.put("/api/codebook", json=cb).json()
    assert (
        novo["hash"] != cb["hash"] and projeto.codebook.variaveis[0].categorias[0].definicao == "Números e estatística."
    )
    texto = (projeto.raiz / "codebook.yaml").read_text(encoding="utf-8")
    assert texto.startswith("# Codebook de exemplo") and "Números e estatística." in texto

    cb["variaveis"][0]["categorias"] = cb["variaveis"][0]["categorias"][:1]  # categórica com uma categoria só
    r = cliente.put("/api/codebook", json=cb)
    assert r.status_code == 422 and "codebook.yaml ficaria inválido" in r.json()["detail"]


@pytest.mark.parametrize("modelo", ["ciencia-politica", "vazio"])
def test_codebook_sem_mudanca_nao_muda_o_arquivo(modelo, tmp_path):
    """O GET devolve os padrões que a leitura preencheu (`exemplos: []`, `rotulo: null`, `categorias: []` numa
    booleana); devolvê-los no PUT, sem mudar nada, deixa o arquivo como estava, byte a byte."""
    p = Projeto.criar(tmp_path / modelo, modelo=modelo, perfil=PERFIS["leve"])
    arquivo = p.raiz / "codebook.yaml"
    antes = arquivo.read_text(encoding="utf-8")
    with TestClient(criar_app(pasta_dados=p.saida / "dados", projeto=p, estatico=tmp_path / "x"), base_url=LOCAL) as c:
        cb = c.get("/api/codebook").json()
        assert c.put("/api/codebook", json=cb).json()["hash"] == cb["hash"]
        assert arquivo.read_text(encoding="utf-8") == antes
        # mudar uma definição só troca essa linha; tirar as categorias de uma variável que virou booleana as apaga
        variavel = next(v for v in cb["variaveis"] if v["categorias"])
        variavel["categorias"][0]["definicao"] = "Outra definição."
        variavel["tipo"] = "booleana"
        del variavel["categorias"]
        assert c.put("/api/codebook", json=cb).status_code == 200
    depois = arquivo.read_text(encoding="utf-8")
    assert "exemplos: []" not in depois and "categorias: []" not in depois and "rotulo: null" not in depois
    assert yaml.safe_load(depois)["variaveis"][cb["variaveis"].index(variavel)].get("categorias") is None


def test_nao_muda_o_projeto_com_uma_etapa_rodando(projeto, tmp_path):
    liberar = threading.Event()

    def lenta(p, o, progresso):
        progresso.etapa("Esperando")
        liberar.wait(10)

    app = criar_app(
        pasta_dados=projeto.saida / "dados", projeto=projeto, estatico=tmp_path / "x", etapas={"lenta": lenta}
    )
    with TestClient(app, base_url=LOCAL) as c:
        job = c.post("/api/etapas/lenta").json()["id"]
        esperar_estado(c, job, {"rodando"})
        assert c.patch("/api/configuracao", json={"titulo": "x"}).status_code == 409
        assert c.put("/api/codebook", json=c.get("/api/codebook").json()).status_code == 409
        liberar.set()
        esperar_estado(c, job, {"concluido"})
        assert c.patch("/api/configuracao", json={"titulo": "x"}).status_code == 200


def test_revistas_do_retrato(cliente):
    achadas = cliente.get("/api/revistas", params={"busca": "opiniao publica"}).json()
    assert achadas[0]["issn"] == "0104-6276" and achadas[0]["titulo"] == "Opinião Pública"
    pedidas = cliente.get("/api/revistas", params={"issn": "0011-5258,0104-6276,9999-9999"}).json()
    assert [r["acronimo"] for r in pedidas] == ["dados", "op"]
    assert len(cliente.get("/api/revistas", params={"busca": "a"}).json()) <= 50


def test_redes_e_uma_etapa_do_painel():
    import pydantic

    from mapa_da_ciencia.servidor.etapas import ETAPAS_DO_PAINEL, OPCOES

    # a vista Redes some quando outra etapa a desatualiza: o painel precisa refazê-la sem a CLI
    assert "redes" in ETAPAS_DO_PAINEL and OPCOES["redes"]().model_dump() == {}
    with pytest.raises(pydantic.ValidationError):
        OPCOES["redes"](limite=3)


# ---------------------------------------------------------------- rótulos dos tópicos
ROTULOS_COM_SECOES = """\
# rotulos.yaml — exemplo. Rótulos corrigidos à mão.
topicos:
  # --- rótulos que os títulos desmentem ---
  14:  # era "Política externa sob Lula"
    rotulo: Política externa brasileira
    descricao: Os trabalhos analisam a política externa brasileira.
  26:  # a descrição do modelo termina truncada
    rotulo: Cooperação Sul-Sul e desenvolvimento
    descricao: Os trabalhos analisam a cooperação Sul-Sul.

  # --- rótulos que nomeiam só uma parte do tópico ---
  0:  # era "Capacidades estatais municipais"
    rotulo: Federalismo e capacidades estatais
    descricao: Os trabalhos analisam o federalismo.
macrotemas:
  1:
    rotulo: Instituições e políticas
    descricao: As instituições políticas.
"""


def _com_topicos(projeto):
    """Um resultado de tópicos mínimo (quatro tópicos em dois macrotemas), sem rodar a etapa."""
    from mapa_da_ciencia.topicos.resultado import PASTA, MacroResultado, Resultado, TopicoResultado

    def topico(i, macro, rotulo, palavras):
        return TopicoResultado(i, macro, rotulo, f"Sobre {rotulo}.", "llm", "#336699",
                               [(p, 1.0) for p in palavras], [], 10, (0.0, 0.0))  # fmt: skip

    Resultado(
        assinatura="x", gerado_em="2026-10-10T00:00:00+00:00", parametros={}, estabilidade_ari=None, ruido=0,
        reatribuidos=0, modelos={},
        topicos=[topico(0, 1, "Capacidades estatais", ["federalismo", "estado"]),
                 topico(14, 1, "Política externa", ["política", "externa", "itamaraty"]),
                 topico(26, 2, "Cooperação", ["cooperação", "sul"]),
                 topico(30, 2, "Gênero", ["gênero", "mulheres"])],
        macrotemas=[MacroResultado(1, "Estado", "", "llm", "#336699", [0, 14]),
                    MacroResultado(2, "Internacional", "", "llm", "#996633", [26, 30])],
    ).gravar(projeto.dados / PASTA, [{"id": "d1", "topico": 0, "atribuicao": "cluster", "x": 0.0, "y": 0.0,
                                      "vizinhos": [], "idioma_analise": "en", "fonte_analise": "resumo"}])  # fmt: skip


def test_rotulos_pelo_painel(cliente, projeto):
    assert cliente.get("/api/rotulos").status_code == 404  # sem tópicos
    _com_topicos(projeto)
    r = cliente.get("/api/rotulos").json()
    assert [t["id"] for t in r["topicos"]] == [0, 14, 26, 30] and r["pendentes"] == 0
    assert r["topicos"][1]["palavras"] == ["política", "externa", "itamaraty"] and r["topicos"][1]["manual"] is None

    # o primeiro rótulo à mão cria o arquivo, com um cabeçalho; um acento que parece perdido vira aviso
    r = cliente.patch("/api/rotulos", json={"topicos": {"14": {"rotulo": "Politica externa", "descricao": ""}}})
    assert r.status_code == 200, r.text
    texto = (projeto.raiz / "rotulos.yaml").read_text(encoding="utf-8")
    assert texto.startswith("# rotulos.yaml: rótulos") and "rotulo: Politica externa" in texto
    assert "descricao" not in texto  # uma descrição vazia não vai para o arquivo
    corpo = r.json()
    assert corpo["topicos"][1]["manual"] == {"rotulo": "Politica externa", "descricao": ""}
    assert corpo["pendentes"] == 1 and any("“politica”" in a and "“política”" in a for a in corpo["avisos"])

    # um número que não existe e um rótulo vazio são recusados, sem mudar o arquivo
    assert cliente.patch("/api/rotulos", json={"topicos": {"999": {"rotulo": "X"}}}).status_code == 422
    assert cliente.patch("/api/rotulos", json={"topicos": {"14": {"rotulo": ""}}}).status_code == 422
    assert (projeto.raiz / "rotulos.yaml").read_text(encoding="utf-8") == texto


def test_rotulos_pelo_painel_mantem_os_comentarios(cliente, projeto):
    _com_topicos(projeto)
    arquivo = projeto.raiz / "rotulos.yaml"
    arquivo.write_text(ROTULOS_COM_SECOES, encoding="utf-8")
    # tirar a última entrada de uma seção não leva junto o cabeçalho da seção seguinte (que o ruamel prende a ela)
    r = cliente.patch("/api/rotulos", json={"topicos": {"26": None, "30": {"rotulo": "Gênero e política"}}})
    assert r.status_code == 200, r.text
    texto = arquivo.read_text(encoding="utf-8")
    assert "26:" not in texto and "Cooperação Sul-Sul" not in texto
    for comentario in ("# rotulos.yaml — exemplo", "# --- rótulos que os títulos desmentem ---",
                       '# era "Política externa sob Lula"', "# --- rótulos que nomeiam só uma parte do tópico ---",
                       '# era "Capacidades estatais municipais"'):  # fmt: skip
        assert comentario in texto, comentario
    assert texto.index("# --- rótulos que nomeiam") < texto.index("  0:")
    assert yaml.safe_load(texto)["topicos"][30] == {"rotulo": "Gênero e política"}


def test_rotulos_recusados_com_uma_etapa_rodando(cliente, projeto):
    from mapa_da_ciencia.trava_etapas import uma_etapa_por_vez

    _com_topicos(projeto)
    segurando, soltar = threading.Event(), threading.Event()

    def terminal():
        with uma_etapa_por_vez(projeto, "topicos"):
            segurando.set()
            soltar.wait(10)

    t = threading.Thread(target=terminal)
    t.start()
    try:
        assert segurando.wait(5)
        r = cliente.patch("/api/rotulos", json={"topicos": {"14": {"rotulo": "Outro"}}})
        assert r.status_code == 409 and "topicos" in r.json()["detail"]
    finally:
        soltar.set()
        t.join()
    assert not (projeto.raiz / "rotulos.yaml").exists()
