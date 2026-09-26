# /// script
# requires-python = "==3.12.*"
# dependencies = ["httpx>=0.28", "pyyaml>=6", "numpy>=2", "scikit-learn>=1.6", "psutil>=6"]
# ///
"""Spike M0b: qual modelo local classifica os resumos, e com quais parâmetros.

Para cada configuração (modelo × pensar × concorrência), classifica os mesmos
resumos com o codebook de exemplo via saída estruturada do Ollama e mede:
- JSON válido segundo o esquema;
- evidência literal / aproximada / ausente no resumo;
- segundos por resumo, tokens e velocidade; parte do modelo na GPU (/api/ps);
- concordância entre configurações (% e kappa de Cohen).
Também pede rótulos de tópico ao modelo, a partir de s02_topicos_*.json.

Antes de carregar cada modelo, confere se ele cabe na memória livre e aborta
com uma mensagem clara se não couber (no M0, o gemma4:26b de 17 GB esgotou o
swap da máquina de 24 GB enquanto outros programas rodavam).

Pré-requisitos: spikes/saida/corpus.jsonl (s01) e, para rótulos, s02_topicos_*.json (s02).

Uso:
    uv run spikes/s03_llm.py                                  # configurações padrão (qwen3.5:9b)
    uv run spikes/s03_llm.py --configs qwen-c1                # só uma
    uv run spikes/s03_llm.py --rotulos-com gemma4:26b         # rótulos também com outro modelo
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import difflib
import json
import re
import statistics
import time
import unicodedata
from pathlib import Path

import httpx
import numpy as np
import psutil
import yaml
from sklearn.metrics import cohen_kappa_score

AQUI = Path(__file__).resolve().parent
SAIDA = AQUI / "saida"
OUT = SAIDA / "s03_llm"
OLLAMA = "http://localhost:11434"
SEMENTE = 7

CONFIGS = {
    # nome: (modelo, pensar, concorrência, n_docs)
    "qwen-c1": ("qwen3.5:9b", False, 1, 50),
    "qwen-c4": ("qwen3.5:9b", False, 4, 50),
    "qwen-pensar": ("qwen3.5:9b", True, 1, 15),
    # gemma4:26b (17 GB) saiu da classificação por falta de memória; ver ADR 0005
    "gemma-c1": ("gemma4:26b", False, 1, 50),
}
PADRAO = ["qwen-c1", "qwen-c4", "qwen-pensar"]
MARGEM_GB = 1.5


async def garantir_memoria(cli, modelo: str) -> None:
    """Aborta se o modelo (mais uma margem) não couber na memória disponível agora."""
    carregados = (await cli.get(f"{OLLAMA}/api/ps")).json().get("models", [])
    if any(m["name"] in (modelo, f"{modelo}:latest") for m in carregados):
        return  # já está na memória: carregar de novo não custa nada
    tags = (await cli.get(f"{OLLAMA}/api/tags")).json().get("models", [])
    tamanho = next((m["size"] for m in tags if m["name"] == modelo or m["name"] == f"{modelo}:latest"), None)
    if tamanho is None:
        raise SystemExit(f"Modelo {modelo} não está instalado no Ollama. Rode: ollama pull {modelo}")
    disponivel = psutil.virtual_memory().available
    precisa = tamanho + MARGEM_GB * 1e9
    if disponivel < precisa:
        raise SystemExit(
            f"Memória insuficiente para {modelo}: precisa de ~{precisa / 1e9:.1f} GB e há {disponivel / 1e9:.1f} GB "
            "disponíveis. Feche programas pesados ou use um modelo menor."
        )


# ---------------------------------------------------------------- codebook → esquema e prompt
def esquema(cb: dict) -> dict:
    props = {}
    for v in cb["variaveis"]:
        if v["tipo"] == "categorica":
            valor = {"type": "string", "enum": [c["valor"] for c in v["categorias"]]}
        elif v["tipo"] == "booleana":
            valor = {"type": "boolean"}
        else:
            valor = {"type": "string"}
        props[v["id"]] = {  # evidência ANTES do valor: o modelo ancora a resposta no texto
            "type": "object",
            "properties": {"evidencia": {"type": "string"}, "valor": valor},
            "required": ["evidencia", "valor"],
            "additionalProperties": False,
        }
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


def prompt_sistema(cb: dict) -> str:
    linhas = [cb["instrucoes"].strip(), "", "## Codebook", ""]
    for v in cb["variaveis"]:
        linhas.append(f"### {v['id']} ({v['tipo']})\n{v['pergunta']}")
        for c in v.get("categorias", []):
            linhas.append(f"- `{c['valor']}`: {c['definicao']}")
        linhas.append("")
    return "\n".join(linhas)


def validar(resp: dict, cb: dict) -> bool:
    for v in cb["variaveis"]:
        item = resp.get(v["id"])
        if not isinstance(item, dict) or set(item) != {"evidencia", "valor"}:
            return False
        if v["tipo"] == "categorica" and item["valor"] not in {c["valor"] for c in v["categorias"]}:
            return False
        if v["tipo"] == "booleana" and not isinstance(item["valor"], bool):
            return False
    return set(resp) == {v["id"] for v in cb["variaveis"]}


# ---------------------------------------------------------------- evidência
def normalizar(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).lower()
    s = s.translate(str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'", "–": "-", "—": "-"}))
    return re.sub(r"\s+", " ", s).strip(" .,;:\"'")


def status_evidencia(evidencia: str, resumo: str) -> str:
    e, r = normalizar(evidencia), normalizar(resumo)
    if len(e) < 3:
        return "ausente"
    if e in r:
        return "literal"
    casados = sum(b.size for b in difflib.SequenceMatcher(None, r, e, autojunk=False).get_matching_blocks())
    return "aproximada" if casados / len(e) >= 0.9 else "ausente"


# ---------------------------------------------------------------- amostra
def amostra(n: int) -> list[dict]:
    por_revista = collections.defaultdict(list)
    with open(SAIDA / "corpus.jsonl", encoding="utf-8") as f:
        for linha in f:
            d = json.loads(linha)
            if d["tipo"] == "research-article" and "pt" in d["resumos"] and len(d["resumos"]["pt"]) > 300:
                por_revista[d["revista"]].append(d)
    rng = np.random.default_rng(SEMENTE)
    escolhidos = []
    for rev in sorted(por_revista):  # estratificada: mesma quantidade por revista
        docs = por_revista[rev]
        k = min(len(docs), -(-n // len(por_revista)))
        escolhidos += [docs[i] for i in rng.choice(len(docs), k, replace=False)]
    rng.shuffle(escolhidos)
    return escolhidos[:n]


def texto_do_doc(d: dict) -> str:
    return f"Título: {d['titulos'].get('pt') or next(iter(d['titulos'].values()), '')}\n\nResumo: {d['resumos']['pt']}"


# ---------------------------------------------------------------- Ollama
async def chat(cli, modelo, sistema, usuario, formato, pensar) -> dict:
    corpo = {
        "model": modelo,
        "stream": False,
        "think": pensar,
        "keep_alive": "30m",
        "format": formato,
        "options": {"num_ctx": 8192, "temperature": 0, "seed": SEMENTE},
        "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
    }
    t0 = time.perf_counter()
    r = await cli.post(f"{OLLAMA}/api/chat", json=corpo)
    r.raise_for_status()
    j = r.json()
    j["_parede_s"] = time.perf_counter() - t0
    return j


async def uso_gpu(cli, modelo) -> dict:
    r = await cli.get(f"{OLLAMA}/api/ps")
    for m in r.json().get("models", []):
        if m["name"].startswith(modelo):
            return {"tamanho_gb": m["size"] / 1e9, "na_gpu_gb": m["size_vram"] / 1e9, "fracao_gpu": m["size_vram"] / m["size"]}
    return {}


async def descarregar(cli, modelo) -> None:
    await cli.post(f"{OLLAMA}/api/generate", json={"model": modelo, "keep_alive": 0})


async def rodar_config(cli, nome, cb, docs) -> dict:
    modelo, pensar, conc, n = CONFIGS[nome]
    docs = docs[:n]
    sistema, formato = prompt_sistema(cb), esquema(cb)
    await garantir_memoria(cli, modelo)
    await chat(cli, modelo, sistema, "Título: aquecimento\n\nResumo: texto curto.", formato, pensar)  # carrega o modelo
    gpu = await uso_gpu(cli, modelo)
    sem = asyncio.Semaphore(conc)

    async def um(d):
        async with sem:
            j = await chat(cli, modelo, sistema, texto_do_doc(d), formato, pensar)
        try:
            resp = json.loads(j["message"]["content"])
            valido = validar(resp, cb)
        except json.JSONDecodeError:
            resp, valido = None, False
        evid = {}
        if valido:
            for v in cb["variaveis"]:
                evid[v["id"]] = status_evidencia(resp[v["id"]]["evidencia"], texto_do_doc(d))
        return {
            "pid": d["pid"],
            "revista": d["revista"],
            "valido": valido,
            "resposta": resp,
            "evidencia": evid,
            "parede_s": j["_parede_s"],
            "tokens_saida": j.get("eval_count"),
            "tokens_prompt": j.get("prompt_eval_count"),
            "decode_s": (j.get("eval_duration") or 0) / 1e9,
            "prefill_s": (j.get("prompt_eval_duration") or 0) / 1e9,
            "pensamento_chars": len(j["message"].get("thinking") or ""),
        }

    t0 = time.perf_counter()
    resultados = await asyncio.gather(*(um(d) for d in docs))
    total = time.perf_counter() - t0
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / f"{nome}.jsonl", "w", encoding="utf-8") as f:
        for r in resultados:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    ev = collections.Counter(s for r in resultados for s in r["evidencia"].values())
    n_ev = sum(ev.values()) or 1
    tok_s = [r["tokens_saida"] / r["decode_s"] for r in resultados if r["decode_s"]]
    pre_s = [r["tokens_prompt"] / r["prefill_s"] for r in resultados if r["prefill_s"] and r["tokens_prompt"]]
    return {
        "modelo": modelo,
        "pensar": pensar,
        "concorrencia": conc,
        "n": len(docs),
        "gpu": gpu,
        "json_valido": sum(r["valido"] for r in resultados) / len(docs),
        "evidencia": {k: ev[k] / n_ev for k in ("literal", "aproximada", "ausente")},
        "s_por_doc_mediana": statistics.median(r["parede_s"] for r in resultados),
        "vazao_docs_por_min": 60 * len(docs) / total,
        "tokens_saida_media": statistics.mean(r["tokens_saida"] or 0 for r in resultados),
        "tokens_prompt_media": statistics.mean(r["tokens_prompt"] or 0 for r in resultados),
        "decode_tok_s": statistics.median(tok_s) if tok_s else None,
        "prefill_tok_s": statistics.median(pre_s) if pre_s else None,
        "projecao_4200_docs_h": 4200 / (60 * len(docs) / total) / 60,
    }


# ---------------------------------------------------------------- concordância
def carregar(nome) -> dict[str, dict]:
    arq = OUT / f"{nome}.jsonl"
    if not arq.exists():
        return {}
    return {r["pid"]: r["resposta"] for r in map(json.loads, arq.open(encoding="utf-8")) if r["valido"]}


def concordancia(a: str, b: str, cb: dict) -> dict:
    ra, rb = carregar(a), carregar(b)
    comuns = sorted(set(ra) & set(rb))
    saida = {"n": len(comuns)}
    for v in cb["variaveis"]:
        if v["tipo"] == "texto" or not comuns:
            continue
        xa = [str(ra[p][v["id"]]["valor"]) for p in comuns]
        xb = [str(rb[p][v["id"]]["valor"]) for p in comuns]
        acordo = sum(x == y for x, y in zip(xa, xb, strict=True)) / len(comuns)
        kappa = cohen_kappa_score(xa, xb) if len(set(xa) | set(xb)) > 1 else float("nan")
        saida[v["id"]] = {"acordo": acordo, "kappa": kappa}
    return saida


# ---------------------------------------------------------------- rótulos de tópicos
async def rotulos(cli, modelo) -> list[dict]:
    arqs = sorted(SAIDA.glob("s02_topicos_*.json"))
    if not arqs:
        return []
    await garantir_memoria(cli, modelo)
    topicos = json.loads(arqs[0].read_text())
    formato = {
        "type": "object",
        "properties": {"rotulo": {"type": "string"}, "descricao": {"type": "string"}},
        "required": ["rotulo", "descricao"],
        "additionalProperties": False,
    }
    sistema = (
        "Você nomeia tópicos de um corpus de artigos de ciência política e relações internacionais. "
        "Dado um conjunto de palavras-chave e títulos representativos, escreva em português um rótulo curto "
        "(no máximo 6 palavras, sem aspas) e uma descrição de uma ou duas frases do que o tópico reúne."
    )
    saida = []
    for t in topicos:
        usuario = (
            "Palavras-chave: "
            + ", ".join(t["palavras_chave"])
            + "\n\nTítulos representativos:\n"
            + "\n".join(f"- {x}" for x in t["representativos"])
        )
        j = await chat(cli, modelo, sistema, usuario, formato, False)
        saida.append({"cluster": t["cluster"], "n": t["n"], **json.loads(j["message"]["content"]), "s": j["_parede_s"]})
    return saida


# ---------------------------------------------------------------- leitura humana
def pagina_leitura(cb: dict, docs: list[dict], rot: dict) -> str:
    q, g = carregar("qwen-c1"), carregar("qwen-pensar")
    linhas = [
        "# Spike M0b: leitura das saídas",
        "",
        "Compare as codificações com o resumo. Coluna 1: qwen3.5:9b sem pensar (50 resumos); coluna 2: com o modo "
        "pensar ligado (só os 15 primeiros). **Negrito** = as duas divergem.",
        "",
    ]
    for d in docs[:15]:
        linhas += [
            f"## {d['titulos'].get('pt', '')} ({d['revista']}, {d['ano']})",
            "",
            f"> {d['resumos']['pt']}",
            "",
            "| Variável | qwen3.5:9b | qwen3.5:9b pensando |",
            "|---|---|---|",
        ]
        for v in cb["variaveis"]:
            a = (q.get(d["pid"]) or {}).get(v["id"], {})
            b = (g.get(d["pid"]) or {}).get(v["id"], {})
            fmt = lambda x: f"`{x.get('valor')}` — “{x.get('evidencia', '')}”" if x else "—"  # noqa: E731
            marca = "**" if b and a.get("valor") != b.get("valor") else ""
            linhas.append(f"| {marca}{v['id']}{marca} | {fmt(a)} | {fmt(b)} |")
        linhas.append("")
    if rot:
        linhas += ["# Rótulos de tópicos", ""]
        for modelo, lista in rot.items():
            linhas += [f"## {modelo}", ""]
            linhas += [f"- **{t['rotulo']}** (n={t['n']}): {t['descricao']}" for t in lista]
            linhas.append("")
    return "\n".join(linhas)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", nargs="*", default=PADRAO, choices=list(CONFIGS))
    ap.add_argument("--rotulos-com", nargs="*", default=[], help="modelos extras só para os rótulos de tópicos")
    ap.add_argument("--sem-rotulos", action="store_true")
    args = ap.parse_args()

    cb = yaml.safe_load((AQUI / "codebook_exemplo.yaml").read_text(encoding="utf-8"))
    docs = amostra(max((CONFIGS[c][3] for c in args.configs), default=50))
    print(
        f"amostra: {len(docs)} resumos de {len({d['revista'] for d in docs})} revistas; "
        f"prompt de sistema com ~{len(prompt_sistema(cb)) // 4} tokens"
    )

    # junta com rodadas anteriores (ex.: gemma primeiro, qwen depois)
    anterior = json.loads((SAIDA / "s03_llm.json").read_text()) if (SAIDA / "s03_llm.json").exists() else {}
    resumo, rot = anterior.get("configs", {}), anterior.get("rotulos", {})
    async with httpx.AsyncClient(timeout=httpx.Timeout(900.0)) as cli:
        modelo_atual = None
        for nome in args.configs:
            modelo = CONFIGS[nome][0]
            if modelo_atual and modelo != modelo_atual:
                if not args.sem_rotulos:
                    rot[modelo_atual] = await rotulos(cli, modelo_atual)
                await descarregar(cli, modelo_atual)
            modelo_atual = modelo
            print(f"== {nome}", flush=True)
            resumo[nome] = await rodar_config(cli, nome, cb, docs)
            (SAIDA / "s03_llm.json").write_text(  # parcial: sobrevive a uma interrupção
                json.dumps({"configs": resumo, "rotulos": rot}, ensure_ascii=False, indent=2, default=str)
            )
            r = resumo[nome]
            print(
                f"   válido {r['json_valido']:.0%} | evidência literal {r['evidencia']['literal']:.0%} "
                f"| {r['s_por_doc_mediana']:.1f} s/doc | {r['vazao_docs_por_min']:.1f} docs/min "
                f"| GPU {r['gpu'].get('fracao_gpu', 0):.0%} | projeção 4,2 mil: {r['projecao_4200_docs_h']:.1f} h",
                flush=True,
            )
        if modelo_atual:
            if not args.sem_rotulos:
                rot[modelo_atual] = await rotulos(cli, modelo_atual)
            await descarregar(cli, modelo_atual)
        for modelo in args.rotulos_com:
            print(f"== rótulos com {modelo}", flush=True)
            rot[modelo] = await rotulos(cli, modelo)
            await descarregar(cli, modelo)

    pares = [("qwen-c1", "qwen-c4"), ("qwen-c1", "qwen-pensar"), ("qwen-c1", "gemma-c1")]
    acordos = {f"{a} × {b}": concordancia(a, b, cb) for a, b in pares}
    (SAIDA / "s03_llm.json").write_text(
        json.dumps({"configs": resumo, "concordancia": acordos, "rotulos": rot}, ensure_ascii=False, indent=2, default=str)
    )
    (SAIDA / "s03_leitura.md").write_text(pagina_leitura(cb, docs, rot), encoding="utf-8")

    print(
        "\n| Config | JSON válido | evid. literal | aprox. | ausente | s/doc (med.) | docs/min "
        "| saída tok | decode tok/s | GPU | proj. 4,2 mil |"
    )
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for nome, r in resumo.items():
        e = r["evidencia"]
        print(
            f"| {nome} | {r['json_valido']:.0%} | {e['literal']:.0%} | {e['aproximada']:.0%} | {e['ausente']:.0%} "
            f"| {r['s_por_doc_mediana']:.1f} | {r['vazao_docs_por_min']:.1f} | {r['tokens_saida_media']:.0f} "
            f"| {r['decode_tok_s'] or 0:.0f} | {r['gpu'].get('fracao_gpu', 0):.0%} | {r['projecao_4200_docs_h']:.1f} h |"
        )
    print("\nConcordância (acordo / kappa):")
    for par, a in acordos.items():
        itens = ", ".join(f"{k} {v['acordo']:.0%}/{v['kappa']:.2f}" for k, v in a.items() if k != "n")
        print(f"- {par} (n={a['n']}): {itens}")


if __name__ == "__main__":
    asyncio.run(main())
