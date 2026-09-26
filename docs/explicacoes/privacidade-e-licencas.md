# Privacidade e licenças

## O que nunca sai da sua máquina

- **Textos para modelos:** embeddings e classificação rodam no Ollama local.
- **E-mails de autores:** a ArticleMeta traz o e-mail de alguns autores nas afiliações. A normalização da coleta (marco M2) descarta esse campo, e ele nunca chega aos dados do projeto nem ao site publicado. Os testes do contrato de dados verificam que nenhum arquivo exportado contém e-mails.
- **Codificações humanas individuais:** o site publicado mostra só as métricas agregadas de concordância.
- **Chaves e e-mail de contato:** ficam no `.env` do projeto, que o `mapa novo` já coloca no `.gitignore`.

As únicas chamadas externas são as da coleta de metadados públicos (ArticleMeta e OpenAlex), identificadas por um User-Agent do projeto.

## Licenças dos resumos

O painel local mostra os resumos para você trabalhar. O site publicado (`mapa publicar`) é outra coisa: redistribui os resumos na internet, e aí a licença de cada artigo importa.

As fontes nem sempre concordam sobre a licença:

- no registro das revistas do piloto, a ArticleMeta indica **CC BY** para todas;
- o OpenAlex indica **CC BY-NC** em 2.428 artigos e **CC BY** em 2.174;
- o XML da ArticleMeta chega a indicar CC BY 4.0 para um artigo de 2010, três anos antes de essa versão da licença existir, o que sugere que ele traz a licença *atual* da revista, e não a original.

Por isso o `mapa-da-ciencia` segue uma regra prudente ([ADR 0003](../decisoes/0003-fontes-casamento-e-licencas.md)):

- a licença de cada artigo é a **mais restritiva** entre a do OpenAlex e a da revista, e a fonte fica registrada;
- num site publicado sem fins comerciais, resumos com licença Creative Commons (BY, BY-NC, BY-NC-ND) são mostrados **na íntegra e sem alteração**, com atribuição (autores, revista, DOI e licença);
- resumos sem licença identificada, ou com licença não aberta, ficam de fora: aparecem só título, metadados e link;
- a opção `--sem-resumos` publica sem nenhum resumo.

!!! warning "Não é parecer jurídico"
    Esta é uma regra prática adotada pelo projeto, não uma orientação jurídica. Em caso de dúvida sobre um uso específico, consulte a licença de cada artigo e, se preciso, a assessoria da sua instituição.

## Projeto independente

O `mapa-da-ciencia` é um projeto independente, sem vínculo oficial com o SciELO, o OpenAlex ou o IBGE. Os dados continuam sendo das respectivas fontes. Ao publicar resultados, cite as fontes e as revistas.
