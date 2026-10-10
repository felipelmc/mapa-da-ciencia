"""Edição do `mapa.yaml` e do `codebook.yaml` pelo painel, sem perder os comentários.

A escrita é *round-trip* (`ruamel.yaml`): só os valores que mudaram são trocados, e os comentários, a ordem das
chaves e o estilo do arquivo ficam como estavam. O resultado é validado pelos mesmos modelos Pydantic da leitura
antes de ir para o disco; se for inválido, o arquivo não muda e os problemas voltam na mensagem.

O painel manda o codebook inteiro, com os valores padrão que a leitura preencheu (`exemplos: []`, `rotulo: null`,
`categorias: []` numa booleana). Com `omitir_vazios`, um valor vazio (`None`, `[]`, `{}`) não cria a chave e tira a
que existia: o arquivo continua como a pessoa o escreveu. Só serve onde o padrão de todo campo opcional é vazio, como
no codebook.

Tirar uma entrada (ou trocar um item de lista por outro) não leva junto os comentários de bloco dela: o cabeçalho
da seção seguinte, que o ruamel prende ao último valor da entrada que sai, vai para antes da entrada seguinte; sem
ela, para antes da seguinte de um nível acima, e, sem nenhuma, para o fim do arquivo.
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
from ruamel.yaml.error import CommentMark
from ruamel.yaml.tokens import CommentToken

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


def _lista(
    atual: CommentedSeq,
    valor: list[Any],
    *,
    substituir: bool,
    omitir_vazios: bool = False,
    caminho: list[tuple[Any, Any]] | None = None,
) -> CommentedSeq:
    """A lista nova, reaproveitando os itens (e os comentários) dos que já estavam nela, reconhecidos pelo valor
    ou pelo `id`/`valor` de cada item. `caminho`: onde a lista está (veja `_mesclar`)."""
    caminho = caminho or []
    antigos = {}
    for i, item in enumerate(atual):
        if (chave := _identidade(item)) is not None:
            antigos.setdefault(chave, (i, item))
    nova = CommentedSeq()
    if atual.fa.flow_style():
        nova.fa.set_flow_style()
    nova.ca.comment = atual.ca.comment
    nova.ca.end = atual.ca.end  # o comentário depois do último item, quando ele é escrito em fluxo
    posicao: dict[int, int] = {}  # índice antigo → índice novo, dos itens que ficam
    pendentes = []  # os itens que ficam e mudam por dentro: depois de a lista nova estar completa
    for j, item in enumerate(valor):
        chave = _identidade(item)
        if chave in antigos and antigos[chave][0] not in posicao:
            i, velho = antigos[chave]
            if isinstance(item, dict) and isinstance(velho, CommentedMap):
                pendentes.append((velho, item, j))
                item = velho
            nova.append(item)
            posicao[i] = j
            if i in atual.ca.items:
                nova.ca.items[j] = atual.ca.items[i]
        else:
            nova.append(_sem_vazios(item) if omitir_vazios else item)
    for velho, item, j in pendentes:
        _mesclar(velho, item, substituir=substituir, omitir_vazios=omitir_vazios, caminho=[*caminho, (nova, j)])
    # os comentários de um item tirado (ou trocado por outro) vão para antes do item seguinte que fica
    for i in range(len(atual)):
        if i in posicao or not (linhas := _comentarios_que_saem(atual, i)):
            continue
        seguinte = next((k for k in range(i + 1, len(atual)) if k in posicao), None)
        alvo = (nova, posicao[seguinte], _coluna(atual, seguinte)) if seguinte is not None else None
        _realocar(linhas, alvo, caminho)
    return nova


def _bloco(no: Any) -> bool:
    return isinstance(no, CommentedMap | CommentedSeq) and not no.fa.flow_style()


def _ultima(no: CommentedMap | CommentedSeq) -> Any:
    return list(no.keys())[-1] if isinstance(no, CommentedMap) else len(no) - 1


def _comentarios_que_saem(no: CommentedMap | CommentedSeq, chave: Any) -> list[tuple[str, int]]:
    """Os comentários de bloco que saem com a entrada `chave` de `no`, na ordem do arquivo: os de antes dela e os
    que vêm depois dela (o cabeçalho da seção seguinte, que o ruamel prende ao último valor da entrada, ou ao fim de
    uma lista em bloco). Cada linha vem com a coluna original; uma linha em branco é `("", 0)`. O comentário na
    própria linha do último valor fica de fora: ele é da entrada que sai."""
    linhas: list[tuple[str, int]] = []

    def de_tokens(tokens: Any) -> None:
        for t in tokens or []:
            texto = t.value.strip()
            linhas.append((texto, t.column) if texto.startswith("#") else ("", 0))

    slots = no.ca.items.get(chave)
    if slots and len(slots) > 1 and isinstance(slots[1], list):
        de_tokens(slots[1])
    # desce pelo último valor, enquanto ele for uma coleção em bloco
    finais = []  # os `end` das coleções no caminho, do mais fundo ao mais raso
    pai, k = no, chave
    valor = pai[k]
    while _bloco(valor) and len(valor):
        finais.insert(0, valor.ca.end)
        pai, k = valor, _ultima(valor)
        valor = pai[k]
    slot = (pai.ca.items.get(k) or [None, None, None])[0 if isinstance(pai, CommentedSeq) else 2 :][:1]
    token = slot[0] if slot else None
    if token is not None and "\n" in token.value:
        for linha in token.value.split("\n")[1:]:
            texto = linha.strip()
            if texto.startswith("#"):
                linhas.append((texto, len(linha) - len(linha.lstrip())))
            elif linha == "" and (not linhas or linhas[-1] != ("", 0)):
                linhas.append(("", 0))
    for fim in finais:
        de_tokens(fim)
    # sem as linhas em branco do fim, nem as de antes do primeiro comentário além de uma
    while linhas and linhas[-1] == ("", 0):
        linhas.pop()
    if not any(texto for texto, _ in linhas):
        return []
    primeiro = next(i for i, (texto, _) in enumerate(linhas) if texto)
    return linhas[max(0, primeiro - 1) :]


def _coluna(no: CommentedMap | CommentedSeq, chave: Any) -> int | None:
    """A coluna da entrada no arquivo lido (o traço, num item de lista), ou `None` para uma entrada nova."""
    try:
        if isinstance(no, CommentedMap):
            return no.lc.key(chave)[1]
        return no.lc.item(chave)[1] - 2
    except (KeyError, IndexError, TypeError, AttributeError):
        return None


def _antes(no: CommentedMap | CommentedSeq, chave: Any, linhas: list[tuple[str, int]], coluna: int | None) -> None:
    """Põe as linhas antes da entrada `chave` de `no`, na coluna dela (ou na original, para uma entrada nova)."""
    if coluna is None:
        coluna = min(c for texto, c in linhas if texto)
    anterior = None
    chaves = list(no.keys()) if isinstance(no, CommentedMap) else list(range(len(no)))
    if (i := chaves.index(chave)) > 0:
        anterior = chaves[i - 1]
    if linhas[0] == ("", 0) and (anterior is None or _termina_em_branco(no, anterior)):
        linhas = linhas[1:]  # sem a linha em branco logo depois da chave de cima, nem uma segunda
    tokens = [CommentToken(f"{texto}\n" if texto else "\n", CommentMark(coluna if texto else 0)) for texto, _ in linhas]
    slots = no.ca.items.setdefault(chave, [None, [], None, None] if isinstance(no, CommentedMap) else [None, []])
    while len(slots) < 2:
        slots.append(None)
    if not isinstance(slots[1], list):
        slots[1] = []
    slots[1][0:0] = tokens


def _termina_em_branco(no: CommentedMap | CommentedSeq, chave: Any) -> bool:
    """Se a entrada já termina numa linha em branco (que o ruamel guarda no último valor dela)."""
    pai, k = no, chave
    valor = pai[k]
    while _bloco(valor) and len(valor):
        pai, k = valor, _ultima(valor)
        valor = pai[k]
    slots = pai.ca.items.get(k) or []
    i = 0 if isinstance(pai, CommentedSeq) else 2
    token = slots[i] if len(slots) > i else None
    return token is not None and token.value.endswith("\n\n")


def _seguinte(no: Any, chave: Any) -> Any:
    """A entrada depois de `chave` em `no`, ou `None` (também numa coleção em fluxo, que não leva comentário)."""
    if not _bloco(no):
        return None
    if isinstance(no, CommentedMap):
        chaves = list(no.keys())
        i = chaves.index(chave)
        return chaves[i + 1] if i + 1 < len(chaves) else None
    return chave + 1 if chave + 1 < len(no) else None


def _realocar(
    linhas: list[tuple[str, int]], alvo: tuple[Any, Any, int | None] | None, caminho: list[tuple[Any, Any]]
) -> None:
    """Põe os comentários de uma entrada que saiu antes de `alvo` (a entrada seguinte, no mesmo nível); sem ela,
    antes da entrada seguinte de um nível acima, subindo pelo `caminho`; e, sem nenhuma, no fim do documento."""
    if alvo is not None and _bloco(alvo[0]):
        _antes(*alvo[:2], linhas, alvo[2])
        return
    for no, chave in reversed(caminho):
        if (seguinte := _seguinte(no, chave)) is not None:
            _antes(no, seguinte, linhas, _coluna(no, seguinte))
            return
    raiz = caminho[0][0] if caminho else (alvo[0] if alvo else None)
    if raiz is None:
        return
    if raiz.ca.comment is None:
        raiz.ca.comment = [None, []]  # sem ele, o ruamel não escreve o `end` (representer.represent_mapping)
    if raiz.ca.end is None:
        raiz.ca.end = []
    raiz.ca.end.extend(CommentToken(f"{texto}\n" if texto else "\n", CommentMark(0)) for texto, _ in linhas)


def _tirar(destino: CommentedMap, chave: Any, caminho: list[tuple[Any, Any]]) -> None:
    """Tira a entrada sem perder os comentários de bloco dela: o cabeçalho de uma seção, que o ruamel prende à
    entrada anterior, vai para antes da entrada seguinte (`_realocar`)."""
    linhas = _comentarios_que_saem(destino, chave)
    seguinte = _seguinte(destino, chave)
    coluna = _coluna(destino, seguinte) if seguinte is not None else None
    del destino[chave]
    if linhas:
        _realocar(linhas, (destino, seguinte, coluna) if seguinte is not None else None, caminho or [(destino, None)])


def _mesclar(
    destino: CommentedMap,
    parcial: dict[str, Any],
    *,
    substituir: bool,
    omitir_vazios: bool = False,
    caminho: list[tuple[Any, Any]] | None = None,
) -> None:
    """Põe os valores de `parcial` em `destino`, mantendo o que não mudou e os comentários. Com `substituir`,
    chaves ausentes de `parcial` saem; com `omitir_vazios`, as de valor vazio também (e não são criadas). `caminho`:
    as coleções e as chaves acima de `destino`, da raiz para baixo, para os comentários de uma entrada que sai."""
    caminho = caminho or []
    if substituir:
        for chave in [k for k in destino if k not in parcial]:
            _tirar(destino, chave, caminho)
    for chave, valor in parcial.items():
        atual = destino.get(chave)
        if omitir_vazios and _vazio(valor):
            if chave in destino:
                _tirar(destino, chave, caminho)
        elif isinstance(valor, dict) and isinstance(atual, CommentedMap):
            _mesclar(
                atual, valor, substituir=substituir, omitir_vazios=omitir_vazios, caminho=[*caminho, (destino, chave)]
            )
        elif isinstance(valor, list) and isinstance(atual, CommentedSeq):
            if _simples(atual) != valor:
                destino[chave] = _lista(
                    atual,
                    valor,
                    substituir=substituir,
                    omitir_vazios=omitir_vazios,
                    caminho=[*caminho, (destino, chave)],
                )
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
        # sem o "Value error, " que o Pydantic põe antes da mensagem de um validador
        problemas = "; ".join(
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg'].removeprefix('Value error, ')}" for err in e.errors()
        )
        raise ErroConfig(f"{caminho.name} ficaria inválido: {problemas}") from e
    saida = io.StringIO()
    y.dump(doc, saida)
    tmp = caminho.with_suffix(caminho.suffix + ".tmp")
    tmp.write_text(saida.getvalue(), encoding="utf-8")
    os.replace(tmp, caminho)
    return validado
