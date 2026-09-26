"""Corpus sintético com temas plantados, para testar o agrupamento sem depender de dados reais.

Cada tema tem um vocabulário próprio, em inglês e em português (listas paralelas). Com os embeddings falsos
de saco de palavras do Ollama falso (`conftest.vetor_falso`), documentos do mesmo tema ficam perto.
"""

from __future__ import annotations

import random

from mapa_da_ciencia.documento import Afiliacao, Autor, AutoriaOpenAlex, Documento, InstituicaoOpenAlex, Texto

TEMAS = {
    "legislativo": (
        "congress coalition legislative agenda presidentialism rollcall committees parties bills deputies senate",
        "congresso coalizão legislativa agenda presidencialismo votação comissões partidos projetos deputados senado",
    ),
    "eleicoes": (
        "elections voters turnout campaign ballots electoral polls candidates vote municipal runoff",
        "eleições eleitores comparecimento campanha urnas eleitoral pesquisas candidatos voto municipal segundo",
    ),
    "seguranca": (
        "police violence crime prisons homicide security incarceration drugs militias punishment gangs",
        "polícia violência crime prisões homicídio segurança encarceramento drogas milícias punição facções",
    ),
    "china": (
        "china brics trade diplomacy cooperation investment beijing emerging powers multilateral summit",
        "china brics comércio diplomacia cooperação investimento pequim emergentes potências multilateral cúpula",
    ),
    "saude": (
        "health hospitals sus vaccination epidemic doctors patients pandemic care clinics nurses",
        "saúde hospitais sus vacinação epidemia médicos pacientes pandemia cuidado clínicas enfermeiros",
    ),
    "teoria": (
        "democracy republicanism liberalism deliberation justice legitimacy freedom rawls habermas sovereignty",
        "democracia republicanismo liberalismo deliberação justiça legitimidade liberdade rawls habermas soberania",
    ),
}
GENERICAS = (
    "study analysis data results article brazil approach evidence research findings",
    "estudo análise dados resultados artigo brasil abordagem evidências pesquisa achados",
)
REVISTAS = ["dados", "op", "rbcpol", "rsocp"]


def _frase(rng: random.Random, tema: str, n: int) -> tuple[str, str]:
    en, pt = (TEMAS[tema][0].split(), TEMAS[tema][1].split())
    gen_en, gen_pt = GENERICAS[0].split(), GENERICAS[1].split()
    palavras_en, palavras_pt = [], []
    for _ in range(n):
        if rng.random() < 0.72:
            i = rng.randrange(len(en))
            palavras_en.append(en[i])
            palavras_pt.append(pt[i])
        else:
            i = rng.randrange(len(gen_en))
            palavras_en.append(gen_en[i])
            palavras_pt.append(gen_pt[i])
    return " ".join(palavras_en), " ".join(palavras_pt)


# afiliações escolhidas pelo índice do documento (sem gastar sorteios: os temas ficam iguais). A cada 6 documentos,
# um sem afiliação; a última instituição não tem registro no OpenAlex e fica "não identificada".
AFILIACOES = [
    ("Universidade de São Paulo", "São Paulo", "BR", "I1001"),
    ("Universidade Federal de Minas Gerais", "Minas Gerais", "BR", "I1002"),
    ("Universidade de Brasília", "Distrito Federal", "BR", "I1003"),
    ("Universidad de Buenos Aires", None, "AR", "I1004"),
    ("Centro de Estudos Sem Registro", "Rio de Janeiro", "BR", None),
]


def _afiliacao(i: int) -> dict:
    autor = Autor(nome="Ana", sobrenome=f"Autora{i % 37}", afiliacoes=[] if i % 6 == 5 else ["aff1"])
    if i % 6 == 5:
        return {"autores": [autor]}
    nome, uf, pais, id_ = AFILIACOES[i % len(AFILIACOES)]
    instituicoes = [InstituicaoOpenAlex(id=id_, nome=nome, pais=pais, tipo="education")] if id_ else []
    return {
        "autores": [autor],
        "afiliacoes": [Afiliacao(id="aff1", instituicao=nome, uf=uf, pais=pais, fonte="v240")],
        "autorias_openalex": [AutoriaOpenAlex(nome=f"Ana Autora{i % 37}", instituicoes=instituicoes)],
    }


def corpus_sintetico(n_por_tema: int = 50, semente: int = 1) -> tuple[list[Documento], dict[str, str]]:
    """Documentos e o tema plantado de cada um (id → tema). ~3% ficam só com resumo em português (reserva) e
    ~1% sem resumo (só título), como no piloto."""
    rng = random.Random(semente)
    docs, temas = [], {}
    for t, tema in enumerate(TEMAS):
        for j in range(n_por_tema):
            i = t * n_por_tema + j
            ano = 2010 + rng.randrange(16)
            titulo_en, titulo_pt = _frase(rng, tema, 6)
            resumo_en, resumo_pt = _frase(rng, tema, 40)
            sorteio = rng.random()
            resumos = [Texto(idioma="en", texto=resumo_en), Texto(idioma="pt", texto=resumo_pt)]
            if sorteio < 0.03:
                resumos = [Texto(idioma="pt", texto=resumo_pt)]
            elif sorteio < 0.04:
                resumos = []
            doc_id = f"S0000-0000{ano}000100{i:03d}"
            docs.append(
                Documento(
                    id=doc_id,
                    pid=doc_id,
                    fonte="articlemeta",
                    tipo="research-article",
                    ano=ano,
                    revista_acronimo=REVISTAS[i % len(REVISTAS)],
                    revista_issn=f"0000-000{i % len(REVISTAS)}",
                    titulos=[Texto(idioma="en", texto=titulo_en.capitalize()), Texto(idioma="pt", texto=titulo_pt)],
                    resumos=resumos,
                    licenca="cc-by",
                    **_afiliacao(i),
                )
            )
            temas[doc_id] = tema
    docs.sort(key=lambda d: d.id)
    return docs, temas
