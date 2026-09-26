# Gerar os tópicos

Depois da coleta, `mapa topicos` descobre os assuntos do corpus, dá um nome a cada um e prepara o mapa do painel. Para entender o método por trás de cada passo, veja [Como os tópicos são construídos](../explicacoes/topicos.md).

## Antes de começar

- O projeto precisa ter documentos coletados (`mapa coletar`), **pelo menos 50** com título ou resumo.
- O Ollama precisa estar rodando, com o modelo de embeddings e o de rótulos do projeto instalados. `mapa diagnostico` confere as duas coisas e mostra se cabem na memória livre agora.

## Rodar

```bash
mapa topicos
```

A primeira execução no piloto (4.275 artigos) leva cerca de 4 minutos nos embeddings e mais uns 3 nos rótulos. As seguintes levam segundos: embeddings, reduções do UMAP e rótulos ficam em cache. A saída termina com os macrotemas e os números da etapa:

```text
Tópicos prontos: 50 tópicos em 7 macrotemas, 4.275 documentos: 2.886 no núcleo, 918 reatribuídos, 471 sem tópico (ARI 0,90), em 11 s.
```

- **Núcleo**: os documentos que o agrupamento reuniu em cada tópico.
- **Reatribuídos**: os que ficaram de fora do agrupamento, mas têm vizinhos suficientes num tópico.
- **Sem tópico**: os que não pertencem claramente a nenhum. No mapa, aparecem em cinza.
- **ARI**: a estabilidade entre sementes diferentes (de 0 a 1; perto de 1, os tópicos não dependem do acaso).

| Opção | Para quê |
|---|---|
| `--sem-rotulos` | Não carrega o modelo de linguagem: os rótulos são as palavras-chave mais fortes. Útil com pouca memória ou para um primeiro olhar rápido |
| `--refazer-embeddings` | Recalcula os embeddings de todos os documentos, em vez de usar o cache |
| `--semente 7` | Troca a semente principal do UMAP (os tópicos casados mantêm número e cor) |
| `-P pasta` | Indica o projeto quando você está fora da pasta dele |

## Conferir

```bash
mapa status
```

A seção **Tópicos** mostra quantos tópicos e macrotemas há, a estabilidade e a proporção de documentos no núcleo, reatribuídos e sem tópico. Depois de uma coleta que mude o corpus, ela avisa que os tópicos estão desatualizados. O painel (`mapa painel`) mostra os macrotemas na página inicial e o mapa dos documentos (veja [Ler o mapa](ler-o-mapa.md)).

Para analisar os tópicos num notebook, a view `atribuicoes` da [API Python](../referencia/api-python.md) traz o tópico, a posição no mapa e os vizinhos de cada documento.

## Ajustar

- **Rótulos.** Para corrigir o nome de um tópico, escreva-o no arquivo `rotulos.yaml` da pasta do projeto, pelo número do tópico ([como](../explicacoes/topicos.md#11-rotulos)). O que está lá tem prioridade e continua valendo nas próximas execuções.
- **Parâmetros.** A seção `topicos:` do `mapa.yaml` controla o tamanho mínimo dos tópicos, o número de macrotemas e a reatribuição (veja a [referência da configuração](../referencia/configuracao.md)). Os padrões foram calibrados no piloto ([ADR 0007](../decisoes/0007-parametros-dos-topicos.md)). Para um corpus muito diferente, refaça a calibração:

    ```bash
    uv run python scripts/calibrar_topicos.py caminho/do/projeto  # fora do CI
    ```

## Problemas comuns

| Mensagem | O que fazer |
|---|---|
| "precisa de ~7,6 GB e há ... disponíveis" | O modelo de rótulos não cabe na memória livre agora. Feche programas pesados e rode de novo, ou use `--sem-rotulos` |
| "A memória do computador acabou no meio dos rótulos" | A etapa parou para não travar o computador. Os rótulos já escritos estão guardados: libere memória e rode de novo |
| "os tópicos precisam de pelo menos 50" | Amplie o recorte (mais anos ou revistas) e rode `mapa coletar` |
| "não encontrou nenhum tópico" | Diminua `topicos.min_cluster_size` no `mapa.yaml` |
