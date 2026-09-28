# Redes de coautoria e citação

As redes mostram **quem escreve com quem** (pessoas e instituições), **de onde para onde** vai a colaboração entre
estados, e **quem cita quem**: dentro do corpus e fora dele (o cânone). Elas não usam modelo de linguagem: saem dos
autores, das afiliações e das referências que a coleta já traz.

## Quem é quem

Um autor aparece em vários artigos com grafias diferentes, e dois autores diferentes podem ter o mesmo nome. No
piloto, o erro mais comum é o primeiro: o OpenAlex dá vários ids à mesma pessoa, e a rede a mostraria em pedaços. A
etapa junta as autorias em pessoas, em ordem de confiança:

1. o **ORCID é conferido pelo nome**: se a ArticleMeta e o OpenAlex dão ORCIDs diferentes à mesma autoria, nenhum
   vale; e um ORCID que aparece com nomes incompatíveis (um ORCID trocado na fonte, o de um coautor) fica só com o
   nome dono dele;
2. o **mesmo id de autor no OpenAlex** e o **mesmo ORCID** são a mesma pessoa, ainda que ela acabe com dois ORCIDs
   (no piloto, isso era a mesma pessoa com dois registros no ORCID); um id do OpenAlex nunca fica em duas pessoas;
3. uma autoria sem id nem ORCID entra na pessoa de mesmo nome, **se houver só uma**;
4. dois homônimos, ou duas grafias variantes do mesmo nome ("Marjorie Marona" e "Marjorie Corrêa Marona"), se juntam
   se tiverem **um coautor ou uma instituição em comum**.

O que sobra fica separado e aparece em `mapa redes --revisar`, com as evidências de cada lado (documentos, anos,
revistas, instituições, coautores e um título) e um bloco para o `pessoas.yaml` do projeto: `fundir`, `nao_fundir`
(que também desfaz uma fusão automática) e `nomes`. As taxas medidas no piloto estão no
[ADR 0014](../decisoes/0014-redes-de-coautoria-e-citacao.md#identidade-o-que-o-piloto-mostrou). O site não publica ORCIDs nem ids do OpenAlex: cada pessoa tem um id
curto, um HMAC com o segredo do projeto (ver [Privacidade e licenças](privacidade-e-licencas.md)).

## Pesos fracionários

Na coautoria, cada **autor** vale 1 em cada artigo, e reparte esse 1 entre os `n − 1` coautores: cada par recebe
`1/(n − 1)`. Um artigo de `n` autores soma, então, `n/2` na rede (e não 1, como na contagem fracionária da
geografia, em que o artigo inteiro vale 1): a ideia é a mesma, repartir para que artigos com muitos autores não
dominem, mas a unidade é o autor. Assim, a **força** de uma pessoa na rede (a soma dos pesos das arestas dela) é o
número de artigos em que ela teve coautor, e um artigo com dez autores (45 pares de peso 1/9) não pesa mais para
cada um do que um com dois. A colaboração entre **instituições** segue a mesma regra, com as instituições
identificadas distintas do artigo; a colaboração entre **estados** também, com as UFs distintas e `EX` (o
**Exterior**, na vista) para qualquer vínculo fora do Brasil.

Na rede de instituições, duas instituições ficam ligadas quando aparecem juntas nas afiliações de um artigo, **mesmo
que seja um autor só com duas afiliações**. A escolha é deliberada: uma pessoa com vínculo nas duas liga as
instituições tanto quanto dois coautores. No piloto, esses artigos de um autor só são cerca de um décimo dos que
têm duas ou mais instituições (e do peso da rede), e por eles a série "documentos com mais de uma instituição" pode
passar a de coautoria em alguns anos. A rede mede instituições que dividem artigos, e não só equipes diferentes
trabalhando juntas.

## Comunidades e desenho

As comunidades são grupos de nós mais ligados entre si do que com o resto, achados pelo algoritmo de **Louvain**
(com semente fixa, para dar sempre o mesmo resultado). Só as grandes ganham número (8 pessoas ou 5 instituições, no
mínimo). O rótulo de cada comunidade são os **dois tópicos mais frequentes** nos artigos dela (no empate, o de menor
id): uma comunidade não recebe nome de pessoa. Comunidades são um agrupamento automático, e não grupos de pesquisa
declarados.

O agregado das comunidades é estável, mas a **composição** de cada uma não é tanto: no piloto, trocar a semente do
Louvain (1 a 20) mantinha o número de comunidades (37 a 41) e a modularidade (0,958 a 0,959), mas algumas das dez
maiores trocavam de 30% a 45% dos membros, e usar os pesos arredondados a seis casas, em vez dos exatos, mudava a
comunidade de um terço das pessoas. Por isso os pesos são somados como frações exatas, e a semente é fixa. Os dois
tópicos do rótulo cobrem, em geral, de um quinto a metade dos artigos de uma comunidade de coautoria; nas de
instituições, bem menos (as instituições grandes publicam de tudo). E a maioria das pessoas com coautor (59% no
piloto) está em grupos menores do que o mínimo, fora das comunidades numeradas.

O desenho posiciona cada componente conectado à parte (`spring_layout`, semente 7), com tamanho proporcional à raiz
do número de nós. O maior componente fica em cima, e os outros numa faixa embaixo, menores, do maior para o menor.
**A distância no desenho não é uma medida**: nós perto costumam estar no mesmo grupo, mas muitas vezes não estão
ligados (na primeira versão do desenho do piloto, só um terço das pessoas tinha como coautor o vizinho mais próximo),
e dois nós longe podem estar a um passo um do outro.

## Citações e cânone

As referências vêm do OpenAlex (`referenced_works`), em lotes de 100 obras por requisição. Com elas:

- **citações internas**: um artigo do corpus citando outro. Uma citação a um artigo publicado mais de um ano depois
  (um erro de casamento no OpenAlex) é descartada e contada;
- **fluxos**: quantas citações internas vão de um macrotema a outro;
- **cânone**: as obras de fora do corpus citadas pelo maior número de artigos, com os metadados buscados no OpenAlex
  (a coleta busca os das 500 mais citadas; o cânone guarda as 200 primeiras). O OpenAlex casa muitas referências a
  livros com o registro de uma **resenha** do livro, com o resenhista como primeiro autor e o ano da resenha: no
  piloto, "Theory of International Politics" saía como de Joseph Frankel (1980), e não de Waltz (1979). Por isso a
  autoria e o ano de cada obra são conferidos nas referências que a ArticleMeta lista nos artigos que a citam (o que
  os próprios autores escreveram), quando há pelo menos três delas com o mesmo título (ou com o título sem o
  subtítulo) e elas somam ao menos um quinto dos artigos que citam a obra. Aí os autores são os sobrenomes que metade
  dessas referências traz, na ordem delas (King, Keohane e Verba), mais os outros do OpenAlex; o autor do OpenAlex
  que elas não citam (o resenhista) sai. O ano é o que a maioria das referências dá (a edição original de um livro
  que o OpenAlex casou com um capítulo de coletânea de 2015, ou com uma reimpressão); num registro de resenha, ou com
  um ano que as referências quase não citam, é o mais citado, ou a primeira edição que várias citam. Registros da
  mesma obra somam quando têm o mesmo primeiro sobrenome e o mesmo título: igual, sem o subtítulo, ou quase igual
  (92% de semelhança, como "…Democratic Government" e "…Democratic Governance"). A numeração de capítulo sai do
  título ("66. Civil Society…"), e registros com título genérico ("Resumos", "Introdução") ficam fora. A obra que o
  OpenAlex usa no lugar de registros apagados (`W4285719527`) não conta.

## Limitações

- **O cânone e as citações se apoiam em cerca de metade das referências.** Nos artigos casados com o OpenAlex que
  listam referências na ArticleMeta (também os que não têm nenhuma resolvida), o OpenAlex resolve a mediana de 50%
  delas por artigo (no piloto, 52% no total, e menos nos anos mais recentes); a nota do cânone traz o número do
  projeto. Ficam de fora sobretudo livros, capítulos, teses e textos em português
  sem DOI. As referências da ArticleMeta quase nunca trazem DOI (2,2% no campo próprio e 5,3% em qualquer campo, no
  piloto; de 0,3% a 17% conforme a revista), e o casamento aproximado por título fica para uma versão futura.
- **Livros entram muitas vezes por uma resenha.** A conferência nas referências corrige o autor e o ano quando há
  pelo menos três referências com o mesmo título, somando um quinto ou mais dos artigos que citam a obra; com menos,
  o registro fica como o OpenAlex o deu (autor e ano podem ser os da resenha), e a tabela do cânone mostra quando o
  registro é uma resenha. No piloto, mais de um quarto das 200 obras chegou por uma resenha.
- A identidade das pessoas erra mais por **fragmentação** do que por fusão: homônimos e grafias variantes sem
  coautor nem instituição em comum ficam separados (5 dos 30 pares de homônimos do piloto que eram a mesma pessoa),
  e a revisão manual corrige. Um id do OpenAlex que junte duas pessoas de mesmo nome só se separa no `pessoas.yaml`.
- As afiliações não identificadas ficam fora da rede de instituições; os artigos sem afiliação, fora da rede de
  estados.
- A rede é do corpus: uma pessoa que escreve com colegas de fora dele aparece com menos coautores do que tem.

As decisões e os números do piloto estão no [ADR 0014](../decisoes/0014-redes-de-coautoria-e-citacao.md).
