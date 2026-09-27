"""Aplicação FastAPI do painel local.

Rotas:
- `/`             interface compilada (`web/estatico/`); sem build, uma página explica como gerá-lo
- `/dados/…`      arquivos do contrato (de `saida/dados/` do projeto, ou do exemplo sintético)
- `/api/…`        API do painel: as etapas como jobs com progresso ao vivo (`rotas_jobs.py`, `jobs.py`) e a
                  codificação da amostra de validação (`validacao.py`); só com projeto aberto

O `manifesto.json` é servido dinamicamente para marcar `api: true` no painel. No site
publicado (`mapa publicar`) ele vai com `api: false` e a interface fica só de leitura.

A API só responde a pedidos feitos a um endereço local (`Host` 127.0.0.1 ou localhost). Assim uma página de outro
site que faça o próprio domínio apontar para 127.0.0.1 (*DNS rebinding*) não lê as codificações nem as métricas;
as rotas de escrita conferem também o `Origin` (`servidor/validacao.py`).
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from importlib import resources
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from mapa_da_ciencia import __version__
from mapa_da_ciencia.contrato.exportar import manifesto_do_projeto
from mapa_da_ciencia.manifesto import status_das_etapas
from mapa_da_ciencia.projeto import Projeto
from mapa_da_ciencia.servidor.origem import HOSTS_LOCAIS

_SEM_BUILD = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><title>mapa-da-ciencia</title>
<style>body{{font-family:system-ui,sans-serif;background:#0A0E1F;color:#ECEAF4;max-width:40rem;margin:4rem auto;
padding:0 1rem;line-height:1.5}}code{{background:#111733;padding:.1rem .3rem;border-radius:4px}}
a{{color:#FFB547}}</style></head><body>
<h1>A interface ainda não foi compilada</h1>
<p>O servidor está no ar (versão {versao}), mas o pacote não traz a interface web. Isso é normal quando se
roda a partir do código-fonte. Encerre este painel (Ctrl+C no terminal) e compile a interface uma vez, com o
Node.js 22.18 ou mais recente:</p>
<pre><code>cd frontend
npm ci
npm run empacotar
cd ..</code></pre>
<p>Depois, abra o painel de novo. Para não precisar compilar, instale o <em>wheel</em> de uma
<a href="https://github.com/felipelmc/mapa-da-ciencia/releases">release</a>, que já traz a interface.</p>
<p>Os dados continuam disponíveis em <a href="dados/manifesto.json">dados/manifesto.json</a>.</p>
</body></html>"""


def pasta_estatico() -> Path:
    return Path(str(resources.files("mapa_da_ciencia.web").joinpath("estatico")))


def criar_app(
    *,
    pasta_dados: Path,
    projeto: Projeto | None = None,
    api: bool = True,
    estatico: Path | None = None,
    etapas: dict | None = None,
    so_local: bool = True,
) -> FastAPI:
    """A aplicação do painel. `etapas` troca o registro das etapas que rodam como jobs (os testes usam etapas
    falsas); `so_local=False` aceita pedidos de outro endereço (só no Colab, pelo *proxy*; ver `origem.py`)."""
    jobs = None
    if projeto is not None and api:
        from mapa_da_ciencia.servidor.etapas import ETAPAS_DO_PAINEL
        from mapa_da_ciencia.servidor.jobs import Jobs

        jobs = Jobs(projeto, etapas if etapas is not None else ETAPAS_DO_PAINEL)

    @asynccontextmanager
    async def ciclo(_: FastAPI):
        yield
        if jobs is not None:
            jobs.fechar()

    app = FastAPI(title="mapa-da-ciencia", version=__version__, docs_url="/api/docs", redoc_url=None, lifespan=ciclo)
    app.state.jobs = jobs
    app.state.so_local = so_local
    estatico = estatico if estatico is not None else pasta_estatico()

    @app.middleware("http")
    async def so_desta_maquina(request: Request, seguir):
        if so_local and request.url.path.startswith("/api/") and request.url.hostname not in HOSTS_LOCAIS:
            return JSONResponse({"detail": "O painel só responde a pedidos feitos desta máquina."}, status_code=403)
        return await seguir(request)

    @app.get("/api/saude")
    def saude() -> dict:
        """Confere se o painel está no ar: a versão do pacote e o nome do projeto aberto (ou `null`, no exemplo)."""
        return {"ok": True, "versao": __version__, "projeto": projeto.config.nome if projeto else None}

    @app.get("/api/projeto")
    def info_projeto() -> dict:
        """O projeto aberto: nome, título, pasta e a última execução de cada etapa."""
        if projeto is None:
            raise HTTPException(404, "O painel está mostrando o exemplo, sem projeto aberto.")
        etapas = {
            etapa: (None if m is None else {"fim": m["fim"], "duracao_s": m["duracao_s"], "contagens": m["contagens"]})
            for etapa, m in status_das_etapas(projeto).items()
        }
        return {
            "nome": projeto.config.nome,
            "titulo": projeto.config.titulo,
            "raiz": str(projeto.raiz),
            "etapas": etapas,
        }

    if projeto is not None and jobs is not None:
        from mapa_da_ciencia.servidor.etapas import OPCOES
        from mapa_da_ciencia.servidor.rotas_jobs import rotas_jobs
        from mapa_da_ciencia.servidor.rotas_projeto import rotas_projeto
        from mapa_da_ciencia.servidor.validacao import rotas_validacao

        app.include_router(rotas_validacao(projeto))
        app.include_router(rotas_jobs(jobs, OPCOES if etapas is None else {}))
        app.include_router(rotas_projeto(projeto, jobs))

    @app.get("/dados/manifesto.json")
    def manifesto() -> JSONResponse:
        """O manifesto do contrato, com `api: true` no painel (a interface usa isso para mostrar o que só funciona
        localmente); sem exportação ainda, um manifesto mínimo do projeto."""
        arq = pasta_dados / "manifesto.json"
        if arq.exists():
            dados = json.loads(arq.read_text(encoding="utf-8"))
        elif projeto is not None:
            dados = manifesto_do_projeto(projeto, api=api).model_dump(mode="json")
        else:
            raise HTTPException(404, "manifesto.json não encontrado")
        dados["api"] = api
        return JSONResponse(dados, headers={"Cache-Control": "no-store"})

    pasta_dados.mkdir(parents=True, exist_ok=True)
    app.mount("/dados", StaticFiles(directory=pasta_dados), name="dados")

    if (estatico / "index.html").exists():
        app.mount("/", StaticFiles(directory=estatico, html=True), name="estatico")
    else:

        @app.get("/", response_class=HTMLResponse, include_in_schema=False)
        def sem_build() -> str:
            return _SEM_BUILD.format(versao=__version__)

    return app
