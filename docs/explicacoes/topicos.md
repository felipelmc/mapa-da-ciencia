# Como os tópicos são construídos

Os tópicos do `mapa-da-ciencia` não vêm de uma lista pronta: eles saem dos próprios textos. Artigos que tratam de assuntos parecidos ficam perto uns dos outros num espaço de muitas dimensões, e o agrupamento encontra as regiões mais densas desse espaço. Esta página descreve cada passo e as escolhas por trás deles.

!!! note "Em construção no marco M3"
    Por enquanto, esta página descreve o texto de análise, os embeddings, a vizinhança, o UMAP e o HDBSCAN. A reatribuição do ruído, as palavras-chave, os rótulos, os macrotemas e a estabilidade entram ao longo do M3.

## 1. O texto de análise

Cada documento é representado por **título e resumo no mesmo idioma**. O idioma é o de `recorte.idioma_analise` no `mapa.yaml`: o inglês, por padrão, porque é o único presente em quase todo o corpus do SciELO ([ADR 0004](../decisoes/0004-embeddings-e-idioma-de-analise.md)).

Nem todo artigo tem resumo em inglês. O texto de análise nunca junta idiomas diferentes, e cada documento fica marcado com a fonte do texto:

| Marca | Quando | Texto usado |
|---|---|---|
| `resumo` | Há resumo no idioma de análise | Título e resumo nesse idioma (ou só o resumo, se o título não existir nesse idioma) |
| `reserva` | Não há resumo no idioma de análise | Título e resumo em outro idioma, na ordem: português, espanhol, inglês, francês |
| `so_titulo` | O documento não tem resumo | Só o título, de preferência no idioma de análise |

A reserva funciona porque o modelo de embeddings é multilíngue: no spike M0a, 99,9% dos resumos em português encontraram a própria versão em inglês como vizinho mais próximo. No piloto de ciência política (4.275 documentos), 4.161 entram com o resumo em inglês, 96 (2,2%) como reserva e 18 (0,4%) só pelo título. A marca aparece no cartão de cada documento no mapa e nas contagens da etapa. Um documento sem título nem resumo fica fora dos tópicos.

## 2. Embeddings

Um **embedding** é uma lista de números (1.024, no modelo padrão) que resume o sentido de um texto. Textos sobre assuntos parecidos têm embeddings parecidos, mesmo sem palavras em comum.

- O modelo padrão é o `qwen3-embedding:0.6b`, rodando no Ollama da sua máquina ([Modelos locais](modelos-locais.md)).
- Textos maiores que o contexto (`modelos.embeddings.num_ctx`, 2.048 tokens por padrão) são truncados. Título e resumo cabem com folga.
- Antes de carregar o modelo, o `mapa` confere se ele cabe na memória livre, e o descarrega ao terminar.

Os vetores ficam em `dados/embeddings/<modelo>@<digest>.npz`. Na segunda execução, só os textos novos ou alterados vão ao Ollama. O **digest** identifica o arquivo exato do modelo: se o Ollama baixar uma versão nova do mesmo nome, os embeddings são recalculados, e os antigos ficam guardados.

Com o modelo padrão, o piloto leva cerca de 4 minutos na primeira vez (18 documentos por segundo num Mac M4 Pro); nas seguintes, vem do cache, sem passar pelo Ollama.

## 3. Vizinhança

Para cada documento, o `mapa` calcula os 15 mais parecidos (similaridade de cosseno entre os embeddings), de forma exata. Esse grafo de vizinhança é a base de tudo o que vem depois: o UMAP, a estabilidade e os 5 vizinhos mostrados no cartão de cada documento no mapa.

## 4. UMAP: de 1.024 dimensões para 5 e para 2

Agrupar diretamente em 1.024 dimensões funciona mal: nesse espaço, quase todas as distâncias ficam parecidas. O [UMAP](https://umap-learn.readthedocs.io) reduz os embeddings preservando a vizinhança de cada documento. Ele roda duas vezes:

- em **5 dimensões**, com os pontos podendo se sobrepor (`topicos.min_dist: 0`), para o agrupamento;
- em **2 dimensões**, um pouco mais espalhado (`topicos.min_dist_mapa: 0.1`), para o mapa.

As duas reduções usam a mesma semente e o mesmo grafo de vizinhança, e ficam em cache: reexecutar sem mudar os dados nem os parâmetros não roda o UMAP de novo.

!!! warning "O que as posições no mapa querem dizer"
    Documentos próximos no mapa tratam de assuntos parecidos. Os eixos, porém, não têm significado, e distâncias grandes são pouco confiáveis: dois grupos distantes não são necessariamente "mais diferentes" que dois grupos a meia distância. Na mesma máquina, a mesma semente dá o mesmo mapa; em máquinas diferentes, as posições podem variar um pouco.

## 5. HDBSCAN: os tópicos

O [HDBSCAN](https://scikit-learn.org/stable/modules/clustering.html#hdbscan) procura regiões densas na redução de 5 dimensões. Não é preciso dizer quantos tópicos existem, só o tamanho mínimo de um tópico:

- `topicos.min_cluster_size`: menor tópico, em documentos. Vazio, é automático: 1 a cada 200 documentos, nunca menos de 10 (21 no piloto).
- `topicos.min_samples`: quão conservador é o agrupamento. Valores maiores deixam mais documentos de fora.
- `topicos.selecao`: `eom` prefere tópicos maiores; `leaf`, tópicos menores e mais numerosos.

Os documentos que o HDBSCAN agrupa formam o **núcleo** de cada tópico. Os demais ficam como **ruído**: não pertencem claramente a nenhuma região densa. O ruído não é um erro, e sim uma informação: são trabalhos isolados, de fronteira ou que misturam assuntos. Com menos de 50 documentos, não há tópicos: a etapa para e sugere ampliar o recorte.
