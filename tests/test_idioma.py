from itertools import combinations

import pytest

from mapa_da_ciencia.idioma import PALAVRAS, acertos, detectar


def test_as_listas_de_palavras_nao_se_cruzam():
    for a, b in combinations(PALAVRAS, 2):
        assert not PALAVRAS[a] & PALAVRAS[b], (a, b)


@pytest.mark.parametrize(
    ("texto", "idioma"),
    [
        (
            "O artigo analisa as coalizões de governo no Brasil e mostra que os partidos não recebem ministérios "
            "na proporção das cadeiras, o que também afeta a disciplina das bancadas.",
            "pt",
        ),
        (
            "El artículo analiza las coaliciones de gobierno en Brasil y muestra que los partidos no reciben "
            "ministerios en proporción a sus escaños, lo que también afecta la disciplina de las bancadas.",
            "es",
        ),
        (
            "This article analyzes government coalitions in Brazil and shows that parties do not receive "
            "ministries in proportion to their seats, which also affects the discipline of the delegations.",
            "en",
        ),
        (
            "Cet article analyse les coalitions de gouvernement au Brésil et montre que les partis ne reçoivent "
            "pas des ministères en proportion de leurs sièges, ce qui affecte aussi la discipline des groupes.",
            "fr",
        ),
    ],
)
def test_reconhece_cada_idioma(texto, idioma):
    assert detectar(texto) == idioma


def test_as_elisoes_do_frances_contam():
    assert acertos("l'État et l'Église")["fr"] == 3  # l, et, l


def test_texto_curto_ou_ambiguo_fica_sem_idioma():
    assert detectar("Este ensaio visa articular a poética com algumas questões") is None  # curto
    assert detectar("") is None
    # palavras bastantes, mas quase nenhuma funcional: nomes próprios e números
    nomes = "Brasil Argentina Chile Uruguai Paraguai 2010 2012 2014 Lula Dilma Temer Bolsonaro FHC PT PSDB"
    assert detectar(nomes) is None
