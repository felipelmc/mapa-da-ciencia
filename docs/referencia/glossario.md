# Glossário

**ArticleMeta**
: API pública do SciELO com os metadados de cada artigo: títulos, resumos, palavras-chave, autores e afiliações. É a fonte principal do corpus. Veja [Fontes de dados](../explicacoes/fontes.md).

**Codebook**
: Conjunto de variáveis, categorias e definições que o modelo usa para classificar cada resumo. Veja [Escrever um codebook](../guias/codebook.md).

**Contagem fracionária**
: Forma de atribuir um artigo a instituições: cada artigo vale 1, dividido entre os autores e, para cada autor, entre as suas afiliações. Evita que artigos com muitos autores pesem mais.

**Contrato de dados**
: Os arquivos JSON que o pipeline gera e a interface lê. Veja a [referência](contrato.md).

**Embedding**
: Representação de um texto como um vetor de números, em que textos de assunto parecido ficam próximos. É a base dos tópicos e do mapa de documentos.

**Evidência**
: Trecho do resumo que o modelo copia para justificar cada resposta do codebook. O `mapa` confere se ele é literal, aproximado ou ausente.

**HDBSCAN**
: Algoritmo de agrupamento que encontra grupos de densidade variável e deixa de fora os pontos que não se encaixam em nenhum grupo (*outliers*).

**Kappa de Cohen**
: Medida de concordância entre dois codificadores que desconta a concordância esperada ao acaso. Vai de −1 a 1. Acima de 0,6 costuma ser considerado substancial, e acima de 0,8, quase perfeito.

**Macrotema**
: Agrupamento de tópicos próximos, usado para organizar as cores e a navegação.

**Manifesto de execução**
: Registro gravado a cada vez que uma etapa roda: versões, modelos, parâmetros, contagens e duração. Veja [Reprodutibilidade](../explicacoes/reprodutibilidade.md).

**Ollama**
: Programa que baixa e roda modelos de linguagem abertos no seu computador. [ollama.com](https://ollama.com)

**OpenAlex**
: Catálogo aberto (CC0) de publicações científicas, usado para citações, licenças e busca por termo.

**PABAK**
: Kappa ajustado para prevalência e viés. Complementa o kappa quando uma categoria é muito mais frequente que as outras, caso em que o kappa pode ficar baixo mesmo com alta concordância.

**Perfil de modelos**
: Conjunto de modelos recomendado para uma faixa de memória (`leve`, `padrao`, `forte`). Veja [Instalar e escolher os modelos](../guias/instalacao.md).

**PID**
: Identificador de um artigo no SciELO, como `S0104-62762024000100200`. Os caracteres 11 a 14 são o ano.

**Tópico**
: Grupo de artigos de assunto próximo, encontrado automaticamente. Recebe um rótulo e uma descrição escritos por um modelo de linguagem a partir de palavras-chave e títulos representativos.

**UMAP**
: Técnica que reduz os embeddings a poucas dimensões, preservando vizinhanças. Com 5 dimensões, alimenta o agrupamento; com 2, desenha o mapa.
