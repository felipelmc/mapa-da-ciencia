"""Clientes HTTP do projeto. Toda requisição externa passa por aqui (ver ADR 0001).

- Certificados do sistema operacional via `truststore`, para funcionar em redes com
  proxy ou autoridade certificadora própria (universidades, órgãos públicos).
- User-Agent identificando o projeto e, se configurado, o e-mail de contato
  (`MAPA_EMAIL`), como pedem as boas práticas das APIs públicas.
"""

from __future__ import annotations

import os
import ssl
from pathlib import Path

import httpx
import truststore

from mapa_da_ciencia import __version__

URL_PROJETO = "https://github.com/felipelmc/mapa-da-ciencia"


def ler_env(pasta: Path) -> dict[str, str]:
    """Lê `pasta/.env` (linhas `CHAVE=valor`; `#` comenta). Não sobrescreve o ambiente."""
    arq = pasta / ".env"
    valores: dict[str, str] = {}
    if arq.exists():
        for linha in arq.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if linha and not linha.startswith("#") and "=" in linha:
                chave, valor = linha.split("=", 1)
                valores[chave.strip()] = valor.strip().strip("'\"")
    return valores


def variavel(chave: str, pasta: Path | None = None) -> str | None:
    """Valor de uma variável: primeiro o ambiente, depois o `.env` do projeto."""
    if os.environ.get(chave):
        return os.environ[chave]
    return (ler_env(pasta).get(chave) or None) if pasta else None


def user_agent(pasta: Path | None = None) -> str:
    email = variavel("MAPA_EMAIL", pasta)
    contato = f"; mailto:{email}" if email else ""
    return f"mapa-da-ciencia/{__version__} (+{URL_PROJETO}{contato})"


def _ssl() -> ssl.SSLContext:
    return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)


def cliente(*, timeout: float = 60.0, pasta: Path | None = None) -> httpx.Client:
    """Cliente síncrono para APIs externas (ArticleMeta, OpenAlex)."""
    return httpx.Client(
        verify=_ssl(),
        timeout=timeout,
        headers={"User-Agent": user_agent(pasta)},
        follow_redirects=True,
    )


def cliente_async(*, timeout: float = 60.0, pasta: Path | None = None) -> httpx.AsyncClient:
    """Cliente assíncrono para coletas com requisições simultâneas."""
    return httpx.AsyncClient(
        verify=_ssl(),
        timeout=timeout,
        headers={"User-Agent": user_agent(pasta)},
        follow_redirects=True,
    )
