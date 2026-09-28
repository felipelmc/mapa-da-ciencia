# Redes de coautoria e citação

As redes mostram **quem escreve com quem** (pessoas e instituições), **de onde para onde** vai a colaboração entre
estados, e **quem cita quem**: dentro do corpus e fora dele (o cânone). Elas não usam modelo de linguagem: saem dos
autores, das afiliações e das referências que a coleta já traz.

## Quem é quem

Um autor aparece em vários artigos com grafias diferentes, e dois autores diferentes podem ter o mesmo nome. A etapa
junta as autorias em pessoas, em ordem de confiança:

1. o **mesmo id de autor no OpenAlex** ou o **mesmo ORCID** (da ArticleMeta ou do OpenAlex) é a mesma pessoa, mas
   dois ORCIDs diferentes nunca se juntam: quando o OpenAlex fundiu homônimos, o ORCID separa;
2. uma autoria sem id nem ORCID entra na pessoa de mesmo nome, **se houver só uma**;
3. dois homônimos sem ORCIDs em conflito se juntam se tiverem **um coautor em comum**.

O que sobra de homônimos fica separado e aparece em `mapa redes --revisar`, com um bloco pronto para o `pessoas.yaml`
do projeto (`fundir`, `nao_fundir` e `nomes`). O site não publica ORCIDs nem ids do OpenAlex: cada pessoa tem um id
curto, um HMAC com o segredo do projeto (ver [Privacidade e licenças](privacidade-e-licencas.md)).

## Pesos fracionários

Como na geografia, cada documento vale 1. Num artigo com `n` autores, cada um reparte o seu 1 entre os `n − 1`
coautores: cada par recebe `1/(n − 1)`. Assim, a **força** de uma pessoa na rede (a soma dos pesos das arestas dela)
é o número de artigos em que ela teve coautor, e um artigo com dez autores não pesa dez vezes mais que um com dois. A
colaboração entre **instituições** segue a mesma regra, com as instituições identificadas distintas do artigo; a
colaboração entre **estados** também, com as UFs distintas e `EX` para qualquer vínculo no exterior.

## Comunidades e desenho

As comunidades são grupos de nós mais ligados entre si do que com o resto, achados pelo algoritmo de **Louvain**
(com semente fixa, para dar sempre o mesmo resultado). Só as grandes ganham número (8 pessoas ou 5 instituições, no
mínimo). O rótulo de cada comunidade são os **dois tópicos mais frequentes** nos artigos dela: uma comunidade não
recebe nome de pessoa. Comunidades são um agrupamento automático, e não grupos de pesquisa declarados.

O desenho posiciona cada componente conectado à parte (`spring_layout`, semente 7), com tamanho proporcional ao
número de nós, e empacota os componentes do maior para o menor. **A distância no desenho não é uma medida**: dois nós
perto estão ligados, mas dois nós longe podem estar a um passo um do outro.

## Citações e cânone

As referências vêm do OpenAlex (`referenced_works`), em lotes de 100 obras por requisição. Com elas:

- **citações internas**: um artigo do corpus citando outro. Uma citação a um artigo publicado mais de um ano depois
  (um erro de casamento no OpenAlex) é descartada e contada;
- **fluxos**: quantas citações internas vão de um macrotema a outro;
- **cânone**: as obras de fora do corpus citadas pelo maior número de artigos, com os metadados buscados no OpenAlex.
  Edições da mesma obra (mesmo título normalizado e mesmo primeiro sobrenome) somam.

## Limitações

- **O cânone é enviesado para o que o OpenAlex indexa**: artigos com DOI e livros em inglês entram bem; livros,
  capítulos e teses em português, muitas vezes, não. A coleta também guarda as referências da ArticleMeta, mas só
  3% a 9% delas trazem DOI, e o casamento aproximado por título fica para uma versão futura.
- A identidade das pessoas erra nos homônimos sem id nem ORCID (a revisão manual corrige) e herda os erros de fusão
  do OpenAlex que não têm ORCID para separá-los.
- As afiliações não identificadas ficam fora da rede de instituições; os artigos sem afiliação, fora da rede de
  estados.
- A rede é do corpus: uma pessoa que escreve com colegas de fora dele aparece com menos coautores do que tem.

As decisões e os números do piloto estão no [ADR 0014](../decisoes/0014-redes-de-coautoria-e-citacao.md).
