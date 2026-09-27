"""Trocar o conteúdo de uma pasta gerada (`saida/dados`, o site publicado) sem trocar a pasta.

As etapas escrevem a versão nova numa pasta temporária e só então a põem no lugar. A primeira versão fazia isso
renomeando a pasta inteira (a velha saía, a nova entrava com o mesmo nome). Numa pasta sincronizada, como a Mesa ou
os Documentos no iCloud Drive do macOS, isso dá errado: o serviço vê uma pasta nova com o nome de uma que ainda está
sincronizando e, mais tarde, a renomeia para "dados 2", "dados 3"... e o projeto fica sem `dados`.

Aqui a pasta de destino continua a mesma: cada arquivo novo entra por `os.replace` (o mesmo jeito atômico dos
editores de texto ao salvar), e o que sobrou da versão anterior é apagado. A troca de cada arquivo é atômica, a da
pasta não: uma interrupção no meio deixa arquivos novos e velhos misturados, e rodar a etapa de novo conserta. Para
o painel perceber o mínimo, o manifesto e o `index.html` entram por último.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

POR_ULTIMO = ("manifesto.json", "index.html")


def _preparar_pasta(pasta: Path, raiz: Path) -> None:
    """Garante que `pasta` (dentro de `raiz`) seja uma pasta de verdade: um arquivo ou um link simbólico no caminho
    sai do lugar."""
    for parte in reversed([pasta, *pasta.parents]):
        if parte == raiz or raiz not in parte.parents:
            continue
        if parte.is_symlink() or parte.is_file():
            parte.unlink()
        parte.mkdir(exist_ok=True)


def substituir_conteudo(novo: Path, destino: Path) -> None:
    """Põe em `destino` os arquivos de `novo`, um a um, apaga de `destino` o que não está em `novo` e remove `novo`.
    As duas pastas precisam estar no mesmo disco (as etapas criam `novo` ao lado de `destino`)."""
    novo_r, destino_r = novo.resolve(), destino.resolve()
    if not novo.is_dir():
        raise ValueError(f"{novo} não é uma pasta.")
    if novo_r == destino_r or novo_r in destino_r.parents or destino_r in novo_r.parents:
        raise ValueError(f"{novo} e {destino} não podem ser a mesma pasta nem uma dentro da outra.")
    if destino.is_symlink() or destino.is_file():
        destino.unlink()
    destino.mkdir(parents=True, exist_ok=True)

    arquivos = sorted(
        (Path(pasta, nome).relative_to(novo) for pasta, _, nomes in os.walk(novo) for nome in nomes),
        key=lambda r: (r.name in POR_ULTIMO, str(r)),
    )
    colocados: set[tuple[int, int]] = set()
    for relativo in arquivos:
        alvo = destino / relativo
        _preparar_pasta(alvo.parent, destino)
        if alvo.is_symlink():
            alvo.unlink()
        elif alvo.is_dir():  # um arquivo no lugar de uma pasta antiga
            shutil.rmtree(alvo)
        os.replace(novo / relativo, alvo)
        info = alvo.stat()
        colocados.add((info.st_dev, info.st_ino))

    # a limpeza não segue links simbólicos: um link para uma pasta de fora sai, e o que está lá fica
    for pasta, pastas, nomes in os.walk(destino, topdown=False):
        for nome in nomes:
            p = Path(pasta) / nome
            if p.is_symlink():
                p.unlink()  # a versão nova não tem links
                continue
            info = p.stat()
            # o inode, e não o nome: num disco que não diferencia maiúsculas, "Chunk.js" e "chunk.js" são o mesmo
            if (info.st_dev, info.st_ino) not in colocados:
                p.unlink()
        for nome in pastas:
            p = Path(pasta) / nome
            if p.is_symlink():
                p.unlink()
            elif not any(p.iterdir()):
                p.rmdir()
    shutil.rmtree(novo, ignore_errors=True)
