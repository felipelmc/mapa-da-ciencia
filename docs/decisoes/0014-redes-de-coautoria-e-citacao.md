# 0014 · Redes de coautoria e citação

- **Estado:** aceita
- **Data:** 2026-09-28
- **Marco:** v2.0

## Contexto

A versão 1 deixou a vista Redes reservada ("na versão 2"). O cache da coleta já tinha o necessário para a
coautoria: os ids de autor e os ORCIDs do OpenAlex, que eram descartados na normalização, e as afiliações casadas pela
geografia. Para as citações, as referências da ArticleMeta estão no cache bruto, mas quase nunca trazem DOI (no
piloto, 2,2% no campo próprio, `v237`, e 5,3% em qualquer campo; de 0,3% a 17% conforme a revista); o OpenAlex tem
as referências já resolvidas (`referenced_works`), a 1 crédito por 100 obras.

## Decisões

1. **Identidade das pessoas por *union-find*, em ordem de confiança:** o ORCID conferido pelo nome; o mesmo id do
   OpenAlex ou o mesmo ORCID; a autoria sem id na única pessoa de mesmo nome; homônimos e grafias variantes com um
   coautor ou uma instituição em comum. O resto vai para `mapa redes --revisar` e para o `pessoas.yaml`, cujo
   `nao_fundir` também desfaz as fusões automáticas. Alternativa descartada: casar nomes por semelhança sem evidência
   (fundiria homônimos comuns na área, como "Silva"). O raciocínio e as medidas estão em "Identidade: o que o piloto
   mostrou", abaixo.
2. **Pesos fracionários** (`1/(n − 1)` por par em cada artigo com `n` autores distintos): cada autor reparte 1 entre
   os coautores de cada artigo, e o artigo soma `n/2`. A ideia é a da contagem fracionária da geografia (ADR 0008),
   mas a unidade é o autor, e não o artigo: a força de uma pessoa é o número de artigos com coautor, e os artigos com
   muitos autores não dominam a rede. Os pesos são somados como frações exatas (arredondá-los mudava as comunidades).
   Na rede de instituições, a dupla afiliação de um autor só também liga as duas instituições: a rede é de
   instituições que dividem artigos (cerca de um décimo do peso vem desses artigos, no piloto).
3. **Comunidades por Louvain** (networkx, resolução 1, semente 7), rotuladas pelos dois tópicos mais frequentes dos
   artigos delas, **sem nome de pessoa**. Dependência nova: `networkx` (BSD-3, Python puro, cerca de 2 MB, importado
   só dentro das funções das redes). igraph e graph-tool ficaram de fora pela licença e pelos binários.
4. **Desenho no Python, fixo** (por comunidades desde a 2.1.0, veja o adendo): `spring_layout` por componente, com
   semente, empacotado em [-1, 1]. O navegador não
   recalcula o desenho: filtrar o recorte esmaece nós e arestas, e o mapa mental do leitor não muda a cada filtro.
   O exemplo sintético do contrato usa um desenho determinístico mais simples, porque o `spring_layout` varia na
   quarta casa decimal entre plataformas, e o exemplo é conferido byte a byte no CI.
5. **Citações pelo OpenAlex** (`referenced_works`, em lotes de 100), e os metadados das 500 obras de fora mais
   citadas, das quais o cânone guarda as 200 primeiras. A coleta guarda as duas tabelas, e a segunda coleta faz 0
   requisições. As referências da ArticleMeta (autores, título e ano, lidas do cache) entram na cobertura por
   referência e na **conferência da autoria do cânone**: o OpenAlex casa muitas referências a livros com o registro
   de uma resenha, com o resenhista como autor (11 das 60 primeiras obras do piloto, como "Theory of International
   Politics" atribuída a Joseph Frankel, 1980). Com três ou mais referências de mesmo título, o autor que as
   referências não citam sai, e o autor e o ano vêm delas; registros da mesma obra (mesmo primeiro sobrenome, título
   igual, sem o subtítulo ou quase igual) somam. Alternativa descartada: tirar do cânone os registros de resenha (o
   livro sumiria, e ele é o mais citado). O casamento aproximado das referências da ArticleMeta por título, para as
   obras que o OpenAlex não resolve, fica para depois.
6. **Contrato 1.5:** `redes.json` traz as pessoas (com id publicado; **nenhum ORCID**), as autorias por
   índice de documento (o navegador recalcula as arestas dentro do recorte, sem mandar uma lista de documentos por
   aresta), as instituições com o desenho, as comunidades, as métricas e as séries da colaboração. `citacoes.json`
   traz as citações internas, o cânone com os citantes, o fluxo entre macrotemas e a cobertura.
7. **Privacidade:** os nomes dos autores já eram públicos no painel (são metadados bibliográficos dos artigos). O
   site não publica ORCIDs nem e-mails, e as histórias da abertura não fazem rankings de pessoas. O id publicado é
   um HMAC-SHA256 do id interno com um segredo do projeto guardado no `estado.sqlite`, e não um *hash* sem chave: a
   revisão mostrou que o SHA-256 truncado de `orcid:…` devolvia 58 ORCIDs do piloto em 26 s de força bruta. Um id
   sequencial num mapa interno também serviria, mas mudaria com a ordem das pessoas; o HMAC só muda quando a
   identidade da pessoa muda (ou o segredo se perde). O `mapa publicar` procura ORCIDs (com o dígito verificador),
   além de e-mails, em todos os JSON do site.

## Identidade: o que o piloto mostrou

A primeira versão confiava no ORCID acima de tudo: dois ORCIDs diferentes nunca se juntavam ("quando o OpenAlex funde
homônimos, o ORCID separa"), e dois homônimos só se juntavam com um coautor em comum. A auditoria da identidade
(todos os casos julgados à mão, com coautores, instituições, revistas e títulos de cada lado) mostrou o contrário do
que a regra supunha:

- **O ORCID errava para os dois lados.** Os 8 ids do OpenAlex que o conflito de ORCIDs repartia em duas pessoas não
  eram homônimos fundidos: 5 eram a mesma pessoa com dois registros no ORCID, e 3 vinham de um ORCID trocado na fonte
  (o de um coautor). E a união por ORCID juntava 8 autorias de nomes incompatíveis (um autor com o ORCID de um
  coautor), com arestas falsas; em 2 delas a ArticleMeta e o OpenAlex discordavam do
  ORCID, e o código preferia o da ArticleMeta.
- **Manter homônimos separados errava quase sempre.** Dos 32 pares de homônimos exatos que ficavam separados, 30
  eram a mesma pessoa (93,8%, IC95% de Wilson 79,9%–98,3%); numa amostra de 30 dos 81 pares de grafias variantes
  (como "Maria Souza" e "Maria Lima Souza"), 12 eram (40%, IC95% 24,6%–57,7%). Já as fusões por nome não
  erraram (0 de 36). O erro dominante é a **fragmentação**: o OpenAlex dá vários ids à mesma pessoa.
- **A instituição separa bem.** Juntar os homônimos com uma instituição casada em comum acertaria 22 dos 30 sem
  nenhuma fusão errada; nas variantes da amostra, 7 dos 12, também sem fusão errada.

Daí as regras de agora:

1. o ORCID é conferido pelo nome antes de valer: se a ArticleMeta e o OpenAlex discordam, nenhum vale; um ORCID em
   autorias de nomes incompatíveis (nenhuma parte do nome depois da primeira em comum) fica só com o maior grupo de
   nomes compatíveis;
2. o mesmo id do OpenAlex junta sempre, e o mesmo ORCID também, mesmo que a pessoa fique com dois ORCIDs; essas
   pessoas vão para a revisão. Assim **nenhum id do OpenAlex fica em duas pessoas**, salvo um `nao_fundir` explícito
   no `pessoas.yaml`;
3. a autoria sem id nem ORCID entra na única pessoa de mesmo nome, como antes;
4. homônimos e grafias variantes (o mesmo primeiro nome, as partes de um nome contidas nas do outro) se juntam com um
   coautor **ou uma instituição** em comum (as do OpenAlex, com a linhagem, e as casadas pela geografia), desde que
   todos os nomes de um grupo sejam comparáveis com todos os do outro: "Ana Silva" não emenda "Ana Maria Silva" com
   "Ana Paula Silva". Uma grafia curta não barra a união quando um nome por extenso (sem iniciais) contém todos os
   outros: "João Pedro Almeida Costa" junta "João Pedro Almeida" e "João Costa".

Medido com os mesmos julgamentos (os casos casados pelas autorias, na cópia do piloto): dos 30 pares de homônimos que
eram a mesma pessoa, 25 agora se juntam, e os 2 que eram pessoas diferentes continuam separados; das variantes da
amostra, 7 dos 12 se juntam, nenhuma das 18 distintas; os 8 ids repartidos e as 8 autorias com ORCID trocado estão
corrigidos, e a varredura de fusões suspeitas (nomes incompatíveis na mesma pessoa) acha 0 casos, contra 8 antes
(fora as grafias curtas juntadas de propósito por um nome por extenso: 2 no piloto). Das 36 fusões por nome, 35 continuam; a outra virou um par de
homônimos na revisão, porque a autoria ganhou um id do OpenAlex com o alinhamento novo. Os homônimos sem coautor nem
instituição em comum (5 dos 30) continuam na revisão: um nome igual sozinho não basta, porque os
dois pares distintos também eram nomes iguais.

## Números do piloto

Rodada de 28/09/2026 (10 revistas, 4.275 documentos, 2010–2025), com as referências do OpenAlex coletadas uma vez
(48 requisições; as coletas seguintes vêm do cache).

| | |
|---|---|
| Pessoas | 4.190 (3.021 com algum coautor) |
| Rede de coautoria | 3.837 arestas, 654 componentes; o maior tem 1.004 pessoas (33%); 38 comunidades numeradas, modularidade 0,96 |
| Rede de instituições | 462 instituições com coautoria entre si, 1.123 arestas, 27 componentes (o maior com 406, 88%) |
| Identidade | 17 pessoas com dois ORCIDs (a mesma pessoa, conferido à mão), 5 ORCIDs de outro nome retirados, 69 pares para revisar |
| Citações dentro do corpus | 4.923 (nenhuma anacrônica; 7 autorreferências) |
| Cobertura | 3.976 dos 4.275 documentos têm referências no OpenAlex; nos 4.171 documentos casados, a ArticleMeta lista 201.288 referências e o OpenAlex resolve 105.602 (52% no total; mediana de 50% por documento) |
| Cânone | 200 obras de fora do corpus, citadas por 1.790 documentos; 55 chegaram por um registro de resenha e 62 tiveram a autoria conferida nas referências |

Uma auditoria metodológica independente recalculou esses números do zero, com scripts próprios, e julgou à mão as
fusões e separações de pessoas: nenhuma fusão errada em 80 pessoas julgadas (IC 95% de 0 a 4,6%); dos 9 pares de
homônimos que ficaram separados, 7 são a mesma pessoa, e vão para a revisão (`mapa redes --revisar`).

## Consequências

- `mapa redes` é uma etapa nova (`ETAPAS`), rápida e sem modelo.
- A coleta faz cerca de 1 requisição a cada 100 artigos a mais, só na primeira vez.
- O cânone é enviesado para obras indexadas no OpenAlex (ver "Limitações e vieses").

## Adendo (2.1.0): o desenho por comunidades

Na 2.0.0, o maior componente saía de um `spring_layout` só, com os parâmetros padrão. No piloto, isso fazia um núcleo
denso: na área do grafo de uma tela de 1920 × 1080 (1206 × 838 px, com a interface da 2.1.0), 58% das pessoas
desenhadas encostavam em outra, e o maior componente ocupava só 27% do desenho, com os grupos menores numa faixa
embaixo. O autor pediu grafos "mais espaçados".

Comparamos cinco desenhos no piloto, com métricas na vista inicial (os raios da vista, os componentes de 2 e 3 nós
escondidos, como por padrão): o atual; o `spring_layout` com mais distância e mais iterações; o `forceatlas2_layout`
do networkx, com e sem o modo linlog; e um desenho por comunidades, em duas versões (com os componentes menores
embaixo, ou à direita do maior). Um avaliador independente viu os seis candidatos sem saber qual era qual e escolheu
pelas imagens e pelas métricas o mesmo que elas apontavam, a segunda versão do desenho por comunidades:

- **O maior componente por comunidades.** Cada comunidade do Louvain (a partição inteira) é desenhada à parte, num
  disco. Os discos são arrumados por um `spring_layout` do grafo das comunidades (o peso entre duas é a soma das
  arestas entre elas), e esse arranjo é ampliado até nenhum disco encostar noutro e depois contraído aos poucos,
  desfazendo as sobreposições a cada passo.
- **Os componentes menores à direita do maior**, na altura dele, e depois embaixo, com a largura que deixa o desenho
  visível perto de 1,6 : 1, a proporção de uma tela larga. As duplas e os trios ficam embaixo de tudo.
- **Nenhum nó encostado noutro numa área de 1250 × 840 px** (a tela de referência, perto da área do grafo numa tela de
  1920 × 1080): um relaxamento dentro de cada componente afasta os nós pelos raios que a vista desenha
  (`raios_na_vista`). O raio vai de 1 documento (o mínimo) ao nó com mais documentos (o máximo); na 2.0.0, a fórmula
  levava 0 documento ao mínimo, e o menor nó saía bem maior que ele.

Medido no piloto com uma reconstrução fiel da vista (os raios de cada versão, o enquadramento da vista e os componentes
de 4 nós ou mais), por um auditor independente e conferido de novo depois do ajuste do arranjo dos discos:

| Piloto, vista inicial | Coautoria, 2.0.0 | Coautoria, 2.1.0 | Instituições, 2.0.0 | Instituições, 2.1.0 |
|---|---|---|---|---|
| Nós encostados em outro, tela de 1920 × 1080 (1206 × 838 px) | 58% | 0% | 25% | 0% |
| Nós encostados em outro, notebook de 1440 × 900 (726 × 547 px) | 84% | 63% | 67% | 18% |
| Idem, com o grafo em tela cheia (1032 × 868 px; a 2.0.0 não tinha tela cheia) | — | 3% | — | 0% |
| Distância ao vizinho mais próximo (mediana, 1206 × 838) | 5,8 px | 7,7 px | 10,0 px | 17,4 px |
| Área do desenho ocupada pelo maior componente | 27% | 61% | 50% | 87% |
| O vizinho mais próximo é um parceiro (coautor, instituição parceira) | 55% | 75% | 14% | 34% |
| Dos 5 vizinhos mais próximos, os da mesma comunidade | 62% | 98% | 35% | 98% |

Numa tela pequena, os nós ainda se tocam; em tela cheia, quase nenhum, e o zoom separa o resto. A última linha é alta em boa parte
por construção (cada comunidade tem um disco próprio), e **o vão entre dois grupos não é uma medida**, como a distância
em geral (veja "Como ler as redes"). A proximidade entre as comunidades acompanha a ligação entre elas só em parte:
entre as comunidades de 8 nós ou mais, a correlação de Spearman entre o peso das arestas que as ligam e a distância
entre elas é de −0,54 na coautoria (−0,28 na 2.0.0) e de −0,19 nas instituições (−0,46 na 2.0.0), e a comunidade mais
ligada a cada uma está entre as três mais próximas dela em 40% e 78% dos casos (16% e 38% seriam o acaso; 25% e 67% na
2.0.0). Nas instituições, 45% das arestas do maior componente ligam comunidades diferentes: o desenho as esmaece (as
arestas entre comunidades ficam mais fracas que as de dentro), e passar o mouse num nó as acende.

O desenho leva cerca de 1 s no piloto e não depende do hash das strings do Python (`PYTHONHASHSEED`): três rodadas de
`mapa redes`, com sementes diferentes, deram arquivos idênticos byte a byte. Só as
coordenadas mudaram: pessoas, comunidades, métricas, arestas, citações e o cânone são os mesmos da 2.0.0. O
relaxamento garante a folga até o tamanho do piloto; numa rede bem maior, os nós voltam a se tocar na tela de
referência (num corpus sintético, 0,4% com 3 mil nós desenhados, 82% com 8 mil), e o zoom continua sendo o caminho.
