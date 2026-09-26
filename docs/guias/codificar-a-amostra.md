# Codificar a amostra

Para saber se a classificação do modelo é confiável, compare-a com a leitura de pessoas numa amostra de documentos. Esta página mostra como sortear a amostra e como trazer para o projeto as codificações feitas fora dele.

## Sortear a amostra

```bash
uv run mapa validar amostra
```

A amostra é sorteada uma vez e fica guardada no `estado.sqlite` do projeto. Rodar o comando de novo mostra a mesma amostra; para sortear outra, use `--refazer` (as codificações já feitas continuam guardadas, mas só as dos documentos da amostra nova entram nas métricas).

O sorteio segue a seção `validacao` do `mapa.yaml`:

```yaml
validacao:
  n: 200                    # tamanho da amostra
  estratificar_por: topico  # topico, ano ou revista
  semente: 7                # mesma semente, mesma amostra
```

- A amostra sai só dos documentos que a classificação lê, os que têm resumo.
- **Estratificada:** cada tópico (ou ano, ou revista) recebe uma parte proporcional ao seu tamanho, com pelo menos um documento. Os documentos sem tópico formam um estrato próprio. Sem tópicos ainda, a estratificação usa a revista e a saída avisa.
- A ordem da amostra é embaralhada, e é nessa ordem que ela vem na fila de codificação e na fila da classificação: `mapa classificar --somente-amostra` classifica só a amostra, para a validação começar antes da rodada completa.

O comando também grava `validacao/amostra.jsonl`, com uma linha por documento e só o que quem codifica precisa ver:

```json
{"doc": "S0104-62762024000100201", "titulo": "…", "resumo": "…", "idioma": "pt"}
```

Nenhuma resposta do modelo vai nesse arquivo: a codificação é **cega**.

## Codificar no painel

Com o painel aberto (`mapa painel`), vá a **Validação › Codificar a amostra**, escreva o seu nome (sem acentos nem espaços, como `maria`) e comece. A ficha mostra o título e o resumo à esquerda e as variáveis do codebook à direita, uma de cada vez. Tudo funciona pelo teclado:

| Tecla | O que faz |
|---|---|
| ++1++ a ++9++ | Escolhe a opção da variável atual e passa para a próxima. Nas booleanas, ++1++ é Sim e ++2++ é Não. Na múltipla escolha, liga ou desliga a opção. |
| ++tab++, ++down++, ++up++ | Troca de variável. Numa variável de texto, digite a resposta e aperte ++enter++. |
| ++enter++ | Confirma a ficha (todas as variáveis respondidas) e abre a próxima. |
| ++left++, ++right++ | Ficha anterior e próxima, sem confirmar. |
| ++s++ | Marca a resposta como incerta. |
| ++n++ | Escreve uma nota sobre a resposta. |
| ++e++ | Usa o trecho selecionado no resumo (com o mouse) como evidência. |
| ++d++ | Mostra as definições das categorias. |
| ++question++ | Mostra a ajuda. |

- A codificação é **cega**: a ficha nunca mostra o que o modelo respondeu.
- Cada pessoa tem a própria ordem na fila, sempre a mesma, e a amostra inteira passa por todas.
- Tudo é gravado sozinho, primeiro no navegador e depois no projeto. Se o painel cair, as respostas ficam guardadas no navegador e são enviadas quando ele voltar. Ao reabrir, a fila continua da primeira ficha incompleta.
- A evidência é opcional para pessoas: ela ajuda a discutir as divergências depois.

## Importar codificações feitas fora do painel

Quem codificou numa planilha, num script ou com outro anotador entrega um JSONL com uma linha por documento:

```json
{"doc": "S0104-62762024000100201", "respostas": {"abordagem": {"valor": "quantitativa", "evidencia": "análise de regressão com dados do ESEB"}, "brasil_como_caso": {"valor": true}}}
```

- Uma chave por variável do codebook, com o `valor` (a categoria, `true`/`false`, uma lista nas de múltipla escolha, ou um texto) e, opcionalmente, `evidencia`, `incerto` (`true` para marcar dúvida) e `nota`.
- As variáveis também podem vir direto na linha, sem `respostas`.
- Todas as variáveis são obrigatórias em cada linha.

```bash
uv run mapa validar importar codificacoes.jsonl --codificador maria
```

O nome do codificador identifica as respostas no relatório (letras sem acento, números, `-`, `_` e `.`). Importar de novo com o mesmo nome substitui as respostas dos documentos importados.

A saída diz quantos documentos da amostra foram codificados, quais linhas eram de documentos fora da amostra (ignoradas) e quais eram inválidas (um valor fora das categorias, uma variável que falta), com o motivo. Uma linha inválida não é gravada, e o comando sai com erro para você corrigir e importar de novo.

### Codificadores de referência

`--tipo referencia` marca um codificador que não é uma pessoa: por exemplo, um modelo maior usado como leitura de referência enquanto a codificação humana não fica pronta. O relatório e o painel nunca o chamam de humano, e as métricas contra ele dizem quanto o modelo local concorda com essa referência, não com uma pessoa.

```bash
uv run mapa validar importar referencia.jsonl --codificador claude-opus --tipo referencia
```

### Pela API do painel

Com o painel aberto (`mapa painel`), a codificação também pode ser gravada por um script, na própria máquina:

| Rota | O que faz |
|---|---|
| `GET /api/validacao/fila?codificador=NOME` | A amostra na ordem da fila desse codificador (embaralhada a partir do nome, sempre a mesma), com título, resumo, o codebook e as respostas que ele já deu. Nunca traz respostas de modelos. |
| `PUT /api/validacao/codificacoes/{doc}` | Grava as respostas de um documento: `{"codificador": "maria", "respostas": {...}, "completa": true}`. Com `completa: false`, as variáveis ainda não respondidas não são erro. |
| `GET /api/validacao/metricas` | A concordância calculada na hora, no formato de `validacao.json`. |

As rotas de escrita só aceitam pedidos feitos desta máquina (endereço `127.0.0.1` ou `localhost`), para que uma página aberta em outro site não consiga gravar no projeto pelo navegador.

## Medir a concordância

```bash
uv run mapa validar metricas
```

Compara cada codificador com cada modelo que classificou a amostra, os codificadores entre si e os modelos entre si: concordância, kappa com intervalo de 95%, PABAK e alfa de Krippendorff, por variável. Veja [Ler kappa e PABAK](ler-kappa-e-pabak.md).

## O relatório

```bash
uv run mapa validar relatorio
```

Grava em `validacao/`:

- `relatorio.md`: os participantes e o tipo de cada um, a concordância por variável e par, a precisão e a revocação por categoria, as matrizes de confusão, a comparação entre modelos, a taxa de evidência literal e todas as divergências com o modelo principal, com o trecho que o modelo citou;
- `tabelas.tex`: as tabelas de concordância em LaTeX (pacote `booktabs`), com vírgula decimal, prontas para um artigo;
- `validacao.json`: as mesmas métricas, para outras análises.

O desenho da validação está no [ADR 0012](../decisoes/0012-validacao-e-codificador-de-referencia.md).

Em Python, `mapa.amostra_de_validacao(p)`, `mapa.importar_codificacoes(p, arquivo, "maria")`, `mapa.codificacoes(p)`, `mapa.validacao(p)` e `mapa.relatorio_de_validacao(p)` fazem o mesmo (veja a [API Python](../referencia/api-python.md)).
