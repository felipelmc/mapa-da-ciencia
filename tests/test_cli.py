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
