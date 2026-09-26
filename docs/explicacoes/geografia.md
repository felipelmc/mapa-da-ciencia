# Geografia da produção

A vista Geografia responde onde a produção de um corpus acontece: em que UFs, países e instituições estão os autores. Para isso, o `mapa` precisa de duas coisas que as fontes não entregam prontas: saber **qual instituição** está por trás de cada texto de afiliação e decidir **quanto cada documento conta** para cada lugar. Esta página explica as duas, e onde elas falham. Os números são do piloto (4.275 artigos de dez revistas de ciência política, 2010–2025); a decisão, com a calibração completa, está no [ADR 0008](../decisoes/0008-geografia-casamento-das-afiliacoes.md).

## De onde vêm as afiliações

Cada artigo pode trazer as afiliações dos autores de três jeitos:

- **`v240` da ArticleMeta**: a afiliação normalizada pelo SciELO, com o nome da instituição, a cidade, a UF e o país. É a melhor fonte, mas no piloto aparece quase só a partir de 2014: são 20 afiliações `v240` de 2010 a 2013 e 4.071 depois.
- **`v70` da ArticleMeta**: o texto que o autor escreveu, como "USP", "PUC-Rio", "Universidade de Maryland" ou "Centro de Formação da Câmara dos Deputados". Às vezes com o país errado ("Universidade de Cambridge, Brasil"). São 1.129 afiliações `v70` até 2013 e 1.552 depois.
- **OpenAlex**: para cada autor, as instituições que o OpenAlex reconheceu (com identificador, país e as instituições acima delas) e o texto de onde as tirou.

A coleta guarda também o **registro de cada instituição** do OpenAlex: siglas, nomes alternativos, país, região, cidade, tipo e linhagem. É com esses registros que o casamento compara nomes, e por isso a geografia roda sem rede e em segundos.

## Qual instituição é

Contar direto pelos textos daria dezenas de grafias para a mesma instituição. O `mapa` liga cada afiliação a uma instituição do OpenAlex, procurando os candidatos do mais próximo ao mais distante:

1. **apelidos**: textos que o pacote ou o `instituicoes.yaml` do projeto já ligam a uma instituição ("Instituto de Estudos Sociais e Políticos" é a UERJ);
2. **autoria**: as instituições que o OpenAlex deu ao mesmo autor, se o nome se parecer com o texto;
3. **obra**: as instituições de todos os autores do artigo, com uma exigência maior de semelhança;
4. **corpus**: o mesmo texto já casado em outros artigos, pelo menos duas vezes e sem divergência;
5. **índice**: todas as instituições conhecidas, só com um nome quase idêntico e bem à frente do segundo candidato.

A semelhança compara as palavras dos dois nomes, sem acentos e sem palavras vazias, com as palavras genéricas traduzidas para uma forma só ("University", "Universidad" e "Universidade" são a mesma palavra). Palavras raras pesam mais que palavras comuns, como "universidade". Siglas do registro que aparecem no texto ("UFSCar", "PUC-Rio") casam direto.

Nomes de instituições brasileiras são muito parecidos entre si, e o maior risco é casar com a vizinha errada. Por isso há travas:

- **palavras discriminantes** precisam ser as mesmas nos dois nomes: federal, estadual, católica, rural, tecnológica, nova, e os pontos cardeais. Assim a UERJ não casa com a UFRJ, nem a UFMS com a UFMT;
- **substituição**: se cada nome tem uma palavra distintiva que o outro não tem, são instituições diferentes ("Paraná" e "Pará", "Administração Pública" e "Saúde Pública");
- **país**: quando a fonte informa o país e o registro diz outro, o candidato cai. A trava vale mesmo quando a `v70` erra o país, porque aceitar nomes idênticos de outro país casaria a Escola Superior de Guerra com a da Colômbia;
- **lugar**: ter só uma cidade em comum ("London" e "SOAS University of London") não basta.

Depois do casamento, a instituição **sobe na linhagem** até a organização de ensino "mãe", como faz a `v240`: um hospital universitário conta para a universidade, e a Escola de Administração de Empresas de São Paulo, para a FGV. Uma universidade de uma federação (King's College London, na University of London) não sobe.

Nos artigos mais antigos, o OpenAlex tira "afiliações" do texto raspado do PDF ("Em maio de 2007 o Ministério Público Federal ingressou…") e as liga a instituições sem relação com o autor. Uma instituição do OpenAlex só vale quando o texto que a sustenta parece uma afiliação e se parece com o nome dela.

**Como ficou no piloto.** Das afiliações `v240`, 99,4% casaram; das `v70`, 83,8%, e 86,5% depois de uma rodada de revisão (`mapa geografia --revisar`) que acrescentou 22 apelidos e 6 instituições próprias. Numa amostra independente de 200 vínculos lidos um a um, a precisão dos casamentos foi de 99,8%. O que não casa é, na maior parte, instituição que o OpenAlex não conhece: institutos nacionais de ciência e tecnologia, grupos de pesquisa, órgãos públicos.

## Quanto cada documento conta

Um artigo de três autores, dois da USP e um da UnB, conta quanto para cada uma? O `mapa` usa a **contagem fracionária**: cada documento vale 1, dividido igualmente entre os autores e, para cada autor, entre as afiliações dele. No exemplo, a USP recebe 2/3 e a UnB, 1/3. Um autor com duas afiliações divide a sua parte entre elas.

Assim, artigos com muitos autores não pesam mais que os outros, e a soma de tudo é exatamente o número de documentos (4.275 no piloto). A vista também mostra a **contagem inteira** (quantos documentos têm alguma afiliação no lugar), que responde a outra pergunta: em quantos artigos a instituição aparece.

Três casos pedem regra:

- **autor sem afiliação**: a parte dele vai para "sem afiliação", e não é redistribuída entre os coautores. No piloto, 223 do peso total (5,2%);
- **afiliação que ninguém cita** (a fonte lista a afiliação, mas não diz de qual autor é): vai para os autores sem afiliação ou, se todos têm, entra na lista de cada um;
- **afiliação que não casou**: conta como "instituição não identificada", mas com o país e a UF que a fonte informou.

## UF e país

O país de cada vínculo é o da instituição identificada (o casamento já descartou os que discordam da fonte) ou, sem ela, o que a fonte escreveu. A UF, só para vínculos no Brasil, sai da primeira informação disponível, nesta ordem:

1. a UF escrita na fonte (ou junto da cidade: "Niterói, RJ");
2. a cidade da fonte, quando o nome do município é único no país ou é capital; senão, a UF que a `v240` do corpus dá à cidade (há São Carlos em SP e em SC);
3. a UF que o `instituicoes.yaml` do projeto dá à instituição;
4. a UF mais comum da instituição nas afiliações `v240` do corpus;
5. a região do registro no OpenAlex, que falta em 45% das instituições brasileiras;
6. a cidade do registro no OpenAlex.

No piloto, o país é conhecido em 98,9% do peso com afiliação, e a UF em 99,2% do peso brasileiro.

## Filtrar por lugar

Na interface, escolher uma UF, um país ou uma instituição põe o lugar no recorte, que vale para as outras vistas. Um documento passa no recorte se tiver **alguma** afiliação no lugar escolhido. No Mapa e nos Tópicos, cada documento que passa conta 1; o peso fracionário só entra nas somas da Geografia. Com São Paulo no recorte, o ranking das instituições mostra também os coautores de fora de São Paulo desses artigos: é a rede de colaboração dos artigos paulistas, e não só as instituições paulistas.

## Limitações e vieses

- **Cobertura desigual no tempo.** Nos primeiros anos do piloto, as afiliações vêm quase só como texto livre, e mais autores ficam sem afiliação. A vista mostra a cobertura por ano e avisa dos anos em que mais de 20% do peso fica sem afiliação: comparar esses anos com os recentes exige cuidado.
- **Instituições com vários campi.** Uma universidade com campi em vários estados recebe uma UF por vínculo, quando a fonte informa, mas a UF da tabela de instituições é a mais comum no corpus.
- **Redes e programas interinstitucionais** (INCTs, programas de pós-graduação de várias universidades) não são instituições no OpenAlex e ficam como não identificados, a menos que o projeto os declare no `instituicoes.yaml`.
- **Erros das fontes.** Um país errado na `v70` fica errado na contagem; o casamento só não piora o erro.
- **A amostra de precisão** foi lida pelo Claude, não por um especialista em instituições brasileiras. Ela está em `docs/decisoes/dados/0008-amostra-geografia.csv`, para quem quiser conferir.

## Para saber mais

- [Gerar a geografia](../guias/geografia.md): a etapa, a revisão e o `instituicoes.yaml`.
- [Ler a geografia](../guias/ler-a-geografia.md): os mapas, o ranking e a cobertura na interface.
- [ADR 0008](../decisoes/0008-geografia-casamento-das-afiliacoes.md): a decisão, os limiares e a calibração.
