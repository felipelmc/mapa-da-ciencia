"""Rótulos e descrições dos tópicos e dos macrotemas, em português, escritos por um modelo local.

Para cada tópico, o modelo recebe as 15 palavras-chave e 5 títulos representativos e devolve um rótulo curto e
uma descrição (esquema JSON, temperatura 0, semente fixa). Para cada macrotema, recebe os rótulos dos seus
tópicos. Cuidados, do spike M0b (ADR 0005):

- **Acentos.** Modelos pequenos às vezes perdem acentos ("Gnero", "Genero"). O rótulo é conferido contra as
  palavras-chave e os títulos; se uma palavra perdeu o acento, há uma nova tentativa com um pedido que aponta a
  palavra (repetir o mesmo pedido, com temperatura 0, daria a mesma resposta). Se ainda assim faltar, o acento
  é corrigido pela forma do vocabulário. Só contam palavras de 4 letras ou mais cuja forma sem acento não é
  também uma palavra: senão "é" e "à" dos títulos virariam a forma certa de "e" e "a" (a versão 1 do prompt
  errou assim no piloto).
- **Estabilidade.** Um tópico casado com o da execução anterior (`identidade.py`) cujas palavras-chave mudaram
  pouco mantém o rótulo, sem chamar o modelo.
- **Edição à mão.** `rotulos.yaml`, na pasta do projeto, tem prioridade sobre tudo (`rotulo_fonte: manual`).
- **Memória.** O modelo só é carregado se couber na memória livre, e a etapa para limpa se a memória acabar no
  meio; os rótulos prontos ficam no cache (`estado.sqlite`) e a próxima execução continua de onde parou.

Com `sem_rotulos`, os rótulos são as palavras-chave mais fortes (`rotulo_fonte: palavras`).
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from mapa_da_ciencia.config import ErroConfig, ModeloLLM, ler_yaml
from mapa_da_ciencia.llm.base import ErroProvedor
from mapa_da_ciencia.llm.cache import CacheLLM, chave_de
from mapa_da_ciencia.llm.memoria import garantir_modelo, memoria_critica
from mapa_da_ciencia.llm.ollama import Ollama
from mapa_da_ciencia.progresso import Progresso, ProgressoNulo

TAREFA = "rotulos"
VERSAO_PROMPT = 4  # 2: acentos sem falsos positivos ("e"/"é", "a"/"à"); 3: caixa de frase; 4: macrotemas com palavras
ARQUIVO_MANUAL = "rotulos.yaml"
REUSO_MINIMO = 0.5  # Jaccard das 10 palavras-chave para manter o rótulo de um tópico casado
FonteRotulo = Literal["llm", "palavras", "manual"]

ESQUEMA = {
    "type": "object",
    "properties": {"rotulo": {"type": "string"}, "descricao": {"type": "string"}},
    "required": ["rotulo", "descricao"],
    "additionalProperties": False,
}
SISTEMA_TOPICO = (
    "Você nomeia tópicos de um mapa da literatura científica (ciência política, relações internacionais e áreas "
    "próximas). Dadas as palavras-chave e títulos representativos de um tópico, escreva em português do Brasil, "
    "com todos os acentos: um rótulo curto (no máximo 6 palavras, sem aspas nem ponto final) que nomeie o assunto, "
    "e uma descrição de uma ou duas frases do que os trabalhos do tópico estudam. O rótulo vai em caixa de frase: "
    "maiúscula só na primeira palavra, nas siglas e nos nomes próprios. Não comece o rótulo com 'Estudos sobre', "
    "'Tópico' ou 'Pesquisas'."
)
SISTEMA_MACRO = (
    "Você nomeia grandes áreas de um mapa da literatura científica. Dados os rótulos dos tópicos de uma área e as "
    "palavras-chave mais fortes dela, escreva em português do Brasil, com todos os acentos: um rótulo curto (de 2 a "
    "5 palavras, sem aspas nem ponto final, em caixa de frase: maiúscula só na primeira palavra, nas siglas e nos "
    "nomes próprios) que dê nome ao que os tópicos têm em comum, como o nome de uma subárea da disciplina, e não "
    "uma lista dos tópicos; use só palavras que existem em português. E uma descrição de uma frase."
)


@dataclass(frozen=True)
class Rotulo:
    rotulo: str
    descricao: str
    fonte: FonteRotulo


@dataclass
class EntradaTopico:
    palavras: list[str]
    titulos: list[str]
    anterior: Rotulo | None = None  # do tópico casado na execução anterior
    palavras_anteriores: list[str] = field(default_factory=list)


@dataclass
class ResumoRotulos:
    chamadas: int = 0
    do_cache: int = 0
    reaproveitados: int = 0
    manuais: int = 0
    acentos_corrigidos: int = 0
    modelo: str = ""


# ---------------------------------------------------------------- acentos
def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def _palavras(texto: str) -> list[str]:
    return re.findall(r"[^\W\d_]+", texto.lower())


# formas sem acento que também são palavras (verbos, sobretudo): nunca contam como acento perdido
SEM_ACENTO_VALIDAS = frozenset(
    {
        "esta",
        "estas",
        "para",
        "pelo",
        "pela",
        "pode",
        "pais",
        "secretaria",
        "secretarias",
        "media",
        "medias",
        "sabia",
        "valido",
        "critica",
        "criticas",
        "pratica",
        "praticas",
        "analise",
        "analises",
        "publica",
        "publicas",
        "publico",
        "publicos",
        "numero",
        "numeros",
        "historia",
        "historias",
        "duvida",
        "duvidas",
        "copia",
        "copias",
        "fabrica",
        "fabricas",
        "ultimo",
        "ultima",
        "ultimos",
        "ultimas",
        "transito",
        "influencia",
        "influencias",
        "referencia",
        "referencias",
        "evidencia",
        "evidencias",
        "potencia",
        "potencias",
        "agencia",
        "agencias",
        "sequencia",
        "sequencias",
    }
)
MINIMO_LETRAS = 4


def acentos_perdidos(texto: str, vocabulario: list[str]) -> dict[str, str]:
    """Palavras do texto sem o acento que têm no vocabulário: {"genero": "gênero"}.

    Palavras curtas ("e"/"é", "a"/"à"), formas sem acento que também são palavras ("critica"/"crítica") e
    palavras que aparecem das duas formas no próprio vocabulário não contam: não dá para saber qual é a certa.
    """
    formas = {p for termo in vocabulario for p in _palavras(termo)}
    acentuadas: dict[str, str] = {}
    for p in sorted(formas):
        base = _sem_acento(p)
        if base != p and len(base) >= MINIMO_LETRAS and base not in SEM_ACENTO_VALIDAS and base not in formas:
            acentuadas.setdefault(base, p)
    return {p: acentuadas[p] for p in _palavras(texto) if p in acentuadas}


def _corrigir(texto: str, trocas: dict[str, str]) -> str:
    def trocar(m: re.Match) -> str:
        palavra = m.group(0)
        certa = trocas.get(palavra.lower())
        if certa is None:
            return palavra
        return certa.capitalize() if palavra[0].isupper() else certa

    return re.sub(r"[^\W\d_]+", trocar, texto)


def _limpar(texto: str) -> str:
    return " ".join(texto.strip().strip('"').strip("'").split()).rstrip(".")


# ---------------------------------------------------------------- edição à mão
class _RotuloManual(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rotulo: str
    descricao: str = ""


class _Manuais(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topicos: dict[int, _RotuloManual] = Field(default_factory=dict)
    macrotemas: dict[int, _RotuloManual] = Field(default_factory=dict)


def ler_manuais(raiz: Path) -> _Manuais:
    arquivo = raiz / ARQUIVO_MANUAL
    if not arquivo.exists():
        return _Manuais()
    try:
        return _Manuais.model_validate(ler_yaml(arquivo.read_text(encoding="utf-8"), arquivo.name) or {})
    except (yaml.YAMLError, ValidationError) as e:
        raise ErroConfig(
            f"{ARQUIVO_MANUAL} inválido: {e}. O formato é `topicos: {{12: {{rotulo: ..., descricao: ...}}}}`."
        ) from e


# ---------------------------------------------------------------- rotulador
class Rotulador:
    def __init__(
        self,
        cfg: ModeloLLM,
        estado: Path,
        *,
        ollama: Ollama | None = None,
        progresso: Progresso | None = None,
    ) -> None:
        self.cfg = cfg
        self.ollama = ollama or Ollama()
        self.progresso = progresso or ProgressoNulo()
        self.estado = estado
        self.resumo = ResumoRotulos(modelo=cfg.modelo)
        self._digest: str | None = None
        self._carregou = False
        self._pronto = False

    def _identificar(self) -> str:
        """`nome@digest` do modelo, para a chave do cache: basta ele estar instalado (sem carregá-lo)."""
        if self._digest is None:
            instalado = self.ollama.instalado(self.cfg.modelo)
            self._digest = (instalado or garantir_modelo(self.ollama, self.cfg.modelo)).digest
            self.resumo.modelo = f"{self.cfg.modelo}@{self._digest}"
        return self.resumo.modelo

    def _preparar(self) -> str:
        """Confere a memória e carrega o modelo, só antes da primeira chamada de verdade (com tudo no cache, nunca)."""
        modelo = self._identificar()
        if not self._pronto:
            ja_carregado = any(
                m.nome.removesuffix(":latest") == self.cfg.modelo.removesuffix(":latest")
                for m in self.ollama.modelos_carregados()
            )
            garantir_modelo(self.ollama, self.cfg.modelo)
            self._carregou = not ja_carregado
            self._pronto = True
        return modelo

    def _perguntar(self, cache: CacheLLM, sistema: str, pedido: str, vocabulario: list[str]) -> Rotulo:
        modelo = self._identificar()
        parametros = (self.cfg.num_ctx, self.cfg.temperatura, self.cfg.semente, self.cfg.pensar)
        chave = chave_de(VERSAO_PROMPT, sistema, pedido, modelo, parametros)
        if (guardado := cache.obter(TAREFA, chave)) is not None:
            self.resumo.do_cache += 1
            return Rotulo(guardado["rotulo"], guardado["descricao"], "llm")
        self._preparar()
        if memoria_critica():
            raise ErroProvedor(
                "A memória do computador acabou no meio dos rótulos. Feche programas pesados e rode de novo: "
                "os rótulos já escritos estão guardados e não serão pedidos outra vez."
            )
        mensagens = [{"role": "system", "content": sistema}, {"role": "user", "content": pedido}]
        resposta = self._gerar(mensagens)
        perdidos = acentos_perdidos(f"{resposta['rotulo']} {resposta['descricao']}", vocabulario)
        if perdidos:  # outra tentativa, com um pedido que aponta as palavras
            aviso = ", ".join(f"'{certa}'" for certa in perdidos.values())
            mensagens.append({"role": "assistant", "content": f"{resposta['rotulo']} — {resposta['descricao']}"})
            mensagens.append({"role": "user", "content": f"Reescreva com os acentos corretos: {aviso}."})
            resposta = self._gerar(mensagens)
            perdidos = acentos_perdidos(f"{resposta['rotulo']} {resposta['descricao']}", vocabulario)
            if perdidos:
                resposta = {k: _corrigir(v, perdidos) for k, v in resposta.items()}
                self.resumo.acentos_corrigidos += 1
        cache.guardar(TAREFA, chave, resposta, modelo)
        return Rotulo(resposta["rotulo"], resposta["descricao"], "llm")

    def _gerar(self, mensagens: list[dict[str, str]]) -> dict[str, str]:
        self.resumo.chamadas += 1
        r = self.ollama.gerar_estruturado(
            self.cfg.modelo,
            mensagens,
            ESQUEMA,
            num_ctx=self.cfg.num_ctx,
            temperatura=self.cfg.temperatura,
            semente=self.cfg.semente,
            pensar=self.cfg.pensar,
        )
        rotulo, descricao = _limpar(str(r.get("rotulo", ""))), str(r.get("descricao", "")).strip()
        if not rotulo:
            raise ErroProvedor(f"{self.cfg.modelo} devolveu um rótulo vazio.")
        return {"rotulo": rotulo, "descricao": descricao}

    def fim(self) -> None:
        if self._carregou:
            self.ollama.descarregar(self.cfg.modelo)
            self._carregou = False

    # ------------------------------------------------------------ tarefas
    def topicos(self, entradas: dict[int, EntradaTopico], *, sem_llm: bool, manuais: _Manuais) -> dict[int, Rotulo]:
        saida: dict[int, Rotulo] = {}
        pendentes = []
        for t, e in entradas.items():
            if t in manuais.topicos:
                m = manuais.topicos[t]
                saida[t] = Rotulo(m.rotulo, m.descricao, "manual")
                self.resumo.manuais += 1
            elif sem_llm:
                saida[t] = Rotulo(
                    ", ".join(e.palavras[:3]), f"Palavras-chave: {', '.join(e.palavras[:8])}.", "palavras"
                )
            elif e.anterior and e.anterior.fonte == "llm" and _parecidas(e.palavras, e.palavras_anteriores):
                saida[t] = e.anterior
                self.resumo.reaproveitados += 1
            else:
                pendentes.append(t)
        if pendentes:
            self.progresso.etapa(f"Rótulos ({self.cfg.modelo})", len(pendentes))
            with CacheLLM(self.estado) as cache:
                for t in pendentes:
                    e = entradas[t]
                    pedido = "Palavras-chave: " + ", ".join(e.palavras[:15])
                    pedido += "\n\nTítulos representativos:\n" + "\n".join(f"- {x}" for x in e.titulos[:5])
                    saida[t] = self._perguntar(cache, SISTEMA_TOPICO, pedido, e.palavras + e.titulos)
                    self.progresso.avancar()
        return saida

    def macrotemas(
        self,
        grupos: dict[int, list[int]],
        rotulos_topicos: dict[int, Rotulo],
        palavras: dict[int, list[tuple[str, float]]],
        *,
        sem_llm: bool,
        manuais: _Manuais,
    ) -> dict[int, Rotulo]:
        """`grupos`: macrotema → tópicos (do maior para o menor); `palavras`: macrotema → (termo, peso)."""
        saida: dict[int, Rotulo] = {}
        with CacheLLM(self.estado) as cache:
            for m, topicos in grupos.items():
                if m in manuais.macrotemas:
                    r = manuais.macrotemas[m]
                    saida[m] = Rotulo(r.rotulo, r.descricao, "manual")
                    self.resumo.manuais += 1
                    continue
                termos = [t for t, _ in sorted(palavras[m], key=lambda par: -par[1])]
                if sem_llm:
                    saida[m] = Rotulo(", ".join(termos[:3]), f"Palavras-chave: {', '.join(termos[:8])}.", "palavras")
                    continue
                if len(topicos) == 1:  # um macrotema de um tópico só leva o nome dele
                    saida[m] = rotulos_topicos[topicos[0]]
                    continue
                nomes = [rotulos_topicos[t].rotulo for t in topicos]
                pedido = "Tópicos desta área:\n" + "\n".join(f"- {n}" for n in nomes)
                pedido += "\n\nPalavras-chave da área: " + ", ".join(termos[:10])
                saida[m] = self._perguntar(cache, SISTEMA_MACRO, pedido, nomes + termos)
        return saida


def _parecidas(a: list[str], b: list[str]) -> bool:
    x, y = set(a[:10]), set(b[:10])
    return bool(x | y) and len(x & y) / len(x | y) >= REUSO_MINIMO


def palavras_do_macrotema(topicos: list[int], palavras: dict[int, list[tuple[str, float]]], tamanhos: dict[int, int]):
    """Palavras-chave de um macrotema: as dos tópicos, pesadas pelo tamanho de cada um."""
    soma: Counter[str] = Counter()
    for t in topicos:
        for termo, peso in palavras.get(t, []):
            soma[termo] += peso * tamanhos.get(t, 1)
    return soma.most_common(15)
