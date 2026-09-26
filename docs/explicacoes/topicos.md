# Como os tópicos são construídos

Os tópicos do `mapa-da-ciencia` não vêm de uma lista pronta: eles saem dos próprios textos. Artigos que tratam de assuntos parecidos ficam perto uns dos outros num espaço de muitas dimensões, e o agrupamento encontra as regiões mais densas desse espaço. Esta página descreve cada passo e as escolhas por trás deles.

Para rodar a etapa, veja o guia [Gerar os tópicos](../guias/topicos.md) ou a [parte 2 do tutorial](../tutoriais/primeiro-mapa-topicos.md); para ler o resultado no painel, o guia [Ler o mapa](../guias/ler-o-mapa.md).

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
- `topicos.selecao`: `leaf`, o padrão, fica com as regiões densas mais finas, e os tópicos mudam pouco quando o corpus muda; `eom` prefere tópicos maiores, mas uma mudança pequena nos dados pode trocar um tópico grande por vários pequenos.

Os padrões foram calibrados no piloto ([ADR 0007](../decisoes/0007-parametros-dos-topicos.md)): 57 tópicos, com números parecidos nas três sementes testadas e nenhum tópico acima de 3,5% do corpus.

Os documentos que o HDBSCAN agrupa formam o **núcleo** de cada tópico. Os demais ficam como **ruído**: não pertencem claramente a nenhuma região densa. O ruído não é um erro, e sim uma informação: são trabalhos isolados, de fronteira ou que misturam assuntos. Com menos de 50 documentos, não há tópicos: a etapa para e sugere ampliar o recorte.

Os documentos **só com título** nunca entram no núcleo. Textos curtos ficam parecidos entre si pela forma, e não pelo assunto: no piloto, os ensaios sem resumo formavam um "tópico" próprio. Eles ainda podem entrar num tópico pela vizinhança (próxima seção), marcados.

## 6. Reatribuição do ruído

No piloto, um terço dos documentos fica como ruído, com qualquer configuração estável do agrupamento ([ADR 0007](../decisoes/0007-parametros-dos-topicos.md)). Deixá-los de fora esconderia um terço do corpus, e forçar parâmetros para reduzir o ruído cria tópicos gigantes e instáveis. O `mapa` faz outra coisa: **reatribui por vizinhança**.

- Cada documento de ruído olha para os seus 15 vizinhos mais próximos (no espaço dos embeddings, não no UMAP).
- Os vizinhos que estão no núcleo de algum tópico votam no próprio tópico, com peso igual à similaridade.
- O documento vai para o tópico vencedor se ele tiver ao menos 3 desses vizinhos (`topicos.votos_minimos`). Senão, fica **sem tópico**.

No piloto, 66,5% dos documentos estão no núcleo, 22,5% são reatribuídos e 11% ficam sem tópico. Os reatribuídos ficam marcados (`atribuicao: vizinho`) e aparecem assim no cartão do mapa.

O núcleo é a base de tudo o que descreve um tópico: palavras-chave, documentos representativos, contornos no mapa e estabilidade. Os reatribuídos entram nas contagens e nas séries no tempo. As séries quase não mudam com eles: a correlação entre a proporção anual de cada tópico só com o núcleo e com os reatribuídos tem mediana 0,94.

## 7. Estabilidade

O UMAP depende de uma semente aleatória. Para saber se os tópicos são do corpus e não do acaso, o agrupamento roda com três sementes (`topicos.sementes`), e o `mapa` mede a concordância entre elas pelo **índice de Rand ajustado** (ARI), sobre os documentos que estão no núcleo nas duas execuções comparadas. O ARI vai de 0 (concordância de acaso) a 1 (os mesmos grupos).

No piloto, o ARI é 0,89. Os tópicos publicados vêm da primeira semente; as outras só medem a estabilidade.

## 8. Palavras-chave e documentos representativos

As palavras-chave de cada tópico saem de uma variante do TF-IDF por classe, o **c-TF-IDF** (a mesma ideia do BERTopic): cada tópico é tratado como um grande documento, e um termo pesa mais quanto mais frequente é nele e mais raro no resto do corpus.

- Os termos são palavras de três letras ou mais e pares de palavras vizinhas ("ciência política", "rio janeiro").
- Palavras vazias em português, inglês e espanhol ficam de fora, assim como palavras do gênero acadêmico ("artigo", "análise", "resultados") que aparecem em quase todo resumo.
- Um termo precisa aparecer em ao menos três documentos do corpus.
- Um par de palavras substitui as palavras soltas que contém: entra "rio janeiro", e não "rio" e "janeiro".
- Só o **núcleo** de cada tópico conta.

As palavras-chave são calculadas nos textos no **idioma de exibição** (`recorte.idioma_exibicao`, português por padrão), com o de análise como reserva. Revistas que publicam só em inglês (comuns em relações internacionais) trazem termos em inglês para os tópicos em que predominam.

Os **documentos representativos** são os cinco do núcleo mais próximos do centro do tópico (a média dos embeddings). Eles aparecem no painel e, junto com as palavras-chave, orientam o rótulo.

## 9. Macrotemas

Dezenas de tópicos, cada um com uma cor, seriam ilegíveis. Os tópicos próximos são agrupados em **macrotemas** (até 7 por padrão, no máximo 8: `topicos.macrotemas`), por aglomeração hierárquica (método de Ward) dos centros dos tópicos no espaço dos embeddings. Com poucos tópicos, os macrotemas são menos, para que cada um reúna em média ao menos três tópicos: 13 tópicos formam 4 macrotemas, e não 7 grupos de um ou dois tópicos.

Cada macrotema tem uma cor bem distinta das outras, inclusive para quem tem daltonismo, e os tópicos dele são variações dessa cor. As cores são geradas no espaço OKLCH, em que distâncias iguais parecem diferenças iguais, e conferidas em teste: contraste suficiente sobre os dois fundos da interface e diferença perceptível entre macrotemas sob simulação de protanopia, deuteranopia e tritanopia.

## 10. Identidade estável

A cada execução, o HDBSCAN numera os tópicos de um jeito. Para que as cores, os links do mapa e os rótulos editados à mão continuem valendo quando você coleta mais anos ou muda um parâmetro, o `mapa` casa os tópicos novos com os da execução anterior pela **sobreposição de membros**: dois tópicos são o mesmo se boa parte dos documentos do núcleo de um estiver no núcleo do outro (índice de Jaccard de pelo menos 0,3, com casamento ótimo entre as duas listas).

- Um tópico casado mantém o número, o rótulo e, se continuar no mesmo macrotema, a cor.
- Um tópico novo ganha um número nunca usado antes: um link antigo nunca aponta para outro assunto.
- Os macrotemas persistem: um tópico casado continua no macrotema que tinha, e um tópico novo entra no macrotema do tópico casado mais parecido. A aglomeração só roda de novo quando menos da metade dos tópicos casa, ou com `mapa topicos --refazer-macrotemas`. Refazê-la a cada execução mudaria de cor metade dos tópicos do piloto.
- Trocar o modelo de embeddings ou o idioma de análise recomeça o casamento (os números continuam de onde pararam).

No piloto, rodar de novo com outra semente mantém o número e a cor de 50 dos 57 tópicos; tirar os artigos de 2010 também mantém 50 dos 57.

## 11. Rótulos

Cada tópico e cada macrotema ganha um **rótulo** curto e uma **descrição** em português, escritos pelo modelo de linguagem local do projeto (`modelos.rotulos`, o `qwen3.5:9b` no perfil padrão). O modelo recebe as 15 palavras-chave e os 5 títulos representativos do tópico; para um macrotema, recebe os rótulos dos seus tópicos. As respostas seguem um esquema JSON, com temperatura 0 e semente fixa.

Alguns cuidados:

- **Acentos.** Modelos pequenos às vezes perdem acentos ("Genero" em vez de "Gênero"). O rótulo é conferido contra as palavras-chave e os títulos; se uma palavra perdeu o acento, o modelo recebe um pedido que aponta a palavra. Se ainda assim faltar, o acento é corrigido pela forma do vocabulário. Só contam palavras de quatro letras ou mais cuja forma sem acento não é também uma palavra: "e" e "é", "a" e "à" ou "critica" e "crítica" nunca são trocadas.
- **Caixa de frase.** O modelo é orientado a usar maiúscula só na primeira palavra, nas siglas e nos nomes próprios, mas o `qwen3.5:9b` ainda devolve alguns rótulos com Iniciais Maiúsculas. O `rotulos.yaml` (abaixo) corrige os que incomodarem.
- **Estabilidade.** Um tópico que continua o mesmo de uma execução para outra (veja a seção anterior) e cujas palavras-chave mudaram pouco mantém o rótulo, sem chamar o modelo de novo, desde que o rótulo tenha sido escrito pela versão atual das instruções ao modelo.
- **Cache.** As respostas ficam no `estado.sqlite`: rodar de novo sem mudanças não chama o modelo.
- **Memória.** O modelo só é carregado se couber na memória livre, e a etapa para, sem perder o que já foi feito, se a memória acabar no meio.

Os rótulos são um ponto de partida. Para corrigir um, crie o arquivo `rotulos.yaml` na pasta do projeto, com o número do tópico (ou do macrotema) que aparece no painel:

```yaml
topicos:
  12:
    rotulo: Judicialização da política
    descricao: O Supremo Tribunal Federal e o Judiciário como atores políticos.
macrotemas:
  0:
    rotulo: Instituições e eleições
```

O que está no `rotulos.yaml` tem prioridade sobre o modelo, e continua valendo nas execuções seguintes, porque o número do tópico é estável. Sem modelo de linguagem (`mapa topicos --sem-rotulos`), os rótulos são as três palavras-chave mais fortes.

## 12. Onde ficam os resultados

Tudo o que a etapa produz fica em `dados/topicos/`, dentro da pasta do projeto:

| Arquivo | Conteúdo |
|---|---|
| `atribuicoes.parquet` | Uma linha por documento: tópico (−1 = sem tópico), atribuição (`cluster` ou `vizinho`), coordenadas no mapa, os 5 vizinhos e o texto de análise usado (idioma e marca) |
| `resultado.json` | Os tópicos e macrotemas: rótulos, cores, palavras-chave, representativos, parâmetros e estabilidade |
| `identidade.json` | O estado da identidade estável, usado pela próxima execução |
| `reducoes/` | As reduções do UMAP em cache |

Ao fim da etapa, o `mapa` exporta o resultado para `saida/dados/`, nos arquivos do [contrato de dados](../referencia/contrato.md) que o painel lê (`documentos.json`, `topicos.json`, `agregados.json` e os detalhes). Se uma coleta nova mudar o corpus depois, os tópicos ficam desatualizados: o painel volta a mostrar só os números do corpus até a próxima execução de `mapa topicos`.

O `atribuicoes.parquet` pode ser lido direto pelo pandas, pelo polars ou pelo R, e cruzado com `dados/documentos.parquet` pelo `id`. No piloto, a etapa inteira leva cerca de 20 segundos quando os embeddings já estão em cache (4 minutos na primeira vez, mais uns 3 minutos para os rótulos).
