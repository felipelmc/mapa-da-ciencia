"""Interface de linha de comando `mapa`.

Cada etapa do pipeline é um subcomando (`mapa novo`, `mapa coletar`, `mapa topicos`...).
Os comandos só orquestram: a lógica fica nos módulos do pacote, que também são usados
pelo servidor do painel e pela API Python para notebooks.
"""

from __future__ import annotations

import typer

from mapa_da_ciencia import __version__

app = typer.Typer(
    name="mapa",
    help="Observatório da literatura científica: coleta artigos, mapeia tópicos no tempo, "
    "classifica resumos com um codebook e mostra a geografia da produção, com modelos locais.",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _mostrar_versao(valor: bool) -> None:
    if valor:
        typer.echo(f"mapa-da-ciencia {__version__}")
        raise typer.Exit()


@app.callback()
def principal(
    versao: bool = typer.Option(
        False,
        "--versao",
        "-V",
        callback=_mostrar_versao,
        is_eager=True,
        help="Mostra a versão instalada e sai.",
    ),
) -> None:
    """Observatório da literatura científica."""
