"""Aplicação FastAPI do painel local.

Rotas:
- `/`             interface compilada (`web/estatico/`); sem build, uma página explica como gerá-lo
- `/dados/…`      arquivos do contrato (de `saida/dados/` do projeto, ou do exemplo sintético)
- `/api/…`        API do painel (cresce a cada marco: etapas, codificação, modelos); a codificação da amostra
                  de validação está em `servidor/validacao.py`

O `manifesto.json` é servido dinamicamente para marcar `api: true` no painel. No site
publicado (`mapa publicar`) ele vai com `api: false` e a interface fica só de leitura.
"""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from mapa_da_ciencia import __version__
from mapa_da_ciencia.contrato.exportar import manifesto_do_projeto
from mapa_da_ciencia.manifesto import status_das_etapas
from mapa_da_ciencia.projeto import Projeto

_SEM_BUILD = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><title>mapa-da-ciencia</title>
<style>body{{font-family:system-ui,sans-serif;background:#0A0E1F;color:#ECEAF4;max-width:40rem;margin:4rem auto;
padding:0 1rem;line-height:1.5}}code{{background:#111733;padding:.1rem .3rem;border-radius:4px}}
a{{color:#FFB547}}</style></head><body>
<h1>A interface ainda não foi compilada</h1>
<p>O servidor está no ar (versão {versao}), mas o pacote não traz a interface web. Isso é normal quando se
roda a partir do código-fonte. Para compilar:</p>
<pre><code>cd frontend
npm ci
npm run build
npm run empacotar</code></pre>
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
) -> FastAPI:
    app = FastAPI(title="mapa-da-ciencia", version=__version__, docs_url="/api/docs", redoc_url=None)
    estatico = estatico if estatico is not None else pasta_estatico()

    @app.get("/api/saude")
    def saude() -> dict:
        return {"ok": True, "versao": __version__, "projeto": projeto.config.nome if projeto else None}

    @app.get("/api/projeto")
    def info_projeto() -> dict:
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

    if projeto is not None and api:
        from mapa_da_ciencia.servidor.validacao import rotas_validacao

        app.include_router(rotas_validacao(projeto))

    @app.get("/dados/manifesto.json")
    def manifesto() -> JSONResponse:
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

        @app.get("/", response_class=HTMLResponse)
        def sem_build() -> str:
            return _SEM_BUILD.format(versao=__version__)

    return app
