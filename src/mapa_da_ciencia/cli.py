"""Interface de linha de comando `mapa`.

Cada etapa do pipeline é um subcomando (`mapa novo`, `mapa coletar`, `mapa topicos`...).
Os comandos só orquestram: a lógica fica nos módulos do pacote, que também são usados
pelo servidor do painel e pela API Python para notebooks.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from mapa_da_ciencia import __version__
from mapa_da_ciencia.config import ErroConfig
from mapa_da_ciencia.llm.perfis import PERFIS, ram_total_gb, sugerir_perfil
from mapa_da_ciencia.manifesto import status_das_etapas
from mapa_da_ciencia.projeto import MODELOS_DE_PROJETO, Projeto

app = typer.Typer(
    name="mapa",
    help="Observatório da literatura científica: coleta artigos, mapeia tópicos no tempo, "
    "classifica resumos com um codebook e mostra a geografia da produção, com modelos locais.",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]},
)
console = Console()

OpcaoProjeto = Annotated[
    Path,
    typer.Option("--projeto", "-P", help="Pasta do projeto (padrão: a pasta atual ou uma acima dela)."),
]


@contextmanager
def _erros_amigaveis() -> Iterator[None]:
    """Mostra erros de configuração como mensagem, sem traceback, e sai com código 1."""
    try:
        yield
    except ErroConfig as e:
        console.print(f"[bold red]Erro:[/] {e}")
        raise typer.Exit(1) from e


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


@app.command()
def novo(
    pasta: Annotated[Path, typer.Argument(help="Pasta onde o projeto será criado.")],
    modelo: Annotated[
        str, typer.Option("--modelo", "-m", help=f"Modelo de projeto: {', '.join(MODELOS_DE_PROJETO)}.")
    ] = "ciencia-politica",
    perfil: Annotated[
        str | None,
        typer.Option(
            "--perfil",
            "-p",
            help=f"Perfil de modelos locais: {', '.join(PERFIS)}. Padrão: sugerido pela memória da máquina.",
        ),
    ] = None,
) -> None:
    """Cria um projeto novo, com [bold]mapa.yaml[/] e [bold]codebook.yaml[/] prontos para editar."""
    with _erros_amigaveis():
        if perfil is not None and perfil not in PERFIS:
            raise ErroConfig(f"Perfil desconhecido: {perfil}. Opções: {', '.join(PERFIS)}.")
        escolhido = PERFIS[perfil] if perfil else sugerir_perfil()  # type: ignore[index]
        projeto = Projeto.criar(pasta, modelo=modelo, perfil=escolhido)

    origem = "escolhido por você" if perfil else f"sugerido para {ram_total_gb():.0f} GB de memória"
    console.print(f"[bold green]Projeto criado[/] em {projeto.raiz}")
    console.print(f"Perfil de modelos: [bold]{escolhido.nome}[/] ({origem}).")
    console.print(
        "\nPróximos passos:\n"
        f"  1. Revise [bold]{projeto.raiz.name}/mapa.yaml[/] (revistas, anos) e "
        f"[bold]{projeto.raiz.name}/codebook.yaml[/].\n"
        "  2. Rode [bold]mapa diagnostico[/] para conferir o Ollama e os modelos.\n"
        "  3. Rode [bold]mapa coletar[/] dentro da pasta do projeto."
    )


@app.command()
def status(projeto: OpcaoProjeto = Path(".")) -> None:
    """Mostra o recorte do projeto e em que ponto está cada etapa do pipeline."""
    with _erros_amigaveis():
        p = Projeto.abrir(projeto)
        cfg = p.config
    console.print(f"[bold]{cfg.titulo}[/]  ({cfg.nome})  —  {p.raiz}")
    if cfg.fontes.scielo:
        console.print(f"SciELO ({cfg.fontes.scielo.colecao}): {len(cfg.fontes.scielo.revistas)} revista(s)")
    console.print(f"Anos: {cfg.recorte.anos[0]}–{cfg.recorte.anos[1]}")
    m = cfg.modelos
    console.print(
        f"Modelos: embeddings [bold]{m.embeddings.modelo}[/], classificação [bold]{m.classificacao.modelo}[/], "
        f"rótulos [bold]{m.rotulos.modelo}[/]"
    )

    tabela = Table("Etapa", "Estado", "Última execução", "Duração", "Contagens")
    for etapa, manifesto in status_das_etapas(p).items():
        if manifesto is None:
            tabela.add_row(etapa, "[dim]pendente[/]", "", "", "")
            continue
        quando = datetime.fromisoformat(manifesto["fim"]).astimezone().strftime("%d/%m/%Y %H:%M")
        contagens = ", ".join(f"{k}={v}" for k, v in manifesto["contagens"].items())
        tabela.add_row(etapa, "[green]concluída[/]", quando, f"{manifesto['duracao_s']:.0f} s", contagens)
    console.print(tabela)
