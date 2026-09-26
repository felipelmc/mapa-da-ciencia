"""O modelo está pronto para uso? Instalado, e já carregado ou cabendo na memória livre agora.

Usado pelo `mapa diagnostico` (que só informa) e pelas etapas que carregam modelos (que param antes de
carregar um modelo que não cabe, em vez de levar o computador ao swap; ver ADR 0005).
"""

from __future__ import annotations

from dataclasses import dataclass

from mapa_da_ciencia.formatar import gb
from mapa_da_ciencia.llm.base import ErroProvedor, ModeloInstalado, ProvedorLLM
from mapa_da_ciencia.llm.perfis import TAMANHOS_GB
from mapa_da_ciencia.recursos import Folga, cabe_na_memoria


@dataclass(frozen=True)
class Situacao:
    nome: str
    instalado: ModeloInstalado | None
    carregado: bool
    folga: Folga | None  # só quando está instalado e ainda não carregado

    @property
    def pronto(self) -> bool:
        return self.instalado is not None and (self.carregado or (self.folga is not None and self.folga.cabe))

    def explicar(self) -> str:
        if self.instalado is None:
            tamanho = TAMANHOS_GB.get(self.nome)
            download = f" (download de ~{gb(tamanho)})" if tamanho else ""
            return f"O modelo {self.nome} não está instalado. Rode: ollama pull {self.nome}{download}"
        if self.carregado:
            return f"{self.nome} já está carregado na memória."
        assert self.folga is not None
        return self.folga.explicar(self.nome)


def _sem_latest(nome: str) -> str:
    return nome.removesuffix(":latest")


def situacao(ollama: ProvedorLLM, nome: str) -> Situacao:
    """Um modelo já carregado não precisa de folga: a memória livre já o desconta."""
    instalado = next((m for m in ollama.listar_modelos() if _sem_latest(m.nome) == _sem_latest(nome)), None)
    if instalado is None:
        return Situacao(nome, None, False, None)
    if _sem_latest(nome) in {_sem_latest(m.nome) for m in ollama.modelos_carregados()}:
        return Situacao(nome, instalado, True, None)
    return Situacao(nome, instalado, False, cabe_na_memoria(instalado.tamanho_gb))


def garantir_modelo(ollama: ProvedorLLM, nome: str) -> ModeloInstalado:
    """O modelo instalado, se ele puder ser usado agora; senão, `ErroProvedor` dizendo o que fazer."""
    s = situacao(ollama, nome)
    if not s.pronto:
        raise ErroProvedor(s.explicar())
    assert s.instalado is not None
    return s.instalado


def memoria_critica(*, minimo_livre_gb: float = 0.5, minimo_swap_gb: float = 0.3) -> bool:
    """A memória acabou: quase nada livre e o swap no fim. Etapas longas param aqui, limpas (ADR 0005)."""
    from mapa_da_ciencia import recursos

    m = recursos.memoria()
    return m.disponivel_gb < minimo_livre_gb and (m.swap_total_gb - m.swap_usado_gb) < minimo_swap_gb
