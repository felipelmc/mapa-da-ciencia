"""Consolidação: dos votos às decisões do júri e às três fontes que a validação compara.

Para cada documento × variável:

| Estágio | Quando |
|---|---|
| `unanime` | todos os membros deram o mesmo valor na rodada 1 |
| `maioria` | houve maioria na rodada 1 e não houve deliberação (variável de texto, ou `deliberar: false`) |
| `deliberacao` | depois da deliberação houve maioria (`virou`: a maioria é outra, ou antes não havia) |
| `sem_maioria` | nem depois da deliberação; vai para o supervisor, se houver resposta dele |

O júri cobre os documentos da amostra de validação. Uma variável em disputa que ainda não foi deliberada fica com o
estágio da rodada 1 (`maioria` ou `sem_maioria`) e entra em `nao_deliberados`: o próximo passo é deliberar.

As três fontes, gravadas em `dados/classificacao/` como se fossem modelos:

- `juri-r1`: a maioria da rodada 1 (sem maioria, o voto do presidente, o primeiro membro);
- `juri`: a maioria depois da deliberação (sem maioria, o voto do presidente depois da deliberação);
- `juri-supervisor`: o `juri`, com a escolha do supervisor onde não houve maioria. Só existe com alguma resposta do
  supervisor. Se o supervisor e um codificador de referência forem da mesma família, a comparação entre os dois é
  circular (ver `validacao.familias`): é um limite superior, e não uma medida independente.

Rodar de novo, sem mudanças, dá os mesmos arquivos: a consolidação só lê (votos, deliberação e respostas do
supervisor) e não chama modelo nenhum.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from ..armazenamento import ARQUIVO as ARQUIVO_DOCUMENTOS
from ..armazenamento import gravar_tabela, ler_documentos
from ..classificacao.resultado import PASTA as PASTA_CLASSIFICACAO
from ..classificacao.resultado import Resultado, nome_do_arquivo, valor_como_texto
from ..config import Variavel
from ..llm.cache import chave_de
from ..projeto import Projeto
from ..topicos.resultado import assinatura_corpus
from .agregacao import Decisao, Voto, agregar, chave
from .deliberacao import DELIBERAVEIS, ler_deliberacao, votos_da_deliberacao
from .estado import conectar, pasta_dados
from .prompt import VERSAO_PROMPT_JURI
from .votacao import Votos, carregar_votos, membros_do_juri, textos_da_amostra

VERSAO_JURI = 1
FONTES = ("juri-r1", "juri", "juri-supervisor")
COLUNAS_DECISOES = {
    "doc": "VARCHAR",
    "variavel": "VARCHAR",
    "etapa": "VARCHAR",
    "virou": "BOOLEAN",
    "valor_r1": "VARCHAR",
    "valor_juri": "VARCHAR",
    "valor_final": "VARCHAR",
    "evidencia": "VARCHAR",
    "status": "VARCHAR",
    "campo": "VARCHAR",
    "inicio": "INTEGER",
    "fim": "INTEGER",
    "membro_evidencia": "VARCHAR",
    "candidatos": "VARCHAR",
    "chave_pedido": "VARCHAR",
    "supervisor": "VARCHAR",
    "justificativa": "VARCHAR",
    "nenhum_adequado": "BOOLEAN",
}
COLUNAS_VOTOS = {
    "doc": "VARCHAR",
    "variavel": "VARCHAR",
    "membro": "VARCHAR",
    "rodada": "INTEGER",
    "valor": "VARCHAR",
    "evidencia": "VARCHAR",
    "status": "VARCHAR",
    "revisou": "BOOLEAN",
}


def assinatura_juri(membros: list[str], deliberar: bool) -> str:
    return chave_de(VERSAO_JURI, VERSAO_PROMPT_JURI, membros, deliberar)[:12]


def chave_pedido(doc: str, variavel: str, candidatos: list[str]) -> str:
    """Identifica um pedido ao supervisor: muda se os candidatos mudarem (e aí a resposta antiga deixa de valer)."""
    return chave_de(VERSAO_PROMPT_JURI, doc, variavel, candidatos)[:16]


@dataclass
class DecisaoFinal:
    doc: str
    variavel: Variavel
    etapa: str
    virou: bool
    r1: Decisao
    juri: Decisao
    votos_r1: list[Voto]
    votos_r2: list[Voto]  # iguais aos da rodada 1 onde não houve deliberação
    valor_r1: Any
    valor_juri: Any
    voto_juri: Voto  # de onde vem a evidência do `juri`
    supervisor: dict[str, Any] | None = None  # a resposta do supervisor que vale para este item
    deliberada: bool = True  # False: em disputa, mas a deliberação ainda não passou por aqui

    @property
    def candidatos(self) -> list[str]:
        return [c.chave for c in self.juri.candidatos]

    @property
    def chave_pedido(self) -> str:
        return chave_pedido(self.doc, self.variavel.id, self.candidatos)


NOME_DO_ESTAGIO = {"unanime": "unânimes", "maioria": "por maioria", "deliberacao": "na deliberação",
                   "sem_maioria": "sem maioria"}  # fmt: skip


def _num(n: int) -> str:
    return f"{n:,}".replace(",", ".")


@dataclass
class ResumoJuri:
    membros: list[str]
    supervisor: str | None
    documentos: int
    etapas: dict[str, dict[str, int]] = field(default_factory=dict)  # variável → estágio → n
    virou: dict[str, int] = field(default_factory=dict)  # variável → decisões que mudaram na deliberação
    revisoes: dict[str, int] = field(default_factory=dict)  # membro → valores mudados na deliberação
    pendentes_supervisor: int = 0  # sem maioria, sem resposta do supervisor
    nao_deliberados: int = 0  # em disputa, ainda sem deliberação
    arbitrados: int = 0
    nenhum_adequado: int = 0
    gerado_em: str = ""

    def __str__(self) -> str:
        total = {e: sum(v.get(e, 0) for v in self.etapas.values()) for e in ESTAGIOS}
        partes = ", ".join(f"{_num(n)} {NOME_DO_ESTAGIO.get(e, e)}" for e, n in total.items() if n)
        texto = (
            f"Júri de {len(self.membros)} membros em {_num(self.documentos)} documento(s), com as decisões por "
            f"variável: {partes}; {_num(self.arbitrados)} decididas pelo supervisor, "
            f"{_num(self.pendentes_supervisor)} esperando o supervisor"
        )
        if self.nao_deliberados:
            texto += f"; {self.nao_deliberados} em disputa ainda sem deliberação"
        return texto + "."


ESTAGIOS = ("unanime", "maioria", "deliberacao", "sem_maioria")


def respostas_do_supervisor(
    projeto: Projeto, hash_codebook: str, tarefa: str, supervisor: str
) -> dict[tuple[str, str], dict]:
    """As respostas guardadas de um supervisor (uma por documento × variável). As de outro nome não se misturam:
    trocar `juri.supervisor.nome` começa a supervisão de novo."""
    with conectar(projeto) as con:
        linhas = con.execute(
            "SELECT * FROM juri_supervisor WHERE hash_codebook = ? AND tarefa = ? AND supervisor = ?",
            (hash_codebook, tarefa, supervisor),
        ).fetchall()
    return {(r["doc"], r["variavel"]): dict(r) for r in linhas}


def votos_do_juri(projeto: Projeto, membros: list[str]) -> Votos:
    """Os votos da rodada 1 nos documentos da amostra de validação (os membros podem ter classificado mais)."""
    return carregar_votos(projeto, membros, {t.doc for t in textos_da_amostra(projeto)})


def decidir(projeto: Projeto, votos: Votos | None = None) -> list[DecisaoFinal]:
    """As decisões de todos os documentos × variáveis da amostra com votos de todos os membros."""
    membros = membros_do_juri(projeto)
    cfg = projeto.config.juri
    codebook = projeto.codebook
    hash_cb = codebook.hash()
    votos = votos if votos is not None else votos_do_juri(projeto, membros)
    r2, info = votos_da_deliberacao(codebook, votos, ler_deliberacao(projeto, hash_cb)) if cfg.deliberar else ({}, {})
    # deliberada é a disputa em que todos os membros deliberaram: uma deliberação interrompida no meio (memória,
    # ctrl+c) deixa o item pendente, e `mapa juri deliberar` retoma de onde parou
    quem: dict[tuple[str, str], set[str]] = {}
    for doc, var, membro in info:
        quem.setdefault((doc, var), set()).add(membro)
    deliberados = {item for item, membros_do_item in quem.items() if membros_do_item >= set(membros)}
    arbitragens = respostas_do_supervisor(projeto, hash_cb, "arbitragem", cfg.supervisor.nome)
    saida = []
    for doc in sorted(votos):
        for v in codebook.variaveis:
            if v.id not in votos[doc]:
                continue
            v1 = votos[doc][v.id]
            d1 = agregar(v, v1)
            em_disputa = cfg.deliberar and v.tipo in DELIBERAVEIS and d1.etapa != "unanime"
            deliberavel = em_disputa and (doc, v.id) in deliberados
            v2 = [r2.get((doc, v.id, x.membro), x) for x in v1] if deliberavel else v1
            d2 = agregar(v, v2) if deliberavel else d1
            if d1.etapa == "unanime":
                etapa = "unanime"
            elif not deliberavel:
                etapa = "maioria" if d1.decidida else "sem_maioria"
            else:
                etapa = "deliberacao" if d2.decidida else "sem_maioria"
            virou = deliberavel and d2.decidida and (not d1.decidida or chave(v, d1.valor) != chave(v, d2.valor))
            valor_r1 = d1.valor if d1.decidida else v1[0].valor
            voto_juri = d2.voto if d2.decidida else v2[0]
            final = DecisaoFinal(doc, v, etapa, virou, d1, d2, v1, v2, valor_r1, voto_juri.valor, voto_juri)
            final.deliberada = deliberavel or not em_disputa
            if etapa == "sem_maioria":
                resposta = arbitragens.get((doc, v.id))
                if resposta and resposta["chave_pedido"] == final.chave_pedido:
                    final.supervisor = resposta
            saida.append(final)
    return saida


def _linha_fonte(d: DecisaoFinal, valor: Any, voto: Voto | None, supervisor: dict | None = None) -> dict[str, Any]:
    if supervisor is not None:
        return {
            "doc": d.doc,
            "variavel": d.variavel.id,
            "valor": supervisor["valor"],
            "evidencia": supervisor["evidencia"] or "",
            "status": supervisor["status"],
            "campo": None,
            "inicio": None,
            "fim": None,
            "tentativas": 3,
            "valida_na_primeira": True,
            "segundos": 0.0,
        }
    assert voto is not None
    return {
        "doc": d.doc,
        "variavel": d.variavel.id,
        "valor": valor_como_texto(valor),
        "evidencia": voto.evidencia,
        "status": voto.status,
        "campo": voto.campo,
        "inicio": voto.inicio,
        "fim": voto.fim,
        "tentativas": 2 if d.etapa in ("deliberacao", "sem_maioria") and d.votos_r2 is not d.votos_r1 else 1,
        "valida_na_primeira": True,
        "segundos": 0.0,
    }


def _revisou(d: DecisaoFinal, x: Voto, info_r2: dict) -> bool:
    linha = info_r2.get((d.doc, d.variavel.id, x.membro))
    return bool(linha and linha["revisou"])


def _resumo(projeto: Projeto) -> tuple[ResumoJuri, list[DecisaoFinal], dict]:
    """O resumo do júri com os votos e as respostas atuais, sem gravar nada (é o que o status mostra)."""
    membros = membros_do_juri(projeto)
    cfg = projeto.config.juri
    codebook = projeto.codebook
    votos = votos_do_juri(projeto, membros)
    decisoes = decidir(projeto, votos)
    _, info_r2 = (
        votos_da_deliberacao(codebook, votos, ler_deliberacao(projeto, codebook.hash())) if cfg.deliberar else ({}, {})
    )
    resumo = ResumoJuri(
        membros=membros,
        supervisor=cfg.supervisor.nome if any(d.supervisor for d in decisoes) else None,
        documentos=len(votos),
        gerado_em=datetime.now(UTC).isoformat(timespec="seconds"),
    )
    for d in decisoes:
        por_var = resumo.etapas.setdefault(d.variavel.id, dict.fromkeys(ESTAGIOS, 0))
        por_var[d.etapa] += 1
        resumo.virou[d.variavel.id] = resumo.virou.get(d.variavel.id, 0) + int(d.virou)
        resumo.nao_deliberados += int(not d.deliberada)
        if d.etapa == "sem_maioria" and d.variavel.tipo in DELIBERAVEIS and d.deliberada:
            if d.supervisor:
                resumo.arbitrados += 1
                resumo.nenhum_adequado += int(bool(d.supervisor["nenhum_adequado"]))
            else:
                resumo.pendentes_supervisor += 1
        if d.votos_r2 is not d.votos_r1:
            for x in d.votos_r2:
                resumo.revisoes[x.membro] = resumo.revisoes.get(x.membro, 0) + int(_revisou(d, x, info_r2))
    return resumo, decisoes, info_r2


def resumir(projeto: Projeto) -> ResumoJuri:
    """O resumo atual do júri, recalculado (sem ler o `resumo.json`, que é da última consolidação)."""
    return _resumo(projeto)[0]


def consolidar(projeto: Projeto) -> ResumoJuri:
    """Grava as decisões, os votos e as três fontes do júri; devolve o resumo."""
    membros = membros_do_juri(projeto)
    cfg = projeto.config.juri
    codebook = projeto.codebook
    hash_cb = codebook.hash()
    resumo, decisoes, info_r2 = _resumo(projeto)
    tem_supervisor = resumo.supervisor is not None
    linhas_decisoes, linhas_votos = [], []
    fontes: dict[str, list[dict[str, Any]]] = {f: [] for f in FONTES}
    for d in decisoes:
        sup = d.supervisor
        final = sup["valor"] if sup else valor_como_texto(d.valor_juri)
        ev = sup if sup else None
        linhas_decisoes.append(
            {
                "doc": d.doc,
                "variavel": d.variavel.id,
                "etapa": d.etapa,
                "virou": d.virou,
                "valor_r1": valor_como_texto(d.valor_r1),
                "valor_juri": valor_como_texto(d.valor_juri),
                "valor_final": final,
                "evidencia": (ev["evidencia"] if ev else d.voto_juri.evidencia) or "",
                "status": ev["status"] if ev else d.voto_juri.status,
                "campo": None if ev else d.voto_juri.campo,
                "inicio": None if ev else d.voto_juri.inicio,
                "fim": None if ev else d.voto_juri.fim,
                "membro_evidencia": sup["supervisor"] if sup else d.voto_juri.membro,
                "candidatos": json.dumps(d.candidatos, ensure_ascii=False),
                "chave_pedido": d.chave_pedido if d.etapa == "sem_maioria" else None,
                "supervisor": sup["supervisor"] if sup else None,
                "justificativa": sup["justificativa"] if sup else None,
                "nenhum_adequado": bool(sup["nenhum_adequado"]) if sup else None,
            }
        )
        for x in d.votos_r1:
            linhas_votos.append(_voto(d, x, 1, False))
        if d.votos_r2 is not d.votos_r1:
            for x in d.votos_r2:
                linhas_votos.append(_voto(d, x, 2, _revisou(d, x, info_r2)))
        fontes["juri-r1"].append(_linha_fonte(d, d.valor_r1, d.r1.voto if d.r1.decidida else d.votos_r1[0]))
        fontes["juri"].append(_linha_fonte(d, d.valor_juri, d.voto_juri))
        fontes["juri-supervisor"].append(_linha_fonte(d, d.valor_juri, d.voto_juri, sup))

    pasta = pasta_dados(projeto, hash_cb)
    gravar_tabela(linhas_decisoes, COLUNAS_DECISOES, pasta / "decisoes.parquet", ordem="doc")
    gravar_tabela(linhas_votos, COLUNAS_VOTOS, pasta / "votos.parquet", ordem="doc")
    tmp = pasta / "resumo.json.tmp"
    tmp.write_text(json.dumps(asdict(resumo), ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, pasta / "resumo.json")

    ids = [doc.id for doc in ler_documentos(projeto.dados / ARQUIVO_DOCUMENTOS)]
    assinatura = assinatura_corpus(ids)
    h = assinatura_juri(membros, cfg.deliberar)
    destino = projeto.dados / PASTA_CLASSIFICACAO
    for fonte, linhas in fontes.items():
        if fonte == "juri-supervisor" and not tem_supervisor:
            (destino / f"{nome_do_arquivo(fonte, hash_cb)}.json").unlink(missing_ok=True)
            (destino / f"{nome_do_arquivo(fonte, hash_cb)}.parquet").unlink(missing_ok=True)
            continue
        status = [linha["status"] for linha in linhas if linha["status"] != "dispensada"]
        Resultado(
            modelo=f"{fonte}@{h}",
            codebook=f"{codebook.nome} {codebook.versao}",
            hash_codebook=hash_cb,
            assinatura=assinatura,
            gerado_em=resumo.gerado_em,
            documentos=resumo.documentos,
            classificados=resumo.documentos,
            sem_resumo=0,
            json_valido_na_primeira=1.0 if linhas else None,
            evidencia={s: round(status.count(s) / len(status), 4) for s in ("literal", "aproximada", "ausente")}
            if status
            else {},
            parcial=True,
        ).gravar(destino, linhas)
    return resumo


def _voto(d: DecisaoFinal, x: Voto, rodada: int, revisou: bool) -> dict[str, Any]:
    return {
        "doc": d.doc,
        "variavel": d.variavel.id,
        "membro": x.membro,
        "rodada": rodada,
        "valor": valor_como_texto(x.valor),
        "evidencia": x.evidencia,
        "status": x.status,
        "revisou": revisou,
    }


def ler_resumo(projeto: Projeto) -> ResumoJuri | None:
    arquivo = pasta_dados(projeto, projeto.codebook.hash()) / "resumo.json"
    if not arquivo.exists():
        return None
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    return ResumoJuri(**{k: x for k, x in dados.items() if k in ResumoJuri.__dataclass_fields__})
