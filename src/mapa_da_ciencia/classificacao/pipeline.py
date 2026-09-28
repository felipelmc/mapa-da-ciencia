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
from typing import Any

from ..armazenamento import ARQUIVO, ler_documentos
from ..config import ErroConfig
from ..contrato.exportar import exportar
from ..formatar import num
from ..llm.cache import chave_de
from ..llm.ollama import Ollama
from ..manifesto import registrar_execucao, ultima_execucao
from ..progresso import Progresso, ProgressoNulo
from ..projeto import Projeto
from ..topicos.resultado import assinatura_corpus
from ..validacao.amostra import ler as ler_amostra
from .executor import Classificacao, Classificador, textos_para_classificar
from .prompt import VERSAO_PROMPT
from .resultado import PASTA, Resultado, resultados, valor_como_texto

AMOSTRA_ESTIMATIVA = 5
GRAVAR_A_CADA = 50
# a fração dos textos que pode ficar sem resposta válida numa rodada completa que substitui o resultado completo de
# outra execução (com no mínimo 1 documento): acima disso, a versão nova provavelmente tem um problema
LIMITE_FALHAS = 0.02


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
    a_parte: bool = False  # gravado no resultado à parte da versão nova (`Resultado.a_parte`)

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
    # um resultado completo (de uma rodada que terminou, mesmo com falhas) de outra execução (modelo atualizado, outro
    # prompt ou outros parâmetros) não é trocado por um parcial desta (--somente-amostra, --estimar, --limite ou uma
    # rodada interrompida): só a rodada completa o substitui, mesmo que alguns documentos tenham falhado nas duas
    # tentativas (com temperatura 0 e semente fixa, a falha tende a se repetir, e o resultado novo nunca chegaria),
    # mas não com falhas demais (acima de `LIMITE_FALHAS`: um modelo que devolve JSON inválido em tudo apagaria horas
    # de classificação). Enquanto isso, as respostas da versão nova ficam no resultado à parte, que as métricas da
    # validação comparam com o completo
    anterior = Resultado.ler(projeto.dados / PASTA, modelo_cfg.modelo, codebook.hash())
    protegido = (
        anterior is not None
        and anterior.classificados + len(anterior.falhas) >= anterior.documentos  # a rodada que o gravou terminou
        and not _mesma_execucao(
            projeto,
            anterior,
            execucao,
            classificador.modelo,
            {
                "num_ctx": modelo_cfg.num_ctx,
                "temperatura": modelo_cfg.temperatura,
                "semente": modelo_cfg.semente,
                "pensar": modelo_cfg.pensar,
                "versao_prompt": VERSAO_PROMPT,
            },
        )
    )
    limite_falhas = max(1, int(len(textos) * LIMITE_FALHAS))
    gravou = False  # a última chamada de `gravar` gravou o resultado principal?
    principal = not opcoes.modelo or opcoes.modelo == cfg.modelos.classificacao.modelo
    assinatura = assinatura_corpus([d.id for d in docs])

    def gravar(resultados: list[Classificacao], *, parcial: bool) -> Resultado:
        """Grava o resultado com o que já foi classificado: no fim, e a cada `GRAVAR_A_CADA` documentos novos,
        com uma exportação para o painel (assim a rodada longa aparece enquanto corre)."""
        nonlocal gravou
        resultados = resultados + fora_do_alvo
        # cobre o corpus: a rodada chegou ao fim, cada texto foi classificado ou falhou nas duas tentativas, e as
        # falhas não passam do limite
        cobre = not parcial and len(resultados) + len(k.falhas) >= len(textos) and len(k.falhas) <= limite_falhas
        parcial = parcial or len(resultados) < len(textos)
        gravou = not protegido or cobre
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
            a_parte=not gravou,
        )
        resultado.gravar(projeto.dados / PASTA, linhas)
        # gravado o principal, a versão à parte sai: ou é esta mesma (ficou repetida), ou uma que deixou de ser a mais
        # nova (outra atualização, ou o parâmetro de volta); uma versão à parte nova toma o lugar da anterior
        if gravou and (velha := Resultado.ler(projeto.dados / PASTA, modelo_cfg.modelo, codebook.hash(), a_parte=True)):
            velha.apagar(projeto.dados / PASTA)
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
        a_parte=resultado.a_parte,
    )
    if k.falhas:
        resumo.avisos.append(
            f"{num(len(k.falhas), 0)} documento(s) sem resposta válida depois de duas tentativas (por exemplo "
            f"{', '.join(k.falhas[:3])}). Rodar de novo tenta outra vez, mas com temperatura 0 e semente fixa a falha "
            "tende a se repetir: veja “Documentos que falham sempre” no guia Classificar os resumos."
        )
    if resultado.a_parte:
        nome = anterior.modelo.split("@", 1)[0] if anterior else classificador.modelo.split("@", 1)[0]
        versao_nova = f'"{nome.removesuffix(":latest")} (versão nova)"'
        if len(k.falhas) > limite_falhas and resultado.classificados + len(k.falhas) >= len(textos):
            motivo = (
                f"{num(len(k.falhas), 0)} documentos ficaram sem resposta válida com a versão nova, mais que o limite "
                f"para substituí-lo ({num(limite_falhas, 0)}, 2% dos documentos)"
            )
            conselho = (
                "Confira o modelo e os parâmetros na amostra (`mapa classificar --somente-amostra`) antes de rodar "
                "tudo de novo."
            )
        else:
            motivo = "esta rodada é parcial"
            conselho = "Rode `mapa classificar` sem --somente-amostra, --limite ou --estimar para substituí-lo."
        resumo.avisos.append(
            f"O resultado completo anterior ({nome}, de outra execução) foi mantido: {motivo}. As respostas da versão "
            f"nova ficam num resultado à parte, que `mapa validar metricas` compara com ele como {versao_nova}. "
            + conselho
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
            "execucao": execucao,  # a mesma do resultado: o status escolhe por ela (`manifesto.ultima_classificacao`)
        },
        hash_codebook=resultado.hash_codebook,  # o do começo da etapa, mesmo que o arquivo mude no meio dela
    )
    if principal and gravou:  # a versão à parte não muda o contrato (ver `validacao.metricas.calcular`)
        resumo.avisos += exportar(projeto)
    return resumo


def _mesma_execucao(
    projeto: Projeto, anterior: Resultado, execucao: str, modelo: str, parametros: dict[str, Any]
) -> bool:
    """O resultado `anterior` é desta mesma execução (o mesmo modelo com o digest, a versão do prompt e os
    parâmetros)? Um resultado gravado por uma versão anterior do pacote não tem a marca `execucao`: vale o modelo que
    ele registra e os parâmetros do manifesto da rodada que o gravou (a mais recente com esse modelo, também sem a
    marca). Sem manifesto para conferir, não é: na dúvida, o resultado fica protegido."""
    if anterior.execucao:
        return anterior.execucao == execucao
    if anterior.modelo != modelo:
        return False
    manifesto = ultima_execucao(
        projeto,
        "classificacao",
        lambda m: (
            (m.get("modelos") or {}).get("classificacao") == anterior.modelo
            and "execucao" not in (m.get("parametros") or {})
        ),
    )
    if manifesto is None:
        return False
    gravados = manifesto.get("parametros") or {}
    return all(k in gravados and gravados[k] == v for k, v in parametros.items())


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
