"""As páginas de referência geradas do código: tabelas bem formadas e os subcomandos da CLI."""

from pathlib import Path

RAIZ = Path(__file__).parents[1] / "docs" / "referencia"


def test_tabelas_sem_barra_escapada_duas_vezes():
    for nome in ("configuracao.md", "codebook.md", "contrato.md"):
        assert "\\\\|" not in (RAIZ / nome).read_text(encoding="utf-8"), nome


def test_cli_lista_os_subcomandos_dos_grupos():
    texto = (RAIZ / "cli.md").read_text(encoding="utf-8")
    for sub in ("amostra", "importar", "metricas", "relatorio"):
        assert f"## `mapa validar {sub}`" in texto, sub
