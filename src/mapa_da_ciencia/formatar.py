"""Formatação de números para mensagens em português (vírgula decimal)."""

from __future__ import annotations


def num(valor: float, casas: int = 1) -> str:
    """`num(13.24)` → `"13,2"`; `num(4947, 0)` → `"4.947"`."""
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "\0").replace(".", ",").replace("\0", ".")


def gb(valor: float) -> str:
    return f"{num(valor)} GB"
