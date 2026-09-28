"""O adaptador da API da Anthropic, sem rede: o limite de gasto, a chave fora do repr e os certificados do sistema."""

import json
from types import SimpleNamespace

import pytest

from mapa_da_ciencia.llm.anthropic import MAX_TOKENS, Anthropic, ErroOrcamento, pior_caso


class ClienteGastador:
    """Toda resposta usa o teto de tokens (o raciocínio do modelo não se desliga)."""

    def __init__(self) -> None:
        self.messages = self
        self.chamadas = 0

    def create(self, **kw):
        self.chamadas += 1
        assert kw["max_tokens"] == MAX_TOKENS
        uso = SimpleNamespace(
            input_tokens=900, output_tokens=MAX_TOKENS, cache_read_input_tokens=0, cache_creation_input_tokens=0
        )
        texto = SimpleNamespace(type="text", text=json.dumps({"ok": True}))
        return SimpleNamespace(content=[texto], usage=uso, stop_reason="end_turn")


def test_o_gasto_nunca_passa_do_limite_mesmo_com_respostas_no_teto():
    cliente = ClienteGastador()
    limite = 1.0
    gerador = Anthropic("claude-opus-5-5", limite_usd=limite, cliente=cliente)
    sistema, pedido = "instruções " * 200, json.dumps({"resumo": "texto " * 300})
    with pytest.raises(ErroOrcamento):
        for _ in range(100):
            gerador.gerar_estruturado(sistema, pedido, {"type": "object"})
    assert cliente.chamadas > 0
    assert gerador.custo_usd() <= limite
    assert gerador.custo_usd() + pior_caso("claude-opus-5-5", sistema, pedido) > limite  # parou só quando precisou


def test_a_chave_nao_aparece_no_repr():
    gerador = Anthropic("claude-opus-5-5", chave="sk-ant-segredo-123", cliente=ClienteGastador())
    assert "sk-ant-segredo-123" not in repr(gerador)


def test_o_cliente_do_sdk_usa_os_certificados_do_sistema(monkeypatch):
    anthropic = pytest.importorskip("anthropic")
    import truststore

    recebidos = {}
    original = anthropic.DefaultHttpxClient

    def cliente_http(**kw):
        recebidos.update(kw)
        return original(**kw)

    monkeypatch.setattr(anthropic, "DefaultHttpxClient", cliente_http)
    gerador = Anthropic("claude-opus-5-5", chave="sk-ant-teste")  # só constrói: nenhuma requisição
    assert isinstance(recebidos["verify"], truststore.SSLContext)
    assert gerador.cliente.max_retries == 4
