"""Rodada 2 do júri: a deliberação.

Nas variáveis em que os membros não foram unânimes (só as categóricas, booleanas e de múltipla escolha: texto livre
não se delibera), cada membro recebe, na mesma conversa da classificação, a própria resposta e as dos outros,
anônimas, com as evidências (ver `prompt.py`), e responde de novo só essas variáveis. Uma chamada por membro e
documento, uma rodada só.

A nova resposta de uma variável só vale se vier no formato do codebook e com evidência que não seja `ausente`; do
contrário, fica o voto da rodada 1 (`valida = False`). Cada resposta válida vai para o cache (`juri_deliberacao`),
com uma chave que inclui as respostas dos pares: se o voto de um par mudar (outro modelo, outro codebook), só aquele
documento é deliberado de novo. O resultado vai para `dados/juri/<hash>/deliberacao.parquet`, regravado a cada
`GRAVAR_A_CADA` documentos e no fim, com o `contexto` de cada voto (o que o membro viu), para a consolidação
descartar votos de um contexto que já mudou.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from ..armazenamento import gravar_tabela, ler_tabela
from ..classificacao.codebook import esquema, sem_informacao, validar
from ..classificacao.evidencia import conferir
from ..classificacao.executor import Classificador, Texto
from ..classificacao.prompt import assinatura, mensagem_documento, mensagem_sistema
from ..classificacao.resultado import valor_como_texto, valor_do_texto
from ..config import Codebook, Variavel
from ..llm.base import ErroProvedor
from ..llm.cache import CacheLLM, chave_de
from ..llm.memoria import garantir_modelo, memoria_critica
from ..llm.ollama import Ollama
from ..progresso import Progresso, ProgressoNulo
from ..projeto import Projeto
from .agregacao import Voto, agregar, chave
from .estado import TAREFA_DELIBERACAO, pasta_dados
from .prompt import VERSAO_PROMPT_JURI, mensagem_deliberacao, resposta_propria
from .votacao import Votos

DELIBERAVEIS = ("categorica", "booleana", "multipla")
GRAVAR_A_CADA = 25
ARQUIVO = "deliberacao.parquet"
COLUNAS = {
    "doc": "VARCHAR",
    "variavel": "VARCHAR",
    "membro": "VARCHAR",
    "valor": "VARCHAR",
    "evidencia": "VARCHAR",
    "status": "VARCHAR",
    "campo": "VARCHAR",
    "inicio": "INTEGER",
    "fim": "INTEGER",
    "revisou": "BOOLEAN",
    "valida": "BOOLEAN",
    "contexto": "VARCHAR",
    "segundos": "DOUBLE",
}


def em_disputa(codebook: Codebook, votos_doc: dict[str, list[Voto]]) -> list[Variavel]:
    """As variáveis deliberáveis em que os membros não foram unânimes."""
    return [
        v
        for v in codebook.variaveis
        if v.tipo in DELIBERAVEIS and v.id in votos_doc and agregar(v, votos_doc[v.id]).etapa != "unanime"
    ]


def _pares(variavel: Variavel, votos: list[Voto], membro: str) -> list[Voto]:
    """Os votos dos outros membros, na ordem dos valores (e não dos membros), para não revelar quem é quem."""
    outros = [v for v in votos if v.membro != membro]
    return sorted(outros, key=lambda v: (chave(variavel, v.valor), v.evidencia))


def disputas_do_membro(
    codebook: Codebook, votos_doc: dict[str, list[Voto]], membro: str
) -> list[tuple[Variavel, Voto, list[Voto]]]:
    saida = []
    for v in em_disputa(codebook, votos_doc):
        proprio = next(x for x in votos_doc[v.id] if x.membro == membro)
        saida.append((v, proprio, _pares(v, votos_doc[v.id], membro)))
    return saida


def contexto(doc: str, disputadas: list[tuple[Variavel, Voto, list[Voto]]]) -> str:
    """O que o membro vê na deliberação de um documento (sem o modelo): muda se algum voto da rodada 1 mudar."""
    return chave_de(
        VERSAO_PROMPT_JURI,
        doc,
        [(v.id, p.valor, p.evidencia, [(x.valor, x.evidencia, x.status) for x in pares]) for v, p, pares in disputadas],
    )[:24]


@dataclass
class ResumoDeliberacao:
    documentos: int = 0  # com alguma variável em disputa
    chamadas: int = 0
    do_cache: int = 0
    invalidas: int = 0  # respostas fora do formato (fica o voto da rodada 1)
    revisoes: dict[str, int] = field(default_factory=dict)  # membro → variáveis em que mudou de valor

    def __str__(self) -> str:
        revisoes = ", ".join(f"{m}: {n}" for m, n in self.revisoes.items()) or "nenhuma"
        return (
            f"Deliberação em {self.documentos} documento(s): {self.chamadas} chamada(s) novas e {self.do_cache} do "
            f"cache; mudanças de voto por membro: {revisoes}."
        )


def _linha(doc: str, voto: Voto, variavel: Variavel, *, revisou: bool, valida: bool, ctx: str, seg: float) -> dict:
    return {
        "doc": doc,
        "variavel": variavel.id,
        "membro": voto.membro,
        "valor": valor_como_texto(voto.valor),
        "evidencia": voto.evidencia,
        "status": voto.status,
        "campo": voto.campo,
        "inicio": voto.inicio,
        "fim": voto.fim,
        "revisou": revisou,
        "valida": valida,
        "contexto": ctx,
        "segundos": seg,
    }


def deliberar(
    projeto: Projeto,
    membros: list[str],
    votos: Votos,
    textos: dict[str, Texto],
    *,
    ollama: Ollama | None = None,
    progresso: Progresso | None = None,
) -> ResumoDeliberacao:
    """Delibera, membro a membro, os documentos com variáveis em disputa, e grava `deliberacao.parquet`."""
    codebook = projeto.codebook
    ollama = ollama or Ollama()
    progresso = progresso or ProgressoNulo()
    base = projeto.config.modelos.classificacao
    sistema = mensagem_sistema(codebook)
    assin = assinatura(codebook)
    destino = pasta_dados(projeto, codebook.hash()) / ARQUIVO
    resumo = ResumoDeliberacao()
    docs = [d for d in votos if em_disputa(codebook, votos[d]) and d in textos]
    resumo.documentos = len(docs)
    linhas: list[dict[str, Any]] = []

    for membro in membros:
        cfg = base.model_copy(update={"modelo": membro})
        modelo = Classificador(cfg, codebook, projeto.estado, ollama=ollama).modelo  # nome@digest
        parametros = (cfg.num_ctx, cfg.temperatura, cfg.semente, cfg.pensar)
        carregou = pronto = False
        resumo.revisoes.setdefault(membro, 0)
        progresso.etapa(f"Deliberação ({membro})", len(docs))
        with CacheLLM(projeto.estado) as cache:
            try:
                for i, doc in enumerate(docs, 1):
                    texto = textos[doc]
                    disputadas = disputas_do_membro(codebook, votos[doc], membro)
                    ctx = contexto(doc, disputadas)
                    k = chave_de(VERSAO_PROMPT_JURI, assin, modelo, parametros, texto.titulo, texto.resumo, ctx)
                    guardado = cache.obter(TAREFA_DELIBERACAO, k)
                    if guardado is None:
                        if not pronto:
                            ja = any(
                                m.nome.removesuffix(":latest") == membro.removesuffix(":latest")
                                for m in ollama.modelos_carregados()
                            )
                            garantir_modelo(ollama, membro)
                            carregou, pronto = not ja, True
                        if memoria_critica():
                            raise ErroProvedor(
                                "A memória do computador acabou no meio da deliberação. Feche programas pesados e "
                                "rode de novo: o que já foi deliberado está guardado."
                            )
                        guardado = _perguntar(ollama, cfg, codebook, sistema, texto, disputadas)
                        resumo.chamadas += 1
                        if guardado is not None:
                            cache.guardar(TAREFA_DELIBERACAO, k, guardado, modelo)
                    else:
                        resumo.do_cache += 1
                    linhas += _linhas_do_membro(doc, texto, disputadas, guardado, ctx, resumo)
                    progresso.avancar()
                    if i % GRAVAR_A_CADA == 0:
                        gravar_tabela(linhas, COLUNAS, destino, ordem="doc")
            finally:
                if carregou:
                    ollama.descarregar(membro)
        progresso.fim()
    gravar_tabela(linhas, COLUNAS, destino, ordem="doc")
    return resumo


def _perguntar(
    ollama: Ollama,
    cfg,
    codebook: Codebook,
    sistema: str,
    texto: Texto,
    disputadas: list[tuple[Variavel, Voto, list[Voto]]],
) -> dict[str, Any] | None:
    """Uma chamada: a resposta crua validada (valores e evidências), ou None se nem JSON veio."""
    recorte = codebook.model_copy(update={"variaveis": [v for v, _, _ in disputadas]})
    mensagens = [
        {"role": "system", "content": sistema},
        {"role": "user", "content": mensagem_documento(texto.titulo, texto.resumo)},
        {"role": "assistant", "content": resposta_propria(disputadas)},
        {"role": "user", "content": mensagem_deliberacao(disputadas)},
    ]
    inicio = time.perf_counter()
    try:
        bruto = ollama.gerar_estruturado(
            cfg.modelo,
            mensagens,
            esquema(recorte),
            num_ctx=cfg.num_ctx,
            temperatura=cfg.temperatura,
            semente=cfg.semente,
            pensar=cfg.pensar,
        )
    except ErroProvedor as erro:
        if "JSON" not in str(erro):
            raise
        return None
    r = validar(bruto, recorte)
    return {
        "valores": {k: valor_como_texto(v) for k, v in r.valores.items()},
        "evidencias": r.evidencias,
        "segundos": round(time.perf_counter() - inicio, 3),
    }


def _linhas_do_membro(
    doc: str,
    texto: Texto,
    disputadas: list[tuple[Variavel, Voto, list[Voto]]],
    guardado: dict[str, Any] | None,
    ctx: str,
    resumo: ResumoDeliberacao,
) -> list[dict[str, Any]]:
    linhas = []
    segundos = guardado["segundos"] if guardado else 0.0
    for v, proprio, _ in disputadas:
        novo = None
        if guardado and v.id in guardado["valores"]:
            valor = valor_do_texto(guardado["valores"][v.id], v.tipo)
            evidencia = guardado["evidencias"].get(v.id, "")
            c = conferir(evidencia, texto.resumo, texto.titulo, sem_informacao=sem_informacao(v, valor))
            if c.status != "ausente":
                novo = Voto(proprio.membro, valor, evidencia, c.status, c.campo, c.inicio, c.fim)
        if novo is None:
            resumo.invalidas += 1
            linhas.append(_linha(doc, proprio, v, revisou=False, valida=False, ctx=ctx, seg=segundos))
            continue
        revisou = chave(v, novo.valor) != chave(v, proprio.valor)
        resumo.revisoes[proprio.membro] = resumo.revisoes.get(proprio.membro, 0) + int(revisou)
        linhas.append(_linha(doc, novo, v, revisou=revisou, valida=True, ctx=ctx, seg=segundos))
    return linhas


def ler_deliberacao(projeto: Projeto, hash_codebook: str) -> list[dict[str, Any]]:
    arquivo = pasta_dados(projeto, hash_codebook) / ARQUIVO
    return ler_tabela(arquivo) if arquivo.exists() else []


def votos_da_deliberacao(
    codebook: Codebook, votos: Votos, linhas: list[dict[str, Any]]
) -> tuple[dict[tuple[str, str, str], Voto], dict[tuple[str, str, str], dict[str, Any]]]:
    """Os votos da rodada 2 que ainda valem (o contexto não mudou), por (doc, variável, membro), e as linhas."""
    tipos = {v.id: v for v in codebook.variaveis}
    ctx_atual: dict[tuple[str, str], str] = {}
    saida: dict[tuple[str, str, str], Voto] = {}
    info: dict[tuple[str, str, str], dict[str, Any]] = {}
    for linha in linhas:
        doc, var, membro = linha["doc"], linha["variavel"], linha["membro"]
        if doc not in votos or var not in tipos:
            continue
        if (doc, membro) not in ctx_atual:
            ctx_atual[(doc, membro)] = contexto(doc, disputas_do_membro(codebook, votos[doc], membro))
        if linha["contexto"] != ctx_atual[(doc, membro)]:
            continue
        v = tipos[var]
        saida[(doc, var, membro)] = Voto(
            membro,
            valor_do_texto(linha["valor"], v.tipo),
            linha["evidencia"] or "",
            linha["status"],
            linha["campo"],
            linha["inicio"],
            linha["fim"],
        )
        info[(doc, var, membro)] = linha
    return saida, info
