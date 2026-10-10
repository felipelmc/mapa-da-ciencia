"""O relatório que compara duas rodadas de um projeto (scripts/comparar_rodadas.py)."""

import importlib.util
from pathlib import Path

from mapa_da_ciencia.documento import Documento, Texto

RAIZ = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("comparar_rodadas", RAIZ / "scripts" / "comparar_rodadas.py")
comparar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparar)

PT = "O artigo analisa as coalizões de governo no Brasil e mostra que os partidos não recebem ministérios."
FR = "Cet article analyse les coalitions de gouvernement au Brésil et montre que les partis ne reçoivent pas."


def _doc(id_, resumos):
    return Documento(
        id=id_,
        fonte="articlemeta",
        tipo="research-article",
        ano=2020,
        titulos=[Texto(idioma="pt", texto=f"Título de {id_}")],
        resumos=[Texto(idioma=i, texto=t) for i, t in resumos],
    )


def test_documentos_resumos_e_textos_que_mudaram():
    antes = {
        "a": _doc("a", [("pt", PT), ("es", FR)]),
        "b": _doc("b", [("pt", "Resumo")]),
        "c": _doc("c", [("pt", PT)]),
    }
    depois = {"a": _doc("a", [("pt", PT), ("fr", FR)]), "b": _doc("b", [])}
    texto = "\n".join(comparar.secao_documentos(antes, depois, ("pt", "en")))
    assert "3 → 2 documentos; saíram 1, entraram 0." in texto and "- saiu: c" in texto
    assert "### Resumos que saíram (1)" in texto and "- b (pt): Resumo" in texto
    assert "### Resumos que mudaram de idioma (1)" in texto and "- a: es → fr" in texto
    assert "### Texto a classificar mudou (1)" in texto  # b perdeu o único resumo


def test_jaccard():
    assert comparar.jaccard({"a", "b"}, {"b", "c"}) == 1 / 3
    assert comparar.jaccard(set(), set()) == 1.0
