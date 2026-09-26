"""A parte do contrato que vem do codebook, da classificação e da validação: `codebook.json`,
`classificacoes.json`, `validacao.json`, as colunas `cls` de `documentos.json` e as `evidencias` dos detalhes.

Só o modelo principal (`modelos.classificacao.modelo`) vai para o painel, e só com o codebook atual. Na validação,
as divergências publicadas são só as de codificadores de referência: as de pessoas são codificações individuais e
ficam na API local do painel.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from typing import TYPE_CHECKING, Any

from mapa_da_ciencia.contrato import modelos as m

if TYPE_CHECKING:
    from mapa_da_ciencia.classificacao.resultado import Resultado
    from mapa_da_ciencia.config import Codebook
    from mapa_da_ciencia.projeto import Projeto
    from mapa_da_ciencia.validacao.metricas import Validacao


def codebook_contrato(cb: Codebook) -> m.CodebookContrato:
    return m.CodebookContrato(
        nome=cb.nome,
        versao=cb.versao,
        hash=cb.hash(),
        instrucoes=cb.instrucoes,
        variaveis=[
            m.VariavelContrato(
                id=v.id,
                rotulo=v.rotulo,
                tipo=v.tipo,
                pergunta=v.pergunta,
                categorias=[
                    m.CategoriaContrato(
                        valor=c.valor,
                        rotulo=c.rotulo or c.valor.replace("_", " "),
                        definicao=c.definicao,
                        exemplos=c.exemplos,
                    )
                    for c in v.categorias
                ],
            )
            for v in cb.variaveis
        ],
    )


def dicionario_cls(v: Any, valores: list[str]) -> list[str]:
    """Os valores de uma variável em `dicionarios.cls`: as categorias do codebook (categórica), `false`/`true`
    (booleana) ou as combinações que aparecem, como listas JSON (múltipla)."""
    if v.tipo == "categorica":
        return [c.valor for c in v.categorias]
    if v.tipo == "booleana":
        return ["false", "true"]
    return sorted(set(valores), key=lambda x: (len(json.loads(x)), x))


def classificacao_contrato(
    cb: Codebook, resultado: Resultado, linhas: list[dict[str, Any]], n_documentos: int
) -> tuple[m.Classificacoes, dict[str, dict[str, m.Evidencia]]]:
    """`classificacoes.json` e as evidências de cada documento (doc → variável → evidência)."""
    from mapa_da_ciencia.classificacao.codebook import sem_informacao
    from mapa_da_ciencia.classificacao.resultado import valor_do_texto

    variaveis = {v.id: v for v in cb.variaveis}
    evidencias: dict[str, dict[str, m.Evidencia]] = defaultdict(dict)
    contagens: dict[str, Counter[str]] = defaultdict(Counter)
    sem_info: Counter[str] = Counter()
    n: Counter[str] = Counter()
    status: dict[str, Counter[str]] = defaultdict(Counter)
    for linha in linhas:
        v = variaveis.get(linha["variavel"])
        if v is None:
            continue
        valor = valor_do_texto(linha["valor"], v.tipo)
        evidencias[linha["doc"]][v.id] = m.Evidencia(
            valor=valor,
            evidencia=linha["evidencia"],
            status=linha["status"],
            inicio=linha["inicio"],
            fim=linha["fim"],
            campo=linha["campo"],
        )
        n[v.id] += 1
        sem_info[v.id] += sem_informacao(v, valor)
        if linha["status"] != "dispensada":
            status[v.id][linha["status"]] += 1
        if v.tipo == "multipla":
            contagens[v.id].update(valor)
        elif v.tipo != "texto":
            contagens[v.id][linha["valor"]] += 1
    por_variavel = {
        vid: m.VariavelClassificada(
            n=n[vid],
            sem_informacao=round(sem_info[vid] / n[vid], 4),
            evidencia={s: round(k / sum(status[vid].values()), 4) for s, k in sorted(status[vid].items())},
        )
        for vid in variaveis
        if n[vid]
    }
    classificacoes = m.Classificacoes(
        modelo=resultado.modelo,
        hash_codebook=resultado.hash_codebook,
        cobertura=round(resultado.classificados / n_documentos, 4) if n_documentos else 0.0,
        evidencia_literal=resultado.evidencia.get("literal", 0.0),
        contagens={vid: dict(c.most_common()) for vid, c in contagens.items()},
        classificados=resultado.classificados,
        documentos=resultado.documentos,
        sem_resumo=resultado.sem_resumo,
        parcial=resultado.parcial,
        json_valido_na_primeira=resultado.json_valido_na_primeira,
        por_variavel=por_variavel,
    )
    return classificacoes, dict(evidencias)


def colunas_cls(
    cb: Codebook, ids: list[str], linhas: list[dict[str, Any]]
) -> tuple[dict[str, list[int]], dict[str, list[str]]]:
    """As colunas `cls` de `documentos.json` (índice em `dicionarios.cls[variavel]`, ou -1) e os dicionários.
    Variáveis de texto ficam de fora: a resposta de cada documento está nas evidências dos detalhes."""
    por_var: dict[str, dict[str, str]] = defaultdict(dict)
    for linha in linhas:
        por_var[linha["variavel"]][linha["doc"]] = linha["valor"]
    colunas, dicionarios = {}, {}
    for v in cb.variaveis:
        if v.tipo == "texto":
            continue
        valores = por_var.get(v.id, {})
        if v.tipo == "multipla":  # combinações comparadas sem a ordem
            valores = {d: json.dumps(sorted(json.loads(x)), ensure_ascii=False) for d, x in valores.items()}
        dic = dicionario_cls(v, list(valores.values()))
        pos = {x: i for i, x in enumerate(dic)}
        colunas[v.id] = [pos.get(valores[d], -1) if d in valores else -1 for d in ids]
        dicionarios[v.id] = dic
    return colunas, dicionarios


def validacao_contrato(v: Validacao) -> m.Validacao:
    tipos = {p.nome: p.tipo for p in v.participantes}
    return m.Validacao(
        amostra=m.AmostraInfo(
            n=v.amostra["n"], estratificar_por=v.amostra["estratificar_por"], semente=v.amostra["semente"]
        ),
        metricas=[
            m.MetricaVariavel(
                variavel=x.variavel,
                comparacao=x.comparacao,
                n=x.n,
                concordancia=_r(x.concordancia),
                kappa=_r(x.kappa),
                kappa_ic95=(_r(x.kappa_ic95[0]), _r(x.kappa_ic95[1])) if x.kappa_ic95 else None,
                pabak=_r(x.pabak),
                alfa=_r(x.alfa),
                matriz=m.Matriz(rotulos=x.rotulos, valores=x.matriz),
                referencia=x.referencia,
                comparado=x.comparado,
                por_classe=[
                    m.MetricaClasse(
                        rotulo=c.rotulo,
                        suporte=c.suporte,
                        precisao=_r(c.precisao),
                        revocacao=_r(c.revocacao),
                        f1=_r(c.f1),
                    )
                    for c in x.por_classe
                ],
            )
            for x in v.metricas
        ],
        modelos=[p.nome for p in v.participantes if p.tipo == "modelo"],
        divergencias=[
            m.Divergencia(
                doc=d.doc,
                variavel=d.variavel,
                humano=d.valor_codificador,
                modelo=d.valor_modelo,
                evidencia=d.evidencia_modelo,
                codificador=d.codificador,
                status=d.status_evidencia,
                incerto=d.incerto,
            )
            for d in v.divergencias
            if tipos.get(d.codificador) == "referencia"
        ],
        codificadores=[m.Participante(nome=p.nome, tipo=p.tipo, n=p.n) for p in v.participantes],
        modelo_principal=v.modelo_principal,
        hash_codebook=v.hash_codebook,
        comparacoes_modelos=[
            m.ComparacaoModelos(
                variavel=c.variavel,
                referencia=c.referencia,
                modelo_a=c.modelo_a,
                modelo_b=c.modelo_b,
                n=c.n,
                acertos_a=c.acertos_a,
                acertos_b=c.acertos_b,
                p=round(c.p, 6),
            )
            for c in v.comparacoes_modelos
        ],
        evidencia_literal=v.evidencia_literal,
    )


def _r(x: float | None, casas: int = 4) -> float | None:
    return None if x is None else round(x, casas)


def exportar_classificacao(
    projeto: Projeto, arquivos: dict[str, Any], fragmentos: dict[str, m.Fragmento], n_documentos: int, avisos: list[str]
) -> dict[str, Any]:
    """Acrescenta `codebook.json`, `classificacoes.json` (com as colunas `cls` e as evidências, se houver
    documentos exportados) e `validacao.json`. Devolve o que o manifesto precisa: modelo, hash do codebook,
    classificados e validados."""
    from mapa_da_ciencia.classificacao.pipeline import classificacao_em_dia
    from mapa_da_ciencia.classificacao.resultado import PASTA, Resultado, ler_linhas
    from mapa_da_ciencia.validacao import amostra as va
    from mapa_da_ciencia.validacao.metricas import calcular

    info: dict[str, Any] = {}
    if not (projeto.raiz / "codebook.yaml").exists():
        return info
    cb = projeto.codebook
    arquivos["codebook"] = codebook_contrato(cb)
    info["hash_codebook"] = cb.hash()
    modelo = projeto.config.modelos.classificacao.modelo
    resultado = Resultado.ler(projeto.dados / PASTA, modelo, cb.hash())
    if resultado is None:
        if classificacao_em_dia(projeto) is False:
            avisos.append("A classificação é de outro codebook. Rode `mapa classificar` para refazê-la com o atual.")
    else:
        linhas = ler_linhas(projeto.dados / PASTA, modelo, cb.hash())
        classificacoes, evidencias = classificacao_contrato(cb, resultado, linhas, n_documentos)
        arquivos["classificacoes"] = classificacoes
        info |= {"modelo": resultado.modelo, "classificados": resultado.classificados}
        documentos = arquivos.get("documentos")
        if documentos is not None:
            colunas, dicionarios = colunas_cls(cb, documentos.colunas.id, linhas)
            documentos.colunas.cls = colunas
            documentos.dicionarios.cls = dicionarios
            for frag in fragmentos.values():
                for doc, detalhe in frag.documentos.items():
                    if doc in evidencias:
                        detalhe.evidencias = evidencias[doc]
    amostra = va.ler(projeto)
    if amostra is not None:
        v = calcular(projeto)
        codificadas = {c["doc"] for c in va.codificacoes(projeto)} & set(amostra.docs)
        info["validados"] = len(codificadas)
        if v.metricas:
            arquivos["validacao"] = validacao_contrato(v)
    return info
