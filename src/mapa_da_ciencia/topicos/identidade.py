"""Identidade estável dos tópicos e dos macrotemas entre execuções.

Ao rodar de novo (com mais anos, outra semente ou outro parâmetro), o HDBSCAN numera os tópicos de outro jeito.
Para as cores, os permalinks (`#/mapa?topicos=12`) e os rótulos editados à mão continuarem valendo, cada tópico
novo é casado com um da execução anterior pela **sobreposição de membros**: o índice de Jaccard entre os núcleos,
contando só os documentos presentes nas duas execuções, com casamento húngaro e um limiar. Centroides não
servem para isso: comparam mal num espaço de embeddings e mudam com o modelo.

- Um tópico casado mantém o id, a cor (se continuar no mesmo macrotema) e o rótulo.
- Um tópico novo ganha um id nunca usado (`proximo_id`): ids aposentados não voltam, para um link antigo não
  apontar para outro assunto.
- Os macrotemas persistem: quando ao menos metade dos tópicos casou, cada tópico casado fica no macrotema que
  tinha, e cada tópico novo entra no macrotema do tópico casado mais parecido (centros dos núcleos). Refazer a
  aglomeração a cada execução mudaria de macrotema, e de cor, metade dos tópicos casados do piloto (ADR 0007).
- Com menos da metade casada, os macrotemas vêm da aglomeração e são casados com os anteriores pelos tópicos
  que os compõem.
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
from typing import TYPE_CHECKING

from mapa_da_ciencia.topicos.paleta import cores_macrotemas, proxima_cor

if TYPE_CHECKING:
    import numpy as np

ARQUIVO = "identidade.json"
LIMIAR = 0.3  # Jaccard mínimo para dois tópicos (ou macrotemas) serem o mesmo
FRACAO_PERSISTENTE = 0.5  # tópicos casados, no mínimo, para os macrotemas anteriores continuarem valendo


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
    versao_rotulo: int | None = None  # versão do prompt que escreveu o rótulo (`rotulos.VERSAO_PROMPT`)


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
    macrotemas_persistentes: bool = False  # os macrotemas vieram da execução anterior, e não da aglomeração


def estabilizar(
    nucleos: list[set[str]],
    grupos_macro: list[int],
    anterior: Identidade | None,
    chave: dict,
    corpus: set[str],
    *,
    centros: np.ndarray | None = None,
    persistir_macrotemas: bool = True,
    limiar: float = LIMIAR,
) -> Estabilizados:
    """Dá ids, macrotemas e cores estáveis aos tópicos novos.

    `nucleos[i]` são os documentos do núcleo do tópico novo `i`; `grupos_macro[i]`, o grupo de macrotema dele
    (de `agrupar_macrotemas`); `corpus`, todos os ids do corpus atual; `centros[i]`, o centro normalizado do
    núcleo (de `macrotemas.centros`), para pôr os tópicos novos no macrotema do casado mais parecido. Com
    `persistir_macrotemas=False`, os macrotemas sempre vêm de `grupos_macro`.
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

    # ---- macrotemas: os anteriores persistem se a maior parte dos tópicos casou; senão, os da aglomeração,
    # casados pelos documentos dos tópicos casados que cada grupo herdou
    macro_do_grupo: dict[int, int] = {}
    persistentes = bool(
        persistir_macrotemas and valida and valida.macrotemas and len(casados) >= FRACAO_PERSISTENTE * len(nucleos)
    )
    if persistentes:
        grupos_macro, macro_do_grupo = _macrotemas_anteriores(casados, valida, tamanhos, centros)  # type: ignore[arg-type]
    n_grupos = max(grupos_macro, default=-1) + 1
    if valida and valida.macrotemas and not persistentes:
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
            versao_rotulo=velho.versao_rotulo if velho else None,
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
    return Estabilizados(ids, macros, cores, cores_macro, casados, nova, mesma_cor, persistentes)


def _macrotemas_anteriores(
    casados: dict[int, int], anterior: Identidade, tamanhos: list[int], centros: np.ndarray | None
) -> tuple[list[int], dict[int, int]]:
    """Grupo de cada tópico novo pelos macrotemas anteriores (0 = o de mais documentos) e o macrotema de cada grupo.

    Um tópico casado fica no macrotema que tinha; um novo vai para o do tópico casado de centro mais parecido
    (sem centros, para o do maior tópico casado).
    """
    macro = {i: anterior.topicos[antigo].macro for i, antigo in casados.items()}
    referencias = sorted(casados)
    for i in range(len(tamanhos)):
        if i in macro:
            continue
        if centros is not None:
            parecido = max(referencias, key=lambda j: (float(centros[i] @ centros[j]), -j))
        else:
            parecido = max(referencias, key=lambda j: (tamanhos[j], -j))
        macro[i] = macro[parecido]
    peso: dict[int, int] = {}
    for i, m in macro.items():
        peso[m] = peso.get(m, 0) + tamanhos[i]
    ordem = sorted(peso, key=lambda m: (-peso[m], m))
    return [ordem.index(macro[i]) for i in range(len(tamanhos))], dict(enumerate(ordem))
