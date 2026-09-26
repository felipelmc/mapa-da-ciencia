"""Rotas das etapas e dos jobs do painel.

- `POST /api/etapas/{etapa}`: começa uma etapa (coleta, tópicos, geografia, classificação) com as opções no corpo;
  409 se já houver uma rodando.
- `GET /api/jobs` e `GET /api/jobs/{id}`: os jobs recentes e o estado de um.
- `GET /api/jobs/{id}/eventos`: o progresso ao vivo, em Server-Sent Events. Cada evento leva `id:` (a sequência);
  quem reconecta manda `Last-Event-ID` (ou `?desde=`) e recebe só o que perdeu. A conexão fecha no evento `fim`, e
  um comentário a cada 15 s a mantém aberta.
- `DELETE /api/jobs/{id}`: pede para cancelar.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from .jobs import Jobs, Ocupado
from .origem import conferir_origem

BATIMENTO = 15.0


def _evento_sse(seq: int, tipo: str, dados: dict[str, Any]) -> str:
    return f"id: {seq}\nevent: {tipo}\ndata: {json.dumps(dados, ensure_ascii=False)}\n\n"


def rotas_jobs(jobs: Jobs, opcoes: dict[str, type] | None = None) -> APIRouter:
    rotas = APIRouter(prefix="/api", tags=["etapas"])
    opcoes = opcoes or {}

    def _job(id_: str):
        job = jobs.obter(id_)
        if job is None:
            raise HTTPException(404, f"Job {id_} não encontrado.")
        return job

    @rotas.post("/etapas/{etapa}", status_code=202, dependencies=[Depends(conferir_origem)])
    def iniciar(etapa: str, corpo: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:  # noqa: B008
        """Começa uma etapa do pipeline em segundo plano e devolve o job."""
        if etapa not in jobs.etapas:
            raise HTTPException(404, f"Etapa desconhecida: {etapa}. As etapas são: {', '.join(jobs.etapas)}.")
        if etapa in opcoes:
            try:
                corpo = opcoes[etapa](**corpo).model_dump(exclude_defaults=True)
            except ValidationError as e:
                raise HTTPException(422, {"problemas": [err["msg"] for err in e.errors()]}) from e
        try:
            return dataclasses.asdict(jobs.iniciar(etapa, corpo))
        except Ocupado as e:
            raise HTTPException(409, {"mensagem": str(e), "job": dataclasses.asdict(e.job)}) from e

    @rotas.get("/jobs")
    def listar() -> list[dict[str, Any]]:
        """Os jobs mais recentes, do mais novo ao mais antigo."""
        return [dataclasses.asdict(j) for j in jobs.listar()]

    @rotas.get("/jobs/{job}")
    def obter(job: str) -> dict[str, Any]:
        """O estado de um job: etapa, opções, estado, início, fim, resumo e erro."""
        return dataclasses.asdict(_job(job))

    @rotas.delete("/jobs/{job}", dependencies=[Depends(conferir_origem)])
    def cancelar(job: str) -> dict[str, Any]:
        """Pede para o job parar; ele para na próxima atualização de progresso."""
        _job(job)
        return dataclasses.asdict(jobs.cancelar(job))

    @rotas.get("/jobs/{job}/eventos")
    async def eventos(
        job: str,
        request: Request,
        desde: int = 0,
        last_event_id: str | None = Header(None),
    ) -> StreamingResponse:
        """O progresso do job em Server-Sent Events, a partir do evento seguinte ao último recebido."""
        _job(job)
        inicio = int(last_event_id) if last_event_id and last_event_id.isdigit() else desde

        async def fluxo() -> AsyncIterator[str]:
            visto = inicio
            yield "retry: 1000\n\n"
            while True:
                novos = await asyncio.to_thread(jobs.esperar, job, visto, BATIMENTO)
                if not novos:
                    if await request.is_disconnected():
                        return
                    yield ": batimento\n\n"
                    continue
                for e in novos:
                    visto = e.seq
                    yield _evento_sse(e.seq, e.tipo, e.dados)
                    if e.tipo == "fim":
                        return

        return StreamingResponse(
            fluxo(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    return rotas
