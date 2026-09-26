"""Etapa de embeddings: um vetor por documento, a partir do título e do resumo no idioma de análise.

O texto de análise nunca mistura idiomas (ADR 0003, adendo; ADR 0004):

- `resumo`: título e resumo no idioma de análise (`recorte.idioma_analise`, inglês por padrão);
- `reserva`: não há resumo nesse idioma; vão o resumo e o título em outro idioma. O modelo é multilíngue
  (no spike M0a, 99,9% dos resumos em português acharam a própria versão em inglês como vizinha mais próxima);
- `so_titulo`: o documento não tem resumo.

Cada documento fica marcado com a fonte, que aparece no cartão do mapa.

Os vetores ficam em `dados/embeddings/<modelo>@<digest>.npz` (ids, hash do texto, vetores), sem pickle. O
cache é incremental: só textos novos ou alterados vão ao Ollama. O digest do modelo no nome do arquivo faz uma
atualização do modelo gerar um cache novo; a versão do Ollama é registrada, mas não invalida o cache.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from mapa_da_ciencia.armazenamento import ARQUIVO, ler_documentos
from mapa_da_ciencia.config import ErroConfig
from mapa_da_ciencia.documento import Documento, Texto
from mapa_da_ciencia.llm.base import ErroProvedor
from mapa_da_ciencia.llm.memoria import garantir_modelo
from mapa_da_ciencia.llm.ollama import Ollama
from mapa_da_ciencia.manifesto import registrar_execucao
from mapa_da_ciencia.progresso import Progresso, ProgressoNulo
from mapa_da_ciencia.projeto import Projeto

if TYPE_CHECKING:
    import numpy as np

VERSAO_TEXTO = 1  # muda quando a montagem do texto de análise muda; invalida o cache
PASTA = "embeddings"
PONTO_DE_CONTROLE = 512  # documentos entre gravações do cache, para uma interrupção perder pouco
_RESERVA = ("pt", "es", "en", "fr")  # ordem dos idiomas quando falta o de análise

FonteAnalise = Literal["resumo", "reserva", "so_titulo"]


@dataclass(frozen=True)
class TextoAnalise:
    id: str
    texto: str
    idioma: str | None
    fonte: FonteAnalise

    @property
    def hash(self) -> str:
        return hashlib.sha256(self.texto.encode("utf-8")).hexdigest()[:16]


def _no_idioma(textos: list[Texto], idioma: str | None) -> Texto | None:
    return next((t for t in textos if t.idioma == idioma), None)


def _juntar(titulo: Texto | None, resumo: Texto | None) -> str:
    partes = [titulo.texto.strip().rstrip(".") if titulo else "", resumo.texto.strip() if resumo else ""]
    return ". ".join(p for p in partes if p)


def texto_de_analise(doc: Documento, idioma_analise: str) -> TextoAnalise | None:
    """Título e resumo no mesmo idioma: o de análise, senão o do resumo disponível; sem resumo, só o título."""
    if resumo := _no_idioma(doc.resumos, idioma_analise):
        return TextoAnalise(doc.id, _juntar(_no_idioma(doc.titulos, idioma_analise), resumo), idioma_analise, "resumo")
    if doc.resumos:
        ordem = [i for i in _RESERVA if i != idioma_analise]
        resumo = next((r for i in ordem if (r := _no_idioma(doc.resumos, i))), doc.resumos[0])
        titulo = _no_idioma(doc.titulos, resumo.idioma)
        return TextoAnalise(doc.id, _juntar(titulo, resumo), resumo.idioma, "reserva")
    titulo = doc.texto_em("titulos", [idioma_analise, *_RESERVA])
    if titulo is None or not titulo.texto.strip():
        return None
    return TextoAnalise(doc.id, _juntar(titulo, None), titulo.idioma, "so_titulo")


# ---------------------------------------------------------------- cache
def _slug(modelo: str) -> str:
    return modelo.replace("/", "_").replace(":", "_")


def _chave(num_ctx: int) -> str:
    return json.dumps({"versao_texto": VERSAO_TEXTO, "num_ctx": num_ctx, "truncate": True}, sort_keys=True)


def _ler_cache(caminho: Path, chave: str) -> dict[tuple[str, str], np.ndarray]:
    import numpy as np

    if not caminho.exists():
        return {}
    try:
        with np.load(caminho, allow_pickle=False) as z:
            if str(z["chave"]) != chave:
                return {}
            return {(i, h): v for i, h, v in zip(z["ids"], z["hashes"], z["vetores"], strict=True)}
    except (OSError, ValueError, KeyError):
        return {}  # arquivo corrompido: recalcula


def _gravar_cache(caminho: Path, chave: str, itens: dict[tuple[str, str], np.ndarray]) -> None:
    import numpy as np

    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_name(caminho.name + ".tmp.npz")
    chaves = sorted(itens)
    np.savez(
        temporario,
        chave=np.array(chave),
        ids=np.array([i for i, _ in chaves]),
        hashes=np.array([h for _, h in chaves]),
        vetores=np.stack([itens[k] for k in chaves]).astype(np.float32),
    )
    os.replace(temporario, caminho)


# ---------------------------------------------------------------- etapa
@dataclass
class Embeddings:
    """Resultado da etapa: a matriz (uma linha por documento com texto, na ordem dos ids), já normalizada."""

    ids: list[str]
    matriz: np.ndarray
    textos: list[TextoAnalise]
    modelo: str
    digest: str
    novos: int = 0
    do_cache: int = 0
    sem_texto: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    duracao_s: float = 0.0

    @property
    def por_fonte(self) -> dict[str, int]:
        return dict(Counter(t.fonte for t in self.textos))

    @property
    def rotulo_modelo(self) -> str:
        return f"{self.modelo}@{self.digest}" if self.digest else self.modelo


def _cache_sem_ollama(pasta: Path, modelo: str, chave: str, textos: list[TextoAnalise]) -> tuple[str, dict] | None:
    """Com o Ollama fora do ar: o cache mais recente deste modelo que cubra todos os textos."""
    precisa = {(t.id, t.hash) for t in textos}
    for arquivo in sorted(pasta.glob(f"{_slug(modelo)}@*.npz"), key=lambda a: a.stat().st_mtime, reverse=True):
        itens = _ler_cache(arquivo, chave)
        if precisa <= itens.keys():
            return arquivo.stem.split("@", 1)[1], itens
    return None


def calcular_embeddings(
    projeto: Projeto,
    *,
    refazer: bool = False,
    ollama: Ollama | None = None,
    progresso: Progresso | None = None,
) -> Embeddings:
    """Embeddings de todos os documentos do corpus, com cache incremental. Registra a etapa `embeddings`."""
    import numpy as np

    progresso = progresso or ProgressoNulo()
    cfg = projeto.config
    modelo, num_ctx, lote = cfg.modelos.embeddings.modelo, cfg.modelos.embeddings.num_ctx, cfg.modelos.embeddings.lote
    caminho_corpus = projeto.dados / ARQUIVO
    if not caminho_corpus.exists():
        raise ErroConfig("O projeto ainda não tem documentos. Rode `mapa coletar` antes.")
    inicio, t0 = datetime.now(UTC), time.perf_counter()

    textos: list[TextoAnalise] = []
    sem_texto: list[str] = []
    for doc in ler_documentos(caminho_corpus):
        if t := texto_de_analise(doc, cfg.recorte.idioma_analise):
            textos.append(t)
        else:
            sem_texto.append(doc.id)
    chave = _chave(num_ctx)
    pasta = projeto.dados / PASTA
    ollama = ollama or Ollama()
    avisos: list[str] = []

    try:
        instalado = ollama.instalado(modelo)
        versao_ollama = ollama.versao()
    except ErroProvedor:
        achado = None if refazer else _cache_sem_ollama(pasta, modelo, chave, textos)
        if achado is None:
            raise
        digest, itens = achado
        instalado, versao_ollama = None, "?"
        avisos.append("O Ollama não respondeu; os embeddings vieram inteiros do cache.")
    else:
        if instalado is None:
            garantir_modelo(ollama, modelo)  # levanta o erro com a dica de `ollama pull`
        digest = instalado.digest
        itens = {} if refazer else _ler_cache(pasta / f"{_slug(modelo)}@{digest}.npz", chave)

    caminho = pasta / f"{_slug(modelo)}@{digest}.npz"
    faltam = [t for t in textos if (t.id, t.hash) not in itens]
    carregou = False
    if faltam:
        carregou = not any(m.nome.removesuffix(":latest") == modelo for m in ollama.modelos_carregados())
        garantir_modelo(ollama, modelo)
        progresso.etapa(f"Embeddings ({modelo})", len(faltam))
        for inicio_bloco in range(0, len(faltam), PONTO_DE_CONTROLE):
            bloco = faltam[inicio_bloco : inicio_bloco + PONTO_DE_CONTROLE]
            vetores = [
                v
                for parte in ollama.embutir_lotes(
                    modelo, [t.texto for t in bloco], lote=lote, num_ctx=num_ctx, ao_avancar=progresso.avancar
                )
                for v in parte
            ]
            for t, v in zip(bloco, vetores, strict=True):
                itens[(t.id, t.hash)] = np.asarray(v, dtype=np.float32)
            _gravar_cache(caminho, chave, itens)
        if carregou:
            ollama.descarregar(modelo)  # libera a memória para o modelo dos rótulos
    elif refazer or not caminho.exists():
        _gravar_cache(caminho, chave, itens)

    matriz = np.stack([itens[(t.id, t.hash)] for t in textos]) if textos else np.zeros((0, 0), np.float32)
    normas = np.linalg.norm(matriz, axis=1, keepdims=True) if len(matriz) else 1
    matriz = (matriz / np.where(normas == 0, 1, normas)).astype(np.float32)
    progresso.fim()

    resultado = Embeddings(
        ids=[t.id for t in textos],
        matriz=matriz,
        textos=textos,
        modelo=modelo,
        digest=digest,
        novos=len(faltam),
        do_cache=len(textos) - len(faltam),
        sem_texto=sem_texto,
        avisos=avisos,
        duracao_s=round(time.perf_counter() - t0, 2),
    )
    registrar_execucao(
        projeto,
        "embeddings",
        inicio=inicio,
        fim=datetime.now(UTC),
        contagens={
            "documentos": len(textos),
            "novos": resultado.novos,
            "do_cache": resultado.do_cache,
            "reserva": resultado.por_fonte.get("reserva", 0),
            "so_titulo": resultado.por_fonte.get("so_titulo", 0),
            "sem_texto": len(sem_texto),
        },
        modelos={"embeddings": resultado.rotulo_modelo},
        parametros={
            "idioma_analise": cfg.recorte.idioma_analise,
            "num_ctx": num_ctx,
            "lote": lote,
            "versao_texto": VERSAO_TEXTO,
            "versao_ollama": versao_ollama,
            "dimensao": int(matriz.shape[1]) if len(matriz) else 0,
        },
    )
    return resultado
