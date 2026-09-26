"""Adaptador do Ollama (servidor local, `http://localhost:11434` por padrão).

Fala direto com a API HTTP do Ollama via httpx, sem SDK. O endereço pode ser trocado
pela variável `OLLAMA_HOST`, como no próprio Ollama.
"""

from __future__ import annotations

import os

import httpx

from mapa_da_ciencia.llm.base import ErroProvedor, ModeloCarregado, ModeloInstalado

GB = 1024**3
ENDERECO_PADRAO = "http://localhost:11434"


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

    def _get(self, caminho: str) -> dict:
        try:
            r = self._http.get(caminho)
            r.raise_for_status()
            return r.json()
        except httpx.ConnectError as e:
            raise ErroProvedor(
                f"O Ollama não está respondendo em {self.endereco}. Abra o aplicativo Ollama ou rode `ollama serve`. "
                "Para instalar: https://ollama.com/download"
            ) from e
        except httpx.HTTPError as e:
            raise ErroProvedor(f"Erro ao consultar o Ollama ({caminho}): {e}") from e

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

    def descarregar(self, modelo: str) -> None:
        """Tira o modelo da memória agora (em vez de esperar o `keep_alive` expirar)."""
        try:
            self._http.post("/api/generate", json={"model": modelo, "keep_alive": 0}).raise_for_status()
        except httpx.HTTPError as e:
            raise ErroProvedor(f"Não foi possível descarregar {modelo}: {e}") from e
