"""Gerador de dados de exemplo do contrato: **sintéticos e fictícios**, mas plausíveis.

Serve para desenvolver e testar o frontend sem rodar o pipeline, para a demonstração
`mapa painel --exemplo` e para oficinas. Títulos, autores, resumos e afiliações são
inventados; as revistas e instituições são reais só para o exemplo parecer familiar.
É determinístico: a mesma semente gera exatamente os mesmos arquivos.
"""

from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import resources

import yaml

from mapa_da_ciencia.config import Codebook
from mapa_da_ciencia.contrato import modelos as m
from mapa_da_ciencia.contrato.classificacao import codebook_contrato
from mapa_da_ciencia.contrato.exportar import agregados_geograficos, tendencia_contrato
from mapa_da_ciencia.topicos.paleta import cores_macrotemas, proxima_cor

ANOS = list(range(2010, 2026))

REVISTAS = [
    ("rbcpol", "0103-3352", "Revista Brasileira de Ciência Política"),
    ("dados", "0011-5258", "Dados"),
    ("op", "0104-6276", "Opinião Pública"),
    ("ln", "0102-6445", "Lua Nova"),
    ("rsocp", "0104-4478", "Revista de Sociologia e Política"),
    ("bpsr", "1981-3821", "Brazilian Political Science Review"),
    ("cint", "0102-8529", "Contexto Internacional"),
    ("rbpi", "0034-7329", "Revista Brasileira de Política Internacional"),
    ("nec", "0101-3300", "Novos Estudos CEBRAP"),
    ("rbcsoc", "0102-6909", "Revista Brasileira de Ciências Sociais"),
]


@dataclass(frozen=True)
class _Macro:
    rotulo: str
    subarea: str
    revistas: tuple[str, ...]  # revistas preferidas
    topicos: tuple[tuple[str, str, float], ...]  # (rótulo, palavras-chave, tendência de -1 a 1)


MACROS = [
    _Macro(
        "Instituições políticas",
        "instituicoes_politicas",
        ("dados", "rbcpol", "bpsr", "rsocp"),
        (
            (
                "Legislativo e coalizões",
                "coalizão congresso agenda legislativa presidencialismo votação plenário comissões",
                0.0,
            ),
            (
                "Judiciário e STF",
                "supremo tribunal judicialização ministros decisões controle constitucionalidade",
                0.6,
            ),
            (
                "Federalismo",
                "federalismo estados municípios relações intergovernamentais transferências governadores",
                -0.2,
            ),
            ("Burocracia e Estado", "burocracia servidores capacidades estatais nomeações cargos administração", 0.2),
        ),
    ),
    _Macro(
        "Eleições e partidos",
        "eleicoes_e_partidos",
        ("op", "dados", "rbcpol", "bpsr"),
        (
            (
                "Sistemas eleitorais",
                "lista aberta representação proporcional distritos magnitude cadeiras reforma",
                -0.3,
            ),
            (
                "Partidos e sistema partidário",
                "partidos fragmentação filiação organização partidária sistema partidário",
                0.0,
            ),
            ("Financiamento de campanhas", "financiamento doações campanhas gastos eleitorais empresas fundo", -0.4),
            (
                "Voto e comportamento eleitoral",
                "voto eleitores preferências identificação partidária escolha eleitoral",
                0.1,
            ),
        ),
    ),
    _Macro(
        "Opinião pública e cultura política",
        "comportamento_e_opiniao",
        ("op", "rbcsoc", "bpsr"),
        (
            ("Confiança nas instituições", "confiança democracia apoio satisfação instituições cidadãos", 0.1),
            (
                "Polarização e redes sociais",
                "polarização redes sociais desinformação bolsonarismo afetiva digital",
                1.0,
            ),
            ("Religião e política", "evangélicos religião igrejas bancada conservadorismo moral", 0.7),
            ("Mídia e comunicação política", "mídia imprensa jornalismo comunicação agenda enquadramento", 0.0),
        ),
    ),
    _Macro(
        "Políticas públicas",
        "politicas_publicas",
        ("rsocp", "dados", "nec", "rbcsoc"),
        (
            ("Políticas sociais", "bolsa família transferência renda pobreza proteção social assistência", -0.2),
            ("Saúde e SUS", "saúde sus sistema único política de saúde pandemia covid", 0.5),
            ("Educação", "educação escolas ensino superior cotas universidades políticas educacionais", 0.1),
            ("Segurança pública", "segurança pública polícia violência crime drogas encarceramento", 0.4),
        ),
    ),
    _Macro(
        "Relações internacionais",
        "relacoes_internacionais",
        ("cint", "rbpi"),
        (
            ("Política externa brasileira", "política externa itamaraty diplomacia inserção internacional brasil", 0.0),
            ("China e BRICS", "china brics cooperação sul-sul potências emergentes ordem global", 0.8),
            ("Segurança e defesa", "defesa segurança internacional forças armadas conflitos guerra", 0.2),
            ("Integração regional", "mercosul integração regional unasul américa do sul regionalismo", -0.8),
        ),
    ),
    _Macro(
        "Teoria política",
        "teoria_politica",
        ("ln", "rbcsoc", "nec"),
        (
            ("Teoria democrática", "democracia teoria democrática representação deliberação soberania", 0.0),
            ("Pensamento político brasileiro", "pensamento social intelectuais freyre buarque formação nacional", -0.3),
            ("Teoria crítica e decolonial", "colonialidade teoria crítica modernidade marx periferia decolonial", 0.5),
            ("Justiça e liberalismo", "justiça liberalismo rawls igualdade liberdade direitos", -0.2),
        ),
    ),
    _Macro(
        "Sociedade civil e movimentos",
        "sociedade_civil_e_movimentos",
        ("rbcsoc", "ln", "nec", "rsocp"),
        (
            (
                "Movimentos sociais e protesto",
                "movimentos sociais protestos junho mobilização ativismo repertórios",
                0.3,
            ),
            (
                "Participação e conselhos",
                "participação conselhos orçamento participativo sociedade civil controle social",
                -0.6,
            ),
            ("Gênero e representação", "mulheres gênero representação feminina cotas candidaturas feminismo", 0.6),
            ("Raça e desigualdade racial", "raça racismo negros desigualdade racial ações afirmativas", 0.7),
        ),
    ),
]

INSTITUICOES = [
    ("usp", "Universidade de São Paulo", "USP", "SP", "BR", 9),
    ("unicamp", "Universidade Estadual de Campinas", "Unicamp", "SP", "BR", 4),
    ("ufmg", "Universidade Federal de Minas Gerais", "UFMG", "MG", "BR", 6),
    ("unb", "Universidade de Brasília", "UnB", "DF", "BR", 6),
    ("ufrj", "Universidade Federal do Rio de Janeiro", "UFRJ", "RJ", "BR", 5),
    ("iesp-uerj", "Instituto de Estudos Sociais e Políticos da UERJ", "IESP-UERJ", "RJ", "BR", 5),
    ("puc-rio", "Pontifícia Universidade Católica do Rio de Janeiro", "PUC-Rio", "RJ", "BR", 3),
    ("fgv", "Fundação Getulio Vargas", "FGV", "SP", "BR", 4),
    ("ufpe", "Universidade Federal de Pernambuco", "UFPE", "PE", "BR", 4),
    ("ufrgs", "Universidade Federal do Rio Grande do Sul", "UFRGS", "RS", "BR", 4),
    ("ufpr", "Universidade Federal do Paraná", "UFPR", "PR", "BR", 3),
    ("ufsc", "Universidade Federal de Santa Catarina", "UFSC", "SC", "BR", 2),
    ("ufba", "Universidade Federal da Bahia", "UFBA", "BA", "BR", 2),
    ("ufc", "Universidade Federal do Ceará", "UFC", "CE", "BR", 2),
    ("ufpa", "Universidade Federal do Pará", "UFPA", "PA", "BR", 1),
    ("ufg", "Universidade Federal de Goiás", "UFG", "GO", "BR", 1),
    ("ufscar", "Universidade Federal de São Carlos", "UFSCar", "SP", "BR", 2),
    ("ipea", "Instituto de Pesquisa Econômica Aplicada", "Ipea", "DF", "BR", 2),
    ("cebrap", "Centro Brasileiro de Análise e Planejamento", "Cebrap", "SP", "BR", 2),
    ("ufrn", "Universidade Federal do Rio Grande do Norte", "UFRN", "RN", "BR", 1),
    ("ufes", "Universidade Federal do Espírito Santo", "UFES", "ES", "BR", 1),
    ("ufam", "Universidade Federal do Amazonas", "UFAM", "AM", "BR", 1),
    ("ufpb", "Universidade Federal da Paraíba", "UFPB", "PB", "BR", 1),
    ("harvard", "Harvard University", None, None, "US", 1),
    ("lisboa", "Universidade de Lisboa", None, None, "PT", 1),
    ("uba", "Universidad de Buenos Aires", "UBA", None, "AR", 1),
    ("unam", "Universidad Nacional Autónoma de México", "UNAM", None, "MX", 1),
    ("sciencespo", "Sciences Po", None, None, "FR", 1),
    ("lse", "London School of Economics", "LSE", None, "GB", 1),
]

SOBRENOMES = [
    "Silva",
    "Santos",
    "Oliveira",
    "Souza",
    "Lima",
    "Pereira",
    "Carvalho",
    "Almeida",
    "Ribeiro",
    "Rodrigues",
    "Barbosa",
    "Cardoso",
    "Rocha",
    "Dias",
    "Nascimento",
    "Moreira",
    "Araújo",
    "Mendes",
    "Freitas",
    "Teixeira",
    "Costa",
    "Martins",
    "Gomes",
    "Monteiro",
    "Figueiredo",
    "Limongi",
    "Melo",
    "Cavalcanti",
    "Nogueira",
    "Batista",
    "Campos",
    "Ramos",
    "Vieira",
    "Castro",
    "Pinto",
    "Fonseca",
    "Lopes",
    "Machado",
    "Moura",
    "Tavares",
]

METODO = {  # técnica -> (abordagem, frase que evidencia a técnica)
    "survey": ("quantitativa", "Com base em dados de survey nacional, estimamos modelos de regressão logística"),
    "experimento": ("quantitativa", "Realizamos um experimento de survey com amostra representativa da população"),
    "dados_observacionais_agregados": (
        "quantitativa",
        "A análise estatística utiliza séries de dados eleitorais, legislativos e orçamentários",
    ),
    "textos_e_documentos": ("qualitativa", "O estudo examina documentos oficiais, discursos e matérias de imprensa"),
    "entrevistas_e_observacao": (
        "qualitativa",
        "A pesquisa se baseia em entrevistas semiestruturadas com atores-chave",
    ),
    "estudo_de_caso_historico": ("qualitativa", "Reconstruímos o processo histórico a partir de um estudo de caso"),
    "bibliografia": ("teorica_ensaistica", "O ensaio discute a literatura clássica e contemporânea sobre o tema"),
}
TECNICAS_POR_MACRO = {
    "instituicoes_politicas": {
        "dados_observacionais_agregados": 5,
        "textos_e_documentos": 3,
        "entrevistas_e_observacao": 2,
    },
    "eleicoes_e_partidos": {"dados_observacionais_agregados": 5, "survey": 4, "experimento": 1},
    "comportamento_e_opiniao": {"survey": 6, "experimento": 3, "textos_e_documentos": 2},
    "politicas_publicas": {
        "dados_observacionais_agregados": 3,
        "entrevistas_e_observacao": 3,
        "textos_e_documentos": 3,
    },
    "relacoes_internacionais": {"textos_e_documentos": 5, "estudo_de_caso_historico": 4, "bibliografia": 1},
    "teoria_politica": {"bibliografia": 9, "estudo_de_caso_historico": 1},
    "sociedade_civil_e_movimentos": {"entrevistas_e_observacao": 5, "textos_e_documentos": 3, "survey": 2},
}
RECORTES = {  # recorte -> frase de lugar
    "brasil_nacional": "no Brasil",
    "brasil_subnacional": "em municípios e estados brasileiros",
    "america_latina": "na América Latina",
    "outro_pais_ou_regiao": "em perspectiva comparada com a Europa",
    "internacional_global": "no sistema internacional",
    "sem_recorte": "no debate teórico contemporâneo",
}


def _escolher(rng: random.Random, pesos: dict[str, float]) -> str:
    return rng.choices(list(pesos), weights=list(pesos.values()))[0]


def _codebook() -> Codebook:
    texto = resources.files("mapa_da_ciencia.modelos_projeto").joinpath("codebook-exemplo.yaml").read_text("utf-8")
    return Codebook.model_validate(yaml.safe_load(texto))


def gerar_exemplo(n_docs: int = 1500, semente: int = 42) -> tuple[dict[str, m.BaseModel], dict[str, m.Fragmento]]:
    """Gera todos os arquivos do contrato. Devolve (arquivos por nome, fragmentos de detalhes)."""
    rng = random.Random(semente)
    cb = _codebook()

    # ---- tópicos: posição no plano, cor (a mesma paleta do pipeline) e tendência
    cores_macro = cores_macrotemas(len(MACROS))
    # ids dos macrotemas não contíguos, como os do piloto depois de execuções com a identidade estável (ADR 0007):
    # quem usar o id como índice (em vez da posição em `topicos.macrotemas`) erra aqui também
    id_macro = [k if k < 3 else k + 2 for k in range(len(MACROS))]
    topicos_def = []  # (id, posição do macrotema, rotulo, palavras, tendência, centro, cor)
    for mi, macro in enumerate(MACROS):
        ang = 2 * math.pi * mi / len(MACROS)
        cx, cy = 6.5 * math.cos(ang), 6.5 * math.sin(ang)
        usadas: list[str] = []
        for ti, (rotulo, palavras, tend) in enumerate(macro.topicos):
            a2 = ang + (ti - 1.5) * 0.9
            centro = (cx + 1.9 * math.cos(a2), cy + 1.9 * math.sin(a2))
            usadas.append(proxima_cor(cores_macro[mi], usadas))
            idx = len(topicos_def)
            tid = idx + 2 * (idx // 5)  # ids não contíguos, como depois de execuções que aposentaram tópicos
            topicos_def.append((tid, mi, rotulo, palavras.split(), tend, centro, usadas[-1]))

    # ---- documentos
    pesos_ano = [1 + 0.04 * (a - ANOS[0]) for a in ANOS]
    docs = []
    for i in range(n_docs):
        ano = rng.choices(ANOS, weights=pesos_ano)[0]
        t_ano = (ano - ANOS[0]) / (ANOS[-1] - ANOS[0])
        pesos_top = [math.exp(2.6 * tend * (t_ano - 0.5)) for *_, tend, _, _ in topicos_def]
        tid, mi, rotulo, palavras, _, (cx, cy), _ = topicos_def[rng.choices(range(len(topicos_def)), pesos_top)[0]]
        macro = MACROS[mi]
        revista = rng.choice(macro.revistas) if rng.random() < 0.8 else rng.choice(REVISTAS)[0]
        idioma = "pt"  # os resumos sintéticos são todos em português
        vizinho = rng.random() < 0.15  # o HDBSCAN deixou sem tópico; a vizinhança atribuiu (ou não: -1)
        sem_topico = vizinho and rng.random() < 0.12
        espalhamento = 0.5 if not vizinho else (0.9 if not sem_topico else 1.6)
        x, y = cx + rng.gauss(0, espalhamento), cy + rng.gauss(0, espalhamento)
        tecnica = _escolher(rng, TECNICAS_POR_MACRO[macro.subarea])
        abordagem = METODO[tecnica][0]
        if abordagem != "teorica_ensaistica" and rng.random() < 0.12:
            abordagem = "mista"
        if macro.subarea == "relacoes_internacionais":
            recorte = _escolher(rng, {"internacional_global": 4, "america_latina": 3, "brasil_nacional": 3})
        elif macro.subarea == "teoria_politica":
            recorte = _escolher(rng, {"sem_recorte": 7, "brasil_nacional": 3})
        else:
            recorte = _escolher(rng, {"brasil_nacional": 6, "brasil_subnacional": 3, "america_latina": 1})
        docs.append(
            {
                "id": f"exemplo:{i:05d}",
                "doi": f"10.0000/exemplo.{i:05d}" if rng.random() < 0.95 else None,
                "ano": ano,
                "revista": revista,
                "idioma": idioma,
                "x": round(x, 4),
                "y": round(y, 4),
                "topico": -1 if sem_topico else tid,
                "atribuicao": "vizinho" if vizinho else "cluster",
                "palavras": palavras,
                "rotulo_topico": rotulo,
                "cls": {
                    "abordagem": abordagem,
                    "tecnica_principal": tecnica,
                    "recorte_geografico": recorte,
                    "brasil_como_caso": recorte in ("brasil_nacional", "brasil_subnacional") or rng.random() < 0.1,
                    "subarea": macro.subarea if rng.random() < 0.85 else "outra",
                },
                "autores": [
                    f"{rng.choice(SOBRENOMES)}, {rng.choice('ABCDEFGHIJLMNPRST')}."
                    for _ in range(rng.choices([1, 2, 3, 4], [4, 4, 2, 1])[0])
                ],
            }
        )

    # ---- títulos e resumos com evidências localizáveis
    sufixos = ["no Brasil contemporâneo", "em perspectiva comparada", "uma análise empírica", "teoria e evidências"]
    detalhes: dict[str, m.Detalhe] = {}
    for d in docs:
        kw = rng.sample(d["palavras"], 3)
        periodo = (d["ano"] - rng.randint(4, 15), d["ano"] - rng.randint(1, 3))
        d["titulo"] = f"{kw[0].capitalize()} e {kw[1]}: {rng.choice(sufixos)}"
        frase_objeto = f"Este artigo analisa {d['rotulo_topico'].lower()} {RECORTES[d['cls']['recorte_geografico']]}"
        frase_metodo = METODO[d["cls"]["tecnica_principal"]][1]
        frase_periodo = f"O período analisado vai de {periodo[0]} a {periodo[1]}"
        frases = [
            frase_objeto,
            frase_metodo,
            frase_periodo,
            f"Os resultados indicam que {kw[0]} e {kw[2]} estão associados de forma consistente",
            f"Discutimos as implicações para a agenda de pesquisa sobre {kw[1]}",
        ]
        resumo = ". ".join(frases) + "."
        evid = {}
        for var, frase in (
            ("abordagem", frase_metodo),
            ("tecnica_principal", frase_metodo),
            ("recorte_geografico", frase_objeto),
            ("brasil_como_caso", frase_objeto),
            ("subarea", frase_objeto),
            ("periodo_analisado", frase_periodo),
        ):
            valor = d["cls"].get(var, f"{periodo[0]}–{periodo[1]}")
            if valor is False:  # "não": a evidência pode ficar vazia
                evid[var] = m.Evidencia(valor=valor, evidencia="", status="dispensada")
            elif rng.random() < 0.05:  # às vezes o modelo parafraseia: evidência aproximada, sem posição
                evid[var] = m.Evidencia(valor=valor, evidencia=frase.lower()[:-3], status="aproximada")
            else:
                ini = resumo.index(frase)
                evid[var] = m.Evidencia(
                    valor=valor, evidencia=frase, status="literal", inicio=ini, fim=ini + len(frase), campo="resumo"
                )
        licenca = rng.choices(["cc-by", "cc-by-nc", "desconhecida"], [45, 50, 5])[0]
        fonte_analise = "reserva" if rng.random() < 0.03 else "resumo"  # sem resumo em inglês: vai o português
        detalhes[d["id"]] = m.Detalhe(
            resumo=resumo if licenca != "desconhecida" else None,
            idioma=d["idioma"],
            palavras_chave=kw,
            autores=[a.replace(",", "") for a in d["autores"]],
            url=f"https://doi.org/{d['doi']}" if d["doi"] else None,
            licenca=licenca,
            licenca_fonte="openalex" if licenca != "desconhecida" else "nenhuma",
            evidencias=evid,
            idioma_analise="en" if fonte_analise == "resumo" else "pt",
            fonte_analise=fonte_analise,
        )

    # ---- vizinhos mais próximos (força bruta basta para o exemplo)
    xs, ys = [d["x"] for d in docs], [d["y"] for d in docs]
    vizinhos = []
    for i in range(len(docs)):
        dist = sorted(((xs[j] - xs[i]) ** 2 + (ys[j] - ys[i]) ** 2, j) for j in range(len(docs)) if j != i)
        vizinhos.append([j for _, j in dist[:5]])

    # ---- documentos.json (colunar)
    id_revistas = [r[0] for r in REVISTAS]
    idiomas = ["pt"]
    vars_cls = [v for v in cb.variaveis if v.tipo in ("categorica", "booleana")]
    dic_cls = {v.id: [c.valor for c in v.categorias] if v.tipo == "categorica" else ["false", "true"] for v in vars_cls}

    def _idx_cls(var: str, valor: object) -> int:
        chave = str(valor).lower() if isinstance(valor, bool) else str(valor)
        return dic_cls[var].index(chave)

    documentos = m.Documentos(
        n=len(docs),
        colunas=m.ColunasDocumentos(
            id=[d["id"] for d in docs],
            doi=[d["doi"] for d in docs],
            titulo=[d["titulo"] for d in docs],
            ano=[d["ano"] for d in docs],
            revista=[id_revistas.index(d["revista"]) for d in docs],
            idioma=[idiomas.index(d["idioma"]) for d in docs],
            x=xs,
            y=ys,
            topico=[d["topico"] for d in docs],
            atribuicao=[0 if d["atribuicao"] == "cluster" else 1 for d in docs],
            autores_curto=[
                d["autores"][0] + (f"; +{len(d['autores']) - 1}" if len(d["autores"]) > 1 else "") for d in docs
            ],
            vizinhos=vizinhos,
            cls={v.id: [_idx_cls(v.id, d["cls"][v.id]) for d in docs] for v in vars_cls},
        ),
        dicionarios=m.DicionariosDocumentos(revista=id_revistas, idioma=idiomas, cls=dic_cls),
    )

    # ---- afiliações (contagem fracionária pela regra do glossário: 1 por documento, dividido entre os autores e
    # depois entre as afiliações de cada um). Casos de borda como no piloto: documentos sem afiliação, concentrados
    # nos primeiros anos; autores sem afiliação; instituições não identificadas; vínculos brasileiros sem UF.
    insts = [m.Instituicao(id=i[0], nome=i[1], sigla=i[2], uf=i[3], pais=i[4]) for i in INSTITUICOES]
    insts.append(m.Instituicao(id=m.NAO_IDENTIFICADA, nome="Instituição não identificada", pais=""))
    i_nao_identificada = len(insts) - 1
    ufs = list(m.SIGLAS_UF)
    paises = sorted({i.pais for i in insts if i.pais})
    pesos_inst = [i[5] for i in INSTITUICOES]
    linhas_af: dict[tuple[int, int, int, int], float] = defaultdict(float)
    for di, d in enumerate(docs):
        sem_afiliacao = rng.random() < (0.25 if d["ano"] <= 2014 else 0.02)
        for _ in d["autores"]:
            fracao = 1 / len(d["autores"])
            if sem_afiliacao or rng.random() < 0.03:
                linhas_af[(di, -1, -1, -1)] += fracao
                continue
            n_af = 2 if rng.random() < 0.2 else 1
            for _ in range(n_af):
                if rng.random() < 0.05:  # a afiliação foi informada, mas não casou com nenhuma instituição
                    pais = paises.index("BR") if rng.random() < 0.7 else -1
                    linhas_af[(di, i_nao_identificada, -1, pais)] += fracao / n_af
                    continue
                ii = rng.choices(range(len(INSTITUICOES)), pesos_inst)[0]
                inst = insts[ii]
                uf = ufs.index(inst.uf) if inst.uf and rng.random() > 0.03 else -1
                linhas_af[(di, ii, uf, paises.index(inst.pais))] += fracao / n_af
    af: dict[str, list] = defaultdict(list)
    for (di, ii, uf, pais), peso in sorted(linhas_af.items()):
        af["doc"].append(di)
        af["instituicao"].append(ii)
        af["uf"].append(uf)
        af["pais"].append(pais)
        af["peso"].append(round(peso, 6))
    afiliacoes = m.Afiliacoes(
        n=len(af["doc"]),
        colunas=m.ColunasAfiliacoes(**af),
        dicionarios=m.DicionariosAfiliacoes(instituicao=insts, uf=ufs, pais=paises),
    )

    # ---- topicos.json
    total_ano = Counter(d["ano"] for d in docs)
    total = [total_ano[a] for a in ANOS]
    topicos = []
    for tid, mi, rotulo, palavras, _, (cx, cy), cor in topicos_def:
        membros = [d for d in docs if d["topico"] == tid]
        nucleo = [d for d in membros if d["atribuicao"] == "cluster"]
        por_ano = Counter(d["ano"] for d in membros)
        base = nucleo or membros or [{"x": cx, "y": cy}]  # exemplos pequenos podem deixar um tópico vazio
        centro_real = (sum(d["x"] for d in base) / len(base), sum(d["y"] for d in base) / len(base))
        repr_ = sorted(nucleo, key=lambda d: (d["x"] - cx) ** 2 + (d["y"] - cy) ** 2)[:5]
        topicos.append(
            m.Topico(
                id=tid,
                macro_id=id_macro[mi],
                rotulo=rotulo,
                descricao=f"Trabalhos sobre {rotulo.lower()}, com destaque para {palavras[0]} e {palavras[1]}.",
                palavras_chave=[(p, round(1 / (k + 1), 3)) for k, p in enumerate(palavras)],
                n=len(membros),
                centroide=(round(centro_real[0], 4), round(centro_real[1], 4)),
                cor=cor,
                serie=m.Serie(
                    n=[por_ano[a] for a in ANOS],
                    prop=[round(por_ano[a] / total_ano[a], 5) if total_ano[a] else 0.0 for a in ANOS],
                ),
                por_revista=dict(sorted(Counter(d["revista"] for d in membros).items())),
                representativos=[d["id"] for d in repr_],
                rotulo_fonte="llm",
                n_nucleo=len(nucleo),
                tendencia=tendencia_contrato([por_ano[a] for a in ANOS], total, ANOS),
            )
        )
    macrotemas = []
    for mi, mc in enumerate(MACROS):
        ids_m = [t[0] for t in topicos_def if t[1] == mi]
        por_ano_m = Counter(d["ano"] for d in docs if d["topico"] in ids_m)
        macrotemas.append(
            m.Macrotema(
                id=id_macro[mi],
                rotulo=mc.rotulo,
                cor=cores_macro[mi],
                topicos=ids_m,
                serie=m.Serie(
                    n=[por_ano_m[a] for a in ANOS],
                    prop=[round(por_ano_m[a] / total_ano[a], 5) if total_ano[a] else 0.0 for a in ANOS],
                ),
                tendencia=tendencia_contrato([por_ano_m[a] for a in ANOS], total, ANOS),
            )
        )
    ruido = [d for d in docs if d["atribuicao"] == "vizinho"]
    ruido_ano = Counter(d["ano"] for d in ruido)
    sem_topico_ano = Counter(d["ano"] for d in docs if d["topico"] == -1)
    topicos_arq = m.Topicos(
        anos=ANOS,
        total_por_ano=total,
        parametros={"modelo_embeddings": "exemplo", "min_cluster_size": 10, "semente": semente},
        estabilidade_ari=0.81,
        macrotemas=macrotemas,
        topicos=topicos,
        outliers=m.Outliers(
            n=len(ruido),
            reatribuidos=sum(d["topico"] != -1 for d in ruido),
            por_ano=[ruido_ano[a] for a in ANOS],
            sem_topico_por_ano=[sem_topico_ano[a] for a in ANOS],
        ),
        metodo_tendencia=m.MetodoTendencia(),
    )

    # ---- codebook, classificações e validação
    codebook = codebook_contrato(cb)
    contagens_cls = {
        v.id: dict(Counter(str(d["cls"][v.id]).lower() if v.tipo == "booleana" else d["cls"][v.id] for d in docs))
        for v in vars_cls
    }
    n_evid = sum(e.status != "dispensada" for det in detalhes.values() for e in det.evidencias.values())
    n_lit = sum(e.status == "literal" for det in detalhes.values() for e in det.evidencias.values())
    por_variavel = {}
    for v in cb.variaveis:
        evs = [det.evidencias[v.id] for det in detalhes.values() if v.id in det.evidencias]
        st = Counter(e.status for e in evs if e.status != "dispensada")
        por_variavel[v.id] = m.VariavelClassificada(
            n=len(evs),
            sem_informacao=round(sum(e.status == "dispensada" for e in evs) / len(evs), 4),
            evidencia={k: round(x / sum(st.values()), 4) for k, x in sorted(st.items())},
        )
    classificacoes = m.Classificacoes(
        modelo="exemplo",
        hash_codebook=cb.hash(),
        cobertura=1.0,
        evidencia_literal=round(n_lit / n_evid, 4),
        contagens=contagens_cls,
        classificados=len(docs),
        documentos=len(docs),
        por_variavel=por_variavel,
    )
    validacao, amostra = _validacao_sintetica(rng, docs, vars_cls, dic_cls)
    _juri_sintetico(rng, validacao, amostra, vars_cls, dic_cls, detalhes)

    # ---- agregados (gabarito do filtro cruzado)
    tar = Counter((d["topico"], d["ano"], d["revista"]) for d in docs)
    geo = agregados_geograficos(afiliacoes)
    agregados = m.Agregados(topico_ano_revista=[(t, a, r, n) for (t, a, r), n in sorted(tar.items())], **geo)

    revistas = m.Revistas(
        revistas=[
            m.Revista(id=a, issn=issn, titulo=t, areas=["Ciências Humanas"], n=sum(d["revista"] == a for d in docs))
            for a, issn, t in REVISTAS
        ]
    )
    macro_do_topico = {tid: id_macro[mi] for tid, mi, *_ in topicos_def}
    redes, citacoes, gabarito = _redes_sinteticas(
        random.Random(semente + 1), docs, macro_do_topico, af, insts, i_nao_identificada, id_macro
    )
    agregados = agregados.model_copy(update=gabarito)
    licencas = Counter(det.licenca for det in detalhes.values())
    arquivos: dict[str, m.BaseModel] = {
        "revistas": revistas,
        "documentos": documentos,
        "afiliacoes": afiliacoes,
        "topicos": topicos_arq,
        "codebook": codebook,
        "classificacoes": classificacoes,
        "validacao": validacao,
        "agregados": agregados,
        "redes": redes,
        "citacoes": citacoes,
    }
    manifesto = m.Manifesto(
        api=False,
        gerado_em=datetime(2026, 9, 26, 12, 0, tzinfo=UTC),
        projeto=m.ProjetoInfo(
            nome="exemplo",
            titulo="Exemplo sintético: ciência política, 2010–2025",
            descricao="Dados FICTÍCIOS gerados para demonstração e testes. Não use em análises.",
        ),
        recorte=m.RecorteInfo(anos=(ANOS[0], ANOS[-1]), fontes=["exemplo"], idioma_analise="en", idioma_exibicao="pt"),
        contagens=m.Contagens(
            documentos=len(docs),
            topicos=len(topicos),
            classificados=len(docs),
            validados=validacao.amostra.n,
            com_afiliacao=len({di for di, ii in zip(af["doc"], af["instituicao"], strict=True) if ii >= 0}),
            com_instituicao=len(
                {di for di, ii in zip(af["doc"], af["instituicao"], strict=True) if 0 <= ii != i_nao_identificada}
            ),
        ),
        arquivos=["manifesto", *arquivos, "detalhes"],
        execucao=m.ExecucaoInfo(
            versao_pacote="exemplo",  # fixo: os dados de exemplo não mudam a cada versão
            modelos={"embeddings": "exemplo", "classificacao": "exemplo", "rotulos": "exemplo"},
            hash_codebook=cb.hash(),
            sementes={"exemplo": semente},
        ),
        licencas=dict(sorted(licencas.items())),
    )
    arquivos = {"manifesto": manifesto, **arquivos}

    fragmentos: dict[str, dict[str, m.Detalhe]] = defaultdict(dict)
    for doc_id, det in detalhes.items():
        fragmentos[m.fragmento_de(doc_id)][doc_id] = det
    return arquivos, {k: m.Fragmento(fragmento=k, documentos=v) for k, v in fragmentos.items()}


def _kappa(a: list[str], b: list[str]) -> tuple[float, float, float]:
    """(concordância, kappa de Cohen, PABAK) para duas listas de rótulos."""
    n = len(a)
    po = sum(x == y for x, y in zip(a, b, strict=True)) / n
    ca, cb_ = Counter(a), Counter(b)
    pe = sum(ca[k] * cb_[k] for k in set(ca) | set(cb_)) / n**2
    k = len(set(a) | set(b))
    kappa = (po - pe) / (1 - pe) if pe < 1 else 1.0
    pabak = (k * po - 1) / (k - 1) if k > 1 else 1.0
    return po, kappa, pabak


REFERENCIA = "referencia-exemplo"  # um codificador de referência fictício (não humano)


def _validacao_sintetica(rng, docs, vars_cls, dic_cls) -> tuple[m.Validacao, list[dict]]:
    amostra = rng.sample(docs, 60)
    metricas, divergencias = [], []
    for v in vars_cls:
        erro = {"abordagem": 0.1, "tecnica_principal": 0.25, "recorte_geografico": 0.12}.get(v.id, 0.08)
        modelo = [str(d["cls"][v.id]).lower() if v.tipo == "booleana" else d["cls"][v.id] for d in amostra]
        humano = [x if rng.random() > erro else rng.choice(dic_cls[v.id]) for x in modelo]
        po, kappa, pabak = _kappa(humano, modelo)
        rotulos = dic_cls[v.id]
        matriz = [
            [sum(h == r and mo == c for h, mo in zip(humano, modelo, strict=True)) for c in rotulos] for r in rotulos
        ]
        metricas.append(
            m.MetricaVariavel(
                variavel=v.id,
                comparacao=f"{REFERENCIA} × exemplo",
                n=len(amostra),
                concordancia=round(po, 4),
                kappa=round(kappa, 4),
                kappa_ic95=(round(max(kappa - 0.12, -1), 4), round(min(kappa + 0.1, 1), 4)),
                pabak=round(pabak, 4),
                alfa=None,
                matriz=m.Matriz(rotulos=rotulos, valores=matriz),
                referencia=REFERENCIA,
                comparado="exemplo",
                por_classe=[
                    m.MetricaClasse(
                        rotulo=r,
                        suporte=sum(linha),
                        precisao=round(matriz[i][i] / col, 4) if (col := sum(x[i] for x in matriz)) else None,
                        revocacao=round(matriz[i][i] / sum(linha), 4) if sum(linha) else None,
                        f1=round(2 * matriz[i][i] / (sum(linha) + col), 4) if sum(linha) + col else None,
                    )
                    for i, (r, linha) in enumerate(zip(rotulos, matriz, strict=True))
                ],
            )
        )
        for d, h, mo in zip(amostra, humano, modelo, strict=True):
            if h != mo and len(divergencias) < 40:
                divergencias.append(
                    m.Divergencia(
                        doc=d["id"],
                        variavel=v.id,
                        humano=h,
                        modelo=mo,
                        evidencia="(ver resumo)",
                        codificador=REFERENCIA,
                        status="literal",
                    )
                )
    return m.Validacao(
        amostra=m.AmostraInfo(n=len(amostra), estratificar_por="topico", semente=7),
        metricas=metricas,
        modelos=["exemplo"],
        divergencias=divergencias,
        codificadores=[
            m.Participante(nome=REFERENCIA, tipo="referencia", n=len(amostra)),
            m.Participante(nome="exemplo", tipo="modelo", n=len(amostra)),
        ],
        modelo_principal="exemplo",
        evidencia_literal={"exemplo": 0.95},
    ), amostra


MEMBROS_EXEMPLO = ["exemplo", "modelo-b", "modelo-c"]


def _juri_sintetico(rng, validacao: m.Validacao, amostra: list[dict], vars_cls, dic_cls, detalhes) -> None:
    """Um júri fictício de três membros na amostra: votos, deliberação, supervisor e auditoria, para a interface."""
    from mapa_da_ciencia.juri.agregacao import Voto, agregar
    from mapa_da_ciencia.juri.supervisor import wilson

    etapas = {v.id: {"unanime": 0, "maioria": 0, "deliberacao": 0, "sem_maioria": 0} for v in vars_cls}
    virou = dict.fromkeys(etapas, 0)
    deliberacao = {x: {"votos": 0, "mudou": 0, "para_referencia": 0, "contra": 0} for x in MEMBROS_EXEMPLO}
    for d in amostra:
        decisoes = {}
        for v in vars_cls:
            certo = d["cls"][v.id]
            valores = [certo] + [certo if rng.random() < q else rng.choice(dic_cls[v.id]) for q in (0.85, 0.7)]
            if v.tipo == "booleana":
                valores = [x if isinstance(x, bool) else str(x).lower() == "true" for x in valores]
            r1 = [
                Voto(membro, x, "(ver resumo)", "literal") for membro, x in zip(MEMBROS_EXEMPLO, valores, strict=True)
            ]
            d1 = agregar(v, r1)
            votos = [m.VotoJuri(membro=x.membro, rodada=1, valor=x.valor, evidencia=x.evidencia, status="literal")
                     for x in r1]  # fmt: skip
            etapa, valor, supervisor, justificativa = d1.etapa, d1.valor, None, None
            if d1.etapa != "unanime":
                r2 = [
                    x if x.valor == d1.valor or rng.random() < 0.5 else Voto(x.membro, certo, x.evidencia) for x in r1
                ]
                d2 = agregar(v, r2)
                for a, b in zip(r1, r2, strict=True):
                    deliberacao[a.membro]["votos"] += 1
                    mudou = a.valor != b.valor
                    deliberacao[a.membro]["mudou"] += mudou
                    deliberacao[a.membro]["para_referencia"] += mudou
                    votos.append(m.VotoJuri(membro=b.membro, rodada=2, valor=b.valor, evidencia=b.evidencia,
                                            status="literal", revisou=mudou))  # fmt: skip
                etapa = "deliberacao" if d2.decidida else "sem_maioria"
                virou[v.id] += d2.decidida and (not d1.decidida or d1.valor != d2.valor)
                valor = d2.valor if d2.decidida else r2[0].valor
                if not d2.decidida:
                    supervisor, justificativa = "supervisor", "Exemplo: o resumo descreve o desenho da pesquisa."
                    valor = certo
            etapas[v.id][etapa] += 1
            decisoes[v.id] = m.DecisaoJuri(
                etapa=etapa,
                virou=bool(virou[v.id]) and etapa == "deliberacao",
                valor=valor,
                valor_sem_supervisor=valor if supervisor is None else r1[0].valor,
                supervisor=supervisor,
                justificativa=justificativa,
                votos=votos,
            )
        if d["id"] in detalhes:
            detalhes[d["id"]].juri = decisoes
    validacao.juri = m.ResumoJuri(
        referencia=REFERENCIA,
        membros=MEMBROS_EXEMPLO,
        supervisor="supervisor",
        familia_supervisor="exemplo",
        documentos=len(amostra),
        etapas=etapas,
        virou=virou,
        concordancia_por_etapa={"unanime": {"n": 240, "acertos": 221}, "sem_maioria": {"n": 20, "acertos": 8}},
        concordancia_supervisor=m.ConcordanciaSupervisor(n=20, acertos=12, circular=True),
        deliberacao=deliberacao,
        auditoria=m.AuditoriaJuri(n=12, erros=1, taxa=round(1 / 12, 4), ic95=wilson(1, 12), por_variavel={}),
    )
    for x in list(validacao.metricas):
        for nome, circular in (("juri", False), ("juri-supervisor", True)):
            validacao.metricas.append(
                x.model_copy(update={"comparacao": f"{REFERENCIA} × {nome}", "comparado": nome, "circular": circular})
            )
    validacao.modelos += ["juri", "juri-supervisor"]
    validacao.codificadores = [
        m.Participante(nome=REFERENCIA, tipo="referencia", n=len(amostra), familia="exemplo"),
        m.Participante(nome="exemplo", tipo="modelo", n=len(amostra)),
        m.Participante(nome="juri", tipo="modelo", n=len(amostra)),
        m.Participante(nome="juri-supervisor", tipo="modelo", n=len(amostra), familia="exemplo"),
    ]


PRENOMES = ["Ana", "Bruno", "Carla", "Diego", "Elisa", "Fábio", "Gisele", "Hugo", "Iara", "João", "Karina", "Luís"]
SOBRENOMES = ["Almeida", "Barros", "Cardoso", "Duarte", "Esteves", "Freitas", "Gomes", "Hollanda", "Iório", "Jardim"]


def _redes_sinteticas(rng, docs, macro_do_topico, af, insts, i_nao_identificada, ids_macros):
    """Redes fictícias sobre os documentos do exemplo: pessoas por macrotema (com alguma mistura), a colaboração
    entre as instituições das afiliações do exemplo, citações de documentos mais antigos e um cânone inventado."""
    from mapa_da_ciencia.contrato.redes import fluxo_por_posicao
    from mapa_da_ciencia.redes.citacoes import calcular
    from mapa_da_ciencia.redes.grafos import colaboracao_por_ano, comunidades, grafo, metricas, pares_ponderados

    ids = [d["id"] for d in docs]
    macro_do_doc = {d["id"]: macro_do_topico.get(d["topico"], -1) for d in docs}
    pessoas = [f"{p} {s}" for s in SOBRENOMES for p in PRENOMES]  # 120 pessoas fictícias
    grupo = {x: ids_macros[i % len(ids_macros)] for i, x in enumerate(pessoas)}
    por_macro = defaultdict(list)
    for x in pessoas:
        por_macro[grupo[x]].append(x)
    autores: dict[str, list[str]] = {}
    for d in docs:
        mi = macro_do_doc[d["id"]]
        base = por_macro[mi if mi >= 0 else rng.choice(ids_macros)]
        n = rng.choices([1, 2, 3, 4], [0.45, 0.33, 0.15, 0.07])[0]
        escolhidos = rng.sample(base, min(n, len(base)))
        if n > 1 and rng.random() < 0.15:
            escolhidos[-1] = rng.choice(pessoas)
        autores[d["id"]] = escolhidos
    arestas = pares_ponderados(autores)
    g = grafo(arestas)
    com, particao = comunidades(g, "coautoria")
    pos = _desenho_do_exemplo(g)
    ordem = sorted(pessoas)
    pos_de = {x: i for i, x in enumerate(ordem)}
    grau = Counter(x for par in arestas for x in par)
    n_docs = Counter(x for lista in autores.values() for x in set(lista))
    # instituições: as do exemplo, por documento
    inst_do_doc: dict[str, list[str]] = defaultdict(list)
    lugares: dict[str, list[str]] = defaultdict(list)
    for di, ii, uf in zip(af["doc"], af["instituicao"], af["uf"], strict=True):
        if ii >= 0 and ii != i_nao_identificada:
            inst_do_doc[ids[di]].append(insts[ii].id)
            if insts[ii].pais == "BR" and uf >= 0:
                lugares[ids[di]].append(insts[ii].uf)
            elif insts[ii].pais != "BR":
                lugares[ids[di]].append("EX")
    arestas_i = pares_ponderados(inst_do_doc)
    gi = grafo(arestas_i)
    com_i, particao_i = comunidades(gi, "instituicoes")
    pos_i = _desenho_do_exemplo(gi)
    grau_i = Counter(x for par in arestas_i for x in par)
    comunidades_c = []
    for rede, rotulos, membros_de in (("coautoria", com, autores), ("instituicoes", com_i, inst_do_doc)):
        for k in sorted({c for c in rotulos.values() if c >= 0}):
            membros = {x for x, c in rotulos.items() if c == k}
            docs_k = [d for d, lista in membros_de.items() if membros & set(lista)]
            macros = Counter(macro_do_doc[d] for d in docs_k if macro_do_doc[d] >= 0)
            topicos_k = Counter(d["topico"] for d in docs if d["id"] in set(docs_k) and d["topico"] >= 0)
            comunidades_c.append(
                m.ComunidadeRede(
                    rede=rede,
                    id=k,
                    n=len(membros),
                    documentos=len(docs_k),
                    macro=macros.most_common(1)[0][0] if macros else None,
                    topicos=[t for t, _ in topicos_k.most_common(3)],
                    rotulo=f"Comunidade {k + 1}",
                )
            )
    anos = {d["id"]: d["ano"] for d in docs}
    serie = colaboracao_por_ano(anos, autores, dict(inst_do_doc), dict(lugares))
    redes = m.Redes(
        pessoas=m.ColunasPessoas(
            id=[f"p{i:04d}" for i in range(len(ordem))],
            nome=ordem,
            documentos=[n_docs[x] for x in ordem],
            grau=[grau.get(x, 0) for x in ordem],
            comunidade=[com.get(x, -1) for x in ordem],
            x=[pos[x][0] if x in pos else None for x in ordem],
            y=[pos[x][1] if x in pos else None for x in ordem],
        ),
        autorias=m.AutoriasRede(
            doc=[i for i, d in enumerate(ids) for _ in autores[d]],
            pessoa=[pos_de[x] for d in ids for x in autores[d]],
        ),
        instituicoes=m.ColunasInstituicoesRede(
            id=sorted(pos_i),
            grau=[grau_i[i] for i in sorted(pos_i)],
            comunidade=[com_i.get(i, -1) for i in sorted(pos_i)],
            x=[pos_i[i][0] for i in sorted(pos_i)],
            y=[pos_i[i][1] for i in sorted(pos_i)],
        ),
        comunidades=comunidades_c,
        metricas={
            "coautoria": m.MetricasRede(**vars(metricas(g, particao))),
            "instituicoes": m.MetricasRede(**vars(metricas(gi, particao_i))),
        },
        colaboracao=[m.ColaboracaoAno(**{k: v for k, v in vars(c).items() if k != "extras"}) for c in serie],
        parametros={"semente": 7, "exemplo": True},
    )
    # citações: cada documento cita até três documentos mais antigos, quase sempre do mesmo macrotema, e obras
    # clássicas inventadas
    obra = {d: f"W{i:06d}" for i, d in enumerate(ids)}
    doc_da_obra = {w: d for d, w in obra.items()}
    por_ano_macro = defaultdict(list)
    for d in docs:
        por_ano_macro[macro_do_doc[d["id"]]].append(d)
    referencias = []
    classicas = [f"W9{k:05d}" for k in range(25)]
    for d in docs:
        mesmos = [x for x in por_ano_macro[macro_do_doc[d["id"]]] if x["ano"] < d["ano"]]
        for x in rng.sample(mesmos, min(len(mesmos), rng.randrange(4))):
            referencias.append({"obra": obra[d["id"]], "citada": obra[x["id"]]})
        for w in rng.sample(classicas, rng.randrange(3)):
            referencias.append({"obra": obra[d["id"]], "citada": w})
    citadas = [
        {"id": w, "titulo": f"Obra clássica fictícia {k + 1}", "ano": 1950 + k, "autores": [f"Autor Fictício {k + 1}"],
         "veiculo": "Editora Exemplo", "tipo": "book", "doi": None, "citacoes": 1000 - k}
        for k, w in enumerate(classicas)
    ]  # fmt: skip
    # uma delas chega pelo registro de uma resenha, como muitos livros no OpenAlex
    citadas[1] |= {"tipo": "book-review", "veiculo": "Choice Reviews Online"}
    topico_do_doc = {d["id"]: d["topico"] for d in docs}
    # a ArticleMeta lista mais referências do que o OpenAlex resolve (no piloto, cerca do dobro)
    resolvidas = Counter(doc_da_obra[r["obra"]] for r in referencias)
    listadas = {d: 2 * n + 1 for d, n in resolvidas.items()}
    c = calcular(referencias, citadas, doc_da_obra, anos, topico_do_doc, macro_do_topico, listadas=listadas)
    indice = {d: i for i, d in enumerate(ids)}
    fluxo = fluxo_por_posicao(c.fluxo_macrotemas, ids_macros)
    citacoes = m.Citacoes(
        n_referencias=[c.n_referencias.get(d, 0) for d in ids],
        internas=m.ArestasCitacao(de=[indice[a] for a, _ in c.internas], para=[indice[b] for _, b in c.internas]),
        canone=[
            m.ObraCitada(
                id=o.id,
                titulo=o.titulo,
                ano=o.ano,
                autores=o.autores,
                veiculo=o.veiculo,
                tipo=o.tipo,
                doi=o.doi,
                n=o.n,
                edicoes=o.edicoes,
                resenha=o.resenha,
            )
            for o in c.canone
        ],
        canone_citantes=m.CitantesCanone(
            doc=[indice[d] for o in c.canone for d in o.citantes],
            obra=[k for k, o in enumerate(c.canone) for _ in o.citantes],
        ),
        fluxo_macrotemas=fluxo,
        cobertura={k: int(v) for k, v in c.cobertura.items()},
    )
    gabarito = {
        "arestas_coautoria": len(arestas),
        "uf_pares": [(a, b, p, n) for (a, b), (p, n) in pares_ponderados(dict(lugares)).items()],
        "canone_n": [o.n for o in c.canone],
    }
    return redes, citacoes, gabarito


def _desenho_do_exemplo(g) -> dict[str, tuple[float, float]]:
    """Um desenho simples e igual em qualquer máquina (o `spring_layout` muda na quarta casa entre o Mac e o Linux, e
    o exemplo é conferido byte a byte no CI): cada componente num círculo, os componentes numa grade."""
    import networkx as nx

    componentes = sorted((sorted(c) for c in nx.connected_components(g)), key=lambda c: (-len(c), c[0]))
    lado = max(1, math.ceil(math.sqrt(len(componentes))))
    pos = {}
    for k, nos in enumerate(componentes):
        cx, cy = (k % lado) * 2.2, (k // lado) * 2.2
        raio = 0.2 + 0.8 * min(1.0, len(nos) / 40)
        for j, no in enumerate(nos):
            ang = 2 * math.pi * j / len(nos)
            pos[no] = (cx + raio * math.cos(ang), cy + raio * math.sin(ang))
    if not pos:
        return {}
    xs, ys = [x for x, _ in pos.values()], [y for _, y in pos.values()]
    mx, my = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    meia = max(max(xs) - min(xs), max(ys) - min(ys), 1e-9) / 2
    return {no: (round((x - mx) / meia, 3), round((y - my) / meia, 3)) for no, (x, y) in pos.items()}
