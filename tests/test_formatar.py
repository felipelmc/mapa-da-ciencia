"""As frases em português: números, contagens com acento e durações."""

from mapa_da_ciencia.formatar import contagem, duracao, num


def test_contagens_e_duracoes():
    assert num(4947, 0) == "4.947"
    assert contagem("vinculos", 7242) == "7.242 vínculos"
    assert contagem("topicos", 57) == "57 tópicos" and contagem("documentos", 4275) == "4.275 documentos"
    assert duracao(12) == "12 s" and duracao(95) == "1 min 35 s" and duracao(120) == "2 min"
    assert duracao(36329) == "10 h 5 min" and duracao(3600) == "1 h"
