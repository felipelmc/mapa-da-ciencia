"""O júri de ponta a ponta com o Ollama falso: votação, deliberação, pedidos ao supervisor, respostas e relatório.

Três "modelos" discordam de propósito: em `abordagem`, cada um escolhe uma categoria (sem maioria, vai para o
supervisor); em `subarea`, o `qwen3.5:9b` fica sozinho (maioria, com deliberação); no resto, todos concordam.
"""

import json

import pytest
import yaml

from mapa_da_ciencia.coleta import coletar
from mapa_da_ciencia.juri.consolidar import ler_resumo
from mapa_da_ciencia.juri.pipeline import deliberar_juri, estado
from mapa_da_ciencia.juri.relatorio import gerar
from mapa_da_ciencia.juri.supervisor import auditoria, exportar_pedidos, importar_respostas, wilson
from mapa_da_ciencia.juri.votacao import votar
from mapa_da_ciencia.llm.perfis import PERFIS
from mapa_da_ciencia.projeto import Projeto
from mapa_da_ciencia.validacao import amostra as va
from mapa_da_ciencia.validacao.metricas import calcular

MEMBROS = ["qwen3.5:4b", "qwen3.5:9b", "gemma4:12b-it-qat"]
INDICE = {m: i for i, m in enumerate(MEMBROS)}


def _resumo_do_pedido(corpo: dict) -> list[str]:
    documento = next(m["content"] for m in corpo["messages"] if m["role"] == "user")
    return documento.split("Resumo:", 1)[-1].split()


def responder(corpo: dict) -> str:
    """Cada membro responde de um jeito, na classificação e na deliberação (onde mantém o voto)."""
    i = INDICE[corpo["model"]]
    evidencia = " ".join(_resumo_do_pedido(corpo)[:8])
    saida = {}
    for var, prop in corpo["format"]["properties"].items():
        valor = prop["properties"]["valor"]
        if valor["type"] == "boolean":
            v: object = True
        elif valor["type"] == "array":
            v = [valor["items"]["enum"][0]]
        elif "enum" in valor:
            enum = valor["enum"]
            v = enum[i] if var == "abordagem" else enum[1] if var == "subarea" and i == 1 else enum[0]
        else:
            v = "2010–2020"
        saida[var] = {"evidencia": evidencia, "valor": v}
    return json.dumps(saida, ensure_ascii=False)


@pytest.fixture
def projeto(tmp_path, apis_falsas):
    apis_falsas.modelos_ollama["gemma4:12b-it-qat"] = 0.5
    apis_falsas.responder_chat = responder
    p = Projeto.criar(
        tmp_path / "op", modelo="ciencia-politica", perfil=PERFIS["leve"], revistas=["0104-6276"], anos=(2024, 2024)
    )
    arquivo = p.raiz / "mapa.yaml"
    cfg = yaml.safe_load(arquivo.read_text(encoding="utf-8"))
    cfg["juri"] = {"membros": MEMBROS, "auditoria": 3, "supervisor": {"familia": "claude"}}
    cfg.setdefault("validacao", {})["familias"] = {"claude-opus": "claude"}
    arquivo.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    coletar(p)
    p = Projeto.abrir(p.raiz)
    va.sortear(p, n=8)
    return p


def test_juri_de_ponta_a_ponta(projeto, apis_falsas):
    n_amostra = len(va.ler(projeto).docs)
    r = votar(projeto)
    assert set(r.classificados) == set(MEMBROS) and not r.ja_prontos
    assert votar(projeto).ja_prontos == MEMBROS  # tudo no cache

    chamadas = apis_falsas.chamadas["ollama_chat"]
    d, resumo = deliberar_juri(projeto)
    assert d.documentos == n_amostra and d.chamadas == len(MEMBROS) * n_amostra
    assert apis_falsas.chamadas["ollama_chat"] == chamadas + d.chamadas
    variaveis = len(projeto.codebook.variaveis)
    assert sum(sum(e.values()) for e in resumo.etapas.values()) == n_amostra * variaveis
    assert resumo.etapas["abordagem"]["sem_maioria"] == n_amostra
    assert resumo.etapas["subarea"]["deliberacao"] == n_amostra and resumo.virou["subarea"] == 0
    assert resumo.etapas["brasil_como_caso"]["unanime"] == n_amostra
    assert resumo.pendentes_supervisor == n_amostra

    # a deliberação: mesmo prefixo da classificação, a própria resposta e os pares sem nome
    deliberacoes = [c for c in apis_falsas.pedidos_chat if len(c["messages"]) == 4]
    assert len(deliberacoes) == d.chamadas
    exemplo = deliberacoes[0]
    classificacao = next(c for c in apis_falsas.pedidos_chat if len(c["messages"]) == 2)
    assert exemplo["messages"][0] == classificacao["messages"][0]
    assert set(exemplo["format"]["properties"]) == {"abordagem", "subarea"}
    texto = json.dumps(exemplo["messages"][3], ensure_ascii=False)
    assert "Modelo A" in texto and not any(m in texto for m in MEMBROS)

    # retomada: rodar de novo não chama os modelos
    chamadas = apis_falsas.chamadas["ollama_chat"]
    d2, _ = deliberar_juri(projeto)
    assert d2.chamadas == 0 and d2.do_cache == d.chamadas and apis_falsas.chamadas["ollama_chat"] == chamadas

    # pedidos ao supervisor: sem nomes dos modelos, com as instruções
    pedidos = exportar_pedidos(projeto, lote=5)
    assert (pedidos.arbitragem, pedidos.auditoria) == (n_amostra, 3)
    pasta = projeto.raiz / "juri"
    assert (pasta / "instrucoes-supervisor.md").exists()
    linhas = [json.loads(x) for f in sorted(pasta.glob("arbitragem-*.jsonl")) for x in f.read_text().splitlines()]
    assert len(linhas) == n_amostra and not any(m in json.dumps(linhas) for m in MEMBROS)
    assert all(len(p["candidatos"]) == 3 for p in linhas)
    auditorias = [json.loads(x) for x in (pasta / "auditoria-01.jsonl").read_text().splitlines()]

    def ev(p):
        return " ".join(p["resumo"].split()[:5])

    respostas = [
        {"id": p["id"], "escolha": 2, "evidencia": ev(p), "justificativa": "…", "nenhum_adequado": False}
        for p in linhas[2:]
    ]
    respostas.append({"id": linhas[0]["id"], "escolha": 9, "evidencia": ev(linhas[0])})  # fora dos candidatos
    respostas.append({"id": linhas[1]["id"], "escolha": 1, "evidencia": "um trecho que não está no texto"})
    respostas += [{"id": a["id"], "correto": True, "evidencia": ev(a), "justificativa": "ok"} for a in auditorias]
    arquivo = pasta / "arbitragem-01.respostas.jsonl"
    arquivo.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in respostas), encoding="utf-8")
    r = importar_respostas(projeto, [arquivo])
    assert r.aceitas == n_amostra - 2 + 3 and len(r.recusadas) == 2
    assert any("escolha" in m for m in r.recusadas) and any("evidência" in m for m in r.recusadas)
    resumo = ler_resumo(projeto)
    assert resumo.arbitrados == n_amostra - 2 and resumo.pendentes_supervisor == 2
    a = auditoria(projeto)
    assert (a.n, a.erros) == (3, 0)
    assert exportar_pedidos(projeto).arbitragem == 2  # só o que falta

    # validação: o supervisor e a referência da mesma família ficam marcados como circulares
    referencia = projeto.raiz / "ref.jsonl"
    with referencia.open("w", encoding="utf-8") as f:
        for doc in va.ler(projeto).docs:
            valores = {v.id: {"valor": "2010–2020" if v.tipo == "texto" else True if v.tipo == "booleana" else
                              [v.categorias[0].valor] if v.tipo == "multipla" else v.categorias[0].valor}
                       for v in projeto.codebook.variaveis}  # fmt: skip
            f.write(json.dumps({"doc": doc, "respostas": valores}, ensure_ascii=False) + "\n")
    va.importar(projeto, referencia, "claude-opus", tipo="referencia")
    v = calcular(projeto)
    nomes = {p.nome for p in v.participantes}
    assert {"juri-r1", "juri", "juri-supervisor", *MEMBROS} <= nomes
    assert v.metrica("abordagem", "claude-opus", "juri-supervisor").circular
    assert not v.metrica("abordagem", "claude-opus", "juri").circular
    destino, numeros = gerar(projeto)
    texto = destino.read_text(encoding="utf-8")
    assert "Limite superior" in texto and "(circular)" in texto and numeros.referencia == "claude-opus"
    assert numeros.deliberacao["qwen3.5:9b"]["mudou"] == 0
    assert estado(projeto).proximo.startswith("mapa juri exportar-pedidos")


def test_wilson():
    assert wilson(0, 0) is None
    baixo, alto = wilson(0, 40)
    assert baixo == 0 and 0.08 < alto < 0.09
    baixo, alto = wilson(4, 40)
    assert 0.03 < baixo < 0.05 and 0.22 < alto < 0.24


def test_config_do_juri():
    from mapa_da_ciencia.config import ConfigJuri, ErroConfig  # noqa: F401

    with pytest.raises(ValueError):
        ConfigJuri(membros=["qwen3.5:9b"])
    with pytest.raises(ValueError):
        ConfigJuri(membros=["qwen3.5:9b", "qwen3.5:9b"])
    assert ConfigJuri().supervisor.modo == "arquivo" and not ConfigJuri().supervisor.enviar_textos


class ClienteFalso:
    """Um substituto do `anthropic.Anthropic`: responde cada pedido como um supervisor, e conta o uso."""

    def __init__(self) -> None:
        self.pedidos: list[dict] = []
        self.messages = self

    def create(self, **kw):
        from types import SimpleNamespace

        self.pedidos.append(kw)
        pedido = json.loads(kw["messages"][0]["content"])
        evidencia = " ".join(pedido["resumo"].split()[:5])
        if pedido["tarefa"] == "arbitragem":
            r = {"escolha": 1, "evidencia": evidencia, "justificativa": "…", "nenhum_adequado": False}
        else:
            r = {"correto": True, "valor_sugerido": "", "evidencia": evidencia, "justificativa": "ok"}
        uso = SimpleNamespace(input_tokens=900, output_tokens=400, cache_read_input_tokens=0,
                              cache_creation_input_tokens=0)  # fmt: skip
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=json.dumps(r))], usage=uso, stop_reason="end_turn"
        )


def test_supervisor_pela_api_com_consentimento_e_limite(projeto):
    from mapa_da_ciencia.config import ErroConfig
    from mapa_da_ciencia.juri.supervisor import supervisionar

    votar(projeto)
    deliberar_juri(projeto)
    with pytest.raises(ErroConfig, match="por arquivos"):
        supervisionar(projeto)
    arquivo = projeto.raiz / "mapa.yaml"
    cfg = yaml.safe_load(arquivo.read_text(encoding="utf-8"))
    cfg["juri"]["supervisor"] = {"modo": "api"}
    arquivo.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ErroConfig, match="enviar_textos"):
        supervisionar(Projeto.abrir(projeto.raiz))
    cfg["juri"]["supervisor"] = {"modo": "api", "enviar_textos": True, "limite_gasto_usd": 5}
    arquivo.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    p = Projeto.abrir(projeto.raiz)

    cliente = ClienteFalso()
    estimativa = supervisionar(p, cliente=cliente)  # sem confirmar: nada sai da máquina
    assert not estimativa.feito and estimativa.pedidos > 0 and not cliente.pedidos
    with pytest.raises(ErroConfig, match="limite de gasto"):
        supervisionar(p, limite_gasto=0.0001, cliente=cliente)

    # um limite que cabe na estimativa, mas acaba no meio: para antes de passar dele
    r = supervisionar(p, limite_gasto=estimativa.estimativa_usd * 1.01, confirmar=True, cliente=cliente)
    assert r.feito and r.respondidos == len(cliente.pedidos) > 0
    assert r.gasto_usd <= estimativa.estimativa_usd * 1.01
    primeiro = cliente.pedidos[0]
    assert primeiro["model"] == "claude-opus-5-5" and primeiro["system"][0]["cache_control"]
    assert primeiro["output_config"]["format"]["type"] == "json_schema"
    assert r.importacao.aceitas == r.respondidos and not r.importacao.recusadas

    r = supervisionar(p, limite_gasto=5, confirmar=True, cliente=ClienteFalso())
    assert ler_resumo(p).pendentes_supervisor == 0 and auditoria(p).n == 3


def test_antes_de_deliberar_nada_e_rotulado_como_deliberacao(projeto):
    from mapa_da_ciencia.config import ErroConfig
    from mapa_da_ciencia.juri.consolidar import consolidar

    votar(projeto)
    n = len(va.ler(projeto).docs)
    resumo = consolidar(projeto)
    assert resumo.etapas["subarea"]["maioria"] == n and resumo.etapas["subarea"]["deliberacao"] == 0
    assert resumo.nao_deliberados == 2 * n  # abordagem e subarea, em todos os documentos
    assert resumo.pendentes_supervisor == 0  # nada vai ao supervisor antes da deliberação
    assert estado(projeto).proximo == "mapa juri deliberar"
    with pytest.raises(ErroConfig, match="deliberar"):
        exportar_pedidos(projeto)
    _, resumo = deliberar_juri(projeto)
    assert resumo.nao_deliberados == 0 and resumo.etapas["subarea"]["deliberacao"] == n


def test_o_juri_fica_na_amostra_mesmo_com_o_corpus_classificado(projeto):
    from mapa_da_ciencia.classificacao.pipeline import OpcoesClassificacao, classificar

    for membro in MEMBROS:
        classificar(projeto, OpcoesClassificacao(modelo=membro))
    n = len(va.ler(projeto).docs)
    d, resumo = deliberar_juri(projeto)
    assert d.documentos == n and resumo.documentos == n
    assert resumo.pendentes_supervisor == n and resumo.nao_deliberados == 0


def test_concordancia_por_estagio_nao_inclui_o_supervisor(projeto):
    votar(projeto)
    deliberar_juri(projeto)
    exportar_pedidos(projeto, lote=1000)
    pasta = projeto.raiz / "juri"
    linhas = [json.loads(x) for f in sorted(pasta.glob("arbitragem-*.jsonl")) for x in f.read_text().splitlines()]
    escolha = next(c["n"] for c in linhas[0]["candidatos"] if c["valor"] == "qualitativa")
    respostas = [
        {"id": p["id"], "escolha": escolha, "evidencia": " ".join(p["resumo"].split()[:5]), "justificativa": "x"}
        for p in linhas
    ]
    arquivo = pasta / "a.respostas.jsonl"
    arquivo.write_text("\n".join(json.dumps(r) for r in respostas), encoding="utf-8")
    importar_respostas(projeto, [arquivo])
    referencia = projeto.raiz / "ref.jsonl"
    with referencia.open("w", encoding="utf-8") as f:
        for doc in va.ler(projeto).docs:
            valores = {
                v.id: {
                    "valor": "2010–2020"
                    if v.tipo == "texto"
                    else True
                    if v.tipo == "booleana"
                    else [v.categorias[0].valor]
                    if v.tipo == "multipla"
                    else "qualitativa"
                    if v.id == "abordagem"
                    else v.categorias[0].valor
                }
                for v in projeto.codebook.variaveis
            }
            f.write(json.dumps({"doc": doc, "respostas": valores}, ensure_ascii=False) + "\n")
    va.importar(projeto, referencia, "claude-opus", tipo="referencia")
    destino, numeros = gerar(projeto)
    sem_maioria = numeros.concordancia_por_etapa["sem_maioria"]
    assert sem_maioria["acertos"] < sem_maioria["n"]  # o voto do presidente, e não a escolha do supervisor
    s = numeros.concordancia_supervisor
    assert s["acertos"] == s["n"] == len(linhas) and s["circular"]
    secao4 = destino.read_text(encoding="utf-8").split("## 4.")[1].split("## 5.")[0]
    assert "circular" in secao4


def test_deliberacao_interrompida_fica_pendente_e_o_status_ve_votacao_nova(projeto, apis_falsas):
    from mapa_da_ciencia.armazenamento import gravar_tabela, ler_tabela
    from mapa_da_ciencia.config import ErroConfig
    from mapa_da_ciencia.juri.consolidar import consolidar
    from mapa_da_ciencia.juri.deliberacao import ARQUIVO, COLUNAS
    from mapa_da_ciencia.juri.estado import pasta_dados

    votar(projeto)
    deliberar_juri(projeto)
    n = len(va.ler(projeto).docs)
    # a deliberação parou no meio: o último membro não deliberou
    arquivo = pasta_dados(projeto, projeto.codebook.hash()) / ARQUIVO
    linhas = [x for x in ler_tabela(arquivo) if x["membro"] != MEMBROS[-1]]
    gravar_tabela(linhas, COLUNAS, arquivo, ordem="doc")
    resumo = consolidar(projeto)
    assert resumo.nao_deliberados == 2 * n and resumo.etapas["subarea"]["deliberacao"] == 0
    assert estado(projeto).proximo == "mapa juri deliberar"
    with pytest.raises(ErroConfig, match="deliberar"):
        exportar_pedidos(projeto)
    _, resumo = deliberar_juri(projeto)  # retoma do cache
    assert resumo.nao_deliberados == 0

    # uma votação nova muda os votos: o status recalcula, e não lê o resumo.json da consolidação anterior
    def responder2(corpo):
        saida = json.loads(responder(corpo))
        if corpo["model"] == "gemma4:12b-it-qat" and "subarea" in saida:
            saida["subarea"]["valor"] = "relacoes_internacionais"
        return json.dumps(saida, ensure_ascii=False)

    apis_falsas.responder_chat = responder2
    apis_falsas.digests["gemma4:12b-it-qat"] = "ffffffff00000000"
    votar(projeto)
    assert estado(projeto).proximo == "mapa juri deliberar"
    _, numeros = gerar(projeto)
    assert numeros.nao_deliberados > 0
    assert "**Atenção:**" in (projeto.raiz / "validacao" / "juri.md").read_text(encoding="utf-8")


def test_limite_abaixo_do_pior_caso_de_uma_chamada_para_antes_de_perguntar(projeto, monkeypatch):
    from mapa_da_ciencia.config import ErroConfig
    from mapa_da_ciencia.juri.supervisor import supervisionar
    from mapa_da_ciencia.llm import anthropic

    monkeypatch.setattr(anthropic, "MAX_TOKENS", 200_000)  # um teto alto: a estimativa cabe, o pior caso não

    votar(projeto)
    deliberar_juri(projeto)
    arquivo = projeto.raiz / "mapa.yaml"
    cfg = yaml.safe_load(arquivo.read_text(encoding="utf-8"))
    cfg["juri"]["supervisor"] = {"modo": "api", "enviar_textos": True}
    arquivo.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    p = Projeto.abrir(projeto.raiz)
    estimativa = supervisionar(p, cliente=ClienteFalso()).estimativa_usd
    with pytest.raises(ErroConfig, match="pior caso"):
        supervisionar(p, limite_gasto=estimativa * 1.01, cliente=ClienteFalso())


def test_mudar_um_rotulo_de_categoria_pede_votar_e_os_votos_vem_do_cache(projeto, apis_falsas):
    votar(projeto)
    deliberar_juri(projeto)
    n = len(va.ler(projeto).docs)
    antes = estado(projeto)
    assert antes.classificados == dict.fromkeys(MEMBROS, n) and antes.proximo != "mapa juri votar"
    # o rótulo de uma categoria, que o modelo não lê: o hash do codebook muda, o cache continua valendo
    arquivo = projeto.raiz / "codebook.yaml"
    cb = yaml.safe_load(arquivo.read_text(encoding="utf-8"))
    cb["variaveis"][0]["categorias"][0]["rotulo"] = "Outro rótulo"
    arquivo.write_text(yaml.safe_dump(cb, allow_unicode=True), encoding="utf-8")
    projeto = Projeto.abrir(projeto.raiz)
    depois = estado(projeto)
    # sem o resultado do codebook novo, nenhum voto conta, e o status pede votar (e não o relatório de um resumo vazio)
    assert depois.classificados == dict.fromkeys(MEMBROS, 0) and depois.proximo == "mapa juri votar"
    assert depois.resumo is None
    chamadas = apis_falsas.chamadas["ollama_chat"]
    r = votar(projeto)
    assert set(r.classificados) == set(MEMBROS)  # regravados…
    assert apis_falsas.chamadas["ollama_chat"] == chamadas  # …do cache, sem chamar o modelo
    assert estado(projeto).classificados == dict.fromkeys(MEMBROS, n)


def test_o_painel_mostra_o_juri_na_validacao(projeto, tmp_path):
    from fastapi.testclient import TestClient

    from mapa_da_ciencia.servidor.app import criar_app

    votar(projeto)
    deliberar_juri(projeto)
    app = criar_app(pasta_dados=projeto.saida / "dados", projeto=projeto, estatico=tmp_path / "x")
    v = TestClient(app, base_url="http://127.0.0.1:8765").get("/api/validacao/metricas").json()
    # como no validacao.json exportado: sem o júri, a vista do painel perdia a seção dele
    assert v["juri"] is not None and v["juri"]["membros"] == MEMBROS
