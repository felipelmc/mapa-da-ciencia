# Privacidade e licenças

## O que nunca sai da sua máquina

- **Textos para modelos:** os embeddings, os rótulos dos tópicos e a classificação rodam no Ollama local.
- **E-mails de autores:** a ArticleMeta traz o e-mail de alguns autores nas afiliações. A normalização da coleta descarta esse campo, e ele nunca chega aos dados do projeto nem ao site publicado. Os testes do contrato de dados verificam que nenhum arquivo exportado contém e-mails. Os textos (afiliações, títulos e resumos) também passam por um detector, que tira o endereço comum (`fulana@exemplo.br`, também com o arroba largo `＠` ou `﹫`) e as formas com espaço em volta do `@` ou depois do ponto, ou com `[at]`/`(arroba)` e `[dot]`/`(ponto)`. Nessas formas, ele só reconhece o endereço se o domínio terminar num domínio de topo, em minúsculas: qualquer domínio de país (`.br`, `.pa`, `.st`…) ou um genérico comum (`.com`, `.org`, `.io`, `.cat`…). A forma `palavra @dominio.tld`, com espaço só antes do `@`, é ambígua: pode ser um e-mail com espaço ou um perfil de rede social citado num resumo (`o perfil @frente.pe`). Nela, o detector tira só o `@dominio.tld` e deixa a palavra anterior: o endereço não fica reconstruível, e um perfil perde só o `@…`, sem apagar o texto em volta. Um perfil que não termina num domínio de topo, como `@maria.silva`, continua no texto. Para não apagar palavras de um texto com linguagem neutra ou métricas (`entre tod@s. no entanto`, `P@10. de acordo`), a forma com espaço depois do ponto exige um primeiro rótulo de duas letras ou mais no domínio: `fulana@a. br` escapa. Antes de procurar, o detector ignora o hífen suave e os espaços de largura zero, que escondem um endereço inteiro na tela, e lê o ponto largo (`．`) como ponto.
- **Codificações humanas individuais:** ficam no `estado.sqlite` do projeto. O mesmo vale para um supervisor do júri que seja uma pessoa (sem família de modelo em `juri.supervisor.familia`): as escolhas e as justificativas dele entram só nos números agregados. Os arquivos que o painel lê (`saida/dados/`) e o site publicado trazem só as métricas agregadas de concordância; as divergências caso a caso saem apenas para codificadores de referência, que não são pessoas. As divergências de uma pessoa aparecem só no painel local, pela API, e no relatório em `validacao/`, que não é publicado e que o `.gitignore` do projeto deixa fora do git.
- **ORCIDs e ids de autor do OpenAlex:** a etapa das redes usa-os para saber quem é quem, mas eles não vão para o
  site. Cada pessoa aparece com um id curto, um HMAC do id interno com um segredo do projeto, gerado na primeira
  `mapa redes` e guardado no `estado.sqlite` (que não é publicado). Sem o segredo, não dá para voltar do id publicado
  ao ORCID testando candidatos, o que um *hash* sem chave permitiria em minutos. O id continua o mesmo entre
  execuções enquanto a pessoa for a mesma; uma fusão ou separação no `pessoas.yaml`, ou um projeto copiado sem o
  `estado.sqlite`, muda os ids (e os links com `no=`). O `mapa publicar` procura ORCIDs, além de e-mails, em cada
  arquivo do site, e interrompe a publicação se achar um que tenha chegado aos dados por outro caminho (um título de
  obra, um nome no `pessoas.yaml`).
- **Chaves e e-mail de contato:** ficam no `.env` do projeto, que o `mapa novo` já coloca no `.gitignore`.

As únicas chamadas externas são as da coleta de metadados públicos (ArticleMeta e OpenAlex), identificadas por um User-Agent do projeto.

A exceção é opcional e explícita: o supervisor do júri pela API da Anthropic (`juri.supervisor.modo: api`) envia os títulos e resumos dos pedidos em disputa. Ele só roda com `enviar_textos: true` no `mapa.yaml`, uma confirmação a cada execução e um limite de gasto; o padrão é o supervisor por arquivos, sem rede. Veja [Usar o júri](../guias/juri.md#o-supervisor-pela-api-da-anthropic-opcional).

## Licenças dos resumos

O painel local mostra os resumos para você trabalhar. O site publicado ([`mapa publicar`](../guias/publicar.md)) é outra coisa: redistribui os resumos na internet, e aí a licença de cada artigo importa.

As fontes nem sempre concordam sobre a licença:

- no registro das revistas do piloto, a ArticleMeta indica **CC BY** para todas;
- o OpenAlex indica **CC BY-NC** em 2.428 artigos e **CC BY** em 2.174;
- o XML da ArticleMeta chega a indicar CC BY 4.0 para um artigo de 2010, três anos antes de essa versão da licença existir, o que sugere que ele traz a licença *atual* da revista, e não a original.

Por isso o `mapa-da-ciencia` segue uma regra prudente:

- a licença de cada artigo é a **mais restritiva** entre a do OpenAlex e a da revista, e a fonte fica registrada;
- num site publicado sem fins comerciais, resumos com licença Creative Commons (BY, BY-NC, BY-NC-ND) são mostrados **na íntegra e sem alteração**, com atribuição (autores, revista, DOI e licença);
- resumos sem licença identificada, ou com licença não aberta, ficam de fora: aparecem só título, metadados e link;
- a opção `--sem-resumos` publica sem nenhum resumo.

!!! warning "Não é parecer jurídico"
    Esta é uma regra prática adotada pelo projeto, não uma orientação jurídica. Em caso de dúvida sobre um uso específico, consulte a licença de cada artigo e, se preciso, a assessoria da sua instituição.

## Projeto independente

O `mapa-da-ciencia` é um projeto independente, sem vínculo oficial com o SciELO, o OpenAlex ou o IBGE. Os dados continuam sendo das respectivas fontes. Ao publicar resultados, cite as fontes e as revistas.
