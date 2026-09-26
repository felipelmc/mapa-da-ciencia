"""`mapa diagnostico`: confere se a máquina está pronta para rodar o pipeline.

Produz uma lista de checagens (ok / aviso / erro), cada uma com uma dica do que fazer.
A apresentação fica na CLI; o painel reaproveita a mesma lista.
"""

from __future__ import annotations

import ssl
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import httpx

from mapa_da_ciencia import rede
from mapa_da_ciencia.formatar import gb
from mapa_da_ciencia.llm.base import ErroProvedor
from mapa_da_ciencia.llm.ollama import Ollama
from mapa_da_ciencia.llm.perfis import TAMANHOS_GB, sugerir_perfil
from mapa_da_ciencia.projeto import Projeto
from mapa_da_ciencia.recursos import cabe_na_memoria, disco_livre_gb, memoria

Estado = Literal["ok", "aviso", "erro"]

URLS_REDE = {
    "ArticleMeta (SciELO)": "https://articlemeta.scielo.org/api/v1/journal/identifiers/?collection=scl&limit=1",
    # busca de um trabalho por DOI não consome créditos do OpenAlex
    "OpenAlex": "https://api.openalex.org/works/doi:10.1590/1807-019120243011?select=id",
}

DICAS_OLLAMA = (
    "Variáveis do servidor Ollama que costumam ajudar (defina antes de abrir o Ollama): "
    "OLLAMA_NUM_PARALLEL=2 (atende chamadas simultâneas), OLLAMA_FLASH_ATTENTION=1 e "
    "OLLAMA_KV_CACHE_TYPE=q8_0 (menos memória por contexto)."
)


@dataclass(frozen=True)
class Checagem:
    grupo: str
    item: str
    estado: Estado
    detalhe: str
    dica: str = ""


def _maquina(projeto: Projeto | None) -> list[Checagem]:
    mem = memoria()
    perfil = sugerir_perfil(mem.total_gb)
    saida = [
        Checagem("Máquina", "Memória total", "ok", f"{mem.total_gb:.0f} GB (perfil sugerido: {perfil.nome})"),
        Checagem(
            "Máquina",
            "Memória disponível agora",
            "ok" if mem.disponivel_gb >= 4 else "aviso",
            gb(mem.disponivel_gb),
            "" if mem.disponivel_gb >= 4 else "Pouca memória livre: feche programas pesados antes de rodar modelos.",
        ),
    ]
    if mem.swap_total_gb > 0:
        cheio = mem.swap_usado_gb / mem.swap_total_gb > 0.8
        saida.append(
            Checagem(
                "Máquina",
                "Swap",
                "aviso" if cheio else "ok",
                f"{gb(mem.swap_usado_gb)} de {gb(mem.swap_total_gb)} em uso",
                "O swap está quase cheio: a máquina pode ficar lenta ao carregar modelos." if cheio else "",
            )
        )
    livre = disco_livre_gb(projeto.raiz if projeto else Path.home())
    estado: Estado = "erro" if livre < 2 else "aviso" if livre < 10 else "ok"
    saida.append(
        Checagem(
            "Máquina",
            "Disco livre",
            estado,
            gb(livre),
            "" if estado == "ok" else "Pouco espaço: modelos ocupam de 0,6 a 17 GB, e a coleta do piloto, ~200 MB.",
        )
    )
    return saida


def _modelos(ollama: Ollama, projeto: Projeto | None) -> list[Checagem]:
    try:
        versao = ollama.versao()
    except ErroProvedor as e:
        return [Checagem("Ollama", "Servidor", "erro", "não está respondendo", str(e))]
    saida = [Checagem("Ollama", "Servidor", "ok", f"versão {versao} em {ollama.endereco}")]
    for m in ollama.modelos_carregados():
        saida.append(Checagem("Ollama", f"Carregado: {m.nome}", "ok", f"{gb(m.tamanho_gb)}, {m.fracao_gpu:.0%} na GPU"))

    if projeto:
        cfg = projeto.config.modelos
        papeis = {"embeddings": cfg.embeddings.modelo, "classificação": cfg.classificacao.modelo}
        papeis["rótulos"] = cfg.rotulos.modelo
        grupo = "Modelos do projeto"
    else:
        perfil = sugerir_perfil()
        papeis = {"embeddings": perfil.embeddings, "classificação": perfil.classificacao, "rótulos": perfil.rotulos}
        grupo = f"Modelos do perfil {perfil.nome}"

    vistos: dict[str, list[str]] = {}
    for papel, nome in papeis.items():
        vistos.setdefault(nome, []).append(papel)
    for nome, usos in vistos.items():
        item = f"{nome} ({', '.join(usos)})"
        inst = ollama.instalado(nome)
        if inst is None:
            tam = TAMANHOS_GB.get(nome)
            tamanho = f" (download de ~{gb(tam)})" if tam else ""
            saida.append(Checagem(grupo, item, "erro", "não instalado", f"Rode: ollama pull {nome}{tamanho}"))
            continue
        folga = cabe_na_memoria(inst.tamanho_gb)
        saida.append(
            Checagem(
                grupo,
                item,
                "ok" if folga.cabe else "aviso",
                f"instalado, {gb(inst.tamanho_gb)}",
                "" if folga.cabe else folga.explicar(nome),
            )
        )
    return saida


def _rede(http: httpx.Client) -> list[Checagem]:
    saida = []
    for nome, url in URLS_REDE.items():
        try:
            r = http.get(url, timeout=20)
            r.raise_for_status()
            saida.append(Checagem("Rede", nome, "ok", "HTTPS funcionando"))
        except httpx.ConnectError as e:
            if isinstance(e.__cause__, ssl.SSLError) or "CERTIFICATE" in str(e).upper():
                dica = (
                    "Falha de certificado: a rede pode usar um proxy com autoridade certificadora própria (ADR 0001)."
                )
            else:
                dica = "Sem conexão: confira a internet ou o proxy da instituição."
            saida.append(Checagem("Rede", nome, "erro", "não conectou", dica))
        except httpx.HTTPError as e:
            saida.append(
                Checagem("Rede", nome, "aviso", f"respondeu com erro: {e}", "Tente de novo em alguns minutos.")
            )
    return saida


def diagnosticar(
    projeto: Projeto | None = None,
    *,
    ollama: Ollama | None = None,
    checar_rede: bool = True,
) -> list[Checagem]:
    checagens = _maquina(projeto) + _modelos(ollama or Ollama(), projeto)
    if checar_rede:
        with rede.cliente(pasta=projeto.raiz if projeto else None) as http:
            checagens += _rede(http)
    return checagens
