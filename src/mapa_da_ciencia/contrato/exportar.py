"""Escrita dos arquivos do contrato e dos JSON Schemas."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from mapa_da_ciencia import __version__
from mapa_da_ciencia.contrato.modelos import (
    ARQUIVOS,
    Contagens,
    ExecucaoInfo,
    Fragmento,
    Manifesto,
    ProjetoInfo,
    RecorteInfo,
    Revista,
    Revistas,
)
from mapa_da_ciencia.projeto import Projeto


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
    pasta.mkdir(exist_ok=True)
    for chave, frag in sorted(fragmentos.items()):
        arq = pasta / f"{chave}.json"
        arq.write_text(_serializar(frag), encoding="utf-8")
        escritos.append(arq)
    return escritos


def exportar_coleta(projeto: Projeto, *, duracao_s: float | None = None) -> list[Path]:
    """Depois da coleta: `manifesto.json` com as contagens e `revistas.json`, para o painel já mostrar o corpus.

    Com isso a capa do painel já mostra documentos, revistas e período. As etapas seguintes (tópicos,
    geografia...) acrescentam os seus arquivos e reescrevem o manifesto com a lista completa.
    """
    from mapa_da_ciencia.armazenamento import ARQUIVO, cobertura, conectar
    from mapa_da_ciencia.fontes import revistas as retrato

    caminho = projeto.dados / ARQUIVO
    cob = cobertura(caminho)
    con = conectar(caminho)
    try:
        linhas = con.execute(
            """SELECT coalesce(revista_acronimo, revista_issn, '?'), revista_issn, any_value(revista_titulo), count(*)
               FROM documentos GROUP BY 1, 2 ORDER BY 4 DESC"""
        ).fetchall()
    finally:
        con.close()
    lista = []
    for acronimo, issn, titulo, n in linhas:
        conhecida = retrato.por_issn(issn) if issn else None
        lista.append(
            Revista(
                id=acronimo,
                issn=issn or "",
                titulo=titulo or acronimo,
                areas=list(conhecida.areas) if conhecida else [],
                n=n,
            )
        )
    manifesto = manifesto_do_projeto(
        projeto,
        api=False,
        contagens=Contagens(documentos=cob["documentos"], com_afiliacao=cob["com_afiliacao"]),
        arquivos=["manifesto", "revistas"],
    )
    execucao = manifesto.execucao.model_copy(
        update={"duracao_s": {"coleta": round(duracao_s, 1)} if duracao_s is not None else {}}
    )
    manifesto = manifesto.model_copy(update={"licencas": cob["licencas"], "execucao": execucao})
    destino = projeto.saida / "dados"
    return escrever_dados(destino, {"manifesto": manifesto, "revistas": Revistas(revistas=lista)}, {})
