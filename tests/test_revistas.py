import json
import re
from importlib import resources

from typer.testing import CliRunner

from mapa_da_ciencia.cli import app
from mapa_da_ciencia.fontes import revistas as rv

runner = CliRunner()


def test_retrato_completo_e_sem_emails():
    texto = resources.files("mapa_da_ciencia.fontes").joinpath("scielo-revistas.json").read_text("utf-8")
    dados = json.loads(texto)
    assert dados["n"] == len(dados["revistas"]) >= 400
    assert "@" not in texto
    assert all(re.fullmatch(r"\d{4}-\d{3}[\dX]", r["issn"]) for r in dados["revistas"])
    acronimos = [r["acronimo"] for r in dados["revistas"]]
    assert len(acronimos) == len(set(acronimos))


def test_resolver_por_issn_impresso_online_ou_acronimo():
    assert rv.resolver("0104-6276").acronimo == "op"
    assert rv.resolver("1807-0191").acronimo == "op"  # ISSN online
    assert rv.resolver("OP").titulo == "Opinião Pública"
    assert rv.resolver("9999-9999") is None


def test_as_dez_revistas_do_piloto_existem():
    piloto = ["0103-3352", "0011-5258", "0104-6276", "0102-6445", "0104-4478",
              "1981-3821", "0102-8529", "0034-7329", "0101-3300", "0102-6909"]  # fmt: skip
    assert [rv.por_issn(i).acronimo for i in piloto] == [
        "rbcpol", "dados", "op", "ln", "rsocp", "bpsr", "cint", "rbpi", "nec", "rbcsoc",
    ]  # fmt: skip


def test_buscar_sem_acento_e_por_area():
    achadas = {r.acronimo for r in rv.buscar("opiniao")}
    assert "op" in achadas
    humanas = rv.buscar(area="humanas")
    assert humanas and all("Ciências Humanas" in r.areas for r in humanas)
    assert rv.buscar("0104-6276")[0].acronimo == "op"


def test_cli_revistas():
    r = runner.invoke(app, ["revistas", "opiniao"])
    assert r.exit_code == 0 and "Opinião Pública" in r.output
    r = runner.invoke(app, ["revistas", "opiniao", "--yaml"])
    assert "- 0104-6276" in r.output and "# Opinião Pública" in r.output
