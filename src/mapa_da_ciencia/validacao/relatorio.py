"""O relatório da validação, em `validacao/` na pasta do projeto:

- `relatorio.md`: participantes, concordância por variável e par, precisão e revocação por classe, matrizes de
  confusão, comparação entre modelos, evidência literal e as divergências com o modelo principal;
- `tabelas.tex`: as tabelas de concordância em LaTeX (`booktabs`), com vírgula decimal, prontas para um artigo;
- `metricas.json`: as mesmas métricas em JSON, para outras análises.

O relatório e o JSON trazem as respostas de cada pessoa nas divergências: a pasta fica fora do git (`.gitignore` do
projeto).

Um codificador de referência nunca é chamado de humano: o relatório diz o tipo de cada participante.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from .. import __version__
from ..formatar import num
from ..projeto import Projeto
from .amostra import ESTRATOS, PASTA_EXPORTACAO
from .metricas import Metrica, Validacao, calcular

TIPOS = {"humano": "pessoa", "referencia": "referência (não humano)", "modelo": "modelo local"}


def _f(valor: float | None, casas: int = 2) -> str:
    return "—" if valor is None else num(valor, casas)


def _pct(valor: float | None) -> str:
    return "—" if valor is None else f"{num(100 * valor, 0)}%"


def _kappa(m: Metrica) -> str:
    if m.kappa is None:
        return "—"
    ic = f" [{_f(m.kappa_ic95[0])}; {_f(m.kappa_ic95[1])}]" if m.kappa_ic95 else ""
    return _f(m.kappa) + ic


def _pares(v: Validacao) -> list[tuple[str, str]]:
    return list(dict.fromkeys((m.referencia, m.comparado) for m in v.metricas))


def _tabela_md(linhas: list[list[str]], cabecalho: list[str]) -> str:
    saida = ["| " + " | ".join(cabecalho) + " |", "|" + "---|" * len(cabecalho)]
    saida += ["| " + " | ".join(linha) + " |" for linha in linhas]
    return "\n".join(saida)


def markdown(v: Validacao, *, projeto: str) -> str:
    tipos = {p.nome: p.tipo for p in v.participantes}
    partes = [
        f"# Validação da classificação: {projeto}",
        "",
        f"Gerado em {datetime.now(UTC):%Y-%m-%d %H:%M} UTC pelo mapa-da-ciencia {__version__}. Codebook "
        f"**{v.codebook}** (hash `{v.hash_codebook}`). Amostra de {num(v.amostra['n'], 0)} documentos com resumo, "
        f"estratificada por {ESTRATOS[v.amostra['estratificar_por']]}, semente {v.amostra['semente']}.",
        "",
        "## Participantes",
        "",
        _tabela_md(
            [[f"`{p.nome}`", TIPOS[p.tipo], num(p.n, 0)] for p in v.participantes],
            ["Participante", "Tipo", "Documentos da amostra"],
        ),
    ]
    referencias = [p.nome for p in v.participantes if p.tipo == "referencia"]
    if referencias:
        nomes = ", ".join(f"`{n}`" for n in referencias)
        partes += [
            "",
            f"> **Atenção:** {nomes} {'é um codificador' if len(referencias) == 1 else 'são codificadores'} de "
            "referência, não humano. A concordância com ele mede quanto o modelo local reproduz essa leitura, "
            "não se o modelo acerta segundo uma pessoa.",
        ]
    if not v.metricas:
        partes += ["", "Ainda não há dois participantes com respostas na amostra: nada a comparar."]
        return "\n".join(partes) + "\n"

    partes += [
        "",
        "## Concordância por variável",
        "",
        "Kappa de Cohen com intervalo de 95% por *bootstrap* (1.000 reamostras dos documentos). PABAK: kappa "
        "ajustado para prevalência e viés. Alfa: Krippendorff, nominal. Nas variáveis de múltipla escolha, cada "
        "categoria é uma variável sim/não; nas de texto, só a concordância.",
    ]
    for ref, comp in _pares(v):
        linhas = [
            [f"`{m.variavel}`", num(m.n, 0), _pct(m.concordancia), _kappa(m), _f(m.pabak), _f(m.alfa)]
            for m in v.metricas
            if (m.referencia, m.comparado) == (ref, comp)
        ]
        partes += [
            "",
            f"### `{ref}` × `{comp}`",
            "",
            f"{TIPOS[tipos[ref]].capitalize()} × {TIPOS[tipos[comp]]}.",
            "",
            _tabela_md(linhas, ["Variável", "n", "Concordância", "Kappa [IC 95%]", "PABAK", "Alfa"]),
        ]

    principais = [(ref, comp) for ref, comp in _pares(v) if comp == v.modelo_principal and tipos[ref] != "modelo"]
    for ref, comp in principais:
        partes += [
            "",
            f"## Por classe: `{ref}` (referência) × `{comp}`",
            "",
            "Precisão: das vezes em que o modelo deu a categoria, quantas a referência também deu. Revocação: das "
            "vezes em que a referência deu a categoria, quantas o modelo encontrou.",
        ]
        for m in (m for m in v.metricas if (m.referencia, m.comparado) == (ref, comp) and m.rotulos):
            classes = [c for c in m.por_classe if c.suporte or any(row[m.rotulos.index(c.rotulo)] for row in m.matriz)]
            partes += [
                "",
                f"### `{m.variavel}`",
                "",
                _tabela_md(
                    [[f"`{c.rotulo}`", num(c.suporte, 0), _f(c.precisao), _f(c.revocacao), _f(c.f1)] for c in classes],
                    ["Categoria", "Na referência", "Precisão", "Revocação", "F1"],
                ),
                "",
                "Matriz de confusão (linhas: referência; colunas: modelo):",
                "",
            ]
            usados = [i for i, r in enumerate(m.rotulos) if any(m.matriz[i]) or any(row[i] for row in m.matriz)]
            partes.append(
                _tabela_md(
                    [
                        [f"`{m.rotulos[i]}`"] + [str(m.matriz[i][j]) if m.matriz[i][j] else "·" for j in usados]
                        for i in usados
                    ],
                    [""] + [f"`{m.rotulos[j]}`" for j in usados],
                )
            )

    if v.comparacoes_modelos:
        partes += [
            "",
            "## Comparação entre modelos",
            "",
            "Teste de McNemar exato: só os documentos em que um modelo acertou e o outro errou, contra a mesma "
            "referência. Com muitas variáveis, alguma diferença com p < 0,05 aparece por acaso.",
            "",
            _tabela_md(
                [
                    [
                        f"`{c.variavel}`",
                        f"`{c.referencia}`",
                        f"`{c.modelo_a}` × `{c.modelo_b}`",
                        num(c.n, 0),
                        f"{num(c.acertos_a, 0)} × {num(c.acertos_b, 0)}",
                        f"{num(c.so_a, 0)} × {num(c.so_b, 0)}",
                        num(c.p, 3),
                    ]
                    for c in v.comparacoes_modelos
                ],
                ["Variável", "Referência", "Modelos", "n", "Acertos", "Só um acertou", "p"],
            ),
        ]
    if v.evidencia_literal:
        partes += [
            "",
            "## Evidência literal na amostra",
            "",
            _tabela_md(
                [[f"`{m}`", _pct(x)] for m, x in v.evidencia_literal.items()],
                ["Modelo", "Evidências copiadas literalmente do resumo"],
            ),
        ]
    if v.divergencias:
        partes += [
            "",
            f"## Divergências com `{v.modelo_principal}`",
            "",
            f"{num(len(v.divergencias), 0)} respostas diferentes entre os codificadores e o modelo principal. "
            "Leia-as antes de mudar o codebook: muitas revelam uma definição ambígua, e não um erro do modelo.",
        ]
        for var in dict.fromkeys(d.variavel for d in v.divergencias):
            dessa = [d for d in v.divergencias if d.variavel == var]
            partes += ["", f"### `{var}` ({num(len(dessa), 0)})", ""]
            for d in dessa:
                incerto = " (marcado como incerto)" if d.incerto else ""
                linha = (
                    f"- `{d.doc}`: `{d.codificador}` deu `{d.valor_codificador}`{incerto}; o modelo, `{d.valor_modelo}`"
                )
                if d.evidencia_modelo:
                    linha += f", citando «{d.evidencia_modelo}» ({d.status_evidencia})"
                partes.append(linha + ".")
    return "\n".join(partes) + "\n"


def _tex(texto: str) -> str:
    for a, b in [("\\", r"\textbackslash{}"), ("_", r"\_"), ("%", r"\%"), ("&", r"\&"), ("#", r"\#"), ("$", r"\$")]:
        texto = texto.replace(a, b)
    return texto


def latex(v: Validacao) -> str:
    partes = [
        "% Tabelas de concordância geradas pelo mapa-da-ciencia. Requer \\usepackage{booktabs}.",
        f"% Codebook {_tex(v.codebook)} (hash {v.hash_codebook}); amostra de {v.amostra['n']} documentos.",
    ]
    tipos = {p.nome: p.tipo for p in v.participantes}
    for ref, comp in _pares(v):
        rotulo = "tab:concordancia-" + re.sub(r"[^a-z0-9]+", "-", f"{ref}-{comp}".lower()).strip("-")
        partes += [
            "",
            r"\begin{table}[htbp]",
            r"  \centering",
            f"  \\caption{{Concordância entre {_tex(ref)} ({TIPOS[tipos[ref]]}) e {_tex(comp)} "
            f"({TIPOS[tipos[comp]]}), por variável}}",
            f"  \\label{{{rotulo}}}",
            r"  \begin{tabular}{lrrlrr}",
            r"    \toprule",
            r"    Variável & $n$ & Concordância & $\kappa$ [IC 95\%] & PABAK & $\alpha$ \\",
            r"    \midrule",
        ]
        for m in (m for m in v.metricas if (m.referencia, m.comparado) == (ref, comp)):
            conc = "---" if m.concordancia is None else f"{num(100 * m.concordancia, 0)}\\%"
            kappa = _kappa(m).replace("—", "---")
            partes.append(
                f"    {_tex(m.variavel)} & {m.n} & {conc} & {kappa} & {_f(m.pabak).replace('—', '---')} & "
                f"{_f(m.alfa).replace('—', '---')} \\\\"
            )
        partes += [r"    \bottomrule", r"  \end{tabular}", r"\end{table}"]
    return "\n".join(partes) + "\n"


def gerar(projeto: Projeto) -> tuple[Validacao, dict[str, Path]]:
    """Calcula as métricas e grava `relatorio.md`, `tabelas.tex` e `metricas.json` em `validacao/`."""
    v = calcular(projeto)
    pasta = projeto.raiz / PASTA_EXPORTACAO
    pasta.mkdir(exist_ok=True)
    arquivos = {"markdown": pasta / "relatorio.md", "latex": pasta / "tabelas.tex", "json": pasta / "metricas.json"}
    arquivos["markdown"].write_text(markdown(v, projeto=projeto.config.titulo), encoding="utf-8")
    arquivos["latex"].write_text(latex(v), encoding="utf-8")
    arquivos["json"].write_text(json.dumps(asdict(v), ensure_ascii=False, indent=1), encoding="utf-8")
    return v, arquivos
