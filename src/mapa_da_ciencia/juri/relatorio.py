"""O relatório do júri (`validacao/juri.md`) e os números que vão para o contrato.

A ordem das tabelas segue a honestidade metodológica (ADR 0015):

1. **Resultado principal:** a referência contra cada membro, contra `juri-r1` (a votação) e contra `juri` (depois
   da deliberação), com o McNemar entre o `juri` e o modelo principal. Nenhum desses participantes é da família do
   supervisor, então a comparação é independente dele.
2. **Limite superior (circular):** a referência contra `juri-supervisor`. Quando o supervisor e o codificador de
   referência são da mesma família (os dois Claude, no piloto), esse número superestima a qualidade.
3. **Estágios:** quantas decisões foram unânimes, por maioria, na deliberação ou sem maioria.
4. **Concordância com a referência por estágio:** mostra se a unanimidade serve de sinal de confiança. Usa a
   decisão do júri sem o supervisor; a concordância com a escolha dele, nas decisões arbitradas, vem à parte e
   marcada "circular" quando for o caso.
5. **Deliberação:** quantas vezes cada membro mudou de voto, e se mudou na direção da referência ou para longe.
6. **Auditoria:** a taxa de erro entre as decisões unânimes, pelo supervisor, com o intervalo de Wilson.

A referência principal é o primeiro codificador humano com ao menos 50 documentos; na falta dele, o primeiro
codificador de referência.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..armazenamento import ler_tabela
from ..classificacao.resultado import valor_do_texto
from ..formatar import num
from ..projeto import Projeto
from ..validacao import amostra as va
from ..validacao.metricas import Validacao, calcular, circular, familias_dos_participantes
from .agregacao import chave
from .consolidar import ESTAGIOS, ResumoJuri, consolidar
from .deliberacao import ler_deliberacao
from .estado import pasta_dados
from .supervisor import Auditoria, auditoria

MINIMO_HUMANO = 50


def referencia_principal(v: Validacao) -> str | None:
    humanos = [p for p in v.participantes if p.tipo == "humano" and p.n >= MINIMO_HUMANO]
    if humanos:
        return humanos[0].nome
    refs = [p for p in v.participantes if p.tipo == "referencia"]
    return refs[0].nome if refs else None


@dataclass
class NumerosJuri:
    """O que o relatório mostra, também exportado para o painel (contrato: `Validacao.juri`)."""

    referencia: str | None
    membros: list[str]
    supervisor: str | None
    familia_supervisor: str | None
    documentos: int
    etapas: dict[str, dict[str, int]]
    virou: dict[str, int]
    concordancia_por_etapa: dict[str, dict[str, float | int]] = field(default_factory=dict)  # etapa → {n, acertos}
    concordancia_supervisor: dict[str, Any] | None = None  # {n, acertos, circular}: a escolha do supervisor
    deliberacao: dict[str, dict[str, int]] = field(default_factory=dict)  # membro → {mudou, para_referencia, …}
    auditoria: Auditoria | None = None
    minutos: dict[str, float] = field(default_factory=dict)
    nao_deliberados: int = 0  # em disputa, ainda sem deliberação (o relatório avisa)


def _respostas_da_referencia(projeto: Projeto, referencia: str) -> dict[tuple[str, str], str]:
    return {(c["doc"], c["variavel"]): c["valor"] for c in va.codificacoes(projeto, referencia)}


def numeros(projeto: Projeto, resumo: ResumoJuri, v: Validacao) -> NumerosJuri:
    codebook = projeto.codebook
    variaveis = {x.id: x for x in codebook.variaveis}
    ref = referencia_principal(v)
    cfg = projeto.config.juri
    n = NumerosJuri(
        referencia=ref,
        membros=resumo.membros,
        supervisor=resumo.supervisor,
        familia_supervisor=cfg.supervisor.familia_efetiva if resumo.supervisor else None,
        documentos=resumo.documentos,
        etapas=resumo.etapas,
        virou=resumo.virou,
        auditoria=auditoria(projeto),
        nao_deliberados=resumo.nao_deliberados,
    )
    pasta = pasta_dados(projeto, codebook.hash())
    decisoes = ler_tabela(pasta / "decisoes.parquet") if (pasta / "decisoes.parquet").exists() else []
    if ref:
        certo = _respostas_da_referencia(projeto, ref)

        def igual(doc: str, var: str, valor: str) -> bool | None:
            if (doc, var) not in certo:
                return None
            tipo = variaveis[var].tipo
            return chave(variaveis[var], valor_do_texto(valor, tipo)) == chave(
                variaveis[var], valor_do_texto(certo[(doc, var)], tipo)
            )

        for etapa in ESTAGIOS:
            dessa = [igual(d["doc"], d["variavel"], d["valor_juri"]) for d in decisoes if d["etapa"] == etapa]
            dessa = [x for x in dessa if x is not None]
            if dessa:
                n.concordancia_por_etapa[etapa] = {"n": len(dessa), "acertos": sum(dessa)}
        arbitradas = [igual(d["doc"], d["variavel"], d["valor_final"]) for d in decisoes if d["supervisor"]]
        arbitradas = [x for x in arbitradas if x is not None]
        if arbitradas:
            n.concordancia_supervisor = {
                "n": len(arbitradas),
                "acertos": sum(arbitradas),
                "circular": circular(familias_dos_participantes(projeto), ref, "juri-supervisor"),
            }
        votos_r1 = {}
        votos = ler_tabela(pasta / "votos.parquet") if (pasta / "votos.parquet").exists() else []
        for linha in votos:
            if linha["rodada"] == 1:
                votos_r1[(linha["doc"], linha["variavel"], linha["membro"])] = linha["valor"]
        for linha in votos:
            if linha["rodada"] != 2:
                continue
            m = n.deliberacao.setdefault(linha["membro"], {"votos": 0, "mudou": 0, "para_referencia": 0, "contra": 0})
            m["votos"] += 1
            if not linha["revisou"]:
                continue
            m["mudou"] += 1
            antes = igual(linha["doc"], linha["variavel"], votos_r1[(linha["doc"], linha["variavel"], linha["membro"])])
            depois = igual(linha["doc"], linha["variavel"], linha["valor"])
            if antes is False and depois:
                m["para_referencia"] += 1
            elif antes and depois is False:
                m["contra"] += 1
    delib = ler_deliberacao(projeto, codebook.hash())
    if delib:
        vistos = {}
        for linha in delib:
            vistos[(linha["doc"], linha["membro"])] = linha["segundos"] or 0.0
        n.minutos["deliberacao"] = round(sum(vistos.values()) / 60, 1)
    return n


def _k(v: Validacao, ref: str, outro: str, var: str) -> str:
    m = v.metrica(var, ref, outro)
    if m is None or m.kappa is None:
        return "—"
    texto = num(m.kappa, 2)
    if m.kappa_ic95:
        texto += f" ({num(m.kappa_ic95[0], 2)}–{num(m.kappa_ic95[1], 2)})"
    return texto


def gerar(projeto: Projeto) -> tuple[Path, NumerosJuri]:
    """Consolida o júri, calcula a validação e grava `validacao/juri.md`."""
    resumo = consolidar(projeto)
    v = calcular(projeto)
    nums = numeros(projeto, resumo, v)
    principal = v.modelo_principal
    ref = nums.referencia
    medidas = sorted({m.variavel for m in v.metricas if m.kappa is not None}, key=_ordem(projeto))
    linhas = [
        "# Júri de modelos locais",
        "",
        *(
            [
                f"**Atenção:** {resumo.nao_deliberados} decisão(ões) em disputa ainda não passaram pela deliberação "
                "(ela foi interrompida, ou houve uma votação nova). Rode `mapa juri deliberar` e gere o relatório de "
                "novo.",
                "",
            ]
            if resumo.nao_deliberados
            else []
        ),
        f"Membros: {', '.join(f'`{m}`' for m in nums.membros)}. Documentos: {nums.documentos} (a amostra de "
        f"validação). Supervisor: {nums.supervisor or 'ainda sem respostas'}"
        + (
            ""
            if not nums.supervisor
            else f" (família `{nums.familia_supervisor}`)"
            if nums.familia_supervisor
            else " (sem família de modelo declarada: tratado como uma pessoa)"
        )
        + ".",
        "",
    ]
    if ref:
        participantes = [*nums.membros, "juri-r1", "juri"]
        linhas += [
            f"## 1. Resultado principal: kappa contra `{ref}`",
            "",
            "Nenhum destes participantes passa pelo supervisor: a comparação não depende dele.",
            "",
            "| Variável | "
            + " | ".join(f"`{p}`" for p in participantes)
            + " | McNemar `juri` × principal (só o júri acerta × só o principal acerta) |",
            "|---|" + "---|" * (len(participantes) + 1),
        ]
        for var in medidas:
            mc = next(
                (
                    c
                    for c in v.comparacoes_modelos
                    if c.variavel == var and c.referencia == ref and {c.modelo_a, c.modelo_b} == {principal, "juri"}
                ),
                None,
            )
            if mc is None:
                mc_txt = "—"
            else:
                so_juri, so_principal = (mc.so_a, mc.so_b) if mc.modelo_a == "juri" else (mc.so_b, mc.so_a)
                p_txt = "p < 0,001" if mc.p < 0.001 else f"p = {num(mc.p, 3)}"
                mc_txt = f"{p_txt} ({so_juri} × {so_principal})"
            linhas.append(f"| `{var}` | " + " | ".join(_k(v, ref, p, var) for p in participantes) + f" | {mc_txt} |")
        linhas.append("")
        if any(p.nome == "juri-supervisor" for p in v.participantes):
            circ = any(m.circular for m in v.metricas if {m.referencia, m.comparado} == {ref, "juri-supervisor"})
            linhas += [
                "## 2. Limite superior: com o supervisor" + (" (circular)" if circ else ""),
                "",
                (
                    f"O supervisor e `{ref}` são da mesma família de modelo: a concordância abaixo **superestima** a "
                    "qualidade e não deve ser lida como uma medida independente."
                    if circ
                    else "O supervisor e a referência são de famílias diferentes."
                ),
                "",
                "| Variável | `juri` | `juri-supervisor` |",
                "|---|---|---|",
            ]
            for var in medidas:
                linhas.append(f"| `{var}` | {_k(v, ref, 'juri', var)} | {_k(v, ref, 'juri-supervisor', var)} |")
            linhas.append("")
    linhas += ["## 3. Estágios das decisões", "", "| Variável | " + " | ".join(ESTAGIOS) + " | mudou na deliberação |"]
    linhas.append("|---|" + "---|" * (len(ESTAGIOS) + 1))
    for var, etapas in nums.etapas.items():
        linhas.append(
            f"| `{var}` | " + " | ".join(str(etapas.get(e, 0)) for e in ESTAGIOS) + f" | {nums.virou.get(var, 0)} |"
        )
    linhas.append("")
    if nums.concordancia_por_etapa:
        linhas += [f"## 4. Concordância com `{ref}` por estágio", "", "| Estágio | n | Concordância |", "|---|---|---|"]
        for etapa, c in nums.concordancia_por_etapa.items():
            linhas.append(f"| {etapa} | {c['n']} | {num(100 * c['acertos'] / c['n'], 0)}% |")
        linhas += [
            "",
            "Com a decisão do júri sem o supervisor (no estágio `sem_maioria`, o voto do primeiro membro).",
            "",
        ]
        if (s := nums.concordancia_supervisor) is not None:
            linhas += [
                f"Nas {s['n']} decisões sem maioria que o supervisor arbitrou, a escolha dele concorda com `{ref}` em "
                f"{num(100 * s['acertos'] / s['n'], 0)}%"
                + (" (**circular**: os dois são da mesma família de modelo)." if s["circular"] else "."),
                "",
            ]
    if nums.deliberacao:
        linhas += [
            "## 5. Deliberação",
            "",
            "| Membro | Votos revistos | Mudou | Para a referência | Contra a referência |",
            "|---|---|---|---|---|",
        ]
        for membro, d in nums.deliberacao.items():
            linhas.append(f"| `{membro}` | {d['votos']} | {d['mudou']} | {d['para_referencia']} | {d['contra']} |")
        linhas.append("")
    a = nums.auditoria
    if a and a.n:
        linhas += [
            "## 6. Auditoria das decisões unânimes",
            "",
            f"O supervisor conferiu {a.n} decisões unânimes sorteadas: {a.erros} erradas "
            f"({num(100 * (a.taxa or 0), 1)}%; IC 95% de Wilson: {num(100 * a.ic95[0], 1)}–{num(100 * a.ic95[1], 1)}%)."
            if a.ic95
            else "",
            "",
        ]
    destino = projeto.raiz / "validacao" / "juri.md"
    destino.parent.mkdir(exist_ok=True)
    destino.write_text("\n".join(linhas).rstrip() + "\n", encoding="utf-8")
    return destino, nums


def _ordem(projeto: Projeto):
    ordem = {v.id: i for i, v in enumerate(projeto.codebook.variaveis)}
    return lambda var: (ordem.get(var.split(":", 1)[0], 99), var)


def como_dict(n: NumerosJuri) -> dict[str, Any]:
    a = n.auditoria
    return {
        "referencia": n.referencia,
        "membros": n.membros,
        "supervisor": n.supervisor,
        "familia_supervisor": n.familia_supervisor,
        "documentos": n.documentos,
        "etapas": n.etapas,
        "virou": n.virou,
        "concordancia_por_etapa": n.concordancia_por_etapa,
        "concordancia_supervisor": n.concordancia_supervisor,
        "deliberacao": n.deliberacao,
        "auditoria": None
        if not a or not a.n
        else {"n": a.n, "erros": a.erros, "taxa": a.taxa, "ic95": a.ic95, "por_variavel": a.por_variavel},
    }
