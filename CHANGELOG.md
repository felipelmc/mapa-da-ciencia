# Registro de mudanças

Todas as mudanças relevantes do projeto ficam registradas aqui. O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/), e as versões seguem o [versionamento semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

### Adicionado

- **Marco M5 (classificação por codebook e validação)**:
  - o codebook vira o JSON Schema da resposta do modelo, com a evidência (até 200 caracteres) antes do valor em cada variável, e as respostas são validadas contra ele; a mensagem de sistema é fixa (o Ollama reaproveita o prefixo) e traz as regras da evidência curta;
  - conferência da evidência: `literal` (a menos de maiúsculas, espaços, aspas e travessões), `aproximada` (90% dos caracteres casando em blocos), `ausente` ou `dispensada` (vazia numa resposta "sem informação"), com os *offsets* do trecho no resumo exibido;
  - executor da classificação retomável: cada resposta válida vai para o cache do `estado.sqlite` (chave com o texto, a assinatura do que o modelo lê, o modelo com o digest, a versão do prompt e os parâmetros; mudar só a versão ou os rótulos das categorias reaproveita as respostas), uma nova tentativa quando a resposta foge do codebook ou a evidência não está no texto, guarda de memória entre documentos, concorrência configurável e o modelo descarregado no fim;
  - `mapa classificar [--estimar] [--limite N] [--modelo X]` e `api.classificar()`: a etapa grava `dados/classificacao/` (um resultado por modelo e codebook, para comparar modelos), registra o manifesto com o hash do codebook e aparece no `mapa status`, com aviso quando está incompleta ou é de outro codebook; a view `classificacoes` em `conectar()`; o resultado é regravado a cada 50 documentos novos e numa interrupção, para a rodada longa aparecer enquanto corre; ADR 0011 (proposta);
  - amostra de validação (`mapa validar amostra [--n N] [--refazer]`, `api.amostra_de_validacao()`): sorteada uma vez entre os documentos com resumo, estratificada por tópico (ou ano, ou revista) com alocação proporcional e ao menos um por estrato, guardada no `estado.sqlite` e exportada em `validacao/amostra.jsonl` só com id, título, resumo e idioma; a fila da classificação começa pela amostra, e `mapa classificar --somente-amostra` classifica só ela;
  - codificações (`mapa validar importar ARQUIVO --codificador NOME [--tipo humano|referencia]`, `api.importar_codificacoes()`, `api.codificacoes()`): JSONL validado contra o codebook, com evidência, incerteza e nota por variável; guias "Classificar os resumos" e "Codificar a amostra";
  - na saída de `mapa validar amostra`, os estratos com o rótulo do tópico; na de `mapa classificar`, as categorias com o rótulo do codebook;
  - métricas de concordância (`mapa validar metricas`, `api.validacao()`), por variável e por par de participantes (codificador × modelo, codificador × codificador, modelo × modelo): concordância, kappa de Cohen (igual ao do scikit-learn) com IC 95% por *bootstrap*, PABAK, alfa de Krippendorff nominal (conferido com o exemplo publicado), matriz de confusão e precisão, revocação e F1 por classe; McNemar exato entre modelos contra a mesma referência; divergências com o modelo principal; múltipla escolha medida por categoria; guia "Ler kappa e PABAK";
  - relatório da validação (`mapa validar relatorio`, `api.relatorio_de_validacao()`) em `validacao/`: Markdown com participantes, concordância, P/R/F1 e matrizes por classe, McNemar, evidência literal e as divergências com a evidência do modelo; tabelas LaTeX (`booktabs`, vírgula decimal); JSON. O `.gitignore` de um projeto novo deixa `validacao/amostra.jsonl` (com os resumos) fora do git; ADR 0012 (proposta);
  - tutorial "Seu primeiro mapa, parte 4: classificação e validação" (com os comandos rodados no CI) e ADRs 0011 e 0012 aceitos, com a evidência do piloto: 100% de JSON válido na primeira tentativa, 94,8% de evidência literal, 10,8 s por resumo, retomada depois de `kill -9` sem refazer nada, e o kappa `claude-opus` × `qwen3.5:9b` por variável (de 0,37 na técnica a 0,93 em "Brasil como caso");
  - contrato de dados 1.3 (só acréscimos): `codebook.json` sempre; `classificacoes.json` com cobertura, classificação parcial, JSON válido e evidência por variável; colunas `cls` em `documentos.json` (múltipla escolha como combinações) e as evidências nos detalhes, com o campo onde o trecho está e o status `dispensada`; `validacao.json` com os participantes e o tipo de cada um, P/R/F1 por classe, McNemar entre modelos e as divergências só de codificadores de referência (as de pessoas ficam fora do contrato); `hash_codebook`, classificados e validados no manifesto; a importação de codificações e a rodada da classificação atualizam o painel;
  - a vista **Classificação** do painel, no filtro cruzado: uma variável do codebook por vez, com o selo de kappa da validação (hachura abaixo de 0,6; borda tracejada contra um codificador de referência), barras 100% por ano e o cruzamento com macrotemas, tópicos ou revistas; uma célula lista os documentos com a evidência marcada no resumo; a variável e o cruzamento vão na URL (`variavel=`, `cruzar=`); guia "Ler a classificação";
  - rótulos com acento nas categorias do codebook de exemplo (o `rotulo`, só de exibição);
  - a vista **Codificar** (Validação › Codificar a amostra, só no painel local): uma ficha por vez, cega, com o título, o resumo e o codebook; tudo pelo teclado (`1`–`9`, `Tab`, `Enter`, `←`/`→`, `S` incerto, `N` nota, `E` evidência do trecho selecionado, `D` definições, `?` ajuda); gravação automática com fila de pendências no navegador, retomada na primeira ficha incompleta; e2e com 20 fichas pelo teclado que sobrevivem a um reload, contra uma API falsa que espelha a do Python;
  - o cartão do documento no Mapa marca no resumo as evidências da classificação e lista as respostas do modelo; passar o mouse (ou clicar) numa resposta acende só o trecho dela;
  - a vista **Validação › Concordância**: os participantes com o tipo (aviso quando há codificador de referência), o par escolhido com concordância, kappa (barra com hachura abaixo de 0,6) e IC 95%, PABAK e alfa por variável; a variável escolhida com a matriz de confusão, P/R/F1 por categoria e as divergências com a evidência do modelo; McNemar entre modelos e evidência literal. No painel local, as métricas vêm da API, calculadas na hora;
  - API local da codificação no painel: `GET /api/validacao/fila` (a amostra embaralhada por codificador, cega, com o codebook e as respostas já dadas), `PUT /api/validacao/codificacoes/{doc}` (gravação parcial ou completa, só a partir desta máquina: `Host` e `Origin` locais) e `GET /api/validacao/metricas` (concordância na hora, com as divergências de todos os codificadores);

## [0.4.0] - 2026-09-26

Os tópicos no tempo e a geografia: o painel mostra como os assuntos do corpus mudam ano a ano, quais estão em alta e em queda, e de onde vêm os autores, por UF, país e instituição, com contagem fracionária. No piloto (4.275 artigos), 13 dos 57 tópicos têm tendência distinguível do acaso, 93,9% dos vínculos de autoria são ligados a uma de 639 instituições com precisão de 99,8% numa amostra lida à mão, e a geografia leva 2 segundos.

### Adicionado

- **Marco M4 (tópicos no tempo e geografia)**:
  - tendência de cada tópico (em alta, em queda, estável) por regressão logística quase-binomial da participação anual, com `scripts/tendencias.py` para comparar os modelos (ADR 0009);
  - a coleta guarda, de cada documento, os autores segundo o OpenAlex, com as instituições (ROR, país, tipo, linhagem) e os textos de afiliação, sem e-mails; um corpus coletado antes da 0.4.0 é reconhecido (`armazenamento.tem_coluna`);
  - a coleta busca os registros dessas instituições no OpenAlex (siglas, nomes alternativos, cidade, região, linhagem), em lotes de 100, com cache em `brutos/` e gravação em `dados/instituicoes_openalex.parquet`; uns 10 créditos no piloto;
  - tabelas de lugares para a geografia: países em português, inglês e espanhol (do CLDR, com variantes como EUA e Holanda), as 27 UFs com capitais e os 5.571 municípios do IBGE; `geografia/normalizar.py` reconhece o que as fontes escrevem ("Brazi", "RJ)", "Federal District", "Niterói, RJ");
  - casamento das afiliações da ArticleMeta com as instituições do OpenAlex, do candidato mais próximo (a instituição que o OpenAlex deu ao mesmo autor) ao mais distante (todas as instituições conhecidas), com vetos contra nomes parecidos (UFPR × UFPA, UERJ × UFRJ) e contra países divergentes, subida até a universidade "mãe" (EAESP → FGV) e correções do projeto em `instituicoes.yaml`; no piloto, 99% das afiliações da `v240` e 84% das da `v70` identificadas, em menos de um segundo;
  - contagem fracionária da produção (`geografia/contagem.py`): cada documento vale 1, dividido entre os autores e depois entre as afiliações de cada um, com "sem afiliação" para quem não informou; UF de cada vínculo brasileiro pela fonte, pela cidade (com o que a `v240` do corpus ensina sobre cidades homônimas), pelo projeto ou pelo registro do OpenAlex. No piloto, país conhecido em 98,7% do peso e UF em 99,2% do peso brasileiro;
  - `mapa geografia` e `api.geografia()`: a etapa grava `dados/geografia/` (vínculos, pesos e instituições, com o nome em português para as instituições de países lusófonos), registra o manifesto e aparece no `mapa status`, com aviso quando o corpus ou o `instituicoes.yaml` mudaram; as views `vinculos`, `pesos` e `instituicoes` ficam disponíveis em `conectar()`. No piloto, leva 2 segundos;
  - `mapa geografia --revisar [--limite N]`: as afiliações sem instituição mais frequentes, com as grafias agrupadas, as instituições parecidas e um bloco pronto para o `instituicoes.yaml` (apelidos para as sugestões muito parecidas; o resto comentado, como modelo de instituição própria). No piloto, uma rodada leva a `v70` de 83,8% a 86,5%;
  - exportação de `afiliacoes.json` (a contagem fracionária por documento, instituição, UF e país; instituições com id `ror:…`) e dos campos geográficos de `agregados.json`, quando tópicos e geografia estão em dia; `Contagens.com_instituicao` no manifesto. No piloto, 5.959 linhas e 640 instituições em 170 KB;
  - a vista **Geografia** do painel: coroplético das UFs, mapa-múndi com o Brasil fora da escala e ranking das instituições, todos com a contagem fracionária e no filtro cruzado (cada gráfico ignora o próprio filtro); clicar numa UF, num país ou numa instituição põe o lugar no recorte, que vale para as outras vistas; dicas, teclado, "Ver como tabela" e créditos das malhas; escala de cores sequencial nos dois temas, com teste de contraste;
  - na Início, cada macrotema ganha a mini-série da participação por ano e a tendência, e o nome leva à vista Tópicos com ele aberto; "Com afiliação" leva à Geografia e diz quantos documentos têm instituição identificada. A Ajuda explica o recorte e como ler os tópicos e a geografia;
  - cobertura da geografia por ano (peso com instituição identificada, não identificada e sem afiliação), com um aviso gerado dos dados para os anos em que mais de 20% do peso fica sem afiliação;
  - malhas da vista Geografia, versionadas e carregadas sob demanda: as 27 UFs do IBGE (31 KB) e os países do Natural Earth (104 KB), com projeções equivalentes; `frontend/scripts/baixar-malhas.ts` as regenera (ADR 0010);
  - `scripts/calibrar_geografia.py`: identificação por fonte e nível, amostra estratificada para rotular à mão (herdando rótulos antigos) e precisão por nível; no piloto, 92,9% dos vínculos identificados, com precisão de 99,8% numa amostra independente de 200 (ADR 0008, proposta);
  - documentação: tutorial "Seu primeiro mapa, parte 3: tempo e geografia" (a classificação passa a ser a parte 4), guias "Ler os tópicos no tempo", "Gerar a geografia" e "Ler a geografia", explicação "Geografia da produção", ADRs 0008 (geografia), 0009 (tendência) e 0010 (gráficos) aceitos, glossário e capturas das vistas Tópicos e Geografia geradas do piloto (`frontend/scripts/capturas.ts`);
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

[Não lançado]: https://github.com/felipelmc/mapa-da-ciencia/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/felipelmc/mapa-da-ciencia/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/felipelmc/mapa-da-ciencia/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/felipelmc/mapa-da-ciencia/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/felipelmc/mapa-da-ciencia/releases/tag/v0.1.0
