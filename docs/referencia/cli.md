<!-- Página gerada por scripts/gerar_referencias.py a partir do código. Não edite à mão. -->

# Linha de comando

Todos os comandos têm ajuda embutida: `mapa --help` ou `mapa <comando> --help`.

Opção global: `mapa --versao` (`-V`) mostra a versão instalada.

## `mapa novo`

Cria um projeto novo, com mapa.yaml e codebook.yaml prontos para editar.

```
mapa novo [OPÇÕES] pasta
```

| Argumento ou opção | Descrição | Padrão |
|---|---|---|
| `pasta` | Pasta onde o projeto será criado. | **obrigatório** |
| `--modelo`, `-m` | Modelo de projeto: ciencia-politica, vazio. | `ciencia-politica` |
| `--perfil`, `-p` | Perfil de modelos locais: leve, padrao, forte. Padrão: sugerido pela memória da máquina. |  |
| `--revista`, `-r` | ISSN ou acrônimo de uma revista do recorte (repita para várias). |  |
| `--anos` | Período do recorte: 2024 ou 2010-2025. |  |

## `mapa status`

Mostra o recorte do projeto e em que ponto está cada etapa do pipeline.

```
mapa status [OPÇÕES]
```

| Argumento ou opção | Descrição | Padrão |
|---|---|---|
| `--projeto`, `-P` | Pasta do projeto (padrão: a pasta atual ou uma acima dela). | pasta atual |

## `mapa diagnostico`

Confere memória, disco, o Ollama, os modelos do projeto e a conexão com as fontes.

```
mapa diagnostico [OPÇÕES]
```

| Argumento ou opção | Descrição | Padrão |
|---|---|---|
| `--projeto`, `-P` | Pasta do projeto (padrão: a pasta atual ou uma acima dela). | pasta atual |
| `--sem-rede` | Não testa a conexão com ArticleMeta e OpenAlex. |  |

## `mapa publicar`

Gera o site estático do projeto (para o GitHub Pages): resumos só com licença aberta, sem API.

```
mapa publicar [OPÇÕES]
```

| Argumento ou opção | Descrição | Padrão |
|---|---|---|
| `--projeto`, `-P` | Pasta do projeto (padrão: a pasta atual ou uma acima dela). | pasta atual |
| `--destino` | Pasta do site (padrão: saida/site do projeto). |  |
| `--sem-resumos` | Publica sem nenhum resumo, nem os de licença aberta. |  |

## `mapa painel`

Abre o painel no navegador: a interface do projeto, servida só nesta máquina.

```
mapa painel [OPÇÕES]
```

| Argumento ou opção | Descrição | Padrão |
|---|---|---|
| `--projeto`, `-P` | Pasta do projeto (padrão: a pasta atual ou uma acima dela). | pasta atual |
| `--exemplo` | Mostra o exemplo sintético, sem precisar de um projeto. |  |
| `--porta` | Porta local do servidor. | `8765` |
| `--abrir`, `--nao-abrir` | Abre o navegador automaticamente. | `True` |

## `mapa revistas`

Lista as revistas do SciELO Brasil, para escolher o recorte de um projeto.

```
mapa revistas [OPÇÕES] busca
```

| Argumento ou opção | Descrição | Padrão |
|---|---|---|
| `busca` | Parte do título, acrônimo, categoria ou ISSN. | **obrigatório** |
| `--area`, `-a` | Filtra pela grande área (ex.: humanas, saúde). | `` |
| `--yaml` | Imprime as linhas prontas para colar em `fontes.scielo.revistas`. |  |

## `mapa coletar`

Coleta os artigos do recorte e monta o corpus do projeto (dados/documentos.parquet).

```
mapa coletar [OPÇÕES]
```

| Argumento ou opção | Descrição | Padrão |
|---|---|---|
| `--projeto`, `-P` | Pasta do projeto (padrão: a pasta atual ou uma acima dela). | pasta atual |
| `--revista`, `-r` | Coleta só esta revista (ISSN ou acrônimo); repita para várias. |  |
| `--anos` | Coleta só este período: 2024 ou 2010-2025. |  |
| `--limite` | Coleta só os N primeiros artigos (para testar). |  |
| `--atualizar` | Baixa de novo as listas de artigos (para pegar publicações novas). |  |
| `--offline` | Não acessa a internet: usa só o que está em brutos/. |  |
| `--sem-openalex` | Não enriquece com o OpenAlex (citações, licença por artigo). |  |
| `--consulta` | Só os artigos cujo título ou resumo respondem a esta busca (via OpenAlex). |  |

## `mapa topicos`

Descobre os tópicos do corpus, dá um nome a cada um e prepara o mapa do painel.

```
mapa topicos [OPÇÕES]
```

| Argumento ou opção | Descrição | Padrão |
|---|---|---|
| `--projeto`, `-P` | Pasta do projeto (padrão: a pasta atual ou uma acima dela). | pasta atual |
| `--sem-rotulos` | Rótulos pelas palavras-chave, sem carregar o modelo de linguagem. |  |
| `--refazer-embeddings` | Recalcula os embeddings de todos os documentos. |  |
| `--semente` | Semente principal do UMAP (padrão: a primeira de topicos.sementes). |  |
| `--refazer-macrotemas` | Agrupa os tópicos em macrotemas de novo, em vez de manter os da execução anterior (as cores mudam). |  |

## `mapa classificar`

Classifica os resumos segundo o codebook do projeto, com evidência textual para cada resposta.

```
mapa classificar [OPÇÕES]
```

| Argumento ou opção | Descrição | Padrão |
|---|---|---|
| `--projeto`, `-P` | Pasta do projeto (padrão: a pasta atual ou uma acima dela). | pasta atual |
| `--estimar` | Classifica 5 documentos, mede o tempo e projeta quanto falta. Grava os 5. |  |
| `--limite` | Classifica só os primeiros N da fila (a amostra de validação, depois por id). |  |
| `--modelo` | Outro modelo do Ollama, para comparar (o painel mostra só o principal). |  |
| `--somente-amostra` | Classifica só os documentos da amostra de validação. |  |

## `mapa redes`

Redes de coautoria, de colaboração entre instituições e estados, e de citação, com as comunidades.

```
mapa redes [OPÇÕES]
```

| Argumento ou opção | Descrição | Padrão |
|---|---|---|
| `--projeto`, `-P` | Pasta do projeto (padrão: a pasta atual ou uma acima dela). | pasta atual |
| `--revisar` | Lista os homônimos que podem ser a mesma pessoa, com um bloco para o pessoas.yaml. |  |
| `--limite` | Quantos homônimos listar na revisão. | `20` |

## `mapa geografia`

Liga cada afiliação a uma instituição, com UF e país, e faz a contagem fracionária da produção.

```
mapa geografia [OPÇÕES]
```

| Argumento ou opção | Descrição | Padrão |
|---|---|---|
| `--projeto`, `-P` | Pasta do projeto (padrão: a pasta atual ou uma acima dela). | pasta atual |
| `--revisar` | Lista as afiliações que não casaram, com sugestões e um bloco pronto para o instituicoes.yaml. |  |
| `--limite` | Quantas afiliações listar na revisão. | `20` |

## `mapa importar`

Acrescenta ao projeto artigos de uma busca exportada do search.scielo.org (ou de uma lista de DOIs).

```
mapa importar [OPÇÕES] arquivos
```

| Argumento ou opção | Descrição | Padrão |
|---|---|---|
| `arquivos` | Arquivos RIS, CSV ou BibTeX do search.scielo.org, ou listas de DOIs (.txt). | **obrigatório** |
| `--projeto`, `-P` | Pasta do projeto (padrão: a pasta atual ou uma acima dela). | pasta atual |
| `--nao-coletar` | Só copia os arquivos para importados/, sem rodar a coleta. |  |
| `--sem-openalex` | Não usa o OpenAlex na coleta. |  |

## `mapa validar`

Validação da classificação: a amostra, as codificações e a concordância.

```
mapa validar [OPÇÕES]
```

## `mapa juri`

Júri de modelos locais: votação, deliberação, supervisor e relatório (ver o guia "Usar o júri").

```
mapa juri [OPÇÕES]
```
