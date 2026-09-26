"""A etapa de tópicos de ponta a ponta (`mapa topicos`).

embeddings → vizinhança → UMAP 5D (3 sementes) e 2D → HDBSCAN → reatribuição do ruído → palavras-chave e
representativos → macrotemas → identidade estável → rótulos → `dados/topicos/` → manifesto da etapa.

Cada passo pesado tem cache (embeddings, reduções, rótulos): rodar de novo sem mudanças leva segundos. Ver
"Como os tópicos são construídos" na documentação e o ADR 0007.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from mapa_da_ciencia.armazenamento import ARQUIVO, ler_documentos
from mapa_da_ciencia.config import ErroConfig
from mapa_da_ciencia.contrato.exportar import exportar
from mapa_da_ciencia.embeddings import VERSAO_TEXTO, calcular_embeddings
from mapa_da_ciencia.formatar import num
from mapa_da_ciencia.llm.base import ErroProvedor
from mapa_da_ciencia.llm.ollama import Ollama
from mapa_da_ciencia.manifesto import registrar_execucao
from mapa_da_ciencia.progresso import Progresso, ProgressoNulo
from mapa_da_ciencia.projeto import Projeto
from mapa_da_ciencia.topicos.resultado import PASTA, MacroResultado, Resultado, TopicoResultado, assinatura_corpus
from mapa_da_ciencia.topicos.rotulos import (
    EntradaTopico,
    ResumoRotulos,
    Rotulador,
    Rotulo,
    ler_manuais,
    palavras_do_macrotema,
)

if TYPE_CHECKING:
    import numpy as np

VIZINHOS_EXPORTADOS = 5  # o contrato pede os 5 mais próximos de cada documento


@dataclass
class OpcoesTopicos:
    sem_rotulos: bool = False
    refazer_embeddings: bool = False
    semente: int | None = None  # substitui a primeira de `topicos.sementes`


@dataclass
class ResumoTopicos:
    """O que a etapa de tópicos fez. `print(resumo)` mostra os números principais numa frase.

    `nucleo`, `reatribuidos` e `sem_topico` somam `documentos`; `casados` conta os tópicos que mantiveram o número
    da execução anterior e `mesma_cor`, os que mantiveram também a cor (não mudaram de macrotema); `rotulos` diz
    quantos rótulos vieram do modelo, do cache ou do `rotulos.yaml`.
    """

    documentos: int
    topicos: int
    macrotemas: int
    nucleo: int
    reatribuidos: int
    sem_topico: int
    estabilidade_ari: float | None
    casados: int
    mesma_cor: int
    embeddings_novos: int
    rotulos: ResumoRotulos
    duracao_s: float
    avisos: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        ari = f"ARI {num(self.estabilidade_ari, 2)}" if self.estabilidade_ari is not None else "sem ARI"
        return (
            f"{num(self.topicos, 0)} tópicos em {num(self.macrotemas, 0)} macrotemas, {num(self.documentos, 0)} "
            f"documentos: {num(self.nucleo, 0)} no núcleo, {num(self.reatribuidos, 0)} reatribuídos, "
            f"{num(self.sem_topico, 0)} sem tópico ({ari}), em {num(self.duracao_s, 0)} s."
        )


def _medoide(pontos: np.ndarray) -> tuple[float, float]:
    """O ponto do grupo com a menor soma de distâncias aos outros: fica dentro do grupo, mesmo curvo."""
    import numpy as np

    dist = np.sqrt(((pontos[:, None, :] - pontos[None, :, :]) ** 2).sum(axis=-1))
    x, y = pontos[int(np.argmin(dist.sum(axis=1)))]
    return round(float(x), 5), round(float(y), 5)


def gerar_topicos(
    projeto: Projeto,
    opcoes: OpcoesTopicos | None = None,
    progresso: Progresso | None = None,
    *,
    ollama: Ollama | None = None,
) -> ResumoTopicos:
    import numpy as np

    from mapa_da_ciencia.topicos.agrupamento import (
        agrupar,
        conferir_tamanho,
        estabilidade,
        min_cluster_size_automatico,
        reatribuir,
    )
    from mapa_da_ciencia.topicos.ctfidf import palavras_chave, representativos, texto_de_exibicao
    from mapa_da_ciencia.topicos.identidade import Identidade, estabilizar
    from mapa_da_ciencia.topicos.macrotemas import agrupar_macrotemas, centros
    from mapa_da_ciencia.topicos.reducao import assinatura_dados, reduzir
    from mapa_da_ciencia.topicos.vizinhos import knn_exato

    opcoes = opcoes or OpcoesTopicos()
    progresso = progresso or ProgressoNulo()
    ollama = ollama or Ollama()
    cfg, ct = projeto.config, projeto.config.topicos
    inicio, t0 = datetime.now(UTC), time.perf_counter()
    avisos: list[str] = []

    e = calcular_embeddings(projeto, refazer=opcoes.refazer_embeddings, ollama=ollama, progresso=progresso)
    avisos += e.avisos
    n = len(e.ids)
    conferir_tamanho(n)
    docs = {d.id: d for d in ler_documentos(projeto.dados / ARQUIVO)}

    # ---- vizinhança, reduções e agrupamento (com a semente principal e as de estabilidade)
    progresso.etapa("Agrupamento", 4)
    k = min(ct.vizinhos, n - 1)
    knn = knn_exato(e.matriz, max(k, VIZINHOS_EXPORTADOS) + 1)
    knn_umap = (knn[0][:, :k], knn[1][:, :k])
    sementes = list(dict.fromkeys([opcoes.semente if opcoes.semente is not None else ct.sementes[0], *ct.sementes]))
    pasta = projeto.dados / PASTA
    base = assinatura_dados(e.ids, e.matriz, e.rotulo_modelo)
    reduzir_com = {"n_vizinhos": k, "cache": pasta / "reducoes", "base": base}
    reducoes = [
        reduzir(e.matriz, knn_umap, n_componentes=5, min_dist=ct.min_dist, semente=s, **reduzir_com) for s in sementes
    ]
    progresso.avancar()
    mapa2d = reduzir(e.matriz, knn_umap, n_componentes=2, min_dist=ct.min_dist_mapa, semente=sementes[0], **reduzir_com)
    progresso.avancar()
    mcs = ct.min_cluster_size or min_cluster_size_automatico(n)
    grupos = [agrupar(r, min_cluster_size=mcs, min_samples=ct.min_samples, selecao=ct.selecao) for r in reducoes]
    brutos = grupos[0].rotulos
    if brutos.max() < 0:
        raise ErroConfig(
            f"O agrupamento não encontrou nenhum tópico em {n} documentos. Diminua `topicos.min_cluster_size` "
            "(ou `topicos.min_samples`) no mapa.yaml, ou amplie o recorte."
        )
    ari = estabilidade([g.rotulos for g in grupos]) if len(grupos) > 1 else None
    finais_brutos = reatribuir(brutos, *knn_umap, votos_minimos=ct.votos_minimos)
    progresso.avancar()

    # ---- descrição dos tópicos: palavras-chave, representativos, macrotemas e identidade estável
    k_brutos = int(brutos.max()) + 1
    nucleos = [{e.ids[i] for i in np.flatnonzero(brutos == t)} for t in range(k_brutos)]
    tamanhos = [len(nc) for nc in nucleos]
    idiomas = (cfg.recorte.idioma_exibicao, cfg.recorte.idioma_analise)
    palavras = palavras_chave([texto_de_exibicao(docs[i], *idiomas) for i in e.ids], brutos)
    reps = representativos(e.matriz, brutos, e.ids)
    grupos_macro = agrupar_macrotemas(centros(e.matriz, brutos, list(range(k_brutos))), tamanhos, ct.macrotemas)
    chave = {"modelo": e.rotulo_modelo, "idioma_analise": cfg.recorte.idioma_analise, "versao_texto": VERSAO_TEXTO}
    anterior = Identidade.ler(pasta)
    est = estabilizar(nucleos, grupos_macro, anterior, chave, set(e.ids))
    progresso.avancar()
    progresso.fim()

    # ---- rótulos
    def titulo(doc_id: str) -> str:
        t = docs[doc_id].texto_em("titulos", list(idiomas))
        return t.texto if t else ""

    entradas: dict[int, EntradaTopico] = {}
    for b in range(k_brutos):
        tid = est.ids[b]
        velho = anterior.topicos.get(est.casados[b]) if anterior and b in est.casados else None
        rotulo_velho = (
            Rotulo(velho.rotulo, velho.descricao or "", velho.rotulo_fonte) if velho and velho.rotulo else None
        )
        entradas[tid] = EntradaTopico(
            [t for t, _ in palavras[b]], [titulo(i) for i in reps[b]], rotulo_velho, velho.palavras if velho else []
        )
    por_macro: dict[int, list[int]] = {}
    for b in sorted(range(k_brutos), key=lambda b: -tamanhos[b]):
        por_macro.setdefault(est.macros[b], []).append(est.ids[b])
    tamanho_de = {est.ids[b]: tamanhos[b] for b in range(k_brutos)}
    palavras_de = {est.ids[b]: palavras[b] for b in range(k_brutos)}
    manuais = ler_manuais(projeto.raiz)
    rotulador = Rotulador(cfg.modelos.rotulos, projeto.estado, ollama=ollama, progresso=progresso)
    try:
        rotulos = rotulador.topicos(entradas, sem_llm=opcoes.sem_rotulos, manuais=manuais)
        palavras_macro = {m: palavras_do_macrotema(ts, palavras_de, tamanho_de) for m, ts in por_macro.items()}
        rotulos_macro = rotulador.macrotemas(
            por_macro, rotulos, palavras_macro, sem_llm=opcoes.sem_rotulos, manuais=manuais
        )
    except ErroProvedor as erro:
        raise ErroProvedor(f"{erro} Para seguir sem o modelo de linguagem, use `mapa topicos --sem-rotulos`.") from erro
    finally:
        rotulador.fim()
        progresso.fim()

    # ---- identidade (com os rótulos) e resultado
    for tid, r in rotulos.items():
        t = est.identidade.topicos[tid]
        t.rotulo, t.descricao, t.rotulo_fonte, t.palavras = r.rotulo, r.descricao, r.fonte, entradas[tid].palavras
    for m, r in rotulos_macro.items():
        mt = est.identidade.macrotemas[m]
        mt.rotulo, mt.descricao, mt.rotulo_fonte = r.rotulo, r.descricao, r.fonte
    est.identidade.gravar(pasta)

    estavel = {b: est.ids[b] for b in range(k_brutos)}
    topico_final = [estavel[int(t)] if t >= 0 else -1 for t in finais_brutos]
    fonte_por_id = {t.id: t for t in e.textos}
    atribuicoes = [
        {
            "id": doc_id,
            "topico": topico_final[i],
            "atribuicao": "cluster" if brutos[i] >= 0 else "vizinho",
            "x": float(mapa2d[i, 0]),
            "y": float(mapa2d[i, 1]),
            "vizinhos": [e.ids[j] for j in knn[0][i, 1 : VIZINHOS_EXPORTADOS + 1]],
            "idioma_analise": fonte_por_id[doc_id].idioma,
            "fonte_analise": fonte_por_id[doc_id].fonte,
        }
        for i, doc_id in enumerate(e.ids)
    ]
    topicos_res = [
        TopicoResultado(
            id=est.ids[b],
            macro=est.macros[b],
            rotulo=rotulos[est.ids[b]].rotulo,
            descricao=rotulos[est.ids[b]].descricao,
            rotulo_fonte=rotulos[est.ids[b]].fonte,
            cor=est.cores[b],
            palavras=palavras[b],
            representativos=reps[b],
            n_nucleo=tamanhos[b],
            centroide=_medoide(mapa2d[brutos == b]),
        )
        for b in sorted(range(k_brutos), key=lambda b: est.ids[b])
    ]
    macros_res = [
        MacroResultado(
            m, rotulos_macro[m].rotulo, rotulos_macro[m].descricao, rotulos_macro[m].fonte, cor, por_macro[m]
        )
        for m, cor in sorted(est.cores_macro.items())
    ]
    modelos = {"embeddings": e.rotulo_modelo}
    if not opcoes.sem_rotulos and rotulador.resumo.chamadas + rotulador.resumo.do_cache:
        modelos["rotulos"] = rotulador.resumo.modelo
    parametros = {
        "vizinhos": k,
        "min_dist": ct.min_dist,
        "min_dist_mapa": ct.min_dist_mapa,
        "min_cluster_size": mcs,
        "min_samples": ct.min_samples,
        "selecao": ct.selecao,
        "votos_minimos": ct.votos_minimos,
        "macrotemas": ct.macrotemas,
        "semente": sementes[0],
        "sementes_estabilidade": ",".join(map(str, sementes)),
        "idioma_analise": cfg.recorte.idioma_analise,
        "idioma_exibicao": cfg.recorte.idioma_exibicao,
    }
    ruido = int((brutos == -1).sum())
    reatribuidos = int(((brutos == -1) & (finais_brutos >= 0)).sum())
    Resultado(
        assinatura=assinatura_corpus(list(docs)),
        gerado_em=datetime.now(UTC).isoformat(),
        parametros=parametros,
        estabilidade_ari=ari,
        ruido=ruido,
        reatribuidos=reatribuidos,
        modelos=modelos,
        topicos=topicos_res,
        macrotemas=macros_res,
    ).gravar(pasta, atribuicoes)

    resumo = ResumoTopicos(
        documentos=n,
        topicos=k_brutos,
        macrotemas=len(macros_res),
        nucleo=n - ruido,
        reatribuidos=reatribuidos,
        sem_topico=ruido - reatribuidos,
        estabilidade_ari=ari,
        casados=len(est.casados),
        mesma_cor=est.mesma_cor,
        embeddings_novos=e.novos,
        rotulos=rotulador.resumo,
        duracao_s=round(time.perf_counter() - t0, 2),
        avisos=avisos,
    )
    registrar_execucao(
        projeto,
        "topicos",
        inicio=inicio,
        fim=datetime.now(UTC),
        contagens={
            "topicos": resumo.topicos,
            "macrotemas": resumo.macrotemas,
            "documentos": n,
            "nucleo": resumo.nucleo,
            "reatribuidos": reatribuidos,
            "sem_topico": resumo.sem_topico,
            "casados": resumo.casados,
            "rotulos_llm": rotulador.resumo.chamadas,
        },
        modelos=modelos,
        parametros={**parametros, "estabilidade_ari": ari},
    )
    resumo.avisos += exportar(projeto)  # o painel passa a mostrar o mapa
    return resumo
