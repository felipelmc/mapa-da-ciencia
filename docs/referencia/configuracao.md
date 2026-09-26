<!-- Página gerada por scripts/gerar_referencias.py a partir do código. Não edite à mão. -->

# Configuração do projeto (mapa.yaml)

Cada projeto tem um `mapa.yaml` na raiz da pasta. `mapa novo` cria um já preenchido e comentado. Campos desconhecidos são recusados, para pegar erros de digitação. Veja também o guia [Criar um projeto](../guias/criar-projeto.md).

## ConfigProjeto

Conteúdo do `mapa.yaml`.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `versao_config` | `1` | `1` | Versão do formato deste arquivo. |
| `nome` | texto | **obrigatório** | Identificador em minúsculas, sem acento. |
| `titulo` | texto | **obrigatório** | Título exibido no painel e no site publicado. |
| `descricao` | texto | `""` | Um parágrafo sobre o recorte e o objetivo do projeto. |
| `fontes` | [Fontes](#fontes) | **obrigatório** | De onde vêm os artigos. Pode combinar mais de uma fonte. |
| `recorte` | [Recorte](#recorte) | **obrigatório** | Período e idiomas do corpus. |
| `modelos` | [Modelos](#modelos) | valores padrão da seção | Modelos locais de cada papel. `mapa novo` preenche conforme a memória da máquina. |
| `topicos` | [ConfigTopicos](#configtopicos) | valores padrão da seção | Parâmetros do agrupamento em tópicos. Os padrões vêm da calibração no piloto (ADR 0007). |
| `validacao` | [Validacao](#validacao) | valores padrão da seção | Amostra de resumos codificados por pessoas para medir a qualidade da classificação. |

### Fontes

De onde vêm os artigos. Pode combinar mais de uma fonte.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `scielo` | [FonteScielo](#fontescielo) ou vazio | vazio | Coleta pela ArticleMeta do SciELO, revista a revista. |
| `openalex` | [FonteOpenAlex](#fonteopenalex) | valores padrão da seção | Enriquecimento (citações, licença) e busca por termo no OpenAlex. |
| `importar` | lista de caminho | vazio | Arquivos RIS, CSV ou BibTeX exportados do search.scielo.org, ou listas de DOIs (.txt), relativos à pasta do projeto. Os da pasta `importados/` entram sempre, sem precisar listar aqui. |

### FonteScielo

Coleta pela ArticleMeta do SciELO, revista a revista.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `colecao` | texto | `"scl"` | Coleção do SciELO (`scl` = Brasil). |
| `revistas` | lista de texto | vazio | ISSNs das revistas; vazio num projeto só com artigos importados. |
| `tipos` | lista de texto | `["research-article", "review-article"]` | Tipos de documento incluídos (`document_type` da ArticleMeta). |

### FonteOpenAlex

Enriquecimento (citações, licença) e busca por termo no OpenAlex.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `enriquecer` | sim/não | `true` | Casar cada artigo com o OpenAlex para obter citações e licença. |
| `consulta` | texto ou vazio | vazio | Busca por termo no título e no resumo, via OpenAlex. Com revistas no recorte, busca só nelas; sem revistas, em todo o SciELO. O corpus passa a ser os resultados da busca, e não as revistas inteiras. |

### Recorte

Período e idiomas do corpus.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `anos` | par de inteiro e inteiro | **obrigatório** | Primeiro e último ano de publicação, inclusive. |
| `idioma_analise` | `"pt"` \\| `"en"` \\| `"es"` | `"en"` | Idioma dos textos usados nos embeddings e nos tópicos (ver ADR 0004). |
| `idioma_exibicao` | `"pt"` \\| `"en"` \\| `"es"` | `"pt"` | Idioma preferido para mostrar resumos e palavras-chave. |

### Modelos

Modelos locais de cada papel. `mapa novo` preenche conforme a memória da máquina.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `embeddings` | [ModeloEmbeddings](#modeloembeddings) | valores padrão da seção | Modelo que transforma título e resumo em vetores (base dos tópicos e do mapa). |
| `classificacao` | [ModeloLLM](#modelollm) | valores padrão da seção | Modelo de linguagem usado para classificar resumos ou nomear tópicos. |
| `rotulos` | [ModeloLLM](#modelollm) | valores padrão da seção | Modelo de linguagem usado para classificar resumos ou nomear tópicos. |

### ModeloEmbeddings

Modelo que transforma título e resumo em vetores (base dos tópicos e do mapa).

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `provedor` | `"ollama"` | `"ollama"` | No MVP, só o Ollama local. |
| `modelo` | texto | `"qwen3-embedding:0.6b"` | Nome do modelo no Ollama (ver ADR 0004). |
| `num_ctx` | inteiro | `2048` | Contexto em tokens. Título e resumo cabem com folga em 2.048; o que passar é truncado. Contextos maiores ocupam mais memória. |
| `lote` | inteiro | `32` | Textos por requisição ao Ollama. |

### ModeloLLM

Modelo de linguagem usado para classificar resumos ou nomear tópicos.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `provedor` | `"ollama"` | `"ollama"` | No MVP, só o Ollama local. |
| `modelo` | texto | `"qwen3.5:9b"` | Nome do modelo no Ollama (ver `mapa diagnostico`). |
| `num_ctx` | inteiro | `8192` | Janela de contexto pedida ao Ollama. |
| `temperatura` | número | `0.0` | 0 = respostas determinísticas (recomendado). |
| `pensar` | sim/não | `false` | Liga o modo de raciocínio do modelo (mais lento). |
| `concorrencia` | inteiro | `1` | Chamadas simultâneas ao Ollama. |
| `semente` | inteiro | `7` | Semente do gerador, para resultados reprodutíveis. |

### ConfigTopicos

Parâmetros do agrupamento em tópicos. Os padrões vêm da calibração no piloto (ADR 0007).

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `vizinhos` | inteiro | `15` | Vizinhos de cada documento no grafo do UMAP: mais vizinhos, estrutura mais global. |
| `min_dist` | número | `0.0` | Distância mínima entre pontos no UMAP de 5 dimensões, usado no agrupamento. |
| `min_dist_mapa` | número | `0.1` | A mesma distância no mapa de 2 dimensões: maior, pontos mais espalhados. |
| `min_cluster_size` | inteiro ou vazio | vazio | Menor tópico, em documentos. Vazio: automático, 1 a cada 200 documentos (mínimo 10). |
| `min_samples` | inteiro | `5` | Quão conservador é o HDBSCAN: maior, mais documentos ficam de fora dos tópicos. |
| `selecao` | `"eom"` \\| `"leaf"` | `"eom"` | `eom` prefere tópicos maiores e mais estáveis; `leaf`, tópicos menores e mais numerosos. |
| `sementes` | lista de inteiro | `[42, 7, 2024]` | A primeira gera os tópicos; as demais medem a estabilidade (ARI entre as execuções). |

### Validacao

Amostra de resumos codificados por pessoas para medir a qualidade da classificação.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `n` | inteiro | `200` | Tamanho da amostra para codificação humana. |
| `estratificar_por` | `"topico"` \\| `"ano"` \\| `"revista"` | `"topico"` | Garante que a amostra cubra todos os tópicos (ou anos, ou revistas). |
| `semente` | inteiro | `7` | Semente do sorteio da amostra. |
| `codificadores` | lista de texto | vazio | Nomes de quem vai codificar. |
