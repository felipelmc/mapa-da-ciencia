import random

import numpy as np

from mapa_da_ciencia.topicos.identidade import Identidade, estabilizar
from mapa_da_ciencia.topicos.macrotemas import agrupar_macrotemas, numero_de_macrotemas
from mapa_da_ciencia.topicos.paleta import cores_macrotemas

CHAVE = {"modelo": "qwen3-embedding:0.6b@abc", "idioma_analise": "en", "versao_texto": 1}


def _nucleos(tamanhos: list[int]) -> list[set[str]]:
    saida, inicio = [], 0
    for n in tamanhos:
        saida.append({f"d{i:04d}" for i in range(inicio, inicio + n)})
        inicio += n
    return saida


TAMANHOS = [40, 90, 25, 60, 30, 55]
GRUPOS = [1, 0, 1, 0, 2, 2]  # macrotema de cada tópico


def _primeira():
    nucleos = _nucleos(TAMANHOS)
    corpus = set().union(*nucleos)
    return nucleos, corpus, estabilizar(nucleos, GRUPOS, None, CHAVE, corpus)


def test_primeira_execucao_numera_pelo_tamanho():
    _, _, r = _primeira()
    assert r.ids == [3, 0, 5, 1, 4, 2] and r.identidade.proximo_id == 6
    assert r.macros == GRUPOS and set(r.cores_macro.values()) == set(cores_macrotemas(3))
    assert len(set(r.cores)) == 6 and not r.casados


def test_repetir_mantem_ids_cores_e_macrotemas(tmp_path):
    nucleos, corpus, r = _primeira()
    r.identidade.gravar(tmp_path)
    lida = Identidade.ler(tmp_path)
    assert lida == r.identidade
    de_novo = estabilizar(nucleos, GRUPOS, lida, CHAVE, corpus)
    assert (de_novo.ids, de_novo.macros, de_novo.cores) == (r.ids, r.macros, r.cores)


def test_corpus_maior_e_menor_e_ordem_trocada():
    nucleos, corpus, r = _primeira()
    rng = random.Random(1)
    novos = []
    for i, n in enumerate(nucleos):  # −5% dos membros saem, +10% de documentos novos entram
        fica = {d for d in n if rng.random() > 0.05}
        novos.append(fica | {f"novo{i}-{k}" for k in range(len(n) // 10)})
    ordem = [4, 2, 0, 5, 1, 3]  # o HDBSCAN numera de outro jeito
    corpus2 = (corpus - {d for n in nucleos for d in n if rng.random() < 0.05}) | set().union(*novos)
    r2 = estabilizar([novos[i] for i in ordem], [GRUPOS[i] for i in ordem], r.identidade, CHAVE, corpus2)
    assert r2.ids == [r.ids[i] for i in ordem] and r2.cores == [r.cores[i] for i in ordem]
    assert r2.macros == [r.macros[i] for i in ordem] and r2.cores_macro == r.cores_macro


def test_ids_aposentados_nao_voltam_e_chave_nova_nao_casa():
    nucleos, corpus, r = _primeira()
    # o tópico de id 5 (o menor) some; aparece um assunto novo
    sem = [n for i, n in enumerate(nucleos) if r.ids[i] != 5] + [{f"x{k}" for k in range(35)}]
    grupos = [g for i, g in enumerate(GRUPOS) if r.ids[i] != 5] + [2]
    r2 = estabilizar(sem, grupos, r.identidade, CHAVE, corpus | sem[-1])
    assert 5 not in r2.ids and r2.ids[-1] == 6 and r2.identidade.proximo_id == 7
    # outro modelo de embeddings: nada casa, e a numeração continua de onde parou
    r3 = estabilizar(nucleos, GRUPOS, r2.identidade, {**CHAVE, "modelo": "bge-m3@def"}, corpus)
    assert sorted(r3.ids) == list(range(7, 13)) and not r3.casados


def test_topico_que_muda_de_macrotema_muda_de_cor():
    nucleos, corpus, r = _primeira()
    grupos = list(GRUPOS)
    grupos[0] = 0  # o tópico 0 (id 3) passa do macrotema do grupo 1 para o do grupo 0
    r2 = estabilizar(nucleos, grupos, r.identidade, CHAVE, corpus, persistir_macrotemas=False)
    assert r2.ids == r.ids and r2.macros[0] == r.macros[1] and r2.cores[0] != r.cores[0]
    assert r2.cores[1:] == r.cores[1:]
    assert len(r2.casados) == 6 and r2.mesma_cor == 5


def test_macrotemas_persistem_e_topico_novo_vai_para_o_do_casado_mais_parecido():
    nucleos, corpus, r = _primeira()
    novo = {f"n{i:03d}" for i in range(35)}
    centros = np.eye(7)
    centros[6] = centros[4] * 0.9 + centros[0] * 0.1  # o tópico novo parece o tópico 4 (macrotema do grupo 2)
    centros /= np.linalg.norm(centros, axis=1, keepdims=True)
    embaralhados = [0, 0, 0, 1, 1, 1, 2]  # a aglomeração desta vez mudaria os macrotemas de quase todos
    r2 = estabilizar([*nucleos, novo], embaralhados, r.identidade, CHAVE, corpus | novo, centros=centros)
    assert r2.macrotemas_persistentes and r2.macros[:6] == r.macros and r2.macros[6] == r.macros[4]
    assert r2.cores[:6] == r.cores and r2.mesma_cor == 6 and r2.cores[6] not in r.cores
    r3 = estabilizar(nucleos, embaralhados[:6], r.identidade, CHAVE, corpus, persistir_macrotemas=False)
    assert not r3.macrotemas_persistentes and r3.mesma_cor < 6


def test_recem_chegado_grande_nao_toma_a_cor_de_quem_ficou():
    nucleos, corpus, r = _primeira()
    grupos = list(GRUPOS)
    grupos[1] = 1  # o maior tópico (90 documentos) vai para o macrotema dos tópicos 0 e 2, que ficam
    r2 = estabilizar(nucleos, grupos, r.identidade, CHAVE, corpus, persistir_macrotemas=False)
    assert r2.cores[0] == r.cores[0] and r2.cores[2] == r.cores[2]
    assert r2.cores[1] not in (r.cores[0], r.cores[2], r.cores[1])


def test_macrotemas_por_ward_e_ordem_pelo_tamanho():
    rng = np.random.default_rng(0)
    base = rng.normal(size=(3, 16))
    centros = np.vstack([base[g] + 0.05 * rng.normal(size=16) for g in (0, 0, 0, 1, 1, 1, 2, 2, 2)])
    centros /= np.linalg.norm(centros, axis=1, keepdims=True)
    grupos = agrupar_macrotemas(centros, [10, 10, 10, 50, 50, 50, 20, 20, 20], 7)
    assert grupos == [2, 2, 2, 0, 0, 0, 1, 1, 1]  # 9 tópicos → 3 grupos; o grupo 0 é o de mais documentos
    assert agrupar_macrotemas(centros[:2], [5, 9], 7) == [1, 0] and agrupar_macrotemas(centros[:0], [], 7) == []


def test_numero_de_macrotemas_acompanha_os_topicos():
    assert [numero_de_macrotemas(k, 7) for k in (1, 2, 5, 9, 13, 21, 50)] == [1, 2, 2, 3, 4, 7, 7]
    assert numero_de_macrotemas(50, 3) == 3
