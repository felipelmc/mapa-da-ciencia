"""Rotas da codificação da amostra de validação, no painel local.

- `GET /api/validacao/fila?codificador=NOME`: a amostra na ordem da fila desse codificador (embaralhada com uma
  semente tirada do nome, a mesma em qualquer sessão), com título, resumo, o codebook e as respostas que ele já deu;
  nunca as respostas de um modelo (a codificação é cega).
- `PUT /api/validacao/codificacoes/{doc}`: grava as respostas de um documento. Com `completa: false` (o
  salvamento automático), as variáveis ainda não respondidas não são erro.
- `GET /api/validacao/metricas`: a concordância calculada agora, no formato de `validacao.json`, com as
  divergências de todos os codificadores (no contrato publicado, só as de codificadores de referência).

Toda a API só responde a um `Host` local (`servidor/app.py`); as rotas de escrita conferem também o `Origin`,
quando existe. Assim uma página aberta em outro site não consegue ler as codificações nem gravar no projeto pelo
navegador.
"""

from __future__ import annotations

import hashlib
import random
from typing import Any
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from mapa_da_ciencia.config import ErroConfig
from mapa_da_ciencia.projeto import Projeto

HOSTS_LOCAIS = {"127.0.0.1", "localhost", "::1", "[::1]"}


def conferir_origem(request: Request) -> None:
    host = request.url.hostname
    origem = request.headers.get("origin")
    if host not in HOSTS_LOCAIS or (origem is not None and urlsplit(origem).hostname not in HOSTS_LOCAIS):
        raise HTTPException(403, "Gravação recusada: o painel só aceita escrita a partir desta máquina.")


class RespostaVariavel(BaseModel):
    valor: Any = None
    evidencia: str = ""
    incerto: bool = False
    nota: str = Field("", max_length=2000)


class Codificacao(BaseModel):
    codificador: str
    respostas: dict[str, RespostaVariavel]
    completa: bool = Field(False, description="Exige todas as variáveis (ao confirmar a ficha).")


def semente_do_codificador(nome: str) -> int:
    return int.from_bytes(hashlib.sha256(nome.encode("utf-8")).digest()[:8], "big")


def rotas_validacao(projeto: Projeto) -> APIRouter:
    from mapa_da_ciencia.classificacao.resultado import valor_do_texto
    from mapa_da_ciencia.contrato.classificacao import codebook_contrato, validacao_contrato
    from mapa_da_ciencia.validacao import amostra as va

    rotas = APIRouter(prefix="/api/validacao", tags=["validação"])

    def _amostra() -> va.Amostra:
        a = va.ler(projeto)
        if a is None:
            raise HTTPException(404, "O projeto ainda não tem amostra de validação. Rode `mapa validar amostra`.")
        return a

    def _nome(codificador: str) -> str:
        try:
            return va.nome_valido(codificador)
        except ErroConfig as e:
            raise HTTPException(400, str(e)) from e

    @rotas.get("/fila")
    def fila(codificador: str) -> dict[str, Any]:
        """A amostra na ordem da fila do codificador, com as respostas que ele já deu."""
        nome = _nome(codificador)
        a = _amostra()
        cb = projeto.codebook
        tipos = {v.id: v.tipo for v in cb.variaveis}
        textos = {t.doc: t for t in va.textos_do_projeto(projeto)}
        dadas: dict[str, dict[str, Any]] = {}
        for c in va.codificacoes(projeto, nome):
            if c["variavel"] in tipos:
                dadas.setdefault(c["doc"], {})[c["variavel"]] = {
                    "valor": valor_do_texto(c["valor"], tipos[c["variavel"]]),
                    "evidencia": c["evidencia"],
                    "incerto": bool(c["incerto"]),
                    "nota": c["nota"],
                }
        ordem = [d for d in a.docs if d in textos]
        random.Random(semente_do_codificador(nome)).shuffle(ordem)
        return {
            "codificador": nome,
            "tipo": va.codificadores(projeto).get(nome),
            "amostra": {"n": len(a.docs), "estratificar_por": a.estratificar_por, "semente": a.semente},
            "codebook": codebook_contrato(cb).model_dump(mode="json"),
            "fila": [
                {
                    "doc": d,
                    "titulo": textos[d].titulo,
                    "resumo": textos[d].resumo,
                    "idioma": textos[d].idioma,
                    "respostas": dadas.get(d, {}),
                    "completa": set(dadas.get(d, {})) >= set(tipos),
                }
                for d in ordem
            ],
        }

    @rotas.put("/codificacoes/{doc}", dependencies=[Depends(conferir_origem)])
    def gravar(doc: str, corpo: Codificacao) -> dict[str, Any]:
        """Grava as respostas de um codificador para um documento da amostra."""
        nome = _nome(corpo.codificador)
        if doc not in _amostra().docs:
            raise HTTPException(404, f"O documento {doc} não está na amostra de validação.")
        respostas = {v: r.model_dump() for v, r in corpo.respostas.items()}
        problemas = va.salvar(projeto, nome, doc, respostas, completa=corpo.completa)
        if problemas:
            raise HTTPException(422, {"problemas": problemas})
        ja = {c["variavel"] for c in va.codificacoes(projeto, nome) if c["doc"] == doc}
        return {"ok": True, "completa": ja >= {v.id for v in projeto.codebook.variaveis}}

    @rotas.get("/metricas")
    def metricas() -> dict[str, Any]:
        """A concordância agora, com as divergências de todos os codificadores."""
        from mapa_da_ciencia.validacao.metricas import calcular

        _amostra()
        return validacao_contrato(calcular(projeto), so_referencia=False).model_dump(mode="json")

    return rotas
