"""Interface comum dos provedores de modelos de linguagem.

No MVP só existe o adaptador do Ollama (`llm/ollama.py`). Provedores na nuvem entram
depois como novos adaptadores que implementam este mesmo protocolo. O protocolo cresce
a cada marco: embeddings e saída estruturada no M3 (tópicos e rótulos).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Protocol


class ErroProvedor(RuntimeError):
    """Falha ao falar com o provedor de modelos. A mensagem já diz o que fazer."""


@dataclass(frozen=True)
class ModeloInstalado:
    nome: str
    tamanho_gb: float
    digest: str


@dataclass(frozen=True)
class ModeloCarregado:
    nome: str
    tamanho_gb: float
    na_gpu_gb: float

    @property
    def fracao_gpu(self) -> float:
        return self.na_gpu_gb / self.tamanho_gb if self.tamanho_gb else 0.0


class ProvedorLLM(Protocol):
    def versao(self) -> str: ...

    def listar_modelos(self) -> list[ModeloInstalado]: ...

    def modelos_carregados(self) -> list[ModeloCarregado]: ...

    def descarregar(self, modelo: str) -> None: ...

    def embutir_lotes(
        self,
        modelo: str,
        textos: list[str],
        *,
        lote: int = 32,
        num_ctx: int | None = None,
        keep_alive: str = "10m",
        ao_avancar: Callable[[int], None] | None = None,
    ) -> Iterator[list[list[float]]]: ...
