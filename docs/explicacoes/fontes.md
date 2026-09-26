# Fontes de dados

O corpus de um projeto sai de duas fontes públicas, que se complementam.

## ArticleMeta (SciELO)

A [ArticleMeta](https://articlemeta.scielo.org) é a API de metadados do SciELO. Para cada artigo, ela traz:

- títulos e resumos em vários idiomas;
- palavras-chave;
- autores, com ORCID quando informado;
- afiliações com instituição, cidade, UF e país;
- tipo de documento e ano de publicação.

É a fonte principal porque cobre **todas** as revistas de uma coleção do SciELO, com os resumos em português que outras bases muitas vezes não têm.

Duas limitações moldam o desenho:

- **Não tem busca por termo.** A coleta é feita revista a revista: listam-se os PIDs de cada revista e busca-se o registro de cada artigo.
- **Não filtra por ano de publicação.** O filtro de datas da API usa a data em que o registro foi *processado*, e artigos antigos são reprocessados com frequência. O ano de publicação sai do próprio PID (`S0104-6276`**`2024`**`000100200`), que no piloto bateu com o ano de publicação em 100% dos casos.

## O que o `mapa` guarda de cada artigo

Cada registro da ArticleMeta vira um **documento** com títulos, resumos e palavras-chave em cada idioma, autores (com ORCID, quando há), afiliações, revista, ano, tipo, DOI e licença. Três cuidados entram nessa normalização:

- **Nenhum e-mail.** O registro traz e-mails em vários lugares: nas afiliações, no registro da revista embutido em cada artigo e nas referências. O `mapa` copia só campos de uma lista permitida (instituição, departamento, cidade, UF, país) e, no fim, ainda varre todo o documento e remove qualquer endereço que tenha escapado. Os testes conferem isso com e-mails falsos plantados nos dados.
- **Texto limpo.** Um terço dos resumos traz entidades HTML, às vezes escapadas duas vezes (`&amp;#8217;` no lugar de `’`), e muitos começam com "Resumo:". Tudo isso sai na limpeza.
- **Afiliações das duas versões.** A versão normalizada da afiliação (`v240`, com país em código ISO) é usada quando existe. As afiliações que ela não cobre vêm da versão original (`v70`).
- **Autores segundo o OpenAlex.** Do OpenAlex, o documento guarda também os autores na ordem da obra, com as instituições que o OpenAlex reconheceu (com o identificador [ROR](https://ror.org), o país, o tipo e as instituições acima dela) e o texto de afiliação de cada um, sem e-mails. É a base da [geografia](../guias/painel.md): as afiliações da ArticleMeta são casadas com essas instituições.

As referências citadas por cada artigo (cerca de 90% do tamanho de um registro) não entram no documento, só a contagem delas. Elas continuam guardadas nas respostas brutas, para as redes de citação da v2.

## OpenAlex

O [OpenAlex](https://openalex.org) é um catálogo aberto (licença CC0) de publicações científicas do mundo todo. No `mapa-da-ciencia`, ele entra para:

- **enriquecer** cada artigo com o número de citações recebidas e a licença;
- **buscar por termo** dentro das revistas do recorte, o que a ArticleMeta não faz;
- no futuro, fornecer as referências para as redes de citação.

Desde 2026 o OpenAlex cobra por uso. Sem chave, são mil créditos por dia; com a chave gratuita, dez vezes mais. A chave vai no `.env` do projeto (`OPENALEX_API_KEY`) e nunca é gravada junto com as respostas.

| Chamada | Créditos |
|---|---|
| Uma página de lista (até 200 trabalhos de uma revista num período) | 1 |
| Uma lista de até 50 DOIs | 1 |
| Uma página de busca por termo | 10 |
| Um trabalho no endereço direto (`/works/doi:…`) | 0 |
| Um lote de até 100 instituições (`/institutions`) | 1 |

O enriquecimento pede os trabalhos de cada revista no período, então custa cerca de 1 crédito por revista para cada 200 artigos: o piloto inteiro (10 revistas, 16 anos) fica em torno de 32 créditos. O `mapa coletar` mostra quantos foram gastos, e `--sem-openalex` pula essa etapa.

Depois do enriquecimento, a coleta busca os **registros das instituições** que aparecem nas autorias (e as instituições acima delas, como a universidade de um hospital universitário), em lotes de 100. Cada registro traz o nome, as siglas, os nomes alternativos, o país, a cidade, a região (a UF, quando existe) e o tipo. No piloto são cerca de mil instituições, uns 10 créditos na primeira vez e nenhum depois: as respostas ficam em `brutos/openalex/instituicoes/`, com um índice dos pedidos, e um identificador que o OpenAlex não devolve não é pedido de novo. Os registros vão para `dados/instituicoes_openalex.parquet` e alimentam a geografia, que roda sem rede. Se o OpenAlex estiver fora do ar, a coleta termina com um aviso, e a geografia usa só os nomes.

Quando a ArticleMeta não traz resumo de um artigo e o OpenAlex traz, o resumo do OpenAlex entra como **reserva**, marcado com a origem (`openalex`). O mesmo vale para o título: no piloto, seis artigos da *Opinião Pública* e da *Novos Estudos* de 2010 a 2013 estão sem título na ArticleMeta.

O resumo de reserva nem sempre é um resumo. Às vezes o OpenAlex guarda um texto raspado da página do artigo: no piloto, dez artigos da *Novos Estudos CEBRAP* tinham como "resumo" a mesma apresentação, em espanhol, da biblioteca virtual Americanae. Por isso, **um resumo que se repete em documentos diferentes é descartado**. Um resumo do OpenAlex sai assim que aparece em outro documento. Um da ArticleMeta só sai quando se repete em três ou mais documentos, porque artigos publicados em duas partes podem dividir o mesmo resumo. O documento fica com os resumos que sobrarem, ou só com o título, e a coleta avisa quantos resumos saíram.

## E o search.scielo.org?

O buscador do SciELO, usado pelo antigo SciELO-Summarizer, hoje bloqueia acessos automatizados com um desafio anti-robô. Por isso o `mapa-da-ciencia` não o usa diretamente. Você pode buscar no navegador, exportar o resultado (RIS, CSV ou BibTeX) e importar o arquivo no projeto: veja [Importar uma busca do SciELO](../guias/importar.md).

## Como os registros são casados

A ArticleMeta nem sempre informa o DOI: no piloto, faltou em 27% dos registros. Para encontrar o mesmo artigo no OpenAlex, o `mapa` tenta, nesta ordem:

1. o DOI da ArticleMeta;
2. o PID do SciELO dentro dos endereços que o OpenAlex guarda;
3. o DOI derivado do PID (`10.1590/{PID}`), padrão de revistas brasileiras mais antigas;
4. o título normalizado mais o ano.

Os candidatos vêm da lista de trabalhos da revista no período. A lista inclui os trabalhos em que a revista aparece em qualquer lugar, e não só como fonte principal: o OpenAlex às vezes registra um repositório (LA Referencia, DOAJ) como fonte principal de um artigo de revista. Quem sobra sem casamento é procurado pelo DOI, primeiro numa lista de DOIs e depois, um a um, no endereço direto do OpenAlex, que acha trabalhos recentes que a lista ainda não acha.

Antes de aceitar um candidato, o `mapa` **confere** se ele é mesmo o artigo: o ano precisa bater (com um ano de folga) e o título precisa ser parecido em algum idioma. Com o ano fora da folga, só vale um título longo e praticamente igual, porque o OpenAlex também erra anos (artigos da *Novos Estudos* de 2025 aparecem como de 2005). Além disso, cada trabalho do OpenAlex só pode ser casado com um artigo. A conferência existe porque a própria ArticleMeta tem DOIs trocados: na *Dados* de 2014, dois artigos diferentes aparecem com o mesmo DOI. Sem a conferência, os dois seriam casados com o mesmo trabalho (e herdariam as citações e a licença um do outro). Com ela, só o artigo certo casa, e o outro fica sem casamento e **sem DOI**: como o OpenAlex confirmou que o DOI pertence ao primeiro, ele é retirado do segundo, e a coleta avisa (veja [Duplicatas](#duplicatas)).

O passo usado fica registrado em cada documento.

## Duplicatas

O mesmo artigo pode chegar mais de uma vez: de fontes diferentes (coletado da revista e também importado de uma busca) ou da própria ArticleMeta, que tem artigos carregados duas vezes com identificadores diferentes (na *Dados* e na *Lua Nova*, em 2025). O `mapa` junta os registros quando tem certeza:

- **mesmo PID**;
- **mesmo DOI e títulos compatíveis**. DOI igual com títulos diferentes não basta, por causa dos DOIs trocados;
- **sem DOI, mesmo título, ano e sobrenome do primeiro autor**, vindos de fontes diferentes.

Quando junta, fica a versão da ArticleMeta, as origens se somam, e o par fica registrado no manifesto da coleta. Quando só desconfia (mesmo título, ano e autor dentro da mesma fonte, sem DOI em comum), o documento é mantido e marcado como **possível duplicata**, para você decidir. Títulos curtos e genéricos, como "Apresentação", nunca contam como duplicata.

Se, depois disso, um DOI ainda aparece em dois documentos diferentes, ele fica só com aquele que o OpenAlex confirmou (casado pelo DOI, com título conferido). Os outros ficam sem DOI, e a coleta mostra um aviso com o par. Se nenhum foi confirmado, não dá para saber de quem é o DOI, e os dois ficam como estão.

## Cobertura no piloto

Ciência política no SciELO Brasil, 10 revistas, de 2010 a 2025 (coletado em 26/09/2026 com `mapa coletar`):

| | Documentos | % |
|---|---|---|
| Artigos de pesquisa ou revisão (o corpus) | 4.275 | 100 |
| Com resumo | 4.247 | 99,3 |
| Com resumo em inglês | 4.159 | 97,3 |
| Com DOI | 4.262 | 99,7 |
| Com afiliação normalizada (`v240`) | 2.523 | 59,0 |
| Com afiliação só em texto livre (`v70`) | 1.418 | 33,2 |
| Casados com o OpenAlex | 4.249 | 99,4 |
| Com licença Creative Commons | 4.249 | 99,4 |

A ArticleMeta tem 4.947 registros dessas revistas no período. Ficam de fora 670 de outros tipos (resenhas, editoriais, erratas...), e 2 artigos carregados duas vezes são fundidos. Os números por revista estão no adendo do registro de decisão [0003](../decisoes/0003-fontes-casamento-e-licencas.md#adendo-2026-09-26-marco-m2-a-coleta-de-producao).
