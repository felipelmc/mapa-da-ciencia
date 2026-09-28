"""Formatação de números para mensagens em português (vírgula decimal)."""

from __future__ import annotations


def num(valor: float, casas: int = 1) -> str:
    """`num(13.24)` → `"13,2"`; `num(4947, 0)` → `"4.947"`."""
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "\0").replace(".", ",").replace("\0", ".")


def periodo(anos: tuple[int, int] | list[int]) -> str:
    """`(2024, 2024)` → `"2024"`; `(2010, 2025)` → `"2010–2025"`."""
    inicio, fim = anos
    return str(inicio) if inicio == fim else f"{inicio}–{fim}"


def gb(valor: float) -> str:
    return f"{num(valor)} GB"


# os nomes das contagens dos manifestos, como aparecem para quem lê (as chaves não têm acento)
NOME_DA_CONTAGEM = {
    "topicos": "tópicos",
    "vinculos": "vínculos",
    "instituicoes": "instituições",
    "afiliacoes": "afiliações",
    "requisicoes": "requisições",
    "citacoes": "citações",
    "macrotemas": "macrotemas",
}


def contagem(chave: str, valor: float) -> str:
    """`contagem("vinculos", 7242)` → `"7.242 vínculos"`."""
    return f"{num(valor, 0)} {NOME_DA_CONTAGEM.get(chave, chave.replace('_', ' '))}"


def duracao(segundos: float) -> str:
    """`duracao(36329)` → `"10 h 5 min"`; `duracao(95)` → `"1 min 35 s"`; `duracao(12)` → `"12 s"`."""
    s = round(segundos)
    if s < 60:
        return f"{s} s"
    if s < 3600:
        return f"{s // 60} min {s % 60} s" if s % 60 else f"{s // 60} min"
    return f"{s // 3600} h {s % 3600 // 60} min" if s % 3600 // 60 else f"{s // 3600} h"
