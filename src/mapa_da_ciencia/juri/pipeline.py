"""O júri de ponta a ponta, para a CLI (`mapa juri …`).

    votar  →  deliberar  →  exportar-pedidos  →  (supervisor)  →  importar-respostas  →  relatorio

Cada passo pode rodar de novo sem refazer o que já foi feito: a votação e a deliberação vêm do cache, e o supervisor
só recebe o que ainda não tem resposta válida. `status` diz em que passo o júri está; `estado_da_etapa` é o mesmo
cálculo para a linha das etapas do painel e o `mapa status`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..classificacao.resultado import PASTA as PASTA_CLASSIFICACAO
from ..classificacao.resultado import documentos_classificados
from ..llm.ollama import Ollama
from ..progresso import Progresso, ProgressoNulo
from ..projeto import Projeto
from ..trava_etapas import etapa
from .consolidar import ResumoJuri, consolidar, ler_resumo, registrar_passo, resumir
from .deliberacao import ResumoDeliberacao, deliberar
from .estado import PASTA
from .votacao import carregar_votos, membros_do_juri, textos_da_amostra


@etapa("juri")
def deliberar_juri(projeto: Projeto, progresso: Progresso | None = None) -> tuple[ResumoDeliberacao, ResumoJuri]:
    """A rodada de deliberação sobre os votos atuais, seguida da consolidação."""
    inicio = datetime.now(UTC)
    membros = membros_do_juri(projeto)
    textos = {t.doc: t for t in textos_da_amostra(projeto)}
    votos = carregar_votos(projeto, membros, set(textos))
    resumo = (
        deliberar(projeto, membros, votos, textos, progresso=progresso or ProgressoNulo())
        if projeto.config.juri.deliberar
        else ResumoDeliberacao()
    )
    juri = consolidar(projeto)
    registrar_passo(projeto, "deliberar", inicio, juri)
    return resumo, juri


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
        proximo = PROXIMO_RELATORIO
    return EstadoJuri(membros, len(textos), classificados, resumo, proximo)


PROXIMO_RELATORIO = "mapa juri relatorio"


def _sem_data(resumo: ResumoJuri) -> dict[str, Any]:
    return {k: v for k, v in asdict(resumo).items() if k != "gerado_em"}


def estado_da_etapa(projeto: Projeto) -> dict[str, Any] | None:
    """O júri na linha das etapas do painel e no `mapa status`: `None` sem júri no `mapa.yaml`; senão o estado (`None`
    pendente, `"incompleta"`, `False` desatualizado, `True` em dia) e o próximo comando.

    - pendente: sem amostra de validação, ou nenhum membro votou ainda;
    - desatualizado: há um júri de outro codebook e nenhum deste, ou as decisões gravadas (as três fontes que a
      validação lê) não batem mais com os votos e as respostas atuais (rode `mapa juri deliberar`, que consolida);
    - incompleto: falta votar, deliberar ou a resposta do supervisor;
    - em dia: o próximo passo é só o relatório.
    """
    from ..validacao.amostra import ler as ler_amostra

    if not projeto.config.juri.membros:
        return None
    if ler_amostra(projeto) is None:
        return {"estado": None, "proximo": "mapa validar amostra"}
    e = estado(projeto)
    hash_cb = projeto.codebook.hash()
    salvo = ler_resumo(projeto)
    if salvo is None and any(a.parent.name != hash_cb for a in (projeto.dados / PASTA).glob("*/resumo.json")):
        return {"estado": False, "proximo": e.proximo}
    if salvo is None and not any(e.classificados.values()):
        return {"estado": None, "proximo": e.proximo}
    if e.proximo != PROXIMO_RELATORIO:
        return {"estado": "incompleta", "proximo": e.proximo}
    if salvo is None or e.resumo is None or _sem_data(salvo) != _sem_data(e.resumo):
        return {"estado": False, "proximo": "mapa juri deliberar"}
    return {"estado": True, "proximo": PROXIMO_RELATORIO}


def arquivos_de_respostas(projeto: Projeto, arquivos: list[Path]) -> list[Path]:
    """Os arquivos passados, ou, sem nenhum, todos os `*.respostas.jsonl` da pasta `juri/` do projeto."""
    if arquivos:
        return arquivos
    return sorted((projeto.raiz / "juri").glob("*.respostas.jsonl"))
