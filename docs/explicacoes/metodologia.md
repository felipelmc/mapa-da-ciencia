# Metodologia em uma página

Um resumo do método, na ordem em que as etapas rodam, com os parâmetros padrão e os números do piloto (ciência política no SciELO Brasil, 10 revistas, 2010–2025). Serve de rascunho para a seção de métodos de um artigo que use o `mapa-da-ciencia`; cada passo aponta para a explicação completa. Os valores exatos de uma rodada (modelos com o *digest*, sementes, durações) ficam no manifesto do projeto e na página **Metodologia** do site publicado.

## 1. Corpus

Os artigos são listados na ArticleMeta do SciELO, revista a revista, e filtrados pelo ano embutido no identificador (PID) e pelo tipo de documento (artigos de pesquisa e de revisão). Cada registro é casado com o OpenAlex pelo DOI, pelo PID ou pelo título e ano, com conferência do ano e da semelhança dos títulos. Os e-mails dos autores são descartados na coleta. No piloto: 4.275 artigos, 99,3% com resumo, 99,4% casados com o OpenAlex. Veja [Fontes de dados](fontes.md).

## 2. Tópicos

- **Texto:** título e resumo em inglês (97% do piloto); na falta dele, no idioma disponível (2,2%) ou só o título (0,4%), com marca.
- **Embeddings:** `qwen3-embedding:0.6b`, rodando localmente no Ollama, com vetores normalizados.
- **Vizinhança:** os 15 vizinhos mais próximos de cada documento (incluindo o próprio documento, como no UMAP), por similaridade de cosseno, calculados de forma exata.
- **Redução:** UMAP para 5 dimensões (agrupamento, `min_dist` 0) e para 2 (o mapa), com semente fixa.
- **Agrupamento:** HDBSCAN com seleção `leaf`, `min_cluster_size` de 1 a cada 200 documentos (mínimo 10) e `min_samples` 5. Os documentos de ruído vão para o tópico com pelo menos 3 dos seus 14 vizinhos mais próximos no núcleo; os outros ficam sem tópico.
- **Descrição:** palavras-chave por c-TF-IDF sobre o núcleo de cada tópico; rótulo e descrição em português escritos pelo `qwen3.5:9b` a partir de 15 termos e 5 títulos representativos; macrotemas por aglomeração de Ward dos centros dos tópicos (até 7).
- **Estabilidade:** índice de Rand ajustado entre três sementes, sobre os documentos que estão no núcleo nas duas execuções.

No piloto: 57 tópicos em 7 macrotemas, ARI 0,89; 66,5% dos documentos no núcleo, 22,5% reatribuídos e 11% sem tópico. Veja [Como os tópicos são construídos](topicos.md) e o [ADR 0007](../decisoes/0007-parametros-dos-topicos.md).

## 3. Tópicos no tempo

A tendência de cada tópico é a inclinação de uma regressão logística quase-binomial da sua participação anual no corpus, com intervalo de 95% (erro padrão corrigido pela dispersão). Um tópico está "em alta" ou "em queda" quando o intervalo não inclui zero, e a variação é dada em pontos percentuais por ano. No piloto, 13 dos 57 tópicos. Veja [Em alta e em queda](topicos.md#12-em-alta-e-em-queda) e o [ADR 0009](../decisoes/0009-tendencia-dos-topicos.md).

## 4. Geografia

Cada afiliação de autor (a normalizada da ArticleMeta, `v240`, ou o texto livre, `v70`) é ligada a uma instituição do OpenAlex/ROR, dos candidatos mais próximos (as instituições que o OpenAlex deu ao mesmo autor) aos mais distantes, com vetos contra nomes parecidos e países divergentes, e sobe até a instituição de ensino "mãe". A produção é contada de forma fracionária: cada artigo vale 1, dividido entre os autores e, para cada autor, entre as suas afiliações. No piloto: 93,9% dos vínculos ligados a uma de 639 instituições, com precisão de 99,8% numa amostra lida à mão. Veja [Geografia da produção](geografia.md) e o [ADR 0008](../decisoes/0008-geografia-casamento-das-afiliacoes.md).

## 5. Classificação

Um modelo local (`qwen3.5:9b`, temperatura 0, contexto de 8.192 *tokens*) lê o título e o resumo em português de cada artigo e responde às perguntas do codebook num JSON com esquema fixo, citando antes de cada valor o trecho do resumo que o justifica (até 200 caracteres). O `mapa` confere se o trecho está no resumo (literal, aproximado ou ausente) e, quando uma evidência obrigatória não está, pede uma nova resposta uma vez. No piloto: 100% de JSON válido na primeira tentativa, 94,8% das evidências literais, 10,8 s por resumo num notebook. Veja [Classificação ancorada em evidência](classificacao.md) e o [ADR 0011](../decisoes/0011-classificacao-ancorada-em-evidencia.md).

## 6. Validação

Uma amostra estratificada por tópico (200 artigos no piloto, semente 7) é codificada às cegas, sem ver as respostas do modelo. Para cada variável e cada par de participantes: concordância, kappa de Cohen com intervalo de 95% por *bootstrap* (1.000 reamostras), PABAK, alfa de Krippendorff, matriz de confusão e precisão, revocação e F1 por categoria; modelos são comparados entre si pelo teste de McNemar. No piloto, a amostra foi codificada por um codificador de referência (Claude, às cegas), e não por uma pessoa: o kappa vai de 0,37 (técnica de pesquisa) a 0,93 (Brasil como caso). Veja [Desenho da validação](validacao.md) e o [ADR 0012](../decisoes/0012-validacao-e-codificador-de-referencia.md).

## Limites

Os resultados descrevem os títulos e resumos de um conjunto de revistas, com modelos pequenos e uma validação de referência. O que isso deixa de fora está em [Limitações e vieses](limitacoes.md).

## Como citar

Cite o software pelo DOI do Zenodo, [10.5281/zenodo.22998585](https://doi.org/10.5281/zenodo.22998585), que reúne todas as versões; a página do Zenodo tem também o DOI de cada versão, para citar exatamente a usada (o arquivo [`CITATION.cff`](https://github.com/felipelmc/mapa-da-ciencia/blob/main/CITATION.cff) do repositório tem os dados; o GitHub mostra a citação em "Cite this repository") e informe, do manifesto do projeto, os modelos com o *digest*, a versão do codebook e a data da coleta.

Em BibTeX:

```bibtex
@software{lamarca_mapa_da_ciencia,
  author    = {Lamarca, Felipe},
  title     = {mapa-da-ciencia: observatório da literatura científica com modelos de linguagem locais},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.22998585},
  url       = {https://doi.org/10.5281/zenodo.22998585}
}
```
