"""Onde o júri guarda o que produz.

- `dados/juri/<hash do codebook>/`: `votos.parquet` (os votos de cada membro, por rodada), `decisoes.parquet` (a
  decisão de cada documento × variável, com o estágio) e `resumo.json`;
- `dados/classificacao/`: três fontes sintéticas no formato de qualquer modelo (`juri-r1`, `juri` e
  `juri-supervisor`), que a validação lê como mais três participantes;
- `estado.sqlite`: as respostas do supervisor (`juri_supervisor`), que valem enquanto o pedido que as gerou não
  mudar;
- `<projeto>/juri/`: os pedidos ao supervisor externo e as respostas dele, em JSONL (o protocolo por arquivos).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from ..projeto import Projeto

PASTA = "juri"
TAREFA_DELIBERACAO = "juri_deliberacao"
TAREFA_SUPERVISOR = "juri_supervisor"

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS juri_supervisor (
    hash_codebook   TEXT NOT NULL,
    tarefa          TEXT NOT NULL,
    doc             TEXT NOT NULL,
    variavel        TEXT NOT NULL,
    supervisor      TEXT NOT NULL,
    origem          TEXT NOT NULL,
    chave_pedido    TEXT NOT NULL,
    escolha         INTEGER,
    valor           TEXT,
    correto         INTEGER,
    valor_sugerido  TEXT,
    evidencia       TEXT,
    status          TEXT,
    justificativa   TEXT,
    nenhum_adequado INTEGER,
    custo_usd       REAL,
    atualizado      TEXT NOT NULL,
    PRIMARY KEY (hash_codebook, tarefa, doc, variavel, supervisor)
);
"""


def conectar(projeto: Projeto) -> sqlite3.Connection:
    con = sqlite3.connect(projeto.estado)
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(_ESQUEMA)
    con.row_factory = sqlite3.Row
    return con


def pasta_dados(projeto: Projeto, hash_codebook: str) -> Path:
    return projeto.dados / PASTA / hash_codebook


def pasta_pedidos(projeto: Projeto) -> Path:
    return projeto.raiz / PASTA
