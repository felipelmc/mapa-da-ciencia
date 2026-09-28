"""Adaptador opcional da API da Anthropic, usado só pelo supervisor do júri (`juri.supervisor.modo: api`).

O resto do mapa-da-ciencia roda com modelos locais; este adaptador existe para quem quiser que o supervisor do júri
seja um modelo da Anthropic chamado pela API, em vez do protocolo por arquivos. Ele usa o SDK oficial (`anthropic`),
que é uma dependência opcional: `pip install 'mapa-da-ciencia[anthropic]'`.

- **Saída estruturada:** a resposta segue um JSON Schema (`output_config.format`), e o texto volta como JSON.
- **Cache do prompt:** as instruções do supervisor (iguais em todos os pedidos) vão com `cache_control`, e só a
  primeira chamada paga a entrada inteira delas.
- **Custo:** o uso de tokens de cada resposta é somado e convertido em dólares pela tabela `PRECOS`; `ErroOrcamento`
  para antes de passar do limite. A estimativa prévia (`estimar_custo`) é conservadora: conta o raciocínio do
  modelo como saída.
- **Chave:** vem de `ANTHROPIC_API_KEY` (ambiente ou `.env` do projeto) e nunca é gravada em lugar nenhum.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .base import ErroProvedor

# dólares por milhão de tokens: entrada, saída, leitura do cache, escrita do cache (tabela de setembro de 2026)
PRECOS: dict[str, tuple[float, float, float, float]] = {
    "claude-opus-5-5": (4.0, 20.0, 0.20, 5.0),
    "claude-opus-5": (5.0, 25.0, 0.50, 6.25),
    "claude-sonnet-5": (2.0, 10.0, 0.20, 2.5),
}
CARACTERES_POR_TOKEN = 3.5
SAIDA_ESTIMADA = 1500  # tokens por resposta, com o raciocínio (o esforço médio pensa pouco num pedido curto)
MAX_TOKENS = 16000


class ErroOrcamento(ErroProvedor):
    """A próxima chamada passaria do limite de gasto."""


def estimar_tokens(texto: str) -> int:
    return int(len(texto) / CARACTERES_POR_TOKEN) + 1


def precos(modelo: str) -> tuple[float, float, float, float]:
    if modelo not in PRECOS:
        raise ErroProvedor(
            f"Não sei o preço do modelo {modelo!r}. Use um de {', '.join(PRECOS)}, ou acrescente-o em "
            "`mapa_da_ciencia.llm.anthropic.PRECOS`."
        )
    return PRECOS[modelo]


def estimar_custo(modelo: str, sistema: str, pedidos: list[str]) -> float:
    """Estimativa conservadora, em dólares: as instruções escritas no cache uma vez e lidas nas demais chamadas,
    cada pedido como entrada e `SAIDA_ESTIMADA` tokens de saída por pedido."""
    entrada, saida, leitura, escrita = precos(modelo)
    t_sistema = estimar_tokens(sistema)
    total = t_sistema * escrita + t_sistema * leitura * max(0, len(pedidos) - 1)
    total += sum(estimar_tokens(p) for p in pedidos) * entrada + SAIDA_ESTIMADA * saida * len(pedidos)
    return total / 1e6


@dataclass
class Uso:
    entrada: int = 0
    saida: int = 0
    cache_leitura: int = 0
    cache_escrita: int = 0
    chamadas: int = 0

    def custo(self, modelo: str) -> float:
        entrada, saida, leitura, escrita = precos(modelo)
        return (
            self.entrada * entrada + self.saida * saida + self.cache_leitura * leitura + self.cache_escrita * escrita
        ) / 1e6


@dataclass
class Anthropic:
    """Um gerador de respostas estruturadas pela API da Anthropic, com conta do gasto."""

    modelo: str
    esforco: str = "medium"
    limite_usd: float | None = None
    chave: str | None = None
    cliente: Any = None  # um `anthropic.Anthropic` (ou um substituto nos testes)
    uso: Uso = field(default_factory=Uso)

    def __post_init__(self) -> None:
        precos(self.modelo)  # modelo sem preço conhecido: para antes de gastar
        if self.cliente is None:
            try:
                import anthropic
            except ImportError as e:
                raise ErroProvedor(
                    "O supervisor pela API precisa do pacote `anthropic`: instale com "
                    "`pip install 'mapa-da-ciencia[anthropic]'` (ou `uv add anthropic`)."
                ) from e
            if not self.chave:
                raise ErroProvedor(
                    "Falta a chave da API: ponha `ANTHROPIC_API_KEY=...` no `.env` do projeto (o arquivo não vai para "
                    "o git) ou no ambiente."
                )
            self.cliente = anthropic.Anthropic(api_key=self.chave, max_retries=4)

    def custo_usd(self) -> float:
        return self.uso.custo(self.modelo)

    def gerar_estruturado(self, sistema: str, pedido: str, esquema: dict[str, Any]) -> dict[str, Any]:
        """Uma chamada: as instruções (com cache), o pedido e a resposta no formato do esquema."""
        if self.limite_usd is not None:
            proxima = estimar_custo(self.modelo, "", [pedido]) + estimar_tokens(sistema) * precos(self.modelo)[2] / 1e6
            if self.custo_usd() + proxima > self.limite_usd:
                raise ErroOrcamento(
                    f"A próxima chamada passaria do limite de gasto (US$ {self.limite_usd:.2f}; gasto até aqui: "
                    f"US$ {self.custo_usd():.2f}). Aumente `--limite-gasto` para continuar."
                )
        try:
            resposta = self.cliente.messages.create(
                model=self.modelo,
                max_tokens=MAX_TOKENS,
                system=[{"type": "text", "text": sistema, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": pedido}],
                output_config={"effort": self.esforco, "format": {"type": "json_schema", "schema": esquema}},
            )
        except Exception as e:  # erros do SDK (já com as novas tentativas dele em 429, 5xx e 529)
            nome = type(e).__name__
            if nome == "AuthenticationError":
                raise ErroProvedor("A API da Anthropic recusou a chave (ANTHROPIC_API_KEY). Confira o `.env`.") from e
            raise ErroProvedor(f"A API da Anthropic falhou ({nome}): {e}") from e
        u = resposta.usage
        self.uso.entrada += getattr(u, "input_tokens", 0) or 0
        self.uso.saida += getattr(u, "output_tokens", 0) or 0
        self.uso.cache_leitura += getattr(u, "cache_read_input_tokens", 0) or 0
        self.uso.cache_escrita += getattr(u, "cache_creation_input_tokens", 0) or 0
        self.uso.chamadas += 1
        if resposta.stop_reason == "refusal":
            raise ErroProvedor("O modelo recusou o pedido (stop_reason: refusal).")
        if resposta.stop_reason == "max_tokens":
            raise ErroProvedor("A resposta foi cortada no limite de tokens.")
        texto = next((b.text for b in resposta.content if getattr(b, "type", "") == "text"), "")
        try:
            return json.loads(texto)
        except json.JSONDecodeError as e:
            raise ErroProvedor("A resposta da API não era um JSON válido.") from e
