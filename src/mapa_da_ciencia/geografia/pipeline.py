"""A etapa de geografia de ponta a ponta (`mapa geografia`).

corpus + registros das instituições + correções do projeto → casamento das afiliações → país e UF de cada vínculo
→ contagem fracionária → `dados/geografia/` → manifesto da etapa → exportação para o painel.

Roda sem rede e em segundos: os registros das instituições vêm da coleta. Ver o ADR 0008.
"""

from __future__ import annotations

import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime

from ..armazenamento import ARQUIVO, ler_documentos
from ..config import ErroConfig
from ..contrato.exportar import exportar
from ..contrato.modelos import NAO_IDENTIFICADA
from ..formatar import num
from ..manifesto import registrar_execucao
from ..progresso import Progresso, ProgressoNulo
from ..projeto import Projeto
from ..topicos.resultado import assinatura_corpus
from . import instituicoes as inst
from .casamento import NIVEIS, Casador, Indice
from .contagem import Lugares, cobertura, contar
from .resultado import PASTA, VERSAO, Resultado, assinatura_entradas


@dataclass
class ResumoGeografia:
    """O que a etapa de geografia fez. `print(resumo)` mostra os números principais numa frase.

    `por_fonte` conta os vínculos (autor × afiliação) por fonte, e `identificados`, os que casaram com uma
    instituição; `por_nivel` diz como casaram (ADR 0008). As frações de `pais_conhecido` e `identificada` são do
    peso com afiliação; `uf_conhecida`, do peso brasileiro.
    """

    documentos: int
    vinculos: int
    por_fonte: dict[str, int]
    identificados: dict[str, int]
    por_nivel: dict[str, int]
    instituicoes: int
    sem_afiliacao: float
    pais_conhecido: float
    uf_conhecida: float
    identificada: float
    registros_openalex: int
    duracao_s: float
    avisos: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        total = sum(self.identificados.values())
        return (
            f"{num(self.vinculos, 0)} vínculos de {num(self.documentos, 0)} documentos, "
            f"{num(100 * total / max(1, self.vinculos), 1)}% ligados a uma de {num(self.instituicoes, 0)} "
            f"instituições; país conhecido em {num(100 * self.pais_conhecido, 1)}% do peso e UF em "
            f"{num(100 * self.uf_conhecida, 1)}% do peso brasileiro, em {num(self.duracao_s, 1)} s."
        )


def gerar_geografia(projeto: Projeto, progresso: Progresso | None = None) -> ResumoGeografia:
    progresso = progresso or ProgressoNulo()
    inicio, t0 = datetime.now(UTC), time.perf_counter()
    caminho = projeto.dados / ARQUIVO
    if not caminho.exists():
        raise ErroConfig("O projeto ainda não tem corpus. Rode `mapa coletar` antes de `mapa geografia`.")
    progresso.etapa("Casando as afiliações com as instituições")
    docs = ler_documentos(caminho)
    avisos = []
    do_openalex = inst.ler_openalex(projeto.dados)
    if not do_openalex:
        avisos.append(
            "Sem os registros das instituições do OpenAlex (corpus coletado antes da versão 0.4.0 ou sem o "
            "OpenAlex): o casamento usa só os nomes que vêm nas autorias. Rode `mapa coletar` para buscá-los."
        )
    registros, apelidos = inst.combinar(inst.completar(do_openalex, docs), inst.ler_projeto(projeto.raiz))
    indice = Indice(registros, apelidos)
    casamentos = Casador(indice).casar(docs)
    lugares = Lugares(indice, casamentos)
    parcelas = contar(casamentos, indice, lugares)
    progresso.fim()

    vinculos = []
    for c in casamentos:
        for v in c.vinculos:
            pais = lugares.pais(v)
            vinculos.append(
                {
                    "doc": c.doc, "autor": v.autor, "afiliacao": v.afiliacao, "fonte": v.fonte, "texto": v.texto,
                    "casada": v.casada, "instituicao": v.instituicao, "nivel": v.nivel, "semelhanca": v.semelhanca,
                    "pais_fonte": v.pais_fonte, "uf_fonte": v.uf_fonte, "cidade_fonte": v.cidade_fonte,
                    "pais": pais, "uf": lugares.uf(v, pais),
                }
            )  # fmt: skip
    peso_inst: dict[str, float] = defaultdict(float)
    docs_inst: dict[str, set[str]] = defaultdict(set)
    ufs_inst: dict[str, Counter[str]] = defaultdict(Counter)
    for p in parcelas:
        if p.instituicao and p.instituicao != NAO_IDENTIFICADA:
            peso_inst[p.instituicao] += p.peso
            docs_inst[p.instituicao].add(p.doc)
            if p.uf:
                ufs_inst[p.instituicao][p.uf] += p.peso
    linhas_inst = []
    for id_, peso in peso_inst.items():
        r = registros[id_]
        nome, sigla = inst.nome_de_exibicao(r)
        uf = ufs_inst[id_].most_common(1)[0][0] if ufs_inst[id_] else None
        linhas_inst.append(
            {
                "id": id_, "nome": nome, "sigla": sigla, "pais": r.pais, "uf": uf, "tipo": r.tipo, "ror": r.ror,
                "peso": round(peso, 6), "documentos": len(docs_inst[id_]),
            }
        )  # fmt: skip

    por_fonte = Counter(v.fonte for c in casamentos for v in c.vinculos)
    identificados = Counter(v.fonte for c in casamentos for v in c.vinculos if v.instituicao)
    por_nivel = Counter(v.nivel for c in casamentos for v in c.vinculos)
    cob = cobertura(parcelas)
    contagens = {
        "vinculos": len(vinculos),
        "documentos": len(docs),
        "instituicoes": len(linhas_inst),
        "por_fonte": dict(sorted(por_fonte.items())),
        "identificados": dict(sorted(identificados.items())),
        "por_nivel": {n: por_nivel[n] for n in NIVEIS if por_nivel[n]},
        "registros_openalex": len(do_openalex),
    }
    cobertura_ = {
        "sem_afiliacao": round(cob.sem_afiliacao, 4),
        "pais_conhecido": round(cob.pais_conhecido, 4),
        "uf_conhecida": round(cob.uf_conhecida, 4),
        "identificada": round(cob.identificada, 4),
    }
    Resultado(
        versao=VERSAO,
        assinatura=assinatura_corpus([d.id for d in docs]),
        entradas=assinatura_entradas(projeto.raiz, projeto.dados),
        gerado_em=datetime.now(UTC).isoformat(timespec="seconds"),
        contagens=contagens,
        cobertura=cobertura_,
    ).gravar(
        projeto.dados / PASTA,
        vinculos,
        [p.__dict__ for p in parcelas],
        sorted(linhas_inst, key=lambda x: x["id"]),
    )
    resumo = ResumoGeografia(
        documentos=len(docs),
        vinculos=len(vinculos),
        por_fonte=dict(sorted(por_fonte.items())),
        identificados=dict(sorted(identificados.items())),
        por_nivel=contagens["por_nivel"],
        instituicoes=len(linhas_inst),
        sem_afiliacao=cob.sem_afiliacao,
        pais_conhecido=cob.pais_conhecido,
        uf_conhecida=cob.uf_conhecida,
        identificada=cob.identificada,
        registros_openalex=len(do_openalex),
        duracao_s=round(time.perf_counter() - t0, 2),
        avisos=avisos,
    )
    registrar_execucao(
        projeto,
        "geografia",
        inicio=inicio,
        fim=datetime.now(UTC),
        contagens={
            "vinculos": len(vinculos),
            "identificados": sum(identificados.values()),
            "instituicoes": len(linhas_inst),
            "documentos": len(docs),
        },
        parametros={"versao": VERSAO, **cobertura_},
    )
    resumo.avisos += exportar(projeto)
    return resumo


def geografia_em_dia(projeto: Projeto) -> bool | None:
    """True se a geografia corresponde ao corpus e às entradas atuais; False se está desatualizada; None se nunca
    foi gerada."""
    resultado = Resultado.ler(projeto.dados / PASTA)
    if resultado is None:
        return None
    if resultado.versao != VERSAO or resultado.entradas != assinatura_entradas(projeto.raiz, projeto.dados):
        return False
    ids = [d.id for d in ler_documentos(projeto.dados / ARQUIVO)]
    return resultado.assinatura == assinatura_corpus(ids)
