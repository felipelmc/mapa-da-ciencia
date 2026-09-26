import asyncio

from conftest import casos_especiais, registros_articlemeta

from mapa_da_ciencia.fontes import revistas
from mapa_da_ciencia.fontes.articlemeta import (
    RevistaRef,
    ano_do_pid,
    buscar_registros,
    listar_pids,
    normalizar,
    revista_do_registro,
)
from mapa_da_ciencia.fontes.base import Buscador
from mapa_da_ciencia.texto import contem_email

OP = RevistaRef.de_revista(revistas.por_issn("0104-6276"))


def _revista_do(pid: str) -> RevistaRef:
    return revista_do_registro(registros_articlemeta()[pid])


async def _listar_e_buscar(brutos, anos=(2024, 2024)):
    async with Buscador(brutos, espera_inicial=0) as b:
        lista = await listar_pids(b, OP, anos)
        registros = await buscar_registros(b, lista.pids)
        return lista, registros, b.contadores


def test_ano_do_pid():
    assert ano_do_pid("S0104-62762024000100200") == 2024
    assert ano_do_pid("curto") is None


def test_opiniao_publica_2024_e_segunda_execucao_sem_requisicoes(tmp_path, apis_falsas):
    lista, registros, _ = asyncio.run(_listar_e_buscar(tmp_path))
    assert len(lista.pids) == 25 and lista.fora_do_periodo == 15 and lista.aviso is None
    assert all(p[10:14] == "2024" for p in lista.pids) and all(registros.values())
    assert apis_falsas.chamadas["articlemeta"] == 26  # 1 lista + 25 registros
    lista2, _, c2 = asyncio.run(_listar_e_buscar(tmp_path))
    assert lista2.pids == lista.pids and c2.total_requisicoes == 0
    assert apis_falsas.chamadas["articlemeta"] == 26


def test_pids_repetidos_entre_paginas_geram_aviso(tmp_path, apis_falsas):
    ids = apis_falsas.identificadores["0104-6276"]
    ids["objects"] = [*ids["objects"], ids["objects"][-1]]
    lista, _, _ = asyncio.run(_listar_e_buscar(tmp_path))
    assert lista.repetidos == 1 and "repetiu 1 PID" in lista.aviso and len(lista.pids) == 25


def test_pid_desconhecido_vira_none(tmp_path, apis_falsas):
    async def buscar():
        async with Buscador(tmp_path, espera_inicial=0) as b:
            return await buscar_registros(b, ["S0104-62769999000100001"])

    assert asyncio.run(buscar()) == {"S0104-62769999000100001": None}


def test_normalizar_nunca_deixa_email():
    for pid, registro in registros_articlemeta().items():
        assert contem_email(registro)  # as fixtures têm e-mails (falsos) de propósito
        doc = normalizar(registro, _revista_do(pid))
        assert not contem_email(doc.model_dump()), pid


def test_normalizar_opiniao_publica():
    registros = registros_articlemeta()
    pid = next(p for p in sorted(registros) if p.startswith("S0104-62762024"))
    doc = normalizar(registros[pid], OP)
    assert doc.id == doc.pid == pid and doc.ano == 2024 and doc.fonte == "articlemeta"
    assert doc.revista_acronimo == "op" and doc.origens == ["scielo:0104-6276"]
    assert doc.doi and doc.doi.startswith("10.1590/")
    assert {t.idioma for t in doc.titulos} >= {"pt", "en"}
    assert doc.resumos and not doc.resumos[0].texto.lower().startswith("resumo")
    assert doc.autores and all(a.sobrenome for a in doc.autores)
    assert doc.licenca == "cc-by" and doc.licenca_fonte == "revista" and doc.casamento == "nao_tentado"
    assert doc.url and pid in doc.url
    assert doc.n_referencias is not None and doc.n_referencias <= 2  # fixtures guardam só 2


def test_casos_especiais():
    registros, casos = registros_articlemeta(), casos_especiais()
    por_motivo = {m: p for p, m in casos.items()}
    html = normalizar(registros[por_motivo["html"]], _revista_do(por_motivo["html"]))
    assert all("&amp;" not in r.texto and "&#" not in r.texto for r in html.resumos)
    so_v70 = normalizar(registros[por_motivo["so_v70"]], _revista_do(por_motivo["so_v70"]))
    assert so_v70.afiliacoes_fonte == "v70" and so_v70.afiliacoes and all(a.fonte == "v70" for a in so_v70.afiliacoes)
    resenha = normalizar(registros[por_motivo["resenha"]], _revista_do(por_motivo["resenha"]))
    assert resenha.tipo == "book-review"
    par = [p for p, m in casos.items() if m.startswith("DOI repetido")]
    d1, d2 = (normalizar(registros[p], _revista_do(p)) for p in par)
    assert d1.doi == d2.doi and d1.id != d2.id  # a deduplicação decide depois, com o título


def test_palavras_chave_varias_por_idioma():
    registros = registros_articlemeta()
    com_varias = [
        normalizar(r, revista_do_registro(r)) for p, r in registros.items() if len(r["article"].get("v85") or []) > 2
    ]
    assert com_varias
    doc = com_varias[0]
    assert len([k for k in doc.palavras_chave if k.idioma == doc.palavras_chave[0].idioma]) > 1


def test_revista_de_outra_colecao_vem_do_registro():
    registros = registros_articlemeta()
    arg = revista_do_registro(registros["S1514-79912026000100130"])
    assert arg.colecao == "arg" and arg.issn == "1514-7991" and arg.prefixo_cache.startswith("arg-")
    doc = normalizar(registros["S1514-79912026000100130"], arg)
    assert doc.colecao == "arg" and doc.revista_titulo and doc.revista_issn == "1514-7991"
    op = revista_do_registro(next(r for p, r in registros.items() if p.startswith("S0104-6276")))
    assert op.acronimo == "op" and op.titulo == "Opinião Pública"  # do retrato, para o SciELO Brasil
