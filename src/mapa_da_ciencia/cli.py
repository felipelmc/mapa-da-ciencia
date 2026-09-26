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
from rich.columns import Columns
from rich.console import Console
from rich.table import Table

from mapa_da_ciencia import __version__
from mapa_da_ciencia.armazenamento import ARQUIVO as ARQUIVO_DOCUMENTOS
from mapa_da_ciencia.armazenamento import cobertura
from mapa_da_ciencia.coleta import interpretar_anos
from mapa_da_ciencia.config import ErroConfig
from mapa_da_ciencia.diagnostico import DICAS_OLLAMA, diagnosticar
from mapa_da_ciencia.fontes.base import ErroFonte
from mapa_da_ciencia.formatar import num, periodo
from mapa_da_ciencia.llm.base import ErroProvedor
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
    """Mostra erros de configuração, de fonte e de modelo como mensagem, sem traceback, e sai com código 1."""
    try:
        yield
    except (ErroConfig, ErroFonte, ErroProvedor) as e:
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
    revista: Annotated[
        list[str] | None,
        typer.Option("--revista", "-r", help="ISSN ou acrônimo de uma revista do recorte (repita para várias)."),
    ] = None,
    anos: Annotated[str | None, typer.Option("--anos", help="Período do recorte: 2024 ou 2010-2025.")] = None,
) -> None:
    """Cria um projeto novo, com [bold]mapa.yaml[/] e [bold]codebook.yaml[/] prontos para editar."""
    with _erros_amigaveis():
        if perfil is not None and perfil not in PERFIS:
            raise ErroConfig(f"Perfil desconhecido: {perfil}. Opções: {', '.join(PERFIS)}.")
        escolhido = PERFIS[perfil] if perfil else sugerir_perfil()  # type: ignore[index]
        recorte_anos = interpretar_anos(anos) if anos else None
        projeto = Projeto.criar(pasta, modelo=modelo, perfil=escolhido, revistas=revista, anos=recorte_anos)

    origem = "escolhido por você" if perfil else f"sugerido para {ram_total_gb():.0f} GB de memória"
    console.print(f"[bold green]Projeto criado[/] em {projeto.raiz}")
    console.print(f"Perfil de modelos: [bold]{escolhido.nome}[/] ({origem}).")
    console.print(
        "\nPróximos passos:\n"
        f"  1. Revise [bold]{pasta / 'mapa.yaml'}[/] (revistas, anos) e [bold]{pasta / 'codebook.yaml'}[/].\n"
        f"  2. Entre na pasta: [bold]cd {pasta}[/]\n"
        "  3. Rode [bold]mapa diagnostico[/] para conferir o Ollama e os modelos.\n"
        "  4. Rode [bold]mapa coletar[/]."
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
    console.print(f"Anos: {periodo(cfg.recorte.anos)}")
    m = cfg.modelos
    console.print(
        f"Modelos: embeddings [bold]{m.embeddings.modelo}[/], classificação [bold]{m.classificacao.modelo}[/], "
        f"rótulos [bold]{m.rotulos.modelo}[/]"
    )

    tabela = Table("Etapa", "Estado", "Última execução", "Duração", "Resultado")
    etapas = status_das_etapas(p)
    for etapa, manifesto in etapas.items():
        if manifesto is None:
            tabela.add_row(etapa, "[dim]pendente[/]", "", "", "")
            continue
        quando = datetime.fromisoformat(manifesto["fim"]).astimezone().strftime("%d/%m/%Y %H:%M")
        # a primeira contagem é a principal da etapa; as demais aparecem nos detalhes de cada uma
        principal = next(iter(manifesto["contagens"].items()), None)
        resultado = f"{num(principal[1], 0)} {principal[0]}" if principal else ""
        tabela.add_row(etapa, "[green]concluída[/]", quando, f"{num(manifesto['duracao_s'], 0)} s", resultado)
    console.print(tabela)
    _mostrar_corpus(p, etapas.get("coleta"))


_ROTULOS = {
    "casamento": {
        "1_doi": "DOI",
        "2_pid_url": "PID no link",
        "3_doi_derivado": "DOI derivado do PID",
        "4_titulo_ano": "título e ano",
        "sem_casamento": "sem casamento",
        "nao_tentado": "não tentado",
    },
    "afiliacoes_fonte": {
        "v240": "normalizada (v240)",
        "v70": "só texto livre (v70)",
        "openalex": "do OpenAlex",
        "nenhuma": "nenhuma",
    },
    "licenca_fonte": {
        "openalex": "OpenAlex",
        "revista": "revista",
        "ambas": "OpenAlex e revista concordam",
        "nenhuma": "nenhuma",
    },
}


def _tabela_contagem(titulo: str, contagem: dict, total: int, rotulos: dict | None = None) -> Table:
    tabela = Table(title=titulo, title_justify="left", show_edge=False, pad_edge=False, min_width=len(titulo))
    tabela.add_column("")
    tabela.add_column("n", justify="right")
    tabela.add_column("%", justify="right", style="dim")
    for chave, n in contagem.items():
        rotulo = (rotulos or {}).get(chave, chave) if chave is not None else "(sem revista)"
        tabela.add_row(str(rotulo), num(n, 0), num(100 * n / total if total else 0, 0))
    return tabela


def _mostrar_corpus(p: Projeto, coleta: dict | None) -> None:
    """Cobertura do corpus coletado (`dados/documentos.parquet`), se já houver coleta."""
    caminho = p.dados / ARQUIVO_DOCUMENTOS
    if not caminho.exists():
        console.print("\n[dim]Corpus: nenhum documento coletado ainda. Rode `mapa coletar`.[/]")
        return
    cob = cobertura(caminho)
    total = cob["documentos"]
    anos = f", {periodo(cob['anos'])}" if total else ""
    console.print(f"\n[bold]Corpus[/]: {num(total, 0)} documento(s){anos}")
    if coleta:
        c = coleta["contagens"]
        console.print(
            f"[dim]Última coleta: ficaram de fora {num(c.get('fora_do_periodo', 0), 0)} fora do período, "
            f"{num(c.get('excluidos_por_tipo', 0), 0)} por tipo e {num(c.get('nao_encontrados', 0), 0)} não "
            f"encontrado(s); {num(c.get('fundidos', 0), 0)} duplicata(s) fundida(s). "
            f"{num(c.get('requisicoes', 0), 0)} requisição(ões), {num(c.get('do_cache', 0), 0)} do cache, "
            f"{num(c.get('creditos_openalex', 0), 0)} crédito(s) do OpenAlex.[/]"
        )
    if not total:
        return
    geral = {
        "com resumo": cob["com_resumo"],
        "com DOI": cob["com_doi"],
        "com afiliação": cob["com_afiliacao"],
        "possível duplicata": cob["possiveis_duplicatas"],
    }
    console.print(
        Columns(
            [
                _tabela_contagem("Por revista", cob["por_revista"], total),
                _tabela_contagem("Por tipo", cob["por_tipo"], total),
                _tabela_contagem("Cobertura", geral, total),
                _tabela_contagem("Resumo por idioma", cob["resumo_por_idioma"], total),
                _tabela_contagem("Afiliações", cob["afiliacoes_fonte"], total, _ROTULOS["afiliacoes_fonte"]),
                _tabela_contagem("Casamento com o OpenAlex", cob["casamento"], total, _ROTULOS["casamento"]),
                _tabela_contagem("Licença", cob["licencas"], total),
                _tabela_contagem("Licença decidida por", cob["licenca_fonte"], total, _ROTULOS["licenca_fonte"]),
            ],
            padding=(1, 4),
        )
    )


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


@app.command()
def coletar(
    projeto: OpcaoProjeto = Path("."),
    revista: Annotated[
        list[str] | None,
        typer.Option("--revista", "-r", help="Coleta só esta revista (ISSN ou acrônimo); repita para várias."),
    ] = None,
    anos: Annotated[str | None, typer.Option("--anos", help="Coleta só este período: 2024 ou 2010-2025.")] = None,
    limite: Annotated[
        int | None, typer.Option("--limite", help="Coleta só os N primeiros artigos (para testar).")
    ] = None,
    atualizar: Annotated[
        bool, typer.Option("--atualizar", help="Baixa de novo as listas de artigos (para pegar publicações novas).")
    ] = False,
    offline: Annotated[
        bool, typer.Option("--offline", help="Não acessa a internet: usa só o que está em brutos/.")
    ] = False,
    sem_openalex: Annotated[
        bool, typer.Option("--sem-openalex", help="Não enriquece com o OpenAlex (citações, licença por artigo).")
    ] = False,
    consulta: Annotated[
        str | None,
        typer.Option("--consulta", help="Só os artigos cujo título ou resumo respondem a esta busca (via OpenAlex)."),
    ] = None,
) -> None:
    """Coleta os artigos do recorte e monta o corpus do projeto (dados/documentos.parquet)."""
    from mapa_da_ciencia import coleta as etapa
    from mapa_da_ciencia.fontes.base import limpar_temporarios
    from mapa_da_ciencia.progresso import ProgressoRich

    with _erros_amigaveis():
        p = Projeto.abrir(projeto)
        opcoes = etapa.OpcoesColeta(
            revistas=revista or None,
            anos=etapa.interpretar_anos(anos) if anos else None,
            limite=limite,
            atualizar=atualizar,
            offline=offline,
            sem_openalex=sem_openalex,
            consulta=consulta,
        )
        progresso = ProgressoRich(console)
        try:
            resumo = etapa.coletar(p, opcoes, progresso)
        except KeyboardInterrupt:
            progresso.fim()
            limpar_temporarios(p.brutos)
            guardados = len(list((p.brutos / "articlemeta" / "artigos").glob("*.json.gz")))
            console.print(
                f"\n[yellow]Coleta interrompida.[/] {num(guardados, 0)} registro(s) já estão guardados em brutos/. "
                "Rode [bold]mapa coletar[/] de novo para continuar de onde parou."
            )
            raise typer.Exit(130) from None

    plano = resumo.plano
    console.print(
        f"\n[bold green]Coleta concluída[/] em {num(resumo.duracao_s)} s: [bold]{num(resumo.documentos, 0)}[/] "
        f"documento(s) de {len(plano.revistas)} revista(s), {periodo(plano.anos)}."
    )
    if resumo.por_revista:
        tabela = Table("Revista", "Documentos")
        for acronimo, n in resumo.por_revista.items():
            tabela.add_row(acronimo, num(n, 0))
        console.print(tabela)
    fora = [f"fora do período: {num(resumo.fora_do_periodo, 0)}"]
    fora += [f"{tipo}: {num(n, 0)}" for tipo, n in resumo.excluidos_por_tipo.items()]
    if resumo.nao_encontrados:
        fora.append(f"não encontrados na API: {num(resumo.nao_encontrados, 0)}")
    console.print("[dim]Ficaram de fora — " + "; ".join(fora) + ".[/]")
    req = resumo.requisicoes.get("articlemeta", 0)
    cache = resumo.do_cache.get("articlemeta", 0)
    console.print(f"[dim]ArticleMeta: {num(req, 0)} requisição(ões), {num(cache, 0)} resposta(s) do cache.[/]")
    casados = sum(v for k, v in resumo.casamento.items() if k[0].isdigit())
    if set(resumo.casamento) != {"nao_tentado"}:
        console.print(
            f"[dim]OpenAlex: {num(casados, 0)} de {num(resumo.documentos, 0)} casados; "
            f"{num(resumo.requisicoes.get('openalex', 0), 0)} requisição(ões), "
            f"{num(resumo.creditos_openalex, 0)} crédito(s).[/]"
        )
    if resumo.fundidos:
        console.print(f"[dim]Duplicatas fundidas (mesmo artigo registrado duas vezes): {num(resumo.fundidos, 0)}.[/]")
    for doc, original in resumo.possiveis_duplicatas:
        console.print(f"[yellow]Possível duplicata:[/] {doc} parece repetir {original} (mesmo título, ano e 1º autor).")
    for aviso in resumo.avisos:
        console.print(f"[yellow]Aviso:[/] {aviso}")
    console.print("Próximo passo: [bold]mapa status[/] para ver a cobertura do corpus.")


@app.command()
def importar(
    arquivos: Annotated[
        list[Path], typer.Argument(help="Arquivos RIS, CSV ou BibTeX do search.scielo.org, ou listas de DOIs (.txt).")
    ],
    projeto: OpcaoProjeto = Path("."),
    nao_coletar: Annotated[
        bool, typer.Option("--nao-coletar", help="Só copia os arquivos para importados/, sem rodar a coleta.")
    ] = False,
    sem_openalex: Annotated[bool, typer.Option("--sem-openalex", help="Não usa o OpenAlex na coleta.")] = False,
) -> None:
    """Acrescenta ao projeto artigos de uma busca exportada do search.scielo.org (ou de uma lista de DOIs)."""
    from mapa_da_ciencia.coleta import PASTA_IMPORTADOS, guardar_importacao

    with _erros_amigaveis():
        p = Projeto.abrir(projeto)
        for arquivo in arquivos:
            leitura = guardar_importacao(p, arquivo)
            console.print(f"[green]✓[/] {leitura.resumo()}")
            for ignorado in leitura.ignorados[:5]:
                console.print(f"    [dim]ignorado — {ignorado}[/]")
    console.print(f"Arquivo(s) guardado(s) em {PASTA_IMPORTADOS}/; eles entram em toda coleta deste projeto.")
    if not nao_coletar:
        coletar(projeto=p.raiz, sem_openalex=sem_openalex)
