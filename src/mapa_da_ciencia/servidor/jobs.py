"""Jobs do painel: as etapas do pipeline rodando em segundo plano, com o progresso guardado como eventos.

- Um job por vez (um `ThreadPoolExecutor(1)`): pedir outra etapa com um job na fila ou rodando dá `Ocupado`.
- Cada job fica na tabela `jobs` do `estado.sqlite`, e o progresso na tabela `eventos`, com um número de sequência.
  Quem acompanha pela rede (SSE) pode cair e voltar pedindo só os eventos depois do último que viu.
- Cancelar marca um pedido de parada; o `ProgressoSSE` levanta `Cancelado` na próxima chamada. As etapas guardam o
  que já fizeram (cache, brutos), então parar no meio é seguro, como um ++ctrl+c++ na CLI.
- Um job que ficou "rodando" numa sessão anterior (o painel foi fechado no meio) vira "falhou" ao abrir.
"""

from __future__ import annotations

import dataclasses
import json
import sqlite3
import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from ..progresso import Progresso
from ..projeto import Projeto

EstadoJob = Literal["na_fila", "rodando", "concluido", "falhou", "cancelado"]
ATIVOS = ("na_fila", "rodando")
INTERVALO_AVANCO = 0.25  # segundos entre dois eventos de avanço da mesma etapa

Etapa = Callable[[Projeto, dict[str, Any], Progresso], Any]

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id      TEXT PRIMARY KEY,
    etapa   TEXT NOT NULL,
    opcoes  TEXT NOT NULL,
    estado  TEXT NOT NULL,
    criado  TEXT NOT NULL,
    inicio  TEXT,
    fim     TEXT,
    resumo  TEXT,
    erro    TEXT
);
CREATE TABLE IF NOT EXISTS eventos (
    job   TEXT NOT NULL,
    seq   INTEGER NOT NULL,
    tipo  TEXT NOT NULL,
    dados TEXT NOT NULL,
    PRIMARY KEY (job, seq)
);
"""


class Cancelado(BaseException):  # como KeyboardInterrupt: atravessa os `except Exception` das etapas
    """Pedido de parada de um job, levantado pelo progresso."""


class Ocupado(Exception):
    """Já há um job na fila ou rodando."""

    def __init__(self, job: Job) -> None:
        super().__init__(f"Já há uma etapa rodando ({job.etapa}). Espere terminar ou cancele.")
        self.job = job


@dataclass
class Job:
    id: str
    etapa: str
    opcoes: dict[str, Any]
    estado: EstadoJob
    criado: str
    inicio: str | None = None
    fim: str | None = None
    resumo: dict[str, Any] | None = None
    erro: str | None = None


@dataclass
class Evento:
    seq: int
    tipo: str  # etapa | avanco | mensagem | resumo | erro | fim
    dados: dict[str, Any]


def _agora() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def resumo_como_dict(resumo: Any) -> dict[str, Any] | None:
    """O resumo que uma etapa devolveu, em JSON: os campos (se for um dataclass) e a frase de `str()`."""
    if resumo is None:
        return None
    campos = dataclasses.asdict(resumo) if dataclasses.is_dataclass(resumo) else {}
    campos = json.loads(json.dumps(campos, ensure_ascii=False, default=str))
    return {"frase": str(resumo), **campos}


class Jobs:
    def __init__(self, projeto: Projeto, etapas: dict[str, Etapa]) -> None:
        self.projeto = projeto
        self.etapas = etapas
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mapa-job")
        self._trava = threading.Lock()
        self._novidade = threading.Condition()
        self._parar: dict[str, threading.Event] = {}
        with self._conectar() as con:
            con.executescript(_ESQUEMA)
            con.execute(
                "UPDATE jobs SET estado = 'falhou', erro = 'interrompido: o painel foi fechado no meio da etapa', "
                "fim = ? WHERE estado IN ('na_fila', 'rodando')",
                (_agora(),),
            )

    # ---------------------------------------------------------------- banco
    @property
    def _arquivo(self) -> Path:
        return self.projeto.estado

    def _conectar(self) -> sqlite3.Connection:
        con = sqlite3.connect(self._arquivo, timeout=30)
        con.execute("PRAGMA journal_mode=WAL")
        return con

    def _linha(self, linha: tuple) -> Job:
        id_, etapa, opcoes, estado, criado, inicio, fim, resumo, erro = linha
        return Job(id_, etapa, json.loads(opcoes), estado, criado, inicio, fim, json.loads(resumo or "null"), erro)

    def obter(self, id_: str) -> Job | None:
        with self._conectar() as con:
            linha = con.execute("SELECT * FROM jobs WHERE id = ?", (id_,)).fetchone()
        return self._linha(linha) if linha else None

    def listar(self, limite: int = 20) -> list[Job]:
        with self._conectar() as con:
            linhas = con.execute("SELECT * FROM jobs ORDER BY criado DESC, rowid DESC LIMIT ?", (limite,)).fetchall()
        return [self._linha(linha) for linha in linhas]

    def ativo(self) -> Job | None:
        with self._conectar() as con:
            linha = con.execute("SELECT * FROM jobs WHERE estado IN ('na_fila', 'rodando') LIMIT 1").fetchone()
        return self._linha(linha) if linha else None

    def _mudar(self, id_: str, **campos: Any) -> None:
        pares = ", ".join(f"{k} = ?" for k in campos)
        valores = [json.dumps(v, ensure_ascii=False) if k == "resumo" else v for k, v in campos.items()]
        with self._trava, self._conectar() as con:
            con.execute(f"UPDATE jobs SET {pares} WHERE id = ?", (*valores, id_))

    # ---------------------------------------------------------------- eventos
    def emitir(self, id_: str, tipo: str, dados: dict[str, Any] | None = None) -> int:
        with self._trava, self._conectar() as con:
            seq = con.execute("SELECT coalesce(max(seq), 0) + 1 FROM eventos WHERE job = ?", (id_,)).fetchone()[0]
            con.execute(
                "INSERT INTO eventos (job, seq, tipo, dados) VALUES (?, ?, ?, ?)",
                (id_, seq, tipo, json.dumps(dados or {}, ensure_ascii=False)),
            )
        with self._novidade:
            self._novidade.notify_all()
        return seq

    def eventos(self, id_: str, desde: int = 0) -> list[Evento]:
        with self._conectar() as con:
            linhas = con.execute(
                "SELECT seq, tipo, dados FROM eventos WHERE job = ? AND seq > ? ORDER BY seq", (id_, desde)
            ).fetchall()
        return [Evento(seq, tipo, json.loads(dados)) for seq, tipo, dados in linhas]

    def esperar(self, id_: str, desde: int, tempo: float) -> list[Evento]:
        """Os eventos depois de `desde`; sem nenhum, espera até `tempo` segundos por um novo."""
        novos = self.eventos(id_, desde)
        if novos:
            return novos
        with self._novidade:
            self._novidade.wait(tempo)
        return self.eventos(id_, desde)

    # ---------------------------------------------------------------- execução
    def iniciar(self, etapa: str, opcoes: dict[str, Any] | None = None) -> Job:
        if etapa not in self.etapas:
            raise KeyError(etapa)
        with self._trava:
            ativo = self.ativo()
            if ativo is not None:
                raise Ocupado(ativo)
            job = Job(uuid.uuid4().hex[:12], etapa, opcoes or {}, "na_fila", _agora())
            with self._conectar() as con:
                con.execute(
                    "INSERT INTO jobs (id, etapa, opcoes, estado, criado) VALUES (?, ?, ?, ?, ?)",
                    (job.id, etapa, json.dumps(job.opcoes, ensure_ascii=False), job.estado, job.criado),
                )
            self._parar[job.id] = threading.Event()
        self._executor.submit(self._rodar, job.id)
        return job

    def cancelar(self, id_: str) -> Job | None:
        job = self.obter(id_)
        if job is None or job.estado not in ATIVOS:
            return job
        self._parar.setdefault(id_, threading.Event()).set()
        if job.estado == "na_fila":
            self._mudar(id_, estado="cancelado", fim=_agora())
            self.emitir(id_, "fim", {"estado": "cancelado"})
        return self.obter(id_)

    def _rodar(self, id_: str) -> None:
        job = self.obter(id_)
        parar = self._parar.setdefault(id_, threading.Event())
        if job is None or job.estado != "na_fila" or parar.is_set():
            return
        self._mudar(id_, estado="rodando", inicio=_agora())
        self.emitir(id_, "estado", {"estado": "rodando"})
        progresso = ProgressoSSE(self, id_, parar)
        try:
            resumo = resumo_como_dict(self.etapas[job.etapa](self.projeto, job.opcoes, progresso))
        except Cancelado:
            progresso.fim()
            self._mudar(id_, estado="cancelado", fim=_agora())
            self.emitir(id_, "fim", {"estado": "cancelado"})
        except BaseException as e:  # o erro vai para o job, e o servidor continua de pé
            progresso.fim()
            mensagem = str(e) or type(e).__name__
            self._mudar(id_, estado="falhou", fim=_agora(), erro=mensagem)
            self.emitir(id_, "erro", {"mensagem": mensagem})
            self.emitir(id_, "fim", {"estado": "falhou"})
        else:
            progresso.fim()
            self._mudar(id_, estado="concluido", fim=_agora(), resumo=resumo)
            self.emitir(id_, "resumo", resumo or {})
            self.emitir(id_, "fim", {"estado": "concluido"})
        finally:
            self._parar.pop(id_, None)

    def fechar(self) -> None:
        for evento in self._parar.values():
            evento.set()
        self._executor.shutdown(wait=True, cancel_futures=True)


class ProgressoSSE:
    """O protocolo `Progresso` gravando eventos do job. Os avanços são agrupados (no máximo um evento a cada
    `INTERVALO_AVANCO` segundos por etapa); a cada chamada, confere se pediram para parar."""

    def __init__(self, jobs: Jobs, job: str, parar: threading.Event) -> None:
        self.jobs = jobs
        self.job = job
        self.parar = parar
        self._nome: str | None = None
        self._total: int | None = None
        self._feito = 0
        self._ultimo = 0.0
        self._pendente = False

    def _conferir(self) -> None:
        if self.parar.is_set():
            raise Cancelado

    def _avanco(self) -> None:
        if self._nome is not None and self._pendente:
            self.jobs.emitir(self.job, "avanco", {"etapa": self._nome, "feito": self._feito, "total": self._total})
            self._ultimo = time.monotonic()
            self._pendente = False

    def etapa(self, nome: str, total: int | None = None) -> None:
        self._conferir()
        self._avanco()
        self._nome, self._total, self._feito = nome, total, 0
        self.jobs.emitir(self.job, "etapa", {"nome": nome, "total": total})

    def avancar(self, n: int = 1) -> None:
        self._conferir()
        self._feito += n
        self._pendente = True
        if time.monotonic() - self._ultimo >= INTERVALO_AVANCO or (self._total and self._feito >= self._total):
            self._avanco()

    def mensagem(self, texto: str) -> None:
        self._conferir()
        self.jobs.emitir(self.job, "mensagem", {"texto": texto})

    def fim(self) -> None:
        self._avanco()
