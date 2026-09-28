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
