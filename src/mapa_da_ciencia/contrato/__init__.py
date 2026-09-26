"""Contrato de dados entre o pipeline (Python) e a interface (frontend).

O painel local e o site publicado leem exatamente os mesmos arquivos JSON de
`saida/dados/`. Os modelos em `modelos.py` são a fonte da verdade: deles saem os
JSON Schemas de `contrato/schema/` e, a partir destes, os tipos TypeScript do frontend.
"""

from mapa_da_ciencia.contrato.modelos import VERSAO_CONTRATO

__all__ = ["VERSAO_CONTRATO"]
