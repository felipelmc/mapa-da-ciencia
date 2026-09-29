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
| `topicos` | [ConfigTopicos](#configtopicos) | valores padrão da seção | Parâmetros do agrupamento em tópicos. Os padrões vêm da calibração no piloto; para outro |
| `validacao` | [Validacao](#validacao) | valores padrão da seção | Amostra de resumos codificados por pessoas para medir a qualidade da classificação. |
| `juri` | [ConfigJuri](#configjuri) | valores padrão da seção | Júri de modelos locais: cada membro classifica a amostra de validação, os que discordam deliberam vendo as |

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
| `referencias` | sim/não | `true` | Buscar no OpenAlex as referências de cada artigo e os dados das obras mais citadas (as redes de citação e o cânone): cerca de 1 crédito a cada 100 artigos, mais 5 créditos, só na primeira coleta. |
| `consulta` | texto ou vazio | vazio | Busca por termo no título e no resumo, via OpenAlex. Com revistas no recorte, busca só nelas; sem revistas, em todo o SciELO. O corpus passa a ser os resultados da busca, e não as revistas inteiras. |

### Recorte

Período e idiomas do corpus.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `anos` | par de inteiro e inteiro | **obrigatório** | Primeiro e último ano de publicação, inclusive. |
| `idioma_analise` | `"pt"` \| `"en"` \| `"es"` | `"en"` | Idioma dos textos usados nos embeddings e nos tópicos. |
| `idioma_exibicao` | `"pt"` \| `"en"` \| `"es"` | `"pt"` | Idioma preferido para mostrar resumos e palavras-chave. |

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
| `modelo` | texto | `"qwen3-embedding:0.6b"` | Nome do modelo no Ollama. |
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

Parâmetros do agrupamento em tópicos. Os padrões vêm da calibração no piloto; para outro
corpus, `scripts/calibrar_topicos.py` refaz a grade.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `vizinhos` | inteiro | `15` | Vizinhos de cada documento no grafo do UMAP: mais vizinhos, estrutura mais global. |
| `min_dist` | número | `0.0` | Distância mínima entre pontos no UMAP de 5 dimensões, usado no agrupamento. |
| `min_dist_mapa` | número | `0.1` | A mesma distância no mapa de 2 dimensões: maior, pontos mais espalhados. |
| `min_cluster_size` | inteiro ou vazio | vazio | Menor tópico, em documentos. Vazio: automático, 1 a cada 200 documentos (mínimo 10). |
| `min_samples` | inteiro | `5` | Quão conservador é o HDBSCAN: maior, mais documentos ficam de fora dos tópicos. |
| `votos_minimos` | inteiro | `3` | Um documento que o HDBSCAN deixou sem tópico vai para o tópico com mais vizinhos seus no núcleo, se forem pelo menos estes (entre os `vizinhos` − 1 mais próximos: o grafo inclui o próprio documento). Menos que isso, fica sem tópico. |
| `selecao` | `"eom"` \| `"leaf"` | `"leaf"` | `leaf` fica com as regiões densas mais finas, e os tópicos mudam pouco quando o corpus muda; `eom` prefere tópicos maiores, mas pode trocar um tópico grande por vários pequenos com uma mudança mínima. |
| `macrotemas` | inteiro | `7` | Quantos macrotemas, no máximo (grupos de tópicos próximos, com cores bem distintas). Com poucos tópicos são menos, para que cada macrotema reúna em média ao menos 3 tópicos. |
| `sementes` | lista de inteiro | `[42, 7, 2024]` | A primeira gera os tópicos; as demais medem a estabilidade (ARI entre as execuções). |

### Validacao

Amostra de resumos codificados por pessoas para medir a qualidade da classificação.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `n` | inteiro | `200` | Tamanho da amostra para codificação humana. |
| `estratificar_por` | `"topico"` \| `"ano"` \| `"revista"` | `"topico"` | Garante que a amostra cubra todos os tópicos (ou anos, ou revistas). |
| `semente` | inteiro | `7` | Semente do sorteio da amostra. |
| `codificadores` | lista de texto | vazio | Nomes de quem vai codificar. |
| `familias` | mapa de texto para texto | vazio | Família de modelo de cada codificador que não é uma pessoa (por exemplo, `claude-opus: claude`). Uma comparação entre dois participantes da mesma família (o codificador de referência e o supervisor do júri, por exemplo) é marcada como circular: a concordância entre eles superestima a qualidade. |

### ConfigJuri

Júri de modelos locais: cada membro classifica a amostra de validação, os que discordam deliberam vendo as
respostas anônimas dos outros, e o que continuar sem maioria vai para o supervisor. Ver "Júri e supervisor".

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `membros` | lista de texto | vazio | Modelos do Ollama que votam, em ordem: o primeiro preside (desempata quando não há maioria nem supervisor). Vazio: sem júri. Use modelos de famílias diferentes; três é o mínimo para haver maioria. |
| `deliberar` | sim/não | `true` | Fazer a rodada de deliberação nas variáveis sem unanimidade. |
| `auditoria` | inteiro | `40` | Decisões unânimes sorteadas para o supervisor conferir (estimativa do erro). |
| `supervisor` | [SupervisorJuri](#supervisorjuri) | valores padrão da seção | O supervisor do júri: arbitra o que os modelos locais não decidiram e audita uma amostra das decisões |

### SupervisorJuri

O supervisor do júri: arbitra o que os modelos locais não decidiram e audita uma amostra das decisões
unânimes. Por padrão trabalha por arquivos (`mapa juri exportar-pedidos` / `importar-respostas`), com quem o
usuário quiser; `modo: api` chama a API da Anthropic, o que envia os títulos e resumos para fora da máquina.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `modo` | `"arquivo"` \| `"api"` | `"arquivo"` | `arquivo`: pedidos e respostas em JSONL, para um supervisor externo; `api`: a API da Anthropic (precisa de `ANTHROPIC_API_KEY` no `.env`, de `enviar_textos: true` e do pacote extra `anthropic`). |
| `nome` | texto | `"supervisor"` | Nome gravado nas decisões do supervisor (minúsculas, números, - e _). |
| `familia` | texto ou vazio | vazio | Família do modelo supervisor (por exemplo, `claude`). Se for a mesma de um codificador de referência (`validacao.familias`), a comparação entre os dois é marcada como circular. Sem família (ou com `humano`), o supervisor é tratado como uma pessoa: as escolhas dele não saem documento a documento no painel publicado. No modo `api`, o padrão é `claude`. |
| `modelo` | texto | `"claude-opus-5-5"` | Modelo da API da Anthropic, no modo `api`. |
| `esforco` | `"low"` \| `"medium"` \| `"high"` | `"medium"` | Esforço de raciocínio pedido ao modelo da API (mais esforço, mais tokens). |
| `enviar_textos` | sim/não | `false` | Consentimento para enviar títulos e resumos à API. Sem ele, o modo `api` se recusa a rodar. |
| `limite_gasto_usd` | número | `5.0` | Gasto máximo estimado por execução, em dólares; acima dele a etapa não começa. |
