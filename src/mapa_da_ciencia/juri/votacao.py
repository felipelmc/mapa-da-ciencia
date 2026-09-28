"""Rodada 1 do júri: cada membro classifica, e os votos saem dos resultados de cada um.

Votar é classificar com cada membro, um depois do outro, pelo mesmo caminho de `mapa classificar --modelo`: o
mesmo prompt, os mesmos parâmetros e o mesmo cache. Um membro que já classificou os documentos não é chamado de
novo; se falta só o resultado gravado com o codebook atual (depois de mudar um rótulo de categoria, que o modelo
não lê), a classificação o monta do cache, sem chamar o modelo. Antes de carregar um membro, os outros membros
que estiverem na memória são descarregados (nunca outros modelos): no Mac do piloto, dois modelos de 7 GB ao
mesmo tempo apertam a memória.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..classificacao.executor import Classificador, Texto
from ..classificacao.pipeline import OpcoesClassificacao, ResumoClassificacao, classificar
from ..classificacao.resultado import PASTA as PASTA_CLASSIFICACAO
from ..classificacao.resultado import documentos_classificados, ler_linhas, valor_do_texto
from ..config import ErroConfig
from ..llm.ollama import Ollama
from ..progresso import Progresso
from ..projeto import Projeto
from ..validacao import amostra as va
from .agregacao import Voto

# votos[doc][variavel] = um voto por membro, na ordem do júri
Votos = dict[str, dict[str, list[Voto]]]


def membros_do_juri(projeto: Projeto) -> list[str]:
    membros = projeto.config.juri.membros
    if len(membros) < 2:
        raise ErroConfig(
            "O projeto não tem júri. Liste os modelos em `juri.membros` no mapa.yaml (três, de famílias "
            "diferentes, por exemplo `[qwen3.5:9b, gemma4:12b-it-qat, qwen3.5:4b]`)."
        )
    return membros


def textos_da_amostra(projeto: Projeto) -> list[Texto]:
    amostra = va.ler(projeto)
    if amostra is None:
        raise ErroConfig("O projeto ainda não tem amostra de validação. Rode `mapa validar amostra` antes.")
    posicao = {d: i for i, d in enumerate(amostra.docs)}
    textos = [t for t in va.textos_do_projeto(projeto) if t.doc in posicao]
    return sorted(textos, key=lambda t: posicao[t.doc])


@dataclass
class ResumoVotacao:
    membros: list[str]
    classificados: dict[str, int]  # membro → documentos novos nesta execução
    ja_prontos: list[str]  # membros que já tinham classificado tudo

    def __str__(self) -> str:
        novos = ", ".join(f"{m}: {n}" for m, n in self.classificados.items()) or "nenhum"
        return f"Votação do júri ({len(self.membros)} membros): documentos novos por membro — {novos}."


def _descarregar_outros(ollama: Ollama, membros: list[str], membro: str) -> None:
    carregados = {m.nome.removesuffix(":latest") for m in ollama.modelos_carregados()}
    for outro in membros:
        if outro != membro and outro.removesuffix(":latest") in carregados:
            ollama.descarregar(outro)


def gravado(projeto: Projeto, membro: str, textos: list[Texto]) -> bool:
    """O resultado do membro com o codebook atual cobre a amostra (é dele que os votos são lidos)."""
    docs = documentos_classificados(projeto.dados / PASTA_CLASSIFICACAO, membro, projeto.codebook.hash())
    return docs is not None and {t.doc for t in textos} <= docs


def votar(projeto: Projeto, *, progresso: Progresso | None = None) -> ResumoVotacao:
    """Classifica com cada membro o que ainda falta da amostra de validação."""
    membros = membros_do_juri(projeto)
    textos = textos_da_amostra(projeto)
    ollama = Ollama()
    resumo = ResumoVotacao(membros, {}, [])
    base = projeto.config.modelos.classificacao
    for membro in membros:
        cfg = base.model_copy(update={"modelo": membro})
        if not Classificador(cfg, projeto.codebook, projeto.estado, ollama=ollama).pendentes(textos) and gravado(
            projeto, membro, textos
        ):
            resumo.ja_prontos.append(membro)
            continue
        _descarregar_outros(ollama, membros, membro)
        feito: ResumoClassificacao = classificar(
            projeto, OpcoesClassificacao(modelo=membro, somente_amostra=True), progresso
        )
        resumo.classificados[membro] = feito.novos
    return resumo


def carregar_votos(projeto: Projeto, membros: list[str], docs: set[str] | None = None) -> Votos:
    """Os votos da rodada 1, lidos dos resultados de cada membro com o codebook atual. Só entram os documentos ×
    variáveis em que todos os membros responderam."""
    codebook = projeto.codebook
    tipos = {v.id: v.tipo for v in codebook.variaveis}
    hash_cb = codebook.hash()
    pasta = projeto.dados / PASTA_CLASSIFICACAO
    por_membro: list[dict[tuple[str, str], Voto]] = []
    for membro in membros:
        linhas = ler_linhas(pasta, membro, hash_cb)
        por_membro.append(
            {
                (linha["doc"], linha["variavel"]): Voto(
                    membro,
                    valor_do_texto(linha["valor"], tipos[linha["variavel"]]),
                    linha["evidencia"] or "",
                    linha["status"],
                    linha["campo"],
                    linha["inicio"],
                    linha["fim"],
                )
                for linha in linhas
                if linha["variavel"] in tipos and (docs is None or linha["doc"] in docs)
            }
        )
    votos: Votos = {}
    comuns = set.intersection(*(set(m) for m in por_membro)) if por_membro else set()
    for doc, variavel in sorted(comuns):
        votos.setdefault(doc, {})[variavel] = [m[(doc, variavel)] for m in por_membro]
    return votos
