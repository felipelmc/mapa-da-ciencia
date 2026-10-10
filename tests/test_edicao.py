"""A edição do YAML pelo painel: só o que mudou é trocado, com os comentários, e os valores vazios não entram."""

import pytest
from pydantic import BaseModel

from mapa_da_ciencia.config import ErroConfig
from mapa_da_ciencia.edicao import editar_yaml

YAML = """\
# comentário do topo
nome: exemplo  # comentário na linha
itens:
  - id: a
    rotulo: Primeiro
  - id: b
    rotulo: Segundo
    exemplos:
      - um
"""


class _Item(BaseModel):
    id: str
    rotulo: str | None = None
    exemplos: list[str] = []


class _Doc(BaseModel):
    nome: str
    itens: list[_Item]


@pytest.fixture
def arquivo(tmp_path):
    caminho = tmp_path / "doc.yaml"
    caminho.write_text(YAML, encoding="utf-8")
    return caminho


def _completo() -> dict:
    """O documento como a leitura o devolve: com os padrões preenchidos."""
    return _Doc.model_validate({"nome": "exemplo", "itens": [{"id": "a", "rotulo": "Primeiro"},
                               {"id": "b", "rotulo": "Segundo", "exemplos": ["um"]}]}).model_dump()  # fmt: skip


def test_sem_omitir_os_padroes_entram(arquivo):
    editar_yaml(arquivo, _completo(), _Doc.model_validate, substituir=True)
    assert "exemplos: []" in arquivo.read_text(encoding="utf-8")


def test_omitir_vazios_deixa_o_arquivo_igual(arquivo):
    editar_yaml(arquivo, _completo(), _Doc.model_validate, substituir=True, omitir_vazios=True)
    assert arquivo.read_text(encoding="utf-8") == YAML


def test_omitir_vazios_apaga_e_nao_cria(arquivo):
    doc = _completo()
    doc["itens"][1]["exemplos"] = []  # a pessoa tirou o último exemplo
    doc["itens"].append({"id": "c", "rotulo": None, "exemplos": []})  # um item novo, com os padrões
    editar_yaml(arquivo, doc, _Doc.model_validate, substituir=True, omitir_vazios=True)
    texto = arquivo.read_text(encoding="utf-8")
    assert texto.startswith("# comentário do topo\nnome: exemplo  # comentário na linha")
    assert "exemplos" not in texto and "rotulo: null" not in texto and "- id: c" in texto


def test_invalido_nao_grava(arquivo):
    with pytest.raises(ErroConfig, match=r"doc\.yaml ficaria inválido"):
        editar_yaml(arquivo, {"nome": None, "itens": []}, _Doc.model_validate, substituir=True)
    assert arquivo.read_text(encoding="utf-8") == YAML
