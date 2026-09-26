import sqlite3

from mapa_da_ciencia.llm.cache import CacheLLM, chave_de


def test_guarda_le_e_separa_por_tarefa(tmp_path):
    caminho = tmp_path / "estado.sqlite"
    chave = chave_de("prompt", "qwen3.5:9b@abc", {"temperatura": 0, "semente": 7})
    assert chave == chave_de("prompt", "qwen3.5:9b@abc", {"semente": 7, "temperatura": 0})  # ordem não importa
    assert chave != chave_de("prompt", "qwen3.5:9b@def", {"temperatura": 0, "semente": 7})
    with CacheLLM(caminho) as cache:
        assert cache.obter("rotulos", chave) is None
        cache.guardar("rotulos", chave, {"rotulo": "Coalizões e agenda"}, "qwen3.5:9b@abc")
        cache.guardar("rotulos", chave, {"rotulo": "Coalizões e Congresso"}, "qwen3.5:9b@abc")  # substitui
        assert cache.obter("classificacao", chave) is None and cache.contar("rotulos") == 1
    with CacheLLM(caminho) as cache:  # persiste entre aberturas
        assert cache.obter("rotulos", chave) == {"rotulo": "Coalizões e Congresso"}
    modo = sqlite3.connect(caminho).execute("PRAGMA journal_mode").fetchone()[0]
    assert modo == "wal"
