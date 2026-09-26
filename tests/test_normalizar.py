"""Nomes de lugares → códigos (geografia/normalizar.py), com os textos que aparecem no piloto."""

import subprocess
from pathlib import Path

import pytest

from mapa_da_ciencia.contrato.modelos import SIGLAS_UF
from mapa_da_ciencia.geografia import normalizar as n

RAIZ = Path(__file__).resolve().parents[1]

# Países como a v70 do piloto escreve (e o que o autor quis dizer)
PAISES_V70 = {
    "Brasil": "BR", "Brazil": "BR", "BR": "BR", "Brazi": "BR", "Portugal": "PT", "França": "FR",
    "USA": "US", "EUA": "US", "Estados Unidos": "US", "United States of America": "US",
    "Estados Unidos da América": "US", "United Kingdom": "GB", "UK": "GB", "Reino Unido": "GB",
    "Inglaterra": "GB", "Escócia": "GB", "United Kingdom of Great Britain and Northern Ireland": "GB",
    "Alemanha": "DE", "Germany": "DE", "Spain": "ES", "España": "ES", "Espanha": "ES", "México": "MX",
    "Mexico": "MX", "South Africa": "ZA", "Canadá": "CA", "Moçambique": "MZ", "Uruguai": "UY",
    "Vietnam": "VN", "Holanda": "NL", "Áustria": "AT", "Austria": "AT", "Suíça": "CH",
    "Czech Republic": "CZ", "Nova Zelândia": "NZ", "Malasia": "MY", "Taiwan": "TW",
    "Estado Plurinacional da Bolívia": "BO", "Federación de Rusia": "RU",
}  # fmt: skip


@pytest.mark.parametrize(("texto", "iso"), PAISES_V70.items())
def test_paises_da_v70(texto, iso):
    assert n.pais(texto) == iso


@pytest.mark.parametrize("texto", [None, "", "  ", "Paris", "Los Angeles", "D.C.", "XX"])
def test_o_que_nao_e_pais(texto):
    assert n.pais(texto) is None


def test_partes_e_aproximacao():
    assert n.pais("Brasil (Brazil)") == "BR"
    assert n.pais("Porto Alegre, Brasil") == "BR"
    assert n.pais("Brasil / Portugal") is None  # partes que discordam
    assert n.pais("Guinea-Bissau") == "GW"  # o hífen não parte o nome
    # a aproximação não troca países de nomes parecidos
    assert [n.pais(x) for x in ("Austria", "Australia", "Slovakia", "Slovenia", "Niger", "Nigeria")] == [
        "AT", "AU", "SK", "SI", "NE", "NG",
    ]  # fmt: skip


def test_tabela_de_paises():
    codigos = n.codigos_de_pais()
    assert len(codigos) == 250 and {"BR", "XK", "GB"} <= codigos and not {"UK", "SU", "DD", "EU"} & codigos
    assert n.nome_do_pais("BR") == "Brasil" and n.nome_do_pais("GB") == "Reino Unido"
    assert n._paises()[2] == set()  # nenhum nome aponta para dois países


def test_ufs_na_ordem_do_contrato():
    assert tuple(u.sigla for u in n.ufs()) == SIGLAS_UF
    assert n.nome_da_uf("DF") == "Distrito Federal"
    assert sorted({u.regiao for u in n.ufs()}) == ["Centro-Oeste", "Nordeste", "Norte", "Sudeste", "Sul"]


@pytest.mark.parametrize(
    ("texto", "sigla"),
    [
        ("São Paulo", "SP"), ("SP", "SP"), ("sp", "SP"), ("RJ)", "RJ"), ("Federal District", "DF"),
        ("Estado de Minas Gerais", "MG"), ("State of São Paulo", "SP"), ("Paraná", "PR"), ("Parana", "PR"),
        ("Rio de Janeiro - RJ", "RJ"), ("BH", None), ("FU", None), ("", None), (None, None),
    ],
)  # fmt: skip
def test_uf(texto, sigla):
    assert n.uf(texto) == sigla


def test_cidades():
    assert n.uf_da_cidade("Juiz de Fora") == "MG"
    assert n.uf_da_cidade("Brasilia") == "DF"
    assert n.ufs_da_cidade("São Carlos") == {"SP", "SC"} and n.uf_da_cidade("São Carlos") is None
    assert n.uf_da_cidade("São Carlos, SP") == "SP"
    assert n.uf_da_cidade("São Carlos - AM") is None  # não há São Carlos no Amazonas
    assert n.uf_da_cidade("Belém") == "PA" and n.uf_da_cidade("Campo Grande") == "MS"  # a capital pesa mais
    assert n.uf_da_cidade("Bom Jesus") is None
    assert n.uf_da_cidade("Paris") is None
    assert n.uf_da_cidade("Santiago") == "RS"  # por isso só se usa com o país já conferido


def test_separar_cidade_uf():
    assert n.separar_cidade_uf("Niterói, RJ") == ("Niterói", "RJ")
    assert n.separar_cidade_uf("São Paulo - SP") == ("São Paulo", "SP")
    assert n.separar_cidade_uf("Rio de Janeiro/RJ") == ("Rio de Janeiro", "RJ")
    assert n.separar_cidade_uf("Recife, PE, Brasil") == ("Recife", "PE")
    assert n.separar_cidade_uf("Porto Alegre") == ("Porto Alegre", None)
    assert n.separar_cidade_uf(None) == (None, None)


def test_capitais_existem_na_tabela_do_ibge():
    for u in n.ufs():
        assert u.sigla in n.ufs_da_cidade(u.capital), u


def test_municipios():
    assert len(list(n._linhas("municipios.csv"))) > 5500
    assert n._municipios()[n.chave("Alta Floresta D'Oeste")] == {"RO"}


def test_paises_csv_em_dia():
    """O paises.csv é o que o scripts/gerar_paises.ts gera, quando o Node tem a mesma versão do CLDR."""
    try:
        cldr = subprocess.run(["node", "-p", "process.versions.cldr"], capture_output=True, text=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip("sem Node")
    cabecalho = (RAIZ / "src/mapa_da_ciencia/geografia/dados/paises.csv").read_text("utf-8").splitlines()[0]
    if f"CLDR {cldr.stdout.strip()})" not in cabecalho:
        pytest.skip(f"CLDR do Node ({cldr.stdout.strip()}) diferente do que gerou a tabela: {cabecalho}")
    r = subprocess.run(["node", "scripts/gerar_paises.ts", "--checar"], cwd=RAIZ, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_municipios_com_hifen_nao_viram_cidade_e_uf():
    assert n.separar_cidade_uf("Ji-Paraná") == ("Ji-Paraná", None) and n.uf_da_cidade("Ji-Paraná") == "RO"
    assert n.separar_cidade_uf("Grão-Pará") == ("Grão-Pará", None) and n.uf_da_cidade("Grão-Pará") == "SC"
    assert n.separar_cidade_uf("Niterói-RJ") == ("Niterói", "RJ")
