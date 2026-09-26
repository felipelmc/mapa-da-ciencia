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
from mapa_da_ciencia.diagnostico import DICAS_OLLAMA, diagnosticar
from mapa_da_ciencia.llm.perfis import PERFIS, ram_total_gb, sugerir_perfil
from mapa_da_ciencia.manifesto import status_das_etapas
from mapa_da_ciencia.projeto import MODELOS_DE_PROJETO, Projeto, ProjetoNaoEncontrado

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


@app.command()
def diagnostico(
    projeto: OpcaoProjeto = Path("."),
    sem_rede: Annotated[
        bool, typer.Option("--sem-rede", help="Não testa a conexão com ArticleMeta e OpenAlex.")
    ] = False,
) -> None:
    """Confere memória, disco, o Ollama, os modelos do projeto e a conexão com as fontes."""
    with _erros_amigaveis():
        try:
            p: Projeto | None = Projeto.abrir(projeto)
        except ProjetoNaoEncontrado:
            p = None
        checagens = diagnosticar(p, checar_rede=not sem_rede)

    simbolo = {"ok": "[green]✓[/]", "aviso": "[yellow]![/]", "erro": "[red]✗[/]"}
    grupo_atual = None
    for c in checagens:
        if c.grupo != grupo_atual:
            grupo_atual = c.grupo
            console.print(f"\n[bold]{c.grupo}[/]")
        console.print(f"  {simbolo[c.estado]} {c.item}: {c.detalhe}")
        if c.dica:
            console.print(f"      [dim]{c.dica}[/]")
    console.print(f"\n[dim]{DICAS_OLLAMA}[/]")
    erros = sum(c.estado == "erro" for c in checagens)
    if erros:
        console.print(f"\n[bold red]{erros} problema(s) impedem rodar o pipeline.[/]")
        raise typer.Exit(1)
    console.print("\n[bold green]Tudo pronto.[/]")


def _porta_livre(porta: int) -> bool:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", porta)) != 0


@app.command()
def painel(
    projeto: OpcaoProjeto = Path("."),
    exemplo: Annotated[
        bool, typer.Option("--exemplo", help="Mostra o exemplo sintético, sem precisar de um projeto.")
    ] = False,
    porta: Annotated[int, typer.Option("--porta", help="Porta local do servidor.")] = 8765,
    abrir: Annotated[bool, typer.Option("--abrir/--nao-abrir", help="Abre o navegador automaticamente.")] = True,
) -> None:
    """Abre o painel no navegador: a interface do projeto, servida só nesta máquina."""
    import tempfile
    import threading
    import webbrowser

    import uvicorn

    from mapa_da_ciencia.contrato.exemplo import gerar_exemplo
    from mapa_da_ciencia.contrato.exportar import escrever_dados
    from mapa_da_ciencia.servidor.app import criar_app

    if not _porta_livre(porta):
        console.print(f"[bold red]Erro:[/] a porta {porta} já está em uso. Use outra, por exemplo --porta {porta + 1}.")
        raise typer.Exit(1)
    temporario = None
    with _erros_amigaveis():
        if exemplo:
            temporario = tempfile.TemporaryDirectory(prefix="mapa-exemplo-")
            pasta = Path(temporario.name)
            escrever_dados(pasta, *gerar_exemplo())
            aplicacao = criar_app(pasta_dados=pasta, api=False)
            descricao = "exemplo sintético (dados fictícios)"
        else:
            p = Projeto.abrir(projeto)
            aplicacao = criar_app(pasta_dados=p.saida / "dados", projeto=p, api=True)
            descricao = f"projeto {p.config.nome}"

    url = f"http://127.0.0.1:{porta}/"
    console.print(f"Painel do {descricao} em [bold]{url}[/]  (Ctrl+C para encerrar)")
    if abrir:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    try:
        uvicorn.run(aplicacao, host="127.0.0.1", port=porta, log_level="warning")
    finally:
        if temporario is not None:
            temporario.cleanup()


@app.command()
def revistas(
    busca: Annotated[str, typer.Argument(help="Parte do título, acrônimo, categoria ou ISSN.")] = "",
    area: Annotated[str, typer.Option("--area", "-a", help="Filtra pela grande área (ex.: humanas, saúde).")] = "",
    yaml: Annotated[
        bool, typer.Option("--yaml", help="Imprime as linhas prontas para colar em `fontes.scielo.revistas`.")
    ] = False,
) -> None:
    """Lista as revistas do SciELO Brasil, para escolher o recorte de um projeto."""
    from mapa_da_ciencia.fontes.revistas import buscar, retrato

    achadas = buscar(busca, area)
    if yaml:
        for r in achadas:
            typer.echo(f"      - {r.issn}           # {r.titulo}")
        return
    tabela = Table("Acrônimo", "ISSN", "Título", "Área", "Licença")
    for r in achadas:
        tabela.add_row(r.acronimo, r.issn, r.titulo, ", ".join(r.areas), r.licenca or "")
    console.print(tabela)
    console.print(
        f"[dim]{len(achadas)} revista(s). Retrato de {retrato().gerado_em}, só com revistas correntes do "
        "SciELO Brasil. Use --yaml para copiar os ISSNs para o mapa.yaml.[/]"
    )
