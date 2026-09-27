# Glossário

**Apelido**
: Texto de afiliação ligado à mão a uma instituição, no `instituicoes.yaml` do projeto (ou na tabela do pacote). Tem prioridade sobre o casamento automático. Veja [Gerar a geografia](../guias/geografia.md#o-arquivo-instituicoesyaml).

**ARI (índice de Rand ajustado)**
: Mede quanto dois agrupamentos dos mesmos documentos concordam: 0 é concordância de acaso, 1 são os mesmos grupos. O `mapa` compara os tópicos de três sementes diferentes; no piloto, o ARI é 0,89. Veja [Estabilidade](../explicacoes/topicos.md#7-estabilidade).

**ArticleMeta**
: API pública do SciELO com os metadados de cada artigo: títulos, resumos, palavras-chave, autores e afiliações. É a fonte principal do corpus. Veja [Fontes de dados](../explicacoes/fontes.md).

**Casamento**
: Encontrar, no OpenAlex, o mesmo artigo que veio da ArticleMeta. O `mapa` tenta, em ordem, o DOI, o PID dentro dos endereços do OpenAlex, o DOI derivado do PID e o título mais o ano, e confere ano e título antes de aceitar (a ArticleMeta às vezes traz DOIs trocados). O passo usado fica registrado em cada documento.

**Codebook**
: Conjunto de variáveis, categorias e definições que o modelo usa para classificar cada resumo. Veja [Escrever um codebook](../guias/codebook.md).

**Codificador de referência**
: Quem codifica a amostra de validação sem ser uma pessoa: no piloto, um modelo maior (o Claude), lendo às cegas. O relatório e o painel nunca o chamam de humano. Veja [Desenho da validação](../explicacoes/validacao.md).

**Contagem fracionária**
: Forma de atribuir um artigo a instituições: cada artigo vale 1, dividido entre os autores e, para cada autor, entre as suas afiliações. Evita que artigos com muitos autores pesem mais. Veja [Geografia da produção](../explicacoes/geografia.md#quanto-cada-documento-conta).

**Contrato de dados**
: Os arquivos JSON que o pipeline gera e a interface lê. Veja a [referência](contrato.md).

**Documento**
: A unidade do corpus depois da coleta: títulos e resumos em cada idioma, autores, afiliações (sem e-mails), revista, ano, licença e identificadores (PID, DOI, OpenAlex). Todas as fontes viram documentos no mesmo formato.

**Em alta, em queda**
: Tópico cuja participação no corpus cresce ou cai ao longo do período de forma distinguível do acaso: o intervalo de 95% da inclinação de uma regressão logística quase-binomial não inclui zero. Veja [Ler os tópicos no tempo](../guias/ler-os-topicos.md#em-alta-e-em-queda).

**Embedding**
: Representação de um texto como um vetor de números, em que textos de assunto parecido ficam próximos. É a base dos tópicos e do mapa de documentos.

**Evidência**
: Trecho do resumo que o modelo copia para justificar cada resposta do codebook. O `mapa` confere se ele é literal, aproximado ou ausente.

**HDBSCAN**
: Algoritmo de agrupamento que encontra grupos de densidade variável e deixa de fora os pontos que não se encaixam em nenhum grupo (*outliers*).

**Instituição não identificada**
: Afiliação informada pela fonte que não casou com nenhuma instituição conhecida. Conta no país e na UF que a fonte informou, mas não no ranking das instituições. `mapa geografia --revisar` lista as mais frequentes.

**Kappa de Cohen**
: Medida de concordância entre dois codificadores que desconta a concordância esperada ao acaso. Vai de −1 a 1. Acima de 0,6 costuma ser considerado substancial, e acima de 0,8, quase perfeito.

**Licença mais restritiva**
: Regra do projeto para a licença de cada artigo: entre a licença informada pelo OpenAlex e a da revista, vale a mais restritiva (por exemplo, CC BY-NC ganha de CC BY). Veja [Privacidade e licenças](../explicacoes/privacidade-e-licencas.md).

**Linhagem**
: As instituições acima de uma instituição no OpenAlex (a universidade de um hospital universitário, a fundação de uma escola). Na geografia, a instituição sobe na linhagem até a organização de ensino "mãe".

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

**Recorte**
: Os documentos que as vistas de análise mostram, definidos pela barra no alto do painel: período, revistas, tópicos, busca, laço, UFs, países e instituições. Vai junto de uma vista para outra e fica no endereço da página.

**Release**
: Uma versão publicada do `mapa-da-ciencia` no GitHub, com as notas do que mudou e o *wheel* para instalar. Veja as [releases](https://github.com/felipelmc/mapa-da-ciencia/releases).

**Sem afiliação**
: A parte do peso de um documento que cabe a autores sem afiliação informada. Não é redistribuída entre os coautores nem entra em nenhum lugar.

**Tópico**
: Grupo de artigos de assunto próximo, encontrado automaticamente. Recebe um rótulo e uma descrição escritos por um modelo de linguagem a partir de palavras-chave e títulos representativos.

**Trilho**
: A barra à esquerda do painel, com as vistas (Início, Mapa, Tópicos, Classificação, Geografia, Validação, Projeto). O recorte escolhido numa vista vai junto quando se troca de vista pelo trilho.

**UMAP**
: Técnica que reduz os embeddings a poucas dimensões, preservando vizinhanças. Com 5 dimensões, alimenta o agrupamento; com 2, desenha o mapa.

**Vínculo**
: Um autor ligado a uma afiliação, e a afiliação ligada (ou não) a uma instituição, com UF e país. É a unidade da geografia, antes da contagem fracionária.

**Wheel**
: O arquivo de instalação de um pacote Python (`.whl`). O de cada *release* do `mapa-da-ciencia` já traz a interface do painel compilada. Veja [Instalar](../guias/instalacao.md#sem-compilar-a-interface-o-wheel-da-release).
