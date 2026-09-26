"""Cache das respostas dos modelos de linguagem, no `estado.sqlite` do projeto.

Uma tabela só (`llm_cache`) para todas as tarefas (rótulos dos tópicos no M3, classificação no M5), com a chave
calculada a partir de tudo o que muda a resposta: o texto do pedido, o modelo com o digest e os parâmetros.
Rodar de novo sem mudanças não chama o modelo. Só respostas válidas entram: uma resposta rejeitada (JSON
inválido, rótulo sem acento) não fica guardada como se estivesse certa.

O SQLite fica em modo WAL, que tolera leituras enquanto outra etapa escreve (o painel do M6).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS llm_cache (
    tarefa   TEXT NOT NULL,
    chave    TEXT NOT NULL,
    resposta TEXT NOT NULL,
    modelo   TEXT NOT NULL,
    criado   TEXT NOT NULL,
    PRIMARY KEY (tarefa, chave)
)
"""


def chave_de(*partes: Any) -> str:
    """Chave estável a partir de qualquer combinação de textos, números, listas e dicionários."""
    texto = json.dumps(partes, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


class CacheLLM:
    def __init__(self, caminho: Path) -> None:
        self.caminho = caminho
        self._con = sqlite3.connect(caminho)
        self._con.execute("PRAGMA journal_mode=WAL")
        self._con.execute(_ESQUEMA)
        self._con.commit()

    def obter(self, tarefa: str, chave: str) -> dict | None:
        linha = self._con.execute(
            "SELECT resposta FROM llm_cache WHERE tarefa = ? AND chave = ?", (tarefa, chave)
        ).fetchone()
        return json.loads(linha[0]) if linha else None

    def guardar(self, tarefa: str, chave: str, resposta: dict, modelo: str) -> None:
        self._con.execute(
            "INSERT OR REPLACE INTO llm_cache (tarefa, chave, resposta, modelo, criado) VALUES (?, ?, ?, ?, ?)",
            (tarefa, chave, json.dumps(resposta, ensure_ascii=False), modelo, datetime.now(UTC).isoformat()),
        )
        self._con.commit()

    def contar(self, tarefa: str) -> int:
        return self._con.execute("SELECT count(*) FROM llm_cache WHERE tarefa = ?", (tarefa,)).fetchone()[0]

    def fechar(self) -> None:
        self._con.close()

    def __enter__(self) -> CacheLLM:
        return self

    def __exit__(self, *_: object) -> None:
        self.fechar()
