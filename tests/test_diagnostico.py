import httpx
import pytest
import respx

from mapa_da_ciencia.diagnostico import URLS_REDE, diagnosticar
from mapa_da_ciencia.formatar import gb, num
from mapa_da_ciencia.llm.base import ErroProvedor
from mapa_da_ciencia.llm.ollama import Ollama
from mapa_da_ciencia.llm.perfis import PERFIS
from mapa_da_ciencia.projeto import Projeto
from mapa_da_ciencia.recursos import cabe_na_memoria
from mapa_da_ciencia.rede import ler_env, user_agent, variavel

OLLAMA = "http://ollama.teste:11434"
GB = 1024**3


def _mock_ollama(router: respx.MockRouter, instalados: dict[str, float], carregados: dict[str, float] | None = None):
    router.get(f"{OLLAMA}/api/version").respond(json={"version": "0.34.2"})
    router.get(f"{OLLAMA}/api/tags").respond(
        json={"models": [{"name": n, "size": int(t * GB), "digest": "abc123def4567890"} for n, t in instalados.items()]}
    )
    router.get(f"{OLLAMA}/api/ps").respond(
        json={
            "models": [
                {"name": n, "size": int(t * GB), "size_vram": int(t * GB * 0.5)} for n, t in (carregados or {}).items()
            ]
        }
    )


@pytest.fixture
def projeto(tmp_path):
    return Projeto.criar(tmp_path / "p", modelo="ciencia-politica", perfil=PERFIS["padrao"])


@respx.mock
def test_modelo_ausente_vira_erro_com_comando_de_pull(projeto):
    _mock_ollama(respx.mock, {"qwen3-embedding:0.6b": 0.6}, carregados={"qwen3-embedding:0.6b": 0.6})
    checagens = diagnosticar(projeto, ollama=Ollama(OLLAMA), checar_rede=False)
    por_item = {c.item: c for c in checagens}
    ausente = por_item["qwen3.5:9b (classificação, rótulos)"]
    assert ausente.estado == "erro"
    assert "ollama pull qwen3.5:9b" in ausente.dica
    assert "6,6 GB" in ausente.dica
    assert por_item["qwen3-embedding:0.6b (embeddings)"].estado in ("ok", "aviso")
    assert por_item["Carregado: qwen3-embedding:0.6b"].detalhe.endswith("50% na GPU")


@respx.mock
def test_ollama_fora_do_ar(projeto):
    respx.get(f"{OLLAMA}/api/version").mock(side_effect=httpx.ConnectError("recusado"))
    checagens = diagnosticar(projeto, ollama=Ollama(OLLAMA), checar_rede=False)
    servidor = next(c for c in checagens if c.item == "Servidor")
    assert servidor.estado == "erro"
    assert "ollama serve" in servidor.dica
    assert not any(c.grupo == "Modelos do projeto" for c in checagens)


@respx.mock
def test_nome_com_e_sem_latest_e_o_mesmo_modelo():
    _mock_ollama(respx.mock, {"bge-m3:latest": 1.2})
    assert Ollama(OLLAMA).instalado("bge-m3") is not None
    assert Ollama(OLLAMA).instalado("bge-m4") is None


@respx.mock
def test_rede_certificado_e_sem_conexao(projeto):
    _mock_ollama(respx.mock, {})
    urls = list(URLS_REDE.values())
    respx.get(urls[0]).mock(side_effect=httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] self-signed"))
    respx.get(urls[1]).mock(side_effect=httpx.ConnectError("Name or service not known"))
    rede = [c for c in diagnosticar(projeto, ollama=Ollama(OLLAMA)) if c.grupo == "Rede"]
    assert [c.estado for c in rede] == ["erro", "erro"]
    assert "certificado" in rede[0].dica
    assert "internet" in rede[1].dica


def test_cabe_na_memoria():
    assert cabe_na_memoria(6.6, disponivel_gb=13.2).cabe
    folga = cabe_na_memoria(17.0, disponivel_gb=13.2)
    assert not folga.cabe
    assert "18,5 GB" in folga.explicar("gemma4:26b")


def test_formatar_numeros_em_portugues():
    assert num(13.24) == "13,2"
    assert num(4947, 0) == "4.947"
    assert gb(0.64) == "0,6 GB"


def test_env_do_projeto(tmp_path, monkeypatch):
    monkeypatch.delenv("MAPA_EMAIL", raising=False)
    (tmp_path / ".env").write_text("# comentário\nMAPA_EMAIL='pesquisa@example.org'\nOUTRA=1\n")
    assert ler_env(tmp_path) == {"MAPA_EMAIL": "pesquisa@example.org", "OUTRA": "1"}
    assert variavel("MAPA_EMAIL", tmp_path) == "pesquisa@example.org"
    assert "mailto:pesquisa@example.org" in user_agent(tmp_path)
    monkeypatch.setenv("MAPA_EMAIL", "ambiente@example.org")
    assert variavel("MAPA_EMAIL", tmp_path) == "ambiente@example.org"
    assert "mailto:ambiente@example.org" in user_agent(None)


def test_erro_provedor_e_runtimeerror():
    assert issubclass(ErroProvedor, RuntimeError)


@respx.mock
def test_modelo_ja_carregado_nao_vira_aviso_de_memoria(projeto, monkeypatch):
    """Lição do spike M0b: um modelo carregado já está descontado da memória livre."""
    from mapa_da_ciencia import recursos

    _mock_ollama(respx.mock, {"qwen3-embedding:0.6b": 0.6, "qwen3.5:9b": 6.6}, carregados={"qwen3.5:9b": 6.6})
    monkeypatch.setattr(recursos, "memoria", lambda: recursos.Memoria(24, 3.0, 4.0, 5.0))
    checagens = {c.item: c for c in diagnosticar(projeto, ollama=Ollama(OLLAMA), checar_rede=False)}
    carregado = checagens["qwen3.5:9b (classificação, rótulos)"]
    assert carregado.estado == "ok"
    assert "carregado agora" in carregado.detalhe
