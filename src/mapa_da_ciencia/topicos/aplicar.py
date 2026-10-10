"""Aplica o `rotulos.yaml` aos tópicos já calculados, sem refazê-los e sem chamar o modelo.

Corrigir um rótulo (no `rotulos.yaml` ou pelo editor do painel) não muda o agrupamento: basta trocar o rótulo no
`resultado.json` e exportar de novo. É o que `mapa topicos --aplicar-rotulos` (e o botão do painel) faz:

- uma entrada do `rotulos.yaml` vale para o tópico (ou o macrotema) do mesmo número, com a fonte `manual`;
- um macrotema de um tópico só leva o nome do tópico, como no `Rotulador`;
- um rótulo que era `manual` e saiu do `rotulos.yaml` volta às palavras-chave (`palavras`): o rótulo do modelo volta
  na próxima `mapa topicos`, que o tira do cache;
- o rótulo de um macrotema de vários tópicos escrito pelo modelo fica como está até a próxima `mapa topicos` (ele
  foi escrito a partir dos rótulos antigos dos tópicos).

Grava só o `resultado.json` (as atribuições e a identidade dos tópicos não mudam) e não registra um manifesto: o da
etapa de tópicos é o da última execução completa, que a Metodologia mostra.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field

from ..config import ErroConfig
from ..progresso import Progresso, ProgressoNulo
from ..projeto import Projeto
from ..trava_etapas import etapa
from .resultado import PASTA, MacroResultado, Resultado, TopicoResultado
from .rotulos import _Manuais, ler_manuais, palavras_do_macrotema


@dataclass
class ResumoAplicacao:
    """O que `aplicar_rotulos` mudou."""

    aplicados: int = 0  # tópicos e macrotemas com o rótulo do rotulos.yaml que mudou agora
    voltaram: int = 0  # rótulos manuais que saíram do rotulos.yaml e voltaram às palavras-chave
    sem_topico: list[str] = field(default_factory=list)  # entradas do rotulos.yaml sem tópico ou macrotema
    avisos: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        partes = [f"{self.aplicados} rótulo(s) aplicado(s)"]
        if self.voltaram:
            partes.append(f"{self.voltaram} voltaram às palavras-chave (o do modelo volta na próxima `mapa topicos`)")
        return "; ".join(partes) + "."


def _pelas_palavras(termos: list[str]) -> tuple[str, str, str]:
    return ", ".join(termos[:3]), f"Palavras-chave: {', '.join(termos[:8])}.", "palavras"


def aplicar(resultado: Resultado, manuais: _Manuais) -> ResumoAplicacao:
    """Aplica as entradas manuais ao resultado (no lugar) e diz o que mudou."""
    resumo = ResumoAplicacao()

    def trocar(x: TopicoResultado | MacroResultado, novo: tuple[str, str, str]) -> None:
        if (x.rotulo, x.descricao, x.rotulo_fonte) == novo:
            return
        if novo[2] == "manual":
            resumo.aplicados += 1
        elif x.rotulo_fonte == "manual":
            resumo.voltaram += 1
        x.rotulo, x.descricao, x.rotulo_fonte = novo

    topicos = {t.id: t for t in resultado.topicos}
    for t in resultado.topicos:
        if (m := manuais.topicos.get(t.id)) is not None:
            trocar(t, (m.rotulo, m.descricao, "manual"))
        elif t.rotulo_fonte == "manual":  # saiu do rotulos.yaml
            trocar(t, _pelas_palavras([p for p, _ in t.palavras]))
    palavras = {t.id: t.palavras for t in resultado.topicos}
    tamanhos = {t.id: t.n_nucleo for t in resultado.topicos}
    for m in resultado.macrotemas:
        if (e := manuais.macrotemas.get(m.id)) is not None:
            trocar(m, (e.rotulo, e.descricao, "manual"))
        elif len(m.topicos) == 1 and m.topicos[0] in topicos:  # um macrotema de um tópico só leva o nome dele
            t = topicos[m.topicos[0]]
            trocar(m, (t.rotulo, t.descricao, t.rotulo_fonte))
        elif m.rotulo_fonte == "manual":
            trocar(m, _pelas_palavras([p for p, _ in palavras_do_macrotema(m.topicos, palavras, tamanhos)]))
    ids_macros = {m.id for m in resultado.macrotemas}
    resumo.sem_topico = [f"tópico {i}" for i in sorted(set(manuais.topicos) - set(topicos))] + [
        f"macrotema {i}" for i in sorted(set(manuais.macrotemas) - ids_macros)
    ]
    return resumo


def rotulos_pendentes(resultado: Resultado, manuais: _Manuais) -> int:
    """Quantos rótulos o `rotulos.yaml` ainda mudaria nos tópicos (editados depois da última aplicação ou da última
    `mapa topicos`), contando os manuais que saíram do arquivo."""
    r = aplicar(deepcopy(resultado), manuais)
    return r.aplicados + r.voltaram


@etapa("topicos")
def aplicar_rotulos(projeto: Projeto, progresso: Progresso | None = None) -> ResumoAplicacao:
    """Aplica o `rotulos.yaml` aos tópicos em dia, grava o `resultado.json` e exporta. Não chama o modelo."""
    from ..armazenamento import ARQUIVO, ler_documentos
    from ..contrato.exportar import exportar
    from ..redes.pipeline import atualizar_assinatura_legada
    from .resultado import assinatura_corpus

    progresso = progresso or ProgressoNulo()
    pasta = projeto.dados / PASTA
    resultado = Resultado.ler(pasta)
    if resultado is None:
        raise ErroConfig("O projeto ainda não tem tópicos. Rode `mapa topicos` antes de aplicar os rótulos.")
    if resultado.assinatura != assinatura_corpus([d.id for d in ler_documentos(projeto.dados / ARQUIVO)]):
        raise ErroConfig(
            "Os tópicos são de um corpus anterior à última coleta. Rode `mapa topicos`: ele já usa o rotulos.yaml."
        )
    progresso.etapa("Rótulos do rotulos.yaml", 1)
    resumo = aplicar(resultado, ler_manuais(projeto.raiz))
    atualizar_assinatura_legada(projeto)  # redes de antes da 2.3.0: os rótulos ainda estavam na assinatura
    resultado.gravar_rotulos(pasta)
    progresso.avancar()
    if resumo.sem_topico:
        resumo.avisos.append(
            f"O rotulos.yaml tem entradas sem tópico correspondente ({', '.join(resumo.sem_topico)}): elas ficam de "
            "fora. Os números mudam quando os tópicos são refeitos; confira o painel."
        )
    resumo.avisos += exportar(projeto)
    progresso.fim()
    return resumo
