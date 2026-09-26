import json
from collections import Counter, defaultdict
from pathlib import Path

import pytest

from mapa_da_ciencia.contrato import modelos as m
from mapa_da_ciencia.contrato.exemplo import gerar_exemplo
from mapa_da_ciencia.contrato.exportar import escrever_dados

RAIZ = Path(__file__).resolve().parent.parent
EXEMPLO = RAIZ / "contrato" / "exemplo" / "dados"


@pytest.fixture(scope="module")
def exemplo():
    return gerar_exemplo(n_docs=400, semente=1)


def test_fragmento_e_estavel_e_cobre_64_valores():
    assert m.fragmento_de("exemplo:00000") == m.fragmento_de("exemplo:00000")
    valores = {m.fragmento_de(f"doc:{i}") for i in range(5000)}
    assert valores == {f"{i:02x}" for i in range(64)}
    # valores fixos: o frontend implementa a mesma função e testa contra estes
    assert m.fragmento_de("") == "05"
    assert m.fragmento_de("doi:10.1590/1807-019120243011") == m.fragmento_de("doi:10.1590/1807-019120243011")


def test_exemplo_e_deterministico():
    a1, f1 = gerar_exemplo(n_docs=120, semente=3)
    a2, f2 = gerar_exemplo(n_docs=120, semente=3)
    assert {k: v.model_dump() for k, v in a1.items()} == {k: v.model_dump() for k, v in a2.items()}
    assert f1.keys() == f2.keys()


def test_documentos_rejeita_colunas_de_tamanhos_diferentes(exemplo):
    arquivos, _ = exemplo
    dados = arquivos["documentos"].model_dump()
    dados["colunas"]["ano"] = dados["colunas"]["ano"][:-1]
    with pytest.raises(ValueError, match="tamanho diferente"):
        m.Documentos.model_validate(dados)


def test_consistencia_interna_do_exemplo(exemplo):
    arquivos, fragmentos = exemplo
    docs = arquivos["documentos"]
    n = docs.n
    ids = docs.colunas.id
    # todo documento tem detalhe no fragmento certo
    for doc_id in ids:
        assert doc_id in fragmentos[m.fragmento_de(doc_id)].documentos
    # tópicos: soma dos n = total de documentos; séries somam o total por ano
    top = arquivos["topicos"]
    assert sum(t.n for t in top.topicos) == n
    for i, _ano in enumerate(top.anos):
        assert sum(t.serie.n[i] for t in top.topicos) == top.total_por_ano[i]
    # contagem fracionária: soma dos pesos por documento = 1
    af = arquivos["afiliacoes"].colunas
    por_doc = defaultdict(float)
    for d, p in zip(af.doc, af.peso, strict=True):
        por_doc[d] += p
    assert all(abs(s - 1) < 1e-4 for s in por_doc.values())
    # agregados batem com os documentos
    agr = arquivos["agregados"]
    assert sum(t[3] for t in agr.topico_ano_revista) == n
    assert abs(sum(agr.pais.values()) - len(por_doc)) < 0.01
    # vizinhos apontam para índices válidos e não para o próprio documento
    for i, viz in enumerate(docs.colunas.vizinhos):
        assert len(viz) == 5 and i not in viz and all(0 <= j < n for j in viz)


def test_evidencias_literais_apontam_para_o_trecho(exemplo):
    _, fragmentos = exemplo
    for frag in fragmentos.values():
        for det in frag.documentos.values():
            if det.resumo is None:
                continue
            for ev in det.evidencias.values():
                if ev.status == "literal":
                    assert det.resumo[ev.inicio : ev.fim] == ev.evidencia


def test_exemplo_versionado_valida_contra_o_contrato():
    """Os arquivos em contrato/exemplo/dados (usados pelo frontend) respeitam os modelos."""
    for nome, modelo in m.ARQUIVOS.items():
        if nome == "fragmento":
            continue
        modelo.model_validate(json.loads((EXEMPLO / f"{nome}.json").read_text(encoding="utf-8")))
    frags = sorted((EXEMPLO / "detalhes").glob("*.json"))
    assert len(frags) == 64
    m.Fragmento.model_validate(json.loads(frags[0].read_text(encoding="utf-8")))


def test_escrever_dados(tmp_path, exemplo):
    arquivos, fragmentos = exemplo
    escritos = escrever_dados(tmp_path, arquivos, fragmentos)
    assert (tmp_path / "documentos.json").exists()
    assert len(list((tmp_path / "detalhes").glob("*.json"))) == len(fragmentos)
    assert len(escritos) == len(arquivos) + len(fragmentos)
    # nenhum e-mail escapa para o contrato
    texto = "".join(p.read_text(encoding="utf-8") for p in escritos)
    assert "@" not in texto.replace("@digest", "")


def test_licencas_sem_permissao_nao_publicam_resumo(exemplo):
    _, fragmentos = exemplo
    contagem = Counter()
    for frag in fragmentos.values():
        for det in frag.documentos.values():
            contagem[det.licenca] += 1
            if det.licenca == "desconhecida":
                assert det.resumo is None
    assert contagem["desconhecida"] > 0
