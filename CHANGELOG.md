# Registro de mudanças

Todas as mudanças relevantes do projeto ficam registradas aqui. O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/), e as versões seguem o [versionamento semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

### Adicionado

- **Grafos mais interativos** na coautoria e nas instituições: passar o mouse num nó acende ele, os vizinhos e as ligações entre eles, com os nomes; uma comunidade escolhida na legenda ou no rótulo do desenho fica acesa e enquadrada, e vai para o link (`comunidade=`); "Enquadrar" leva o zoom até a vizinhança do nó aberto (e a busca e os links já abrem o nó enquadrado); os nomes aparecem com o zoom, sem se cobrirem; arrastar um nó o move na tela; clique duplo, teclado (+, −, 0 e as setas) e tela cheia. As arestas entre comunidades ficam mais fracas que as de dentro delas.
- Nas redes de estados e de citações: passar o mouse numa UF acende só os arcos dela (sem filtrar), e o Exterior ganha dica; na matriz de citações, passar o mouse numa célula acende a linha e a coluna, e os rótulos usam a largura que sobra; no cânone, a dica traz a referência inteira e os citantes por macrotema.

### Mudado

- **A área de conteúdo fica centrada e mais larga** (até 104rem, 1.664 px): numa tela larga ou em tela cheia, as vistas não ficam mais encostadas à esquerda, e as figuras crescem com a janela (o texto corrido continua na medida de leitura). O grafo das redes ocupa quase a altura da janela.
- Nas redes, a roda do mouse sozinha rola a página (com um aviso de como aproximar), em vez de prender quem lê no grafo; Ctrl/⌘ + roda e a pinça aproximam. No celular, um dedo na vertical rola a página.

- **O desenho das redes de coautoria e de instituições** (`mapa redes`, adendo do ADR 0014): no maior componente, cada comunidade ganha um espaço próprio, e as comunidades muito ligadas ficam vizinhas; os componentes menores vêm à direita e embaixo do maior, e nenhum nó encosta noutro numa tela de computador. No piloto, os nós encostados caem de 57% para 0%, e o maior componente passa de 27% para 61% do desenho. As redes de um projeto ficam desatualizadas até a próxima `mapa redes`.

### Corrigido

- nas redes, abrir um nó com um clique não rola mais a página até o cartão (o foco só vai para o cartão quando a escolha vem do teclado); no celular, um botão leva ao cartão, que fica embaixo do grafo.
- nas redes, a dica e o nome do nó aberto não saem mais cortados nas bordas do grafo, e o texto de abertura conta as pessoas desenhadas de fato (sem as duplas e os trios escondidos).
- o raio dos nós vai de 1 documento (o raio mínimo) ao nó com mais documentos; antes o menor nó saía bem maior que o mínimo, e os nós se sobrepunham mais.
- a vista Validação voltou a abrir no site publicado e no painel com o júri: com seis modelos, dois pares com diferença significativa (McNemar) na mesma variável repetiam a chave da lista, e a página ficava parada em "Carregando a validação…". O exemplo do contrato agora tem vários pares por variável, como o piloto.
- um erro ao desenhar uma vista vira um aviso com "Tentar de novo", em vez de deixar a página parada em "Carregando…" ou em branco; a troca de seção recomeça do zero.

## [2.0.0] - 2026-09-28

A versão 2.0.0 traz duas frentes novas, o **júri de modelos locais com supervisor** e as **redes de coautoria e de citação**, e o resultado de uma revisão geral do projeto por agentes independentes (veja a página [Revisão geral](docs/desenvolvimento/revisao-2026-09.md)). No piloto, o júri leva a `tecnica_principal` de kappa 0,37 a 0,61 (o melhor membro sozinho, o `gemma4:12b`, chega a 0,65), e as redes mostram a colaboração quase dobrando: artigos com mais de um autor eram 29% em 2010–2014 e são 57% em 2021–2025.

### Adicionado

- **Júri de modelos locais e supervisor** (ADR 0015; `mapa juri votar|deliberar|exportar-pedidos|importar-respostas|supervisionar|status|relatorio`): vários modelos locais classificam a amostra de validação, os que discordam deliberam uma vez vendo as respostas anônimas dos outros, e o que continua sem maioria vai a um supervisor que escolhe entre os candidatos, com evidência do texto. O supervisor trabalha por arquivos (JSONL, sem rede) ou, opcionalmente, pela API da Anthropic (extra `[anthropic]`), com consentimento explícito, estimativa de custo e um limite de gasto que o pior caso de cada chamada respeita. Uma auditoria sorteia decisões unânimes para o supervisor conferir, com o intervalo de Wilson. As três fontes (`juri-r1`, `juri`, `juri-supervisor`) entram na validação como mais três participantes; `validacao.familias` marca como **circulares** as comparações entre codificadores da mesma família de modelo, e o número principal do relatório não passa pelo supervisor. Um supervisor que é uma pessoa não sai documento a documento no site publicado. No piloto, a `tecnica_principal` sai de kappa 0,37 (um modelo) para 0,61 (júri de três); o melhor membro sozinho chega a 0,65. As sugestões para o codebook ficam em `validacao/`.
- **Redes de coautoria, de instituições, de estados e de citação** (ADR 0014; `mapa redes [--revisar]`, vista Redes no painel e na demo): pessoas identificadas por id do OpenAlex, ORCID conferido pelo nome e homônimos com coautor ou instituição em comum, com revisão manual (`pessoas.yaml`); pesos fracionários, comunidades (Louvain, rotuladas pelos tópicos, sem nomes de pessoas), desenho fixo no Python e o recorte comum que esmaece sem mover o desenho; citações dentro do corpus, o fluxo entre macrotemas e o cânone das obras de fora mais citadas, com a autoria conferida nas referências da ArticleMeta (o OpenAlex casa referências com resenhas). A coleta traz as referências do OpenAlex em lotes de 100 (cerca de 1 crédito a cada 100 artigos, só na primeira vez). O site não publica ORCIDs: o id de cada pessoa é um HMAC com um segredo do projeto, e `mapa publicar` recusa ORCIDs.
- Contrato de dados **1.5** (só acréscimos): `redes.json`, `citacoes.json`, o júri em `validacao.json` e nos detalhes da amostra, `Participante.familia` e `MetricaVariavel.circular`.
- Duas histórias na abertura do site, tiradas das redes: a colaboração (artigos com mais de um autor, com autores de mais de uma UF e com Brasil e exterior, do início ao fim do período, com os denominadores à vista) e o cânone (quantos artigos citam as obras mais citadas de fora do corpus, sem nomes nem títulos, com a ressalva da cobertura do OpenAlex no cartão).
- A página [Revisão geral (setembro de 2026)](docs/desenvolvimento/revisao-2026-09.md): o método (revisores e verificadores independentes, rubrica, evidência reproduzível), as notas por dimensão e o funil dos achados.
- a vista **Redes** no painel e no site (`#/redes`), recalculada no recorte comum: a coautoria e a colaboração entre instituições num grafo em canvas sobre o desenho do corpus inteiro (quem sai do recorte fica esmaecido; as arestas em faixas pelo peso fracionário), com zoom, busca pelo teclado e o cartão de cada nó com os documentos no recorte; os arcos da colaboração entre estados (e com o exterior) sobre o mapa das UFs; o cânone (as obras mais citadas, pelo macrotema de quem cita, com a nota da cobertura do OpenAlex) e a matriz das citações entre macrotemas; as séries da colaboração por ano. A Ajuda ganha "Como ler as redes".
- o DOI de conceito do Zenodo ([10.5281/zenodo.22998585](https://doi.org/10.5281/zenodo.22998585), todas as versões) no `CITATION.cff`, no README (com o selo e uma seção "Como citar" com o BibTeX), na metodologia (também com o BibTeX) e no rodapé da abertura do site, que o lê do `CITATION.cff`.
- a seção "Como citar" na abertura do site, com a referência, o BibTeX e um botão de copiar, gerados do `CITATION.cff` (`overrides/hooks.py`); um teste confere que o BibTeX do README e da metodologia é o mesmo.

### Mudado

- o repositório ignora as cópias que o iCloud Drive cria ("teste 2.py", "index 2.md") no git, no pytest e no MkDocs, e o CI falha se alguma entrar num commit (armadilha em `desenvolvimento`).
- o resultado da classificação (`dados/classificacao/*.json`) ganha os campos `execucao` e `a_parte`, e o manifesto da classificação, os parâmetros `execucao`, `gravado` e `interrompida`: uma versão anterior do pacote (por exemplo o *wheel* 1.0.1 do caderno do Colab) que abrir um projeto classificado com esta cai com `TypeError`.
- o piloto publicado: 21 rótulos de tópico e os 7 macrotemas corrigidos à mão (`rotulos.yaml`: rótulos que os próprios títulos dos artigos desmentiam, como "Política externa brasileira sob Lula" com Lula em 25 de 208 títulos), e, na geografia, 5 siglas que o casamento mandava para universidades estrangeiras (a "USP" que ia para a Universidad San Pedro, no Peru) e a UF da FGV, que a ArticleMeta põe em Brasília (`instituicoes.yaml`).
- o `.gitignore` que o `mapa novo` cria cobre também `juri/` (os pedidos ao supervisor, com os resumos inteiros, e as respostas dele).
- a geografia normaliza os hífens tipográficos (U+2010 a U+2015 e o sinal de menos) e o "ı" sem ponto, e o alinhamento 1:1 entre as afiliações das duas fontes confere o nome (versão 2 da etapa: rode `mapa geografia` de novo).

### Corrigido

- a classificação guardada só perde documentos numa rodada que cobre o corpus atual (os que saíram dele, e, numa troca de versão, no máximo 2% de falhas): só uma rodada que cobre o corpus atual (sem `--somente-amostra`, `--estimar` ou `--limite`, sem ser interrompida) e deixa até 2% dos documentos sem resposta válida (no mínimo 1) substitui o resultado principal, de qualquer versão do modelo ou dos parâmetros; qualquer outra rodada, inclusive uma completa com falhas demais, só grava nele se ele ainda não existe ou se todo documento classificado nele (mesmo o que saiu do corpus ou ficou sem resumo por um tempo) continua classificado; na 1.0.1, qualquer rodada, mesmo parcial, trocava a classificação completa, sem volta depois de um `ollama pull`; o resultado é gravado sem apagar o JSON antes, e um Parquet que ficou sem JSON continua protegido;
- quando uma rodada não pode gravar no resultado principal, as respostas dela ficam num resultado à parte (`<modelo>__<hash do codebook>__a-parte`), com aviso, que `mapa validar metricas`, o relatório e a vista Validação do painel comparam com o principal como "<modelo> (versão nova)", ou "<modelo> (rodada parcial)" quando é da mesma execução; ele não entra no `validacao.json` nem no site publicado, e sai quando o resultado principal é gravado de novo;
- o `mapa status` mostra a versão à parte e os documentos sem resposta válida, e o guia "Classificar os resumos" explica o que fazer com um documento que falha sempre (com temperatura 0 e semente fixa, rodar de novo repete a falha);
- o status, o painel e a duração publicada mostram o manifesto da execução que gerou o resultado principal da classificação (`parametros.execucao`), e não o de uma rodada que manteve o resultado anterior nem o de uma execução anterior; uma rodada interrompida que grava algo também registra o seu manifesto (`interrompida`), e, se a execução dos dados não deixou nenhum, nenhum é mostrado; o manifesto registra o hash do codebook que a etapa usou, mesmo que o `codebook.yaml` seja editado no meio dela;
- `mapa topicos` num projeto sem coleta volta a dizer "Rode `mapa coletar` antes", na CLI e no job do painel, sem o erro cru do DuckDB;
- um `mapa.yaml` ou `codebook.yaml` salvo com erro dá o erro em toda leitura até ser corrigido, e não volta em silêncio à versão anterior;
- o detector de e-mails, que na 1.0.1 só via a forma comum (`fulana@exemplo.br`), passa a pegar também o arroba largo (`＠`, `﹫`), os endereços escondidos por um hífen suave, um espaço de largura zero ou o ponto largo, e as formas com espaço em volta do `@` ou depois do ponto, ou com `[at]`/`(arroba)` e `[dot]`/`(ponto)` (em qualquer lugar do domínio), quando o domínio termina, em minúsculas, num domínio de país ou num genérico comum (`.com`, `.org`, `.io`, `.cat`…): `maria@ up.ac.pa` e `[at] … [dot] io` saem inteiros; na forma ambígua `palavra @dominio.tld` (um e-mail com espaço antes do `@`, ou um perfil de rede social como `@frente.pe`), sai só o `@dominio.tld`, e a palavra anterior fica; um perfil que não termina num domínio de topo (`@maria.silva`) fica inteiro; na forma com espaço depois do ponto, o primeiro rótulo do domínio precisa de dois caracteres ou mais, um deles letra, para `entre tod@s. no entanto` e `P@10. de acordo` não apagarem texto (por isso `fulana@a. br` escapa); o detector roda em tempo linear;
- `mapa validar amostra` tira do arquivo um e-mail que tenha ficado no texto do corpus, com aviso, em vez de cair com `AssertionError`.
- as vistas cabem na tela do celular, do tablet e de 1024 px: Tópicos, Geografia, Classificação, Validação e a Início rolavam de lado (a coluna das grades crescia até o gráfico mais largo), e no celular a barra de navegação saía da tela; as tabelas da Validação rolam na própria caixa, os macrotemas e as tendências se rearranjam pela largura da seção e a linha do tempo quebra de linha.
- o mapa acompanha a janela redimensionada, o modo apresentação (++p++) e o painel recolhido; antes, o canvas ficava no tamanho do primeiro desenho, cortado ou menor que a tela.
- no celular, o painel e o cartão do mapa terminam acima da barra de navegação (a legenda ficava espremida atrás dela), e a lista de resultados da busca aparece inteira ao lado de uma legenda longa, dizendo quantos resultados ficaram de fora.
- a barra de navegação do celular mostra, com um degradê na borda, que há mais seções, e deixa de fora a seção ainda desativada.
- texto que informa (créditos, notas, o intervalo do kappa, a legenda da matriz de confusão) usa `--texto-suave`, com contraste AA, e não mais `--texto-fraco`, reservado a itens desativados; a diagonal da matriz também passa no AA, e um teste varre os componentes.
- o CSV das figuras sai com números crus (ponto decimal, sem separador de milhar, proporções como fração, intervalos em duas colunas), que o R e o pandas leem sem limpeza; antes, reaproveitava os números formatados em pt-BR da tela, e o R lia 1.095 documentos como 1,095.
- o SVG e o PNG exportados levam o fundo do tema do preset; saíam transparentes, e no Telão e no Slide o título quase branco sumia num slide claro.
- uma figura sem gráfico (as tendências, o cruzamento, o ranking) exporta o CSV já escolhido, e o primeiro clique em Baixar não falha mais.
- uma falha passageira de rede não deixa as vistas quebradas até recarregar a página: elas mostram "Tentar de novo", a barra do recorte volta sozinha (também quando se segue pelo trilho), e a falha do arquivo das afiliações só afeta a Geografia.
- o título de Tópicos, Geografia, Classificação e Validação é anunciado ao navegar (os leitores de tela ouviam o da página anterior), e ao fechar a gaveta do tópico ou o cartão do mapa o foco volta a quem os abriu.
- um link com "&" na busca do mapa reabre a mesma busca (o SvelteKit decodifica o hash na carga, e "voto & partido" abria como "voto").
- um gesto nos controles de ano cria uma entrada só no histórico do navegador (antes, uma por ano), e o campo de busca do mapa acompanha a URL ao voltar.
- o chip "Laço" mostra quantos documentos há no laço, e não repete o contador do recorte.
- um laço compartilhado não abre mais com o aviso de "versão anterior do mapa" depois de uma reexportação (classificar, geografia, publicar): a versão do mapa passa a ser um hash das coordenadas dos documentos.
- na codificação, o ++tab++ sai da ficha (antes, trocava de variável e prendia o foco nela); ++down++ e ++up++ continuam trocando de variável.
- a Ajuda do site publicado não diz mais que as vistas prontas "chegam no marco M3…M6", nem que os arquivos estão "no seu computador", e descreve a Validação como concordância com uma codificação de referência (de uma pessoa ou de outro modelo).
- a nota de "Em alta e em queda" e a Ajuda avisam que um pico no primeiro ou no último ano do período (um dossiê temático) pode puxar a tendência, e que algumas marcações são marginais.
- na tabela da Validação, o kappa de uma variável de texto livre aparece como "não se aplica", e não como "sem variação".
- o menu "Revistas" fecha com ++esc++ e com um clique fora, e esse clique não chega mais ao mapa (abria um documento ou filtrava um macrotema sem a pessoa perceber); aberto, o menu não passa mais da borda direita da tela entre 768 e 1024 px.
- um link com um documento, tópico ou macrotema que não existe nesta publicação avisa e tira o parâmetro do endereço, em vez de abrir a vista calado.
- a página 404 diz "Voltar ao Início"; no cartão, o DOI leva ao doi.org e a página do artigo (em https) é outro link; a Início mostra as fontes pelo nome ("SciELO (coleção scl)"), e não pelo código; nos pequenos múltiplos por revista, os anos das pontas não se encostam mais.
- o botão da linha do tempo se chama "Tocar", e não "Play".
- `mapa painel --porta` aceita só portas de 1 a 65535 (uma porta fora da faixa dava traceback), tenta ocupar a porta antes de anunciar o endereço (e explica em português por que não conseguiu) e sugere a primeira porta livre.
- a ajuda (`-h`), com os tipos das opções (`<caminho>`, `<texto>`, `<inteiro>`), e os erros de uso mais comuns da CLI ("Opção inexistente", "Comando inexistente… Você quis dizer", "Valor inválido", "Falta o argumento", "Argumentos a mais") saem em português (`cli_portugues.py`).
- a descrição da reatribuição do ruído nos tópicos, na metodologia, no ADR 0007 e em `topicos.votos_minimos`: votam os 14 vizinhos mais próximos, porque o grafo de 15 do UMAP inclui o próprio documento (o código não muda).
- números do piloto nas explicações e nos ADRs, conferidos com a rodada publicada: o texto de análise (4.159 com resumo em inglês, 88 em reserva, 28 só com título), a evidência literal e o tempo da classificação completa (93,4%, 9,6 s por resumo), +2,5 pontos para comunicação política nas redes sociais, 111 divergências na técnica e 16,4 s no 90º percentil da amostra.
- as limitações do método, nas explicações e no ADR 0007: a classificação lê o resumo em inglês quando falta o em português (18% do piloto); cerca de 25 "resumos" do piloto são fragmentos da fonte e passam pela coleta; o ARI é 0,89 no núcleo e 0,78 com os reatribuídos (não 0,79), e o maior tópico chega a 4,9% do corpus com eles; os erros medidos da geografia vêm de textos raspados pelo OpenAlex e das travas, e não de nomes parecidos; "modelos maiores concordariam mais" vira hipótese.
- os 84% de concordância no período analisado, na validação e no ADR 0012, vêm com a nota de que 115 dos 168 acertos são "não se aplica" nos dois (entre os 85 artigos com algum período, 62%; a presença do período tem kappa 0,85).
- a tendência dos tópicos, no ADR 0009, nos tópicos e no guia "Ler os tópicos": um dossiê no primeiro ou no último ano da janela (o período inteiro ou o filtrado) ainda pode aparecer como tendência, e três dos 13 tópicos marcados no piloto são marginais (somem com o quantil t ou com um ano a menos); o ADR dizia que todos tinham mudança sustentada.
- o perfil `leve` classifica com o `qwen3.5:4b`, que ainda não passou pela validação: um adendo ao ADR 0005 registra a escolha, e o guia de instalação e as limitações avisam.
- a instalação pelo *wheel*: o tutorial "Seu primeiro mapa" e a API Python dizem como abrir um Python com o pacote (`uv run --no-project --with <wheel> python`), o README, "Explorar o exemplo", o guia de instalação e a solução de problemas dizem o que fazer quando o terminal não encontra o `mapa` (`uv tool update-shell`), o guia de instalação manda trocar `1.0.1` (e não `0.6.0`), e a caixa da Documentação fala da versão 1.0.
- deslizes menores: o link das fontes para a geografia levava ao guia do painel; a calibração dos tópicos pede o código-fonte (o script não vem no *wheel*); a primeira coleta do piloto leva uns 30 minutos, e não "alguns minutos"; a escolha dos modelos cita também o ADR 0005.
- "Modelos locais" e "Reprodutibilidade" falavam da classificação no futuro ("o marco M5 vai") e com a projeção de 14 horas do M0: agora no presente, com os 9,6 s por resumo do piloto, cerca de 12 horas para os 4.247 resumos.
- os exemplos de `rotulos.yaml` (explicação dos tópicos, guia e parte 2 do tutorial) trazem a `descricao` e avisam que uma entrada só com o rótulo deixa o tópico sem descrição.
- as frases das histórias da abertura, em português e em inglês: os +4,1 pontos do tópico em alta são da tendência ajustada (o gráfico mostra a participação observada); os 79% dos autores no Brasil são da produção com país conhecido, e não de toda a produção; a BPSR, só em inglês, está entre as "outras oito", em que o inglês ficou entre 14% e 20% de 2019 a 2025; a abordagem teórica caiu quase pela metade, e o cartão diz que o modelo a marca mais que a referência (40% contra 27% na validação), com a queda nas duas leituras.
- o painel local recusa pedidos com um cabeçalho `Host` de fora em todas as rotas (e não só na API), o que fecha a leitura dos dados por *DNS rebinding*; no modo Colab, os pedidos de escrita conferem a origem.
- um endereço de artigo que não é `http(s)` (como `javascript:`) não vai mais para um link do painel ou do site.
- o estado de cada etapa é o mesmo no `mapa status` e na linha de metrô do painel, e só a classificação principal decide o dela (uma comparação com `--modelo` não a marca como atualizada); a validação registra a etapa, e o status conta a amostra como codificada só com todas as variáveis respondidas.
- o painel relê o `mapa.yaml` e o `codebook.yaml` quando eles mudam no disco; chaves repetidas nesses arquivos, no `rotulos.yaml` e no `instituicoes.yaml` dão erro, em vez de a última valer em silêncio.
- a referência da CLI inclui os subcomandos (`mapa validar …`, `mapa juri …`); os erros da CLI não perdem o texto entre colchetes; `recorte.anos` inválido diz o formato; um corpus vazio ou um documento da amostra que saiu do corpus não derrubam mais a etapa; um job interrompido pelo fim do servidor aparece como erro no painel.
- os títulos e resumos que vêm do OpenAlex passam pelo mesmo detector de e-mails que os da ArticleMeta.
- o workflow de CI roda com permissão só de leitura.

## [1.0.1] - 2026-09-27

A versão 1.0.1 é a primeira com DOI: o repositório passa a ser arquivado no Zenodo a cada *release*. E o pacote fica pronto para o PyPI.

### Adicionado

- arquivamento no Zenodo: cada *release* ganha um DOI, com o ORCID e a afiliação do autor no `.zenodo.json` e no `CITATION.cff` (a licença usa o identificador do vocabulário do Zenodo, `mit`).

### Mudado

- o pacote fica pronto para o PyPI: endereços do site, da documentação, da demo e das mudanças nos metadados, classificadores de uma versão estável, imagens e links do README com endereço completo (o PyPI não resolve caminhos relativos) e um *sdist* só com o código do pacote (antes levava os spikes e o frontend); o CI e o workflow Release conferem os metadados com `twine check`.

## [1.0.0] - 2026-09-27

A versão 1.0.0 fecha o plano do projeto. A abertura do site, "Céu que se forma", mostra os 4.275 artigos do piloto acendendo ano a ano e se juntando nas constelações dos seus assuntos, com as histórias que os dados contam: a polarização em alta, as redes sociais depois de 2018, SP, RJ e DF com 61% da produção brasileira, as revistas de relações internacionais só em inglês desde 2016, os ensaios teóricos caindo de 49% para 26% dos artigos. E a exportação passa a funcionar em pastas sincronizadas pelo iCloud Drive.

### Corrigido

- o `mapa publicar --destino` só escreve numa pasta vazia, numa que ainda não existe ou num site publicado antes (marcado com `.mapa-site`), e nunca na pasta do projeto ou numa que a contenha: como a publicação troca todo o conteúdo do destino, `--destino .` apagava o projeto;
- a exportação (`saida/dados`) e o `mapa publicar` trocam o conteúdo da pasta arquivo por arquivo, e não a pasta inteira: numa pasta sincronizada pelo iCloud Drive (a Mesa ou os Documentos do macOS), trocar a pasta de nome fazia o serviço guardar a nova como "dados 2" e deixava o projeto sem `saida/dados` (`pastas.substituir_conteudo`; guia de problemas);

### Adicionado

- **Abertura do site, "Céu que se forma"**: a página inicial da documentação vira uma abertura própria (`overrides/home.html`). Os 4.275 artigos do piloto acendem como estrelas, ano a ano, e se juntam nas constelações dos macrotemas (a árvore geradora mínima entre os tópicos de cada um), com os rótulos levando à demo; os números do piloto, seis histórias com mini-gráficos tirados dos dados (o tópico em alta, o mais recente, a concentração em SP, RJ e DF, o inglês nas revistas de RI, a abordagem das pesquisas e o kappa por variável), os seis passos do método e uma busca nos tópicos. Em português e inglês, nos temas Observatório e Prancha, com movimento reduzido e no celular. Os dados vêm de `scripts/gerar_pagina.py`; os testes, do Playwright sobre o site montado (no CI) e do pytest. A página inicial antiga vira "Documentação";

## [0.7.0] - 2026-09-27

A publicação, as figuras e a oficina: o projeto vira um site estático, com os resumos só de licença Creative Commons e nenhum e-mail; cada gráfico do painel sai em SVG, PNG ou CSV no tamanho de um artigo ou de um slide; e um caderno do Colab monta um mapa do zero numa GPU gratuita. O piloto inteiro está publicado na [demo](https://felipelamarca.com/mapa-da-ciencia/demo/): os 4.247 resumos classificados pelo `qwen3.5:9b` num notebook, em cerca de 12 horas (9,6 s por resumo, na mediana), com 100% de JSON válido na primeira tentativa e 93,4% das evidências copiadas literalmente do título ou do resumo.

### Adicionado

- **Marco M7 (publicação, figuras e oficina)**:
  - **Exportar figuras** (`lib/exportar/`): cada gráfico do painel baixa em SVG (com título, recorte, fonte, n e data, as cores do tema resolvidas e as fontes embutidas), PNG (rasterizado na resolução do tamanho) ou CSV (os dados da tabela); tamanhos Artigo (85 ou 174 mm, 300 ou 600 dpi, tema Prancha), Slide (1.920 px) e Telão (3.840 px, Observatório); guia "Exportar figuras";
  - **modo apresentação** (tecla ++p++, em todas as vistas menos a codificação): esconde o trilho e as barras e aumenta a letra, para projetar; ++esc++ sai; atalho na Ajuda;
  - **`mapa publicar [--destino] [--sem-resumos]`** e `api.publicar()`: o site estático do projeto, com a interface e o contrato, `api: false`, resumos (e o texto das evidências) só com licença Creative Commons, sem e-mails (varredura final), montado numa pasta nova e trocado de uma vez; contrato 1.4 (`Manifesto.publicacao`); guia "Publicar o site";
  - **Metodologia** no site publicado: sem API, a seção Projeto vira a página Metodologia, tirada do manifesto (fontes, recorte, contagens, modelos com o digest, hash do codebook, sementes, durações, licenças e o que a publicação retirou), com os links para as explicações;
  - o GitHub Pages do projeto publica a documentação em `/` e, a partir do *asset* `piloto-publicado.zip` da última *release*, a demo do piloto em `/demo/` (sem o *asset*, sai só a documentação, com um aviso);
  - **oficina no Colab**: o caderno `notebooks/oficina_colab.ipynb` (GPU T4, Ollama com o perfil padrão, *Opinião Pública* de 2020 a 2024, tópicos, geografia, uma amostra de 30 classificada e o painel), gerado por `scripts/gerar_notebook.py` para instalar sempre o *wheel* da *release* da versão, com os comandos rodados no CI; `api.painel()` abre o painel de dentro de um notebook, com o servidor numa *thread*, e no Colab pelo *proxy* do Google (só nesse modo a API aceita pedidos de outro endereço);
  - explicações "Metodologia em uma página" (o método inteiro com os parâmetros e os números do piloto, um rascunho da seção de métodos, e como citar) e "Limitações e vieses" (corpus, resumos, tópicos, geografia, classificação e reprodutibilidade); o guia de instalação ensina a instalar pelo *wheel* da *release*, com a interface já compilada;
  - README bilíngue (português e inglês), com o GIF do painel do piloto (`frontend/scripts/gif-readme.ts`), a demo, a oficina no Colab e a instalação pelo *wheel* da *release*; `.zenodo.json` e o `CITATION.cff` completos para o DOI; o workflow **Release** constrói o *wheel* com a interface, testa-o sem Node, anexa-o à *release*, atualiza a demo e, depois de configurado, publica no PyPI por *trusted publishing*; o passo a passo de uma *release* no guia de desenvolvimento;
  - o teste do tutorial por uma pessoa de fora (um subagente, num clone limpo, sem ajuda) virou correções: "Explorar o exemplo" com dois caminhos de instalação (o *wheel* da *release* ou o código, com a interface compilada como passo, não como dica, e o Node.js 22.18), a página "interface não compilada" diz para reabrir o painel, os tutoriais explicam `uv run` antes das dicas da CLI, o `.env` a partir do `.env.exemplo`, tempos e memória iguais entre os tutoriais, textos de marcos antigos removidos, os comandos sem o marcador `# fora do CI` (a lista do que o teste pula fica no teste), o caderno do Colab instala o `zstd` e volta para `/content`, e o glossário ganha ARI, codificador de referência, *release*, trilho e *wheel*;
  - `contrato/exemplo-publicado/`: o exemplo sintético passado pelas regras do `mapa publicar`, gerado e conferido pelo `scripts/gerar_contrato.py`; os testes e2e ganham o site publicado (sem API, a Metodologia com a publicação, o cartão de um artigo sem licença aberta com os valores da classificação e sem os trechos);

## [0.6.0] - 2026-09-26

O painel completo: quem não usa o terminal cria e configura o projeto e roda o pipeline pela interface, com o progresso ao vivo. As etapas rodam no servidor local, uma por vez, e o acompanhamento sobrevive a um reload ou a uma queda de conexão. Pela interface, o projeto do tutorial (396 artigos da *Opinião Pública*) teve a coleta refeita do cache, 13 tópicos em 5 minutos, 94,4% dos vínculos de autoria ligados a uma instituição e uma amostra de 20 resumos classificada.

### Adicionado

- **Marco M6 (painel completo)**:
  - jobs do painel (`servidor/jobs.py`): as etapas rodam em segundo plano, uma por vez, guardadas no `estado.sqlite` com o progresso como eventos numerados; `POST /api/etapas/{etapa}` (coleta, tópicos, geografia, classificação, com as opções validadas), `GET /api/jobs`, `GET /api/jobs/{id}`, `DELETE /api/jobs/{id}` (cancela na próxima atualização de progresso) e `GET /api/jobs/{id}/eventos`, em Server-Sent Events com retomada pelo `Last-Event-ID`; um job que ficou rodando numa sessão anterior aparece como interrompido; as rotas de escrita conferem `Host` e `Origin` (`servidor/origem.py`);
  - rotas do projeto no painel (`servidor/rotas_projeto.py`): `GET /api/projeto/etapas` (cada etapa pendente, em dia ou desatualizada, com a última execução), `GET /api/modelos` (memória, perfis, modelos instalados e os do projeto), `POST /api/modelos/baixar` (`ollama pull` como job, com o progresso por camada; `Ollama.baixar`), `GET /api/estimativa/classificacao`, `GET`/`PATCH /api/configuracao` e `GET`/`PUT /api/codebook`, gravados sem perder os comentários do YAML (`edicao.py`, com `ruamel.yaml`), validados antes de ir para o disco e recusados enquanto uma etapa roda;
  - a `FonteApi` do painel fala com a API: estado das etapas, rodar e cancelar uma etapa, acompanhá-la ao vivo (`EventSource`, que reconecta sozinho pedindo só o que perdeu; o estado ignora eventos repetidos), modelos, download, estimativa, configuração e codebook;
  - a vista **Projeto** no painel local: as etapas numa linha de metrô (pendente, em dia, incompleta, desatualizada ou rodando, com a última execução; a linha deita ou fica de pé conforme o espaço da vista), rodar cada uma (com piloto de 20 documentos, estimativa ou só a amostra, onde cabe), o job ao vivo com cancelar, que retoma o acompanhamento depois de um reload, a estimativa da classificação, os modelos do projeto com o download do que falta e as últimas execuções; e2e contra uma API falsa cuja primeira conexão SSE cai de propósito;
  - o **assistente do projeto** no painel, em 5 passos (fontes com a busca nas revistas do SciELO, recorte, modelos com o perfil sugerido pela memória e o que falta baixar, codebook num formulário e revisão com o que muda e o que isso refaz); salvar grava o `mapa.yaml` e o `codebook.yaml` sem perder os comentários, e "Salvar e rodar um piloto" coleta 20 documentos; `GET /api/revistas`;
  - documentação do painel: referência da API HTTP gerada do OpenAPI (`docs/referencia/api-http.md`, conferida no CI com as outras referências), tutorial "Seu primeiro mapa pela interface", guia do painel (rodar as etapas e configurar o projeto) e ADR 0013 (jobs, progresso por SSE e edição do projeto);
  - sortear a amostra de validação pelo painel: `POST /api/validacao/amostra` e, na estação Validação da linha de metrô, o tamanho e o botão "Sortear a amostra";

## [0.5.0] - 2026-09-26

A classificação por codebook e a validação: um modelo local lê o resumo de cada artigo e responde às perguntas do codebook, com o trecho do resumo que justifica cada resposta, e a concordância com uma leitura cuidadosa de uma amostra é medida por variável. Na amostra de 200 artigos do piloto, o `qwen3.5:9b` deu JSON válido em 100% das respostas, copiou literalmente 94,8% das evidências, levou 10,8 s por resumo, e o kappa contra um codificador de referência (Claude, às cegas) vai de 0,37 na técnica a 0,93 em "Brasil como caso".

### Adicionado

- **Marco M5 (classificação por codebook e validação)**:
  - o codebook vira o JSON Schema da resposta do modelo, com a evidência (até 200 caracteres) antes do valor em cada variável, e as respostas são validadas contra ele; a mensagem de sistema é fixa (o Ollama reaproveita o prefixo) e traz as regras da evidência curta;
  - conferência da evidência: `literal` (a menos de maiúsculas, espaços, aspas e travessões), `aproximada` (90% dos caracteres casando em blocos com um pedaço do texto de tamanho parecido, ou cada pedaço de um trecho cortado com reticências presente no texto), `ausente` ou `dispensada` (vazia numa resposta "sem informação"), com os *offsets* do trecho no resumo exibido;
  - executor da classificação retomável: cada resposta válida vai para o cache do `estado.sqlite` (chave com o texto, a assinatura do que o modelo lê, o modelo com o digest, a versão do prompt e os parâmetros; mudar só a versão ou os rótulos das categorias reaproveita as respostas), uma nova tentativa quando a resposta foge do codebook ou a evidência não está no texto, guarda de memória entre documentos, concorrência configurável e o modelo descarregado no fim;
  - `mapa classificar [--estimar] [--limite N] [--modelo X]` e `api.classificar()`: a etapa grava `dados/classificacao/` (um resultado por modelo e codebook, para comparar modelos), registra o manifesto com o hash do codebook e aparece no `mapa status`, com aviso quando está incompleta ou é de outro codebook; a view `classificacoes` em `conectar()`; o resultado é regravado a cada 50 documentos novos e numa interrupção, para a rodada longa aparecer enquanto corre; ADR 0011 (proposta);
  - amostra de validação (`mapa validar amostra [--n N] [--refazer]`, `api.amostra_de_validacao()`): sorteada uma vez entre os documentos com resumo, estratificada por tópico (ou ano, ou revista) com alocação proporcional e ao menos um por estrato, guardada no `estado.sqlite` e exportada em `validacao/amostra.jsonl` só com id, título, resumo e idioma; a fila da classificação começa pela amostra, e `mapa classificar --somente-amostra` classifica só ela;
  - codificações (`mapa validar importar ARQUIVO --codificador NOME [--tipo humano|referencia]`, `api.importar_codificacoes()`, `api.codificacoes()`): JSONL validado contra o codebook, com evidência, incerteza e nota por variável; guias "Classificar os resumos" e "Codificar a amostra";
  - na saída de `mapa validar amostra`, os estratos com o rótulo do tópico; na de `mapa classificar`, as categorias com o rótulo do codebook;
  - métricas de concordância (`mapa validar metricas`, `api.validacao()`), por variável e por par de participantes (codificador × modelo, codificador × codificador, modelo × modelo): concordância, kappa de Cohen (igual ao do scikit-learn) com IC 95% por *bootstrap*, PABAK, alfa de Krippendorff nominal (conferido com o exemplo publicado), matriz de confusão e precisão, revocação e F1 por classe; McNemar exato entre modelos contra a mesma referência; divergências com o modelo principal; múltipla escolha medida por categoria; guia "Ler kappa e PABAK";
  - relatório da validação (`mapa validar relatorio`, `api.relatorio_de_validacao()`) em `validacao/`: Markdown com participantes, concordância, P/R/F1 e matrizes por classe, McNemar, evidência literal e as divergências com a evidência do modelo; tabelas LaTeX (`booktabs`, vírgula decimal); `metricas.json`. O `.gitignore` de um projeto novo deixa `validacao/` (os resumos da amostra e as respostas de cada pessoa) fora do git; ADR 0012 (proposta);
  - tutorial "Seu primeiro mapa, parte 4: classificação e validação" (com os comandos rodados no CI) e ADRs 0011 e 0012 aceitos, com a evidência do piloto: 100% de JSON válido na primeira tentativa, 94,8% de evidência literal, 10,8 s por resumo, retomada depois de `kill -9` sem refazer nada, e o kappa `claude-opus` × `qwen3.5:9b` por variável (de 0,37 na técnica a 0,93 em "Brasil como caso");
  - contrato de dados 1.3 (só acréscimos): `codebook.json` sempre; `classificacoes.json` com cobertura, classificação parcial, JSON válido e evidência por variável; colunas `cls` em `documentos.json` (múltipla escolha como combinações) e as evidências nos detalhes, com o campo onde o trecho está e o status `dispensada`; `validacao.json` com os participantes e o tipo de cada um, P/R/F1 por classe, McNemar entre modelos e as divergências só de codificadores de referência (as de pessoas ficam fora do contrato); `hash_codebook`, classificados e validados no manifesto; a importação de codificações e a rodada da classificação atualizam o painel;
  - a vista **Classificação** do painel, no filtro cruzado: uma variável do codebook por vez, com o selo de kappa da validação (hachura abaixo de 0,6; borda tracejada contra um codificador de referência), barras 100% por ano e o cruzamento com macrotemas, tópicos ou revistas; uma célula lista os documentos com a evidência marcada no resumo; a variável e o cruzamento vão na URL (`variavel=`, `cruzar=`); guia "Ler a classificação";
  - rótulos com acento nas categorias do codebook de exemplo (o `rotulo`, só de exibição);
  - a vista **Codificar** (Validação › Codificar a amostra, só no painel local): uma ficha por vez, cega, com o título, o resumo e o codebook; tudo pelo teclado (`1`–`9`, `Tab`, `Enter`, `←`/`→`, `S` incerto, `N` nota, `E` evidência do trecho selecionado, `D` definições, `?` ajuda); gravação automática com fila de pendências no navegador, retomada na primeira ficha incompleta; e2e com 20 fichas pelo teclado que sobrevivem a um reload, contra uma API falsa que espelha a do Python;
  - o cartão do documento no Mapa marca no resumo as evidências da classificação e lista as respostas do modelo; passar o mouse (ou clicar) numa resposta acende só o trecho dela;
  - a vista **Validação › Concordância**: os participantes com o tipo (aviso quando há codificador de referência), o par escolhido com concordância, kappa (barra com hachura abaixo de 0,6) e IC 95%, PABAK e alfa por variável; a variável escolhida com a matriz de confusão, P/R/F1 por categoria e as divergências com a evidência do modelo; McNemar entre modelos e evidência literal. No painel local, as métricas vêm da API, calculadas na hora;
  - API local da codificação no painel: `GET /api/validacao/fila` (a amostra embaralhada por codificador, cega, com o codebook e as respostas já dadas), `PUT /api/validacao/codificacoes/{doc}` (gravação parcial ou completa; a escrita confere também o `Origin`) e `GET /api/validacao/metricas` (concordância na hora, com as divergências de todos os codificadores); toda a API do painel responde só a um `Host` local;

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

[Não lançado]: https://github.com/felipelmc/mapa-da-ciencia/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/felipelmc/mapa-da-ciencia/compare/v1.0.1...v2.0.0
[1.0.1]: https://github.com/felipelmc/mapa-da-ciencia/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/felipelmc/mapa-da-ciencia/compare/v0.7.0...v1.0.0
[0.7.0]: https://github.com/felipelmc/mapa-da-ciencia/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/felipelmc/mapa-da-ciencia/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/felipelmc/mapa-da-ciencia/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/felipelmc/mapa-da-ciencia/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/felipelmc/mapa-da-ciencia/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/felipelmc/mapa-da-ciencia/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/felipelmc/mapa-da-ciencia/releases/tag/v0.1.0
