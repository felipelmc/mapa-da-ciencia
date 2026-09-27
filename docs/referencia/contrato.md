<!-- Página gerada por scripts/gerar_referencias.py a partir do código. Não edite à mão. -->

# Contrato de dados

Modelos do contrato de dados v1 (arquivos de `saida/dados/`).

Convenções:
- Todo arquivo tem `versao_contrato`. Mudança incompatível = nova versão maior; versões menores
  (1.1, 1.2…) só acrescentam campos, e quem lê a 1.0 lê qualquer 1.x.
- Tabelas grandes são **colunares**: `colunas` com listas do mesmo tamanho, e campos
  categóricos guardados como índices em `dicionarios` (economiza espaço e acelera o
  filtro cruzado no navegador). `-1` significa "sem valor".
- Resumos e evidências ficam fora de `documentos.json`, em fragmentos
  `detalhes/{00..3f}.json`, carregados sob demanda (ver `fragmento_de`).
- Nenhum arquivo do contrato pode conter e-mails ou codificações humanas individuais (as divergências de
  `validacao.json` vêm só de codificadores de referência; as de pessoas ficam na API local do painel).

Versão atual: **1.3**. Os JSON Schemas ficam em [`contrato/schema/`](https://github.com/felipelmc/mapa-da-ciencia/tree/main/contrato/schema), e um exemplo sintético completo em [`contrato/exemplo/dados/`](https://github.com/felipelmc/mapa-da-ciencia/tree/main/contrato/exemplo/dados).

| Arquivo | Modelo |
|---|---|
| `manifesto.json` | [Manifesto](#manifesto) |
| `revistas.json` | [Revistas](#revistas) |
| `documentos.json` | [Documentos](#documentos) |
| `afiliacoes.json` | [Afiliacoes](#afiliacoes) |
| `detalhes/{00..3f}.json` | [Fragmento](#fragmento) |
| `topicos.json` | [Topicos](#topicos) |
| `codebook.json` | [CodebookContrato](#codebookcontrato) |
| `classificacoes.json` | [Classificacoes](#classificacoes) |
| `validacao.json` | [Validacao](#validacao) |
| `agregados.json` | [Agregados](#agregados) |

## `manifesto.json`

### Manifesto

Índice do projeto publicado: o que existe, de onde veio e como foi gerado. É o primeiro arquivo que
a interface lê.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `versao_contrato` | texto | `"1.3"` | Versão do contrato. Versões 1.x só acrescentam campos: quem lê 1.0 lê qualquer 1.x. |
| `api` | sim/não | **obrigatório** | True no painel local (há API); False no site estático publicado. |
| `gerado_em` | datetime | **obrigatório** |  |
| `projeto` | [ProjetoInfo](#projetoinfo) | **obrigatório** | Identificação do projeto. |
| `recorte` | [RecorteInfo](#recorteinfo) | **obrigatório** | Recorte do corpus: período, fontes e idiomas. |
| `contagens` | [Contagens](#contagens) | **obrigatório** | Números do corpus, usados na capa do painel. |
| `arquivos` | lista de texto | **obrigatório** | Arquivos do contrato presentes nesta pasta. |
| `execucao` | [ExecucaoInfo](#execucaoinfo) | **obrigatório** | Dados de reprodutibilidade da última execução de cada etapa. |
| `licencas` | mapa de texto para inteiro | vazio | Licença → número de documentos. |

### ProjetoInfo

Identificação do projeto.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `nome` | texto | **obrigatório** |  |
| `titulo` | texto | **obrigatório** |  |
| `descricao` | texto | `""` |  |

### RecorteInfo

Recorte do corpus: período, fontes e idiomas.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `anos` | par de inteiro e inteiro | **obrigatório** |  |
| `fontes` | lista de texto | **obrigatório** | Ex.: ['scielo:scl', 'openalex']. |
| `idioma_analise` | texto | **obrigatório** |  |
| `idioma_exibicao` | texto | **obrigatório** |  |

### Contagens

Números do corpus, usados na capa do painel.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `documentos` | inteiro | **obrigatório** |  |
| `topicos` | inteiro | `0` |  |
| `classificados` | inteiro | `0` |  |
| `validados` | inteiro | `0` |  |
| `com_afiliacao` | inteiro | `0` |  |
| `com_instituicao` | inteiro | `0` | Documentos com ao menos uma instituição identificada. |

### ExecucaoInfo

Dados de reprodutibilidade da última execução de cada etapa.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `versao_pacote` | texto | **obrigatório** |  |
| `modelos` | mapa de texto para texto | vazio | Papel → `modelo@digest`. |
| `hash_codebook` | texto ou vazio | vazio |  |
| `sementes` | mapa de texto para inteiro | vazio |  |
| `duracao_s` | mapa de texto para número | vazio | Etapa → segundos da última execução. |

## `revistas.json`

### Revistas

Revistas presentes no corpus, com o número de documentos de cada uma.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `versao_contrato` | texto | `"1.3"` | Versão do contrato. Versões 1.x só acrescentam campos: quem lê 1.0 lê qualquer 1.x. |
| `revistas` | lista de [Revista](#revista) | **obrigatório** | Uma revista do corpus. |

### Revista

Uma revista do corpus.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `id` | texto | **obrigatório** | Acrônimo no SciELO, ex.: `dados`. |
| `issn` | texto | **obrigatório** |  |
| `titulo` | texto | **obrigatório** |  |
| `areas` | lista de texto | vazio |  |
| `n` | inteiro | **obrigatório** |  |

## `documentos.json`

### Documentos

Tabela principal: um documento por posição, com coordenadas no mapa, tópico e classificações.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `versao_contrato` | texto | `"1.3"` | Versão do contrato. Versões 1.x só acrescentam campos: quem lê 1.0 lê qualquer 1.x. |
| `n` | inteiro | **obrigatório** |  |
| `colunas` | [ColunasDocumentos](#colunasdocumentos) | **obrigatório** | Colunas da tabela de documentos (todas com `n` itens, na mesma ordem). |
| `dicionarios` | [DicionariosDocumentos](#dicionariosdocumentos) | **obrigatório** | Valores por trás dos índices das colunas categóricas. |

### ColunasDocumentos

Colunas da tabela de documentos (todas com `n` itens, na mesma ordem).

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `id` | lista de texto | **obrigatório** |  |
| `doi` | lista de texto ou vazio | **obrigatório** |  |
| `titulo` | lista de texto | **obrigatório** |  |
| `ano` | lista de inteiro | **obrigatório** |  |
| `revista` | lista de inteiro | **obrigatório** | Índice em `dicionarios.revista`. |
| `idioma` | lista de inteiro | **obrigatório** | Índice em `dicionarios.idioma` (idioma do resumo exibido). |
| `x` | lista de número | **obrigatório** |  |
| `y` | lista de número | **obrigatório** |  |
| `topico` | lista de inteiro | **obrigatório** | Id do tópico (ver topicos.json) ou -1. |
| `atribuicao` | lista de inteiro | **obrigatório** | Índice em `dicionarios.atribuicao`: `cluster` (o HDBSCAN agrupou o documento) ou `vizinho` (o HDBSCAN o deixou sem tópico; os vizinhos o atribuíram, ou não, se `topico` = -1). |
| `autores_curto` | lista de texto | **obrigatório** | Ex.: `Limongi, F.; +2`. |
| `vizinhos` | lista de lista de inteiro | **obrigatório** | Índices (nesta tabela) dos 5 documentos mais próximos. |
| `cls` | mapa de texto para lista de inteiro | vazio | Variável do codebook → índice em `dicionarios.cls[variavel]` ou -1. |

### DicionariosDocumentos

Valores por trás dos índices das colunas categóricas.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `revista` | lista de texto | **obrigatório** |  |
| `idioma` | lista de texto | **obrigatório** |  |
| `atribuicao` | lista de `"cluster"` \\| `"vizinho"` | `["cluster", "vizinho"]` |  |
| `cls` | mapa de texto para lista de texto | vazio |  |

## `afiliacoes.json`

### Afiliacoes

Afiliações com contagem fracionária, base da vista de geografia.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `versao_contrato` | texto | `"1.3"` | Versão do contrato. Versões 1.x só acrescentam campos: quem lê 1.0 lê qualquer 1.x. |
| `n` | inteiro | **obrigatório** |  |
| `colunas` | [ColunasAfiliacoes](#colunasafiliacoes) | **obrigatório** | Colunas da tabela longa de afiliações: uma linha por documento × (instituição, UF, país), pesos somados. |
| `dicionarios` | [DicionariosAfiliacoes](#dicionariosafiliacoes) | **obrigatório** | Instituições, UFs e países por trás dos índices. |

### ColunasAfiliacoes

Colunas da tabela longa de afiliações: uma linha por documento × (instituição, UF, país), pesos somados.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `doc` | lista de inteiro | **obrigatório** | Índice do documento em documentos.json. |
| `instituicao` | lista de inteiro | **obrigatório** | Índice em `dicionarios.instituicao`, ou -1 quando o autor não informou afiliação. |
| `uf` | lista de inteiro | **obrigatório** | Índice em `dicionarios.uf` ou -1 (fora do Brasil ou desconhecida). |
| `pais` | lista de inteiro | **obrigatório** | Índice em `dicionarios.pais` ou -1 (desconhecido). |
| `peso` | lista de número | **obrigatório** | Contagem fracionária: 1 por documento, dividido entre os autores e depois entre as afiliações de cada um. A soma por documento é 1. |

### DicionariosAfiliacoes

Instituições, UFs e países por trás dos índices.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `instituicao` | lista de [Instituicao](#instituicao) | **obrigatório** | Uma instituição de afiliação, já normalizada. |
| `uf` | lista de texto | **obrigatório** | Siglas das UFs (as 27, em ordem alfabética, para índices estáveis). |
| `pais` | lista de texto | **obrigatório** | Códigos ISO 3166-1 alfa-2 presentes nas afiliações. |

### Instituicao

Uma instituição de afiliação, já normalizada.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `id` | texto | **obrigatório** | `ror:…` quando houver, `openalex:I…` sem ROR, um apelido do projeto, ou `nao-identificada` (reservado: afiliação informada que não casou com nenhuma instituição). |
| `nome` | texto | **obrigatório** |  |
| `sigla` | texto ou vazio | vazio |  |
| `uf` | texto ou vazio | vazio |  |
| `pais` | texto | **obrigatório** | ISO 3166-1 alfa-2; vazio em `nao-identificada`. |

## `detalhes/{00..3f}.json`

### Fragmento

Um dos 64 fragmentos de detalhes, carregados sob demanda.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `versao_contrato` | texto | `"1.3"` | Versão do contrato. Versões 1.x só acrescentam campos: quem lê 1.0 lê qualquer 1.x. |
| `fragmento` | texto | **obrigatório** |  |
| `documentos` | mapa de texto para [Detalhe](#detalhe) | **obrigatório** | O que a interface mostra ao abrir um documento: resumo, autores, licença e evidências. |

### Detalhe

O que a interface mostra ao abrir um documento: resumo, autores, licença e evidências.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `resumo` | texto ou vazio | **obrigatório** | None quando a licença não permite publicar o resumo. |
| `idioma` | texto ou vazio | **obrigatório** |  |
| `palavras_chave` | lista de texto | vazio |  |
| `autores` | lista de texto | **obrigatório** |  |
| `url` | texto ou vazio | **obrigatório** |  |
| `licenca` | texto | **obrigatório** |  |
| `licenca_fonte` | texto | **obrigatório** |  |
| `evidencias` | mapa de texto para [Evidencia](#evidencia) | vazio | Valor de uma variável do codebook e o trecho do resumo que o justifica. |
| `idioma_analise` | texto ou vazio | vazio | Idioma do texto usado nos embeddings e nos tópicos. |
| `fonte_analise` | `"resumo"` \\| `"reserva"` \\| `"so_titulo"` ou vazio | vazio | `resumo`: título e resumo no idioma de análise; `reserva`: resumo em outro idioma (não havia no de análise); `so_titulo`: o documento não tem resumo. O texto em si não é publicado. |

### Evidencia

Valor de uma variável do codebook e o trecho do resumo que o justifica.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `valor` | texto ou sim/não ou lista de texto ou vazio | **obrigatório** |  |
| `evidencia` | texto | **obrigatório** |  |
| `status` | `"literal"` \\| `"aproximada"` \\| `"ausente"` \\| `"dispensada"` | **obrigatório** | `literal`: o trecho está no texto; `aproximada`: quase (90% dos caracteres); `ausente`: não está; `dispensada`: vazia numa resposta sem informação. |
| `inicio` | inteiro ou vazio | vazio | Posição do trecho no resumo exibido, se localizado, em pontos de código Unicode (como o Python conta; em JavaScript, converta para UTF-16). |
| `fim` | inteiro ou vazio | vazio |  |
| `campo` | `"titulo"` \\| `"resumo"` ou vazio | vazio | Onde o trecho foi localizado; `inicio` e `fim` são posições nesse texto. |

## `topicos.json`

### Topicos

Tópicos e macrotemas do corpus, com as séries por ano.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `versao_contrato` | texto | `"1.3"` | Versão do contrato. Versões 1.x só acrescentam campos: quem lê 1.0 lê qualquer 1.x. |
| `anos` | lista de inteiro | **obrigatório** |  |
| `total_por_ano` | lista de inteiro | **obrigatório** |  |
| `parametros` | mapa de texto para número ou inteiro ou texto | **obrigatório** |  |
| `estabilidade_ari` | número ou vazio | **obrigatório** |  |
| `macrotemas` | lista de [Macrotema](#macrotema) | **obrigatório** | Agrupamento de tópicos próximos, usado para a cor e a navegação. |
| `topicos` | lista de [Topico](#topico) | **obrigatório** | Um tópico: rótulo e descrição escritos pelo LLM, palavras-chave, cor estável e série no tempo. |
| `outliers` | [Outliers](#outliers) | **obrigatório** | Documentos que o agrupamento não encaixou em nenhum tópico. |
| `metodo_tendencia` | [MetodoTendencia](#metodotendencia) ou vazio | vazio | Como a tendência é calculada. O painel lê daqui os parâmetros para recalcular com os filtros. |

### Macrotema

Agrupamento de tópicos próximos, usado para a cor e a navegação.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `id` | inteiro | **obrigatório** |  |
| `rotulo` | texto | **obrigatório** |  |
| `cor` | texto | **obrigatório** |  |
| `topicos` | lista de inteiro | **obrigatório** |  |
| `descricao` | texto | `""` |  |
| `serie` | [Serie](#serie) ou vazio | vazio | Soma das séries dos tópicos do macrotema. |
| `tendencia` | [Tendencia](#tendencia) ou vazio | vazio | Tendência da participação anual no período inteiro, sem filtros (ADR 0009): o gabarito para o painel. |

### Serie

Série temporal de um tópico.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `n` | lista de inteiro | **obrigatório** | Documentos por ano, alinhado a `anos`. |
| `prop` | lista de número | **obrigatório** | Proporção do total do ano. |

### Tendencia

Tendência da participação anual no período inteiro, sem filtros (ADR 0009): o gabarito para o painel.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `direcao` | `"alta"` \\| `"queda"` \\| `"estavel"` \\| `"insuficiente"` | **obrigatório** |  |
| `inclinacao` | número ou vazio | vazio | Inclinação na escala logit, por ano. |
| `erro_padrao` | número ou vazio | vazio | Erro-padrão da inclinação, já corrigido pela dispersão. |
| `ic95` | par de número e número ou vazio | vazio |  |
| `dispersao` | número ou vazio | vazio | φ de Pearson (1 na binomial pura). |
| `prop_inicio` | número ou vazio | vazio | Participação ajustada no primeiro ano com documentos. |
| `prop_fim` | número ou vazio | vazio | Participação ajustada no último ano com documentos. |
| `pp_periodo` | número ou vazio | vazio | Variação em pontos percentuais no período. |
| `pp_por_ano` | número ou vazio | vazio |  |
| `anos` | par de inteiro e inteiro ou vazio | vazio |  |
| `motivo` | `"poucos_anos"` \\| `"poucos_documentos"` \\| `"sem_variacao"` \\| `"sem_convergencia"` ou vazio | vazio | Por que não há tendência, quando é `insuficiente`. |

### Topico

Um tópico: rótulo e descrição escritos pelo LLM, palavras-chave, cor estável e série no tempo.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `id` | inteiro | **obrigatório** |  |
| `macro_id` | inteiro | **obrigatório** |  |
| `rotulo` | texto | **obrigatório** |  |
| `descricao` | texto | **obrigatório** |  |
| `palavras_chave` | lista de par de texto e número | **obrigatório** |  |
| `n` | inteiro | **obrigatório** |  |
| `centroide` | par de número e número | **obrigatório** |  |
| `cor` | texto | **obrigatório** |  |
| `serie` | [Serie](#serie) | **obrigatório** | Série temporal de um tópico. |
| `por_revista` | mapa de texto para inteiro | **obrigatório** |  |
| `representativos` | lista de texto | **obrigatório** | Ids de documentos. |
| `rotulo_fonte` | `"llm"` \\| `"palavras"` \\| `"manual"` | `"llm"` | Quem escreveu o rótulo: o modelo de linguagem, as palavras-chave ou você (rotulos.yaml). |
| `n_nucleo` | inteiro ou vazio | vazio | Documentos do núcleo, que o HDBSCAN agrupou (os demais foram reatribuídos por vizinhança). |
| `tendencia` | [Tendencia](#tendencia) ou vazio | vazio | Tendência da participação anual no período inteiro, sem filtros (ADR 0009): o gabarito para o painel. |

### Outliers

Documentos que o agrupamento não encaixou em nenhum tópico.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `n` | inteiro | **obrigatório** | Documentos que o HDBSCAN deixou sem tópico. |
| `reatribuidos` | inteiro | **obrigatório** | Quantos deles foram atribuídos ao tópico mais próximo. |
| `por_ano` | lista de inteiro | vazio | Documentos que o HDBSCAN deixou de fora, por ano (inclui os reatribuídos depois), alinhado a `anos`. |
| `sem_topico_por_ano` | lista de inteiro | vazio | Documentos que ficaram sem tópico (−1) no fim, por ano. |

### MetodoTendencia

Como a tendência é calculada. O painel lê daqui os parâmetros para recalcular com os filtros.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `modelo` | `"logistica_binomial"` | `"logistica_binomial"` |  |
| `dispersao` | `"quase"` \\| `"binomial"` | `"quase"` |  |
| `nivel` | número | `0.95` |  |
| `z` | número | `1.959963984540054` |  |
| `anos_minimos` | inteiro | `5` |  |
| `docs_minimos` | inteiro | `10` |  |

## `codebook.json`

### CodebookContrato

Cópia publicada do codebook, com o hash que identifica a versão usada.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `versao_contrato` | texto | `"1.3"` | Versão do contrato. Versões 1.x só acrescentam campos: quem lê 1.0 lê qualquer 1.x. |
| `nome` | texto | **obrigatório** |  |
| `versao` | texto | **obrigatório** |  |
| `hash` | texto | **obrigatório** |  |
| `instrucoes` | texto | **obrigatório** |  |
| `variaveis` | lista de [VariavelContrato](#variavelcontrato) | **obrigatório** | Variável do codebook. |

### VariavelContrato

Variável do codebook.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `id` | texto | **obrigatório** |  |
| `rotulo` | texto | **obrigatório** |  |
| `tipo` | `"categorica"` \\| `"multipla"` \\| `"booleana"` \\| `"texto"` | **obrigatório** |  |
| `pergunta` | texto | **obrigatório** |  |
| `categorias` | lista de [CategoriaContrato](#categoriacontrato) | vazio | Categoria de uma variável, como o codebook define. |

### CategoriaContrato

Categoria de uma variável, como o codebook define.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `valor` | texto | **obrigatório** |  |
| `rotulo` | texto | **obrigatório** |  |
| `definicao` | texto | **obrigatório** |  |
| `exemplos` | lista de texto | vazio |  |

## `classificacoes.json`

### Classificacoes

Resumo da classificação por codebook: modelo, cobertura e contagens por categoria.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `versao_contrato` | texto | `"1.3"` | Versão do contrato. Versões 1.x só acrescentam campos: quem lê 1.0 lê qualquer 1.x. |
| `modelo` | texto | **obrigatório** |  |
| `hash_codebook` | texto | **obrigatório** |  |
| `cobertura` | número | **obrigatório** | Fração dos documentos com classificação válida. |
| `evidencia_literal` | número | **obrigatório** | Fração das evidências encontradas literalmente no resumo. |
| `contagens` | mapa de texto para mapa de texto para inteiro | **obrigatório** | Variável → valor → documentos. Nas de múltipla escolha, cada categoria conta à parte; as de texto ficam de fora. |
| `classificados` | inteiro | `0` |  |
| `documentos` | inteiro | `0` | Documentos com resumo, que podiam ser classificados. |
| `sem_resumo` | inteiro | `0` |  |
| `parcial` | sim/não | `false` | A classificação ainda não cobre todos os documentos com resumo. |
| `json_valido_na_primeira` | número ou vazio | vazio |  |
| `por_variavel` | mapa de texto para [VariavelClassificada](#variavelclassificada) | vazio | Como uma variável saiu na classificação. |

### VariavelClassificada

Como uma variável saiu na classificação.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `n` | inteiro | **obrigatório** | Documentos com resposta nesta variável. |
| `sem_informacao` | número | **obrigatório** | Fração das respostas sem informação (`nao_informado`, `nao_se_aplica` ou falso). |
| `evidencia` | mapa de texto para número | vazio | Status → fração das evidências, sem as dispensadas. |

## `validacao.json`

### Validacao

Resultados da validação da classificação: concordância por variável e por par de participantes.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `versao_contrato` | texto | `"1.3"` | Versão do contrato. Versões 1.x só acrescentam campos: quem lê 1.0 lê qualquer 1.x. |
| `amostra` | [AmostraInfo](#amostrainfo) | **obrigatório** | Como a amostra de validação foi sorteada. |
| `metricas` | lista de [MetricaVariavel](#metricavariavel) | **obrigatório** | Concordância entre dois participantes (codificador × modelo, codificadores ou modelos) numa variável. |
| `modelos` | lista de texto | **obrigatório** |  |
| `divergencias` | lista de [Divergencia](#divergencia) | **obrigatório** | Um caso em que um codificador de referência e o modelo principal discordam, para arbitragem. |
| `codificadores` | lista de [Participante](#participante) | vazio | Participantes, com o tipo. |
| `modelo_principal` | texto ou vazio | vazio |  |
| `hash_codebook` | texto ou vazio | vazio |  |
| `comparacoes_modelos` | lista de [ComparacaoModelos](#comparacaomodelos) | vazio | McNemar exato entre dois modelos, contra a mesma referência, numa variável. |
| `evidencia_literal` | mapa de texto para número | vazio | Modelo → fração das evidências literais na amostra. |

### AmostraInfo

Como a amostra de validação foi sorteada.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `n` | inteiro | **obrigatório** |  |
| `estratificar_por` | texto | **obrigatório** |  |
| `semente` | inteiro | **obrigatório** |  |

### MetricaVariavel

Concordância entre dois participantes (codificador × modelo, codificadores ou modelos) numa variável.
Nas de múltipla escolha, `variavel` é `id:categoria` (uma variável sim/não por categoria).

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `variavel` | texto | **obrigatório** |  |
| `comparacao` | texto | **obrigatório** | Ex.: `claude-opus × qwen3.5:9b` (referência primeiro). |
| `n` | inteiro | **obrigatório** |  |
| `concordancia` | número ou vazio | **obrigatório** |  |
| `kappa` | número ou vazio | **obrigatório** |  |
| `kappa_ic95` | par de número e número ou vazio | **obrigatório** |  |
| `pabak` | número ou vazio | **obrigatório** |  |
| `alfa` | número ou vazio | **obrigatório** |  |
| `matriz` | [Matriz](#matriz) | **obrigatório** | Matriz de confusão entre dois participantes. |
| `referencia` | texto | `""` | Participante tomado como referência (linhas da matriz). |
| `comparado` | texto | `""` |  |
| `por_classe` | lista de [MetricaClasse](#metricaclasse) | vazio | Precisão, revocação e F1 de uma categoria, tomando o primeiro do par como referência. |

### Matriz

Matriz de confusão entre dois participantes.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `rotulos` | lista de texto | **obrigatório** |  |
| `valores` | lista de lista de inteiro | **obrigatório** | Linhas = a referência do par; colunas = o outro participante. |

### MetricaClasse

Precisão, revocação e F1 de uma categoria, tomando o primeiro do par como referência.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `rotulo` | texto | **obrigatório** |  |
| `suporte` | inteiro | **obrigatório** | Quantas vezes a referência deu esta categoria. |
| `precisao` | número ou vazio | **obrigatório** |  |
| `revocacao` | número ou vazio | **obrigatório** |  |
| `f1` | número ou vazio | **obrigatório** |  |

### Divergencia

Um caso em que um codificador de referência e o modelo principal discordam, para arbitragem.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `doc` | texto | **obrigatório** |  |
| `variavel` | texto | **obrigatório** |  |
| `humano` | texto | **obrigatório** | Valor dado pelo codificador (o nome do campo vem da versão 1.0). |
| `modelo` | texto | **obrigatório** |  |
| `evidencia` | texto | **obrigatório** | Trecho que o modelo citou. |
| `codificador` | texto | `""` |  |
| `status` | `"literal"` \\| `"aproximada"` \\| `"ausente"` \\| `"dispensada"` ou vazio | vazio |  |
| `incerto` | sim/não | `false` | O codificador marcou a resposta como incerta. |

### Participante

Quem respondeu na amostra: um codificador (`humano` ou `referencia`, que não é uma pessoa) ou um modelo.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `nome` | texto | **obrigatório** |  |
| `tipo` | `"humano"` \\| `"referencia"` \\| `"modelo"` | **obrigatório** |  |
| `n` | inteiro | **obrigatório** | Documentos da amostra com resposta. |

### ComparacaoModelos

McNemar exato entre dois modelos, contra a mesma referência, numa variável.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `variavel` | texto | **obrigatório** |  |
| `referencia` | texto | **obrigatório** |  |
| `modelo_a` | texto | **obrigatório** |  |
| `modelo_b` | texto | **obrigatório** |  |
| `n` | inteiro | **obrigatório** |  |
| `acertos_a` | inteiro | **obrigatório** |  |
| `acertos_b` | inteiro | **obrigatório** |  |
| `p` | número | **obrigatório** |  |

## `agregados.json`

### Agregados

Gabarito calculado no Python para testar o filtro cruzado do frontend.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `versao_contrato` | texto | `"1.3"` | Versão do contrato. Versões 1.x só acrescentam campos: quem lê 1.0 lê qualquer 1.x. |
| `topico_ano_revista` | lista de tupla | **obrigatório** | (tópico, ano, revista, n). |
| `uf` | mapa de texto para número | **obrigatório** | Contagem fracionária por UF (sigla). |
| `pais` | mapa de texto para número | **obrigatório** | Contagem fracionária por país (ISO alfa-2). |
| `instituicao` | mapa de texto para número | vazio | Contagem fracionária por instituição. |
| `uf_inteiro` | mapa de texto para inteiro | vazio | Documentos com alguma afiliação na UF. |
| `pais_inteiro` | mapa de texto para inteiro | vazio |  |
| `instituicao_inteiro` | mapa de texto para inteiro | vazio |  |
| `sem_afiliacao` | número | `0` | Peso dos autores sem afiliação informada. |
| `sem_pais` | número | `0` | Peso das afiliações de país desconhecido (inclui `sem_afiliacao`). |
