# Classificar os resumos

A etapa `mapa classificar` lê o título e o resumo de cada documento e preenche as variáveis do codebook do projeto (`codebook.yaml`) com um modelo local. Para cada resposta, o modelo copia do resumo um trecho curto que a justifica, a **evidência**, e a etapa confere se esse trecho está mesmo no texto. Esta página mostra como rodar. Para entender o método, veja o [ADR 0011](../decisoes/0011-classificacao-ancorada-em-evidencia.md); para escrever as variáveis, [Escrever um codebook](codebook.md).

## Antes de começar

- O projeto precisa de um corpus coletado (`mapa coletar`) e de um codebook. `mapa novo` já traz o codebook de exemplo, com 6 variáveis sobre método e recorte.
- O Ollama precisa estar rodando, com o modelo de `modelos.classificacao.modelo` do `mapa.yaml` instalado (`qwen3.5:9b` no perfil padrão). `mapa diagnostico` confere as duas coisas.
- A classificação é a etapa mais longa do pipeline: no Mac de desenvolvimento (M4 Pro, 24 GB), cada resumo leva uns segundos, e o piloto inteiro, horas. Feche o que puder antes de rodar, porque o modelo ocupa uns 7 GB de memória.

## Estimar o tempo antes

```bash
uv run mapa classificar --estimar
```

Classifica 5 documentos, mostra os resultados e projeta quanto falta neste computador. Os 5 ficam guardados: a rodada completa não os refaz.

## Rodar

```bash
uv run mapa classificar
```

Cada resposta é guardada no `estado.sqlite` assim que chega. Se a etapa for interrompida (++ctrl+c++, falta de memória, o computador que dormiu), rode o mesmo comando de novo: ela continua de onde parou, sem refazer nada.

No fim, a saída mostra, por variável, os valores mais frequentes e a taxa de **evidência literal** (o trecho aparece no resumo tal como o modelo o copiou). Também mostra quantas respostas vieram em JSON válido na primeira tentativa e o tempo mediano por documento. Documentos sem resumo ficam de fora e aparecem na contagem.

Outras formas de rodar:

| Opção | O que faz |
|---|---|
| `--limite N` | Classifica só os primeiros N da fila (a amostra de validação primeiro, depois por id). |
| `--somente-amostra` | Classifica só os documentos da amostra de validação (`mapa validar amostra`). Útil para começar a validação antes da rodada completa. |
| `--modelo X` | Usa outro modelo do Ollama, para comparar com o principal na amostra de validação. O resultado fica ao lado do principal, e o painel continua mostrando o do modelo do `mapa.yaml`. |

## Quando refazer

A chave de cada resposta guardada inclui o texto, o codebook, o modelo (com a versão exata) e os parâmetros. Por isso:

- **mudar o codebook** (uma definição, uma categoria, um exemplo) faz a próxima rodada classificar tudo de novo. O `mapa status` avisa: "a classificação é de outro codebook";
- trocar o modelo ou atualizá-lo no Ollama também refaz tudo;
- uma coleta nova só classifica os documentos novos.

Teste o codebook numa amostra (`--limite 20`) antes de rodar o corpus inteiro.

## Consultar o resultado

O resultado fica em `dados/classificacao/`, um arquivo por modelo e codebook, e vai para o painel quando a etapa termina. Em Python:

```python
import mapa_da_ciencia.api as mapa

mapa.consultar("cp-scielo", """
    SELECT valor, count(*) AS n
    FROM classificacoes
    WHERE variavel = 'abordagem'
    GROUP BY valor ORDER BY n DESC
""")
```

A view `classificacoes` tem uma linha por documento × variável, com o valor, a evidência, o status da conferência (`literal`, `aproximada`, `ausente` ou `dispensada`) e a posição do trecho no resumo. Veja a [API Python](../referencia/api-python.md#tabelas-para-consulta).

## Antes de usar os números

Um modelo pequeno erra. Antes de tirar conclusões das proporções, meça a concordância do modelo com uma leitura de referência na amostra de validação: veja [Codificar a amostra](codificar-a-amostra.md).
