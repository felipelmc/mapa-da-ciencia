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
    Afiliacoes,
    Agregados,
    ColunasDocumentos,
    Contagens,
    Detalhe,
    DicionariosDocumentos,
    Documentos,
    ExecucaoInfo,
    Fragmento,
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


def _detalhe(doc: Documento, atrib: dict[str, Any], idiomas: list[str]) -> Detalhe:
    resumo = doc.texto_em("resumos", idiomas)
    chaves = [t for t in doc.palavras_chave if t.idioma == (resumo.idioma if resumo else idiomas[0])]
    return Detalhe(
        resumo=resumo.texto if resumo else None,  # no painel local vai tudo; `mapa publicar` (M7) filtra por licença
        idioma=resumo.idioma if resumo else None,
        palavras_chave=list(dict.fromkeys(t.texto for t in (chaves or doc.palavras_chave))),
        autores=[" ".join(p for p in (a.nome, a.sobrenome) if p) for a in doc.autores],
        url=doc.url or (f"https://doi.org/{doc.doi}" if doc.doi else None),
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


def exportar(projeto: Projeto) -> list[str]:
    """Reconstrói `saida/dados/` (o contrato que o painel lê) a partir de `dados/`. Devolve avisos.

    Sempre grava `manifesto.json` e `revistas.json`. Com tópicos em dia (gerados a partir do corpus atual), grava
    também `documentos.json`, `topicos.json`, `agregados.json` e os fragmentos de `detalhes/`. Tudo é escrito
    numa pasta nova, que substitui a antiga de uma vez: o painel nunca vê uma exportação pela metade, e
    arquivos de uma etapa desatualizada não sobram.
    """
    import shutil

    from mapa_da_ciencia.armazenamento import ARQUIVO, cobertura, ler_documentos
    from mapa_da_ciencia.manifesto import ultima_execucao
    from mapa_da_ciencia.topicos.resultado import PASTA, Resultado, assinatura_corpus, ler_atribuicoes

    caminho = projeto.dados / ARQUIVO
    if not caminho.exists():
        return []
    avisos: list[str] = []
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
        else:
            mais, fragmentos = _arquivos_de_topicos(
                projeto, resultado, ler_atribuicoes(projeto.dados / PASTA), docs, [r.id for r in revistas]
            )
            arquivos.update(mais)
            contagens = contagens.model_copy(update={"topicos": len(resultado.topicos)})
            modelos = {"rotulos": "nenhum (palavras-chave)", **resultado.modelos}
            sementes = {"umap": int(resultado.parametros["semente"])}

    manifesto = manifesto_do_projeto(
        projeto,
        api=False,
        contagens=contagens,
        arquivos=["manifesto", *arquivos, *(["detalhes"] if fragmentos else [])],
    )
    duracoes = {
        etapa: round(m["duracao_s"], 1)
        for etapa in ("coleta", "embeddings", "topicos")
        if (m := ultima_execucao(projeto, etapa))
    }
    execucao = manifesto.execucao.model_copy(
        update={"duracao_s": duracoes, "sementes": sementes, "modelos": {**manifesto.execucao.modelos, **modelos}}
    )
    manifesto = manifesto.model_copy(update={"licencas": cob["licencas"], "execucao": execucao})

    destino = projeto.saida / "dados"
    novo = projeto.saida / "dados.novo"
    velho = projeto.saida / "dados.velho"
    shutil.rmtree(novo, ignore_errors=True)
    shutil.rmtree(velho, ignore_errors=True)
    escrever_dados(novo, {"manifesto": manifesto, **arquivos}, fragmentos)
    if destino.exists():
        destino.rename(velho)
    novo.rename(destino)
    shutil.rmtree(velho, ignore_errors=True)
    return avisos
