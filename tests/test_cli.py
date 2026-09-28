import socket

import pytest
from typer.testing import CliRunner

from mapa_da_ciencia import __version__
from mapa_da_ciencia.cli import app

runner = CliRunner()


def test_versao():
    resultado = runner.invoke(app, ["--versao"])
    assert resultado.exit_code == 0
    assert __version__ in resultado.output


def test_ajuda_sem_argumentos():
    resultado = runner.invoke(app, [])
    assert "Observatório da literatura científica" in resultado.output


# ---- mapa painel --porta


def _duas_portas_seguidas() -> tuple[socket.socket, socket.socket]:
    """Dois sockets escutando em portas seguidas (p e p + 1) de 127.0.0.1."""
    for _ in range(50):
        a = socket.socket()
        a.bind(("127.0.0.1", 0))
        b = socket.socket()
        try:
            b.bind(("127.0.0.1", a.getsockname()[1] + 1))
        except OSError:
            a.close()
            b.close()
            continue
        a.listen()
        b.listen()
        return a, b
    pytest.skip("sem duas portas livres seguidas")


def test_painel_com_porta_fora_da_faixa_da_erro_sem_traceback():
    r = runner.invoke(app, ["painel", "--exemplo", "--porta", "99999", "--nao-abrir"])
    assert r.exit_code == 2
    assert not isinstance(r.exception, OverflowError)
    assert "99999" in r.output


def test_painel_nao_anuncia_o_endereco_de_uma_porta_que_nao_consegue_usar(monkeypatch):
    import uvicorn

    monkeypatch.setattr(uvicorn, "run", lambda *a, **k: pytest.fail("o servidor não devia subir"))
    with socket.socket() as ocupada:
        ocupada.bind(("127.0.0.1", 0))  # ocupada, mas sem escutar: só a tentativa de usá-la percebe
        porta = ocupada.getsockname()[1]
        r = runner.invoke(app, ["painel", "--exemplo", "--porta", str(porta), "--nao-abrir"])
    assert r.exit_code == 1
    assert f"a porta {porta} já está em uso" in r.output
    assert "http://127.0.0.1:" not in r.output


def test_painel_sugere_uma_porta_livre_e_nao_so_a_seguinte():
    a, b = _duas_portas_seguidas()
    with a, b:
        porta = a.getsockname()[1]
        r = runner.invoke(app, ["painel", "--exemplo", "--porta", str(porta), "--nao-abrir"])
    assert r.exit_code == 1
    assert "--porta " in r.output
    assert f"--porta {porta + 1}." not in r.output


# ---- textos do Typer e do Click em português


def test_erro_de_opcao_inexistente_em_portugues():
    r = runner.invoke(app, ["status", "--xyz"])
    assert r.exit_code == 2
    assert "No such option" not in r.output
    assert "Opção inexistente: --xyz" in r.output
    assert "Uso: mapa status [OPÇÕES]" in r.output
    assert "Veja 'mapa status -h' para a ajuda." in r.output


def test_erro_de_comando_inexistente_em_portugues():
    r = runner.invoke(app, ["stauts"])
    assert "No such command" not in r.output
    assert "Comando inexistente: 'stauts'. Você quis dizer 'status'?" in r.output


def test_erro_de_valor_invalido_e_de_argumento_faltando_em_portugues():
    r = runner.invoke(app, ["painel", "--porta", "abc"])
    assert "Invalid value" not in r.output
    assert "Valor inválido para '--porta': 'abc' não é um número inteiro." in r.output
    r = runner.invoke(app, ["novo"])
    assert "Falta o argumento 'pasta'." in r.output


def test_ajuda_em_portugues():
    r = runner.invoke(app, ["novo", "-h"])
    assert r.exit_code == 0
    for ingles in ("Show this message", "Options", "Arguments", "[required]", "[default:", "Usage"):
        assert ingles not in r.output
    for portugues in (
        "Mostra esta ajuda e sai.",
        "Opções",
        "Argumentos",
        "[obrigatório]",
        "[padrão:",
        "Uso: mapa novo",
    ):
        assert portugues in r.output
    # também num subcomando de um grupo (mapa validar amostra)
    r = runner.invoke(app, ["validar", "amostra", "-h"])
    assert "Mostra esta ajuda e sai." in r.output
    assert "Show this message" not in r.output
