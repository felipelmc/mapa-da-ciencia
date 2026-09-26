import asyncio
import gzip

import httpx
import pytest
import respx

from mapa_da_ciencia.fontes.base import Buscador, ErroFonte, FaltaNoCache, gravar_gz, ler_gz, limpar_temporarios

URL = "https://api.teste.org/itens"


def rodar(coro):
    return asyncio.run(coro)


async def _buscar(brutos, **kw):
    params = kw.pop("params", {"q": "x"})
    async with Buscador(brutos, espera_inicial=0, **kw) as b:
        dados = await b.json("teste", URL, params, "teste/itens.json.gz")
        return dados, b.contadores


@respx.mock
def test_cache_evita_segunda_requisicao(tmp_path):
    rota = respx.get(URL).respond(json={"itens": [1, 2]})
    dados, c1 = rodar(_buscar(tmp_path))
    assert dados == {"itens": [1, 2]} and c1.requisicoes["teste"] == 1
    dados, c2 = rodar(_buscar(tmp_path))
    assert dados == {"itens": [1, 2]} and c2.total_requisicoes == 0 and c2.do_cache["teste"] == 1
    assert rota.call_count == 1


def test_offline_sem_cache(tmp_path):
    with pytest.raises(FaltaNoCache):
        rodar(_buscar(tmp_path, offline=True))


@respx.mock
def test_tenta_de_novo_em_erro_temporario(tmp_path):
    rota = respx.get(URL).mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(429, headers={"retry-after": "0"}),
            httpx.ConnectError("caiu"),
            httpx.Response(200, json={"ok": True}),
        ]
    )
    dados, c = rodar(_buscar(tmp_path))
    assert dados == {"ok": True} and rota.call_count == 4 and c.requisicoes["teste"] == 1


@respx.mock
def test_erro_definitivo_e_desistencia(tmp_path):
    respx.get(URL).respond(404, text="não achei")
    with pytest.raises(ErroFonte, match="404"):
        rodar(_buscar(tmp_path))
    respx.get(URL).respond(503)
    with pytest.raises(ErroFonte, match="depois de 6 tentativas"):
        rodar(_buscar(tmp_path))


@respx.mock
def test_arquivo_corrompido_e_baixado_de_novo(tmp_path):
    arq = tmp_path / "teste" / "itens.json.gz"
    arq.parent.mkdir(parents=True)
    arq.write_bytes(gzip.compress(b'{"itens": [1'))  # truncado
    rota = respx.get(URL).respond(json={"itens": [9]})
    dados, _ = rodar(_buscar(tmp_path))
    assert dados == {"itens": [9]} and rota.call_count == 1 and ler_gz(arq) == {"itens": [9]}


@respx.mock
def test_chave_de_api_nao_vai_para_o_disco(tmp_path):
    respx.get(URL).respond(json={"meta": {"query": "https://api.teste.org/itens?api_key=SEGREDO123"}})
    rodar(_buscar(tmp_path, params={"q": "x", "api_key": "SEGREDO123"}))
    conteudo = gzip.decompress((tmp_path / "teste" / "itens.json.gz").read_bytes()).decode()
    assert "SEGREDO123" not in conteudo and "***" in conteudo


def test_gravacao_atomica_e_limpeza_de_temporarios(tmp_path):
    gravar_gz(tmp_path / "a" / "b.json.gz", {"x": 1})
    assert not list(tmp_path.rglob("*.tmp"))
    (tmp_path / "a" / "c.json.gz.tmp").write_bytes(b"lixo")
    assert limpar_temporarios(tmp_path) == 1
    assert not list(tmp_path.rglob("*.tmp"))


@respx.mock
def test_saldo_de_creditos_do_openalex(tmp_path):
    respx.get(URL).respond(json={}, headers={"x-ratelimit-remaining": "973"})

    async def buscar():
        async with Buscador(tmp_path, espera_inicial=0) as b:
            await b.json("openalex", URL, {}, "oa/p1.json.gz", custo=1)
            return b.contadores

    c = rodar(buscar())
    assert c.creditos_openalex == 1 and c.saldo_openalex == 973


@respx.mock
def test_404_vira_none_e_fica_no_cache_quando_pedido(tmp_path):
    rota = respx.get(URL).respond(404, json={"error": "not found"})

    async def buscar():
        async with Buscador(tmp_path, espera_inicial=0) as b:
            return await b.json("teste", URL, {}, "teste/ausente.json.gz", ausente_se_404=True), b.contadores

    assert rodar(buscar())[0] is None
    dados, contadores = rodar(buscar())
    assert dados is None and contadores.total_requisicoes == 0 and rota.call_count == 1
    with pytest.raises(ErroFonte, match="404"):
        rodar(_buscar(tmp_path / "outro"))  # sem a opção, 404 continua sendo erro
