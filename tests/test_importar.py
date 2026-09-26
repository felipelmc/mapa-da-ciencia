from pathlib import Path

import pytest
from conftest import FIXTURES
from typer.testing import CliRunner

from mapa_da_ciencia.armazenamento import ARQUIVO, ler_documentos
from mapa_da_ciencia.cli import app
from mapa_da_ciencia.coleta import coletar
from mapa_da_ciencia.config import ErroConfig
from mapa_da_ciencia.fontes.importar import ler_arquivo, ler_csv, ler_txt
from mapa_da_ciencia.llm.perfis import PERFIS
from mapa_da_ciencia.projeto import Projeto

IMPORTAR = FIXTURES / "importar"
runner = CliRunner()
ESPERADOS = {
    ("S1679-44272026000200073", "psi"),
    ("S0101-28002026000202001", "scl"),
    ("S0124-05792026000100005", "col"),
    ("S1514-79912026000100130", "arg"),
}


@pytest.mark.parametrize("arquivo", ["export.ris", "export.csv", "export.bib"])
def test_exportacoes_reais_do_scielo(arquivo):
    imp = ler_arquivo(IMPORTAR / arquivo)
    assert {(i.pid, i.colecao) for i in imp.itens if i.pid} == ESPERADOS
    preprint = next(i for i in imp.itens if not i.pid)
    assert preprint.doi == "10.1590/scielopreprints.17844"  # no CSV, derivado do id "preprint_17844"
    assert not imp.ignorados and all(i.ano == 2026 for i in imp.itens)


def test_lista_txt_com_comentarios_e_lixo():
    imp = ler_arquivo(IMPORTAR / "dois.txt")
    assert [(i.pid, i.doi) for i in imp.itens] == [
        (None, "10.1590/1807-019120243011"),
        (None, "10.1590/scielopreprints.17844"),
        ("S0104-62762024000100200", None),
    ]
    assert imp.ignorados == ["linha 6: não é identificador"]


def test_csv_do_excel_com_ponto_e_virgula_e_cp1252(tmp_path):
    arq = tmp_path / "planilha.csv"
    arq.write_bytes(
        "Título;DOI;Ano\nPolíticas públicas;10.1590/1807-019120243011;2024\nSem id;;2020\n".encode("cp1252")
    )
    imp = ler_arquivo(arq)
    assert [(i.doi, i.titulo, i.ano) for i in imp.itens] == [("10.1590/1807-019120243011", "Políticas públicas", 2024)]
    assert len(imp.ignorados) == 1


def test_pid_antigo_no_doi_e_formato_desconhecido(tmp_path):
    assert ler_txt("10.1590/S0011-52582014000200007").itens[0].pid == "S0011-52582014000200007"
    assert ler_csv("").itens == []
    with pytest.raises(ErroConfig, match="Formato não reconhecido"):
        ler_arquivo(Path(tmp_path / "x.pdf"))


@pytest.fixture
def projeto(tmp_path):
    return Projeto.criar(
        tmp_path / "imp", modelo="vazio", perfil=PERFIS["leve"], revistas=["0104-6276"], anos=(2024, 2026)
    )


def _importar(projeto, *nomes):
    pasta = projeto.raiz / "importados"
    pasta.mkdir(exist_ok=True)
    for nome in nomes:
        (pasta / nome).write_bytes((IMPORTAR / nome).read_bytes())


def test_coleta_com_exportacao_de_outras_colecoes(projeto, apis_falsas):
    _importar(projeto, "export.ris")
    resumo = coletar(projeto)
    docs = {d.id: d for d in ler_documentos(projeto.dados / ARQUIVO)}
    # PIDs da ArticleMeta (Brasil e Argentina), casados com o OpenAlex pelo DOI
    for pid, colecao in [("S0101-28002026000202001", "scl"), ("S1514-79912026000100130", "arg")]:
        assert docs[pid].colecao == colecao and docs[pid].origens == ["importar:export.ris"]
        assert docs[pid].casamento == "1_doi" and docs[pid].citacoes is not None
    # o preprint só existe no OpenAlex e fica fora do recorte de tipos padrão
    assert resumo.excluidos_por_tipo == {"preprint": 1}
    # PePSIC e Colômbia: fora das fixtures da ArticleMeta e do OpenAlex
    assert resumo.nao_encontrados == 2
    assert resumo.importacoes == ["export.ris: 5 registro(s): 4 com PID, 1 só com DOI, 0 sem identificador"]


def test_preprint_entra_quando_o_tipo_esta_no_recorte(projeto, apis_falsas):
    yaml = (projeto.raiz / "mapa.yaml").read_text()
    (projeto.raiz / "mapa.yaml").write_text(
        yaml.replace("  openalex:", "    tipos: [research-article, preprint]\n  openalex:")
    )
    projeto = Projeto.abrir(projeto.raiz)  # relê o mapa.yaml editado
    _importar(projeto, "export.bib")
    coletar(projeto)
    preprint = next(d for d in ler_documentos(projeto.dados / ARQUIVO) if d.tipo == "preprint")
    assert preprint.fonte == "openalex" and preprint.id == "doi:10.1590/scielopreprints.17844"
    assert preprint.titulos and preprint.origens == ["importar:export.bib"]


def test_importado_que_ja_foi_coletado_e_fundido(projeto, apis_falsas):
    _importar(projeto, "dois.txt")
    resumo = coletar(projeto)
    docs = {d.id: d for d in ler_documentos(projeto.dados / ARQUIVO)}
    assert resumo.fundidos >= 2
    assert docs["S0104-62762024000100200"].origens == ["scielo:0104-6276", "importar:dois.txt"]


def test_projeto_so_com_importacao(tmp_path, apis_falsas):
    p = Projeto.criar(tmp_path / "so-imp", modelo="vazio", perfil=PERFIS["leve"], anos=(2026, 2026))
    texto = (p.raiz / "mapa.yaml").read_text().replace("    revistas:\n      - 0104-6276", "    revistas: []")
    (p.raiz / "mapa.yaml").write_text(texto)
    with pytest.raises(ErroConfig, match="Nenhuma fonte"):
        coletar(Projeto.abrir(p.raiz))  # relê o mapa.yaml editado
    r = runner.invoke(app, ["importar", str(IMPORTAR / "export.csv"), "-P", str(p.raiz)])
    assert r.exit_code == 0, r.output
    assert "4 com PID" in r.output and "Coleta concluída" in r.output
    assert (p.raiz / "importados" / "export.csv").exists()
