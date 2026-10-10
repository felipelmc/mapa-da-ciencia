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


def test_tirar_a_ultima_entrada_de_uma_secao_nao_leva_o_cabecalho_da_seguinte(tmp_path):
    arquivo = tmp_path / "x.yaml"
    arquivo.write_text(
        "itens:\n  a:\n    v: 1\n  b:\n    v: 2\n\n  # --- outra seção ---\n  c:\n    v: 3\n", encoding="utf-8"
    )
    editar_yaml(arquivo, {"itens": {"a": {"v": 1}, "c": {"v": 3}}}, lambda d: d, substituir=True)
    assert arquivo.read_text(encoding="utf-8") == "itens:\n  a:\n    v: 1\n\n  # --- outra seção ---\n  c:\n    v: 3\n"


def test_tirar_a_primeira_entrada_passa_o_cabecalho_para_a_seguinte(tmp_path):
    arquivo = tmp_path / "x.yaml"
    arquivo.write_text("topicos:\n  1:\n    rotulo: A\n\n  # --- seção ---\n  2:\n    rotulo: B\n", encoding="utf-8")
    editar_yaml(arquivo, {"topicos": {2: {"rotulo": "B"}}}, lambda d: d, substituir=True)
    assert arquivo.read_text(encoding="utf-8") == "topicos:\n  # --- seção ---\n  2:\n    rotulo: B\n"


def test_tirar_a_unica_entrada_passa_o_cabecalho_para_a_chave_de_cima(tmp_path):
    arquivo = tmp_path / "x.yaml"
    arquivo.write_text(
        "topicos:\n  1:\n    rotulo: A\n\n# --- macrotemas, escritos à mão ---\nmacrotemas:\n  2:\n    rotulo: M\n",
        encoding="utf-8",
    )
    editar_yaml(arquivo, {"topicos": {1: None}}, lambda d: d, substituir=False, omitir_vazios=True)
    texto = arquivo.read_text(encoding="utf-8")
    assert "rotulo: A" not in texto
    assert "# --- macrotemas, escritos à mão ---\nmacrotemas:\n  2:\n    rotulo: M\n" in texto


def test_tirar_uma_entrada_com_comentario_na_linha_leva_so_o_da_linha(tmp_path):
    arquivo = tmp_path / "x.yaml"
    arquivo.write_text(
        "topicos:\n  1:\n    rotulo: A\n  2:\n    rotulo: B  # da entrada\n\n  # --- seção ---\n  3:\n    rotulo: C\n",
        encoding="utf-8",
    )
    editar_yaml(arquivo, {"topicos": {1: {"rotulo": "A"}, 3: {"rotulo": "C"}}}, lambda d: d, substituir=True)
    assert arquivo.read_text(encoding="utf-8") == (
        "topicos:\n  1:\n    rotulo: A\n\n  # --- seção ---\n  3:\n    rotulo: C\n"
    )


def test_tirar_um_item_da_lista_mantem_o_cabecalho_do_seguinte(tmp_path):
    arquivo = tmp_path / "codebook.yaml"
    arquivo.write_text(
        "variaveis:\n  - id: a\n    pergunta: A?\n\n  - id: b\n    pergunta: B?\n\n"
        "  # --- Seção 2: método ---\n  - id: c\n    pergunta: C?\n",
        encoding="utf-8",
    )
    novo = {"variaveis": [{"id": "a", "pergunta": "A?"}, {"id": "c", "pergunta": "C?"}]}
    editar_yaml(arquivo, novo, lambda d: d, substituir=True, omitir_vazios=True)
    assert arquivo.read_text(encoding="utf-8") == (
        "variaveis:\n  - id: a\n    pergunta: A?\n\n  # --- Seção 2: método ---\n  - id: c\n    pergunta: C?\n"
    )
