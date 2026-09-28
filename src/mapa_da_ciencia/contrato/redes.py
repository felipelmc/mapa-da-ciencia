"""`redes.json` e `citacoes.json`: as redes do projeto no formato do contrato, a partir de `dados/redes/`.

Os documentos entram pelo índice deles em `documentos.json` (a mesma ordem), para o navegador recalcular as arestas
no recorte (anos, revistas, tópicos) sem mandar uma lista de documentos por aresta. Nenhum ORCID e nenhum e-mail:
as pessoas têm um id publicado (um *hash*) e o nome.
"""

from __future__ import annotations

from typing import Any

from ..armazenamento import ler_tabela
from ..projeto import Projeto
from . import modelos as m


def instituicoes_fora_de_afiliacoes(redes: m.Redes, afiliacoes: m.Afiliacoes | None) -> list[str]:
    """Os ids de instituição de `redes.json` que `afiliacoes.json` não conhece (deve ser nenhum: o navegador acha o
    nome, a sigla e os documentos de cada instituição da rede por esse id)."""
    if redes.instituicoes is None:
        return []
    conhecidos = {i.id for i in afiliacoes.dicionarios.instituicao} if afiliacoes else set()
    return [i for i in redes.instituicoes.id if i not in conhecidos]


def _numero(x: Any) -> float | None:
    return None if x is None else round(float(x), 4)


def redes_contrato(
    projeto: Projeto, ids_documentos: list[str], n_macrotemas: int
) -> tuple[m.Redes, m.Citacoes | None, dict[str, Any]]:
    """Os dois arquivos e o que vai para o gabarito (`agregados`)."""
    from ..redes.pipeline import PASTA, ResultadoRedes

    pasta = projeto.dados / PASTA
    resultado = ResultadoRedes.ler(pasta)
    indice = {d: i for i, d in enumerate(ids_documentos)}
    pessoas = ler_tabela(pasta / "pessoas.parquet")
    pos_pessoa = {p["id"]: i for i, p in enumerate(pessoas)}
    autorias = [a for a in ler_tabela(pasta / "autorias.parquet") if a["doc"] in indice]
    instituicoes = ler_tabela(pasta / "instituicoes.parquet")
    arestas = ler_tabela(pasta / "arestas.parquet")
    comunidades = ler_tabela(pasta / "comunidades.parquet")
    colaboracao = ler_tabela(pasta / "colaboracao.parquet")
    redes = m.Redes(
        pessoas=m.ColunasPessoas(
            id=[p["id"] for p in pessoas],
            nome=[p["nome"] for p in pessoas],
            documentos=[p["documentos"] for p in pessoas],
            grau=[p["grau"] for p in pessoas],
            comunidade=[p["comunidade"] for p in pessoas],
            x=[_numero(p["x"]) for p in pessoas],
            y=[_numero(p["y"]) for p in pessoas],
        ),
        autorias=m.AutoriasRede(
            doc=[indice[a["doc"]] for a in autorias], pessoa=[pos_pessoa[a["pessoa"]] for a in autorias]
        ),
        instituicoes=m.ColunasInstituicoesRede(
            id=[i["id"] for i in instituicoes],
            grau=[i["grau"] for i in instituicoes],
            comunidade=[i["comunidade"] for i in instituicoes],
            x=[round(i["x"], 4) for i in instituicoes],
            y=[round(i["y"], 4) for i in instituicoes],
        )
        if instituicoes
        else None,
        comunidades=[
            m.ComunidadeRede(
                rede=c["rede"],
                id=c["id"],
                n=c["n"],
                documentos=c["documentos"],
                macro=c["macro"],
                topicos=list(c["topicos"] or []),
                rotulo=c["rotulo"],
            )
            for c in comunidades
        ],
        metricas={k: m.MetricasRede(**v) for k, v in (resultado.metricas if resultado else {}).items()},
        colaboracao=[m.ColaboracaoAno(**c) for c in colaboracao],
        parametros=resultado.parametros if resultado else {},
    )
    gabarito: dict[str, Any] = {
        "arestas_coautoria": sum(1 for a in arestas if a["rede"] == "coautoria"),
        "uf_pares": [(a["a"], a["b"], round(a["peso"], 6), a["documentos"]) for a in arestas if a["rede"] == "ufs"],
    }
    citacoes = None
    if (pasta / "canone.parquet").exists() and resultado and resultado.cobertura_citacoes:
        from ..armazenamento import ARQUIVO, ler_documentos
        from ..topicos.resultado import PASTA as PASTA_TOPICOS
        from ..topicos.resultado import Resultado as ResultadoTopicos
        from ..topicos.resultado import ler_atribuicoes

        internas = [c for c in ler_tabela(pasta / "citacoes.parquet") if c["de"] in indice and c["para"] in indice]
        canone = ler_tabela(pasta / "canone.parquet")
        n_refs = {d: -1 for d in ids_documentos}
        from ..armazenamento import ARQUIVO_REFERENCIAS

        obra_do_doc = {d.openalex_id: d.id for d in ler_documentos(projeto.dados / ARQUIVO) if d.openalex_id}
        for r in ler_tabela(projeto.dados / ARQUIVO_REFERENCIAS):
            doc = obra_do_doc.get(r["obra"])
            if doc in n_refs:
                n_refs[doc] = max(n_refs[doc], 0) + 1
        topicos = ResultadoTopicos.ler(projeto.dados / PASTA_TOPICOS)
        macro_do_topico = {t.id: t.macro for t in topicos.topicos} if topicos else {}
        macro_do_doc = {
            a["id"]: macro_do_topico.get(a["topico"], -1)
            for a in ler_atribuicoes(projeto.dados / PASTA_TOPICOS)
            if a["topico"] is not None and a["topico"] >= 0
        }
        fluxo = [[0] * n_macrotemas for _ in range(n_macrotemas)]
        for c in internas:
            a, b = macro_do_doc.get(c["de"], -1), macro_do_doc.get(c["para"], -1)
            if 0 <= a < n_macrotemas and 0 <= b < n_macrotemas:
                fluxo[a][b] += 1
        cit_doc, cit_obra = [], []
        for k, o in enumerate(canone):
            for d in o["citantes"] or []:
                if d in indice:
                    cit_doc.append(indice[d])
                    cit_obra.append(k)
        citacoes = m.Citacoes(
            n_referencias=[n_refs[d] for d in ids_documentos],
            internas=m.ArestasCitacao(
                de=[indice[c["de"]] for c in internas], para=[indice[c["para"]] for c in internas]
            ),
            canone=[
                m.ObraCitada(
                    id=o["id"],
                    titulo=o["titulo"],
                    ano=o["ano"],
                    autores=list(o["autores"] or []),
                    veiculo=o["veiculo"],
                    tipo=o["tipo"],
                    doi=o["doi"],
                    n=o["n"],
                    edicoes=list(o["edicoes"] or []),
                )
                for o in canone
            ],
            canone_citantes=m.CitantesCanone(doc=cit_doc, obra=cit_obra),
            fluxo_macrotemas=fluxo,
            cobertura={k: int(v) for k, v in resultado.cobertura_citacoes.items()},
        )
        gabarito["canone_n"] = [o["n"] for o in canone]
    return redes, citacoes, gabarito
