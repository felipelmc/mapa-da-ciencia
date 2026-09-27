"""A conferência das rotas de escrita do painel: só pedidos feitos desta máquina.

O `Host` precisa ser local (contra DNS apontado para cá) e o `Origin`, quando existe, também (contra uma página
aberta em outro site tentando gravar no projeto pelo navegador). A leitura também só responde a um `Host` local
(o *middleware* de `servidor/app.py`, com a mesma lista `HOSTS_LOCAIS`).
"""

from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import HTTPException, Request

HOSTS_LOCAIS = {"127.0.0.1", "localhost", "::1", "[::1]"}


def conferir_origem(request: Request) -> None:
    host = request.url.hostname
    origem = request.headers.get("origin")
    if host not in HOSTS_LOCAIS or (origem is not None and urlsplit(origem).hostname not in HOSTS_LOCAIS):
        raise HTTPException(403, "Gravação recusada: o painel só aceita escrita a partir desta máquina.")
