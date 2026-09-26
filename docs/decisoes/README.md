# Registros de decisão

Cada decisão técnica relevante do projeto vira um registro curto (ADR, *architecture decision record*) nesta pasta. O registro explica o que foi decidido, por quê e com base em que evidência. Assim, quem chegar depois, inclusive o autor daqui a um ano, entende as escolhas sem precisar reconstruí-las.

As decisões do marco M0 vêm de **spikes**: experimentos pequenos e descartáveis que respondem a uma pergunta específica. Os scripts ficam em `spikes/` e podem ser rodados de novo para reproduzir os números.

## Índice

| Nº | Decisão | Status |
|---|---|---|
| — | (nenhuma ainda) | — |

## Modelo

Copie o bloco abaixo para um arquivo `NNNN-titulo-curto.md`, com o número seguinte da lista.

```markdown
# NNNN. Título da decisão

- **Status:** proposta | aceita | substituída por NNNN
- **Data:** AAAA-MM-DD
- **Marco:** M0

## Contexto

Qual pergunta precisava de resposta e por que ela importa.

## Opções consideradas

- Opção A: ...
- Opção B: ...

## Evidência

Números do spike, com tabela quando couber. Diga como foram medidos.

## Decisão

O que foi escolhido.

## Consequências

O que muda no projeto e quais riscos continuam abertos.

## Como reproduzir

    uv run spikes/<script>.py
```
