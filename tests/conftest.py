"""Fixtures compartilhadas: APIs falsas (respx) servindo respostas reais recortadas em tests/fixtures/."""

from __future__ import annotations

import gzip
import json
import math
import re
import zlib
from collections import Counter
from pathlib import Path

import httpx
import pytest
import respx

FIXTURES = Path(__file__).parent / "fixtures"

# As cópias do iCloud Drive ("test_cli 2.py") são versões antigas dos testes: ficam fora da coleta.
collect_ignore_glob = ["* [0-9].py", "* [0-9][0-9].py"]
AM = "https://articlemeta.scielo.org/api/v1"
OA = "https://api.openalex.org"
OLLAMA_FALSO = "http://ollama.teste:11434"
DIM_FALSA = 64
GB = 1024**3


def resposta_classificacao_falsa(corpo: dict) -> str:
    """Classificação falsa e determinística: em cada variável, a primeira categoria (ou verdadeiro, ou um período) e,
    como evidência, as oito primeiras palavras do resumo do documento."""
    documento = next(m["content"] for m in corpo["messages"] if m["role"] == "user")
    resumo = documento.split("Resumo:", 1)[-1].split()
    evidencia = " ".join(resumo[:8])
    saida = {}
    for var, prop in corpo["format"]["properties"].items():
        valor = prop["properties"]["valor"]
        if valor["type"] == "boolean":
            v: object = True
        elif valor["type"] == "array":
            v = [valor["items"]["enum"][0]]
        elif "enum" in valor:
            v = valor["enum"][0]
        else:
            v = "2010–2020"
        saida[var] = {"evidencia": evidencia, "valor": v}
    return json.dumps(saida, ensure_ascii=False)


def resposta_chat_padrao(corpo: dict) -> str:
    """Resposta determinística do chat falso: uma classificação, se o esquema pedir uma (`evidencia` e `valor` por
    variável); senão, um rótulo com as duas primeiras palavras-chave do pedido."""
    props = (corpo.get("format") or {}).get("properties") or {}
    if props and all("evidencia" in (p.get("properties") or {}) for p in props.values()):
        return resposta_classificacao_falsa(corpo)
    pedido = corpo["messages"][-1]["content"]
    achado = re.search(r"Palavras-chave: ([^\n]+)", pedido)
    termos = [t.strip() for t in achado.group(1).split(",")] if achado else ["assunto", "geral"]
    return json.dumps(
        {
            "rotulo": f"{termos[0].capitalize()} e {termos[1]}",
            "descricao": f"Trabalhos sobre {termos[0]} e {termos[1]}.",
        },
        ensure_ascii=False,
    )


def vetor_falso(texto: str) -> list[float]:
    """Embedding falso e determinístico: saco de palavras com hash. Textos com vocabulário parecido ficam perto,
    o que basta para os testes do agrupamento (sem depender do Ollama nem de um modelo de verdade)."""
    v = [0.0] * DIM_FALSA
    for palavra in re.findall(r"[a-zà-ÿ]{3,}", texto.lower()):
        h = zlib.crc32(palavra.encode())
        v[h % DIM_FALSA] += 1.0
        v[(h >> 8) % DIM_FALSA] += 0.5
    norma = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / norma for x in v]


def _ler_jsonl(caminho: Path) -> list[dict]:
    with gzip.open(caminho, "rt", encoding="utf-8") as f:
        return [json.loads(linha) for linha in f]


def obras_openalex() -> list[dict]:
    with gzip.open(FIXTURES / "openalex" / "obras.jsonl.gz", "rt", encoding="utf-8") as f:
        return [json.loads(linha) for linha in f]


def registros_articlemeta() -> dict[str, dict]:
    with gzip.open(FIXTURES / "articlemeta" / "artigos.jsonl.gz", "rt", encoding="utf-8") as f:
        return {linha["pid"]: linha["registro"] for linha in map(json.loads, f)}


def identificadores_op() -> dict:
    return json.loads((FIXTURES / "articlemeta" / "identificadores-op.json").read_text(encoding="utf-8"))


def casos_especiais() -> dict[str, str]:
    return json.loads((FIXTURES / "articlemeta" / "casos.json").read_text(encoding="utf-8"))


class ApisFalsas:
    """Roteador respx com as respostas das fixtures e contagem de chamadas por fonte."""

    def __init__(self, router: respx.MockRouter) -> None:
        self.router = router
        self.chamadas: Counter[str] = Counter()
        self.registros = registros_articlemeta()
        self.identificadores = {"0104-6276": identificadores_op()}
        router.get(f"{AM}/article/identifiers/").mock(side_effect=self._identificadores)
        router.get(f"{AM}/article/").mock(side_effect=self._artigo)
        router.get(f"{AM}/journal/identifiers/").respond(json={"meta": {"total": 0}, "objects": []})  # diagnóstico
        self.obras = obras_openalex()
        self.total_forcado: int | None = None  # para simular buscas enormes
        # Ollama: modelos "instalados" (tamanhos pequenos, para a checagem de memória passar em qualquer máquina)
        self.modelos_ollama = {"qwen3-embedding:0.6b": 0.6, "qwen3.5:4b": 0.5, "qwen3.5:9b": 0.5}
        self.digests: dict[str, str] = {}  # para simular um modelo atualizado
        self.carregados: set[str] = set()
        self.textos_embutidos: list[str] = []
        router.get(f"{OLLAMA_FALSO}/api/version").respond(json={"version": "0.34.2"})
        router.get(f"{OLLAMA_FALSO}/api/tags").mock(side_effect=self._tags)
        router.get(f"{OLLAMA_FALSO}/api/ps").mock(side_effect=self._ps)
        router.post(f"{OLLAMA_FALSO}/api/embed").mock(side_effect=self._embed)
        router.post(f"{OLLAMA_FALSO}/api/generate").mock(side_effect=self._generate)
        router.post(f"{OLLAMA_FALSO}/api/chat").mock(side_effect=self._chat)
        router.post(f"{OLLAMA_FALSO}/api/pull").mock(side_effect=self._pull)
        self.pedidos_chat: list[dict] = []
        # os testes trocam esta função para simular respostas (JSON inválido, rótulo sem acento...)
        self.responder_chat = resposta_chat_padrao
        self.fora_dos_filtros: set[str] = set()  # DOIs que só o endereço direto /works/doi:… acha
        router.get(url__regex=rf"^{re.escape(OA)}/works/doi:").mock(side_effect=self._obra)
        router.get(f"{OA}/works").mock(side_effect=self._obras)
        self.instituicoes = {
            r["id"].rsplit("/", 1)[-1]: r for r in _ler_jsonl(FIXTURES / "openalex" / "instituicoes.jsonl.gz")
        }
        router.get(f"{OA}/institutions").mock(side_effect=self._instituicoes)

    def _tags(self, _: httpx.Request) -> httpx.Response:
        modelos = [
            {"name": n, "size": int(t * GB), "digest": self.digests.get(n, f"{zlib.crc32(n.encode()):08x}00000000")}
            for n, t in self.modelos_ollama.items()
        ]
        return httpx.Response(200, json={"models": modelos})

    def _ps(self, _: httpx.Request) -> httpx.Response:
        tamanho = self.modelos_ollama
        modelos = [
            {"name": n, "size": int(tamanho[n] * GB), "size_vram": int(tamanho[n] * GB)} for n in self.carregados
        ]
        return httpx.Response(200, json={"models": modelos})

    def _modelo(self, corpo: dict) -> httpx.Response | None:
        if corpo["model"] not in self.modelos_ollama:
            erro = f'model "{corpo["model"]}" not found, try pulling it first'
            return httpx.Response(404, json={"error": erro})
        self.carregados.add(corpo["model"])
        return None

    def _embed(self, request: httpx.Request) -> httpx.Response:
        self.chamadas["ollama"] += 1
        corpo = json.loads(request.content)
        if erro := self._modelo(corpo):
            return erro
        self.textos_embutidos += corpo["input"]
        return httpx.Response(
            200, json={"model": corpo["model"], "embeddings": [vetor_falso(t) for t in corpo["input"]]}
        )

    def _chat(self, request: httpx.Request) -> httpx.Response:
        self.chamadas["ollama_chat"] += 1
        corpo = json.loads(request.content)
        if erro := self._modelo(corpo):
            return erro
        self.pedidos_chat.append(corpo)
        conteudo = self.responder_chat(corpo)
        return httpx.Response(
            200, json={"model": corpo["model"], "message": {"role": "assistant", "content": conteudo}}
        )

    def _pull(self, request: httpx.Request) -> httpx.Response:
        """`ollama pull` falso: um fluxo de linhas JSON com duas camadas; o modelo passa a estar instalado."""
        modelo = json.loads(request.content)["model"]
        if modelo.startswith("nao-existe"):
            linhas = [{"status": "pulling manifest"}, {"error": "pull model manifest: file does not exist"}]
        else:
            linhas = [{"status": "pulling manifest"}]
            for camada, total in (("sha256:aaaaaaaaaaaaaaaa", 30_000_000), ("sha256:bbbbbbbbbbbbbbbb", 2_000_000)):
                linhas += [{"status": f"pulling {camada[7:19]}", "digest": camada, "total": total, "completed": c}
                           for c in (0, total // 2, total)]  # fmt: skip
            linhas += [{"status": "verifying sha256 digest"}, {"status": "success"}]
            self.modelos_ollama[modelo] = 1.5
        corpo = "\n".join(json.dumps(linha) for linha in linhas) + "\n"
        return httpx.Response(200, content=corpo.encode(), headers={"content-type": "application/x-ndjson"})

    def _generate(self, request: httpx.Request) -> httpx.Response:
        corpo = json.loads(request.content)
        if corpo.get("keep_alive") == 0:
            self.carregados.discard(corpo["model"])
        return httpx.Response(200, json={"model": corpo["model"], "done": True})

    def _obra(self, request: httpx.Request) -> httpx.Response:
        self.chamadas["openalex"] += 1
        doi = request.url.path.split("/works/doi:", 1)[1].lower()
        obra = next((o for o in self.obras if (o.get("doi") or "").lower().endswith(doi)), None)
        return httpx.Response(200, json=obra) if obra else httpx.Response(404, json={"error": "not found"})

    def _instituicoes(self, request: httpx.Request) -> httpx.Response:
        """Registros das instituições pelo filtro `openalex:I1|I2…` (até 100 por página)."""
        self.chamadas["openalex_instituicoes"] += 1
        filtro = request.url.params.get("filter", "")
        ids = filtro.removeprefix("openalex:").split("|") if filtro.startswith("openalex:") else []
        achadas = [self.instituicoes[i] for i in ids if i in self.instituicoes]
        return httpx.Response(200, json={"meta": {"count": len(achadas)}, "results": achadas})

    def _obras(self, request: httpx.Request) -> httpx.Response:
        """Entende os filtros usados pelo mapa: ISSN (com |), intervalo de anos e lista de DOIs."""
        self.chamadas["openalex"] += 1
        filtros = dict(f.split(":", 1) for f in request.url.params.get("filter", "").split(",") if ":" in f)
        obras = [o for o in self.obras if (o.get("doi") or "").lower().removeprefix("https://doi.org/")
                 not in self.fora_dos_filtros]  # fmt: skip
        if "locations.source.issn" in filtros:
            issns = set(filtros["locations.source.issn"].split("|"))
            obras = [o for o in obras if issns & set(_issns_da_fonte(o))]
        if "publication_year" in filtros:
            a, _, b = filtros["publication_year"].partition("-")
            obras = [o for o in obras if int(a) <= (o.get("publication_year") or 0) <= int(b or a)]
        if "title_and_abstract.search" in filtros:
            termo = filtros["title_and_abstract.search"].lower()
            obras = [o for o in obras if termo in (o.get("title") or "").lower()]
        if "doi" in filtros:
            dois = {d.lower().removeprefix("https://doi.org/") for d in filtros["doi"].split("|")}
            obras = [o for o in obras if (o.get("doi") or "").lower().removeprefix("https://doi.org/") in dois]
        return httpx.Response(
            200,
            json={"meta": {"count": self.total_forcado or len(obras), "next_cursor": None}, "results": obras},
            headers={"x-ratelimit-remaining": "990"},
        )

    def _identificadores(self, request: httpx.Request) -> httpx.Response:
        self.chamadas["articlemeta"] += 1
        issn = request.url.params.get("issn")
        offset = int(request.url.params.get("offset", 0))
        dados = self.identificadores.get(issn, {"meta": {"total": 0}, "objects": []})
        return httpx.Response(200, json={"meta": dados["meta"], "objects": dados["objects"][offset : offset + 1000]})

    def _artigo(self, request: httpx.Request) -> httpx.Response:
        self.chamadas["articlemeta"] += 1
        # PID desconhecido: a API real responde 200 com o corpo `null`
        corpo = json.dumps(self.registros.get(request.url.params.get("code"))).encode()
        return httpx.Response(200, content=corpo, headers={"content-type": "application/json"})


@pytest.fixture
def apis_falsas(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", OLLAMA_FALSO)
    with respx.mock(assert_all_called=False) as router:
        yield ApisFalsas(router)


def _issns_da_fonte(obra: dict) -> list[str]:
    locais = [obra.get("primary_location") or {}, *(obra.get("locations") or [])]
    return [i for lc in locais for i in ((lc.get("source") or {}).get("issn") or [])]
