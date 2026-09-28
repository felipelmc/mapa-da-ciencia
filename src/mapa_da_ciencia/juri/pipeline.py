"""O júri de ponta a ponta, para a CLI (`mapa juri …`) e para `mapa_da_ciencia.api`.

    votar  →  deliberar  →  exportar-pedidos  →  (supervisor)  →  importar-respostas  →  relatorio

Cada passo pode rodar de novo sem refazer o que já foi feito: a votação e a deliberação vêm do cache, e o supervisor
só recebe o que ainda não tem resposta válida. `status` diz em que passo o júri está.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..classificacao.resultado import PASTA as PASTA_CLASSIFICACAO
from ..classificacao.resultado import documentos_classificados
from ..llm.ollama import Ollama
from ..progresso import Progresso, ProgressoNulo
from ..projeto import Projeto
from .consolidar import ResumoJuri, consolidar, ler_resumo, resumir
from .deliberacao import ResumoDeliberacao, deliberar
from .votacao import carregar_votos, membros_do_juri, textos_da_amostra


def deliberar_juri(projeto: Projeto, progresso: Progresso | None = None) -> tuple[ResumoDeliberacao, ResumoJuri]:
    """A rodada de deliberação sobre os votos atuais, seguida da consolidação."""
    membros = membros_do_juri(projeto)
    textos = {t.doc: t for t in textos_da_amostra(projeto)}
    votos = carregar_votos(projeto, membros, set(textos))
    resumo = (
        deliberar(projeto, membros, votos, textos, progresso=progresso or ProgressoNulo())
        if projeto.config.juri.deliberar
        else ResumoDeliberacao()
    )
    return resumo, consolidar(projeto)


@dataclass
class EstadoJuri:
    membros: list[str]
    amostra: int
    classificados: dict[str, int]  # membro → documentos da amostra já classificados
    resumo: ResumoJuri | None
    proximo: str
    avisos: list[str] = field(default_factory=list)


def estado(projeto: Projeto, *, ollama: Ollama | None = None) -> EstadoJuri:
    """Em que passo o júri está e qual é o próximo comando. Os votos de cada membro contam pelo resultado gravado
    com o codebook atual (o que o júri lê), e não pelo cache do modelo: o status não depende do Ollama, e uma mudança
    de rótulo no codebook (que deixa o cache inteiro, mas sem o resultado do codebook novo) pede `votar` de novo."""
    membros = membros_do_juri(projeto)
    textos = textos_da_amostra(projeto)
    na_amostra = {t.doc for t in textos}
    pasta = projeto.dados / PASTA_CLASSIFICACAO
    hash_cb = projeto.codebook.hash()
    classificados = {m: len(na_amostra & (documentos_classificados(pasta, m, hash_cb) or set())) for m in membros}
    completos = not any(n < len(textos) for n in classificados.values())
    # recalculado, e não o resumo.json da última consolidação: depois de uma votação nova ele estaria velho
    resumo = resumir(projeto) if completos else ler_resumo(projeto)
    if resumo is not None and not resumo.documentos:  # o resumo de outro codebook, ou vazio
        resumo = None
    if not completos:
        proximo = "mapa juri votar"
    elif resumo is None or resumo.nao_deliberados:
        proximo = "mapa juri deliberar"
    elif resumo.pendentes_supervisor:
        proximo = "mapa juri exportar-pedidos (e depois importar-respostas)"
    else:
        proximo = "mapa juri relatorio"
    return EstadoJuri(membros, len(textos), classificados, resumo, proximo)


def arquivos_de_respostas(projeto: Projeto, arquivos: list[Path]) -> list[Path]:
    """Os arquivos passados, ou, sem nenhum, todos os `*.respostas.jsonl` da pasta `juri/` do projeto."""
    if arquivos:
        return arquivos
    return sorted((projeto.raiz / "juri").glob("*.respostas.jsonl"))
