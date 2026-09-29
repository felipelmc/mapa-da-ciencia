"""Escrita dos arquivos do contrato e dos JSON Schemas."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from mapa_da_ciencia import __version__
from mapa_da_ciencia.contrato.modelos import (
    ARQUIVOS,
    NAO_IDENTIFICADA,
    SIGLAS_UF,
    Afiliacoes,
    Agregados,
    ColunasAfiliacoes,
    ColunasDocumentos,
    Contagens,
    Detalhe,
    DicionariosAfiliacoes,
    DicionariosDocumentos,
    Documentos,
    ExecucaoInfo,
    Fragmento,
    Instituicao,
    Macrotema,
    Manifesto,
    MetodoTendencia,
    Outliers,
    ProjetoInfo,
    RecorteInfo,
    Revista,
    Revistas,
    Serie,
    Tendencia,
    Topico,
    Topicos,
    fragmento_de,
)
from mapa_da_ciencia.pastas import substituir_conteudo
from mapa_da_ciencia.projeto import Projeto

if TYPE_CHECKING:
    from mapa_da_ciencia.documento import Documento


def manifesto_do_projeto(
    projeto: Projeto,
    *,
    api: bool,
    contagens: Contagens | None = None,
    arquivos: list[str] | None = None,
) -> Manifesto:
    """Manifesto a partir da configuração do projeto. Sem argumentos extras, descreve um projeto vazio."""
    cfg = projeto.config
    fontes = [f"scielo:{cfg.fontes.scielo.colecao}"] if cfg.fontes.scielo else []
    if cfg.fontes.openalex.enriquecer or cfg.fontes.openalex.consulta:
        fontes.append("openalex")
    fontes += [f"importar:{p.name}" for p in cfg.fontes.importar]
    if cfg.fontes.openalex.consulta:
        fontes.append(f"consulta:{cfg.fontes.openalex.consulta}")
    return Manifesto(
        api=api,
        gerado_em=datetime.now(UTC),
        projeto=ProjetoInfo(nome=cfg.nome, titulo=cfg.titulo, descricao=cfg.descricao),
        recorte=RecorteInfo(
            anos=cfg.recorte.anos,
            fontes=fontes,
            idioma_analise=cfg.recorte.idioma_analise,
            idioma_exibicao=cfg.recorte.idioma_exibicao,
        ),
        contagens=contagens or Contagens(documentos=0),
        arquivos=arquivos or ["manifesto"],
        execucao=ExecucaoInfo(
            versao_pacote=__version__,
            modelos={
                "embeddings": cfg.modelos.embeddings.modelo,
                "classificacao": cfg.modelos.classificacao.modelo,
                "rotulos": cfg.modelos.rotulos.modelo,
            },
        ),
    )


def _rotulos_sem_registro(projeto: Projeto, resultado: Any) -> str:
    """O modelo dos rótulos quando a execução dos tópicos não o registrou. Sem rótulos do modelo, as palavras-chave;
    com eles, foram reaproveitados de uma execução anterior (antes da 2.1.1, o reaproveitamento não levava o modelo
    junto): o modelo configurado, sem o digest, que não se sabe mais."""
    if any(t.rotulo_fonte == "llm" for t in resultado.topicos):
        return f"{projeto.config.modelos.rotulos.modelo} (numa execução anterior)"
    return "nenhum (palavras-chave)"


def schemas() -> dict[str, dict]:
    """JSON Schema (forma serializada) de cada arquivo do contrato."""
    return {nome: modelo.model_json_schema(mode="serialization") for nome, modelo in ARQUIVOS.items()}


def escrever_schemas(destino: Path) -> list[Path]:
    destino.mkdir(parents=True, exist_ok=True)
    escritos = []
    for nome, schema in schemas().items():
        arq = destino / f"{nome}.schema.json"
        arq.write_text(json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        escritos.append(arq)
    return escritos


def _serializar(obj: BaseModel) -> str:
    # Compacto: documentos.json e afiliacoes.json chegam a ~1 MB no piloto.
    return json.dumps(obj.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":"))


def escrever_dados(destino: Path, arquivos: dict[str, BaseModel], fragmentos: dict[str, Fragmento]) -> list[Path]:
    """Escreve `<nome>.json` para cada arquivo e `detalhes/<xx>.json` para cada fragmento.

    Cada objeto é revalidado contra o seu modelo antes de ser escrito.
    """
    destino.mkdir(parents=True, exist_ok=True)
    escritos = []
    for nome, obj in arquivos.items():
        modelo = ARQUIVOS[nome]
        modelo.model_validate(obj.model_dump())
        arq = destino / f"{nome}.json"
        arq.write_text(_serializar(obj), encoding="utf-8")
        escritos.append(arq)
    pasta = destino / "detalhes"
    if fragmentos:
        pasta.mkdir(exist_ok=True)
    for chave, frag in sorted(fragmentos.items()):
        arq = pasta / f"{chave}.json"
        arq.write_text(_serializar(frag), encoding="utf-8")
        escritos.append(arq)
    return escritos


def _revistas(caminho: Path) -> list[Revista]:
    from mapa_da_ciencia.armazenamento import conectar
    from mapa_da_ciencia.fontes import revistas as retrato

    con = conectar(caminho)
    try:
        linhas = con.execute(
            """SELECT coalesce(revista_acronimo, revista_issn, '?'), revista_issn, any_value(revista_titulo), count(*)
               FROM documentos GROUP BY 1, 2 ORDER BY 4 DESC, 1"""
        ).fetchall()
    finally:
        con.close()
    lista = []
    for acronimo, issn, titulo, n in linhas:
        conhecida = retrato.por_issn(issn) if issn else None
        areas = list(conhecida.areas) if conhecida else []
        lista.append(Revista(id=acronimo, issn=issn or "", titulo=titulo or acronimo, areas=areas, n=n))
    return lista


def _autor_curto(doc: Documento) -> str:
    if not doc.autores:
        return ""
    a = doc.autores[0]
    primeiro = f"{a.sobrenome}, {a.nome[0]}." if a.sobrenome and a.nome else (a.sobrenome or a.nome or "")
    return primeiro + (f"; +{len(doc.autores) - 1}" if len(doc.autores) > 1 else "")


def _url_segura(url: str | None) -> str | None:
    """Só endereços http(s) viram link no cartão (um `javascript:` vindo de uma fonte externa não)."""
    return url if url and url.lower().startswith(("http://", "https://")) else None


def _detalhe(doc: Documento, atrib: dict[str, Any], idiomas: list[str]) -> Detalhe:
    resumo = doc.texto_em("resumos", idiomas)
    chaves = [t for t in doc.palavras_chave if t.idioma == (resumo.idioma if resumo else idiomas[0])]
    return Detalhe(
        resumo=resumo.texto if resumo else None,  # no painel local vai tudo; `mapa publicar` (M7) filtra por licença
        idioma=resumo.idioma if resumo else None,
        palavras_chave=list(dict.fromkeys(t.texto for t in (chaves or doc.palavras_chave))),
        autores=[" ".join(p for p in (a.nome, a.sobrenome) if p) for a in doc.autores],
        url=_url_segura(doc.url) or (f"https://doi.org/{doc.doi}" if doc.doi else None),
        licenca=doc.licenca,
        licenca_fonte=doc.licenca_fonte,
        idioma_analise=atrib["idioma_analise"],
        fonte_analise=atrib["fonte_analise"],
    )


def tendencia_contrato(serie: list[int], total: list[int], anos: list[int]) -> Tendencia:
    """A tendência da série (ADR 0009), arredondada para o contrato."""
    from mapa_da_ciencia.topicos.tendencia import tendencia

    t = tendencia(serie, total, anos)
    r = lambda v: None if v is None else round(v, 6)  # noqa: E731
    return Tendencia(
        direcao=t.direcao,
        inclinacao=r(t.inclinacao),
        erro_padrao=r(t.erro_padrao),
        ic95=(r(t.ic95[0]), r(t.ic95[1])) if t.ic95 else None,
        dispersao=r(t.dispersao),
        prop_inicio=r(t.prop_inicio),
        prop_fim=r(t.prop_fim),
        pp_periodo=r(t.pp_periodo),
        pp_por_ano=r(t.pp_por_ano),
        anos=t.anos,
        motivo=t.motivo,
    )


def agregados_geograficos(afiliacoes: Afiliacoes) -> dict[str, Any]:
    """Os campos geográficos de `agregados.json`, calculados da tabela longa de afiliações (o gabarito)."""
    from collections import defaultdict

    c, dic = afiliacoes.colunas, afiliacoes.dicionarios
    frac: dict[str, dict[str, float]] = {
        "uf": defaultdict(float),
        "pais": defaultdict(float),
        "inst": defaultdict(float),
    }
    docs: dict[str, dict[str, set[int]]] = {"uf": defaultdict(set), "pais": defaultdict(set), "inst": defaultdict(set)}
    sem_afiliacao = sem_pais = 0.0
    for doc, inst, uf, pais, peso in zip(c.doc, c.instituicao, c.uf, c.pais, c.peso, strict=True):
        if inst < 0:
            sem_afiliacao += peso
        else:
            frac["inst"][dic.instituicao[inst].id] += peso
            docs["inst"][dic.instituicao[inst].id].add(doc)
        if pais < 0:
            sem_pais += peso
        else:
            frac["pais"][dic.pais[pais]] += peso
            docs["pais"][dic.pais[pais]].add(doc)
        if uf >= 0:
            frac["uf"][dic.uf[uf]] += peso
            docs["uf"][dic.uf[uf]].add(doc)
    r = lambda d: {k: round(v, 4) for k, v in sorted(d.items())}  # noqa: E731
    n = lambda d: {k: len(v) for k, v in sorted(d.items())}  # noqa: E731
    return {
        "uf": r(frac["uf"]),
        "pais": r(frac["pais"]),
        "instituicao": r(frac["inst"]),
        "uf_inteiro": n(docs["uf"]),
        "pais_inteiro": n(docs["pais"]),
        "instituicao_inteiro": n(docs["inst"]),
        "sem_afiliacao": round(sem_afiliacao, 4),
        "sem_pais": round(sem_pais, 4),
    }


def arquivo_de_afiliacoes(
    pesos: list[dict[str, Any]], instituicoes: list[dict[str, Any]], indice_doc: dict[str, int]
) -> tuple[Afiliacoes, int]:
    """`afiliacoes.json` a partir de `dados/geografia/`, e quantos documentos têm uma instituição identificada.

    As instituições vão da de maior peso à de menor (a "não identificada" no fim); as UFs são as 27, em ordem; os
    países, os presentes. Uma linha por documento × (instituição, UF, país), com o peso somado.
    """
    from collections import defaultdict

    from mapa_da_ciencia.geografia.resultado import id_no_contrato

    ordem = sorted(instituicoes, key=lambda i: (-i["peso"], i["id"]))
    insts = [
        Instituicao(id=id_no_contrato(i), nome=i["nome"], sigla=i["sigla"], uf=i["uf"], pais=i["pais"] or "")
        for i in ordem
    ]
    pos_inst = {i["id"]: k for k, i in enumerate(ordem)}
    if any(p["instituicao"] == NAO_IDENTIFICADA for p in pesos):
        pos_inst[NAO_IDENTIFICADA] = len(insts)
        insts.append(Instituicao(id=NAO_IDENTIFICADA, nome="Instituição não identificada", pais=""))
    paises = sorted({p["pais"] for p in pesos if p["pais"]})
    linhas: dict[tuple[int, int, int, int], float] = defaultdict(float)
    for p in pesos:
        if p["doc"] not in indice_doc:
            continue
        chave = (
            indice_doc[p["doc"]],
            pos_inst[p["instituicao"]] if p["instituicao"] else -1,
            SIGLAS_UF.index(p["uf"]) if p["uf"] else -1,
            paises.index(p["pais"]) if p["pais"] else -1,
        )
        linhas[chave] += p["peso"]
    colunas: dict[str, list] = defaultdict(list)
    for (doc, inst, uf, pais), peso in sorted(linhas.items()):
        for nome, valor in (("doc", doc), ("instituicao", inst), ("uf", uf), ("pais", pais), ("peso", round(peso, 6))):
            colunas[nome].append(valor)
    identificada = pos_inst.get(NAO_IDENTIFICADA)
    com_instituicao = len({doc for (doc, inst, _, _) in linhas if inst >= 0 and inst != identificada})
    afiliacoes = Afiliacoes(
        n=len(linhas),
        colunas=ColunasAfiliacoes(**{k: colunas.get(k, []) for k in ("doc", "instituicao", "uf", "pais", "peso")}),
        dicionarios=DicionariosAfiliacoes(instituicao=insts, uf=list(SIGLAS_UF), pais=paises),
    )
    return afiliacoes, com_instituicao


def _serie(por_ano: dict[int, int], total_ano: dict[int, int], anos: list[int]) -> Serie:
    return Serie(
        n=[por_ano.get(ano, 0) for ano in anos],
        prop=[round(por_ano.get(ano, 0) / total_ano[ano], 5) if total_ano.get(ano) else 0.0 for ano in anos],
    )


def _arquivos_de_topicos(
    projeto: Projeto, resultado: Any, atribuicoes: list[dict[str, Any]], docs: dict[str, Documento], revistas: list[str]
) -> tuple[dict[str, BaseModel], dict[str, Fragmento]]:
    """documentos.json, topicos.json, agregados.json e os fragmentos de detalhes."""
    from collections import Counter, defaultdict

    cfg = projeto.config
    idiomas = [cfg.recorte.idioma_exibicao, cfg.recorte.idioma_analise]
    indice = {a["id"]: i for i, a in enumerate(atribuicoes)}
    linhas = [(a, docs[a["id"]]) for a in atribuicoes]
    idiomas_dic: list[str] = []
    colunas: dict[str, list] = defaultdict(list)
    for a, d in linhas:
        titulo = d.texto_em("titulos", idiomas)
        resumo = d.texto_em("resumos", idiomas)
        idioma = (resumo.idioma if resumo else None) or "?"
        if idioma not in idiomas_dic:
            idiomas_dic.append(idioma)
        colunas["id"].append(d.id)
        colunas["doi"].append(d.doi)
        colunas["titulo"].append(titulo.texto if titulo else "")
        colunas["ano"].append(d.ano)
        colunas["revista"].append(revistas.index(d.chave_revista))
        colunas["idioma"].append(idiomas_dic.index(idioma))
        colunas["x"].append(round(a["x"], 4))
        colunas["y"].append(round(a["y"], 4))
        colunas["topico"].append(a["topico"])
        colunas["atribuicao"].append(0 if a["atribuicao"] == "cluster" else 1)
        colunas["autores_curto"].append(_autor_curto(d))
        colunas["vizinhos"].append([indice[v] for v in a["vizinhos"] if v in indice])
    documentos = Documentos(
        n=len(linhas),
        colunas=ColunasDocumentos(**colunas),
        dicionarios=DicionariosDocumentos(revista=revistas, idioma=idiomas_dic),
    )

    anos_docs = [d.ano for _, d in linhas]
    anos = list(range(min(anos_docs), max(anos_docs) + 1))
    total_ano = Counter(anos_docs)
    membros: dict[int, list[Documento]] = defaultdict(list)
    for a, d in linhas:
        membros[a["topico"]].append(d)
    ruido_ano = Counter(d.ano for a, d in linhas if a["atribuicao"] == "vizinho")
    total = [total_ano[ano] for ano in anos]
    topicos = []
    por_ano_topico: dict[int, Counter[int]] = {}
    for t in resultado.topicos:
        docs_t = membros.get(t.id, [])
        por_ano = Counter(d.ano for d in docs_t)
        por_ano_topico[t.id] = por_ano
        topicos.append(
            Topico(
                id=t.id,
                macro_id=t.macro,
                rotulo=t.rotulo,
                descricao=t.descricao,
                palavras_chave=t.palavras,
                n=len(docs_t),
                centroide=t.centroide,
                cor=t.cor,
                serie=_serie(por_ano, total_ano, anos),
                por_revista=dict(sorted(Counter(d.chave_revista for d in docs_t).items())),
                representativos=t.representativos,
                rotulo_fonte=t.rotulo_fonte,
                n_nucleo=t.n_nucleo,
                tendencia=tendencia_contrato([por_ano[ano] for ano in anos], total, anos),
            )
        )
    macrotemas = []
    for m in resultado.macrotemas:
        por_ano_m = sum((por_ano_topico[t] for t in m.topicos), Counter())
        macrotemas.append(
            Macrotema(
                id=m.id,
                rotulo=m.rotulo,
                cor=m.cor,
                topicos=m.topicos,
                descricao=m.descricao,
                serie=_serie(por_ano_m, total_ano, anos),
                tendencia=tendencia_contrato([por_ano_m[ano] for ano in anos], total, anos),
            )
        )
    sem_topico_ano = Counter(d.ano for a, d in linhas if a["topico"] < 0)
    topicos_arq = Topicos(
        anos=anos,
        total_por_ano=total,
        parametros={k: v for k, v in resultado.parametros.items() if isinstance(v, str | int | float)},
        estabilidade_ari=resultado.estabilidade_ari,
        macrotemas=macrotemas,
        topicos=topicos,
        outliers=Outliers(
            n=resultado.ruido,
            reatribuidos=resultado.reatribuidos,
            por_ano=[ruido_ano[ano] for ano in anos],
            sem_topico_por_ano=[sem_topico_ano[ano] for ano in anos],
        ),
        metodo_tendencia=MetodoTendencia(),
    )
    trio = Counter((a["topico"], d.ano, d.chave_revista) for a, d in linhas)
    agregados = Agregados(
        topico_ano_revista=[(t, ano, r, n) for (t, ano, r), n in sorted(trio.items())], uf={}, pais={}
    )
    fragmentos: dict[str, dict[str, Detalhe]] = defaultdict(dict)
    for a, d in linhas:
        fragmentos[fragmento_de(d.id)][d.id] = _detalhe(d, a, idiomas)
    return (
        {"documentos": documentos, "topicos": topicos_arq, "agregados": agregados},
        {k: Fragmento(fragmento=k, documentos=v) for k, v in fragmentos.items()},
    )


def _geografia(
    projeto: Projeto, arquivos: dict[str, BaseModel], avisos: list[str], desatualizadas: list[str]
) -> int | None:
    """Acrescenta `afiliacoes.json` e os agregados geográficos, se a geografia estiver em dia. Devolve quantos
    documentos têm instituição identificada (ou None, sem geografia)."""
    from mapa_da_ciencia.geografia.pipeline import geografia_em_dia
    from mapa_da_ciencia.geografia.resultado import PASTA as PASTA_GEO
    from mapa_da_ciencia.geografia.resultado import ler_instituicoes, ler_pesos

    em_dia = geografia_em_dia(projeto)
    if em_dia is None:
        return None
    if not em_dia:
        avisos.append(
            "A geografia é de antes da última coleta ou das últimas correções. Rode `mapa geografia` para atualizá-la."
        )
        desatualizadas.append("geografia")
        return None
    documentos = arquivos["documentos"]
    indice_doc = {id_: i for i, id_ in enumerate(documentos.colunas.id)}  # type: ignore[attr-defined]
    pasta = projeto.dados / PASTA_GEO
    afiliacoes, com_instituicao = arquivo_de_afiliacoes(ler_pesos(pasta), ler_instituicoes(pasta), indice_doc)
    arquivos["afiliacoes"] = afiliacoes
    arquivos["agregados"] = arquivos["agregados"].model_copy(update=agregados_geograficos(afiliacoes))
    return com_instituicao


def _redes(
    projeto: Projeto,
    arquivos: dict[str, BaseModel],
    avisos: list[str],
    desatualizadas: list[str],
    mudancas: dict[str, list[str]],
) -> None:
    """Acrescenta `redes.json` e `citacoes.json` se as redes estiverem em dia com o corpus e as entradas; senão, diz o
    que mudou e marca a etapa como desatualizada no manifesto (a vista diz o que rodar, em vez de "sem redes")."""
    from mapa_da_ciencia.contrato.redes import instituicoes_fora_de_afiliacoes, redes_contrato
    from mapa_da_ciencia.redes.pipeline import o_que_mudou, redes_em_dia

    estado = redes_em_dia(projeto)
    if estado is None:
        return
    if estado is False:
        mudancas["redes"] = o_que_mudou(projeto)
        mudou = " e ".join(mudancas["redes"]) or "as entradas"
        avisos.append(
            f"As redes ficaram desatualizadas (mudou {mudou} depois da última `mapa redes`): rode `mapa redes`."
        )
        desatualizadas.append("redes")
        return
    documentos = arquivos["documentos"]
    ids_macros = [mt.id for mt in arquivos["topicos"].macrotemas]  # type: ignore[attr-defined]
    redes, citacoes, gabarito = redes_contrato(projeto, list(documentos.colunas.id), ids_macros)
    if fora := instituicoes_fora_de_afiliacoes(redes, arquivos.get("afiliacoes")):  # type: ignore[arg-type]
        avisos.append(
            f"{len(fora)} instituição(ões) da rede sem registro em afiliacoes.json (por exemplo, {fora[0]}): a rede de "
            "instituições ficou de fora. Rode `mapa geografia` e `mapa redes`."
        )
        redes = redes.model_copy(update={"instituicoes": None})
    arquivos["redes"] = redes
    if citacoes is not None:
        arquivos["citacoes"] = citacoes
    arquivos["agregados"] = arquivos["agregados"].model_copy(update=gabarito)


def exportar(projeto: Projeto) -> list[str]:
    """Reconstrói `saida/dados/` (o contrato que o painel lê) a partir de `dados/`. Devolve avisos.

    Sempre grava `manifesto.json`, `revistas.json` e `codebook.json`. Com tópicos em dia (gerados a partir do
    corpus atual), grava também `documentos.json`, `topicos.json`, `agregados.json` e os fragmentos de
    `detalhes/`; com a geografia também em dia, `afiliacoes.json` e os campos geográficos de `agregados.json`.
    Com a classificação do modelo principal e do codebook atual, `classificacoes.json`, as colunas `cls` e as
    evidências dos detalhes; com a amostra de validação respondida, `validacao.json`. Tudo é escrito
    numa pasta nova e posto no lugar arquivo por arquivo, com o manifesto por último
    (`pastas.substituir_conteudo`, que mantém a pasta por causa do iCloud Drive); arquivos de uma etapa
    desatualizada não sobram.
    """
    import shutil

    from mapa_da_ciencia.armazenamento import ARQUIVO, cobertura, ler_documentos
    from mapa_da_ciencia.manifesto import ultima_classificacao, ultima_execucao
    from mapa_da_ciencia.topicos.resultado import PASTA, Resultado, assinatura_corpus, ler_atribuicoes

    caminho = projeto.dados / ARQUIVO
    if not caminho.exists():
        return []
    avisos: list[str] = []
    desatualizadas: list[str] = []
    mudancas: dict[str, list[str]] = {}
    cob = cobertura(caminho)
    revistas = _revistas(caminho)
    arquivos: dict[str, BaseModel] = {"revistas": Revistas(revistas=revistas)}
    fragmentos: dict[str, Fragmento] = {}
    contagens = Contagens(documentos=cob["documentos"], com_afiliacao=cob["com_afiliacao"])
    modelos: dict[str, str] = {}
    sementes: dict[str, int] = {}

    resultado = Resultado.ler(projeto.dados / PASTA)
    if resultado is not None:
        docs = {d.id: d for d in ler_documentos(caminho)}
        if resultado.assinatura != assinatura_corpus(list(docs)):
            avisos.append("Os tópicos foram gerados antes da última coleta. Rode `mapa topicos` para atualizá-los.")
            desatualizadas.append("topicos")
        else:
            mais, fragmentos = _arquivos_de_topicos(
                projeto, resultado, ler_atribuicoes(projeto.dados / PASTA), docs, [r.id for r in revistas]
            )
            arquivos.update(mais)
            contagens = contagens.model_copy(update={"topicos": len(resultado.topicos)})
            modelos = {"rotulos": _rotulos_sem_registro(projeto, resultado), **resultado.modelos}
            sementes = {"umap": int(resultado.parametros["semente"])}
            geo = _geografia(projeto, arquivos, avisos, desatualizadas)
            if geo is not None:
                contagens = contagens.model_copy(update={"com_instituicao": geo})
            _redes(projeto, arquivos, avisos, desatualizadas, mudancas)

    from mapa_da_ciencia.contrato.classificacao import exportar_classificacao

    cls = exportar_classificacao(projeto, arquivos, fragmentos, cob["documentos"], avisos)
    contagens = contagens.model_copy(
        update={"classificados": cls.get("classificados", 0), "validados": cls.get("validados", 0)}
    )
    if "modelo" in cls:
        modelos["classificacao"] = cls["modelo"]
    from mapa_da_ciencia.classificacao.pipeline import classificacao_em_dia

    if "classificacoes" not in arquivos and classificacao_em_dia(projeto) is False:
        desatualizadas.append("classificacao")
    manifesto = manifesto_do_projeto(
        projeto,
        api=False,
        contagens=contagens,
        arquivos=["manifesto", *arquivos, *(["detalhes"] if fragmentos else [])],
    )
    duracoes = {
        etapa: round(m["duracao_s"], 1)
        for etapa in ("coleta", "embeddings", "topicos", "geografia", "redes", "classificacao")
        if (m := ultima_classificacao(projeto) if etapa == "classificacao" else ultima_execucao(projeto, etapa))
    }
    execucao = manifesto.execucao.model_copy(
        update={
            "duracao_s": duracoes,
            "sementes": sementes,
            "modelos": {**manifesto.execucao.modelos, **modelos},
            "hash_codebook": cls.get("hash_codebook"),
        }
    )
    manifesto = manifesto.model_copy(
        update={
            "licencas": cob["licencas"],
            "execucao": execucao,
            "desatualizadas": desatualizadas,
            "mudancas": mudancas,
        }
    )

    novo = projeto.saida / "dados.novo"
    shutil.rmtree(novo, ignore_errors=True)
    escrever_dados(novo, {"manifesto": manifesto, **arquivos}, fragmentos)
    substituir_conteudo(novo, projeto.saida / "dados")
    return avisos
