"""`mapa publicar`: o site estático, com resumos só de licença aberta, api false e nenhum e-mail."""

import json
from pathlib import Path

import pytest
from corpus_sintetico import corpus_sintetico
from typer.testing import CliRunner

import mapa_da_ciencia.api as mapa
from mapa_da_ciencia.armazenamento import ARQUIVO, gravar_documentos
from mapa_da_ciencia.cli import app
from mapa_da_ciencia.config import ErroConfig
from mapa_da_ciencia.contrato import modelos as m
from mapa_da_ciencia.llm.perfis import PERFIS
from mapa_da_ciencia.projeto import Projeto
from mapa_da_ciencia.texto import EMAIL
from mapa_da_ciencia.topicos.pipeline import gerar_topicos


@pytest.fixture(scope="module")
def projeto(tmp_path_factory):
    import respx
    from conftest import OLLAMA_FALSO, ApisFalsas

    pasta = tmp_path_factory.mktemp("pub")
    mp = pytest.MonkeyPatch()
    mp.setenv("OLLAMA_HOST", OLLAMA_FALSO)
    with respx.mock(assert_all_called=False) as router:
        ApisFalsas(router)
        p = Projeto.criar(pasta / "sintetico", modelo="vazio", perfil=PERFIS["leve"])
        docs, _ = corpus_sintetico()
        # um terço sem licença aberta: o resumo desses não pode ir para o site
        docs = [d.model_copy(update={"licenca": "desconhecida"}) if i % 3 == 0 else d for i, d in enumerate(docs)]
        gravar_documentos(docs, p.dados / ARQUIVO)
        gerar_topicos(p)
        mapa.classificar(p, limite=30, progresso=False)
    mp.undo()
    return p


@pytest.fixture
def estatico(tmp_path):
    pasta = tmp_path / "estatico"
    pasta.mkdir()
    (pasta / "index.html").write_text("<!doctype html><title>mapa</title>")
    return pasta


def _detalhes(site):
    saida = {}
    for arq in (site / "dados" / "detalhes").glob("*.json"):
        saida.update(m.Fragmento.model_validate_json(arq.read_text(encoding="utf-8")).documentos)
    return saida


def test_resumos_so_com_licenca_aberta(projeto, estatico, tmp_path):
    from mapa_da_ciencia.publicar import publicar

    r = publicar(projeto, tmp_path / "site", estatico=estatico)
    site = r.destino
    assert (site / "index.html").exists() and (site / "dados" / "manifesto.json").exists()
    manifesto = m.Manifesto.model_validate_json((site / "dados" / "manifesto.json").read_text(encoding="utf-8"))
    assert manifesto.api is False and manifesto.versao_contrato == m.VERSAO_CONTRATO
    pub = manifesto.publicacao
    assert (pub.resumos_publicados, pub.resumos_retirados) == (r.resumos_publicados, r.resumos_retirados)
    assert r.resumos_retirados >= 90 and r.resumos_publicados >= 180

    detalhes = _detalhes(site)
    locais = _detalhes(projeto.saida)  # o painel local continua com tudo
    for doc, d in detalhes.items():
        if locais[doc].resumo is None:  # documento sem resumo
            continue
        if d.licenca.startswith("cc"):
            assert d.resumo == locais[doc].resumo
        else:
            assert d.resumo is None and locais[doc].resumo is not None
            assert all(e.evidencia == "" and e.inicio is None for e in d.evidencias.values())
    com_evidencia = [d for d in detalhes.values() if d.licenca.startswith("cc") and d.evidencias]
    assert com_evidencia and all(
        e.evidencia for d in com_evidencia for e in d.evidencias.values() if e.status == "literal"
    )
    assert r.evidencias_retiradas > 0
    assert not any(EMAIL.search(a.read_text(encoding="utf-8")) for a in (site / "dados").rglob("*.json"))
    # publicar de novo troca o site inteiro (nada de sobras)
    (site / "sobra.txt").write_text("x")
    publicar(projeto, tmp_path / "site", estatico=estatico)
    assert not (site / "sobra.txt").exists() and not (tmp_path / "site.novo").exists()


def test_varredura_recusa_email_e_orcid(tmp_path):
    from mapa_da_ciencia.publicar import conferir_privacidade

    dados = tmp_path / "dados"
    dados.mkdir()
    # números de quatro em quatro dígitos que não são ORCIDs (ISSN, PID, dígito verificador errado) passam
    parecidos = '{"issn": "0011-5258", "x": "1234-5678-9012-3456", "y": "0000-0002-1825-0098"}'
    (dados / "revistas.json").write_text(parecidos)
    conferir_privacidade(dados)
    (dados / "citacoes.json").write_text('{"canone": [{"titulo": "Uma obra (0000-0002-1825-0097)"}]}')
    with pytest.raises(ErroConfig, match=r"ORCID \(0000-0002-1825-0097\) apareceu em citacoes\.json"):
        conferir_privacidade(dados)
    (dados / "citacoes.json").write_text('{"nome": "fulano@exemplo.org"}')
    with pytest.raises(ErroConfig, match="e-mail"):
        conferir_privacidade(dados)


def test_sem_resumos(projeto, estatico, tmp_path):
    from mapa_da_ciencia.publicar import publicar

    r = publicar(projeto, tmp_path / "site", sem_resumos=True, estatico=estatico)
    assert r.resumos_publicados == 0
    assert all(d.resumo is None for d in _detalhes(r.destino).values())
    assert json.loads((r.destino / "dados" / "manifesto.json").read_text())["publicacao"]["sem_resumos"] is True


def test_sem_interface_explica(projeto, tmp_path):
    from mapa_da_ciencia.publicar import publicar

    with pytest.raises(ErroConfig, match="npm run empacotar"):
        publicar(projeto, tmp_path / "site", estatico=tmp_path / "nada")


def test_cli(projeto, estatico, tmp_path, monkeypatch):
    import mapa_da_ciencia.servidor.app as servidor_app

    monkeypatch.setattr(servidor_app, "pasta_estatico", lambda: estatico)
    r = CliRunner().invoke(
        app, ["publicar", "-P", str(projeto.raiz), "--destino", str(tmp_path / "s")], env={"COLUMNS": "160"}
    )
    assert r.exit_code == 0, r.output
    texto = " ".join(r.output.split())
    assert "Site publicado em" in texto and "resumos com licença aberta" in texto and "http.server" in texto


def test_a_regra_e_a_licenca_mesmo_sem_resumo(tmp_path):
    """No exemplo sintético, os documentos sem licença conhecida já vêm sem resumo, mas as evidências citam o
    texto: elas também saem."""
    import shutil
    from pathlib import Path

    from mapa_da_ciencia.publicar import filtrar_dados

    pasta = tmp_path / "dados"
    shutil.copytree(Path(__file__).parents[1] / "contrato" / "exemplo" / "dados", pasta)
    publicados, retirados, evidencias = filtrar_dados(pasta)
    detalhes = _detalhes(tmp_path)
    fechados = [d for d in detalhes.values() if not d.licenca.startswith("cc")]
    assert fechados and evidencias > 0 and retirados == 0  # nenhum tinha resumo, mas todos tinham evidências
    assert all(e.evidencia == "" for d in fechados for e in d.evidencias.values())
    assert publicados == sum(d.resumo is not None for d in detalhes.values())
    manifesto = m.Manifesto.model_validate_json((pasta / "manifesto.json").read_text(encoding="utf-8"))
    assert manifesto.api is False and manifesto.publicacao.resumos_publicados == publicados
    abertos = {doc for doc, d in detalhes.items() if d.licenca.startswith("cc")}
    val = m.Validacao.model_validate_json((pasta / "validacao.json").read_text(encoding="utf-8"))
    assert all(d.evidencia == "" for d in val.divergencias if d.doc not in abertos)


def test_o_destino_so_pode_ser_uma_pasta_vazia_ou_um_site_publicado(projeto, estatico, tmp_path):
    from mapa_da_ciencia.publicar import publicar

    for destino in (projeto.raiz, projeto.raiz.parent):
        with pytest.raises(ErroConfig, match="contém o projeto"):
            publicar(projeto, destino, estatico=estatico)
    outra = tmp_path / "docs"
    outra.mkdir()
    (outra / "CNAME").write_text("exemplo.org")
    with pytest.raises(ErroConfig, match="já tem arquivos"):
        publicar(projeto, outra, estatico=estatico)
    assert (outra / "CNAME").read_text() == "exemplo.org" and (projeto.raiz / "mapa.yaml").exists()
    site = publicar(projeto, tmp_path / "vazia", estatico=estatico).destino
    assert (site / ".mapa-site").exists()
    publicar(projeto, site, estatico=estatico)  # um site publicado antes pode ser trocado


def test_exemplo_publicado_sem_trechos_do_juri_nos_resumos_fechados():
    """Os votos do júri e a justificativa do supervisor citam o resumo: somem quando a licença não é aberta."""
    raiz = Path(__file__).parents[1] / "contrato" / "exemplo-publicado" / "dados" / "detalhes"
    fechados = 0
    for arquivo in raiz.glob("*.json"):
        for det in json.loads(arquivo.read_text(encoding="utf-8"))["documentos"].values():
            if det.get("juri") and det["resumo"] is None:
                fechados += 1
                assert all(v["evidencia"] == "" for d in det["juri"].values() for v in d["votos"])
                assert all(d["justificativa"] is None for d in det["juri"].values())
    assert fechados > 0
