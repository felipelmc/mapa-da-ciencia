"""Um painel por projeto: a trava do `mapa painel`.

Dois painéis no mesmo projeto se atropelam: o segundo, ao abrir, marcava como interrompida a etapa que o primeiro
ainda rodava, e aceitava outra etapa ao mesmo tempo. O painel trava o projeto enquanto está aberto (`flock` num
arquivo `.painel.lock` na pasta dele, com o PID e a porta); um segundo `mapa painel` no mesmo projeto não abre e
aponta o endereço do primeiro. A trava some com o processo (o sistema a solta mesmo se ele morrer). Sem `fcntl`
(Windows), não há trava.
"""

from __future__ import annotations

import json
import os
from typing import IO

from ..config import ErroConfig
from ..projeto import Projeto

ARQUIVO = ".painel.lock"


class PainelJaAberto(ErroConfig):
    """Outro `mapa painel` já está aberto neste projeto."""


def travar(projeto: Projeto, porta: int) -> IO[str] | None:
    """Trava o projeto para este painel. Devolve o arquivo aberto, que precisa ficar vivo (e aberto) enquanto o
    painel roda; `None` onde não há `fcntl`."""
    try:
        import fcntl
    except ImportError:  # Windows
        return None
    arquivo = open(projeto.raiz / ARQUIVO, "a+", encoding="utf-8")  # noqa: SIM115 (fica aberto com o painel)
    try:
        fcntl.flock(arquivo, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        arquivo.seek(0)
        try:
            dono = json.loads(arquivo.read() or "{}")
        except json.JSONDecodeError:
            dono = {}
        arquivo.close()
        onde = f" em http://127.0.0.1:{dono['porta']}/" if dono.get("porta") else ""
        raise PainelJaAberto(
            f"Este projeto já tem um painel aberto{onde}. Use aquele (ou feche-o com Ctrl+C antes de abrir outro): "
            "dois painéis no mesmo projeto atrapalham as etapas um do outro."
        ) from None
    arquivo.seek(0)
    arquivo.truncate()
    arquivo.write(json.dumps({"pid": os.getpid(), "porta": porta}))
    arquivo.flush()
    _fora_do_git(projeto)
    return arquivo


def _fora_do_git(projeto: Projeto) -> None:
    """Um projeto criado antes da 2.1 não tem a trava no `.gitignore` (que o `mapa novo` gerou): acrescenta."""
    ignorar = projeto.raiz / ".gitignore"
    try:
        texto = ignorar.read_text(encoding="utf-8")
    except OSError:
        return
    if ARQUIVO not in texto.split():
        ignorar.write_text(texto.rstrip("\n") + f"\n{ARQUIVO}\n", encoding="utf-8")
