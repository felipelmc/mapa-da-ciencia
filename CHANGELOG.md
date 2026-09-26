# Registro de mudanças

Todas as mudanças relevantes do projeto ficam registradas aqui. O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/), e as versões seguem o [versionamento semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

### Adicionado

- **Marco M4 (tópicos no tempo e geografia)**:
  - tendência de cada tópico (em alta, em queda, estável) por regressão logística quase-binomial da participação anual, com `scripts/tendencias.py` para comparar os modelos (ADR 0009);
  - a coleta guarda, de cada documento, os autores segundo o OpenAlex, com as instituições (ROR, país, tipo, linhagem) e os textos de afiliação, sem e-mails; um corpus coletado antes da 0.4.0 é reconhecido (`armazenamento.tem_coluna`);
  - contrato de dados 1.2 (só acréscimos): tendência de cada tópico e macrotema como gabarito, com o método; série dos macrotemas; documentos sem tópico por ano; geografia completa (instituição não identificada, autores sem afiliação, as 27 UFs, agregados fracionários e inteiros por UF, país e instituição); casos de referência em `contrato/casos/tendencia.json`; exemplo sintético com a contagem fracionária do glossário e casos de borda;

### Corrigido

- Revistas sem acrônimo (vindas de importações) têm a mesma chave, o ISSN, em `revistas.json`, nos documentos, nas séries por revista e nos agregados; antes, algumas contagens usavam "?".

### Mudado

- `mapa status` deixa de listar a "exportação" como etapa pendente: a exportação para o painel acontece no fim de cada etapa.

## [0.3.0] - 2026-09-26

Os tópicos e o mapa: o `mapa` descobre os assuntos do corpus com modelos locais, dá nome a eles em português e os mostra num mapa navegável. No piloto (4.275 artigos de dez revistas de ciência política), são 57 tópicos em 7 macrotemas, com estabilidade de 0,89 entre sementes; a etapa leva uns 4 minutos nos embeddings e 3 nos rótulos na primeira vez, e segundos depois.

### Adicionado

- **Marco M3 (tópicos e mapa)**:
  - `mapa topicos`: embeddings locais (`qwen3-embedding:0.6b` no Ollama) sobre título e resumo no mesmo idioma, com os artigos sem resumo em inglês marcados como reserva ou só título; cache incremental em `dados/embeddings/`;
  - kNN exato, UMAP e HDBSCAN com cache das projeções; o ruído é reatribuído pelo voto dos vizinhos do núcleo, e a estabilidade é medida pelo ARI entre três sementes. No piloto: 57 tópicos em 7 macrotemas, ARI 0,89, 89% dos artigos com tópico;
  - palavras-chave por c-TF-IDF no idioma de exibição, documentos representativos e macrotemas por aglomeração de Ward;
  - números e cores dos tópicos estáveis entre execuções, por sobreposição dos núcleos, com macrotemas que persistem (`--refazer-macrotemas` refaz a aglomeração); números aposentados nunca voltam;
  - rótulos e descrições em português escritos pelo modelo de linguagem local, com conferência de acentos, cache no `estado.sqlite` e correção manual por `rotulos.yaml`; `--sem-rotulos` usa as palavras-chave;
  - guarda de memória antes de carregar modelos, que para a etapa com uma explicação em vez de travar a máquina;
  - contrato de dados 1.1 (só acréscimos) e exportação única de `saida/dados/`, com os documentos, os tópicos, os fragmentos de detalhe e os agregados;
  - a vista **Mapa** do painel: nuvem de documentos (regl-scatterplot), contornos e rótulos dos tópicos, cartão do documento com os cinco vizinhos, busca, laço, linha do tempo com play e permalink de tudo o que está na tela;
  - `mapa status` com a linha dos tópicos e o aviso de tópicos desatualizados; `api.embeddings()` e `api.topicos()`, com a view `atribuicoes`;
  - documentação: tutorial "Seu primeiro mapa, parte 2", explicação "Como os tópicos são construídos", guias "Gerar os tópicos" e "Ler o mapa", ADR 0007 e adendo ao ADR 0004.

### Corrigido

- A coleta descarta resumos repetidos em documentos diferentes: o OpenAlex dava a dez artigos da *Novos Estudos CEBRAP* o mesmo texto de apresentação da biblioteca Americanae como resumo.

### Mudado

- A tabela de marcos: os rótulos pelo modelo de linguagem entram no M3, e o M4 fica com os tópicos no tempo e a geografia.
- O Python aceito vai de 3.11 a 3.14, porque as dependências numéricas (numba) ainda não têm versão para o 3.15.

## [0.2.0] - 2026-09-26

A coleta: o `mapa` monta o corpus a partir do SciELO e do OpenAlex. No piloto (10 revistas de ciência política, 2010–2025), são 4.275 artigos, 99,6% com resumo e 99,4% casados com o OpenAlex, em menos de um minuto e cerca de 32 créditos do OpenAlex.

### Adicionado

- **Marco M2 (coleta)**:
  - `mapa coletar`: artigos das revistas do recorte pela ArticleMeta, com o ano tirado do PID e o filtro de tipos de documento; opções `--revista`, `--anos`, `--limite`, `--atualizar`, `--offline`, `--sem-openalex` e `--consulta`;
  - cache das respostas em `brutos/`, gravado de forma atômica: a segunda execução faz 0 requisições, e uma coleta interrompida continua de onde parou;
  - enriquecimento pelo OpenAlex (citações, licença por artigo, resumo de reserva), com a cascata de casamento conferida (DOI → PID na URL → DOI derivado → título e ano);
  - deduplicação entre fontes e dentro da ArticleMeta, com suspeitas marcadas em vez de apagadas;
  - `mapa importar`: exportações do search.scielo.org (RIS, CSV, BibTeX) e listas de DOIs ou PIDs, de qualquer coleção do SciELO;
  - busca por termo no título e no resumo, pelo OpenAlex (`--consulta` ou `fontes.openalex.consulta`);
  - `mapa revistas`: as 427 revistas correntes do SciELO Brasil, com busca por nome, ISSN e área; `mapa novo --revista --anos`;
  - corpus em `dados/documentos.parquet` via DuckDB (ADR 0006), com as views `documentos`, `textos`, `autores` e `afiliacoes`;
  - `mapa status` com a cobertura do corpus; o painel passa a mostrar os números do corpus depois da coleta;
  - fachada `mapa_da_ciencia.api` para notebooks, com consultas em SQL;
  - documentação: tutorial "Seu primeiro mapa, parte 1", guias "Montar um recorte" e "Importar uma busca do SciELO", explicação das fontes, ADR 0006 e adendo ao ADR 0003 com os números do piloto.

### Segurança

- Nenhum e-mail sai da ArticleMeta: extração por lista branca de campos e varredura final, com teste sobre o Parquet e `saida/`.
- A chave do OpenAlex nunca é gravada em `brutos/`.

## [0.1.0] - 2026-09-26

Primeira versão marcada: o esqueleto do projeto. Ainda não coleta nem analisa artigos (isso começa no M2).

### Adicionado

- **Marco M0 (spikes técnicos)**, com os resultados registrados em `docs/decisoes/`:
  - fontes, casamento ArticleMeta↔OpenAlex e licenças ([ADR 0003](docs/decisoes/0003-fontes-casamento-e-licencas.md));
  - modelo de embeddings e idioma de análise ([ADR 0004](docs/decisoes/0004-embeddings-e-idioma-de-analise.md));
  - frontend com router por hash e regl-scatterplot ([ADR 0002](docs/decisoes/0002-frontend-router-hash-e-regl-scatterplot.md));
  - certificados do sistema com `truststore` ([ADR 0001](docs/decisoes/0001-certificados-do-sistema-com-truststore.md));
  - modelo local de classificação e parâmetros ([ADR 0005](docs/decisoes/0005-modelo-de-classificacao.md)).
- **Marco M1 (esqueleto)**:
  - pacote Python e CLI `mapa` com os comandos `novo`, `status`, `diagnostico` e `painel`;
  - configuração do projeto (`mapa.yaml`) e do codebook (`codebook.yaml`), com erros explicados em português;
  - perfis de modelos locais por memória e checagem de memória antes de carregar modelos;
  - manifesto de execução para reprodutibilidade;
  - contrato de dados v1 com JSON Schemas e um exemplo sintético determinístico;
  - servidor local do painel (FastAPI) e `mapa painel --exemplo`;
  - site de documentação (Material for MkDocs), com referência gerada a partir do código.

[Não lançado]: https://github.com/felipelmc/mapa-da-ciencia/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/felipelmc/mapa-da-ciencia/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/felipelmc/mapa-da-ciencia/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/felipelmc/mapa-da-ciencia/releases/tag/v0.1.0
