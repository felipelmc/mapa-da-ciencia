"""Interface de linha de comando `mapa`.

Cada etapa do pipeline é um subcomando (`mapa novo`, `mapa coletar`, `mapa topicos`...).
Os comandos só orquestram: a lógica fica nos módulos do pacote, que também são usados
pelo servidor do painel e pela API Python para notebooks.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.columns import Columns
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from mapa_da_ciencia import __version__
from mapa_da_ciencia.armazenamento import ARQUIVO as ARQUIVO_DOCUMENTOS
from mapa_da_ciencia.armazenamento import cobertura
from mapa_da_ciencia.cli_portugues import GrupoEmPortugues
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
    cls=GrupoEmPortugues,  # ajuda e erros de uso em português
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
        console.print(f"[bold red]Erro:[/] {escape(str(e))}")
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

    from mapa_da_ciencia.manifesto import estados_das_etapas

    tabela = Table("Etapa", "Estado", "Última execução", "Duração", "Resultado")
    etapas = status_das_etapas(p)
    estados = estados_das_etapas(p)  # o mesmo cálculo da linha de metrô do painel
    rotulos = {
        "pendente": "[dim]pendente[/]",
        "em_dia": "[green]em dia[/]",
        "incompleta": "[yellow]incompleta[/]",
        "desatualizada": "[yellow]desatualizada[/]",
    }
    for etapa, manifesto in etapas.items():
        estado = estados[etapa]["estado"] if etapa in estados else ("em_dia" if manifesto else "pendente")
        amostra = estados.get(etapa, {}).get("amostra")
        if manifesto is None:
            resultado = f"{num(amostra['codificados'], 0)} de {num(amostra['n'], 0)} codificados" if amostra else ""
            tabela.add_row(etapa, rotulos[estado], "", "", resultado)
            continue
        quando = datetime.fromisoformat(manifesto["fim"]).astimezone().strftime("%d/%m/%Y %H:%M")
        # a primeira contagem é a principal da etapa; as demais aparecem nos detalhes de cada uma
        principal = next(iter(manifesto["contagens"].items()), None)
        resultado = f"{num(principal[1], 0)} {principal[0]}" if principal else ""
        tabela.add_row(etapa, rotulos[estado], quando, f"{num(manifesto['duracao_s'], 0)} s", resultado)
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


def _mostrar_topicos(p: Projeto) -> None:
    from mapa_da_ciencia.armazenamento import ler_documentos
    from mapa_da_ciencia.topicos.resultado import PASTA, Resultado, assinatura_corpus, ler_atribuicoes

    resultado = Resultado.ler(p.dados / PASTA)
    if resultado is None:
        console.print("[dim]Tópicos: ainda não gerados. Rode `mapa topicos`.[/]")
        return
    atrib = ler_atribuicoes(p.dados / PASTA)
    n = len(atrib)
    sem = sum(a["topico"] == -1 for a in atrib)
    reatrib = sum(a["atribuicao"] == "vizinho" and a["topico"] >= 0 for a in atrib)
    fontes = {t.rotulo_fonte for t in resultado.topicos}
    ari = num(resultado.estabilidade_ari, 2) if resultado.estabilidade_ari is not None else "—"
    console.print(
        f"[bold]Tópicos[/]: {num(len(resultado.topicos), 0)} em {num(len(resultado.macrotemas), 0)} macrotemas "
        f"(ARI {ari}); núcleo {num(100 * (n - sem - reatrib) / n, 0)}%, reatribuídos {num(100 * reatrib / n, 0)}%, "
        f"sem tópico {num(100 * sem / n, 0)}%; rótulos: {', '.join(sorted(fontes))}."
    )
    ids = [d.id for d in ler_documentos(p.dados / ARQUIVO_DOCUMENTOS)]
    if resultado.assinatura != assinatura_corpus(ids):
        console.print(
            "[yellow]Os tópicos são de antes da última coleta.[/] Rode [bold]mapa topicos[/] para atualizá-los."
        )


def _mostrar_classificacao_status(p: Projeto) -> None:
    from mapa_da_ciencia.classificacao.pipeline import classificacao_em_dia
    from mapa_da_ciencia.classificacao.resultado import PASTA, Resultado, rotulo_a_parte

    cfg = p.config.modelos.classificacao
    r = Resultado.ler(p.dados / PASTA, cfg.modelo, p.codebook.hash())
    em_dia = classificacao_em_dia(p)
    if r is None:
        if em_dia is False:
            console.print(
                "[yellow]A classificação é de outro codebook ou de outro modelo.[/] Rode [bold]mapa classificar[/]."
            )
        else:
            console.print("[dim]Classificação: ainda não feita. Rode `mapa classificar --estimar`.[/]")
        return
    literal = r.evidencia.get("literal")
    console.print(
        f"[bold]Classificação[/]: {num(r.classificados, 0)} de {num(r.documentos, 0)} documentos com resumo "
        f"({r.modelo.split('@', 1)[0]}, codebook {r.codebook})"
        + (f"; evidência literal em {num(100 * literal, 0)}%" if literal is not None else "")
        + "."
    )
    so_falhas = bool(r.falhas) and r.classificados + len(r.falhas) >= r.documentos  # nada mais ficou de fora
    if em_dia is False and not (so_falhas and _mesmo_corpus(p, r.assinatura)):
        console.print(
            "[yellow]A classificação está incompleta ou é de antes da última coleta.[/] Rode "
            "[bold]mapa classificar[/] para completá-la."
        )
    if r.falhas:
        console.print(
            f"[yellow]{num(len(r.falhas), 0)} documento(s) sem resposta válida nas duas tentativas[/] (por exemplo "
            f"{', '.join(r.falhas[:3])}). Com temperatura 0 e semente fixa, a falha tende a se repetir: veja "
            "“Documentos que falham sempre” no guia Classificar os resumos."
        )
    a_parte = Resultado.ler(p.dados / PASTA, cfg.modelo, p.codebook.hash(), a_parte=True)
    if a_parte is not None:
        o_que = (
            "Uma rodada parcial da mesma versão"
            if rotulo_a_parte(a_parte, r) == "rodada parcial"
            else "Uma versão nova"
        )
        console.print(
            f"[yellow]{o_que} ({a_parte.modelo}) está à parte e não entrou nesta[/]: "
            f"{num(a_parte.classificados, 0)} de {num(a_parte.documentos, 0)} documentos, "
            f"{num(len(a_parte.falhas), 0)} sem resposta válida. `mapa validar metricas` compara as duas na amostra."
        )


def _mesmo_corpus(p: Projeto, assinatura: str) -> bool:
    from mapa_da_ciencia.armazenamento import ler_documentos
    from mapa_da_ciencia.topicos.resultado import assinatura_corpus

    return assinatura == assinatura_corpus([d.id for d in ler_documentos(p.dados / ARQUIVO_DOCUMENTOS)])


def _mostrar_geografia(p: Projeto) -> None:
    from mapa_da_ciencia.geografia.pipeline import geografia_em_dia
    from mapa_da_ciencia.geografia.resultado import PASTA, Resultado

    resultado = Resultado.ler(p.dados / PASTA)
    if resultado is None:
        console.print("[dim]Geografia: ainda não gerada. Rode `mapa geografia`.[/]")
        return
    c, cob = resultado.contagens, resultado.cobertura
    ligados = sum(c["identificados"].values())
    console.print(
        f"[bold]Geografia[/]: {num(100 * ligados / max(1, c['vinculos']), 1)}% dos {num(c['vinculos'], 0)} vínculos "
        f"ligados a uma de {num(c['instituicoes'], 0)} instituições; país conhecido em "
        f"{num(100 * cob['pais_conhecido'], 1)}% do peso, UF em {num(100 * cob['uf_conhecida'], 1)}% do peso "
        f"brasileiro."
    )
    if geografia_em_dia(p) is False:
        console.print(
            "[yellow]A geografia é de antes da última coleta ou das últimas correções.[/] Rode [bold]mapa "
            "geografia[/] para atualizá-la."
        )


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
    _mostrar_topicos(p)
    _mostrar_geografia(p)
    _mostrar_classificacao_status(p)
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


def _problema_da_porta(porta: int) -> str | None:
    """`None` se o painel pode usar a porta; senão, o motivo, em português.

    Além de ver se alguém já escuta nela, tenta ocupá-la como o uvicorn (e a solta em seguida): assim o erro sai
    antes de o painel anunciar o endereço, e não em inglês, depois dele.
    """
    import errno
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("127.0.0.1", porta)) == 0:
            return f"a porta {porta} já está em uso"
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # como o uvicorn
        try:
            s.bind(("127.0.0.1", porta))
        except OSError as e:
            if e.errno == errno.EADDRINUSE:
                return f"a porta {porta} já está em uso"
            if e.errno == errno.EACCES:
                return f"sem permissão para usar a porta {porta} (as abaixo de 1024 costumam ser reservadas)"
            return f"não foi possível usar a porta {porta} ({e.strerror})"
    return None


def _porta_sugerida(porta: int) -> int | None:
    """A primeira porta livre depois de `porta` (e acima de 1024), para sugerir no erro."""
    inicio = max(porta + 1, 1025)
    return next((p for p in range(inicio, min(inicio + 50, 65536)) if _problema_da_porta(p) is None), None)


@app.command()
def publicar(
    projeto: OpcaoProjeto = Path("."),
    destino: Annotated[
        Path | None, typer.Option("--destino", help="Pasta do site (padrão: saida/site do projeto).")
    ] = None,
    sem_resumos: Annotated[
        bool, typer.Option("--sem-resumos", help="Publica sem nenhum resumo, nem os de licença aberta.")
    ] = False,
) -> None:
    """Gera o site estático do projeto (para o GitHub Pages): resumos só com licença aberta, sem API."""
    from mapa_da_ciencia.publicar import publicar as rodar

    with _erros_amigaveis():
        p = Projeto.abrir(projeto)
        r = rodar(p, destino, sem_resumos=sem_resumos)
    console.print(f"[bold green]{r}[/]")
    if r.evidencias_retiradas:
        console.print(
            f"[dim]O texto de {num(r.evidencias_retiradas, 0)} evidência(s) da classificação também saiu (são trechos "
            "de resumos sem licença aberta); os valores continuam.[/]"
        )
    for aviso in r.avisos:
        console.print(f"[yellow]Aviso:[/] {aviso}")
    console.print(
        f"Para ver antes de publicar: [bold]python -m http.server -d {r.destino}[/] e abra http://localhost:8000. "
        "Veja o guia Publicar para o GitHub Pages."
    )


@app.command()
def painel(
    projeto: OpcaoProjeto = Path("."),
    exemplo: Annotated[
        bool, typer.Option("--exemplo", help="Mostra o exemplo sintético, sem precisar de um projeto.")
    ] = False,
    porta: Annotated[int, typer.Option("--porta", min=1, max=65535, help="Porta local do servidor.")] = 8765,
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

    if problema := _problema_da_porta(porta):
        sugerida = _porta_sugerida(porta)
        dica = f"por exemplo --porta {sugerida}" if sugerida else "com --porta"
        console.print(f"[bold red]Erro:[/] {problema}. Use outra, {dica}.")
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
        f"documento(s) de {len(resumo.por_revista)} revista(s), {periodo(plano.anos)}."
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
def topicos(
    projeto: OpcaoProjeto = Path("."),
    sem_rotulos: Annotated[
        bool,
        typer.Option("--sem-rotulos", help="Rótulos pelas palavras-chave, sem carregar o modelo de linguagem."),
    ] = False,
    refazer_embeddings: Annotated[
        bool, typer.Option("--refazer-embeddings", help="Recalcula os embeddings de todos os documentos.")
    ] = False,
    semente: Annotated[
        int | None,
        typer.Option("--semente", help="Semente principal do UMAP (padrão: a primeira de topicos.sementes)."),
    ] = None,
    refazer_macrotemas: Annotated[
        bool,
        typer.Option(
            "--refazer-macrotemas",
            help="Agrupa os tópicos em macrotemas de novo, em vez de manter os da execução anterior (as cores mudam).",
        ),
    ] = False,
) -> None:
    """Descobre os tópicos do corpus, dá um nome a cada um e prepara o mapa do painel."""
    from mapa_da_ciencia.progresso import ProgressoRich
    from mapa_da_ciencia.topicos.pipeline import OpcoesTopicos, gerar_topicos
    from mapa_da_ciencia.topicos.resultado import PASTA, Resultado

    with _erros_amigaveis():
        p = Projeto.abrir(projeto)
        progresso = ProgressoRich(console)
        opcoes = OpcoesTopicos(
            sem_rotulos=sem_rotulos,
            refazer_embeddings=refazer_embeddings,
            semente=semente,
            refazer_macrotemas=refazer_macrotemas,
        )
        try:
            resumo = gerar_topicos(p, opcoes, progresso)
        except KeyboardInterrupt:
            progresso.fim()
            console.print(
                "\n[yellow]Etapa interrompida.[/] Embeddings e rótulos já calculados estão em cache: "
                "rode [bold]mapa topicos[/] de novo para continuar."
            )
            raise typer.Exit(130) from None

    resultado = Resultado.ler(p.dados / PASTA)
    console.print(f"\n[bold green]Tópicos prontos[/]: {resumo}")
    if resultado:
        tabela = Table("Macrotema", "Tópicos", "Documentos")
        docs_por_topico = {t.id: t.n_nucleo for t in resultado.topicos}
        for m in resultado.macrotemas:
            tabela.add_row(
                f"[{m.cor}]●[/] {m.rotulo}", num(len(m.topicos), 0), num(sum(docs_por_topico[t] for t in m.topicos), 0)
            )
        console.print(tabela)
        console.print("[dim]Documentos do núcleo de cada tópico; os reatribuídos entram nas contagens do painel.[/]")
    ari = f"{num(resumo.estabilidade_ari, 2)}" if resumo.estabilidade_ari is not None else "—"
    console.print(
        f"[dim]Núcleo: {num(resumo.nucleo, 0)}; reatribuídos pela vizinhança: {num(resumo.reatribuidos, 0)}; "
        f"sem tópico: {num(resumo.sem_topico, 0)}. Estabilidade entre sementes (ARI): {ari}.[/]"
    )
    if resumo.casados == resumo.mesma_cor > 0:
        console.print(f"[dim]{num(resumo.casados, 0)} tópico(s) mantiveram o número e a cor da execução anterior.[/]")
    elif resumo.casados:
        console.print(
            f"[dim]{num(resumo.casados, 0)} tópico(s) mantiveram o número da execução anterior; "
            f"{num(resumo.mesma_cor, 0)} também a cor (os outros mudaram de macrotema).[/]"
        )
    console.print(f"[dim]Embeddings novos: {num(resumo.embeddings_novos, 0)} (os demais vieram do cache).[/]")
    r = resumo.rotulos
    if sem_rotulos:
        console.print("[dim]Rótulos: palavras-chave (sem modelo de linguagem).[/]")
    else:
        console.print(
            f"[dim]Rótulos ({r.modelo}): {num(r.chamadas, 0)} chamada(s) ao modelo, {num(r.do_cache, 0)} do cache, "
            f"{num(r.reaproveitados, 0)} mantidos da execução anterior, {num(r.manuais, 0)} do rotulos.yaml"
            + (f", {num(r.acentos_corrigidos, 0)} com acento corrigido" if r.acentos_corrigidos else "")
            + ".[/]"
        )
    for aviso in resumo.avisos:
        console.print(f"[yellow]Aviso:[/] {aviso}")
    console.print("Próximo passo: [bold]mapa painel[/] para ver o mapa.")


@app.command()
def classificar(
    projeto: OpcaoProjeto = Path("."),
    estimar: Annotated[
        bool,
        typer.Option("--estimar", help="Classifica 5 documentos, mede o tempo e projeta quanto falta. Grava os 5."),
    ] = False,
    limite: Annotated[
        int | None,
        typer.Option(
            "--limite", help="Classifica só os primeiros N da fila (a amostra de validação, depois por id).", min=1
        ),
    ] = None,
    modelo: Annotated[
        str | None,
        typer.Option("--modelo", help="Outro modelo do Ollama, para comparar (o painel mostra só o principal)."),
    ] = None,
    somente_amostra: Annotated[
        bool,
        typer.Option("--somente-amostra", help="Classifica só os documentos da amostra de validação."),
    ] = False,
) -> None:
    """Classifica os resumos segundo o codebook do projeto, com evidência textual para cada resposta."""
    from mapa_da_ciencia.classificacao.pipeline import OpcoesClassificacao
    from mapa_da_ciencia.classificacao.pipeline import classificar as rodar
    from mapa_da_ciencia.progresso import ProgressoRich

    with _erros_amigaveis():
        p = Projeto.abrir(projeto)
        try:
            resumo = rodar(
                p,
                OpcoesClassificacao(estimar=estimar, limite=limite, modelo=modelo, somente_amostra=somente_amostra),
                ProgressoRich(console),
            )
        except KeyboardInterrupt:
            console.print(
                "\n[yellow]Etapa interrompida.[/] Os documentos já classificados estão guardados: rode "
                "[bold]mapa classificar[/] de novo para continuar."
            )
            raise typer.Exit(130) from None
    _mostrar_classificacao(p, resumo, estimar=estimar)


def _mostrar_classificacao(p: Projeto, resumo, *, estimar: bool) -> None:
    from mapa_da_ciencia.classificacao.resultado import PASTA, ler_linhas

    console.print(f"\n[bold green]Classificação pronta[/]: {resumo}")
    linhas = ler_linhas(p.dados / PASTA, resumo.modelo, p.codebook.hash(), a_parte=resumo.a_parte)
    tabela = Table("Variável", "Mais frequentes", "Evidência literal")
    for v in p.codebook.variaveis:
        valores = Counter(linha["valor"] for linha in linhas if linha["variavel"] == v.id)
        status = [linha["status"] for linha in linhas if linha["variavel"] == v.id and linha["status"] != "dispensada"]
        literal = f"{num(100 * status.count('literal') / len(status), 0)}%" if status else "—"
        rotulos = {c.valor: c.rotulo or c.valor for c in v.categorias} | {"true": "Sim", "false": "Não"}
        mais = ", ".join(f"{rotulos.get(k, k)} ({num(n, 0)})" for k, n in valores.most_common(3))
        tabela.add_row(v.rotulo, mais, literal)
    if linhas:
        console.print(tabela)
    if resumo.json_valido_na_primeira is not None:
        console.print(
            f"[dim]JSON válido na primeira tentativa: {num(100 * resumo.json_valido_na_primeira, 1)}%; "
            f"{num(resumo.segundos_por_documento or 0, 1)} s por documento (mediana); "
            f"{num(resumo.sem_resumo, 0)} documento(s) sem resumo ficam de fora.[/]"
        )
    if estimar and resumo.estimativa_restante_s is not None:
        horas = resumo.estimativa_restante_s / 3600
        console.print(
            f"[bold]Estimativa:[/] faltam {num(resumo.pendentes, 0)} documentos, cerca de "
            f"{num(horas, 1)} h neste computador. Rode [bold]mapa classificar[/] para classificar todos: a "
            "etapa pode ser interrompida e retomada."
        )
    elif resumo.pendentes:
        console.print(f"Faltam {num(resumo.pendentes, 0)} documento(s): rode [bold]mapa classificar[/] de novo.")
    for aviso in resumo.avisos:
        console.print(f"[yellow]Aviso:[/] {aviso}")


validar_app = typer.Typer(
    help="Validação da classificação: a amostra, as codificações e a concordância.",
    no_args_is_help=True,
)
app.add_typer(validar_app, name="validar")


@validar_app.command("amostra")
def validar_amostra(
    projeto: OpcaoProjeto = Path("."),
    refazer: Annotated[
        bool, typer.Option("--refazer", help="Sorteia outra amostra (as codificações já feitas continuam guardadas).")
    ] = False,
    n: Annotated[
        int | None,
        typer.Option("--n", help="Tamanho da amostra neste sorteio (padrão: validacao.n do mapa.yaml).", min=1),
    ] = None,
) -> None:
    """Sorteia a amostra de validação (uma vez) e exporta os textos para quem vai codificar."""
    from mapa_da_ciencia.validacao import amostra as va

    with _erros_amigaveis():
        p = Projeto.abrir(projeto)
        ja = va.ler(p)
        if ja is not None and n is not None and n != len(ja.docs) and not refazer:
            raise ErroConfig(
                f"A amostra já foi sorteada, com {len(ja.docs)} documentos. Use --refazer para sortear outra."
            )
        a = va.sortear(p, refazer=refazer, n=n)
        arquivo = va.exportar(p, a)
    novo = ja is None or refazer
    console.print(
        f"[bold green]Amostra {'sorteada' if novo else 'já sorteada'}[/]: {num(len(a.docs), 0)} documentos, "
        f"estratificada por {va.ESTRATOS[a.estratificar_por]} ({num(len(a.por_estrato()), 0)} estratos), "
        f"semente {a.semente}."
    )
    tabela = Table("Estrato", "Documentos")
    nomes = va.nomes_dos_estratos(p, list(a.por_estrato()))
    for estrato, n in sorted(a.por_estrato().items(), key=lambda e: (-e[1], e[0]))[:12]:
        tabela.add_row(nomes[estrato], num(n, 0))
    if len(a.por_estrato()) > 12:
        tabela.add_row("…", "")
    console.print(tabela)
    console.print(
        f"Textos para codificar em [bold]{arquivo.relative_to(p.raiz)}[/] (só id, título, resumo e idioma). "
        "Codifique no painel ([bold]mapa painel[/], Validação › Codificar) ou importe um arquivo com "
        "[bold]mapa validar importar[/]."
    )
    for aviso in a.avisos:
        console.print(f"[yellow]Aviso:[/] {aviso}")


@validar_app.command("importar")
def validar_importar(
    arquivo: Annotated[Path, typer.Argument(help="JSONL com uma linha por documento.", exists=True, dir_okay=False)],
    codificador: Annotated[str, typer.Option("--codificador", "-c", help="Nome de quem codificou.")],
    projeto: OpcaoProjeto = Path("."),
    tipo: Annotated[
        str,
        typer.Option(
            "--tipo", help="`humano` ou `referencia` (um anotador que não é uma pessoa, como outro modelo de IA)."
        ),
    ] = "humano",
) -> None:
    """Importa as codificações de um arquivo JSONL (formato no guia "Codificar a amostra")."""
    from mapa_da_ciencia.contrato.exportar import exportar
    from mapa_da_ciencia.validacao import amostra as va

    with _erros_amigaveis():
        if tipo not in ("humano", "referencia"):
            raise ErroConfig(f"Tipo de codificador inválido: {tipo!r}. Use `humano` ou `referencia`.")
        p = Projeto.abrir(projeto)
        r = va.importar(p, arquivo, codificador, tipo=tipo)  # type: ignore[arg-type]
        n_amostra = len(va.ler(p).docs)  # type: ignore[union-attr]
        avisos = exportar(p) if r.documentos else []  # o painel passa a mostrar a concordância
    console.print(
        f"[bold green]Importado[/]: {num(r.documentos, 0)} de {num(n_amostra, 0)} documentos da amostra "
        f"codificados por [bold]{r.codificador}[/] ({tipo})."
    )
    if r.fora_da_amostra:
        console.print(
            f"[yellow]Aviso:[/] {num(len(r.fora_da_amostra), 0)} linha(s) com documentos fora da amostra foram "
            f"ignoradas (por exemplo {', '.join(r.fora_da_amostra[:3])})."
        )
    for aviso in avisos:
        console.print(f"[yellow]Aviso:[/] {aviso}")
    for problema in r.invalidas[:10]:
        console.print(f"[red]Inválida:[/] {problema}")
    if len(r.invalidas) > 10:
        console.print(f"[red]… e mais {num(len(r.invalidas) - 10, 0)} linha(s) inválida(s).[/]")
    if r.invalidas:
        raise typer.Exit(1)


@validar_app.command("metricas")
def validar_metricas(projeto: OpcaoProjeto = Path(".")) -> None:
    """Concordância entre codificadores e modelos na amostra: kappa com IC 95%, PABAK e alfa, por variável."""
    from mapa_da_ciencia.validacao.metricas import calcular

    with _erros_amigaveis():
        p = Projeto.abrir(projeto)
        r = calcular(p)
    _mostrar_validacao(r)


@validar_app.command("relatorio")
def validar_relatorio(projeto: OpcaoProjeto = Path(".")) -> None:
    """Grava o relatório da validação em `validacao/`: Markdown, tabelas LaTeX e JSON."""
    from mapa_da_ciencia.validacao.relatorio import gerar

    with _erros_amigaveis():
        p = Projeto.abrir(projeto)
        v, arquivos = gerar(p)
    _mostrar_validacao(v)
    console.print(
        "[bold green]Relatório gravado[/]: "
        + ", ".join(f"[bold]{a.relative_to(p.raiz)}[/]" for a in arquivos.values())
        + "."
    )


juri_app = typer.Typer(
    help='Júri de modelos locais: votação, deliberação, supervisor e relatório (ver o guia "Usar o júri").',
    no_args_is_help=True,
)
app.add_typer(juri_app, name="juri")


@juri_app.command("votar")
def juri_votar(projeto: OpcaoProjeto = Path(".")) -> None:
    """Rodada 1: cada membro de `juri.membros` classifica a amostra de validação (o que ainda falta)."""
    from mapa_da_ciencia.juri.votacao import votar
    from mapa_da_ciencia.progresso import ProgressoRich

    with _erros_amigaveis():
        p = Projeto.abrir(projeto)
        r = votar(p, progresso=ProgressoRich(console))
    console.print(f"[bold green]Votação pronta[/]: {r}")
    if r.ja_prontos:
        console.print(f"Já tinham classificado tudo: {', '.join(r.ja_prontos)}.")
    console.print("Próximo passo: [bold]mapa juri deliberar[/].")


@juri_app.command("deliberar")
def juri_deliberar(projeto: OpcaoProjeto = Path(".")) -> None:
    """Rodada 2: os membros que discordam reveem as respostas vendo as dos outros, anônimas."""
    from mapa_da_ciencia.juri.pipeline import deliberar_juri
    from mapa_da_ciencia.progresso import ProgressoRich

    with _erros_amigaveis():
        p = Projeto.abrir(projeto)
        d, r = deliberar_juri(p, ProgressoRich(console))
    console.print(f"[bold green]Deliberação pronta[/]: {d}")
    console.print(str(r))
    if r.pendentes_supervisor:
        console.print(
            f"{num(r.pendentes_supervisor, 0)} decisão(ões) sem maioria: [bold]mapa juri exportar-pedidos[/] prepara "
            "os pedidos ao supervisor."
        )


@juri_app.command("exportar-pedidos")
def juri_exportar_pedidos(
    projeto: OpcaoProjeto = Path("."),
    lote: Annotated[int, typer.Option("--lote", min=1, help="Pedidos por arquivo.")] = 20,
    todos: Annotated[bool, typer.Option("--todos", help="Inclui os pedidos que já têm resposta.")] = False,
) -> None:
    """Grava em `juri/` os pedidos ao supervisor (arbitragem e auditoria), em lotes JSONL, com as instruções."""
    from mapa_da_ciencia.juri.supervisor import exportar_pedidos

    with _erros_amigaveis():
        p = Projeto.abrir(projeto)
        r = exportar_pedidos(p, lote=lote, todos=todos)
    console.print(f"[bold green]Pedidos ao supervisor[/]: {r}")
    if r.arquivos:
        console.print(
            "Entregue ao supervisor as instruções ([bold]juri/instrucoes-supervisor.md[/]) e cada lote; as respostas "
            "voltam como [bold]<lote>.respostas.jsonl[/] e entram com [bold]mapa juri importar-respostas[/]."
        )


@juri_app.command("importar-respostas")
def juri_importar_respostas(
    arquivos: Annotated[
        list[Path] | None,
        typer.Argument(help="Arquivos de respostas; sem nenhum, todos os `juri/*.respostas.jsonl`.", exists=True),
    ] = None,
    projeto: OpcaoProjeto = Path("."),
) -> None:
    """Confere e guarda as respostas do supervisor (o de `juri.supervisor.nome`), e consolida o júri."""
    from mapa_da_ciencia.juri.pipeline import arquivos_de_respostas
    from mapa_da_ciencia.juri.supervisor import importar_respostas

    with _erros_amigaveis():
        p = Projeto.abrir(projeto)
        lista = arquivos_de_respostas(p, list(arquivos or []))
        if not lista:
            raise ErroConfig("Nenhum arquivo de respostas: passe os arquivos ou ponha-os em `juri/` do projeto.")
        r = importar_respostas(p, lista)
    console.print(f"[bold green]Respostas do supervisor[/]: {r}")
    for motivo in r.recusadas[:10]:
        console.print(f"[red]Recusada:[/] {motivo}")
    if len(r.recusadas) > 10:
        console.print(f"[red]… e mais {num(len(r.recusadas) - 10, 0)}.[/]")


@juri_app.command("supervisionar")
def juri_supervisionar(
    projeto: OpcaoProjeto = Path("."),
    limite_gasto: Annotated[
        float | None,
        typer.Option("--limite-gasto", min=0, help="Gasto máximo em dólares (padrão: o do mapa.yaml)."),
    ] = None,
    sim: Annotated[bool, typer.Option("--sim", help="Envia sem perguntar (depois de mostrar a estimativa).")] = False,
) -> None:
    """Supervisor pela API da Anthropic (modo `api`): envia os pedidos, com consentimento e limite de gasto."""
    from mapa_da_ciencia.juri.supervisor import supervisionar

    with _erros_amigaveis():
        p = Projeto.abrir(projeto)
        estimativa = supervisionar(p, limite_gasto=limite_gasto)
        console.print(str(estimativa))
        if not estimativa.pedidos:
            return
        if not sim and not typer.confirm(
            f"Enviar {estimativa.pedidos} pedido(s), com títulos e resumos, para a API da Anthropic?", default=False
        ):
            raise typer.Exit(1)
        r = supervisionar(p, limite_gasto=limite_gasto, confirmar=True)
    console.print(f"[bold green]Supervisor[/]: {r}")
    if r.importacao:
        console.print(str(r.importacao))
    for falha in r.falhas[:5]:
        console.print(f"[red]Falhou:[/] {falha}")


@juri_app.command("status")
def juri_status(projeto: OpcaoProjeto = Path(".")) -> None:
    """Em que passo o júri está."""
    from mapa_da_ciencia.juri.pipeline import estado

    with _erros_amigaveis():
        p = Projeto.abrir(projeto)
        e = estado(p)
    tabela = Table("Membro", "Amostra classificada")
    for membro, n in e.classificados.items():
        tabela.add_row(membro, f"{num(n, 0)} de {num(e.amostra, 0)}")
    console.print(tabela)
    if e.resumo:
        console.print(str(e.resumo))
    console.print(f"Próximo passo: [bold]{e.proximo}[/].")


@juri_app.command("relatorio")
def juri_relatorio(projeto: OpcaoProjeto = Path(".")) -> None:
    """Grava `validacao/juri.md`: kappa de cada membro e do júri, estágios, deliberação e auditoria."""
    from mapa_da_ciencia.contrato.exportar import exportar
    from mapa_da_ciencia.juri.relatorio import gerar

    with _erros_amigaveis():
        p = Projeto.abrir(projeto)
        destino, n = gerar(p)
        avisos = exportar(p)
    console.print(f"[bold green]Relatório do júri[/]: [bold]{destino.relative_to(p.raiz)}[/].")
    if n.nao_deliberados:
        console.print(
            f"[yellow]Aviso:[/] {num(n.nao_deliberados, 0)} decisão(ões) em disputa ainda sem deliberação: rode "
            "[bold]mapa juri deliberar[/]."
        )
    if n.referencia is None:
        console.print("[yellow]Aviso:[/] sem codificador de referência, o relatório só tem os estágios.")
    for aviso in avisos:
        console.print(f"[yellow]Aviso:[/] {aviso}")


def _f(valor: float | None, casas: int = 2) -> str:
    return "—" if valor is None else num(valor, casas)


def _mostrar_validacao(r) -> None:
    from mapa_da_ciencia.validacao.amostra import ESTRATOS

    tipos = {"humano": "pessoa", "referencia": "referência, não humano", "modelo": "modelo"}
    console.print(
        f"[bold]Validação[/] na amostra de {num(r.amostra['n'], 0)} documentos (estratificada por "
        f"{ESTRATOS[r.amostra['estratificar_por']]}, semente {r.amostra['semente']}), codebook {r.codebook}."
    )
    console.print(
        "Participantes: "
        + "; ".join(f"[bold]{x.nome}[/] ({tipos[x.tipo]}, {num(x.n, 0)} documentos)" for x in r.participantes)
    )
    if not r.metricas:
        console.print(
            "[yellow]Nada a comparar ainda.[/] É preciso ao menos dois participantes: codifique a amostra "
            "([bold]mapa validar importar[/] ou o painel) e classifique-a "
            "([bold]mapa classificar --somente-amostra[/])."
        )
        return
    for par in dict.fromkeys((m.referencia, m.comparado) for m in r.metricas):
        tabela = Table("Variável", "n", "Concordância", "Kappa (IC 95%)", "PABAK", "Alfa", title=" × ".join(par))
        for m in (m for m in r.metricas if (m.referencia, m.comparado) == par):
            ic = f" ({_f(m.kappa_ic95[0])} a {_f(m.kappa_ic95[1])})" if m.kappa_ic95 else ""
            conc = "—" if m.concordancia is None else f"{num(100 * m.concordancia, 0)}%"
            tabela.add_row(m.variavel, num(m.n, 0), conc, _f(m.kappa) + ic, _f(m.pabak), _f(m.alfa))
        console.print(tabela)
    diferentes = [c for c in r.comparacoes_modelos if c.p < 0.05]
    for c in diferentes:
        melhor = c.modelo_a if c.acertos_a > c.acertos_b else c.modelo_b
        console.print(
            f"McNemar ({c.variavel}, contra {c.referencia}): {melhor} acerta mais "
            f"({num(c.acertos_a, 0)} × {num(c.acertos_b, 0)} de {num(c.n, 0)}; p = {num(c.p, 3)})."
        )
    if r.comparacoes_modelos and not diferentes:
        console.print("[dim]McNemar: nenhuma diferença entre os modelos com p < 0,05.[/]")
    if r.divergencias:
        console.print(
            f"{num(len(r.divergencias), 0)} divergência(s) entre os codificadores e o modelo principal: veja o "
            "relatório ([bold]mapa validar relatorio[/]) ou a vista Concordância do painel."
        )


@app.command()
def geografia(
    projeto: OpcaoProjeto = Path("."),
    revisar: Annotated[
        bool,
        typer.Option(
            "--revisar",
            help="Lista as afiliações que não casaram, com sugestões e um bloco pronto para o instituicoes.yaml.",
        ),
    ] = False,
    limite: Annotated[int, typer.Option("--limite", help="Quantas afiliações listar na revisão.", min=1)] = 20,
) -> None:
    """Liga cada afiliação a uma instituição, com UF e país, e faz a contagem fracionária da produção."""
    from mapa_da_ciencia.geografia.pipeline import gerar_geografia
    from mapa_da_ciencia.geografia.resultado import PASTA, ler_instituicoes
    from mapa_da_ciencia.progresso import ProgressoRich

    with _erros_amigaveis():
        p = Projeto.abrir(projeto)
        resumo = gerar_geografia(p, ProgressoRich(console))
    if revisar:
        _revisar_geografia(p, limite)
        return

    console.print(f"\n[bold green]Geografia pronta[/]: {resumo}")
    fontes = Table("Fonte das afiliações", "Vínculos", "Ligados a uma instituição")
    nomes = {"v240": "ArticleMeta, normalizada (v240)", "v70": "ArticleMeta, texto livre (v70)", "openalex": "OpenAlex"}
    for fonte, n in resumo.por_fonte.items():
        ok = resumo.identificados.get(fonte, 0)
        fontes.add_row(nomes.get(fonte, fonte), num(n, 0), f"{num(ok, 0)} ({num(100 * ok / n, 1)}%)")
    console.print(fontes)
    maiores = sorted(ler_instituicoes(p.dados / PASTA), key=lambda i: -i["peso"])[:10]
    tabela = Table("Instituição", "Lugar", "Peso", "Documentos")
    for i in maiores:
        nome = f"{i['nome']} ({i['sigla']})" if i["sigla"] else i["nome"]
        lugar = f"{i['uf']}, {i['pais']}" if i["uf"] else (i["pais"] or "")
        tabela.add_row(nome, lugar, num(i["peso"], 1), num(i["documentos"], 0))
    console.print(tabela)
    niveis = ", ".join(f"{k} {num(v, 0)}" for k, v in resumo.por_nivel.items())
    console.print(
        f"[dim]Peso fracionário: cada documento vale 1, dividido entre os autores e as afiliações de cada um. "
        f"Sem afiliação: {num(resumo.sem_afiliacao, 1)} de {num(resumo.documentos, 0)}. Casamentos por nível: "
        f"{niveis}.[/]"
    )
    for aviso in resumo.avisos:
        console.print(f"[yellow]Aviso:[/] {aviso}")
    console.print(
        "Próximo passo: [bold]mapa painel[/] para ver a geografia, ou [bold]mapa geografia --revisar[/] para "
        "corrigir as afiliações que não casaram."
    )


def _revisar_geografia(p: Projeto, limite: int) -> None:
    from mapa_da_ciencia.geografia.revisao import bloco_yaml, pendencias

    lista = pendencias(p, limite)
    if not lista:
        console.print("\n[bold green]Todas as afiliações com texto casaram com uma instituição.[/]")
        return
    tabela = Table("Texto da afiliação", "Vínculos", "Docs", "País", "Instituição parecida", title_justify="left")
    tabela.title = f"As {num(len(lista), 0)} afiliações sem instituição mais frequentes"
    for pend in lista:
        grafias = f" [dim](+{pend.grafias - 1} grafia(s))[/]" if pend.grafias > 1 else ""
        sugestao = (
            "\n".join(f"{s.nome} ({s.pais or '?'}, {num(s.nota, 2)})" for s in pend.sugestoes)
            if pend.sugestoes
            else "[dim]—[/]"
        )
        tabela.add_row(pend.texto + grafias, num(pend.vinculos, 0), num(pend.documentos, 0), pend.pais or "", sugestao)
    console.print()
    console.print(tabela)
    console.print(
        "\nCopie para o [bold]instituicoes.yaml[/] do projeto o que estiver certo (as linhas comentadas são "
        "modelos de instituição própria) e rode [bold]mapa geografia[/] de novo:\n"
    )
    # sem quebrar as linhas, para o bloco poder ser copiado como está
    console.print(bloco_yaml(lista), highlight=False, markup=False, soft_wrap=True)


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
