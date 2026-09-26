"""Protocolo de progresso das etapas: a CLI mostra barras (Rich); o painel (M6) vai transmitir por SSE."""

from __future__ import annotations

from typing import Protocol

from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TaskID, TextColumn, TimeRemainingColumn


class Progresso(Protocol):
    def etapa(self, nome: str, total: int | None = None) -> None: ...

    def avancar(self, n: int = 1) -> None: ...

    def mensagem(self, texto: str) -> None: ...

    def fim(self) -> None: ...


class ProgressoNulo:
    """Não mostra nada (testes, notebooks sem saída, painel antes do M6)."""

    def etapa(self, nome: str, total: int | None = None) -> None:
        pass

    def avancar(self, n: int = 1) -> None:
        pass

    def mensagem(self, texto: str) -> None:
        pass

    def fim(self) -> None:
        pass


class ProgressoRich:
    """Uma barra por etapa no terminal. Sem terminal interativo, só as mensagens aparecem."""

    def __init__(self, console: Console) -> None:
        self.console = console
        self._barras = Progress(
            TextColumn("{task.description:<28}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeRemainingColumn(),
            console=console,
            disable=not console.is_terminal,
        )
        self._atual: TaskID | None = None
        self._iniciado = False

    def etapa(self, nome: str, total: int | None = None) -> None:
        if not self._iniciado:
            self._barras.start()
            self._iniciado = True
        if self._atual is not None:
            self._barras.update(self._atual, completed=self._barras.tasks[self._atual].total or 0)
        self._atual = self._barras.add_task(nome, total=total)

    def avancar(self, n: int = 1) -> None:
        if self._atual is not None:
            self._barras.advance(self._atual, n)

    def mensagem(self, texto: str) -> None:
        self._barras.console.print(texto)

    def fim(self) -> None:
        if self._iniciado:
            if self._atual is not None:
                self._barras.update(self._atual, completed=self._barras.tasks[self._atual].total or 0)
            self._barras.stop()
            self._iniciado = False
