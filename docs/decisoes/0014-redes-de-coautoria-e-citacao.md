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
2. **Pesos fracionários** (`1/(n − 1)` por par em cada artigo com `n` autores distintos), a mesma lógica da contagem
   fracionária da geografia (ADR 0008): a força de uma pessoa é o número de artigos com coautor, e os artigos com
   muitos autores não dominam a rede.
3. **Comunidades por Louvain** (networkx, resolução 1, semente 7), rotuladas pelos dois tópicos mais frequentes dos
   artigos delas, **sem nome de pessoa**. Dependência nova: `networkx` (BSD-3, Python puro, cerca de 2 MB, importado
   só dentro das funções das redes). igraph e graph-tool ficaram de fora pela licença e pelos binários.
4. **Desenho no Python, fixo:** `spring_layout` por componente, com semente, empacotado em [-1, 1]. O navegador não
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
  (o de um coautor). E a união por ORCID juntava 8 autorias de nomes incompatíveis ("Marcelo Kunrath Silva" com o
  ORCID de "Matheus Mazzilli Pereira"), com arestas falsas; em 2 delas a ArticleMeta e o OpenAlex discordavam do
  ORCID, e o código preferia o da ArticleMeta.
- **Manter homônimos separados errava quase sempre.** Dos 32 pares de homônimos exatos que ficavam separados, 30
  eram a mesma pessoa (93,8%, IC95% de Wilson 79,9%–98,3%); numa amostra de 30 dos 81 pares de grafias variantes
  ("Marjorie Marona" e "Marjorie Corrêa Marona"), 12 eram (40%, IC95% 24,6%–57,7%). Já as fusões por nome não
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
   "Ana Paula Silva".

Medido com os mesmos julgamentos (os casos casados pelas autorias, na cópia do piloto): dos 30 pares de homônimos que
eram a mesma pessoa, 25 agora se juntam, e os 2 que eram pessoas diferentes continuam separados; das variantes da
amostra, 7 dos 12 se juntam, nenhuma das 18 distintas; os 8 ids repartidos e as 8 autorias com ORCID trocado estão
corrigidos, e a varredura de fusões suspeitas (nomes incompatíveis na mesma pessoa) acha 0 casos, contra 8 antes. Das
36 fusões por nome, 35 continuam; a outra virou um par de homônimos na revisão, porque a autoria ganhou um id do
OpenAlex com o alinhamento novo. Os homônimos sem coautor nem instituição em comum (5 dos 30, como "Celso Amorim")
continuam na revisão: um nome igual sozinho não basta, porque os dois pares distintos também eram nomes iguais.

## Números do piloto

(Preenchidos com a rodada do piloto: pessoas, com coautor, arestas, componentes e o maior, comunidades, instituições,
citações internas, cobertura das referências e o cânone.)

## Consequências

- `mapa redes` é uma etapa nova (`ETAPAS`), rápida e sem modelo.
- A coleta faz cerca de 1 requisição a cada 100 artigos a mais, só na primeira vez.
- O cânone é enviesado para obras indexadas no OpenAlex (ver "Limitações e vieses").
