"""Gerador de dados de exemplo do contrato: **sintéticos e fictícios**, mas plausíveis.

Serve para desenvolver e testar o frontend sem rodar o pipeline, para a demonstração
`mapa painel --exemplo` e para oficinas. Títulos, autores, resumos e afiliações são
inventados; as revistas e instituições são reais só para o exemplo parecer familiar.
É determinístico: a mesma semente gera exatamente os mesmos arquivos.
"""

from __future__ import annotations

import colorsys
import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import resources

import yaml

from mapa_da_ciencia import __version__
from mapa_da_ciencia.config import Codebook
from mapa_da_ciencia.contrato import modelos as m

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
    cor: str
    subarea: str
    revistas: tuple[str, ...]  # revistas preferidas
    topicos: tuple[tuple[str, str, float], ...]  # (rótulo, palavras-chave, tendência de -1 a 1)


MACROS = [
    _Macro(
        "Instituições políticas",
        "#5B8DEF",
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
        "#E0A43B",
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
        "#D9667B",
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
        "#4FB39E",
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
        "#8E7CE8",
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
        "#C9A06B",
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
        "#5FB7D4",
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


def _cor_variante(base: str, i: int, total: int) -> str:
    r, g, b = (int(base[k : k + 2], 16) / 255 for k in (1, 3, 5))
    h, lum, s = colorsys.rgb_to_hls(r, g, b)
    passo = (i - (total - 1) / 2) / max(total - 1, 1)
    h = (h + passo * 0.06) % 1
    lum = min(max(lum + passo * 0.16, 0.25), 0.8)
    r, g, b = colorsys.hls_to_rgb(h, lum, s)
    return "#" + "".join(f"{round(c * 255):02X}" for c in (r, g, b))


def _escolher(rng: random.Random, pesos: dict[str, float]) -> str:
    return rng.choices(list(pesos), weights=list(pesos.values()))[0]


def _codebook() -> Codebook:
    texto = resources.files("mapa_da_ciencia.modelos_projeto").joinpath("codebook-exemplo.yaml").read_text("utf-8")
    return Codebook.model_validate(yaml.safe_load(texto))


def gerar_exemplo(n_docs: int = 1500, semente: int = 42) -> tuple[dict[str, m.BaseModel], dict[str, m.Fragmento]]:
    """Gera todos os arquivos do contrato. Devolve (arquivos por nome, fragmentos de detalhes)."""
    rng = random.Random(semente)
    cb = _codebook()

    # ---- tópicos: posição no plano, cor e tendência
    topicos_def = []  # (id, macro_id, rotulo, palavras, tendência, centro, cor)
    for mi, macro in enumerate(MACROS):
        ang = 2 * math.pi * mi / len(MACROS)
        cx, cy = 6.5 * math.cos(ang), 6.5 * math.sin(ang)
        for ti, (rotulo, palavras, tend) in enumerate(macro.topicos):
            a2 = ang + (ti - 1.5) * 0.9
            centro = (cx + 1.9 * math.cos(a2), cy + 1.9 * math.sin(a2))
            cor = _cor_variante(macro.cor, ti, len(macro.topicos))
            topicos_def.append((len(topicos_def), mi, rotulo, palavras.split(), tend, centro, cor))

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
        vizinho = rng.random() < 0.15
        x, y = cx + rng.gauss(0, 0.5 if not vizinho else 0.9), cy + rng.gauss(0, 0.5 if not vizinho else 0.9)
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
                "topico": tid,
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
            if rng.random() < 0.05:  # às vezes o modelo parafraseia: evidência aproximada, sem posição
                evid[var] = m.Evidencia(valor=valor, evidencia=frase.lower()[:-3], status="aproximada")
            else:
                ini = resumo.index(frase)
                evid[var] = m.Evidencia(
                    valor=valor, evidencia=frase, status="literal", inicio=ini, fim=ini + len(frase)
                )
        licenca = rng.choices(["cc-by", "cc-by-nc", "desconhecida"], [45, 50, 5])[0]
        detalhes[d["id"]] = m.Detalhe(
            resumo=resumo if licenca != "desconhecida" else None,
            idioma=d["idioma"],
            palavras_chave=kw,
            autores=[a.replace(",", "") for a in d["autores"]],
            url=f"https://doi.org/{d['doi']}" if d["doi"] else None,
            licenca=licenca,
            licenca_fonte="openalex" if licenca != "desconhecida" else "nenhuma",
            evidencias=evid,
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

    # ---- afiliações (contagem fracionária: soma 1 por documento)
    insts = [m.Instituicao(id=i[0], nome=i[1], sigla=i[2], uf=i[3], pais=i[4]) for i in INSTITUICOES]
    ufs = sorted({i.uf for i in insts if i.uf})
    paises = sorted({i.pais for i in insts})
    pesos_inst = [i[5] for i in INSTITUICOES]
    af = defaultdict(list)
    for di, d in enumerate(docs):
        escolhidas = {rng.choices(range(len(insts)), pesos_inst)[0] for _ in d["autores"]}
        for ii in sorted(escolhidas):
            inst = insts[ii]
            af["doc"].append(di)
            af["instituicao"].append(ii)
            af["uf"].append(ufs.index(inst.uf) if inst.uf else -1)
            af["pais"].append(paises.index(inst.pais))
            af["peso"].append(round(1 / len(escolhidas), 6))
    afiliacoes = m.Afiliacoes(
        n=len(af["doc"]),
        colunas=m.ColunasAfiliacoes(**af),
        dicionarios=m.DicionariosAfiliacoes(instituicao=insts, uf=ufs, pais=paises),
    )

    # ---- topicos.json
    total_ano = Counter(d["ano"] for d in docs)
    topicos = []
    for tid, mi, rotulo, palavras, _, (cx, cy), cor in topicos_def:
        membros = [d for d in docs if d["topico"] == tid]
        por_ano = Counter(d["ano"] for d in membros)
        centro_real = (sum(d["x"] for d in membros) / len(membros), sum(d["y"] for d in membros) / len(membros))
        repr_ = sorted(membros, key=lambda d: (d["x"] - cx) ** 2 + (d["y"] - cy) ** 2)[:5]
        topicos.append(
            m.Topico(
                id=tid,
                macro_id=mi,
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
            )
        )
    macrotemas = [
        m.Macrotema(id=mi, rotulo=mc.rotulo, cor=mc.cor, topicos=[t[0] for t in topicos_def if t[1] == mi])
        for mi, mc in enumerate(MACROS)
    ]
    n_viz = sum(d["atribuicao"] == "vizinho" for d in docs)
    topicos_arq = m.Topicos(
        anos=ANOS,
        total_por_ano=[total_ano[a] for a in ANOS],
        parametros={"modelo_embeddings": "exemplo", "min_cluster_size": 10, "semente": semente},
        estabilidade_ari=0.81,
        macrotemas=macrotemas,
        topicos=topicos,
        outliers=m.Outliers(n=n_viz, reatribuidos=n_viz),
    )

    # ---- codebook, classificações e validação
    codebook = m.CodebookContrato(
        nome=cb.nome,
        versao=cb.versao,
        hash=cb.hash(),
        instrucoes=cb.instrucoes,
        variaveis=[
            m.VariavelContrato(
                id=v.id,
                rotulo=v.rotulo,
                tipo=v.tipo,
                pergunta=v.pergunta,
                categorias=[
                    m.CategoriaContrato(
                        valor=c.valor, rotulo=c.rotulo or c.valor.replace("_", " "), definicao=c.definicao
                    )
                    for c in v.categorias
                ],
            )
            for v in cb.variaveis
        ],
    )
    contagens_cls = {
        v.id: dict(Counter(str(d["cls"][v.id]).lower() if v.tipo == "booleana" else d["cls"][v.id] for d in docs))
        for v in vars_cls
    }
    n_evid = sum(len(det.evidencias) for det in detalhes.values())
    n_lit = sum(e.status == "literal" for det in detalhes.values() for e in det.evidencias.values())
    classificacoes = m.Classificacoes(
        modelo="exemplo",
        hash_codebook=cb.hash(),
        cobertura=1.0,
        evidencia_literal=round(n_lit / n_evid, 4),
        contagens=contagens_cls,
    )
    validacao = _validacao_sintetica(rng, docs, vars_cls, dic_cls)

    # ---- agregados (gabarito do filtro cruzado)
    tar = Counter((d["topico"], d["ano"], d["revista"]) for d in docs)
    soma_uf: dict[str, float] = defaultdict(float)
    soma_pais: dict[str, float] = defaultdict(float)
    for uf, pais, peso in zip(af["uf"], af["pais"], af["peso"], strict=True):
        if uf >= 0:
            soma_uf[ufs[uf]] += peso
        soma_pais[paises[pais]] += peso
    agregados = m.Agregados(
        topico_ano_revista=[(t, a, r, n) for (t, a, r), n in sorted(tar.items())],
        uf={k: round(v, 4) for k, v in sorted(soma_uf.items())},
        pais={k: round(v, 4) for k, v in sorted(soma_pais.items())},
    )

    revistas = m.Revistas(
        revistas=[
            m.Revista(id=a, issn=issn, titulo=t, areas=["Ciências Humanas"], n=sum(d["revista"] == a for d in docs))
            for a, issn, t in REVISTAS
        ]
    )
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
            com_afiliacao=len(docs),
        ),
        arquivos=["manifesto", *arquivos, "detalhes"],
        execucao=m.ExecucaoInfo(
            versao_pacote=__version__,
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


def _validacao_sintetica(rng, docs, vars_cls, dic_cls) -> m.Validacao:
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
                comparacao="humano × exemplo",
                n=len(amostra),
                concordancia=round(po, 4),
                kappa=round(kappa, 4),
                kappa_ic95=(round(max(kappa - 0.12, -1), 4), round(min(kappa + 0.1, 1), 4)),
                pabak=round(pabak, 4),
                alfa=None,
                matriz=m.Matriz(rotulos=rotulos, valores=matriz),
            )
        )
        for d, h, mo in zip(amostra, humano, modelo, strict=True):
            if h != mo and len(divergencias) < 40:
                divergencias.append(
                    m.Divergencia(doc=d["id"], variavel=v.id, humano=h, modelo=mo, evidencia="(ver resumo)")
                )
    return m.Validacao(
        amostra=m.AmostraInfo(n=len(amostra), estratificar_por="topico", semente=7),
        metricas=metricas,
        modelos=["exemplo"],
        divergencias=divergencias,
    )
