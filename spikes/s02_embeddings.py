# /// script
# requires-python = "==3.12.*"
# dependencies = ["httpx>=0.28", "numpy>=2", "scikit-learn>=1.6", "umap-learn>=0.5.7"]
# ///
"""Spike M0a: qual modelo de embeddings e qual política de idioma usar nos tópicos.

Perguntas:
- O modelo alinha o mesmo resumo em pt e en (recuperação cruzada)?
- Num corpus com resumos em idiomas misturados, os vizinhos e os clusters se
  organizam por idioma em vez de por assunto (homofilia de idioma, AMI)?
- A estrutura de tópicos muda muito se usarmos só pt ou só en (ARI pt × en)?
- Quanto tempo leva para embutir o corpus?

Pré-requisitos: `spikes/saida/corpus.jsonl` (gerado por s01_fontes.py) e o
Ollama rodando com `qwen3-embedding:0.6b` e `bge-m3` baixados.

Uso:
    uv run spikes/s02_embeddings.py
    uv run spikes/s02_embeddings.py --modelos bge-m3 --limite 500
"""

from __future__ import annotations

import argparse
import collections
import json
import time
from pathlib import Path

import httpx
import numpy as np
from sklearn.cluster import HDBSCAN
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics import adjusted_mutual_info_score, adjusted_rand_score
from sklearn.neighbors import NearestNeighbors

SAIDA = Path(__file__).resolve().parent / "saida"
OLLAMA = "http://localhost:11434"
TIPOS = {"research-article", "review-article"}
SEMENTE = 42

STOP_PT = set(
    """a à ao aos as às até com como da das de dela dele deles demais do dos e é ela elas ele eles em
entre era essa essas esse esses esta está estas este estes eu foi foram há isso isto já la lhe mais mas me
mesmo meu minha muito na nas nem no nos nós num numa o os ou para pela pelas pelo pelos por qual quando que
quem se sem ser seu seus sua suas só também te tem têm ter um uma umas uns vez são sobre entre partir
através bem assim ainda cada onde após neste nesta nesse nessa desse dessa deste desta artigo trabalho
estudo análise analisa busca discute objetivo presente texto resultados pesquisa ser forma modo caso
aqui além apenas tanto outro outra outros outras sendo sido pode podem seja sejam""".split()
)
STOP_EN = set(
    """a an and are as at be been but by for from has have in into is it its of on or that the their
this to was were which with we our paper article study analysis this these those than then also between
based results research using used can may how what whether""".split()
)


def carregar_corpus(limite: int | None) -> list[dict]:
    docs = []
    with open(SAIDA / "corpus.jsonl", encoding="utf-8") as f:
        for linha in f:
            d = json.loads(linha)
            if d["tipo"] in TIPOS and "pt" in d["resumos"] and "en" in d["resumos"]:
                docs.append(d)
    rng = np.random.default_rng(SEMENTE)
    if limite and limite < len(docs):
        docs = [docs[i] for i in sorted(rng.choice(len(docs), limite, replace=False))]
    return docs


def texto(d: dict, lang: str) -> str:
    titulo = d["titulos"].get(lang) or next(iter(d["titulos"].values()), "")
    return f"{titulo}. {d['resumos'][lang]}"


def idioma_original(d: dict) -> str:
    lang = d.get("idioma_openalex")
    return lang if lang in d["resumos"] else "pt"


def embutir(cli: httpx.Client, modelo: str, textos: list[str], lote: int = 32) -> tuple[np.ndarray, float]:
    vetores, t0 = [], time.perf_counter()
    for i in range(0, len(textos), lote):
        r = cli.post(
            f"{OLLAMA}/api/embed",
            json={
                "model": modelo,
                "input": textos[i : i + lote],
                "truncate": True,
                "keep_alive": "10m",
            },
        )
        r.raise_for_status()
        vetores += r.json()["embeddings"]
    m = np.asarray(vetores, dtype=np.float32)
    m /= np.linalg.norm(m, axis=1, keepdims=True)
    return m, time.perf_counter() - t0


def embeddings_em_cache(cli, modelo: str, docs: list[dict], lang: str) -> tuple[np.ndarray, float | None]:
    nome = modelo.replace(":", "_").replace("/", "_")
    arq = SAIDA / "emb" / f"{nome}_{lang}_{len(docs)}.npy"
    if arq.exists():
        return np.load(arq), None
    m, seg = embutir(cli, modelo, [texto(d, lang) for d in docs])
    arq.parent.mkdir(parents=True, exist_ok=True)
    np.save(arq, m)
    return m, seg


def agrupar(m: np.ndarray) -> np.ndarray:
    import umap  # importação lenta (numba); só quando necessário

    red = umap.UMAP(n_components=5, n_neighbors=15, min_dist=0.0, metric="cosine", random_state=SEMENTE).fit_transform(m)
    return HDBSCAN(min_cluster_size=max(10, len(m) // 200), min_samples=5, copy=True).fit_predict(red)


def homofilia_idioma(m: np.ndarray, idiomas: list[str], k: int = 10) -> float:
    """Fração média de vizinhos com o mesmo idioma, menos o esperado ao acaso."""
    viz = NearestNeighbors(n_neighbors=k + 1, metric="cosine").fit(m).kneighbors(m, return_distance=False)[:, 1:]
    idiomas = np.asarray(idiomas)
    observado = (idiomas[viz] == idiomas[:, None]).mean()
    freq = collections.Counter(idiomas)
    esperado = sum((c / len(idiomas)) ** 2 for c in freq.values())
    return float(observado - esperado)


def palavras_chave(textos: list[str], rotulos: np.ndarray, n: int = 15) -> dict[int, list[str]]:
    """c-TF-IDF simples: termos distintivos de cada cluster."""
    grupos = sorted(set(rotulos) - {-1})
    docs_cluster = [" ".join(t for t, r in zip(textos, rotulos, strict=True) if r == g) for g in grupos]
    cv = CountVectorizer(
        ngram_range=(1, 2), stop_words=sorted(STOP_PT | STOP_EN), min_df=2, token_pattern=r"(?u)\b[^\W\d_]{3,}\b"
    )
    x = cv.fit_transform(docs_cluster).toarray().astype(float)
    tf = x / x.sum(axis=1, keepdims=True)
    idf = np.log(1 + x.sum(axis=1).mean() / x.sum(axis=0))
    termos = cv.get_feature_names_out()
    return {g: [termos[j] for j in np.argsort(-(tf[i] * idf))[:n]] for i, g in enumerate(grupos)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelos", nargs="*", default=["qwen3-embedding:0.6b", "bge-m3"])
    ap.add_argument("--limite", type=int, default=None, help="amostra de N documentos (padrão: todos)")
    args = ap.parse_args()

    docs = carregar_corpus(args.limite)
    originais = [idioma_original(d) for d in docs]
    print(f"{len(docs)} documentos com resumo em pt e en; idioma original: {dict(collections.Counter(originais))}")

    resultados = {}
    with httpx.Client(timeout=600) as cli:
        for modelo in args.modelos:
            print(f"\n== {modelo}")
            emb, tempos = {}, {}
            for lang in ("pt", "en"):
                emb[lang], tempos[lang] = embeddings_em_cache(cli, modelo, docs, lang)
                if tempos[lang]:
                    print(f"   {lang}: {len(docs)} textos em {tempos[lang]:.1f}s ({len(docs) / tempos[lang]:.0f}/s)")
            # recuperação cruzada: o vizinho en mais próximo do texto pt é o mesmo artigo?
            sim = emb["pt"] @ emb["en"].T
            top1 = float((sim.argmax(axis=1) == np.arange(len(docs))).mean())
            posto = (sim > sim[np.arange(len(docs)), np.arange(len(docs))][:, None]).sum(axis=1) + 1
            mrr = float((1 / posto).mean())
            # corpus misto: cada artigo no seu idioma original (en fica en; pt, es e outros ficam pt)
            idiomas_misto = ["en" if o == "en" else "pt" for o in originais]
            misto = np.where(np.asarray(idiomas_misto)[:, None] == "en", emb["en"], emb["pt"])
            hom_misto = homofilia_idioma(misto, idiomas_misto)
            print(f"   recuperação pt→en: top-1 {top1:.3f}, MRR {mrr:.3f}; homofilia de idioma no misto: {hom_misto:+.3f}")

            rot = {nome: agrupar(m) for nome, m in (("pt", emb["pt"]), ("en", emb["en"]), ("misto", misto))}
            validos = (rot["pt"] != -1) & (rot["en"] != -1)
            ari_pt_en = float(adjusted_rand_score(rot["pt"][validos], rot["en"][validos]))
            nao_ruido = rot["misto"] != -1
            ami_idioma = float(adjusted_mutual_info_score(np.asarray(idiomas_misto)[nao_ruido], rot["misto"][nao_ruido]))
            resumo_clusters = {
                nome: {"n_clusters": int(len(set(r)) - (-1 in r)), "ruido": float((r == -1).mean())} for nome, r in rot.items()
            }
            print(f"   ARI pt×en: {ari_pt_en:.3f}; AMI(cluster, idioma) no misto: {ami_idioma:.3f}; clusters: {resumo_clusters}")

            # material para o teste de rótulos do spike M0b: clusters da condição pt
            textos_pt = [texto(d, "pt") for d in docs]
            chaves = palavras_chave(textos_pt, rot["pt"])
            maiores = [g for g, _ in collections.Counter(r for r in rot["pt"] if r != -1).most_common(8)]
            topicos = []
            for g in maiores:
                idx = np.where(rot["pt"] == g)[0]
                centro = emb["pt"][idx].mean(axis=0)
                repr_ = idx[np.argsort(-(emb["pt"][idx] @ centro))[:5]]
                topicos.append(
                    {
                        "cluster": int(g),
                        "n": int(len(idx)),
                        "palavras_chave": chaves[g],
                        "representativos": [docs[i]["titulos"].get("pt") or texto(docs[i], "pt")[:150] for i in repr_],
                    }
                )
            nome = modelo.replace(":", "_")
            (SAIDA / f"s02_topicos_{nome}.json").write_text(json.dumps(topicos, ensure_ascii=False, indent=2))

            resultados[modelo] = {
                "n_docs": len(docs),
                "segundos": tempos,
                "recuperacao_top1": top1,
                "recuperacao_mrr": mrr,
                "homofilia_idioma_misto": hom_misto,
                "ari_pt_en": ari_pt_en,
                "ami_idioma_misto": ami_idioma,
                "clusters": resumo_clusters,
            }

    (SAIDA / "s02_embeddings.json").write_text(json.dumps(resultados, ensure_ascii=False, indent=2))
    print(
        "\n| Modelo | top-1 pt→en | MRR | homofilia idioma (misto) | AMI cluster×idioma (misto) "
        "| ARI pt×en | clusters pt / en / misto | ruído pt |"
    )
    print("|---|---|---|---|---|---|---|---|")
    for m, r in resultados.items():
        c = r["clusters"]
        print(
            f"| {m} | {r['recuperacao_top1']:.3f} | {r['recuperacao_mrr']:.3f} | {r['homofilia_idioma_misto']:+.3f} "
            f"| {r['ami_idioma_misto']:.3f} | {r['ari_pt_en']:.3f} | {c['pt']['n_clusters']} / {c['en']['n_clusters']} / "
            f"{c['misto']['n_clusters']} | {c['pt']['ruido']:.0%} |"
        )


if __name__ == "__main__":
    main()
