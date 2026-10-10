"""Edição do `mapa.yaml` e do `codebook.yaml` pelo painel, sem perder os comentários.

A escrita é *round-trip* (`ruamel.yaml`): só os valores que mudaram são trocados, e os comentários, a ordem das
chaves e o estilo do arquivo ficam como estavam. O resultado é validado pelos mesmos modelos Pydantic da leitura
antes de ir para o disco; se for inválido, o arquivo não muda e os problemas voltam na mensagem.

O painel manda o codebook inteiro, com os valores padrão que a leitura preencheu (`exemplos: []`, `rotulo: null`,
`categorias: []` numa booleana). Com `omitir_vazios`, um valor vazio (`None`, `[]`, `{}`) não cria a chave e tira a
que existia: o arquivo continua como a pessoa o escreveu. Só serve onde o padrão de todo campo opcional é vazio, como
no codebook.

Tirar uma entrada não leva junto o comentário de bloco que vem depois dela (o cabeçalho de uma seção, que o ruamel
prende à entrada anterior): ele passa para a entrada que fica antes.
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


def _vazio(valor: Any) -> bool:
    return valor is None or (isinstance(valor, list | dict) and not valor)


def _sem_vazios(valor: Any) -> Any:
    """Um item novo (que não estava no arquivo) sem as chaves de valor vazio, em qualquer nível."""
    if isinstance(valor, dict):
        return {k: _sem_vazios(v) for k, v in valor.items() if not _vazio(v)}
    if isinstance(valor, list):
        return [_sem_vazios(v) for v in valor]
    return valor


def _lista(atual: CommentedSeq, valor: list[Any], *, substituir: bool, omitir_vazios: bool = False) -> CommentedSeq:
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
                _mesclar(velho, item, substituir=substituir, omitir_vazios=omitir_vazios)
                item = velho
            nova.append(item)
            if i in atual.ca.items:
                nova.ca.items[j] = atual.ca.items[i]
        else:
            nova.append(_sem_vazios(item) if omitir_vazios else item)
    return nova


def _fim_da_entrada(no: Any, chave: Any) -> tuple[Any, Any]:
    """Onde o ruamel guarda o comentário que vem depois da entrada `chave` de `no`: no último valor escalar dela."""
    valor = no[chave]
    while isinstance(valor, CommentedMap | CommentedSeq) and len(valor):
        no, chave = valor, (list(valor.keys())[-1] if isinstance(valor, CommentedMap) else len(valor) - 1)
        valor = no[chave]
    return no, chave


def _tirar(destino: CommentedMap, chave: Any) -> None:
    """Tira a entrada sem perder o comentário de bloco que vem depois dela (o cabeçalho de uma seção, que o ruamel
    prende à entrada anterior): ele passa para a entrada que fica antes."""
    chaves = list(destino.keys())
    i = chaves.index(chave)
    no, ultima = _fim_da_entrada(destino, chave)
    slot = no.ca.items.get(ultima)
    token = slot[2] if slot and len(slot) > 2 else None
    del destino[chave]
    if token is None or i == 0:
        return
    texto = token.value if token.value.startswith("\n") else token.value.split("\n", 1)[-1]  # sem o comentário da linha
    if "#" not in texto:
        return
    no_ant, ultima_ant = _fim_da_entrada(destino, chaves[i - 1])
    slot_ant = no_ant.ca.items.setdefault(ultima_ant, [None, None, None, None])
    if slot_ant[2] is None:
        token.value = texto if texto.startswith("\n") else "\n" + texto
        slot_ant[2] = token
    else:
        slot_ant[2].value = slot_ant[2].value + texto.removeprefix("\n")


def _mesclar(destino: CommentedMap, parcial: dict[str, Any], *, substituir: bool, omitir_vazios: bool = False) -> None:
    """Põe os valores de `parcial` em `destino`, mantendo o que não mudou e os comentários. Com `substituir`,
    chaves ausentes de `parcial` saem; com `omitir_vazios`, as de valor vazio também (e não são criadas)."""
    if substituir:
        for chave in [k for k in destino if k not in parcial]:
            _tirar(destino, chave)
    for chave, valor in parcial.items():
        atual = destino.get(chave)
        if omitir_vazios and _vazio(valor):
            if chave in destino:
                _tirar(destino, chave)
        elif isinstance(valor, dict) and isinstance(atual, CommentedMap):
            _mesclar(atual, valor, substituir=substituir, omitir_vazios=omitir_vazios)
        elif isinstance(valor, list) and isinstance(atual, CommentedSeq):
            if _simples(atual) != valor:
                destino[chave] = _lista(atual, valor, substituir=substituir, omitir_vazios=omitir_vazios)
        elif atual != valor or chave not in destino:
            destino[chave] = _sem_vazios(valor) if omitir_vazios else valor


def _simples(no: Any) -> Any:
    """O documento do ruamel como dicionários e listas comuns (para validar)."""
    if isinstance(no, dict):
        return {str(k): _simples(v) for k, v in no.items()}
    if isinstance(no, list):
        return [_simples(v) for v in no]
    return no


def editar_yaml(
    caminho: Path,
    parcial: dict[str, Any],
    validar: Callable[[dict[str, Any]], Any],
    *,
    substituir: bool = False,
    omitir_vazios: bool = False,
) -> Any:
    """Aplica `parcial` ao YAML e grava, se `validar` aceitar o resultado. Devolve o que `validar` devolveu."""
    y = _yaml()
    doc = y.load(caminho.read_text(encoding="utf-8")) or CommentedMap()
    _mesclar(doc, parcial, substituir=substituir, omitir_vazios=omitir_vazios)
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
