"""A amostra de validação e as codificações, guardadas no `estado.sqlite` do projeto.

**Amostra.** Sorteada uma vez (e refeita só a pedido), entre os documentos que a classificação pode ler (com
resumo), estratificada pelo tópico (ou pelo ano, ou pela revista, conforme `validacao.estratificar_por`): cada
estrato recebe uma parte proporcional ao seu tamanho, com pelo menos um documento quando cabe, e o restante vai
pelos maiores restos. Os documentos sem tópico formam um estrato próprio. A semente é `validacao.semente`.

**Codificações.** Uma linha por codificador × documento × variável, com o valor, a evidência (opcional para
pessoas), a marca de incerteza e uma nota. Cada codificador tem um tipo: `humano` ou `referencia` (um anotador que
não é uma pessoa, como o Claude, ver ADR 0012). Os modelos locais não são codificadores: as respostas deles vêm da
classificação.
"""

from __future__ import annotations

import json
import random
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from ..armazenamento import ARQUIVO, ler_documentos
from ..classificacao.codebook import validar
from ..classificacao.executor import Texto, textos_para_classificar
from ..classificacao.resultado import valor_como_texto
from ..config import ErroConfig
from ..projeto import Projeto
from ..texto import contem_email

TipoCodificador = Literal["humano", "referencia"]
PASTA_EXPORTACAO = "validacao"
ARQUIVO_AMOSTRA = "amostra.jsonl"
_NOME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,39}")

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS validacao_amostra (
    doc     TEXT PRIMARY KEY,
    ordem   INTEGER NOT NULL,
    estrato TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS validacao_info (chave TEXT PRIMARY KEY, valor TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS codificadores (nome TEXT PRIMARY KEY, tipo TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS codificacoes (
    codificador TEXT NOT NULL,
    doc         TEXT NOT NULL,
    variavel    TEXT NOT NULL,
    valor       TEXT NOT NULL,
    evidencia   TEXT NOT NULL DEFAULT '',
    incerto     INTEGER NOT NULL DEFAULT 0,
    nota        TEXT NOT NULL DEFAULT '',
    atualizado  TEXT NOT NULL,
    PRIMARY KEY (codificador, doc, variavel)
);
"""


def conectar(projeto: Projeto) -> sqlite3.Connection:
    con = sqlite3.connect(projeto.estado)
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(_ESQUEMA)
    return con


# ---------------------------------------------------------------- amostra
@dataclass
class Amostra:
    docs: list[str]  # na ordem da fila
    estratos: dict[str, str]  # doc → estrato
    estratificar_por: str
    semente: int
    n: int
    sorteada_em: str
    avisos: list[str] = field(default_factory=list)

    def por_estrato(self) -> Counter[str]:
        return Counter(self.estratos.values())


def _estratos(projeto: Projeto, textos: list[Texto], criterio: str) -> tuple[dict[str, str], str, list[str]]:
    """Estrato de cada documento e o critério de fato usado (sem tópicos, cai para a revista)."""
    avisos = []
    docs = {d.id: d for d in ler_documentos(projeto.dados / ARQUIVO)}
    if criterio == "topico":
        from ..topicos.resultado import PASTA, ler_atribuicoes

        if (projeto.dados / PASTA / "atribuicoes.parquet").exists():
            topico = {a["id"]: a["topico"] for a in ler_atribuicoes(projeto.dados / PASTA)}
            return (
                {t.doc: (f"topico {topico[t.doc]}" if topico.get(t.doc, -1) >= 0 else "sem tópico") for t in textos},
                criterio,
                avisos,
            )
        avisos.append("O projeto ainda não tem tópicos: a amostra foi estratificada pela revista.")
        criterio = "revista"
    if criterio == "ano":
        return {t.doc: str(docs[t.doc].ano) for t in textos}, criterio, avisos
    return {t.doc: docs[t.doc].chave_revista for t in textos}, "revista", avisos


def _alocar(tamanhos: dict[str, int], n: int) -> dict[str, int]:
    """Quantos de cada estrato: proporcional, ao menos 1 quando cabe, restante pelos maiores restos."""
    total = sum(tamanhos.values())
    n = min(n, total)
    if not total:
        return {}
    base = {e: 1 if n >= len(tamanhos) else 0 for e in tamanhos}
    resto_n = n - sum(base.values())
    cotas = {e: resto_n * t / total for e, t in tamanhos.items()}
    alocado = {e: min(tamanhos[e], base[e] + int(c)) for e, c in cotas.items()}
    faltam = n - sum(alocado.values())
    for e in sorted(tamanhos, key=lambda e: (-(cotas[e] - int(cotas[e])), e)):
        if faltam <= 0:
            break
        if alocado[e] < tamanhos[e]:
            alocado[e] += 1
            faltam -= 1
    for e in sorted(tamanhos, key=lambda e: -tamanhos[e]):  # estratos pequenos que já esgotaram
        while faltam > 0 and alocado[e] < tamanhos[e]:
            alocado[e] += 1
            faltam -= 1
    return alocado


def nomes_dos_estratos(projeto: Projeto, estratos: list[str]) -> dict[str, str]:
    """Como mostrar cada estrato: `topico 3` vira o rótulo do tópico; os outros ficam como estão."""
    from ..topicos.resultado import PASTA, Resultado

    resultado = Resultado.ler(projeto.dados / PASTA)
    rotulos = {f"topico {t.id}": t.rotulo for t in resultado.topicos} if resultado else {}
    return {e: rotulos.get(e, e) for e in estratos}


def textos_do_projeto(projeto: Projeto) -> list[Texto]:
    cfg = projeto.config
    docs = ler_documentos(projeto.dados / ARQUIVO)
    return textos_para_classificar(docs, [cfg.recorte.idioma_exibicao, cfg.recorte.idioma_analise])[0]


ESTRATOS = {"topico": "tópico", "ano": "ano", "revista": "revista"}


def sortear(projeto: Projeto, *, refazer: bool = False, n: int | None = None) -> Amostra:
    """A amostra do projeto: a guardada, ou uma nova (na primeira vez, ou com `refazer`). `n` troca o tamanho
    de `validacao.n` só neste sorteio."""
    if not refazer and (guardada := ler(projeto)) is not None:
        return guardada
    if not (projeto.dados / ARQUIVO).exists():
        raise ErroConfig("O projeto ainda não tem corpus. Rode `mapa coletar` antes de sortear a amostra.")
    cfg = projeto.config.validacao
    if n is not None:
        if n < 1:
            raise ErroConfig("O tamanho da amostra precisa ser pelo menos 1.")
        cfg = cfg.model_copy(update={"n": n})
    textos = textos_do_projeto(projeto)
    estrato, criterio, avisos = _estratos(projeto, textos, cfg.estratificar_por)
    grupos: dict[str, list[str]] = defaultdict(list)
    for t in textos:
        grupos[estrato[t.doc]].append(t.doc)
    alocacao = _alocar({e: len(d) for e, d in grupos.items()}, cfg.n)
    rng = random.Random(cfg.semente)
    escolhidos = [doc for e in sorted(grupos) for doc in rng.sample(sorted(grupos[e]), alocacao.get(e, 0))]
    rng.shuffle(escolhidos)
    agora = datetime.now(UTC).isoformat(timespec="seconds")
    with conectar(projeto) as con:
        con.execute("DELETE FROM validacao_amostra")
        con.executemany(
            "INSERT INTO validacao_amostra (doc, ordem, estrato) VALUES (?, ?, ?)",
            [(doc, i, estrato[doc]) for i, doc in enumerate(escolhidos)],
        )
        info = {"estratificar_por": criterio, "semente": str(cfg.semente), "n": str(cfg.n), "sorteada_em": agora}
        con.executemany("INSERT OR REPLACE INTO validacao_info (chave, valor) VALUES (?, ?)", info.items())
    amostra = ler(projeto)
    assert amostra is not None
    amostra.avisos = avisos
    if len(escolhidos) < cfg.n:
        amostra.avisos.append(f"Só {len(escolhidos)} documentos com resumo: a amostra ficou menor que {cfg.n}.")
    return amostra


def ler(projeto: Projeto) -> Amostra | None:
    if not projeto.estado.exists():
        return None
    with conectar(projeto) as con:
        linhas = con.execute("SELECT doc, estrato FROM validacao_amostra ORDER BY ordem").fetchall()
        info = dict(con.execute("SELECT chave, valor FROM validacao_info").fetchall())
    if not linhas:
        return None
    return Amostra(
        docs=[d for d, _ in linhas],
        estratos=dict(linhas),
        estratificar_por=info.get("estratificar_por", "topico"),
        semente=int(info.get("semente", 0)),
        n=int(info.get("n", len(linhas))),
        sorteada_em=info.get("sorteada_em", ""),
    )


def exportar(projeto: Projeto, amostra: Amostra) -> Path:
    """`validacao/amostra.jsonl`: id, título, resumo e idioma de cada documento da amostra, na ordem da fila. É o
    que um codificador externo recebe: nenhuma resposta de modelo, nenhum e-mail."""
    textos = {t.doc: t for t in textos_do_projeto(projeto)}
    pasta = projeto.raiz / PASTA_EXPORTACAO
    pasta.mkdir(exist_ok=True)
    destino = pasta / ARQUIVO_AMOSTRA
    with destino.open("w", encoding="utf-8") as f:
        for doc in amostra.docs:
            t = textos[doc]
            linha = {"doc": doc, "titulo": t.titulo, "resumo": t.resumo, "idioma": t.idioma}
            assert not contem_email(linha), f"e-mail no texto de {doc}"
            f.write(json.dumps(linha, ensure_ascii=False) + "\n")
    return destino


# ---------------------------------------------------------------- codificações
def nome_valido(nome: str) -> str:
    if not _NOME.fullmatch(nome):
        raise ErroConfig(
            f"Nome de codificador inválido: {nome!r}. Use letras sem acento, números, `-`, `_` e `.` "
            "(até 40 caracteres), como `felipe` ou `claude-opus`."
        )
    return nome


@dataclass
class ResumoImportacao:
    codificador: str
    documentos: int
    fora_da_amostra: list[str] = field(default_factory=list)
    invalidas: list[str] = field(default_factory=list)  # "doc: problema"


def salvar(
    projeto: Projeto,
    codificador: str,
    doc: str,
    respostas: dict[str, dict[str, Any]],
    *,
    tipo: TipoCodificador = "humano",
    completa: bool = True,
) -> list[str]:
    """Grava as respostas de um codificador para um documento (substituindo as das mesmas variáveis). Devolve os
    problemas; com algum problema, nada é gravado. Com `completa=False` (o salvamento automático do painel), as
    variáveis ainda não respondidas não contam como problema."""
    nome_valido(codificador)
    codebook = projeto.codebook
    bruto = {
        v: {"evidencia": r.get("evidencia") or "", "valor": r.get("valor")} if isinstance(r, dict) else r
        for v, r in respostas.items()
    }
    r = validar(bruto, codebook)
    problemas = [p for p in r.problemas if completa or not p.endswith("faltou a variável")]
    if problemas:
        return problemas
    agora = datetime.now(UTC).isoformat(timespec="seconds")
    with conectar(projeto) as con:
        con.execute("INSERT OR IGNORE INTO codificadores (nome, tipo) VALUES (?, ?)", (codificador, tipo))
        con.executemany(
            "INSERT OR REPLACE INTO codificacoes (codificador, doc, variavel, valor, evidencia, incerto, nota, "
            "atualizado) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    codificador,
                    doc,
                    v,
                    valor_como_texto(r.valores[v]),
                    r.evidencias[v],
                    int(bool(respostas[v].get("incerto"))),
                    str(respostas[v].get("nota") or ""),
                    agora,
                )
                for v in r.valores
            ],
        )
    return []


def importar(
    projeto: Projeto, arquivo: Path, codificador: str, *, tipo: TipoCodificador = "humano"
) -> ResumoImportacao:
    """Importa um JSONL de codificações: uma linha por documento, `{"doc": id, "respostas": {variavel: {"valor":
    …, "evidencia": …, "incerto": …, "nota": …}}}` (ou as variáveis direto na linha, sem `respostas`)."""
    nome_valido(codificador)
    amostra = ler(projeto)
    if amostra is None:
        raise ErroConfig("O projeto ainda não tem amostra. Rode `mapa validar amostra` primeiro.")
    na_amostra = set(amostra.docs)
    resumo = ResumoImportacao(codificador, 0)
    for n, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), 1):
        if not linha.strip():
            continue
        try:
            dado = json.loads(linha)
        except json.JSONDecodeError:
            resumo.invalidas.append(f"linha {n}: não é JSON")
            continue
        doc = dado.get("doc")
        respostas = dado.get("respostas") or {k: v for k, v in dado.items() if k != "doc"}
        if doc not in na_amostra:
            resumo.fora_da_amostra.append(str(doc))
            continue
        if problemas := salvar(projeto, codificador, doc, respostas, tipo=tipo):
            resumo.invalidas.append(f"{doc}: {'; '.join(problemas)}")
            continue
        resumo.documentos += 1
    with conectar(projeto) as con:  # o tipo do codificador vale para a importação inteira
        con.execute("UPDATE codificadores SET tipo = ? WHERE nome = ?", (tipo, codificador))
    return resumo


def codificadores(projeto: Projeto) -> dict[str, TipoCodificador]:
    if not projeto.estado.exists():
        return {}
    with conectar(projeto) as con:
        return dict(con.execute("SELECT nome, tipo FROM codificadores ORDER BY nome").fetchall())


def codificacoes(projeto: Projeto, codificador: str | None = None) -> list[dict[str, Any]]:
    """As codificações (de um codificador, ou de todos), uma por codificador × documento × variável."""
    if not projeto.estado.exists():
        return []
    sql = "SELECT codificador, doc, variavel, valor, evidencia, incerto, nota, atualizado FROM codificacoes"
    with conectar(projeto) as con:
        con.row_factory = sqlite3.Row
        linhas = con.execute(
            sql + (" WHERE codificador = ?" if codificador else ""), (codificador,) if codificador else ()
        )
        return [dict(linha) for linha in linhas]
