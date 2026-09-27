from datetime import UTC, datetime, timedelta

import pytest
import yaml
from typer.testing import CliRunner

from mapa_da_ciencia.cli import app
from mapa_da_ciencia.config import ErroConfig, carregar_codebook, carregar_config
from mapa_da_ciencia.llm.perfis import PERFIS, sugerir_perfil
from mapa_da_ciencia.manifesto import registrar_execucao, status_das_etapas, ultima_execucao
from mapa_da_ciencia.projeto import Projeto, ProjetoNaoEncontrado

runner = CliRunner()


@pytest.fixture
def projeto(tmp_path):
    return Projeto.criar(tmp_path / "piloto", modelo="ciencia-politica", perfil=PERFIS["padrao"])


def test_criar_projeto_gera_arquivos_validos(projeto):
    raiz = projeto.raiz
    for nome in ("mapa.yaml", "codebook.yaml", ".gitignore", ".env.exemplo"):
        assert (raiz / nome).exists(), nome
    for sub in ("brutos", "dados", "execucoes", "saida"):
        assert (raiz / sub).is_dir(), sub
    assert ".env" in (raiz / ".gitignore").read_text() and "validacao/" in (raiz / ".gitignore").read_text()
    cfg = projeto.config
    assert cfg.nome == "piloto"
    assert len(cfg.fontes.scielo.revistas) == 10
    assert cfg.recorte.anos == (2010, 2025)
    assert cfg.recorte.idioma_analise == "en"
    assert cfg.modelos.classificacao.modelo == "qwen3.5:9b"
    assert len(projeto.codebook.variaveis) == 6


def test_modelo_vazio_tambem_e_valido(tmp_path):
    p = Projeto.criar(tmp_path / "Meu Projeto!", modelo="vazio", perfil=PERFIS["leve"])
    assert p.config.nome == "meu_projeto"
    assert p.config.modelos.classificacao.modelo == "qwen3.5:4b"
    assert p.codebook.variaveis[0].id == "abordagem"


def test_nao_sobrescreve_projeto_existente(projeto):
    with pytest.raises(ErroConfig, match="Já existe"):
        Projeto.criar(projeto.raiz, modelo="vazio", perfil=PERFIS["leve"])


def test_abrir_procura_nas_pastas_acima(projeto):
    sub = projeto.raiz / "dados" / "algo"
    sub.mkdir(parents=True)
    assert Projeto.abrir(sub).raiz == projeto.raiz


def test_abrir_sem_projeto(tmp_path):
    with pytest.raises(ProjetoNaoEncontrado, match="mapa novo"):
        Projeto.abrir(tmp_path)


def test_erro_de_config_explica_o_campo(projeto):
    arq = projeto.raiz / "mapa.yaml"
    dados = yaml.safe_load(arq.read_text())
    dados["recorte"]["anos"] = [2025, 2010]
    dados["fontes"]["scielo"]["revistaz"] = []
    arq.write_text(yaml.safe_dump(dados, allow_unicode=True))
    with pytest.raises(ErroConfig) as exc:
        carregar_config(arq)
    msg = str(exc.value)
    assert "recorte.anos" in msg
    assert "fontes.scielo.revistaz: campo desconhecido" in msg


def test_codebook_rejeita_categorica_sem_categorias(tmp_path):
    arq = tmp_path / "codebook.yaml"
    arq.write_text(
        "nome: x\nversao: '1'\ninstrucoes: y\nvariaveis:\n"
        "  - {id: metodo, rotulo: Método, tipo: categorica, pergunta: 'Qual?', categorias: []}\n"
    )
    with pytest.raises(ErroConfig, match="pelo menos 2 categorias"):
        carregar_codebook(arq)


def test_hash_do_codebook_muda_com_a_definicao(projeto):
    cb = projeto.codebook
    original = cb.hash()
    assert original == projeto.codebook.hash()
    alterado = cb.model_copy(update={"instrucoes": cb.instrucoes + " Seja breve."})
    assert alterado.hash() != original


def test_perfil_sugerido_pela_memoria():
    assert sugerir_perfil(4).nome == "leve"
    assert sugerir_perfil(12).nome == "leve"
    assert sugerir_perfil(24).nome == "padrao"
    assert sugerir_perfil(64).nome == "forte"


def test_manifesto_de_execucao(projeto):
    assert ultima_execucao(projeto, "coleta") is None
    fim = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)
    registrar_execucao(projeto, "coleta", inicio=fim - timedelta(seconds=90), fim=fim, contagens={"documentos": 25})
    m = ultima_execucao(projeto, "coleta")
    assert m["duracao_s"] == 90
    assert m["contagens"] == {"documentos": 25}
    assert m["hash_config"]
    assert status_das_etapas(projeto)["topicos"] is None
    with pytest.raises(ValueError):
        registrar_execucao(projeto, "etapa_inexistente", inicio=fim, fim=fim)


def test_cli_novo_e_status(tmp_path):
    destino = tmp_path / "demo"
    r = runner.invoke(app, ["novo", str(destino), "--perfil", "leve"])
    assert r.exit_code == 0, r.output
    assert "Projeto criado" in r.output
    r = runner.invoke(app, ["status", "--projeto", str(destino)])
    assert r.exit_code == 0, r.output
    assert "Ciência política no SciELO Brasil" in r.output
    assert "pendente" in r.output


def test_cli_erros_sao_amigaveis(tmp_path):
    r = runner.invoke(app, ["status", "--projeto", str(tmp_path)])
    assert r.exit_code == 1
    assert "Nenhum projeto encontrado" in r.output
    assert "Traceback" not in r.output
    r = runner.invoke(app, ["novo", str(tmp_path / "x"), "--perfil", "turbo"])
    assert r.exit_code == 1
    assert "Perfil desconhecido" in r.output
