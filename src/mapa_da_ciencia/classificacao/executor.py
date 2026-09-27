"""O executor da classificação: pede ao modelo, confere, tenta de novo quando precisa e guarda cada resposta.

- **Retomável.** Cada resposta válida vai para o cache do `estado.sqlite` assim que chega, com a chave (texto,
  codebook, modelo@digest, versão do prompt, parâmetros). Rodar de novo, depois de uma interrupção ou de um
  `kill -9`, só pede o que falta; mudar o codebook, o modelo ou o prompt invalida tudo de uma vez.
- **Uma nova tentativa** por documento quando a resposta não segue o codebook ou quando alguma evidência não está
  no texto (fora as dispensadas), com uma mensagem que aponta o problema; fica a melhor das duas.
- **Memória.** O modelo só é checado (e carregado) se houver algo a pedir; entre um documento e outro, se a
  memória acabar, a etapa para com uma explicação (ADR 0005). No fim, o modelo é descarregado se foi a etapa que o
  carregou.
- **Concorrência** de `modelos.classificacao.concorrencia` (padrão 1: no Mac do piloto, o Ollama atende uma chamada
  por vez, e mais só aumenta a fila).
"""

from __future__ import annotations

import time
from collections.abc import Iterable, Iterator
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config import Codebook, ModeloLLM
from ..documento import Documento
from ..llm.base import ErroProvedor
from ..llm.cache import CacheLLM, chave_de
from ..llm.memoria import garantir_modelo, memoria_critica
from ..llm.ollama import Ollama
from ..progresso import Progresso, ProgressoNulo
from .codebook import esquema, sem_informacao, validar
from .evidencia import Conferencia, conferir
from .prompt import VERSAO_PROMPT, assinatura, mensagem_correcao, mensagem_documento, mensagem_sistema

TAREFA = "classificacao"


@dataclass(frozen=True)
class Texto:
    """O que é classificado: o título e o resumo que o painel mostra (os *offsets* da evidência valem neles)."""

    doc: str
    titulo: str | None
    resumo: str
    idioma: str | None


def textos_para_classificar(documentos: Iterable[Documento], idiomas: list[str]) -> tuple[list[Texto], list[str]]:
    """Os textos a classificar, no idioma de exibição (com o de análise como reserva), e os documentos sem resumo,
    que ficam fora."""
    textos, sem_resumo = [], []
    for d in documentos:
        resumo = d.texto_em("resumos", idiomas)
        if resumo is None or not resumo.texto.strip():
            sem_resumo.append(d.id)
            continue
        titulo = d.texto_em("titulos", [resumo.idioma, *idiomas])
        textos.append(Texto(d.id, titulo.texto if titulo else None, resumo.texto, resumo.idioma))
    return textos, sem_resumo


@dataclass
class Classificacao:
    """A classificação de um documento: valor, evidência e conferência por variável."""

    doc: str
    valores: dict[str, Any]
    evidencias: dict[str, str]
    conferencias: dict[str, Conferencia]
    tentativas: int
    valida_na_primeira: bool
    segundos: float
    do_cache: bool = False


@dataclass
class Contadores:
    chamadas: int = 0
    do_cache: int = 0
    novos: int = 0
    falhas: list[str] = field(default_factory=list)
    segundos: list[float] = field(default_factory=list)


class Classificador:
    def __init__(
        self,
        cfg: ModeloLLM,
        codebook: Codebook,
        estado: Path,
        *,
        ollama: Ollama | None = None,
        progresso: Progresso | None = None,
    ) -> None:
        self.cfg = cfg
        self.codebook = codebook
        self._assinatura = assinatura(codebook)
        self.estado = estado
        self.ollama = ollama or Ollama()
        self.progresso = progresso or ProgressoNulo()
        self.contadores = Contadores()
        self._sistema = mensagem_sistema(codebook)
        self._esquema = esquema(codebook)
        self._variaveis = {v.id: v for v in codebook.variaveis}
        self._modelo: str | None = None
        self._pronto = False
        self._carregou = False

    # ------------------------------------------------------------ modelo
    @property
    def modelo(self) -> str:
        """`nome@digest` do modelo, que entra na chave do cache (um modelo atualizado classifica de novo)."""
        if self._modelo is None:
            nome = self.cfg.modelo.removesuffix(":latest")
            instalado = next((m for m in self.ollama.listar_modelos() if m.nome.removesuffix(":latest") == nome), None)
            if instalado is None:
                garantir_modelo(self.ollama, self.cfg.modelo)  # explica como instalar
            assert instalado is not None
            self._modelo = f"{self.cfg.modelo}@{instalado.digest}"
        return self._modelo

    def _preparar(self) -> None:
        if not self._pronto:
            ja_carregado = any(
                m.nome.removesuffix(":latest") == self.cfg.modelo.removesuffix(":latest")
                for m in self.ollama.modelos_carregados()
            )
            garantir_modelo(self.ollama, self.cfg.modelo)
            self._carregou = not ja_carregado
            self._pronto = True

    def fim(self) -> None:
        if self._carregou:
            self.ollama.descarregar(self.cfg.modelo)
            self._carregou = False

    # ------------------------------------------------------------ um documento
    def chave(self, texto: Texto) -> str:
        parametros = (self.cfg.num_ctx, self.cfg.temperatura, self.cfg.semente, self.cfg.pensar)
        return chave_de(VERSAO_PROMPT, self._assinatura, self.modelo, parametros, texto.titulo, texto.resumo)

    def _conferir(self, texto: Texto, valores: dict[str, Any], evidencias: dict[str, str]) -> dict[str, Conferencia]:
        return {
            v: conferir(evidencias[v], texto.resumo, texto.titulo, sem_informacao=sem_informacao(var, valores[v]))
            for v, var in self._variaveis.items()
            if v in valores
        }

    def _gerar(self, mensagens: list[dict[str, str]]) -> tuple[Any, str | None]:
        """A resposta crua do modelo, ou None com o motivo quando ela nem é JSON."""
        self.contadores.chamadas += 1
        try:
            resposta = self.ollama.gerar_estruturado(
                self.cfg.modelo,
                mensagens,
                self._esquema,
                num_ctx=self.cfg.num_ctx,
                temperatura=self.cfg.temperatura,
                semente=self.cfg.semente,
                pensar=self.cfg.pensar,
            )
        except ErroProvedor as erro:
            if "JSON" not in str(erro):
                raise  # Ollama fora do ar, modelo ausente: para a etapa
            return None, "a resposta não era um JSON válido"
        return resposta, None

    def _tentar(self, texto: Texto) -> dict[str, Any] | None:
        """Até duas chamadas; devolve o que vai para o cache, ou None se nenhuma resposta seguiu o codebook."""
        inicio = time.perf_counter()
        mensagens = [
            {"role": "system", "content": self._sistema},
            {"role": "user", "content": mensagem_documento(texto.titulo, texto.resumo)},
        ]
        tentativas: list[tuple[Any, Any]] = []  # (resposta validada, conferências)
        bruto, erro = self._gerar(mensagens)
        for n in (1, 2):
            r = validar(bruto, self.codebook)
            if erro:
                r.problemas.insert(0, erro)
            conf = self._conferir(texto, r.valores, r.evidencias) if r.valida else {}
            ausentes = [v for v, c in conf.items() if c.status == "ausente"]
            tentativas.append((r, conf))
            if n == 2 or (r.valida and not ausentes):
                break
            mensagens += [
                {"role": "assistant", "content": _json(bruto)},
                {"role": "user", "content": mensagem_correcao(r.problemas, ausentes)},
            ]
            bruto, erro = self._gerar(mensagens)
        validas = [(r, c) for r, c in tentativas if r.valida]
        if not validas:
            return None
        melhor, _ = min(validas, key=lambda rc: sum(c.status == "ausente" for c in rc[1].values()))
        return {
            "valores": melhor.valores,
            "evidencias": melhor.evidencias,
            "tentativas": len(tentativas),
            "valida_na_primeira": tentativas[0][0].valida,
            "segundos": round(time.perf_counter() - inicio, 3),
        }

    def _montar(self, texto: Texto, guardado: dict[str, Any], *, do_cache: bool) -> Classificacao:
        return Classificacao(
            doc=texto.doc,
            valores=guardado["valores"],
            evidencias=guardado["evidencias"],
            conferencias=self._conferir(texto, guardado["valores"], guardado["evidencias"]),
            tentativas=guardado["tentativas"],
            valida_na_primeira=guardado["valida_na_primeira"],
            segundos=guardado["segundos"],
            do_cache=do_cache,
        )

    # ------------------------------------------------------------ muitos documentos
    def pendentes(self, textos: Iterable[Texto]) -> list[Texto]:
        """Os textos que ainda não estão no cache."""
        with CacheLLM(self.estado) as cache:
            return [t for t in textos if cache.obter(TAREFA, self.chave(t)) is None]

    def do_cache(self, textos: Iterable[Texto]) -> list[Classificacao]:
        """As classificações que já estão no cache, sem chamar o modelo nem mexer nos contadores."""
        with CacheLLM(self.estado) as cache:
            guardados = ((t, cache.obter(TAREFA, self.chave(t))) for t in textos)
            return [self._montar(t, g, do_cache=True) for t, g in guardados if g is not None]

    def classificar(self, textos: list[Texto]) -> Iterator[Classificacao]:
        """As classificações, na ordem em que ficam prontas: primeiro as do cache, depois as novas."""
        with CacheLLM(self.estado) as cache:
            novos = []
            for t in textos:
                guardado = cache.obter(TAREFA, self.chave(t))
                if guardado is None:
                    novos.append(t)
                    continue
                self.contadores.do_cache += 1
                yield self._montar(t, guardado, do_cache=True)
            if not novos:
                return
            self._preparar()
            self.progresso.etapa(f"Classificação ({self.cfg.modelo})", len(novos))
            fila = iter(novos)
            with ThreadPoolExecutor(max(1, self.cfg.concorrencia)) as pool:
                em_voo: dict[Future, Texto] = {}

                def submeter() -> None:
                    t = next(fila, None)
                    if t is None:
                        return
                    if memoria_critica():
                        raise ErroProvedor(
                            "A memória do computador acabou no meio da classificação. Feche programas pesados e rode "
                            "de novo: os documentos já classificados estão guardados e não serão pedidos outra vez."
                        )
                    em_voo[pool.submit(self._tentar, t)] = t

                for _ in range(max(1, self.cfg.concorrencia)):
                    submeter()
                while em_voo:
                    prontos, _ = wait(em_voo, return_when=FIRST_COMPLETED)
                    for futuro in prontos:
                        t = em_voo.pop(futuro)
                        resposta = futuro.result()
                        self.progresso.avancar()
                        if resposta is None:
                            self.contadores.falhas.append(t.doc)
                        else:
                            cache.guardar(TAREFA, self.chave(t), resposta, self.modelo)
                            self.contadores.novos += 1
                            self.contadores.segundos.append(resposta["segundos"])
                            yield self._montar(t, resposta, do_cache=False)
                        submeter()


def _json(valor: Any) -> str:
    import json

    return json.dumps(valor, ensure_ascii=False) if valor is not None else ""
