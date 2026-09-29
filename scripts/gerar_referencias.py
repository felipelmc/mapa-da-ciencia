"""Gera as páginas de referência da documentação a partir do código.

- docs/referencia/cli.md            ← comandos do Typer (`mapa_da_ciencia.cli`)
- docs/referencia/configuracao.md   ← modelos do `mapa.yaml` (`mapa_da_ciencia.config`)
- docs/referencia/codebook.md       ← modelos do `codebook.yaml`
- docs/referencia/contrato.md       ← modelos do contrato de dados (`mapa_da_ciencia.contrato.modelos`)
- docs/desenvolvimento/api-http.md  ← rotas do painel (o OpenAPI de `mapa_da_ciencia.servidor.app`); fica fora do
  site, com as outras notas de desenvolvimento, porque só serve a quem mexe no painel

Uso (da raiz do repo):
    uv run python scripts/gerar_referencias.py            # regenera
    uv run python scripts/gerar_referencias.py --checar   # falha se estiverem desatualizadas (CI)
"""

from __future__ import annotations

import argparse
import inspect
import json
import re
import sys
import types
import typing
from pathlib import Path

import typer
from pydantic import BaseModel
from pydantic_core import PydanticUndefined
from typer.core import TyperArgument, TyperGroup

from mapa_da_ciencia import cli, config
from mapa_da_ciencia.contrato import modelos as contrato

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "docs"
AVISO = "<!-- Página gerada por scripts/gerar_referencias.py a partir do código. Não edite à mão. -->\n"


# ---------------------------------------------------------------- utilidades
def _sem_markup(texto: str) -> str:
    return re.sub(r"\[/?[a-z ]*\]", "", texto or "").strip()


def _celula(texto: str) -> str:
    return texto.replace("|", "\\|").replace("\n", " ")


def _tipo(anot: object) -> str:
    origem, args = typing.get_origin(anot), typing.get_args(anot)
    if origem is typing.Annotated:
        base, *meta = args
        padrao = next((getattr(m, "pattern", None) for m in meta if getattr(m, "pattern", None)), None)
        return _tipo(base) + (f" (formato `{padrao}`)" if padrao else "")
    if origem is typing.Literal:
        return " | ".join(f"`{json.dumps(a, ensure_ascii=False)}`" for a in args)
    if origem in (typing.Union, types.UnionType):
        partes = [a for a in args if a is not type(None)]
        texto = " ou ".join(_tipo(a) for a in partes)
        return f"{texto} ou vazio" if len(partes) < len(args) else texto
    if origem is list:
        return f"lista de {_tipo(args[0])}"
    if origem is tuple:
        return "par de " + " e ".join(_tipo(a) for a in args) if len(args) == 2 else "tupla"
    if origem is dict:
        return f"mapa de {_tipo(args[0])} para {_tipo(args[1])}"
    if inspect.isclass(anot) and issubclass(anot, BaseModel):
        return f"[{anot.__name__}](#{anot.__name__.lower()})"
    nomes = {str: "texto", int: "inteiro", float: "número", bool: "sim/não", Path: "caminho", type(None): "vazio"}
    return nomes.get(anot, getattr(anot, "__name__", str(anot)))  # type: ignore[arg-type]


def _padrao(campo) -> str:
    if campo.default is PydanticUndefined and campo.default_factory is None:
        return "**obrigatório**"
    valor = campo.default_factory() if campo.default_factory else campo.default
    if isinstance(valor, BaseModel):
        return "valores padrão da seção"
    if isinstance(valor, list | dict | tuple) and not valor:
        return "vazio"
    if valor is None:
        return "vazio"
    return f"`{json.dumps(valor, ensure_ascii=False, default=str)}`"


def _modelos_aninhados(modelo: type[BaseModel]) -> list[type[BaseModel]]:
    """O modelo e todos os modelos usados nos seus campos, em ordem de aparição."""
    vistos: list[type[BaseModel]] = []

    def visitar(anot: object) -> None:
        if inspect.isclass(anot) and issubclass(anot, BaseModel):
            if anot not in vistos:
                vistos.append(anot)
                for c in anot.model_fields.values():
                    visitar(c.annotation)
            return
        for a in typing.get_args(anot):
            visitar(a)

    visitar(modelo)
    return vistos


def _doc_da_secao(anot: object) -> str:
    """Primeira linha da docstring do modelo de uma seção (também dentro de `X | None`)."""
    candidatos = [anot, *typing.get_args(anot)]
    for c in candidatos:
        if inspect.isclass(c) and issubclass(c, BaseModel) and c.__doc__:
            return inspect.cleandoc(c.__doc__).splitlines()[0]
    return ""


def _tabela(modelo: type[BaseModel], nivel: int = 3) -> list[str]:
    doc = inspect.cleandoc(modelo.__doc__ or "") if modelo.__doc__ and modelo.__module__ != "pydantic.main" else ""
    linhas = [f"{'#' * nivel} {modelo.__name__}", ""]
    if doc:
        linhas += [doc, ""]
    linhas += ["| Campo | Tipo | Padrão | Descrição |", "|---|---|---|---|"]
    for nome, campo in modelo.model_fields.items():
        descricao = campo.description or _doc_da_secao(campo.annotation)
        linhas.append(
            f"| `{nome}` | {_celula(_tipo(campo.annotation))} | {_celula(_padrao(campo))} | {_celula(descricao)} |"
        )
    return [*linhas, ""]


# ---------------------------------------------------------------- páginas
def pagina_cli() -> str:
    grupo = typer.main.get_command(cli.app)
    assert isinstance(grupo, TyperGroup)
    linhas = [
        AVISO,
        "# Linha de comando",
        "",
        "Todos os comandos têm ajuda embutida: `mapa --help` ou `mapa <comando> --help`.",
        "",
        "Opção global: `mapa --versao` (`-V`) mostra a versão instalada.",
        "",
    ]

    def comandos(g: TyperGroup, prefixo: str):
        for nome, cmd in g.commands.items():
            yield f"{prefixo} {nome}", cmd
            if isinstance(cmd, TyperGroup):
                yield from comandos(cmd, f"{prefixo} {nome}")

    for nome, cmd in comandos(grupo, "mapa"):
        args = [p for p in cmd.params if isinstance(p, TyperArgument)]
        partes = [p.human_readable_name if p.required else f"[{p.human_readable_name}]" for p in args]
        if isinstance(cmd, TyperGroup):
            partes.append("COMANDO")
        uso = " ".join([nome, "[OPÇÕES]", *partes])
        linhas += [f"## `{nome}`", "", _sem_markup(cmd.help or ""), "", f"```\n{uso}\n```", ""]
        if isinstance(cmd, TyperGroup):
            linhas += ["Subcomandos: " + ", ".join(f"`{nome} {s}`" for s in cmd.commands) + ".", ""]
        params = [p for p in cmd.params if p.name != "help"]
        if not params:
            continue
        linhas += ["| Argumento ou opção | Descrição | Padrão |", "|---|---|---|"]
        for p in params:
            if isinstance(p, TyperArgument):
                rotulo = f"`{p.human_readable_name}`"
            else:
                rotulo = ", ".join(f"`{o}`" for o in [*p.opts, *p.secondary_opts])
            if p.required:
                padrao = "**obrigatório**"
            elif p.default in (None, False, "") or callable(p.default):
                padrao = ""
            elif isinstance(p.default, Path):
                padrao = "pasta atual" if str(p.default) == "." else f"`{p.default}`"
            else:
                padrao = f"`{p.default}`"
            ajuda = _sem_markup(getattr(p, "help", "") or "")
            linhas.append(f"| {rotulo} | {_celula(ajuda)} | {padrao} |")
        linhas.append("")
    return "\n".join(linhas)


def pagina_modelo(titulo: str, intro: str, raiz: type[BaseModel]) -> str:
    linhas = [AVISO, f"# {titulo}", "", intro, ""]
    for m in _modelos_aninhados(raiz):
        linhas += _tabela(m, nivel=2 if m is raiz else 3)
    return "\n".join(linhas)


def pagina_contrato() -> str:
    linhas = [
        AVISO,
        "# Contrato de dados",
        "",
        inspect.cleandoc(contrato.__doc__ or ""),
        "",
        f"Versão atual: **{contrato.VERSAO_CONTRATO}**. Os JSON Schemas ficam em "
        "[`contrato/schema/`](https://github.com/felipelmc/mapa-da-ciencia/tree/main/contrato/schema), e um "
        "exemplo sintético completo em "
        "[`contrato/exemplo/dados/`](https://github.com/felipelmc/mapa-da-ciencia/tree/main/contrato/exemplo/dados).",
        "",
        "| Arquivo | Modelo |",
        "|---|---|",
    ]
    for nome, modelo in contrato.ARQUIVOS.items():
        arquivo = "detalhes/{00..3f}.json" if nome == "fragmento" else f"{nome}.json"
        linhas.append(f"| `{arquivo}` | [{modelo.__name__}](#{modelo.__name__.lower()}) |")
    linhas.append("")
    ja: set[type[BaseModel]] = set()
    for nome, modelo in contrato.ARQUIVOS.items():
        arquivo = "detalhes/{00..3f}.json" if nome == "fragmento" else f"{nome}.json"
        linhas += [f"## `{arquivo}`", ""]
        for m in _modelos_aninhados(modelo):
            if m not in ja:
                ja.add(m)
                linhas += _tabela(m, nivel=3)
    return "\n".join(linhas)


TAGS_API = {
    None: "Painel",
    "etapas": "Etapas e jobs",
    "projeto": "Projeto",
    "validação": "Validação",
}


def _tipo_openapi(esquema: dict) -> str:
    if "anyOf" in esquema:
        return " ou ".join(_tipo_openapi(e) for e in esquema["anyOf"] if e.get("type") != "null")
    if "$ref" in esquema:
        return esquema["$ref"].rsplit("/", 1)[-1]
    tipo = esquema.get("type", "objeto")
    if tipo == "array":
        return f"lista de {_tipo_openapi(esquema.get('items', {}))}"
    return {"string": "texto", "integer": "inteiro", "number": "número", "boolean": "booleano", "object": "objeto"}.get(
        tipo, tipo
    )


def pagina_api_http() -> str:
    """As rotas do painel local, a partir do OpenAPI do FastAPI (com um projeto vazio, numa pasta temporária)."""
    import tempfile

    from mapa_da_ciencia.llm.perfis import PERFIS
    from mapa_da_ciencia.projeto import Projeto
    from mapa_da_ciencia.servidor.app import criar_app

    with tempfile.TemporaryDirectory() as tmp:
        projeto = Projeto.criar(Path(tmp) / "p", modelo="vazio", perfil=PERFIS["leve"])
        app = criar_app(pasta_dados=projeto.saida / "dados", projeto=projeto, estatico=Path(tmp) / "x")
        esquema = app.openapi()
        app.state.jobs.fechar()
    componentes = esquema.get("components", {}).get("schemas", {})
    rotas = []
    for caminho, metodos in esquema["paths"].items():
        for metodo, op in metodos.items():
            tag = (op.get("tags") or [None])[0]
            rotas.append((list(TAGS_API).index(tag) if tag in TAGS_API else 99, caminho, metodo.upper(), op, tag))
    rotas.sort(key=lambda r: (r[0], r[1], r[2]))

    linhas = [
        AVISO,
        "# API HTTP do painel",
        "",
        "O `mapa painel` serve, além da interface e dos arquivos do contrato (`/dados/…`), uma API local em `/api/…`. "
        "Ela só existe no painel com um projeto aberto, só escuta em `127.0.0.1` e só responde a pedidos cujo `Host` "
        "seja desta máquina; as rotas de escrita recusam também um `Origin` de fora. O site publicado não tem API. "
        "Com o painel aberto, "
        "a documentação interativa fica em `/api/docs`.",
        "",
        "O progresso das etapas chega por *Server-Sent Events* (`GET /api/jobs/{job}/eventos`): cada evento tem "
        "`id:` (a sequência), `event:` (`estado`, `etapa`, `avanco`, `mensagem`, `resumo`, `erro` ou `fim`) e "
        "`data:` em JSON; quem reconecta manda `Last-Event-ID` e recebe só o que perdeu. Veja o guia "
        "[Usar o painel](../guias/painel.md).",
        "",
        "| Método | Rota | O que faz |",
        "|---|---|---|",
    ]
    for _, caminho, metodo, op, _tag in rotas:
        resumo = " ".join((op.get("description") or op.get("summary") or "").split())
        linhas.append(f"| `{metodo}` | `{caminho}` | {_celula(resumo)} |")
    atual = object()
    for _, caminho, metodo, op, tag in rotas:
        if tag != atual:
            atual = tag
            linhas += ["", f"## {TAGS_API.get(tag, tag)}"]
        linhas += ["", f"### `{metodo} {caminho}`", ""]
        if op.get("description"):
            linhas += [" ".join(_sem_markup(op["description"]).split()), ""]
        params = op.get("parameters") or []
        if params:
            linhas += ["| Parâmetro | Onde | Tipo | Obrigatório |", "|---|---|---|---|"]
            for prm in params:
                onde = {"path": "caminho", "query": "consulta", "header": "cabeçalho"}.get(prm["in"], prm["in"])
                obrig = "sim" if prm.get("required") else "não"
                linhas.append(f"| `{prm['name']}` | {onde} | {_tipo_openapi(prm.get('schema', {}))} | {obrig} |")
            linhas.append("")
        corpo = op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema")
        if corpo:
            nome = _tipo_openapi(corpo)
            campos = componentes.get(nome, {}).get("properties", {})
            if campos:
                linhas += [f"Corpo (JSON, `{nome}`):", "", "| Campo | Tipo |", "|---|---|"]
                linhas += [f"| `{c}` | {_tipo_openapi(e)} |" for c, e in campos.items()]
                linhas.append("")
            else:
                linhas += ["Corpo: um objeto JSON (ver a descrição).", ""]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(linhas))


def paginas() -> dict[str, str]:
    return {
        "referencia/cli.md": pagina_cli(),
        "referencia/configuracao.md": pagina_modelo(
            "Configuração do projeto (mapa.yaml)",
            "Cada projeto tem um `mapa.yaml` na raiz da pasta. `mapa novo` cria um já preenchido e comentado. "
            "Campos desconhecidos são recusados, para pegar erros de digitação. Veja também o guia "
            "[Criar um projeto](../guias/criar-projeto.md).",
            config.ConfigProjeto,
        ),
        "referencia/codebook.md": pagina_modelo(
            "Codebook (codebook.yaml)",
            "O codebook define as variáveis que o modelo preenche para cada resumo. Veja o guia "
            "[Escrever um codebook](../guias/codebook.md) para recomendações de redação.",
            config.Codebook,
        ),
        "referencia/contrato.md": pagina_contrato(),
        "desenvolvimento/api-http.md": pagina_api_http(),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--checar", action="store_true", help="não escreve; falha se alguma página estiver desatualizada")
    args = ap.parse_args()
    desatualizadas = []
    for nome, texto in paginas().items():
        arq = DESTINO / nome
        texto = texto.rstrip() + "\n"
        if args.checar:
            if not arq.exists() or arq.read_text(encoding="utf-8") != texto:
                desatualizadas.append(nome)
        else:
            arq.parent.mkdir(parents=True, exist_ok=True)
            arq.write_text(texto, encoding="utf-8")
    if desatualizadas:
        print("Referência desatualizada; rode `uv run python scripts/gerar_referencias.py`:", *desatualizadas)
        return 1
    print("Referência em dia." if args.checar else f"Páginas de referência escritas em {DESTINO.relative_to(RAIZ)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
