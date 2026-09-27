"""Conferência da evidência (classificacao/evidencia.py)."""

from mapa_da_ciencia.classificacao.evidencia import conferir

RESUMO = (
    "Este artigo analisa  a “polarização afetiva” no Brasil entre 2014 e 2022 — com dados do ESEB — e mostra "
    "que eleitores de esquerda e de direita se afastaram."
)


def test_literal_com_offsets_no_original():
    c = conferir("A polarização afetiva no Brasil", RESUMO)
    assert (c.status, c.campo) == ("literal", "resumo")
    assert RESUMO[c.inicio : c.fim] == "a “polarização afetiva” no Brasil"
    # travessão, aspas e espaços duplos não atrapalham
    c = conferir('analisa a "polarização afetiva" no Brasil entre 2014 e 2022 - com dados do ESEB', RESUMO)
    assert c.status == "literal" and RESUMO[c.inicio : c.fim].startswith("analisa  a “polarização")
    assert RESUMO[c.inicio : c.fim].endswith("ESEB")


def test_bordas_e_caixa():
    c = conferir("  «Eleitores de esquerda e de direita se afastaram.»  ", RESUMO)
    assert c.status == "literal" and RESUMO[c.inicio : c.fim] == "eleitores de esquerda e de direita se afastaram"


def test_aproximada_e_ausente():
    c = conferir("eleitores da esquerda e de direita se afastaram", RESUMO)
    assert c.status == "aproximada" and "eleitores de esquerda" in RESUMO[c.inicio : c.fim]
    assert conferir("o artigo usa entrevistas em profundidade com deputados", RESUMO).status == "ausente"


def test_titulo():
    c = conferir("Polarização afetiva", "Outro resumo qualquer.", "Polarização afetiva no Brasil")
    assert (c.status, c.campo, c.inicio) == ("literal", "titulo", None)


def test_vazia_dispensada_ou_ausente():
    assert conferir("", RESUMO, sem_informacao=True).status == "dispensada"
    assert conferir("", RESUMO).status == "ausente"
    assert conferir("ok", RESUMO, sem_informacao=True).status == "ausente"  # curta demais, mas não vazia
    assert conferir("qualquer coisa", "").status == "ausente"


LONGO = (
    "O artigo examina a formação de coalizões nos governos estaduais brasileiros entre 1995 e 2018. A partir de "
    "um banco de dados original sobre a composição dos secretariados, mostra que os governadores distribuem as "
    "pastas de modo proporcional ao peso legislativo dos partidos aliados, mas reservam as áreas de maior "
    "orçamento para o próprio partido. Os resultados indicam que a lógica da coalizão no plano estadual se "
    "aproxima da observada no governo federal, com diferenças relevantes quanto à estabilidade dos acordos e à "
    "duração dos secretários nos cargos, e que o calendário eleitoral altera a distribuição das pastas. "
) * 2


def test_letras_soltas_num_resumo_longo_nao_casam():
    """Com o resumo inteiro como alvo, letras espalhadas somariam 90% de qualquer frase inventada."""
    for inventada in ("survey com amostra nacional", "os dados mostram a importância das redes"):
        assert conferir(inventada, LONGO).status == "ausente"


def test_aproximada_num_resumo_longo_marca_so_o_trecho():
    c = conferir("os governadores distribuem as pastas de modo proporcional ao peso eleitoral dos partidos", LONGO)
    assert c.status == "aproximada"
    marcado = LONGO[c.inicio : c.fim]
    assert marcado.startswith("os governadores distribuem") and marcado.endswith("dos partidos")


def test_trecho_cortado_com_reticencias():
    c = conferir("formação de coalizões nos governos estaduais… a lógica da coalizão no plano estadual", LONGO)
    assert c.status == "aproximada"
    marcado = LONGO[c.inicio : c.fim]
    assert marcado.startswith("formação de coalizões") and marcado.endswith("no plano estadual")
    # um pedaço inventado não passa
    inventado = "formação de coalizões nos governos estaduais ... survey com amostra nacional"
    assert conferir(inventado, LONGO).status == "ausente"
    # pedaços do título e do resumo
    titulo = "Coalizões estaduais no Brasil"
    c = conferir("Coalizões estaduais ... a lógica da coalizão no plano estadual", LONGO, titulo)
    assert c.status == "aproximada" and LONGO[c.inicio : c.fim] == "a lógica da coalizão no plano estadual"
