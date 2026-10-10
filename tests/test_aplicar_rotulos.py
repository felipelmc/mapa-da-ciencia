"""Aplicar o rotulos.yaml sem refazer os tópicos e sem o modelo (topicos/aplicar.py), no corpus sintético."""

import json

import pytest
from corpus_sintetico import corpus_sintetico
from typer.testing import CliRunner

from mapa_da_ciencia.armazenamento import ARQUIVO, gravar_documentos
from mapa_da_ciencia.cli import app
from mapa_da_ciencia.config import ErroConfig
from mapa_da_ciencia.llm.perfis import PERFIS
from mapa_da_ciencia.manifesto import estados_das_etapas
from mapa_da_ciencia.projeto import Projeto
from mapa_da_ciencia.topicos.aplicar import aplicar_rotulos
from mapa_da_ciencia.topicos.pipeline import gerar_topicos
from mapa_da_ciencia.topicos.resultado import ARQUIVO_ATRIBUICOES, PASTA, Resultado


@pytest.fixture
def projeto(tmp_path, apis_falsas):
    p = Projeto.criar(tmp_path / "sintetico", modelo="vazio", perfil=PERFIS["leve"])
    docs, _ = corpus_sintetico(n_por_tema=40)
    gravar_documentos(docs, p.dados / ARQUIVO)
    gerar_topicos(p)
    return p


def test_aplicar_sem_o_modelo_e_sem_refazer(projeto, apis_falsas):
    resultado = Resultado.ler(projeto.dados / PASTA)
    alvo = resultado.topicos[0]
    macro = next(m for m in resultado.macrotemas if alvo.id in m.topicos)
    atribuicoes = (projeto.dados / PASTA / ARQUIVO_ATRIBUICOES).read_bytes()
    (projeto.raiz / "rotulos.yaml").write_text(
        f"topicos:\n  {alvo.id}:\n    rotulo: '  Um  rótulo à mão '\n    descricao: Escrita por uma pessoa.\n",
        encoding="utf-8",
    )
    assert estados_das_etapas(projeto)["topicos"]["rotulos_pendentes"] == 1
    chats = apis_falsas.chamadas["ollama_chat"]

    resumo = aplicar_rotulos(projeto)
    assert (resumo.aplicados, resumo.voltaram) == (1 + (len(macro.topicos) == 1), 0)
    assert apis_falsas.chamadas["ollama_chat"] == chats  # nenhuma chamada ao modelo
    assert (projeto.dados / PASTA / ARQUIVO_ATRIBUICOES).read_bytes() == atribuicoes  # os tópicos não mudam
    novo = next(t for t in Resultado.ler(projeto.dados / PASTA).topicos if t.id == alvo.id)
    assert (novo.rotulo, novo.descricao, novo.rotulo_fonte) == ("Um rótulo à mão", "Escrita por uma pessoa.", "manual")
    exportado = json.loads((projeto.saida / "dados" / "topicos.json").read_text(encoding="utf-8"))
    assert next(t for t in exportado["topicos"] if t["id"] == alvo.id)["rotulo"] == "Um rótulo à mão"
    assert "rotulos_pendentes" not in estados_das_etapas(projeto)["topicos"]

    # a entrada sai do rotulos.yaml: o rótulo volta às palavras-chave até a próxima `mapa topicos`
    (projeto.raiz / "rotulos.yaml").write_text("topicos: {}\n", encoding="utf-8")
    assert estados_das_etapas(projeto)["topicos"]["rotulos_pendentes"] >= 1
    resumo = aplicar_rotulos(projeto)
    assert resumo.voltaram >= 1
    novo = next(t for t in Resultado.ler(projeto.dados / PASTA).topicos if t.id == alvo.id)
    assert novo.rotulo_fonte == "palavras" and novo.rotulo == ", ".join(p for p, _ in alvo.palavras[:3])


def test_rotulo_vazio_e_entrada_sem_topico(projeto):
    (projeto.raiz / "rotulos.yaml").write_text("topicos:\n  0:\n    rotulo: '   '\n", encoding="utf-8")
    with pytest.raises(ErroConfig, match=r"rotulos\.yaml inválido"):
        aplicar_rotulos(projeto)
    (projeto.raiz / "rotulos.yaml").write_text("topicos:\n  999:\n    rotulo: Ninguém\n", encoding="utf-8")
    resumo = aplicar_rotulos(projeto)
    assert resumo.aplicados == 0 and any("tópico 999" in a for a in resumo.avisos)


def test_cli_aplicar_rotulos(projeto):
    alvo = Resultado.ler(projeto.dados / PASTA).topicos[1]
    (projeto.raiz / "rotulos.yaml").write_text(f"topicos:\n  {alvo.id}:\n    rotulo: Pela CLI\n", encoding="utf-8")
    raiz = str(projeto.raiz)
    status = CliRunner().invoke(app, ["status", "-P", raiz], env={"COLUMNS": "200"}).output
    assert "1 rótulo(s) do rotulos.yaml ainda não aplicado(s)" in status
    r = CliRunner().invoke(app, ["topicos", "--aplicar-rotulos", "--sem-rotulos", "-P", raiz])
    assert r.exit_code == 2 and "sem as outras opções" in r.output
    r = CliRunner().invoke(app, ["topicos", "--aplicar-rotulos", "-P", raiz], env={"COLUMNS": "200"})
    assert r.exit_code == 0, r.output
    assert "Rótulos aplicados" in r.output and "1 rótulo(s) aplicado(s)" in r.output
    status = CliRunner().invoke(app, ["status", "-P", raiz], env={"COLUMNS": "200"}).output
    assert "ainda não aplicado" not in status
