"""Os textos do Typer e do Click em português, para a CLI `mapa` falar uma língua só.

Desde a 0.27, o Typer embute o Click (`typer._click`) com os textos fixos em inglês, sem gettext. O que dá para
trocar sem reescrever a CLI fica aqui:

- os títulos e marcas da ajuda (Argumentos, Opções, Comandos, `[padrão: …]`, `[obrigatório]`), que o Typer lê de
  constantes de `typer.rich_utils`, e a linha "Veja 'mapa … -h' para a ajuda." dos erros;
- a linha `Uso:` (com `[OPÇÕES]` e `COMANDO [ARGS]...`), o texto da opção `-h` e o tipo de cada opção
  (`<caminho>`, `<texto>`, `<inteiro>`), pelo contexto, pelo formatador e pelo `metavar` de cada comando;
- as mensagens dos erros de uso mais comuns (opção ou comando inexistente, valor inválido, opção ou argumento
  faltando), traduzidas quando passam pelo grupo principal (`GrupoEmPortugues`), antes de o Typer mostrá-las.

Uma mensagem que não esteja na lista continua em inglês, e o tipo dos argumentos posicionais também (`pasta
<path>`): neles, o `metavar` trocaria o nome do argumento, e não o tipo.
"""

from __future__ import annotations

import re
from typing import Any

from typer import rich_utils
from typer._click import Command, Context, HelpFormatter
from typer._click.exceptions import UsageError
from typer.core import TyperGroup, TyperOption

AJUDA = "Mostra esta ajuda e sai."

# o tipo que a ajuda mostra ao lado de cada opção (`<path>`, `<int range>`…), pelo nome do tipo no Click
_METAVARS = {
    "path": "<caminho>",
    "file": "<arquivo>",
    "str": "<texto>",
    "int": "<inteiro>",
    "int range": "<inteiro>",
    "float": "<número>",
    "float range": "<número>",
}

rich_utils.ARGUMENTS_PANEL_TITLE = "Argumentos"
rich_utils.OPTIONS_PANEL_TITLE = "Opções"
rich_utils.COMMANDS_PANEL_TITLE = "Comandos"
rich_utils.ERRORS_PANEL_TITLE = "Erro"
rich_utils.DEFAULT_STRING = "[padrão: {}]"
rich_utils.REQUIRED_LONG_STRING = "[obrigatório]"
rich_utils.ENVVAR_STRING = "[variável de ambiente: {}]"
rich_utils.DEPRECATED_STRING = "(obsoleto) "
rich_utils.ABORTED_TEXT = "Interrompido."
rich_utils.RICH_HELP = "Veja [blue]'{command_path} {help_option}'[/] para a ajuda."

_TIPOS = {
    "int": "um número inteiro",
    "int range": "um número inteiro",
    "float": "um número",
    "float range": "um número",
    "boolean": "sim ou não (true/false)",
}

# (padrão em inglês, tradução), aplicados em ordem ao texto final da mensagem
_MENSAGENS: list[tuple[re.Pattern[str], Any]] = [
    (re.compile(r"No such option: (\S+)"), r"Opção inexistente: \1"),
    (re.compile(r"No such command (.+?)\."), r"Comando inexistente: \1."),
    (re.compile(r"Did you mean (.+)\?"), r"Você quis dizer \1?"),
    (re.compile(r"\(Possible options: (.+)\)"), r"(opções possíveis: \1)"),
    (re.compile(r"Invalid value for (.+?): "), r"Valor inválido para \1: "),
    (re.compile(r"Invalid value: "), "Valor inválido: "),
    (
        re.compile(r"(.+) is not a valid ([\w ]+?)\."),
        lambda m: f"{m[1]} não é {_TIPOS.get(m[2], f'um valor válido do tipo {m[2]}')}.",
    ),
    (re.compile(r"(.+) is not in the range (.+)\."), r"\1 está fora da faixa \2."),
    (re.compile(r"Missing option (.+)\."), r"Falta a opção \1."),
    (re.compile(r"Missing argument (.+)\."), r"Falta o argumento \1."),
    (re.compile(r"Missing parameter"), "Falta o parâmetro"),
    (re.compile(r"Missing command\."), "Falta o comando."),
    (re.compile(r"Got unexpected extra argument(?:s|\(s\))? \((.+)\)"), r"Argumentos a mais: \1"),
    (re.compile(r"Option (.+?) requires an argument\."), r"A opção \1 precisa de um valor."),
    (re.compile(r"Option (.+?) requires (\d+) arguments\."), r"A opção \1 precisa de \2 valores."),
    (re.compile(r"Option (.+?) does not take a value\."), r"A opção \1 não aceita valor."),
]


def traduzir(mensagem: str) -> str:
    """A mensagem de um erro de uso do Click, em português (a parte que estiver na lista)."""
    for padrao, traducao in _MENSAGENS:
        mensagem = padrao.sub(traducao, mensagem)
    return mensagem


def _traduzir_erro(erro: UsageError) -> None:
    """Troca a mensagem do erro pela traduzida, na hora em que o Typer for mostrá-la."""
    if getattr(erro, "_em_portugues", False):
        return
    formatar = erro.format_message
    erro.format_message = lambda: traduzir(formatar())  # type: ignore[method-assign]
    erro._em_portugues = True  # type: ignore[attr-defined]


class _FormatadorEmPortugues(HelpFormatter):
    def write_usage(self, prog: str, args: str = "", prefix: str | None = None) -> None:
        super().write_usage(prog, args, "Uso: " if prefix is None else prefix)


class _ContextoEmPortugues(Context):
    formatter_class = _FormatadorEmPortugues


def _em_portugues(comando: Command) -> None:
    """Contexto (a linha `Uso:`) e opção `-h` em português, no comando e nos subcomandos dele."""
    comando.context_class = _ContextoEmPortugues
    if comando.options_metavar == "[OPTIONS]":
        comando.options_metavar = "[OPÇÕES]"
    if getattr(comando, "subcommand_metavar", None) == "COMMAND [ARGS]...":
        comando.subcommand_metavar = "COMANDO [ARGS]..."  # type: ignore[attr-defined]
    criar_ajuda = comando.get_help_option

    def get_help_option(ctx: Context) -> Any:
        opcao = criar_ajuda(ctx)
        if opcao is not None:
            opcao.help = AJUDA
        return opcao

    comando.get_help_option = get_help_option  # type: ignore[method-assign]
    for param in comando.params:
        if isinstance(param, TyperOption) and param.metavar is None and not param.is_flag:
            param.metavar = _METAVARS.get(param.type.name)
    for sub in getattr(comando, "commands", {}).values():
        _em_portugues(sub)


class GrupoEmPortugues(TyperGroup):
    """O grupo principal da CLI: ajuda e erros de uso em português (ver o topo deste módulo)."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        _em_portugues(self)

    def parse_args(self, ctx: Context, args: list[str]) -> list[str]:
        try:
            return super().parse_args(ctx, args)
        except UsageError as e:
            _traduzir_erro(e)
            raise

    def invoke(self, ctx: Context) -> Any:
        # os erros de uso dos subcomandos (e dos grupos abaixo deste) sobem por aqui
        try:
            return super().invoke(ctx)
        except UsageError as e:
            _traduzir_erro(e)
            raise
