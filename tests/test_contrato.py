import json
from collections import Counter, defaultdict
from pathlib import Path

import pytest

from mapa_da_ciencia.contrato import modelos as m
from mapa_da_ciencia.contrato.exemplo import gerar_exemplo
from mapa_da_ciencia.contrato.exportar import agregados_geograficos, escrever_dados, tendencia_contrato

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
    # todo documento tem detalhe no fragmento certo, com o idioma do texto de análise
    for doc_id in ids:
        detalhe = fragmentos[m.fragmento_de(doc_id)].documentos[doc_id]
        assert detalhe.fonte_analise in ("resumo", "reserva") and detalhe.idioma_analise
    # tópicos: soma dos n + documentos sem tópico = total; o mesmo por ano
    top = arquivos["topicos"]
    sem_topico = [i for i, t in enumerate(docs.colunas.topico) if t == -1]
    assert sem_topico and sum(t.n for t in top.topicos) + len(sem_topico) == n
    for i, ano in enumerate(top.anos):
        sem_no_ano = sum(docs.colunas.ano[j] == ano for j in sem_topico)
        assert sum(t.serie.n[i] for t in top.topicos) + sem_no_ano == top.total_por_ano[i]
    # ids de tópico não contíguos (como depois de execuções que aposentaram tópicos), todos conhecidos
    ids_topicos = {t.id for t in top.topicos}
    assert max(ids_topicos) >= len(ids_topicos) and set(docs.colunas.topico) <= ids_topicos | {-1}
    # núcleo e ruído: quem o HDBSCAN deixou de fora foi reatribuído ou ficou em -1
    assert all(t.n_nucleo is not None and t.n_nucleo <= t.n for t in top.topicos)
    assert top.outliers.reatribuidos + len(sem_topico) == top.outliers.n == sum(top.outliers.por_ano)
    assert all(docs.dicionarios.atribuicao[docs.colunas.atribuicao[i]] == "vizinho" for i in sem_topico)
    # contagem fracionária: soma dos pesos por documento = 1
    af = arquivos["afiliacoes"].colunas
    por_doc = defaultdict(float)
    for d, p in zip(af.doc, af.peso, strict=True):
        por_doc[d] += p
    assert all(abs(s - 1) < 1e-4 for s in por_doc.values()) and len(por_doc) == n  # todo documento aparece
    # agregados batem com os documentos e com a tabela de afiliações
    agr = arquivos["agregados"]
    assert sum(t[3] for t in agr.topico_ano_revista) == n
    assert abs(sum(agr.pais.values()) + agr.sem_pais - n) < 0.01
    assert abs(sum(agr.instituicao.values()) + agr.sem_afiliacao - n) < 0.01
    assert agr.model_dump() == {**agr.model_dump(), **agregados_geograficos(arquivos["afiliacoes"])}
    assert all(agr.uf[u] <= agr.uf_inteiro[u] for u in agr.uf)  # fracionária ≤ inteira
    dic = arquivos["afiliacoes"].dicionarios
    assert list(dic.uf) == list(m.SIGLAS_UF) and dic.instituicao[-1].id == m.NAO_IDENTIFICADA
    assert -1 in af.instituicao and agr.sem_afiliacao > 0 and agr.instituicao[m.NAO_IDENTIFICADA] > 0
    # sem tópico por ano e tendências: o gabarito é a função de referência aplicada às séries
    assert top.outliers.sem_topico_por_ano == [
        top.total_por_ano[i] - sum(t.serie.n[i] for t in top.topicos) for i in range(len(top.anos))
    ]
    for t in [*top.topicos, *top.macrotemas]:
        assert t.tendencia == tendencia_contrato(t.serie.n, top.total_por_ano, top.anos)
    for mt in top.macrotemas:
        series = [t.serie.n for t in top.topicos if t.id in mt.topicos]
        assert mt.serie.n == [sum(col) for col in zip(*series, strict=True)]
    assert {t.tendencia.direcao for t in top.topicos} >= {"alta", "queda", "estavel"}
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
