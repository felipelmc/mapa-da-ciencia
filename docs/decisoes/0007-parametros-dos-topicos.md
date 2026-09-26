# 0007. Parâmetros dos tópicos

- **Status:** proposta (em andamento no M3: falta a leitura dos tópicos, depois dos rótulos)
- **Data:** 2026-09-26
- **Marco:** M3

## Contexto

O spike M0a (ADR 0004) escolheu o modelo de embeddings e o idioma de análise, mas deixou os parâmetros do agrupamento em aberto: com os valores do spike, 27% dos documentos ficaram como ruído, sem tópico. O M3 precisa de padrões para a seção `topicos:` do `mapa.yaml` que deem, num corpus como o piloto (4.275 artigos de ciência política):

- um número de tópicos legível num mapa e útil para estratificar a validação (M5);
- estabilidade: sementes diferentes não podem produzir tópicos muito diferentes;
- nenhum tópico gigante, que esconda assuntos distintos sob um rótulo só.

## Evidência

`scripts/calibrar_topicos.py` no piloto (embeddings `qwen3-embedding:0.6b` em inglês, com reserva marcada), em 2026-09-26. Grade: vizinhos do UMAP (15, 30) × `min_cluster_size` (10, 15, 21, 30, 40) × `min_samples` (1, 3, 5, 10) × seleção (`eom`, `leaf`), cada combinação com 3 sementes (42, 7, 2024).

- **Ruído:** fração de documentos que o HDBSCAN deixa sem tópico, na semente principal.
- **Maior:** o maior tópico, como fração do corpus.
- **ARI:** índice de Rand ajustado médio entre os pares de sementes, sobre os documentos que estão no núcleo nas duas execuções.

Linhas selecionadas (15 vizinhos, salvo indicação; a grade completa sai do script):

| `min_cluster_size` | `min_samples` | Seleção | Tópicos (3 sementes) | Ruído | Maior | ARI |
|---|---|---|---|---|---|---|
| 10 | 5 | eom | 115 (115/118/119) | 29,1% | 3,2% | 0,901 |
| 15 | 5 | eom | 78 (78/75/75) | 32,1% | 3,3% | 0,833 |
| **21 (automático)** | **5** | **eom** | **50 (50/50/49)** | **32,5%** | **5,7%** | **0,897** |
| 21 | 10 | eom | 41 (41/41/38) | 30,1% | 5,4% | 0,883 |
| 30 | 5 | leaf | 40 (40/40/41) | 35,2% | 4,4% | 0,891 |
| 40 | 5 | leaf | 33 (33/32/33) | 28,2% | 5,7% | 0,920 |
| 40 | 1 | eom | 23 (23/31/28) | 17,0% | 23,0% | 0,657 |
| 21 (30 vizinhos) | 5 | eom | 38 (38/38/39) | 26,4% | 14,2% | 0,840 |

O que a grade mostra:

- **O ruído é do corpus, não dos parâmetros.** Em todas as combinações estáveis ele fica entre 27% e 35%. Onde cai (`eom` com tópicos de 40 ou mais), aparece um tópico com um quinto do corpus e a estabilidade desaba (ARI 0,66).
- **30 vizinhos pioram:** tópicos maiores (até 14% do corpus) e sementes menos concordantes, sem reduzir o ruído de forma útil.
- **O padrão do spike é estável.** Com o tamanho mínimo automático (1 a cada 200 documentos), 5 amostras e `eom`, as três sementes dão 50, 50 e 49 tópicos, com ARI 0,90 e nenhum tópico acima de 6% do corpus.

**Reatribuição do ruído.** Um documento de ruído vai para o tópico com mais vizinhos seus no núcleo, se forem pelo menos 3 dos 15 mais próximos (similaridade de cosseno entre os embeddings, não no UMAP). Para calibrar o limite: um documento típico do núcleo tem 8 dos 15 vizinhos no próprio tópico, e o 10º percentil tem 4. Com o limite em 3, no piloto:

| | Documentos | % do corpus |
|---|---|---|
| Núcleo (HDBSCAN) | 2.886 | 67,5% |
| Ruído reatribuído por vizinhança | 918 | 21,5% |
| Sem tópico | 471 | 11,0% |

- **O ruído não se concentra** em anos nem em revistas: fica entre 26% e 38% por revista (mais na *Contexto Internacional*) e entre 28% e 35% por ano, com exceção de 2010 (44%) e 2012 (39%).
- **As séries anuais dos tópicos quase não mudam** com a reatribuição: a correlação entre a proporção anual de cada tópico só com o núcleo e com os reatribuídos tem mediana 0,93 (mínima 0,68), e a maior diferença numa proporção anual é de 2,7 pontos percentuais (mediana 1,1).
- **A estabilidade cai onde deveria:** o ARI entre sementes é 0,90 no núcleo e 0,78 contando os reatribuídos, que são documentos de fronteira. Por isso a estabilidade publicada é a do núcleo, e a atribuição por vizinhança fica marcada.
- Documentos só com título ficam sem tópico com mais frequência (10 de 18) que os com resumo em reserva (16 de 96) ou em inglês (445 de 4.161).

Custo: kNN exato em 0,2 s; UMAP de 5 dimensões em 3,5 a 5 s por semente (9 s na primeira, com a compilação do numba); HDBSCAN em menos de 1 s. A grade inteira (80 combinações × 3 sementes) levou 45 s, com pico de 0,77 GB de memória.

## Decisão

1. **Padrões da seção `topicos:`:** 15 vizinhos, `min_dist` 0 no UMAP de agrupamento, `min_cluster_size` automático (1 a cada 200 documentos, mínimo 10), `min_samples` 5, seleção `eom`, sementes 42, 7 e 2024. São os valores do spike, agora confirmados pela grade.
2. **O ruído é tratado depois do agrupamento, e não escondido por parâmetros.** Como um terço do corpus fica de fora com qualquer configuração estável, a reatribuição por vizinhança é parte do método, com `topicos.votos_minimos: 3`. Os documentos reatribuídos ficam marcados (`atribuicao: vizinho`), e o núcleo continua sendo a base das palavras-chave, dos representativos, dos contornos e da estabilidade.
3. **A estabilidade publicada é o ARI do núcleo** entre as três sementes.

## Consequências

- 11% do corpus do piloto fica sem tópico. No mapa, esses documentos aparecem em cinza; na validação (M5), formam um estrato próprio.
- A leitura da lista completa de tópicos (a pergunta aberta do ADR 0004: os tópicos em inglês são tão legíveis quanto seriam em português?) também entra aqui, depois dos rótulos.
- Corpora muito diferentes do piloto (bem menores, ou de outra área) podem pedir outros valores. `scripts/calibrar_topicos.py` refaz a grade em qualquer projeto.

## Como reproduzir

    uv run python scripts/calibrar_topicos.py projetos/cp-scielo --saida calibracao.json
