"""Buscador HTTP com cache em disco: a base de todas as fontes.

Cada resposta das APIs é gravada em `brutos/` (json.gz) antes de qualquer processamento.
Isso dá três garantias:

- **reprodutibilidade:** a normalização pode ser refeita a partir dos arquivos, mesmo que
  a API mude ou saia do ar;
- **retomada:** rodar de novo depois de uma interrupção só busca o que falta;
- **cortesia:** a segunda execução não faz nenhuma requisição.

A gravação é atômica (`.tmp` + `os.replace`), então um Ctrl+C nunca deixa arquivo pela metade.
"""

from __future__ import annotations

import asyncio
import contextlib
import gzip
import json
import os
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from mapa_da_ciencia import rede

STATUS_TEMPORARIOS = {429, 500, 502, 503, 504}


class ErroFonte(RuntimeError):
    """Uma API respondeu com erro definitivo. A mensagem diz qual e o que fazer."""


class FaltaNoCache(ErroFonte):
    """Modo offline: a resposta não está em `brutos/`."""


@dataclass
class Contadores:
    requisicoes: Counter[str] = field(default_factory=Counter)
    do_cache: Counter[str] = field(default_factory=Counter)
    creditos_openalex: int = 0
    saldo_openalex: int | None = None

    @property
    def total_requisicoes(self) -> int:
        return sum(self.requisicoes.values())


def ler_gz(caminho: Path) -> Any:
    with gzip.open(caminho, "rt", encoding="utf-8") as f:
        return json.load(f)


def gravar_gz(caminho: Path, dados: Any, *, ocultar: tuple[str, ...] = ()) -> None:
    """Grava JSON comprimido de forma atômica. `ocultar` tira segredos (ex.: a chave de API) do conteúdo."""
    texto = json.dumps(dados, ensure_ascii=False)
    for segredo in ocultar:
        if segredo:
            texto = texto.replace(segredo, "***")
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_name(caminho.name + ".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        f.write(texto)
    os.replace(tmp, caminho)


def limpar_temporarios(brutos: Path) -> int:
    """Apaga arquivos `.tmp` deixados por uma execução interrompida. Devolve quantos."""
    n = 0
    if brutos.exists():
        for tmp in brutos.rglob("*.tmp"):
            tmp.unlink(missing_ok=True)
            n += 1
    return n


class Buscador:
    """Faz GETs JSON com cache em `brutos/`, requisições simultâneas limitadas e novas tentativas."""

    def __init__(
        self,
        brutos: Path,
        *,
        pasta_projeto: Path | None = None,
        offline: bool = False,
        concorrencia: int = 4,
        tentativas: int = 6,
        espera_inicial: float = 1.0,
        cliente: httpx.AsyncClient | None = None,
    ) -> None:
        self.brutos = brutos
        self.pasta_projeto = pasta_projeto
        self.offline = offline
        self.tentativas = tentativas
        self.espera_inicial = espera_inicial
        self.contadores = Contadores()
        self._semaforo = asyncio.Semaphore(concorrencia)
        self._cliente = cliente
        self._proprio = cliente is None

    async def __aenter__(self) -> Buscador:
        if self._cliente is None:
            self._cliente = rede.cliente_async(pasta=self.pasta_projeto)
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._proprio and self._cliente is not None:
            await self._cliente.aclose()
            self._cliente = None

    async def json(
        self,
        fonte: str,
        url: str,
        params: dict[str, Any],
        cache: str | Path,
        *,
        atualizar: bool = False,
        custo: int = 0,
        ausente_se_404: bool = False,
    ) -> Any:
        """Resposta JSON, do cache se existir. `custo` são os créditos do OpenAlex que a chamada consome.

        Com `ausente_se_404`, um 404 vira `None` (e também vai para o cache), em vez de erro.
        """
        caminho = self.brutos / cache
        if caminho.exists() and not atualizar:
            try:
                dados = ler_gz(caminho)
                self.contadores.do_cache[fonte] += 1
                return dados
            except (OSError, EOFError, json.JSONDecodeError):
                caminho.unlink(missing_ok=True)  # arquivo corrompido: busca de novo
        if self.offline:
            raise FaltaNoCache(f"Modo offline e sem cache para {url} ({caminho.relative_to(self.brutos)}).")
        dados, resposta = await self._buscar(url, params, ausente_se_404=ausente_se_404)
        self.contadores.requisicoes[fonte] += 1
        if fonte == "openalex":
            self.contadores.creditos_openalex += custo
            saldo = resposta.headers.get("x-ratelimit-remaining")
            if saldo and saldo.isdigit():
                self.contadores.saldo_openalex = int(saldo)
        gravar_gz(caminho, dados, ocultar=(str(params.get("api_key", "")),))
        return dados

    async def _buscar(
        self, url: str, params: dict[str, Any], *, ausente_se_404: bool = False
    ) -> tuple[Any, httpx.Response]:
        assert self._cliente is not None, "use o Buscador dentro de `async with`"
        espera = self.espera_inicial
        ultimo_erro: Exception | None = None
        for _ in range(self.tentativas):
            try:
                async with self._semaforo:
                    r = await self._cliente.get(url, params=params)
                if r.status_code in STATUS_TEMPORARIOS:
                    ultimo_erro = ErroFonte(f"{url} respondeu {r.status_code}")
                    retry_after = r.headers.get("retry-after", "")
                    await asyncio.sleep(float(retry_after) if retry_after.isdigit() else espera)
                elif r.status_code == 404 and ausente_se_404:
                    return None, r
                elif r.status_code >= 400:
                    raise ErroFonte(f"{url} respondeu {r.status_code}: {r.text[:200]}")
                else:
                    return r.json(), r
            except (httpx.TransportError, json.JSONDecodeError) as e:
                ultimo_erro = e
                await asyncio.sleep(espera)
            espera *= 2
        raise ErroFonte(
            f"Não foi possível acessar {url} depois de {self.tentativas} tentativas ({ultimo_erro}). "
            "Confira a conexão com `mapa diagnostico` e rode de novo: o que já foi baixado não se perde."
        )


def em_cache(caminho: Path) -> bool:
    """O arquivo existe e pode ser lido (usado para contar o que falta sem baixar)."""
    if not caminho.exists():
        return False
    with contextlib.suppress(OSError, EOFError, json.JSONDecodeError):
        ler_gz(caminho)
        return True
    return False
