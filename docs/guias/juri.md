# Usar o júri de modelos locais

O júri classifica a amostra de validação com vários modelos locais, faz os que discordam deliberarem e leva ao
supervisor o que continua sem maioria. Para entender o porquê de cada passo, veja
[Júri e supervisor](../explicacoes/juri.md).

## Antes de começar

- A classificação e a amostra de validação já existem (`mapa classificar` e `mapa validar amostra`).
- Os modelos do júri estão instalados no Ollama. Use modelos de **famílias diferentes**, e pelo menos três (com dois,
  só há maioria quando os dois concordam). No Mac do piloto, com 24 GB:

```bash
ollama pull gemma4:12b-it-qat   # 7,2 GB
ollama pull qwen3.5:4b          # 3,4 GB
```

- No `mapa.yaml`, liste os membros (o primeiro preside: desempata quando não há maioria nem supervisor):

```yaml
juri:
  membros: [qwen3.5:9b, gemma4:12b-it-qat, qwen3.5:4b]
  auditoria: 40          # decisões unânimes que o supervisor confere
validacao:
  familias:
    claude-opus: claude  # o codificador de referência é um modelo da família Claude
```

## Votar e deliberar

```bash
mapa juri votar       # cada membro classifica a amostra (o que falta), um de cada vez
mapa juri deliberar   # os membros que discordam reveem as respostas vendo as dos outros
mapa juri status      # em que passo o júri está
```

Os dois passos retomam de onde pararam: as respostas ficam no cache do projeto. Um membro só é carregado com os
outros descarregados.

## O supervisor por arquivos (padrão)

```bash
mapa juri exportar-pedidos   # grava em juri/ as instruções e os lotes de pedidos
```

A pasta `juri/` do projeto recebe:

- `instrucoes-supervisor.md`: o que o supervisor deve fazer e o formato da resposta;
- `arbitragem-01.jsonl`, `arbitragem-02.jsonl`…: um pedido por linha (título, resumo, definição da variável e os
  candidatos numerados, sem os nomes dos modelos);
- `auditoria-01.jsonl`…: as decisões unânimes sorteadas para conferir.

Entregue as instruções e os lotes a quem vai supervisionar (uma pessoa ou uma sessão de um modelo maior) e ponha
cada resposta de volta em `juri/` com o nome do lote terminado em `.respostas.jsonl`. Depois:

```bash
mapa juri importar-respostas   # confere e guarda todas as respostas da pasta juri/
```

Cada resposta é conferida: a escolha precisa ser um dos candidatos, a evidência precisa estar no texto e o pedido
precisa ainda valer (se a votação mudou, os candidatos mudam e a resposta antiga é recusada). O que for recusado
aparece na tela; rodar `mapa juri exportar-pedidos` de novo pede só o que falta.

## O supervisor pela API da Anthropic (opcional)

Com a API, os **títulos e resumos saem da máquina**. Para usar:

1. Instale o pacote extra: `pip install 'mapa-da-ciencia[anthropic]'` (ou `uv add anthropic`).
2. Ponha a chave no `.env` do projeto (que não vai para o git): `ANTHROPIC_API_KEY=...`.
3. No `mapa.yaml`:

```yaml
juri:
  supervisor:
    modo: api
    modelo: claude-opus-5-5
    enviar_textos: true       # o consentimento
    limite_gasto_usd: 5
```

4. Rode:

```bash
mapa juri supervisionar
```

O comando mostra quantos pedidos serão enviados e o custo estimado, e pergunta antes de enviar (`--sim` pula a
pergunta). Se a estimativa passar do limite, ele não começa; se o gasto real chegar perto do limite, ele para e
guarda o que já respondeu. As respostas passam pela mesma conferência do protocolo por arquivos.

## O relatório

```bash
mapa juri relatorio   # grava validacao/juri.md e atualiza o painel
```

O relatório começa pelo **resultado principal** (kappa de cada membro, da votação e do júri contra a referência, e o
McNemar entre o júri e o modelo principal), depois o **limite superior** com o supervisor (marcado "circular" quando o
supervisor e a referência são da mesma família), os estágios de cada variável, a concordância por estágio, as
mudanças na deliberação e a auditoria. No painel, a vista Concordância ganha a seção "Júri", e o cartão de cada
documento da amostra mostra os votos.
