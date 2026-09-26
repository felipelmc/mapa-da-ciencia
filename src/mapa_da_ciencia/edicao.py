"""Edição do `mapa.yaml` e do `codebook.yaml` pelo painel, sem perder os comentários.

A escrita é *round-trip* (`ruamel.yaml`): só os valores que mudaram são trocados, e os comentários, a ordem das
chaves e o estilo do arquivo ficam como estavam. O resultado é validado pelos mesmos modelos Pydantic da leitura
antes de ir para o disco; se for inválido, o arquivo não muda e os problemas voltam na mensagem.
"""

from __future__ import annotations

import io
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from .config import ErroConfig


def _yaml() -> YAML:
    y = YAML()
    y.preserve_quotes = True
    y.width = 4096  # não reflui linhas longas (definições do codebook)
    y.indent(mapping=2, sequence=4, offset=2)
    return y


IDENTIDADE = ("id", "valor")  # como reconhecer o mesmo item numa lista de variáveis ou de categorias


def _identidade(item: Any) -> Any:
    if isinstance(item, dict):
        chave = next((k for k in IDENTIDADE if k in item), None)
        return (chave, item[chave]) if chave else None
    return ("valor", item) if isinstance(item, str | int | float | bool) else None


def _lista(atual: CommentedSeq, valor: list[Any], *, substituir: bool) -> CommentedSeq:
    """A lista nova, reaproveitando os itens (e os comentários) dos que já estavam nela, reconhecidos pelo valor
    ou pelo `id`/`valor` de cada item."""
    antigos = {}
    for i, item in enumerate(atual):
        if (chave := _identidade(item)) is not None:
            antigos.setdefault(chave, (i, item))
    nova = CommentedSeq()
    if atual.fa.flow_style():
        nova.fa.set_flow_style()
    for j, item in enumerate(valor):
        chave = _identidade(item)
        if chave in antigos:
            i, velho = antigos[chave]
            if isinstance(item, dict) and isinstance(velho, CommentedMap):
                _mesclar(velho, item, substituir=substituir)
                item = velho
            nova.append(item)
            if i in atual.ca.items:
                nova.ca.items[j] = atual.ca.items[i]
        else:
            nova.append(item)
    return nova


def _mesclar(destino: CommentedMap, parcial: dict[str, Any], *, substituir: bool) -> None:
    """Põe os valores de `parcial` em `destino`, mantendo o que não mudou e os comentários. Com `substituir`,
    chaves ausentes de `parcial` saem."""
    if substituir:
        for chave in [k for k in destino if k not in parcial]:
            del destino[chave]
    for chave, valor in parcial.items():
        atual = destino.get(chave)
        if isinstance(valor, dict) and isinstance(atual, CommentedMap):
            _mesclar(atual, valor, substituir=substituir)
        elif isinstance(valor, list) and isinstance(atual, CommentedSeq):
            if _simples(atual) != valor:
                destino[chave] = _lista(atual, valor, substituir=substituir)
        elif atual != valor or chave not in destino:
            destino[chave] = valor


def _simples(no: Any) -> Any:
    """O documento do ruamel como dicionários e listas comuns (para validar)."""
    if isinstance(no, dict):
        return {str(k): _simples(v) for k, v in no.items()}
    if isinstance(no, list):
        return [_simples(v) for v in no]
    return no


def editar_yaml(
    caminho: Path, parcial: dict[str, Any], validar: Callable[[dict[str, Any]], Any], *, substituir: bool = False
) -> Any:
    """Aplica `parcial` ao YAML e grava, se `validar` aceitar o resultado. Devolve o que `validar` devolveu."""
    y = _yaml()
    doc = y.load(caminho.read_text(encoding="utf-8")) or CommentedMap()
    _mesclar(doc, parcial, substituir=substituir)
    try:
        validado = validar(_simples(doc))
    except ValidationError as e:
        problemas = "; ".join(f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in e.errors())
        raise ErroConfig(f"{caminho.name} ficaria inválido: {problemas}") from e
    saida = io.StringIO()
    y.dump(doc, saida)
    tmp = caminho.with_suffix(caminho.suffix + ".tmp")
    tmp.write_text(saida.getvalue(), encoding="utf-8")
    os.replace(tmp, caminho)
    return validado
