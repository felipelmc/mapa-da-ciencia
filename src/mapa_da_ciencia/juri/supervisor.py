"""O supervisor do júri: arbitragem do que ficou sem maioria e auditoria de uma amostra das decisões unânimes.

**Protocolo por arquivos** (`mapa juri exportar-pedidos` / `importar-respostas`): os pedidos vão para
`<projeto>/juri/` em lotes JSONL (`arbitragem-NN.jsonl`, `auditoria-NN.jsonl`), com as instruções em
`instrucoes-supervisor.md` e o índice dos pedidos em `pedidos.json`. Quem supervisiona (uma pessoa, uma sessão do
Claude, outro modelo) devolve um `*.respostas.jsonl` por lote. Os pedidos não dizem que modelo deu cada candidato.

**Importação:** cada resposta é conferida: o pedido existe e ainda vale (os candidatos não mudaram), a escolha é um
dos candidatos (ou, na auditoria, o valor sugerido é uma categoria da variável), e a evidência está no texto (uma
evidência `ausente` recusa a resposta, a menos que ela seja "sem informação"). As recusas são contadas e listadas;
rodar `exportar-pedidos` de novo pede só o que falta.

**Auditoria:** `juri.auditoria` itens (documento × variável) sorteados uma vez, com a semente da validação, entre as
decisões unânimes das variáveis categóricas, booleanas e de múltipla escolha. A taxa de erro sai com o intervalo de
Wilson de 95%.
"""

from __future__ import annotations

import json
import math
import random
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..classificacao.codebook import EVIDENCIA_MAXIMA, conferir_valor, sem_informacao
from ..classificacao.evidencia import conferir
from ..classificacao.resultado import valor_como_texto, valor_do_texto
from ..config import ErroConfig
from ..projeto import Projeto
from .consolidar import DecisaoFinal, chave_pedido, consolidar, decidir, respostas_do_supervisor
from .deliberacao import DELIBERAVEIS
from .estado import conectar, pasta_pedidos
from .prompt import INSTRUCOES_SUPERVISOR, descrever_variavel
from .votacao import textos_da_amostra

JUSTIFICATIVA_MAXIMA = 300


def wilson(erros: int, n: int, z: float = 1.959964) -> tuple[float, float] | None:
    """Intervalo de Wilson de 95% para uma proporção."""
    if n == 0:
        return None
    p = erros / n
    centro = (p + z * z / (2 * n)) / (1 + z * z / n)
    margem = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centro - margem), min(1.0, centro + margem)


def sorteio_auditoria(projeto: Projeto, decisoes: list[DecisaoFinal]) -> list[tuple[str, str]]:
    """Os itens da auditoria: sorteados na primeira vez e guardados; depois, sempre os mesmos."""
    n = projeto.config.juri.auditoria
    hash_cb = projeto.codebook.hash()
    with conectar(projeto) as con:
        guardados = con.execute(
            "SELECT doc, variavel FROM juri_auditoria WHERE hash_codebook = ? ORDER BY ordem", (hash_cb,)
        ).fetchall()
        if guardados or n == 0:
            return [(r["doc"], r["variavel"]) for r in guardados]
        unanimes = sorted(
            (d.doc, d.variavel.id) for d in decisoes if d.etapa == "unanime" and d.variavel.tipo in DELIBERAVEIS
        )
        itens = random.Random(projeto.config.validacao.semente).sample(unanimes, min(n, len(unanimes)))
        con.executemany(
            "INSERT INTO juri_auditoria (hash_codebook, doc, variavel, ordem) VALUES (?, ?, ?, ?)",
            [(hash_cb, doc, var, i) for i, (doc, var) in enumerate(itens)],
        )
    return itens


def _id(tarefa: str, doc: str, variavel: str) -> str:
    return f"{tarefa[:3]}:{doc}:{variavel}"


@dataclass
class Pedidos:
    arbitragem: int
    auditoria: int
    arquivos: list[Path] = field(default_factory=list)

    def __str__(self) -> str:
        if not self.arquivos:
            return "Nada a pedir ao supervisor: todas as arbitragens e auditorias já têm resposta."
        return (
            f"{self.arbitragem} pedido(s) de arbitragem e {self.auditoria} de auditoria em "
            f"{len(self.arquivos)} lote(s), na pasta {self.arquivos[0].parent}."
        )


def pedidos(projeto: Projeto, *, todos: bool = False) -> tuple[list[dict], list[dict]]:
    """Os pedidos de arbitragem e de auditoria (só os que ainda não têm resposta válida, salvo `todos`)."""
    codebook = projeto.codebook
    hash_cb = codebook.hash()
    textos = {t.doc: t for t in textos_da_amostra(projeto)} | {}
    decisoes = decidir(projeto)
    por_item = {(d.doc, d.variavel.id): d for d in decisoes}
    arbitragem, auditoria = [], []
    for d in decisoes:
        if d.etapa != "sem_maioria" or d.variavel.tipo not in DELIBERAVEIS or (d.supervisor and not todos):
            continue
        texto = textos.get(d.doc)
        if texto is None:
            continue
        candidatos = [
            {
                "n": i,
                "valor": c.valor,
                "evidencia": c.voto.evidencia,
                "evidencia_no_texto": c.voto.status != "ausente",
            }
            for i, c in enumerate(d.juri.candidatos, 1)
        ]
        arbitragem.append(
            {
                "id": _id("arbitragem", d.doc, d.variavel.id),
                "tarefa": "arbitragem",
                "titulo": texto.titulo or "",
                "resumo": texto.resumo,
                "variavel": descrever_variavel(codebook, d.variavel),
                "candidatos": candidatos,
                "_doc": d.doc,
                "_chave": d.chave_pedido,
            }
        )
    respondidas = respostas_do_supervisor(projeto, hash_cb, "auditoria")
    for doc, var in sorteio_auditoria(projeto, decisoes):
        d = por_item.get((doc, var))
        texto = textos.get(doc)
        if d is None or texto is None:
            continue
        chave = chave_pedido(doc, var, d.candidatos)
        if not todos and (r := respondidas.get((doc, var))) and r["chave_pedido"] == chave:
            continue
        auditoria.append(
            {
                "id": _id("auditoria", doc, var),
                "tarefa": "auditoria",
                "titulo": texto.titulo or "",
                "resumo": texto.resumo,
                "variavel": descrever_variavel(codebook, d.variavel),
                "decisao": {"valor": d.valor_juri, "evidencia": d.voto_juri.evidencia},
                "_doc": doc,
                "_chave": chave,
            }
        )
    return arbitragem, auditoria


def exportar_pedidos(projeto: Projeto, *, lote: int = 20, todos: bool = False) -> Pedidos:
    """Grava os pedidos em lotes JSONL e as instruções, para um supervisor externo."""
    consolidar(projeto)
    arbitragem, auditoria = pedidos(projeto, todos=todos)
    pasta = pasta_pedidos(projeto)
    pasta.mkdir(exist_ok=True)
    for antigo in list(pasta.glob("arbitragem-*.jsonl")) + list(pasta.glob("auditoria-*.jsonl")):
        if not antigo.name.endswith(".respostas.jsonl"):
            antigo.unlink()
    (pasta / "instrucoes-supervisor.md").write_text(INSTRUCOES_SUPERVISOR, encoding="utf-8")
    indice = {}
    arquivos = []
    for nome, itens in (("arbitragem", arbitragem), ("auditoria", auditoria)):
        for i in range(0, len(itens), lote):
            arquivo = pasta / f"{nome}-{i // lote + 1:02d}.jsonl"
            with arquivo.open("w", encoding="utf-8") as f:
                for p in itens[i : i + lote]:
                    indice[p["id"]] = {"tarefa": p["tarefa"], "doc": p["_doc"], "chave": p["_chave"]}
                    publico = {k: v for k, v in p.items() if not k.startswith("_")}
                    f.write(json.dumps(publico, ensure_ascii=False) + "\n")
            arquivos.append(arquivo)
    (pasta / "pedidos.json").write_text(json.dumps(indice, ensure_ascii=False, indent=1), encoding="utf-8")
    return Pedidos(len(arbitragem), len(auditoria), arquivos)


@dataclass
class ResumoRespostas:
    aceitas: int = 0
    recusadas: list[str] = field(default_factory=list)  # "id: motivo"

    def __str__(self) -> str:
        texto = f"{self.aceitas} resposta(s) do supervisor aceitas"
        if self.recusadas:
            texto += f", {len(self.recusadas)} recusada(s) (por exemplo: {'; '.join(self.recusadas[:3])})"
        return texto + "."


def _ler_respostas(arquivos: Iterable[Path]) -> list[dict[str, Any]]:
    saida = []
    for arquivo in arquivos:
        for n, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), 1):
            if not linha.strip():
                continue
            try:
                saida.append(json.loads(linha))
            except json.JSONDecodeError as e:
                raise ErroConfig(f"{arquivo.name}, linha {n}: não é um JSON válido ({e.msg}).") from e
    return saida


def importar_respostas(
    projeto: Projeto, arquivos: list[Path], *, supervisor: str | None = None, origem: str = "arquivo"
) -> ResumoRespostas:
    """Confere e guarda as respostas do supervisor, e consolida o júri de novo."""
    codebook = projeto.codebook
    hash_cb = codebook.hash()
    nome = supervisor or projeto.config.juri.supervisor.nome
    indice_arquivo = pasta_pedidos(projeto) / "pedidos.json"
    if not indice_arquivo.exists():
        raise ErroConfig("Não há pedidos exportados. Rode `mapa juri exportar-pedidos` antes.")
    indice = json.loads(indice_arquivo.read_text(encoding="utf-8"))
    variaveis = {v.id: v for v in codebook.variaveis}
    textos = {t.doc: t for t in textos_da_amostra(projeto)}
    decisoes = {(d.doc, d.variavel.id): d for d in decidir(projeto)}
    resumo = ResumoRespostas()
    agora = datetime.now(UTC).isoformat(timespec="seconds")
    linhas = []
    for r in _ler_respostas(arquivos):
        rid = str(r.get("id", ""))
        pedido = indice.get(rid)
        if pedido is None:
            resumo.recusadas.append(f"{rid or '(sem id)'}: pedido desconhecido")
            continue
        tarefa, doc = pedido["tarefa"], pedido["doc"]
        var_id = rid.rsplit(":", 1)[-1]
        v, d, texto = variaveis.get(var_id), decisoes.get((doc, var_id)), textos.get(doc)
        if v is None or d is None or texto is None:
            resumo.recusadas.append(f"{rid}: o documento ou a variável não estão mais no júri")
            continue
        if pedido["chave"] != chave_pedido(doc, var_id, d.candidatos):
            resumo.recusadas.append(f"{rid}: os candidatos mudaram depois do pedido; exporte de novo")
            continue
        evidencia = " ".join(str(r.get("evidencia") or "").split())[:EVIDENCIA_MAXIMA]
        justificativa = " ".join(str(r.get("justificativa") or "").split())[:JUSTIFICATIVA_MAXIMA]
        if tarefa == "arbitragem":
            escolha = r.get("escolha")
            if not isinstance(escolha, int) or not 1 <= escolha <= len(d.juri.candidatos):
                resumo.recusadas.append(f"{rid}: `escolha` precisa ser um dos candidatos (1 a {len(d.candidatos)})")
                continue
            valor = d.juri.candidatos[escolha - 1].valor
            linha = {"escolha": escolha, "valor": valor_como_texto(valor), "correto": None, "valor_sugerido": None}
            referencia = valor
        else:
            correto = r.get("correto")
            if not isinstance(correto, bool):
                resumo.recusadas.append(f"{rid}: `correto` precisa ser true ou false")
                continue
            sugerido = r.get("valor_sugerido")
            if not correto:
                if sugerido is None:
                    resumo.recusadas.append(f"{rid}: sem `valor_sugerido` numa decisão marcada como errada")
                    continue
                sugerido, problema = conferir_valor(v, sugerido)
                if problema:
                    resumo.recusadas.append(f"{rid}: `valor_sugerido` inválido ({problema})")
                    continue
            linha = {
                "escolha": None,
                "valor": None,
                "correto": int(correto),
                "valor_sugerido": None if correto else valor_como_texto(sugerido),
            }
            referencia = d.valor_juri if correto else sugerido
        c = conferir(evidencia, texto.resumo, texto.titulo, sem_informacao=sem_informacao(v, referencia))
        if c.status == "ausente":
            resumo.recusadas.append(f"{rid}: a evidência não está no título nem no resumo")
            continue
        linhas.append(
            (
                hash_cb,
                tarefa,
                doc,
                var_id,
                nome,
                origem,
                pedido["chave"],
                linha["escolha"],
                linha["valor"],
                linha["correto"],
                linha["valor_sugerido"],
                evidencia,
                c.status,
                justificativa,
                int(bool(r.get("nenhum_adequado"))) if tarefa == "arbitragem" else None,
                r.get("custo_usd"),
                agora,
            )
        )
        resumo.aceitas += 1
    with conectar(projeto) as con:
        con.executemany(
            "INSERT OR REPLACE INTO juri_supervisor (hash_codebook, tarefa, doc, variavel, supervisor, origem, "
            "chave_pedido, escolha, valor, correto, valor_sugerido, evidencia, status, justificativa, "
            "nenhum_adequado, custo_usd, atualizado) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            linhas,
        )
    consolidar(projeto)
    return resumo


@dataclass
class Auditoria:
    n: int
    erros: int
    taxa: float | None
    ic95: tuple[float, float] | None
    por_variavel: dict[str, tuple[int, int]]  # variável → (erros, n)


def auditoria(projeto: Projeto) -> Auditoria:
    """A taxa de erro entre as decisões unânimes auditadas pelo supervisor."""
    hash_cb = projeto.codebook.hash()
    decisoes = {(d.doc, d.variavel.id): d for d in decidir(projeto)}
    respostas = respostas_do_supervisor(projeto, hash_cb, "auditoria")
    validas = [
        r
        for (doc, var), r in respostas.items()
        if (d := decisoes.get((doc, var))) and r["chave_pedido"] == chave_pedido(doc, var, d.candidatos)
    ]
    por_variavel: dict[str, tuple[int, int]] = {}
    for r in validas:
        e, n = por_variavel.get(r["variavel"], (0, 0))
        por_variavel[r["variavel"]] = (e + (1 - r["correto"]), n + 1)
    n = len(validas)
    erros = sum(1 - r["correto"] for r in validas)
    return Auditoria(n, erros, erros / n if n else None, wilson(erros, n), por_variavel)


def valor_sugerido(texto: str | None, tipo: str) -> Any:
    return None if texto is None else valor_do_texto(texto, tipo)


# ---------------------------------------------------------------- supervisor pela API
@dataclass
class ResumoSupervisao:
    pedidos: int
    estimativa_usd: float
    modelo: str
    feito: bool = False
    respondidos: int = 0
    gasto_usd: float = 0.0
    parou_no_limite: bool = False
    falhas: list[str] = field(default_factory=list)
    importacao: ResumoRespostas | None = None

    def __str__(self) -> str:
        if not self.feito:
            return (
                f"{self.pedidos} pedido(s) ao supervisor ({self.modelo}), custo estimado de US$ "
                f"{self.estimativa_usd:.2f}."
            )
        texto = (
            f"{self.respondidos} de {self.pedidos} pedido(s) respondidos por {self.modelo}, US$ {self.gasto_usd:.2f}"
        )
        if self.parou_no_limite:
            texto += " (parou no limite de gasto)"
        return texto + "."


def esquema_da_resposta(pedido: dict[str, Any], variavel: Any) -> dict[str, Any]:
    """O JSON Schema da resposta do supervisor a um pedido (o mesmo formato do protocolo por arquivos)."""
    comum = {"evidencia": {"type": "string"}, "justificativa": {"type": "string"}}
    if pedido["tarefa"] == "arbitragem":
        propriedades = {
            "escolha": {"type": "integer", "enum": [c["n"] for c in pedido["candidatos"]]},
            **comum,
            "nenhum_adequado": {"type": "boolean"},
        }
    else:
        categorias = [c.valor for c in variavel.categorias]
        sugerido: dict[str, Any]
        if variavel.tipo == "categorica":
            sugerido = {"type": "string", "enum": [*categorias, ""]}
        elif variavel.tipo == "booleana":
            sugerido = {"type": "string", "enum": ["true", "false", ""]}
        elif variavel.tipo == "multipla":
            sugerido = {"type": "array", "items": {"type": "string", "enum": categorias}}
        else:
            sugerido = {"type": "string"}
        propriedades = {"correto": {"type": "boolean"}, "valor_sugerido": sugerido, **comum}
    return {"type": "object", "properties": propriedades, "required": list(propriedades), "additionalProperties": False}


def _normalizar_auditoria(resposta: dict[str, Any], variavel: Any) -> dict[str, Any]:
    """No esquema da API o valor sugerido nunca é nulo: "" (ou lista vazia) quando a decisão está correta."""
    sugerido = resposta.get("valor_sugerido")
    if resposta.get("correto") or sugerido in ("", [], None):
        resposta["valor_sugerido"] = None
    elif variavel.tipo == "booleana":
        resposta["valor_sugerido"] = sugerido == "true"
    return resposta


def supervisionar(
    projeto: Projeto, *, limite_gasto: float | None = None, confirmar: bool = False, cliente: Any = None
) -> ResumoSupervisao:
    """O supervisor pela API da Anthropic. Sem `confirmar`, só estima (nada sai da máquina); com ele, envia os
    pedidos, para antes de passar do limite de gasto e importa as respostas pelo mesmo caminho do protocolo por
    arquivos (a mesma conferência de candidatos e evidências)."""
    from ..llm.anthropic import Anthropic, ErroOrcamento, estimar_custo
    from ..llm.base import ErroProvedor
    from ..rede import variavel as variavel_do_ambiente

    cfg = projeto.config.juri.supervisor
    if cfg.modo != "api":
        raise ErroConfig(
            "O supervisor deste projeto trabalha por arquivos (`juri.supervisor.modo: arquivo`). Para usar a API da "
            "Anthropic, ponha `modo: api` e `enviar_textos: true` no mapa.yaml; ou use `mapa juri exportar-pedidos`."
        )
    if not cfg.enviar_textos:
        raise ErroConfig(
            "O supervisor pela API envia títulos e resumos à Anthropic. Para consentir, ponha "
            "`juri.supervisor.enviar_textos: true` no mapa.yaml."
        )
    limite = cfg.limite_gasto_usd if limite_gasto is None else limite_gasto
    exportados = exportar_pedidos(projeto, lote=10**6)
    lista = [json.loads(x) for arquivo in exportados.arquivos for x in arquivo.read_text(encoding="utf-8").splitlines()]
    textos = [json.dumps(p, ensure_ascii=False) for p in lista]
    estimativa = estimar_custo(cfg.modelo, INSTRUCOES_SUPERVISOR, textos) if lista else 0.0
    resumo = ResumoSupervisao(len(lista), round(estimativa, 4), cfg.modelo)
    if estimativa > limite:
        raise ErroConfig(
            f"O custo estimado (US$ {estimativa:.2f}) passa do limite de gasto (US$ {limite:.2f}). Aumente "
            "`--limite-gasto` ou `juri.supervisor.limite_gasto_usd`."
        )
    if not confirmar or not lista:
        return resumo
    gerador = Anthropic(
        cfg.modelo, cfg.esforco, limite, chave=variavel_do_ambiente("ANTHROPIC_API_KEY", projeto.raiz), cliente=cliente
    )
    variaveis = {v.id: v for v in projeto.codebook.variaveis}
    respostas = []
    for pedido, texto in zip(lista, textos, strict=True):
        v = variaveis[pedido["variavel"]["id"]]
        antes = gerador.custo_usd()
        try:
            r = gerador.gerar_estruturado(INSTRUCOES_SUPERVISOR, texto, esquema_da_resposta(pedido, v))
        except ErroOrcamento:
            resumo.parou_no_limite = True
            break
        except ErroProvedor as e:
            resumo.falhas.append(f"{pedido['id']}: {e}")
            continue
        if pedido["tarefa"] == "auditoria":
            r = _normalizar_auditoria(r, v)
        respostas.append({**r, "id": pedido["id"], "custo_usd": round(gerador.custo_usd() - antes, 6)})
    resumo.feito = True
    resumo.respondidos = len(respostas)
    resumo.gasto_usd = round(gerador.custo_usd(), 4)
    if respostas:
        carimbo = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        arquivo = pasta_pedidos(projeto) / f"api-{carimbo}.respostas.jsonl"
        arquivo.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in respostas) + "\n", encoding="utf-8")
        resumo.importacao = importar_respostas(projeto, [arquivo], supervisor=cfg.nome, origem="api")
    return resumo
