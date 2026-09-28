# 0014 · Redes de coautoria e citação

- **Estado:** aceita
- **Data:** 2026-09-28
- **Marco:** v2.0

## Contexto

A versão 1 deixou a vista Redes reservada ("na versão 2"). O cache da coleta já tinha o necessário para a
coautoria: os ids de autor e os ORCIDs do OpenAlex, que eram descartados na normalização, e as afiliações casadas pela
geografia. Para as citações, as referências da ArticleMeta estão no cache bruto, mas só 3% a 9% delas trazem DOI; o
OpenAlex tem as referências já resolvidas (`referenced_works`), a 1 crédito por 100 obras.

## Decisões

1. **Identidade das pessoas por *union-find*, em ordem de confiança:** mesmo id do OpenAlex ou mesmo ORCID (nunca
   juntando dois ORCIDs diferentes); autoria sem id na única pessoa de mesmo nome; homônimos com coautor em comum. O
   resto dos homônimos vai para `mapa redes --revisar` e para o `pessoas.yaml`. Alternativa descartada: casar nomes
   por semelhança (fundiria homônimos comuns na área, como "Silva").
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
   citadas (o cânone). A coleta guarda as duas tabelas, e a segunda coleta faz 0 requisições. As referências da
   ArticleMeta entram só na cobertura; o casamento aproximado por título fica para depois.
6. **Contrato 1.5:** `redes.json` traz as pessoas (com id publicado; **nenhum ORCID**), as autorias por
   índice de documento (o navegador recalcula as arestas dentro do recorte, sem mandar uma lista de documentos por
   aresta), as instituições com o desenho, as comunidades, as métricas e as séries da colaboração. `citacoes.json`
   traz as citações internas, o cânone com os citantes, o fluxo entre macrotemas e a cobertura.
7. **Privacidade:** os nomes dos autores já eram públicos no painel (são metadados bibliográficos dos artigos). O
   site não publica ORCIDs nem e-mails, e as histórias da abertura não fazem rankings de pessoas. O id publicado é
   um HMAC-SHA256 do id interno com um segredo do projeto guardado no `estado.sqlite`, e não um *hash* sem chave: a
   revisão mostrou que o SHA-256 truncado de `orcid:…` devolvia 58 ORCIDs do piloto em 26 s de força bruta. Um id
   sequencial num mapa interno também serviria, mas mudaria com a ordem das pessoas; o HMAC só muda quando a
   identidade da pessoa muda (ou o segredo se perde).

## Números do piloto

(Preenchidos com a rodada do piloto: pessoas, com coautor, arestas, componentes e o maior, comunidades, instituições,
citações internas, cobertura das referências e o cânone.)

## Consequências

- `mapa redes` é uma etapa nova (`ETAPAS`), rápida e sem modelo.
- A coleta faz cerca de 1 requisição a cada 100 artigos a mais, só na primeira vez.
- O cânone é enviesado para obras indexadas no OpenAlex (ver "Limitações e vieses").
