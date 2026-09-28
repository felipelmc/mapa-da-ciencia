"""O protocolo por arquivos do supervisor: respostas antigas, reimportação, outro supervisor e escolhas inválidas."""

import json

import test_juri_pipeline as base
import yaml

from mapa_da_ciencia.juri.consolidar import ler_resumo, respostas_do_supervisor
from mapa_da_ciencia.juri.pipeline import arquivos_de_respostas, deliberar_juri
from mapa_da_ciencia.juri.supervisor import exportar_pedidos, importar_respostas
from mapa_da_ciencia.juri.votacao import votar
from mapa_da_ciencia.projeto import Projeto

projeto = base.projeto  # a fixture do júri com o Ollama falso


def _ev(p: dict) -> str:
    return " ".join(p["resumo"].split()[:5])


def _lotes(projeto, prefixo: str = "arbitragem") -> list[dict]:
    pasta = projeto.raiz / "juri"
    return [
        json.loads(x)
        for f in sorted(pasta.glob(f"{prefixo}-*.jsonl"))
        if not f.name.endswith(".respostas.jsonl")
        for x in f.read_text(encoding="utf-8").splitlines()
    ]


def _responder(projeto, nome: str, respostas: list[dict]):
    arquivo = projeto.raiz / "juri" / nome
    arquivo.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in respostas) + "\n", encoding="utf-8")
    return arquivo


def _pronto(projeto) -> list[dict]:
    votar(projeto)
    deliberar_juri(projeto)
    exportar_pedidos(projeto, lote=100)
    return _lotes(projeto)


def test_resposta_a_pedido_antigo_nao_cai_nos_candidatos_novos(projeto, apis_falsas):
    alvo = _pronto(projeto)[0]
    assert [c["valor"] for c in alvo["candidatos"]] == ["mista", "qualitativa", "quantitativa"]
    _responder(projeto, "a.respostas.jsonl", [{"id": alvo["id"], "escolha": 3, "evidencia": _ev(alvo)}])
    assert importar_respostas(projeto, arquivos_de_respostas(projeto, [])).aceitas == 1

    # um membro muda de voto (modelo atualizado): os candidatos do mesmo documento × variável mudam
    def responder2(corpo):
        saida = json.loads(base.responder(corpo))
        if corpo["model"] == "gemma4:12b-it-qat" and "abordagem" in saida:
            saida["abordagem"]["valor"] = "revisao"
        return json.dumps(saida, ensure_ascii=False)

    apis_falsas.responder_chat = responder2
    apis_falsas.digests["gemma4:12b-it-qat"] = "ffffffff00000000"
    votar(projeto)
    deliberar_juri(projeto)
    exportar_pedidos(projeto, lote=100)
    novo = next(p for p in _lotes(projeto) if p["id"].rsplit(":", 1)[0] == alvo["id"].rsplit(":", 1)[0])
    assert novo["id"] != alvo["id"]
    assert [c["valor"] for c in novo["candidatos"]] == ["qualitativa", "quantitativa", "revisao"]

    # importar tudo o que está na pasta: a resposta antiga é reconhecida como antiga, e não vira `revisao`
    r = importar_respostas(projeto, arquivos_de_respostas(projeto, []))
    assert (r.aceitas, r.antigas, r.recusadas) == (0, 1, [])
    doc, var = alvo["id"].split(":")[1:3]
    guardada = respostas_do_supervisor(projeto, projeto.codebook.hash(), "arbitragem", "supervisor")[(doc, var)]
    assert guardada["valor"] == "quantitativa"
    assert ler_resumo(projeto).arbitrados == 0


def test_reimportar_a_mesma_resposta_nao_conta_de_novo(projeto):
    linhas = _pronto(projeto)
    respostas = [{"id": p["id"], "escolha": 2, "evidencia": _ev(p), "justificativa": "…"} for p in linhas]
    arquivo = _responder(projeto, "a.respostas.jsonl", respostas)
    assert importar_respostas(projeto, [arquivo]).aceitas == len(linhas)
    r = importar_respostas(projeto, [arquivo])
    assert (r.aceitas, r.repetidas) == (0, len(linhas))
    assert ler_resumo(projeto).arbitrados == len(linhas)


def test_respostas_de_outro_supervisor_nao_se_misturam(projeto):
    linhas = _pronto(projeto)
    respostas = [{"id": p["id"], "escolha": 2, "evidencia": _ev(p)} for p in linhas]
    importar_respostas(projeto, [_responder(projeto, "a.respostas.jsonl", respostas)])
    assert ler_resumo(projeto).pendentes_supervisor == 0

    arquivo = projeto.raiz / "mapa.yaml"
    cfg = yaml.safe_load(arquivo.read_text(encoding="utf-8"))
    cfg["juri"]["supervisor"] = {"nome": "outra-pessoa"}
    arquivo.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    p = Projeto.abrir(projeto.raiz)
    assert exportar_pedidos(p, lote=100).arbitragem == len(linhas)  # outro supervisor começa do zero
    assert ler_resumo(p).pendentes_supervisor == len(linhas)


def test_escolha_precisa_ser_um_numero_de_candidato(projeto):
    p = _pronto(projeto)[0]
    respostas = [
        {"id": p["id"], "escolha": True, "evidencia": _ev(p)},
        {"id": p["id"], "escolha": "1", "evidencia": _ev(p)},
        {"id": p["id"], "escolha": 0, "evidencia": _ev(p)},
    ]
    r = importar_respostas(projeto, [_responder(projeto, "b.respostas.jsonl", respostas)])
    assert r.aceitas == 0 and len(r.recusadas) == 3 and all("escolha" in m for m in r.recusadas)


def test_supervisor_pessoa_nao_sai_documento_a_documento(projeto):
    from mapa_da_ciencia.config import SupervisorJuri
    from mapa_da_ciencia.contrato.classificacao import juri_contrato
    from mapa_da_ciencia.validacao import amostra as va
    from mapa_da_ciencia.validacao.metricas import calcular

    assert SupervisorJuri().familia_efetiva is None and not SupervisorJuri().e_modelo
    assert SupervisorJuri(modo="api").familia_efetiva == "claude" and SupervisorJuri(modo="api").e_modelo
    assert not SupervisorJuri(familia="humano").e_modelo

    arquivo = projeto.raiz / "mapa.yaml"
    cfg = yaml.safe_load(arquivo.read_text(encoding="utf-8"))
    cfg["juri"]["supervisor"] = {"nome": "maria"}  # uma pessoa: sem família de modelo
    arquivo.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    p = Projeto.abrir(projeto.raiz)
    linhas = _pronto(p)
    respostas = [{"id": x["id"], "escolha": 2, "evidencia": _ev(x), "justificativa": "li o método"} for x in linhas]
    importar_respostas(p, [_responder(p, "a.respostas.jsonl", respostas)])
    assert ler_resumo(p).arbitrados == len(linhas)

    referencia = p.raiz / "ref.jsonl"
    with referencia.open("w", encoding="utf-8") as f:
        for doc in va.ler(p).docs:
            valores = {
                v.id: {"valor": "2010–2020" if v.tipo == "texto" else True if v.tipo == "booleana" else
                       [v.categorias[0].valor] if v.tipo == "multipla" else v.categorias[0].valor}
                for v in p.codebook.variaveis
            }  # fmt: skip
            f.write(json.dumps({"doc": doc, "respostas": valores}, ensure_ascii=False) + "\n")
    va.importar(p, referencia, "claude-opus", tipo="referencia")
    v = calcular(p)
    assert not v.metrica("abordagem", "claude-opus", "juri-supervisor").circular
    resumo, por_doc = juri_contrato(p, v)
    assert resumo.supervisor == "maria" and resumo.familia_supervisor is None
    decisoes = [d for doc in por_doc.values() for d in doc.values() if d.etapa == "sem_maioria"]
    assert decisoes and all(d.supervisor is None and d.justificativa is None for d in decisoes)
    assert all(d.valor == d.valor_sem_supervisor for d in decisoes)


def test_sorteio_da_auditoria_e_estavel_e_segue_a_config():
    from types import SimpleNamespace

    from mapa_da_ciencia.juri.supervisor import sorteio_auditoria

    def projeto_com(n: int):
        return SimpleNamespace(
            config=SimpleNamespace(juri=SimpleNamespace(auditoria=n), validacao=SimpleNamespace(semente=7))
        )

    def decisao(doc: str, etapa: str = "unanime"):
        return SimpleNamespace(doc=doc, etapa=etapa, variavel=SimpleNamespace(id="abordagem", tipo="categorica"))

    decisoes = [decisao(f"d{i:02d}") for i in range(30)]
    tres = sorteio_auditoria(projeto_com(3), decisoes)
    assert len(tres) == 3 and tres == sorteio_auditoria(projeto_com(3), list(reversed(decisoes)))
    cinco = sorteio_auditoria(projeto_com(5), decisoes)
    assert cinco[:3] == tres and len(cinco) == 5  # mudar o tamanho só acrescenta no fim

    # um item sorteado deixa de ser unânime: sai, e os outros continuam
    fora = tres[0][0]
    outras = [decisao(d.doc, "maioria") if d.doc == fora else d for d in decisoes]
    depois = sorteio_auditoria(projeto_com(3), outras)
    assert fora not in {doc for doc, _ in depois} and set(tres[1:]) <= set(depois)


def test_respostas_diferentes_em_dois_arquivos_nao_alternam(projeto):
    p = _pronto(projeto)[0]
    _responder(projeto, "a.respostas.jsonl", [{"id": p["id"], "escolha": 1, "evidencia": _ev(p)}])
    _responder(projeto, "b.respostas.jsonl", [{"id": p["id"], "escolha": 2, "evidencia": _ev(p)}])
    doc, var = p["id"].split(":")[1:3]

    def valor():
        return respostas_do_supervisor(projeto, projeto.codebook.hash(), "arbitragem", "supervisor")[(doc, var)][
            "valor"
        ]

    r = importar_respostas(projeto, arquivos_de_respostas(projeto, []))
    assert r.aceitas == 1 and r.conflitos == [p["id"]]
    primeiro = valor()
    assert primeiro == p["candidatos"][1]["valor"]  # vale o último arquivo em ordem alfabética (b)
    for _ in range(3):
        r = importar_respostas(projeto, arquivos_de_respostas(projeto, []))
        assert (r.aceitas, r.repetidas) == (0, 1) and valor() == primeiro


def test_pedido_de_outro_codebook_e_indice_antigo(projeto):
    linhas = _pronto(projeto)
    indice_arquivo = projeto.raiz / "juri" / "pedidos.json"
    indice = json.loads(indice_arquivo.read_text(encoding="utf-8"))
    respostas = [{"id": x["id"], "escolha": 1, "evidencia": _ev(x)} for x in linhas[:2]]

    # um pedido exportado com outro codebook não vale, mesmo com os mesmos candidatos
    indice[linhas[0]["id"]]["codebook"] = "outro-codebook"
    # um índice gravado por uma versão anterior (sem a variável nem o codebook) continua legível
    for chave in ("variavel", "codebook"):
        indice[linhas[1]["id"]].pop(chave)
    indice_arquivo.write_text(json.dumps(indice), encoding="utf-8")
    r = importar_respostas(projeto, [_responder(projeto, "a.respostas.jsonl", respostas)])
    assert (r.aceitas, r.antigas, r.recusadas) == (1, 1, [])
