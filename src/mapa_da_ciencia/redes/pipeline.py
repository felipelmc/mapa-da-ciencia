"""A etapa das redes de ponta a ponta (`mapa redes`).

corpus + tópicos (+ geografia) + referências → pessoas → grafos, métricas, comunidades e desenho → citações e
cânone → `dados/redes/` → exportação (`redes.json` e `citacoes.json`).

Não chama modelo nenhum (os rótulos das comunidades vêm dos tópicos dos documentos delas) e roda em segundos. Exige
os tópicos em dia; a geografia é opcional: sem ela, a rede de instituições e a de estados ficam de fora, com aviso.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..armazenamento import (
    ARQUIVO,
    ARQUIVO_CITADAS,
    ARQUIVO_REFERENCIAS,
    ARQUIVO_REFERENCIAS_AM,
    gravar_tabela,
    ler_documentos,
    ler_tabela,
)
from ..config import ErroConfig
from ..contrato.modelos import NAO_IDENTIFICADA
from ..manifesto import registrar_execucao
from ..progresso import Progresso, ProgressoNulo
from ..projeto import Projeto
from ..topicos.resultado import PASTA as PASTA_TOPICOS
from ..topicos.resultado import Resultado as ResultadoTopicos
from ..topicos.resultado import assinatura_corpus, ler_atribuicoes
from . import citacoes as cit
from .desenho import desenhar, raios_na_vista
from .grafos import (
    EXTERIOR,
    colaboracao_por_ano,
    comunidades,
    forcas,
    grafo,
    macro_dominante,
    metricas,
    pares_ponderados,
)
from .pessoas import ARQUIVO_PESSOAS, identificar, ler_correcoes

PASTA = "redes"
VERSAO = 3  # 2: identidade revista, cânone conferido nas referências, pesos exatos, ids do contrato nas instituições;
# 3: o desenho por comunidades, sem nós sobrepostos, com os componentes menores à direita do maior
ARQUIVO_RESULTADO = "resultado.json"
_CARIMBOS = ("gerado_em", "duracao_s")


def _hash_arquivos(*caminhos: Path) -> str:
    h = hashlib.sha256()
    for caminho in caminhos:
        h.update(caminho.name.encode())
        h.update(caminho.read_bytes() if caminho.exists() else b"-")
    return h.hexdigest()[:16]


def _hash_resultado(caminho: Path) -> str:
    """O `resultado.json` de outra etapa sem os carimbos de hora: refazer a etapa com as mesmas entradas não muda."""
    if not caminho.exists():
        return "-"
    dados = {k: v for k, v in json.loads(caminho.read_text(encoding="utf-8")).items() if k not in _CARIMBOS}
    return hashlib.sha256(json.dumps(dados, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def _hash_correcoes(raiz: Path) -> str:
    """O conteúdo do `pessoas.yaml` (um comentário ou a ordem das chaves não mudam as redes)."""
    try:
        return hashlib.sha256(ler_correcoes(raiz).model_dump_json().encode()).hexdigest()[:16]
    except ErroConfig:
        return _hash_arquivos(raiz / ARQUIVO_PESSOAS)


def partes_das_entradas(projeto: Projeto) -> dict[str, str]:
    """Um hash por entrada da etapa, com o nome que o aviso de desatualizada mostra."""
    geo = projeto.dados / "geografia"
    top = projeto.dados / PASTA_TOPICOS
    return {
        "o corpus": _hash_arquivos(projeto.dados / ARQUIVO),
        "as referências": _hash_arquivos(
            projeto.dados / ARQUIVO_REFERENCIAS, projeto.dados / ARQUIVO_CITADAS, projeto.dados / ARQUIVO_REFERENCIAS_AM
        ),
        "o pessoas.yaml": _hash_correcoes(projeto.raiz),
        "a geografia": _hash_resultado(geo / "resultado.json")
        + _hash_arquivos(geo / "pesos.parquet", geo / "vinculos.parquet", geo / "instituicoes.parquet"),
        "os tópicos": _hash_resultado(top / "resultado.json") + _hash_arquivos(top / "atribuicoes.parquet"),
    }


def assinatura_entradas(projeto: Projeto, partes: dict[str, str] | None = None) -> str:
    """Hash do que a etapa lê: o corpus, as referências, as correções de pessoas, a geografia e os tópicos (o
    conteúdo, sem os carimbos de hora das outras etapas)."""
    partes = partes if partes is not None else partes_das_entradas(projeto)
    h = hashlib.sha256(f"versao={VERSAO}".encode())
    for nome, valor in sorted(partes.items()):
        h.update(f"{nome}={valor}".encode())
    return h.hexdigest()[:20]


@dataclass
class ResultadoRedes:
    versao: int
    assinatura: str
    entradas: str
    gerado_em: str
    contagens: dict[str, int]
    metricas: dict[str, dict[str, Any]]
    cobertura_citacoes: dict[str, Any] | None
    parametros: dict[str, Any]
    avisos: list[str] = field(default_factory=list)
    partes: dict[str, str] = field(default_factory=dict)  # `partes_das_entradas`, para dizer o que mudou

    def gravar(self, pasta: Path) -> None:
        tmp = pasta / (ARQUIVO_RESULTADO + ".tmp")
        tmp.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, pasta / ARQUIVO_RESULTADO)

    @classmethod
    def ler(cls, pasta: Path) -> ResultadoRedes | None:
        arquivo = pasta / ARQUIVO_RESULTADO
        if not arquivo.exists():
            return None
        return cls(**json.loads(arquivo.read_text(encoding="utf-8")))


def redes_em_dia(projeto: Projeto) -> bool | None:
    """True se as redes correspondem às entradas atuais; False se desatualizadas; None se nunca geradas."""
    r = ResultadoRedes.ler(projeto.dados / PASTA)
    if r is None:
        return None
    return r.versao == VERSAO and r.entradas == assinatura_entradas(projeto)


def o_que_mudou(projeto: Projeto) -> list[str]:
    """O que mudou desde a última `mapa redes` ("o pessoas.yaml", "a geografia"…); vazio se as redes estão em dia."""
    r = ResultadoRedes.ler(projeto.dados / PASTA)
    if r is None:
        return []
    if r.versao != VERSAO:
        return ["a versão da etapa"]
    agora = partes_das_entradas(projeto)
    if r.entradas == assinatura_entradas(projeto, agora):
        return []
    return [nome for nome, valor in agora.items() if r.partes.get(nome) != valor] or ["as entradas"]


@dataclass
class ResumoRedes:
    pessoas: int
    com_coautoria: int
    arestas: int
    componentes: int
    maior_componente: int
    comunidades: int
    instituicoes: int | None
    citacoes_internas: int | None
    canone: int | None
    candidatos: int
    duracao_s: float
    avisos: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        partes = [
            f"{self.pessoas} pessoas, {self.com_coautoria} com coautor ({self.arestas} arestas, {self.componentes} "
            f"componentes, o maior com {self.maior_componente}); {self.comunidades} comunidades"
        ]
        if self.instituicoes is not None:
            partes.append(f"{self.instituicoes} instituições ligadas a outra")
        if self.citacoes_internas is not None:
            partes.append(f"{self.citacoes_internas} citações dentro do corpus; cânone de {self.canone} obras")
        return "; ".join(partes) + "."


COLUNAS = {
    "pessoas": {
        "id": "VARCHAR",
        "interno": "VARCHAR",
        "nome": "VARCHAR",
        "via": "VARCHAR",
        "documentos": "INTEGER",
        "grau": "INTEGER",
        "forca": "DOUBLE",
        "comunidade": "INTEGER",
        "x": "DOUBLE",
        "y": "DOUBLE",
    },
    "autorias": {"doc": "VARCHAR", "posicao": "INTEGER", "pessoa": "VARCHAR"},
    "arestas": {"rede": "VARCHAR", "a": "VARCHAR", "b": "VARCHAR", "peso": "DOUBLE", "documentos": "INTEGER"},
    "instituicoes": {
        "id": "VARCHAR",  # o id do contrato (`ror:…`, `openalex:I…` ou o do `instituicoes.yaml`)
        "grau": "INTEGER",
        "forca": "DOUBLE",
        "comunidade": "INTEGER",
        "x": "DOUBLE",
        "y": "DOUBLE",
    },
    "comunidades": {
        "rede": "VARCHAR",
        "id": "INTEGER",
        "n": "INTEGER",
        "documentos": "INTEGER",
        "macro": "INTEGER",
        "topicos": "INTEGER[]",
        "rotulo": "VARCHAR",
    },
    "citacoes": {"de": "VARCHAR", "para": "VARCHAR"},
    "canone": {
        "id": "VARCHAR",
        "titulo": "VARCHAR",
        "ano": "INTEGER",
        "autores": "VARCHAR[]",
        "veiculo": "VARCHAR",
        "tipo": "VARCHAR",
        "doi": "VARCHAR",
        "n": "INTEGER",
        "citantes": "VARCHAR[]",
        "edicoes": "VARCHAR[]",
        "resenha": "BOOLEAN",
        "autoria_das_referencias": "BOOLEAN",
        "autores_openalex": "VARCHAR[]",
        "ano_openalex": "INTEGER",
    },
    "candidatos": {"a": "VARCHAR", "b": "VARCHAR", "nome": "VARCHAR", "tipo": "VARCHAR"},
    "colaboracao": {
        "ano": "INTEGER",
        "documentos": "INTEGER",
        "com_coautoria": "DOUBLE",
        "autores_medio": "DOUBLE",
        "com_instituicoes": "DOUBLE",
        "entre_ufs": "DOUBLE",
        "com_exterior": "DOUBLE",
    },
}


def gerar_redes(projeto: Projeto, progresso: Progresso | None = None) -> ResumoRedes:
    progresso = progresso or ProgressoNulo()
    t0, inicio = time.perf_counter(), datetime.now(UTC)
    caminho = projeto.dados / ARQUIVO
    if not caminho.exists():
        raise ErroConfig("O projeto ainda não tem corpus. Rode `mapa coletar` antes de `mapa redes`.")
    topicos = ResultadoTopicos.ler(projeto.dados / PASTA_TOPICOS)
    docs = ler_documentos(caminho)
    assinatura = assinatura_corpus([d.id for d in docs])
    if topicos is None or topicos.assinatura != assinatura:
        raise ErroConfig("As redes usam os tópicos: rode `mapa topicos` antes de `mapa redes`.")
    avisos: list[str] = []
    progresso.etapa("Redes", 5)
    anos = {d.id: d.ano for d in docs}
    topico_do_doc = {a["id"]: a["topico"] for a in ler_atribuicoes(projeto.dados / PASTA_TOPICOS)}
    macro_do_topico = {t.id: t.macro for t in topicos.topicos}
    macro_do_doc = {d: macro_do_topico.get(t, -1) for d, t in topico_do_doc.items() if t is not None}
    rotulo_do_topico = {t.id: t.rotulo for t in topicos.topicos}

    from ..geografia.pipeline import geografia_em_dia
    from ..geografia.resultado import PASTA as PASTA_GEO
    from ..geografia.resultado import id_no_contrato, ler_instituicoes, ler_pesos, ler_vinculos
    from ..segredos import segredo

    com_geografia = bool(geografia_em_dia(projeto))

    # 1. pessoas e coautoria (as instituições casadas pela geografia ajudam a juntar homônimos)
    insts_da_autoria: dict[tuple[str, int], set[str]] = defaultdict(set)
    if com_geografia:
        for v in ler_vinculos(projeto.dados / PASTA_GEO):
            if v["autor"] is not None and v["instituicao"] and v["instituicao"] != NAO_IDENTIFICADA:
                insts_da_autoria[(v["doc"], v["autor"])].add(v["instituicao"])
    ident = identificar(
        docs, ler_correcoes(projeto.raiz), segredo=segredo(projeto, "redes"), instituicoes=insts_da_autoria
    )
    avisos += ident.avisos
    pessoas = ident.pessoas
    autores_do_doc: dict[str, list[str]] = defaultdict(list)
    for i, a in enumerate(ident.autorias):
        autores_do_doc[a.doc].append(pessoas[ident.pessoa_da_autoria[i]].publicado)
    arestas_p = pares_ponderados(autores_do_doc)
    g = grafo(arestas_p)
    com_p, particao_p = comunidades(g, "coautoria")
    met_p = metricas(g, particao_p)
    docs_p = Counter(p for lista in autores_do_doc.values() for p in set(lista))
    # o teto do raio vem de todas as pessoas, como na vista (ModoGrafo), e não só das que têm coautor
    pos_p = desenhar(g, particao_p, raios_na_vista(dict(docs_p), "coautoria"))
    progresso.avancar()

    # 2. instituições e estados, pela geografia
    inst_do_doc: dict[str, list[str]] | None = None
    lugares: dict[str, list[str]] | None = None
    arestas_i: dict[tuple[str, str], tuple[float, int]] = {}
    arestas_uf: dict[tuple[str, str], tuple[float, int]] = {}
    com_i: dict[str, int] = {}
    met_i = None
    pos_i: dict[str, tuple[float, float]] = {}
    if com_geografia:
        pesos = ler_pesos(projeto.dados / PASTA_GEO)
        # os ids do contrato (`ror:…`, `openalex:I…`), os mesmos de `afiliacoes.json`
        no_contrato = {i["id"]: id_no_contrato(i) for i in ler_instituicoes(projeto.dados / PASTA_GEO)}
        inst_do_doc = defaultdict(list)
        for p in pesos:
            if p["instituicao"] and p["instituicao"] != NAO_IDENTIFICADA:
                inst_do_doc[p["doc"]].append(no_contrato.get(p["instituicao"], p["instituicao"]))
        lugares = defaultdict(list)
        for p in pesos:
            if p["pais"] == "BR" and p["uf"]:
                lugares[p["doc"]].append(p["uf"])
            elif p["pais"] and p["pais"] != "BR":
                lugares[p["doc"]].append(EXTERIOR)
        arestas_i = pares_ponderados(inst_do_doc)
        arestas_uf = pares_ponderados(lugares)
        gi = grafo(arestas_i)
        com_i, particao_i = comunidades(gi, "instituicoes")
        met_i = metricas(gi, particao_i)
        docs_i = Counter(i for lista in inst_do_doc.values() for i in set(lista))
        pos_i = desenhar(gi, particao_i, raios_na_vista({k: docs_i[k] for k in gi.nodes}, "instituicoes"))
    else:
        avisos.append("Sem a geografia em dia, as redes de instituições e de estados ficam de fora: rode "
                      "`mapa geografia`.")  # fmt: skip
    progresso.avancar()

    # 3. comunidades: tamanho, macrotema dominante e os dois tópicos mais frequentes como rótulo
    linhas_com = []
    for rede, com, docs_do_no in (
        ("coautoria", com_p, _docs_por_no(autores_do_doc)),
        ("instituicoes", com_i, _docs_por_no(inst_do_doc or {})),
    ):
        membros: dict[int, list[str]] = defaultdict(list)
        for no, c in com.items():
            if c >= 0:
                membros[c].append(no)
        for c in sorted(membros):
            docs_c = sorted({d for no in membros[c] for d in docs_do_no.get(no, ())})
            tops = Counter(
                topico_do_doc[d] for d in docs_c if topico_do_doc.get(d) is not None and topico_do_doc[d] >= 0
            )
            # os mais frequentes; no empate, o de menor id (e não a ordem em que apareceram)
            principais = [t for t, _ in sorted(tops.items(), key=lambda kv: (-kv[1], kv[0]))[:3]]
            linhas_com.append(
                {
                    "rede": rede,
                    "id": c,
                    "n": len(membros[c]),
                    "documentos": len(docs_c),
                    "macro": macro_dominante(docs_c, macro_do_doc),
                    "topicos": principais,
                    "rotulo": " · ".join(rotulo_do_topico[t] for t in principais[:2]) or "Sem tópico dominante",
                }
            )
    progresso.avancar()

    # 4. citações
    cobertura = None
    linhas_cit, linhas_canone = [], []
    c_res = None
    if (projeto.dados / ARQUIVO_REFERENCIAS).exists():
        doc_da_obra = {d.openalex_id: d.id for d in docs if d.openalex_id}
        citadas = ler_tabela(projeto.dados / ARQUIVO_CITADAS) if (projeto.dados / ARQUIVO_CITADAS).exists() else []
        refs_am: dict[str, list[dict[str, Any]]] = defaultdict(list)
        if (projeto.dados / ARQUIVO_REFERENCIAS_AM).exists():
            for r in ler_tabela(projeto.dados / ARQUIVO_REFERENCIAS_AM):
                refs_am[r["doc"]].append(r)
        c_res = cit.calcular(
            ler_tabela(projeto.dados / ARQUIVO_REFERENCIAS),
            citadas,
            doc_da_obra,
            anos,
            {d: t for d, t in topico_do_doc.items() if t is not None},
            macro_do_topico,
            referencias_articlemeta=refs_am,
            listadas={d.id: d.n_referencias for d in docs if d.openalex_id and d.n_referencias},
        )
        cobertura = c_res.cobertura
        linhas_cit = [{"de": a, "para": b} for a, b in c_res.internas]
        linhas_canone = [asdict(o) for o in c_res.canone]
        if not citadas:
            avisos.append(
                "Sem os metadados das obras mais citadas, o cânone fica vazio (as citações dentro do corpus valem): "
                "rode `mapa coletar` de novo."
            )
        elif c_res.sem_metadados:
            avisos.append(
                f"{len(c_res.sem_metadados)} obra(s) entre as mais citadas vieram sem metadados do OpenAlex e ficaram "
                f"fora do cânone (por exemplo, {c_res.sem_metadados[0]})."
            )
    else:
        avisos.append("Sem as referências do OpenAlex, a rede de citação fica de fora: rode `mapa coletar`.")
    progresso.avancar()

    # 5. gravar
    pasta = projeto.dados / PASTA
    pasta.mkdir(parents=True, exist_ok=True)
    grau = Counter(x for par in arestas_p for x in par)
    forca = forcas(autores_do_doc)
    n_docs = docs_p
    linhas_p = [
        {
            "id": p.publicado,
            "interno": p.interno,
            "nome": p.nome,
            "via": p.via,
            "documentos": n_docs[p.publicado],
            "grau": grau.get(p.publicado, 0),
            "forca": float(forca.get(p.publicado, 0)),
            "comunidade": com_p.get(p.publicado, -1),
            "x": pos_p.get(p.publicado, (None, None))[0],
            "y": pos_p.get(p.publicado, (None, None))[1],
        }
        for p in pessoas
    ]
    grau_i = Counter(x for par in arestas_i for x in par)
    forca_i = forcas(inst_do_doc or {})
    linhas_i = [
        {"id": i, "grau": grau_i[i], "forca": float(forca_i[i]), "comunidade": com_i.get(i, -1),
         "x": pos_i[i][0], "y": pos_i[i][1]}
        for i in sorted(pos_i)
    ]  # fmt: skip
    arestas = [
        {"rede": rede, "a": a, "b": b, "peso": peso, "documentos": n}
        for rede, conjunto in (("coautoria", arestas_p), ("instituicoes", arestas_i), ("ufs", arestas_uf))
        for (a, b), (peso, n) in conjunto.items()
    ]
    serie = colaboracao_por_ano(anos, autores_do_doc, inst_do_doc, lugares)
    tabelas = {
        "pessoas": linhas_p,
        "autorias": [
            {"doc": a.doc, "posicao": a.posicao, "pessoa": pessoas[ident.pessoa_da_autoria[i]].publicado}
            for i, a in enumerate(ident.autorias)
        ],
        "arestas": arestas,
        "instituicoes": linhas_i,
        "comunidades": linhas_com,
        "citacoes": linhas_cit,
        "canone": linhas_canone,
        "candidatos": _para_revisao(ident),
        "colaboracao": [{k: v for k, v in asdict(c).items() if k != "extras"} for c in serie],
    }
    for nome, linhas in tabelas.items():
        ordem = next(iter(COLUNAS[nome]))
        gravar_tabela(linhas, COLUNAS[nome], pasta / f"{nome}.parquet", ordem=ordem)
    partes = partes_das_entradas(projeto)
    resultado = ResultadoRedes(
        versao=VERSAO,
        assinatura=assinatura,
        entradas=assinatura_entradas(projeto, partes),
        partes=partes,
        gerado_em=datetime.now(UTC).isoformat(timespec="seconds"),
        contagens={
            "pessoas": len(pessoas),
            "com_coautoria": g.number_of_nodes(),
            "arestas_coautoria": len(arestas_p),
            "instituicoes": len(pos_i),
            "arestas_instituicoes": len(arestas_i),
            "citacoes_internas": len(linhas_cit),
            "canone": len(linhas_canone),
            "candidatos": len(ident.candidatos),
            "pessoas_com_dois_orcids": ident.conflitos,
            "orcids_retirados": len(ident.orcids_retirados),
            "orcids_divergentes": ident.orcids_divergentes,
        },
        metricas={"coautoria": asdict(met_p), **({"instituicoes": asdict(met_i)} if met_i else {})},
        cobertura_citacoes=cobertura,
        parametros={"semente": 7, "resolucao": 1.0, "minimo_comunidade": {"coautoria": 8, "instituicoes": 5}},
        avisos=avisos,
    )
    resultado.gravar(pasta)
    progresso.avancar()
    progresso.fim()
    registrar_execucao(
        projeto,
        "redes",
        inicio=inicio,
        fim=datetime.now(UTC),
        contagens=resultado.contagens,
        parametros=resultado.parametros,
    )
    from ..contrato.exportar import exportar

    avisos += exportar(projeto)
    return ResumoRedes(
        pessoas=len(pessoas),
        com_coautoria=g.number_of_nodes(),
        arestas=len(arestas_p),
        componentes=met_p.componentes,
        maior_componente=met_p.maior_componente,
        comunidades=sum(1 for c in linhas_com if c["rede"] == "coautoria"),
        instituicoes=len(pos_i) if met_i else None,
        citacoes_internas=len(linhas_cit) if c_res else None,
        canone=len(linhas_canone) if c_res else None,
        candidatos=len(ident.candidatos),
        duracao_s=round(time.perf_counter() - t0, 2),
        avisos=avisos,
    )


def _para_revisao(ident) -> list[dict[str, Any]]:
    """O que `mapa redes --revisar` lista: os pares de homônimos e de grafias variantes, as pessoas com dois ORCIDs e as
    autorias que perderam um ORCID de outro nome (`a`: a autoria; `b`: a pessoa que ficou com o ORCID)."""
    linhas = [asdict(c) for c in ident.candidatos]
    linhas += [
        {"a": p.interno, "b": None, "nome": p.nome, "tipo": "dois_orcids"} for p in ident.pessoas if len(p.orcids) > 1
    ]
    dono = {o: p.interno for p in ident.pessoas for o in p.orcids}
    for i, orcid in ident.orcids_retirados:
        a = ident.autorias[i]
        linhas.append({"a": a.id, "b": dono.get(orcid), "nome": a.nome, "tipo": "orcid_retirado"})
    return linhas


def _docs_por_no(por_doc: dict[str, list[str]]) -> dict[str, set[str]]:
    saida: dict[str, set[str]] = defaultdict(set)
    for doc, nos in por_doc.items():
        for no in nos:
            saida[no].add(doc)
    return saida
