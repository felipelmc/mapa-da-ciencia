from conftest import registros_articlemeta

from mapa_da_ciencia.armazenamento import ESQUEMA, cobertura, conectar, gravar_documentos, ler_documentos
from mapa_da_ciencia.documento import Documento
from mapa_da_ciencia.fontes.articlemeta import normalizar, revista_do_registro


def _documentos() -> list[Documento]:
    return [normalizar(r, revista_do_registro(r)) for pid, r in sorted(registros_articlemeta().items(), reverse=True)]


def test_esquema_cobre_todos_os_campos_do_documento():
    assert list(ESQUEMA) == list(Documento.model_fields)


def test_ida_e_volta_preserva_tudo_e_ordena_por_id(tmp_path):
    docs = _documentos()
    destino = tmp_path / "dados" / "documentos.parquet"
    assert gravar_documentos(docs, destino) == len(docs)
    lidos = ler_documentos(destino)
    assert [d.id for d in lidos] == sorted(d.id for d in docs)
    assert {d.id: d for d in lidos} == {d.id: d for d in docs}
    assert not list(destino.parent.glob("*.tmp"))


def test_corpus_vazio_gera_parquet_com_esquema(tmp_path):
    destino = tmp_path / "documentos.parquet"
    assert gravar_documentos([], destino) == 0
    assert ler_documentos(destino) == []
    assert cobertura(destino)["documentos"] == 0


def test_views_e_cobertura(tmp_path):
    docs = _documentos()
    destino = tmp_path / "documentos.parquet"
    gravar_documentos(docs, destino)
    con = conectar(destino)
    n_autores = sum(len(d.autores) for d in docs)
    assert con.execute("SELECT count(*) FROM autores").fetchone()[0] == n_autores
    assert con.execute("SELECT min(ordem) FROM autores").fetchone()[0] == 1
    assert con.execute("SELECT count(*) FROM afiliacoes").fetchone()[0] == sum(len(d.afiliacoes) for d in docs)
    c = cobertura(destino)
    assert c["documentos"] == len(docs)
    assert c["por_revista"]["op"] == 25
    assert c["com_resumo"] == sum(bool(d.resumos) for d in docs)
    assert set(c["casamento"]) == {"nao_tentado"}


def test_nenhum_email_no_parquet(tmp_path):
    destino = tmp_path / "documentos.parquet"
    gravar_documentos(_documentos(), destino)
    con = conectar(destino)
    assert (
        con.execute("SELECT count(*) FROM documentos WHERE CAST(documentos AS VARCHAR) LIKE '%@%'").fetchone()[0] == 0
    )
