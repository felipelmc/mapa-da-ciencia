"""A conferência das rotas de escrita do painel: só pedidos feitos desta máquina.

O `Host` precisa ser local (contra DNS apontado para cá) e o `Origin`, quando existe, também (contra uma página
aberta em outro site tentando gravar no projeto pelo navegador). A leitura também só responde a um `Host` local
(o *middleware* de `servidor/app.py`, com a mesma lista `HOSTS_LOCAIS`).

No Colab (`criar_app(so_local=False)`), o painel é aberto pelo *proxy* do Google, que chega com o endereço dele no
`Host` e no `Origin`: aí a lista de hosts locais não vale, mas uma escrita com `Origin` de outro endereço (ou
`null`) continua recusada. A máquina do Colab é só de quem a abriu, e o *proxy* exige o login dessa pessoa.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import HTTPException, Request

HOSTS_LOCAIS = {"127.0.0.1", "localhost", "::1", "[::1]"}


def conferir_origem(request: Request) -> None:
    origem = request.headers.get("origin")
    if not getattr(request.app.state, "so_local", True):
        # no Colab, o Host é o do proxy; mas uma escrita vinda de outra página (ou de uma origem opaca, "null") não
        # tem por que passar
        if origem is not None and (origem == "null" or urlsplit(origem).hostname != request.url.hostname):
            raise HTTPException(403, "Gravação recusada: o pedido veio de outra página.")
        return
    host = request.url.hostname
    if host not in HOSTS_LOCAIS or (origem is not None and urlsplit(origem).hostname not in HOSTS_LOCAIS):
        raise HTTPException(403, "Gravação recusada: o painel só aceita escrita a partir desta máquina.")
