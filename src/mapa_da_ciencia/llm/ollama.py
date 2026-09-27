"""Adaptador do Ollama (servidor local, `http://localhost:11434` por padrão).

Fala direto com a API HTTP do Ollama via httpx, sem SDK. O endereço pode ser trocado
pela variável `OLLAMA_HOST`, como no próprio Ollama.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterator

import httpx

from mapa_da_ciencia.llm.base import ErroProvedor, ModeloCarregado, ModeloInstalado
from mapa_da_ciencia.progresso import Progresso, ProgressoNulo

GB = 1024**3
MB = 1000**2
ENDERECO_PADRAO = "http://localhost:11434"
TIMEOUT_GERACAO = 600.0  # carregar um modelo do disco e processar um lote pode levar minutos


def endereco_padrao() -> str:
    host = os.environ.get("OLLAMA_HOST", ENDERECO_PADRAO)
    return host if host.startswith("http") else f"http://{host}"


def _mesmo_modelo(a: str, b: str) -> bool:
    """`bge-m3` e `bge-m3:latest` são o mesmo modelo."""
    return a.removesuffix(":latest") == b.removesuffix(":latest")


class Ollama:
    def __init__(self, endereco: str | None = None, *, timeout: float = 30.0) -> None:
        self.endereco = (endereco or endereco_padrao()).rstrip("/")
        self._http = httpx.Client(base_url=self.endereco, timeout=timeout)

    def _sem_resposta(self) -> ErroProvedor:
        return ErroProvedor(
            f"O Ollama não está respondendo em {self.endereco}. Abra o aplicativo Ollama ou rode `ollama serve`. "
            "Para instalar: https://ollama.com/download"
        )

    def _get(self, caminho: str) -> dict:
        try:
            r = self._http.get(caminho)
            r.raise_for_status()
            return r.json()
        except httpx.ConnectError as e:
            raise self._sem_resposta() from e
        except httpx.HTTPError as e:
            raise ErroProvedor(f"Erro ao consultar o Ollama ({caminho}): {e}") from e

    def _post(self, caminho: str, corpo: dict) -> dict:
        """POST com os mesmos erros amigáveis do `_get`. Modelo não instalado vira a dica de `ollama pull`."""
        try:
            r = self._http.post(caminho, json=corpo, timeout=TIMEOUT_GERACAO)
        except httpx.ConnectError as e:
            raise self._sem_resposta() from e
        except httpx.HTTPError as e:
            raise ErroProvedor(f"Erro ao consultar o Ollama ({caminho}): {e}") from e
        if r.status_code == 404 and "not found" in r.text:
            from mapa_da_ciencia.llm.perfis import TAMANHOS_GB

            modelo = corpo.get("model", "?")
            tamanho = TAMANHOS_GB.get(modelo)
            download = f" (download de ~{tamanho:.1f} GB)".replace(".", ",") if tamanho else ""
            raise ErroProvedor(f"O modelo {modelo} não está instalado no Ollama. Rode: ollama pull {modelo}{download}")
        if r.status_code >= 400:
            raise ErroProvedor(f"O Ollama respondeu {r.status_code} em {caminho}: {r.text[:200]}")
        return r.json()

    def versao(self) -> str:
        return self._get("/api/version").get("version", "?")

    def listar_modelos(self) -> list[ModeloInstalado]:
        return [
            ModeloInstalado(m["name"], m["size"] / GB, m.get("digest", "")[:12])
            for m in self._get("/api/tags").get("models", [])
        ]

    def modelos_carregados(self) -> list[ModeloCarregado]:
        return [
            ModeloCarregado(m["name"], m["size"] / GB, m.get("size_vram", 0) / GB)
            for m in self._get("/api/ps").get("models", [])
        ]

    def instalado(self, modelo: str) -> ModeloInstalado | None:
        return next((m for m in self.listar_modelos() if _mesmo_modelo(m.nome, modelo)), None)

    def baixar(self, modelo: str, progresso: Progresso | None = None) -> None:
        """Baixa um modelo (`ollama pull`), com o progresso em MB de cada camada."""
        progresso = progresso or ProgressoNulo()
        camada, feito = None, 0
        try:
            with self._http.stream("POST", "/api/pull", json={"model": modelo, "stream": True}, timeout=None) as r:
                if r.status_code >= 400:
                    r.read()
                    raise ErroProvedor(f"O Ollama não conseguiu baixar {modelo}: {r.text[:200]}")
                for linha in r.iter_lines():
                    if not linha.strip():
                        continue
                    evento = json.loads(linha)
                    if erro := evento.get("error"):
                        raise ErroProvedor(f"O Ollama não conseguiu baixar {modelo}: {erro}")
                    total, completo = evento.get("total"), evento.get("completed")
                    if total and evento.get("digest") != camada:
                        camada, feito = evento.get("digest"), 0
                        progresso.etapa(f"Baixando {modelo} ({evento['digest'][7:19]})", total // MB)
                    if total and completo is not None:
                        progresso.avancar(max(0, completo // MB - feito))
                        feito = max(feito, completo // MB)
                    elif evento.get("status") and not total:
                        progresso.mensagem(evento["status"])
        except httpx.ConnectError as e:
            raise self._sem_resposta() from e
        finally:
            progresso.fim()

    def embutir_lotes(
        self,
        modelo: str,
        textos: list[str],
        *,
        lote: int = 32,
        num_ctx: int | None = None,
        keep_alive: str = "10m",
        ao_avancar: Callable[[int], None] | None = None,
    ) -> Iterator[list[list[float]]]:
        """Embeddings em lotes (`/api/embed`), um lote por vez, na ordem dos textos.

        Devolver lote a lote deixa quem chama guardar cada um (num array, num cache) sem acumular milhares de
        listas de floats do Python. Textos maiores que o contexto são truncados pelo Ollama (`truncate`).
        """
        opcoes = {"num_ctx": num_ctx} if num_ctx else {}
        for inicio in range(0, len(textos), lote):
            parte = textos[inicio : inicio + lote]
            corpo = {"model": modelo, "input": parte, "truncate": True, "keep_alive": keep_alive, "options": opcoes}
            vetores = self._post("/api/embed", corpo).get("embeddings") or []
            if len(vetores) != len(parte):
                raise ErroProvedor(
                    f"O Ollama devolveu {len(vetores)} embeddings para {len(parte)} textos ({modelo}). "
                    "Rode de novo; se persistir, atualize o Ollama."
                )
            if ao_avancar:
                ao_avancar(len(parte))
            yield vetores

    def gerar_estruturado(
        self,
        modelo: str,
        mensagens: list[dict[str, str]],
        esquema: dict,
        *,
        num_ctx: int = 8192,
        temperatura: float = 0.0,
        semente: int = 7,
        pensar: bool = False,
        keep_alive: str = "10m",
    ) -> dict:
        """Resposta do modelo como JSON que segue `esquema` (`/api/chat` com `format`). Sem raciocínio por padrão.

        O Ollama restringe a geração ao esquema, então a resposta é JSON válido quase sempre; se não for, o erro
        diz qual modelo falhou, e quem chama decide se tenta de novo.
        """
        corpo = {
            "model": modelo,
            "messages": mensagens,
            "format": esquema,
            "stream": False,
            "think": pensar,
            "keep_alive": keep_alive,
            "options": {"num_ctx": num_ctx, "temperature": temperatura, "seed": semente},
        }
        conteudo = (self._post("/api/chat", corpo).get("message") or {}).get("content") or ""
        try:
            resposta = json.loads(conteudo)
        except json.JSONDecodeError as e:
            raise ErroProvedor(f"{modelo} não devolveu um JSON válido: {conteudo[:120]!r}") from e
        if not isinstance(resposta, dict):
            raise ErroProvedor(f"{modelo} devolveu {type(resposta).__name__}, e não um objeto JSON.")
        return resposta

    def embutir(self, modelo: str, textos: list[str], **opcoes) -> list[list[float]]:
        """Todos os embeddings de uma vez (para listas pequenas; para o corpus, use `embutir_lotes`)."""
        return [v for vetores in self.embutir_lotes(modelo, textos, **opcoes) for v in vetores]

    def descarregar(self, modelo: str) -> None:
        """Tira o modelo da memória agora (em vez de esperar o `keep_alive` expirar)."""
        try:
            self._http.post("/api/generate", json={"model": modelo, "keep_alive": 0}).raise_for_status()
        except httpx.HTTPError as e:
            raise ErroProvedor(f"Não foi possível descarregar {modelo}: {e}") from e
