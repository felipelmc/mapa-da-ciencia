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
