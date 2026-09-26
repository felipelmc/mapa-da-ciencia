"""Identidade estável dos tópicos e dos macrotemas entre execuções.

Ao rodar de novo (com mais anos, outra semente ou outro parâmetro), o HDBSCAN numera os tópicos de outro jeito.
Para as cores, os permalinks (`#/mapa?topicos=12`) e os rótulos editados à mão continuarem valendo, cada tópico
novo é casado com um da execução anterior pela **sobreposição de membros**: o índice de Jaccard entre os núcleos,
contando só os documentos presentes nas duas execuções, com casamento húngaro e um limiar. Centroides não
servem para isso: comparam mal num espaço de embeddings e mudam com o modelo.

- Um tópico casado mantém o id, a cor (se continuar no mesmo macrotema) e o rótulo.
- Um tópico novo ganha um id nunca usado (`proximo_id`): ids aposentados não voltam, para um link antigo não
  apontar para outro assunto.
- Os macrotemas têm identidade própria, casada pelos tópicos que os compõem.
- Uma mudança de modelo, de idioma de análise ou do texto de análise invalida o casamento (os ids continuam de
  onde pararam).

O estado fica em `dados/topicos/identidade.json`. Só a execução principal o grava; as sementes da estabilidade
e a calibração não.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from mapa_da_ciencia.topicos.paleta import cores_macrotemas, proxima_cor

ARQUIVO = "identidade.json"
LIMIAR = 0.3  # Jaccard mínimo para dois tópicos (ou macrotemas) serem o mesmo


@dataclass
class TopicoEstavel:
    id: int
    macro: int
    cor: str
    membros: list[str]  # núcleo
    rotulo: str | None = None
    descricao: str | None = None
    rotulo_fonte: str | None = None
    palavras: list[str] = field(default_factory=list)


@dataclass
class MacroEstavel:
    id: int
    cor: str
    rotulo: str | None = None
    descricao: str | None = None
    rotulo_fonte: str | None = None


@dataclass
class Identidade:
    chave: dict
    proximo_id: int = 0
    proximo_macro: int = 0
    topicos: dict[int, TopicoEstavel] = field(default_factory=dict)
    macrotemas: dict[int, MacroEstavel] = field(default_factory=dict)

    @classmethod
    def ler(cls, pasta: Path) -> Identidade | None:
        arquivo = pasta / ARQUIVO
        if not arquivo.exists():
            return None
        try:
            d = json.loads(arquivo.read_text(encoding="utf-8"))
            return cls(
                chave=d["chave"],
                proximo_id=d["proximo_id"],
                proximo_macro=d["proximo_macro"],
                topicos={int(k): TopicoEstavel(**v) for k, v in d["topicos"].items()},
                macrotemas={int(k): MacroEstavel(**v) for k, v in d["macrotemas"].items()},
            )
        except (OSError, ValueError, KeyError, TypeError):
            return None  # estado ilegível: recomeça (os ids novos podem repetir os antigos só neste caso)

    def gravar(self, pasta: Path) -> None:
        pasta.mkdir(parents=True, exist_ok=True)
        temporario = pasta / (ARQUIVO + ".tmp")
        temporario.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(temporario, pasta / ARQUIVO)


def _casar(pesos: list[list[float]], limiar: float) -> dict[int, int]:
    """Casamento húngaro que maximiza a soma dos pesos; só valem pares com peso ≥ limiar."""
    import numpy as np
    from scipy.optimize import linear_sum_assignment

    if not pesos or not pesos[0]:
        return {}
    m = np.array(pesos)
    linhas, colunas = linear_sum_assignment(-m)
    return {int(i): int(j) for i, j in zip(linhas, colunas, strict=True) if m[i, j] >= limiar}


def _jaccard(a: set[str], b: set[str]) -> float:
    uniao = len(a | b)
    return len(a & b) / uniao if uniao else 0.0


@dataclass
class Estabilizados:
    """Ids, macrotemas e cores dos tópicos novos (na ordem em que foram passados), e a identidade a gravar."""

    ids: list[int]
    macros: list[int]
    cores: list[str]
    cores_macro: dict[int, str]
    casados: dict[int, int]  # índice do tópico novo → id anterior
    identidade: Identidade
    mesma_cor: int = 0  # casados que também mantiveram a cor (não mudaram de macrotema)


def estabilizar(
    nucleos: list[set[str]],
    grupos_macro: list[int],
    anterior: Identidade | None,
    chave: dict,
    corpus: set[str],
    *,
    limiar: float = LIMIAR,
) -> Estabilizados:
    """Dá ids, macrotemas e cores estáveis aos tópicos novos.

    `nucleos[i]` são os documentos do núcleo do tópico novo `i`; `grupos_macro[i]`, o grupo de macrotema dele
    (de `agrupar_macrotemas`); `corpus`, todos os ids do corpus atual.
    """
    valida = anterior if anterior is not None and anterior.chave == chave else None
    proximo_id = anterior.proximo_id if anterior else 0
    proximo_macro = anterior.proximo_macro if anterior else 0
    tamanhos = [len(n) for n in nucleos]

    # ---- tópicos: sobreposição de membros, só com os documentos presentes nas duas execuções
    casados: dict[int, int] = {}
    if valida and valida.topicos:
        antigos = list(valida.topicos.values())
        comuns = corpus & set().union(*(set(t.membros) for t in antigos))
        pesos = [[_jaccard(n & comuns, set(t.membros) & comuns) for t in antigos] for n in nucleos]
        casados = {i: antigos[j].id for i, j in _casar(pesos, limiar).items()}
    ids = [-1] * len(nucleos)
    for i, antigo in casados.items():
        ids[i] = antigo
    for i in sorted((i for i in range(len(nucleos)) if i not in casados), key=lambda i: (-tamanhos[i], i)):
        ids[i], proximo_id = proximo_id, proximo_id + 1

    # ---- macrotemas: casados pelos documentos dos tópicos casados que cada grupo herdou
    n_grupos = max(grupos_macro, default=-1) + 1
    macro_do_grupo: dict[int, int] = {}
    if valida and valida.macrotemas:
        antigos_m = list(valida.macrotemas)
        docs_grupo = [sum(tamanhos[i] for i in range(len(nucleos)) if grupos_macro[i] == g) for g in range(n_grupos)]
        docs_antigo = {m: sum(len(t.membros) for t in valida.topicos.values() if t.macro == m) for m in antigos_m}
        pesos = []
        for g in range(n_grupos):
            linha = []
            for m in antigos_m:
                comum = sum(
                    tamanhos[i]
                    for i, antigo in casados.items()
                    if grupos_macro[i] == g and valida.topicos[antigo].macro == m
                )
                uniao = docs_grupo[g] + docs_antigo[m] - comum
                linha.append(comum / uniao if uniao else 0.0)
            pesos.append(linha)
        macro_do_grupo = {g: antigos_m[j] for g, j in _casar(pesos, limiar).items()}
    for g in range(n_grupos):
        if g not in macro_do_grupo:
            macro_do_grupo[g], proximo_macro = proximo_macro, proximo_macro + 1
    macros = [macro_do_grupo[g] for g in grupos_macro]

    # ---- cores: da paleta para este número de macrotemas; quem já tinha cor e continua no lugar a mantém
    paleta = cores_macrotemas(n_grupos)
    cores_macro: dict[int, str] = {}
    for g in range(n_grupos):
        m = macro_do_grupo[g]
        antiga = valida.macrotemas[m].cor if valida and m in valida.macrotemas else None
        if antiga in paleta and antiga not in cores_macro.values():
            cores_macro[m] = antiga
    livres = [c for c in paleta if c not in cores_macro.values()]
    for g in range(n_grupos):
        if macro_do_grupo[g] not in cores_macro:
            cores_macro[macro_do_grupo[g]] = livres.pop(0)

    # primeiro quem continua no mesmo macrotema reserva a sua cor; depois os que mudaram de macrotema e os novos
    # recebem cores, evitando as reservadas (senão um recém-chegado podia tomar a cor de quem ficou)
    cores = [""] * len(nucleos)
    usadas: dict[int, list[str]] = {m: [] for m in cores_macro}
    mesma_cor = 0
    for i in sorted(casados, key=lambda i: (-tamanhos[i], i)):
        anterior_t = valida.topicos[casados[i]] if valida else None
        if anterior_t and anterior_t.macro == macros[i] and anterior_t.cor not in usadas[macros[i]]:
            cores[i] = anterior_t.cor
            usadas[macros[i]].append(cores[i])
            mesma_cor += 1
    for i in sorted((i for i in range(len(nucleos)) if not cores[i]), key=lambda i: (-tamanhos[i], i)):
        cores[i] = proxima_cor(cores_macro[macros[i]], usadas[macros[i]])
        usadas[macros[i]].append(cores[i])

    # ---- a identidade nova: membros atuais; rótulos dos casados seguem, para a etapa de rótulos decidir
    topicos = {}
    for i, n in enumerate(nucleos):
        velho = valida.topicos.get(casados[i]) if valida and i in casados else None
        topicos[ids[i]] = TopicoEstavel(
            id=ids[i],
            macro=macros[i],
            cor=cores[i],
            membros=sorted(n),
            rotulo=velho.rotulo if velho else None,
            descricao=velho.descricao if velho else None,
            rotulo_fonte=velho.rotulo_fonte if velho else None,
            palavras=velho.palavras if velho else [],
        )
    macrotemas = {}
    for m, cor in cores_macro.items():
        velho_m = valida.macrotemas.get(m) if valida else None
        macrotemas[m] = MacroEstavel(
            id=m,
            cor=cor,
            rotulo=velho_m.rotulo if velho_m else None,
            descricao=velho_m.descricao if velho_m else None,
            rotulo_fonte=velho_m.rotulo_fonte if velho_m else None,
        )
    nova = Identidade(chave, proximo_id, proximo_macro, topicos, macrotemas)
    return Estabilizados(ids, macros, cores, cores_macro, casados, nova, mesma_cor)
