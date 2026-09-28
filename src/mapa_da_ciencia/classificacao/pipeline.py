"""A etapa de classificação de ponta a ponta (`mapa classificar`).

corpus → textos (resumo no idioma de exibição) → executor (cache, nova tentativa, memória) → conferência das
evidências → `dados/classificacao/` → manifesto da etapa → exportação para o painel.

É a etapa mais longa do pipeline: no piloto, horas. Por isso `--estimar` mede o tempo com 5 documentos antes,
`--limite` classifica só os primeiros, e uma execução interrompida retoma de onde parou. Os documentos da amostra
de validação vêm primeiro na fila (e `--somente-amostra` classifica só eles), para a validação poder começar antes
do fim da classificação e para comparar modelos só na amostra.
"""

from __future__ import annotations

import contextlib
import statistics
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime

from ..armazenamento import ARQUIVO, ler_documentos
from ..config import ErroConfig
from ..contrato.exportar import exportar
from ..formatar import num
from ..llm.cache import chave_de
from ..llm.ollama import Ollama
from ..manifesto import registrar_execucao
from ..progresso import Progresso, ProgressoNulo
from ..projeto import Projeto
from ..topicos.resultado import assinatura_corpus
from ..validacao.amostra import ler as ler_amostra
from .executor import Classificacao, Classificador, textos_para_classificar
from .prompt import VERSAO_PROMPT
from .resultado import PASTA, Resultado, resultados, valor_como_texto

AMOSTRA_ESTIMATIVA = 5
GRAVAR_A_CADA = 50


@dataclass
class OpcoesClassificacao:
    estimar: bool = False
    limite: int | None = None
    modelo: str | None = None  # outro modelo, para comparar (padrão: modelos.classificacao.modelo)
    somente_amostra: bool = False  # só os documentos da amostra de validação


@dataclass
class ResumoClassificacao:
    """O que a etapa fez. `print(resumo)` mostra os números principais numa frase."""

    modelo: str
    documentos: int
    classificados: int
    do_cache: int
    novos: int
    falhas: list[str]
    sem_resumo: int
    json_valido_na_primeira: float | None
    evidencia: dict[str, float]
    segundos_por_documento: float | None
    pendentes: int  # ainda não classificados depois desta execução
    estimativa_restante_s: float | None
    duracao_s: float
    parcial: bool
    avisos: list[str] = field(default_factory=list)
    amostra_a_parte: bool = False  # gravado no resultado à parte da amostra (`Resultado.somente_amostra`)

    def __str__(self) -> str:
        literal = self.evidencia.get("literal")
        partes = [
            f"{num(self.classificados, 0)} de {num(self.documentos, 0)} documentos com resumo classificados por "
            f"{self.modelo.split('@', 1)[0]}"
        ]
        if literal is not None:
            partes.append(f"evidência literal em {num(100 * literal, 0)}%")
        partes.append(f"{num(self.novos, 0)} novos e {num(self.do_cache, 0)} do cache, em {num(self.duracao_s, 0)} s")
        return "; ".join(partes) + "."


def _linhas(c: Classificacao, variaveis: list[str]) -> list[dict]:
    return [
        {
            "doc": c.doc,
            "variavel": v,
            "valor": valor_como_texto(c.valores[v]),
            "evidencia": c.evidencias[v],
            "status": c.conferencias[v].status,
            "campo": c.conferencias[v].campo,
            "inicio": c.conferencias[v].inicio,
            "fim": c.conferencias[v].fim,
            "tentativas": c.tentativas,
            "valida_na_primeira": c.valida_na_primeira,
            "segundos": c.segundos,
        }
        for v in variaveis
        if v in c.valores
    ]


def classificar(
    projeto: Projeto, opcoes: OpcoesClassificacao | None = None, progresso: Progresso | None = None
) -> ResumoClassificacao:
    opcoes = opcoes or OpcoesClassificacao()
    progresso = progresso or ProgressoNulo()
    inicio, t0 = datetime.now(UTC), time.perf_counter()
    caminho = projeto.dados / ARQUIVO
    if not caminho.exists():
        raise ErroConfig("O projeto ainda não tem corpus. Rode `mapa coletar` antes de `mapa classificar`.")
    cfg = projeto.config
    modelo_cfg = cfg.modelos.classificacao
    if opcoes.modelo:
        modelo_cfg = modelo_cfg.model_copy(update={"modelo": opcoes.modelo})
    codebook = projeto.codebook
    docs = ler_documentos(caminho)
    idiomas = [cfg.recorte.idioma_exibicao, cfg.recorte.idioma_analise]
    textos, sem_resumo = textos_para_classificar(docs, idiomas)
    amostra = ler_amostra(projeto)
    if opcoes.somente_amostra and amostra is None:
        raise ErroConfig("O projeto ainda não tem amostra de validação. Rode `mapa validar amostra` antes.")
    posicao = {doc: i for i, doc in enumerate(amostra.docs)} if amostra else {}
    # a amostra primeiro, na ordem da fila; depois o resto, por id
    textos = sorted(textos, key=lambda t: (posicao.get(t.doc, len(posicao)), t.doc))

    classificador = Classificador(modelo_cfg, codebook, projeto.estado, ollama=Ollama(), progresso=progresso)
    alvo = textos
    if opcoes.somente_amostra:
        alvo = [t for t in textos if t.doc in posicao]
    if opcoes.estimar or opcoes.limite is not None:
        pendentes = classificador.pendentes(alvo)
        faltando = set(pendentes)
        ja = [t for t in alvo if t not in faltando]
        extra = AMOSTRA_ESTIMATIVA if opcoes.estimar else max(0, (opcoes.limite or 0) - len(ja))
        alvo = ja + pendentes[:extra]

    # o resultado cobre tudo o que o cache já tem, não só o alvo desta execução: `--somente-amostra` ou `--limite`
    # depois de uma rodada completa não encolhem a classificação
    no_alvo = {t.doc for t in alvo}
    fora_do_alvo = classificador.do_cache(t for t in textos if t.doc not in no_alvo)

    variaveis = [v.id for v in codebook.variaveis]
    k = classificador.contadores
    parametros = (modelo_cfg.num_ctx, modelo_cfg.temperatura, modelo_cfg.semente, modelo_cfg.pensar)
    execucao = chave_de(classificador.modelo, VERSAO_PROMPT, parametros)[:16]
    # um resultado completo de outra execução (modelo atualizado, outro prompt ou outros parâmetros) não é trocado
    # por um parcial desta (um --estimar ou --limite, ou uma rodada interrompida): só a rodada completa o substitui,
    # mesmo que alguns documentos tenham falhado nas duas tentativas (com temperatura 0 e semente fixa, a falha
    # tende a se repetir, e o resultado novo nunca chegaria)
    anterior = Resultado.ler(projeto.dados / PASTA, modelo_cfg.modelo, codebook.hash())
    protegido = (
        anterior is not None
        and not anterior.parcial
        and (anterior.execucao or anterior.modelo) != (execucao if anterior.execucao else classificador.modelo)
    )
    avisos_gravacao: list[str] = []
    gravou = False  # a última chamada de `gravar` gravou o resultado?
    principal = not opcoes.modelo or opcoes.modelo == cfg.modelos.classificacao.modelo
    assinatura = assinatura_corpus([d.id for d in docs])

    def gravar(resultados: list[Classificacao], *, parcial: bool) -> Resultado:
        """Grava o resultado com o que já foi classificado: no fim, e a cada `GRAVAR_A_CADA` documentos novos,
        com uma exportação para o painel (assim a rodada longa aparece enquanto corre)."""
        nonlocal gravou
        resultados = resultados + fora_do_alvo
        # cobre o corpus: a rodada chegou ao fim, e cada texto foi classificado ou falhou nas duas tentativas
        cobre = not parcial and len(resultados) + len(k.falhas) >= len(textos)
        parcial = parcial or len(resultados) < len(textos)
        gravar_de_fato = not protegido or cobre
        gravou = gravar_de_fato
        # --somente-amostra com o modelo atualizado ou outros parâmetros: as respostas vão para o resultado à parte da
        # amostra, que as métricas da validação comparam com o completo anterior, sem tocar nele
        a_parte = not gravar_de_fato and opcoes.somente_amostra
        if not gravar_de_fato and not avisos_gravacao:
            nome = anterior.modelo.split("@", 1)[0]
            avisos_gravacao.append(
                f"O resultado completo anterior ({nome}, de outra execução) continua valendo para o painel. As "
                "respostas da amostra com a versão nova ficam num resultado à parte, que `mapa validar metricas` "
                f'compara com ele como "{nome.removesuffix(":latest")} (só amostra)". Rode `mapa classificar` sem '
                "--somente-amostra para substituí-lo."
                if a_parte
                else f"O resultado completo anterior ({nome}, de outra execução) foi mantido: esta rodada é "
                "parcial. Rode `mapa classificar` sem --limite/--estimar para substituí-lo."
            )
        linhas = [linha for c in sorted(resultados, key=lambda c: c.doc) for linha in _linhas(c, variaveis)]
        status = Counter(linha["status"] for linha in linhas if linha["status"] != "dispensada")
        total_status = sum(status.values()) or 1
        por_variavel = {}
        for v in variaveis:
            dessa = [linha["status"] for linha in linhas if linha["variavel"] == v and linha["status"] != "dispensada"]
            if dessa:
                por_variavel[v] = round(dessa.count("literal") / len(dessa), 4)
        segundos = [c.segundos for c in resultados]
        resultado = Resultado(
            modelo=classificador.modelo,
            codebook=f"{codebook.nome} {codebook.versao}",
            hash_codebook=codebook.hash(),
            assinatura=assinatura,
            gerado_em=datetime.now(UTC).isoformat(timespec="seconds"),
            documentos=len(textos),
            classificados=len(resultados),
            sem_resumo=len(sem_resumo),
            falhas=k.falhas,
            json_valido_na_primeira=(
                round(sum(c.valida_na_primeira for c in resultados) / len(resultados), 4) if resultados else None
            ),
            evidencia={s: round(status[s] / total_status, 4) for s in ("literal", "aproximada", "ausente")},
            evidencia_por_variavel=por_variavel,
            segundos_por_documento=round(statistics.median(segundos), 2) if segundos else None,
            parcial=parcial or bool(k.falhas),
            execucao=execucao,
            somente_amostra=a_parte,
        )
        if gravar_de_fato or a_parte:
            resultado.gravar(projeto.dados / PASTA, linhas)
        if gravar_de_fato:  # a amostra à parte desta mesma execução ficou repetida
            amostra = Resultado.ler(projeto.dados / PASTA, modelo_cfg.modelo, codebook.hash(), somente_amostra=True)
            if amostra is not None and amostra.execucao == execucao:
                amostra.apagar(projeto.dados / PASTA)
        return resultado

    resultados: list[Classificacao] = []
    try:
        for c in classificador.classificar(alvo):
            resultados.append(c)
            if not c.do_cache and k.novos % GRAVAR_A_CADA == 0:
                gravar(resultados, parcial=True)
                if principal and not protegido:
                    with contextlib.suppress(Exception):  # o painel acompanha; uma falha aqui não para a etapa
                        exportar(projeto)
    except BaseException:
        if k.novos:  # o cache já tem tudo; o resultado parcial deixa o painel em dia com ele
            with contextlib.suppress(Exception):
                gravar(resultados, parcial=True)
        raise
    finally:
        classificador.fim()
        progresso.fim()

    classificados = len(resultados) + len(fora_do_alvo)
    faltam = len(textos) - classificados
    estimativa = None
    if opcoes.estimar and k.segundos:
        estimativa = round(statistics.median(k.segundos) * faltam / max(1, modelo_cfg.concorrencia), 0)
    resultado = gravar(resultados, parcial=False)  # parcial se algo ficou de fora (ver `gravar`)
    json_ok, evidencia, mediana = (
        resultado.json_valido_na_primeira,
        resultado.evidencia,
        resultado.segundos_por_documento,
    )
    resumo = ResumoClassificacao(
        modelo=classificador.modelo,
        documentos=len(textos),
        classificados=classificados,
        do_cache=k.do_cache,
        novos=k.novos,
        falhas=k.falhas,
        sem_resumo=len(sem_resumo),
        json_valido_na_primeira=json_ok,
        evidencia=evidencia,
        segundos_por_documento=mediana,
        pendentes=faltam,
        estimativa_restante_s=estimativa,
        duracao_s=round(time.perf_counter() - t0, 2),
        parcial=resultado.parcial,
        amostra_a_parte=resultado.somente_amostra,
    )
    if k.falhas:
        resumo.avisos.append(
            f"{num(len(k.falhas), 0)} documento(s) sem resposta válida depois de duas tentativas (por exemplo "
            f"{', '.join(k.falhas[:3])}); rode a etapa de novo para tentar outra vez."
        )
    registrar_execucao(
        projeto,
        "classificacao",
        inicio=inicio,
        fim=datetime.now(UTC),
        contagens={
            "classificados": classificados,
            "documentos": len(textos),
            "novos": k.novos,
            "chamadas": k.chamadas,
            "falhas": len(k.falhas),
            "sem_resumo": len(sem_resumo),
        },
        modelos={"classificacao": classificador.modelo},
        parametros={
            "num_ctx": modelo_cfg.num_ctx,
            "temperatura": modelo_cfg.temperatura,
            "semente": modelo_cfg.semente,
            "pensar": modelo_cfg.pensar,
            "concorrencia": modelo_cfg.concorrencia,
            "versao_prompt": VERSAO_PROMPT,
            "parcial": resultado.parcial,
            "somente_amostra": opcoes.somente_amostra,
            # False quando o resultado completo anterior foi mantido: esta execução não é a dos dados
            "gravado": gravou,
        },
    )
    resumo.avisos += avisos_gravacao
    if principal and (gravou or resultado.somente_amostra):  # a amostra à parte entra nas métricas do painel
        resumo.avisos += exportar(projeto)
    return resumo


def classificacao_em_dia(projeto: Projeto) -> bool | None:
    """True se a classificação do modelo principal cobre o corpus e o codebook atuais; False se está desatualizada
    ou incompleta; None se nunca rodou."""
    cfg = projeto.config.modelos.classificacao
    resultado = Resultado.ler(projeto.dados / PASTA, cfg.modelo, projeto.codebook.hash())
    if resultado is None:  # nunca rodou com este modelo, ou rodou com outro codebook
        principal = cfg.modelo.removesuffix(":latest")
        anteriores = [r for r in resultados(projeto.dados / PASTA) if r.modelo.split("@")[0] == principal]
        return False if anteriores else None
    if resultado.parcial:
        return False
    ids = [d.id for d in ler_documentos(projeto.dados / ARQUIVO)]
    return resultado.assinatura == assinatura_corpus(ids)
