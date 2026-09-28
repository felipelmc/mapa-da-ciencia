"""O júri de ponta a ponta, para a CLI (`mapa juri …`) e para `mapa_da_ciencia.api`.

    votar  →  deliberar  →  exportar-pedidos  →  (supervisor)  →  importar-respostas  →  relatorio

Cada passo pode rodar de novo sem refazer o que já foi feito: a votação e a deliberação vêm do cache, e o supervisor
só recebe o que ainda não tem resposta válida. `status` diz em que passo o júri está.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..classificacao.executor import Classificador
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
    """Em que passo o júri está e qual é o próximo comando."""
    membros = membros_do_juri(projeto)
    textos = textos_da_amostra(projeto)
    base = projeto.config.modelos.classificacao
    ollama = ollama or Ollama()
    classificados = {}
    for membro in membros:
        cfg = base.model_copy(update={"modelo": membro})
        try:
            pendentes = Classificador(cfg, projeto.codebook, projeto.estado, ollama=ollama).pendentes(textos)
            classificados[membro] = len(textos) - len(pendentes)
        except Exception:  # modelo não instalado ou Ollama fora do ar: o status não quebra
            classificados[membro] = 0
    completos = not any(n < len(textos) for n in classificados.values())
    # recalculado, e não o resumo.json da última consolidação: depois de uma votação nova ele estaria velho
    resumo = resumir(projeto) if completos else ler_resumo(projeto)
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
