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
