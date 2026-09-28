"""Segredos do projeto, gerados uma vez e guardados no `estado.sqlite` (que nunca é publicado nem vai para o git).

O primeiro uso é o id publicado das pessoas nas redes: um HMAC do id interno com o segredo `redes`. Sem o segredo,
não dá para ligar o id publicado a um ORCID ou a um id do OpenAlex testando candidatos (o *hash* sem chave de um
ORCID se quebra em minutos, porque os ORCIDs válidos são só ~10⁸). Com o mesmo `estado.sqlite`, os ids ficam
estáveis entre execuções; um projeto copiado sem ele ganha ids novos na próxima `mapa redes`.
"""

from __future__ import annotations

import secrets
import sqlite3

from .projeto import Projeto

_ESQUEMA = "CREATE TABLE IF NOT EXISTS segredos (nome TEXT PRIMARY KEY, valor TEXT NOT NULL)"


def segredo(projeto: Projeto, nome: str) -> bytes:
    """O segredo `nome` do projeto (32 bytes aleatórios), criado na primeira chamada."""
    con = sqlite3.connect(projeto.estado)
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute(_ESQUEMA)
        with con:
            con.execute("INSERT OR IGNORE INTO segredos (nome, valor) VALUES (?, ?)", (nome, secrets.token_hex(32)))
        (valor,) = con.execute("SELECT valor FROM segredos WHERE nome = ?", (nome,)).fetchone()
    finally:
        con.close()
    return bytes.fromhex(valor)
