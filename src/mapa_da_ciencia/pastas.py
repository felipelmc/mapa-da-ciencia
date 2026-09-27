"""Trocar o conteúdo de uma pasta gerada (`saida/dados`, o site publicado) sem trocar a pasta.

As etapas escrevem a versão nova numa pasta temporária e só então a põem no lugar, para o painel nunca ler uma
exportação pela metade. A primeira versão fazia isso renomeando a pasta inteira (a velha saía, a nova entrava com o
mesmo nome). Numa pasta sincronizada, como a Mesa ou os Documentos no iCloud Drive do macOS, isso dá errado: o
serviço vê uma pasta nova com o nome de uma que ainda está sincronizando e, mais tarde, a renomeia para "dados 2",
"dados 3"... e o projeto fica sem `dados`. Aqui a pasta de destino continua a mesma: cada arquivo novo entra por
`os.replace` (o mesmo jeito atômico dos editores de texto ao salvar), e o que sobrou da versão anterior é apagado.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def substituir_conteudo(novo: Path, destino: Path) -> None:
    """Põe em `destino` os arquivos de `novo`, um a um, apaga de `destino` o que não está em `novo` e remove `novo`.
    As duas pastas precisam estar no mesmo disco (as etapas criam `novo` ao lado de `destino`)."""
    destino.mkdir(parents=True, exist_ok=True)
    arquivos = sorted(p.relative_to(novo) for p in novo.rglob("*") if p.is_file())
    for relativo in arquivos:
        alvo = destino / relativo
        if alvo.is_dir():  # um arquivo no lugar de uma pasta antiga
            shutil.rmtree(alvo)
        alvo.parent.mkdir(parents=True, exist_ok=True)
        os.replace(novo / relativo, alvo)
    manter = set(arquivos)
    for p in sorted(destino.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        relativo = p.relative_to(destino)
        if p.is_file() or p.is_symlink():
            if relativo not in manter:
                p.unlink()
        elif p.is_dir() and not any(p.iterdir()):
            p.rmdir()
    shutil.rmtree(novo, ignore_errors=True)
