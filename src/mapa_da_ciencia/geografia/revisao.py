"""Revisão das afiliações que não casaram (`mapa geografia --revisar`).

Agrupa os textos de afiliação sem instituição pela forma normalizada (sem acentos e pontuação), do mais frequente
ao menos, com as instituições conhecidas que mais se parecem com cada um. O bloco YAML que sai no fim vai direto
para o `instituicoes.yaml` do projeto: os textos com uma sugestão boa viram apelidos; os outros ficam comentados,
como modelo de instituição própria.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from ..armazenamento import ARQUIVO as ARQUIVO_DOCUMENTOS
from ..armazenamento import ler_documentos
from ..projeto import Projeto
from . import instituicoes as inst
from . import normalizar
from .casamento import LIMIAR_OBRA, Indice, parece_organizacao
from .resultado import PASTA, ler_vinculos

SUGESTAO_MINIMA = 0.3  # abaixo disso, a instituição parecida não ajuda quem revisa
LIMIAR_SUGERIR_ID = 0.5  # daqui até SUGESTAO_BOA, o apelido sai comentado, apontando para a parecida
SUGESTAO_BOA = LIMIAR_OBRA  # a partir daqui, o bloco YAML já traz o apelido ativo


@dataclass
class Sugestao:
    id: str
    nome: str
    pais: str | None
    nota: float


@dataclass
class Pendencia:
    """Um texto de afiliação (com as grafias que dão a mesma forma normalizada) que não casou."""

    texto: str  # a grafia mais comum
    grafias: int
    vinculos: int
    documentos: int
    pais: str | None  # o país mais comum na fonte
    uf: str | None
    sugestoes: list[Sugestao] = field(default_factory=list)


def pendencias(projeto: Projeto, limite: int | None = 20) -> list[Pendencia]:
    """As pendências da última execução de `mapa geografia`, das mais frequentes às menos."""
    vinculos = [v for v in ler_vinculos(projeto.dados / PASTA) if not v["instituicao"] and v["texto"]]
    grupos: dict[str, list[dict]] = defaultdict(list)
    for v in vinculos:
        if v["fonte"] != "openalex" or parece_organizacao(v["texto"]):
            grupos[normalizar.chave(v["texto"])].append(v)
    ordem = sorted(grupos.values(), key=lambda g: (-len(g), normalizar.chave(g[0]["texto"])))
    if limite is not None:
        ordem = ordem[:limite]
    if not ordem:
        return []
    docs = ler_documentos(projeto.dados / ARQUIVO_DOCUMENTOS)
    registros, apelidos = inst.combinar(
        inst.completar(inst.ler_openalex(projeto.dados), docs), inst.ler_projeto(projeto.raiz)
    )
    indice = Indice(registros, apelidos)
    saida = []
    for grupo in ordem:
        texto = Counter(v["texto"] for v in grupo).most_common(1)[0][0]
        pais = Counter(v["pais_fonte"] for v in grupo if v["pais_fonte"]).most_common(1)
        pais_ = pais[0][0] if pais else None
        uf = Counter(v["uf"] for v in grupo if v["uf"] and v["pais"] == pais_).most_common(1)
        notas = indice.melhores(texto, indice.candidatos_globais(texto), pais_)
        sugestoes = [
            Sugestao(id_, inst.nome_de_exibicao(registros[id_])[0], registros[id_].pais, round(nota, 2))
            for nota, id_ in notas[:3]
            if nota >= SUGESTAO_MINIMA
        ]
        saida.append(
            Pendencia(
                texto=texto,
                grafias=len({v["texto"] for v in grupo}),
                vinculos=len(grupo),
                documentos=len({v["doc"] for v in grupo}),
                pais=pais_,
                uf=uf[0][0] if uf else None,
                sugestoes=sugestoes,
            )
        )
    return saida


def _aspas(texto: str) -> str:
    return '"' + texto.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _identificador(texto: str) -> str:
    return re.sub(r"\s+", "-", normalizar.chave(texto))[:40].strip("-") or "instituicao"


def bloco_yaml(lista: list[Pendencia]) -> str:
    """O trecho para colar no `instituicoes.yaml`: apelidos para as sugestões boas; o resto, comentado."""
    apelidos, proprias = [], []
    for p in lista:
        melhor = p.sugestoes[0] if p.sugestoes else None
        comentario = f"  # {p.vinculos} vínculo(s)"
        if melhor and melhor.nota >= SUGESTAO_BOA:
            apelidos.append(f"  {_aspas(p.texto)}: {melhor.id}{comentario}; {melhor.nome} ({melhor.pais or '?'})")
        elif melhor and melhor.nota >= LIMIAR_SUGERIR_ID:
            apelidos.append(
                f"  # {_aspas(p.texto)}: {melhor.id}{comentario}; confira: {melhor.nome} ({melhor.pais or '?'})"
            )
        else:
            alvo = f"; parecida: {melhor.nome} ({melhor.id})" if melhor else ""
            apelidos.append(f"  # {_aspas(p.texto)}: {_identificador(p.texto)}{comentario}{alvo}")
            proprias += [
                f"  # {_identificador(p.texto)}:",
                f"  #   nome: {_aspas(p.texto)}",
                f"  #   pais: {p.pais or 'BR'}",
                *([f"  #   uf: {p.uf}"] if p.uf else []),
            ]
    linhas = ["apelidos:", *apelidos]
    if proprias:
        linhas += ["instituicoes:", *proprias]
    return "\n".join(linhas) + "\n"
