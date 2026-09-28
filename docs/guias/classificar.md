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

Cada resposta é guardada no `estado.sqlite` assim que chega, e o resultado em `dados/classificacao/` é regravado a cada 50 documentos, então o painel e as consultas já mostram o que foi classificado enquanto a etapa corre. Se a etapa for interrompida (++ctrl+c++, falta de memória, o computador que dormiu), rode o mesmo comando de novo: ela continua de onde parou, sem refazer nada.

No fim, a saída mostra, por variável, os valores mais frequentes e a taxa de **evidência literal** (o trecho aparece no resumo tal como o modelo o copiou). Também mostra quantas respostas vieram em JSON válido na primeira tentativa e o tempo mediano por documento. Documentos sem resumo ficam de fora e aparecem na contagem.

Outras formas de rodar:

| Opção | O que faz |
|---|---|
| `--limite N` | Classifica só os primeiros N da fila (a amostra de validação primeiro, depois por id). |
| `--somente-amostra` | Classifica só os documentos da amostra de validação (`mapa validar amostra`). Útil para começar a validação antes da rodada completa, ou para medir na amostra uma versão nova do modelo (veja abaixo). |
| `--modelo X` | Usa outro modelo do Ollama, para comparar com o principal na amostra de validação. O resultado fica ao lado do principal, e o painel continua mostrando o do modelo do `mapa.yaml`. |

## Quando refazer

A chave de cada resposta guardada inclui o texto, o codebook, o modelo (com a versão exata) e os parâmetros. Por isso:

- **mudar o codebook** (uma definição, uma categoria, um exemplo) faz a próxima rodada classificar tudo de novo. O `mapa status` avisa: "a classificação é de outro codebook";
- trocar o modelo, atualizá-lo no Ollama ou mudar os parâmetros dele (`num_ctx`, `temperatura`, `semente`, `pensar`) também refaz tudo;
- uma coleta nova só classifica os documentos novos.

Teste o codebook numa amostra (`--limite 20`) antes de rodar o corpus inteiro.

### Uma versão nova do modelo ou dos parâmetros

O resultado principal, o que o painel mostra, só é substituído por uma rodada que cobre o corpus atual: sem `--somente-amostra`, `--estimar` ou `--limite`, que chega ao fim sem ser interrompida e deixa no máximo 2% dos documentos sem resposta válida (no mínimo 1). Qualquer outra rodada, inclusive uma completa com falhas demais, nunca tira documentos dele: ela só grava no resultado principal se ele ainda não existe ou se todo documento classificado nele, e que ainda está no corpus, continua classificado (a retomada de uma rodada interrompida, por exemplo). Conta quais documentos, e não quantos: uma rodada com o mesmo número de documentos pode ter trocado alguns. Assim, depois de atualizar o modelo ou mudar os parâmetros, um `--somente-amostra`, um `--estimar` ou uma rodada interrompida não apagam a classificação anterior, e uma rodada completa em que a versão nova falha demais também não: com tantas falhas, ela provavelmente tem um problema (um parâmetro que corta a resposta, um modelo que não segue o esquema). Isso importa porque, depois de um `ollama pull`, as respostas da versão antiga continuam no cache, mas o Ollama não volta a oferecer a versão antiga.

Quando uma rodada não pode gravar no resultado principal, as respostas dela vão para um resultado à parte (`dados/classificacao/<modelo>__<hash do codebook>__a-parte.*`), e a saída avisa. O `mapa status` mostra essa versão à parte. A comparação com o resultado principal na amostra de validação, como `<modelo> (versão nova)`, aparece em `mapa validar metricas`, no relatório da validação e na vista Validação do painel, que calcula as métricas na hora. O resto do painel (o mapa, a classificação, as contagens) continua com o resultado completo, e a versão nova não entra no `validacao.json` exportado, que é o que vai para o site publicado. Para medir o efeito de uma versão nova antes de rodar o corpus inteiro, use `--somente-amostra`. Há um resultado à parte por modelo e codebook, sempre o da última rodada que não pôde gravar no principal: um novo toma o lugar do anterior, e ele sai quando o resultado principal é gravado de novo, pela versão nova ou por outra (um parâmetro que voltou ao valor antigo, por exemplo).

### Documentos que falham sempre

Um documento sem resposta válida depois de duas tentativas fica sem classificação, e a saída e o `mapa status` dizem quais são. Com temperatura 0 e semente fixa (o padrão), o modelo responde igual a cada rodada, e a falha tende a se repetir: rodar de novo não resolve, e a classificação continua "incompleta" no `mapa status` e no painel. Nesse caso:

1. **Veja o documento** (o id vem na saída): um resumo muito longo, cortado ou com a formatação quebrada costuma ser a causa.
2. **Aumente `num_ctx`** ou **desligue `pensar`** em `modelos.classificacao`, no `mapa.yaml`, se o resumo é longo ou se o raciocínio consome o contexto. Isso muda a execução: a próxima rodada classifica tudo de novo, e o resultado principal só é trocado quando ela cobre o corpus. Meça antes na amostra (`--somente-amostra`).
3. **Ou deixe como está.** Os documentos que falharam ficam fora das contagens da classificação, e o `mapa status` continua dizendo quantos são.

## Consultar o resultado

O resultado fica em `dados/classificacao/`, um arquivo por modelo e codebook, e vai para o painel quando a etapa termina. Em Python:

```python
import mapa_da_ciencia.api as mapa

mapa.consultar(
    "cp-scielo",
    """
    SELECT valor, count(*) AS n
    FROM classificacoes
    WHERE variavel = 'abordagem'
    GROUP BY valor ORDER BY n DESC
""",
)
```

A view `classificacoes` tem uma linha por documento × variável, com o valor, a evidência, o status da conferência (`literal`, `aproximada`, `ausente` ou `dispensada`) e a posição do trecho no resumo. Veja a [API Python](../referencia/api-python.md#tabelas-para-consulta).

## Antes de usar os números

Um modelo pequeno erra. Antes de tirar conclusões das proporções, meça a concordância do modelo com uma leitura de referência na amostra de validação: veja [Codificar a amostra](codificar-a-amostra.md).
