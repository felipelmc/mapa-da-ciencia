"""Uma etapa por vez em cada projeto, entre a linha de comando, o notebook e o painel.

Duas etapas ao mesmo tempo no mesmo projeto se atropelam: uma coleta pelo terminal regrava o corpus enquanto o
painel calcula os tópicos, e as duas exportam `saida/dados/` por cima uma da outra. O painel já roda uma etapa por
vez (`servidor/jobs.py`) e trava o projeto contra um segundo painel (`servidor/trava.py`), mas a linha de comando e o
notebook passavam por cima dele (ADR 0013).

Cada função que escreve em `dados/` ou `saida/`, ou que carrega um modelo, roda dentro de `uma_etapa_por_vez`
(o decorador `etapa`): um `flock` num arquivo `.etapa.lock` na pasta do projeto, com o PID, a etapa, a origem
(`painel` ou `terminal`, que inclui o notebook) e a hora. Uma segunda etapa, de outro processo ou de outra thread,
não começa: sai com `EtapaEmAndamento`, que diz quem roda e desde quando. Na mesma thread, a trava é reentrante (a
votação do júri chama a classificação; `mapa importar`, a coleta). O sistema solta a trava se o processo morrer.

`quem_roda` lê o dono (o painel consulta antes de começar um job e a cada poucos segundos): um arquivo vazio, ou com o
PID de um processo que já não existe, quer dizer livre; com o PID de um processo vivo, uma sonda confere se a trava
está mesmo presa (o PID pode ser de outro processo, depois de uma queda). Sem `fcntl` (Windows), não há trava.
"""

from __future__ import annotations

import functools
import json
import os
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import IO, Any, Literal, ParamSpec, TypeVar

from .config import ErroConfig
from .projeto import Projeto

ARQUIVO = ".etapa.lock"
Origem = Literal["painel", "terminal"]
_local = threading.local()

P = ParamSpec("P")
R = TypeVar("R")


class EtapaEmAndamento(ErroConfig):
    """Outra etapa está rodando neste projeto."""


@contextmanager
def origem(nome: Origem) -> Iterator[None]:
    """Marca as etapas desta thread com a origem (o painel marca as dos jobs; o resto é `terminal`)."""
    anterior = getattr(_local, "origem", "terminal")
    _local.origem = nome
    try:
        yield
    finally:
        _local.origem = anterior


def _travas() -> dict[str, list[Any]]:
    if not hasattr(_local, "travas"):
        _local.travas = {}
    return _local.travas


def _ler(arquivo: IO[str]) -> dict[str, Any]:
    arquivo.seek(0)
    try:
        return json.loads(arquivo.read() or "{}")
    except json.JSONDecodeError:
        return {}


def _vivo(pid: Any) -> bool:
    if not isinstance(pid, int):
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:  # existe, de outro usuário
        return True
    return True


def mensagem(projeto: Projeto, dono: dict[str, Any]) -> str:
    """A frase que diz quem roda a etapa: pelo painel (com o endereço dele) ou em outro terminal ou notebook."""
    etapa = dono.get("etapa", "uma etapa")
    try:
        desde = f" desde as {datetime.fromisoformat(dono['inicio']):%H:%M}"
    except (KeyError, TypeError, ValueError):
        desde = ""
    if dono.get("origem") == "painel":
        from .servidor.trava import ARQUIVO as ARQUIVO_PAINEL

        try:
            porta = json.loads((projeto.raiz / ARQUIVO_PAINEL).read_text(encoding="utf-8")).get("porta")
        except (OSError, json.JSONDecodeError):
            porta = None
        onde = f" (http://127.0.0.1:{porta}/)" if porta else ""
        return (
            f"A etapa {etapa} está rodando pelo painel{onde}{desde}. Espere terminar, ou cancele no painel, e rode "
            "de novo: duas etapas ao mesmo tempo no mesmo projeto estragam os dados uma da outra."
        )
    return (
        f"A etapa {etapa} está rodando em outro terminal ou notebook (processo {dono.get('pid', '?')}){desde}. "
        "Espere terminar e rode de novo: duas etapas ao mesmo tempo no mesmo projeto estragam os dados uma da outra."
    )


@contextmanager
def uma_etapa_por_vez(projeto: Projeto, etapa: str) -> Iterator[None]:
    """Roda o bloco com o projeto travado para a `etapa`, ou sai com `EtapaEmAndamento` se outra estiver rodando."""
    try:
        import fcntl
    except ImportError:  # Windows: sem trava
        yield
        return
    chave = str(projeto.raiz.resolve())
    travas = _travas()
    if chave in travas:  # reentrada na mesma thread
        travas[chave][1] += 1
        try:
            yield
        finally:
            travas[chave][1] -= 1
        return
    arquivo = open(projeto.raiz / ARQUIVO, "a+", encoding="utf-8")  # noqa: SIM115 (fica aberto com a etapa)
    try:
        fcntl.flock(arquivo, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        dono = _ler(arquivo)
        arquivo.close()
        raise EtapaEmAndamento(mensagem(projeto, dono)) from None
    arquivo.seek(0)
    arquivo.truncate()
    dono = {
        "pid": os.getpid(),
        "etapa": etapa,
        "origem": getattr(_local, "origem", "terminal"),
        "inicio": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    arquivo.write(json.dumps(dono))
    arquivo.flush()
    _fora_do_git(projeto)
    travas[chave] = [arquivo, 1]
    try:
        yield
    finally:
        del travas[chave]
        arquivo.seek(0)
        arquivo.truncate()
        arquivo.flush()
        fcntl.flock(arquivo, fcntl.LOCK_UN)
        arquivo.close()


def etapa(nome: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorador: a função (que recebe o projeto como primeiro argumento) roda com o projeto travado."""

    def decorar(funcao: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(funcao)
        def travada(*args: P.args, **kwargs: P.kwargs) -> R:
            projeto = args[0] if args else kwargs["projeto"]
            with uma_etapa_por_vez(projeto, nome):  # type: ignore[arg-type]
                return funcao(*args, **kwargs)

        travada.__etapa__ = nome  # type: ignore[attr-defined]
        return travada

    return decorar


def quem_roda(projeto: Projeto) -> dict[str, Any] | None:
    """O dono da trava (`pid`, `etapa`, `origem`, `inicio`), ou `None` se nenhuma etapa roda.

    Lê o arquivo sem travar. Só quando ele aponta para um processo vivo, confere a trava com uma sonda (`LOCK_SH`
    sem esperar): um `kill -9` deixa o PID no arquivo, e o sistema pode dar esse número a outro processo."""
    try:
        texto = (projeto.raiz / ARQUIVO).read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        dono = json.loads(texto) if texto.strip() else {}
    except json.JSONDecodeError:
        return None
    if not dono or not _vivo(dono.get("pid")):
        return None
    try:
        import fcntl
    except ImportError:  # Windows: sem trava, vale o arquivo
        return dono
    try:
        arquivo = open(projeto.raiz / ARQUIVO, encoding="utf-8")  # noqa: SIM115 (fechado no finally)
    except OSError:
        return dono
    try:
        fcntl.flock(arquivo, fcntl.LOCK_SH | fcntl.LOCK_NB)
    except BlockingIOError:
        return dono
    else:
        fcntl.flock(arquivo, fcntl.LOCK_UN)
        return None  # o arquivo ficou de uma etapa que caiu
    finally:
        arquivo.close()


def _fora_do_git(projeto: Projeto) -> None:
    """Um projeto criado antes da 2.3 não tem a trava no `.gitignore` (que o `mapa novo` gerou): acrescenta."""
    ignorar = projeto.raiz / ".gitignore"
    try:
        texto = ignorar.read_text(encoding="utf-8")
    except OSError:
        return
    if ARQUIVO not in texto.split():
        ignorar.write_text(texto.rstrip("\n") + f"\n{ARQUIVO}\n", encoding="utf-8")
