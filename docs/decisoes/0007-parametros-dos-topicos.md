# 0007. Parâmetros dos tópicos

- **Status:** aceita
- **Data:** 2026-09-26
- **Marco:** M3

## Contexto

O spike M0a (ADR 0004) escolheu o modelo de embeddings e o idioma de análise, mas deixou os parâmetros do agrupamento em aberto: com os valores do spike, 27% dos documentos ficaram como ruído, sem tópico. O M3 precisa de padrões para a seção `topicos:` do `mapa.yaml` que deem, num corpus como o piloto (4.275 artigos de ciência política):

- um número de tópicos legível num mapa e útil para estratificar a validação (M5);
- estabilidade: sementes diferentes, ou uma coleta um pouco diferente, não podem produzir tópicos muito diferentes;
- nenhum tópico gigante, que esconda assuntos distintos sob um rótulo só.

A primeira versão desta decisão ficou com a seleção `eom` do HDBSCAN, a do spike. Ela foi revista ainda no M3, depois que uma correção pequena no corpus derrubou a estabilidade desse padrão (abaixo, "Sensibilidade a mudanças no corpus").

## Evidência

`scripts/calibrar_topicos.py` no piloto (embeddings `qwen3-embedding:0.6b` em inglês, com reserva marcada), em 2026-09-26. Grade: vizinhos do UMAP (15, 30) × `min_cluster_size` (10, 15, 21, 30, 40) × `min_samples` (1, 3, 5, 10) × seleção (`eom`, `leaf`), cada combinação com 3 sementes (42, 7, 2024). A grade mede o HDBSCAN puro, antes da reatribuição.

- **Ruído:** fração de documentos que o HDBSCAN deixa sem tópico, na semente principal.
- **Maior:** o maior tópico, como fração do corpus.
- **ARI:** índice de Rand ajustado médio entre os pares de sementes, sobre os documentos que estão no núcleo nas duas execuções.

Linhas selecionadas (15 vizinhos, salvo indicação; a grade completa sai do script):

| `min_cluster_size` | `min_samples` | Seleção | Tópicos (3 sementes) | Ruído | Maior | ARI |
|---|---|---|---|---|---|---|
| 15 | 5 | leaf | 85 (85/83/84) | 42,3% | 2,1% | 0,915 |
| **21 (automático)** | **5** | **leaf** | **58 (58/61/61)** | **32,8%** | **3,4%** | **0,887** |
| 21 | 10 | leaf | 51 (51/49/52) | 41,1% | 3,4% | 0,913 |
| 30 | 5 | leaf | 41 (41/40/42) | 36,2% | 3,4% | 0,894 |
| 40 | 5 | leaf | 33 (33/33/32) | 29,2% | 5,5% | 0,904 |
| 21 (automático) | 5 | eom | 53 (53/44/51) | 28,0% | 5,5% | 0,695 |
| 40 | 1 | eom | 24 (24/26/25) | 17,0% | 23,0% | 0,634 |
| 21 (30 vizinhos) | 5 | leaf | 49 (49/53/52) | 36,9% | 6,1% | 0,916 |

O que a grade mostra:

- **O ruído é do corpus, não dos parâmetros.** Nas combinações estáveis (ARI ≥ 0,85) e sem tópico gigante (nenhum acima de 10% do corpus), ele fica entre 27% e 51%. Ruído abaixo de 25% só aparece com `eom`, e sempre com um preço: um tópico com 14% a 23% do corpus, ou estabilidade baixa (ARI abaixo de 0,76).
- **`leaf` é estável em toda a grade** (ARI de 0,84 a 0,96), com tópicos menores e um pouco mais de ruído que `eom`. O número de tópicos varia pouco entre as sementes.
- **30 vizinhos não ajudam:** tópicos maiores (até 6,5% do corpus com `leaf`, contra 5,5% com 15 vizinhos), sem reduzir o ruído de forma útil.

**Sensibilidade a mudanças no corpus.** A grade rodou duas vezes: antes e depois de a coleta passar a descartar resumos repetidos, o que trocou o texto de análise de 10 dos 4.275 documentos, 0,2% do corpus (ADR 0003, "Correção no M3").

- Com `eom`, o padrão do spike (21 e 5) foi de 50/50/49 tópicos e ARI 0,90 para 53/44/51 e ARI 0,69. Na grade inteira, o ARI de `eom` mudou até 0,27 (mediana 0,04). A seleção `eom` escolhe entre um tópico grande e os seus subtópicos pela "massa" de cada um, e uma mudança mínima nos dados vira essa escolha.
- Com `leaf`, o ARI mudou no máximo 0,06 (mediana 0,01), e a média da grade ficou em 0,90 nas duas rodadas. O padrão escolhido (21 e 5) foi de 57/56/60 tópicos e ARI 0,888 para 58/61/61 e 0,887.

**Documentos só com título.** Com `leaf`, 21 dos 28 documentos que não têm resumo formavam um tópico próprio, de 29 documentos, junto com textos sem relação entre si (quase todos ensaios da *Novos Estudos CEBRAP*). Textos curtos ficam parecidos entre si pela forma, e não pelo assunto.

**Reatribuição do ruído.** Um documento de ruído vai para o tópico com mais vizinhos seus no núcleo, se forem pelo menos 3 dos 14 mais próximos (o grafo de 15 inclui o próprio documento; similaridade de cosseno entre os embeddings, não no UMAP). Para calibrar o limite: um documento típico do núcleo tem 8 dos 14 vizinhos no próprio tópico, e o 10º percentil tem 4. Com o limite em 3 e os padrões finais, no piloto:

| | Documentos | % do corpus |
|---|---|---|
| Núcleo (HDBSCAN) | 2.845 | 66,5% |
| Ruído reatribuído por vizinhança | 963 | 22,5% |
| Sem tópico | 467 | 10,9% |

- **O ruído não se concentra** em anos nem em revistas: fica entre 28% e 38% por revista (mais na *RBCS*, na *Contexto Internacional* e na *Lua Nova*) e entre 26% e 40% por ano, com exceção de 2010 (45%).
- **As séries anuais dos tópicos quase não mudam** com a reatribuição: a correlação entre a proporção anual de cada tópico só com o núcleo e com os reatribuídos tem mediana 0,94 (mínima 0,74), e a maior diferença numa proporção anual é de 3,9 pontos percentuais (mediana 1,1).
- **A estabilidade cai onde deveria:** o ARI entre sementes é 0,89 no núcleo e 0,78 contando os reatribuídos, que são documentos de fronteira. Por isso a estabilidade publicada é a do núcleo, e a atribuição por vizinhança fica marcada.
- Ficam sem tópico 19 dos 28 documentos só com título, 8 dos 88 com resumo em reserva e 440 dos 4.159 com resumo em inglês.

Custo: kNN exato em 0,2 s; UMAP de 5 dimensões em 3,5 a 5 s por semente (9 s na primeira, com a compilação do numba); HDBSCAN em menos de 1 s. A grade inteira (80 combinações × 3 sementes) leva cerca de 45 s, com pico de 0,77 GB de memória.

**Leitura dos tópicos.** A lista completa dos 57 tópicos do piloto (palavras-chave e títulos representativos, em `dados/topicos/resultado.json`) foi lida para responder à pergunta aberta do ADR 0004: tópicos calculados sobre textos em inglês são legíveis?

- Cada tópico corresponde a uma subárea reconhecível: judicialização e STF, comunicação política digital, ideologia e voto, partidos, Legislativo, coalizões ministeriais, carreiras políticas, financiamento de campanha e gênero, participação e conselhos, desigualdade educacional, sindicalismo, relações raciais e cotas, religião e política, memória da ditadura, aborto no Congresso, Mercosul, China e BRICS, cooperação Sul-Sul, operações de paz, securitização, pensamento social brasileiro, Maquiavel, democracia deliberativa, legitimidade policial, entre outras.
- **O idioma não separa os tópicos.** A mediana é de 16% de documentos em inglês por tópico, e só um passa de 80% (cooperação Sul-Sul para o desenvolvimento, 86%). Os 12 com maioria em inglês são de relações internacionais, área em que várias revistas publicam só em inglês, e mesmo esses misturam artigos em português e em inglês.
- Pontos fracos: três tópicos amplos, de 100 a 150 documentos no núcleo (STF, judiciário e corrupção; teoria social, de Weber a Luhmann e ao pensamento decolonial; política externa brasileira); e um macrotema heterogêneo, de 13 tópicos, que junta pensamento social, a ciência política como disciplina, religião, relações raciais, movimentos sociais, memória, artes e gênero.

## Decisão

1. **Padrões da seção `topicos:`:** 15 vizinhos, `min_dist` 0 no UMAP de agrupamento, `min_cluster_size` automático (1 a cada 200 documentos, mínimo 10), `min_samples` 5, **seleção `leaf`**, sementes 42, 7 e 2024. `leaf` troca um pouco mais de ruído (que a reatribuição absorve) por tópicos que não mudam com uma correção pequena no corpus.
2. **O ruído é tratado depois do agrupamento, e não escondido por parâmetros.** Como um terço do corpus fica de fora com qualquer configuração estável, a reatribuição por vizinhança é parte do método, com `topicos.votos_minimos: 3`. Os documentos reatribuídos ficam marcados (`atribuicao: vizinho`), e o núcleo continua sendo a base das palavras-chave, dos representativos, dos contornos e da estabilidade.
3. **Documentos só com título não entram no núcleo.** Eles podem entrar num tópico pela vizinhança, marcados, e um tópico que fica abaixo do tamanho mínimo sem eles se desfaz. No piloto, isso desfaz o tópico dos ensaios sem resumo e deixa 57 tópicos.
4. **A estabilidade publicada é o ARI do núcleo** entre as três sementes.
5. **Macrotemas por aglomeração de Ward** dos centros dos tópicos, até 7 por padrão; com poucos tópicos, um macrotema para cada três tópicos (a *Opinião Pública* sozinha ficava com 7 macrotemas, dois deles de um tópico só). No piloto, a ligação média deixava três macrotemas de um tópico só; a de Ward dá grupos de 3 a 13 tópicos (111 a 743 documentos no núcleo): instituições, eleições e comportamento político; políticas públicas, economia política e desigualdades; política externa e regionalismo; relações internacionais, segurança e direitos humanos; sociedade, cultura e pensamento; teoria política; segurança pública e violência.
6. **Os macrotemas persistem entre execuções.** A aglomeração roda na primeira execução, quando menos da metade dos tópicos casa com os da anterior, ou com `mapa topicos --refazer-macrotemas`. Nas outras, cada tópico casado fica no macrotema que tinha, e cada tópico novo entra no macrotema do tópico casado mais parecido. Refazer a aglomeração a cada execução mudava de macrotema, e portanto de cor, metade dos tópicos casados: 26 de 51 com outra semente, 27 de 51 sem os artigos de 2010.
7. **Identidade estável por sobreposição de membros** (Jaccard ≥ 0,3 entre os núcleos, só com documentos presentes nas duas execuções, casamento húngaro), e não por centroides. No piloto, trocar a semente principal mantém o número e a cor de 50 dos 57 tópicos, e tirar os 241 artigos de 2010 também mantém 50 dos 57. Ids aposentados nunca voltam.

## Consequências

- A pergunta do ADR 0004 está respondida: o inglês continua como idioma de análise padrão.
- Os pontos fracos são assunto para quem usar o piloto: um `min_cluster_size` menor divide os tópicos amplos (e cria outros pequenos), e os rótulos podem ser corrigidos no `rotulos.yaml`.
- 11% do corpus do piloto fica sem tópico. No mapa, esses documentos aparecem em cinza; na validação (M5), formam um estrato próprio.
- Com os macrotemas persistentes, coletas que mudam muito o corpus podem deixar os macrotemas menos coerentes com o tempo. `--refazer-macrotemas` refaz a aglomeração, ao custo de mudar as cores.
- Corpora muito diferentes do piloto (bem menores, ou de outra área) podem pedir outros valores. Os menores também são menos estáveis: a *Opinião Pública* sozinha (396 artigos, o recorte do tutorial) dá 15 tópicos com ARI 0,77. `scripts/calibrar_topicos.py` refaz a grade em qualquer projeto.

## Como reproduzir

    uv run python scripts/calibrar_topicos.py projetos/cp-scielo --saida calibracao.json
