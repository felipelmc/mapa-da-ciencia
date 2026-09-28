# Revisão geral (setembro de 2026)

Entre a versão 1.0.1 e a 2.0.0, o projeto passou por uma revisão geral e sistemática, feita por agentes independentes
(Claude Opus 5.5), cada um sem ver o trabalho dos outros. Esta página registra o método, as notas e o que foi feito
com cada achado, para que a próxima revisão possa repetir o processo e comparar.

## Método

1. **Linha de base automática:** lint, testes (pytest, vitest, svelte-check, e2e), geradores com `--checar`,
   `mkdocs --strict`, o *wheel* testado sem Node, `npm audit`, `pip-audit`, links do site montado e os números do
   piloto.
2. **Sete revisores, um por dimensão**, só com leitura do repositório e cópias do piloto:

    | # | Dimensão |
    |---|---|
    | 1 | Backend: correção |
    | 2 | Frontend: correção, acessibilidade e desempenho |
    | 3 | Metodologia (cada número da metodologia recalculado do zero) |
    | 4 | Segurança e privacidade |
    | 5 | Documentação (inclusive uma "pessoa de fora" seguindo o tutorial num clone limpo) |
    | 6 | Dados do piloto e textos públicos (rótulos, macrotemas, instituições, histórias da abertura) |
    | 7 | Experiência de uso (demo e abertura no Playwright, em 1440 px e 375 px, temas claro e escuro, CLI) |

3. **Formato fixo dos achados:** severidade, arquivo e linha (ou comando), **evidência reproduzível**, impacto e
   correção sugerida. Achado sem evidência reproduzível não conta.
4. **Verificação adversarial:** cada achado foi para um verificador que não viu o revisor original e tentou
   reproduzi-lo e refutá-lo (confirmado, refutado ou inconclusivo, com a prova).
5. **Correção com teste:** só o que foi confirmado virou correção, cada uma com um teste que falhava antes. Correções
   que invalidariam horas de modelo (codebook, parâmetros dos tópicos) viraram recomendações.
6. **Re-revisão:** cada branch de correção passou por um revisor novo antes do merge, com o CI verde.

## Rubrica e notas

De 0 a 3 por critério (— quando o critério não se aplica à dimensão):

| Dimensão | Correção | Robustez | Testes | Clareza | Coerência | Privacidade | Reprodutibilidade |
|---|---|---|---|---|---|---|---|
| 1. Backend | 2 | 2 | 2 | 3 | 1 | 3 | 2 |
| 2. Frontend | 2 | 2 | 2 | 3 | 2 | 3 | 2 |
| 3. Metodologia | 2 | 2 | 2 | 2 | 2 | 3 | 3 |
| 4. Segurança e privacidade | 2 | 2 | 2 | 2 | 2 | 2 | 2 |
| 5. Documentação | 2 | — | 2 | 2 | 2 | 3 | 3 |
| 6. Dados e textos públicos | 2 | 2 | — | 2 | 2 | — | 3 |
| 7. Experiência de uso | 2 | 1 | 2 | 2 | 2 | 2 | — |

As notas mais baixas: a **coerência do backend** (o estado das etapas e o que o painel mostra divergiam em casos de
borda) e a **robustez da experiência de uso** (vistas que transbordavam no celular, exportações que falhavam).

## O funil dos achados

| | Altos | Médios | Baixos | Total |
|---|---|---|---|---|
| Encontrados pelos revisores | 7 | 39 | 31 | 77 |
| Novos, achados pelos verificadores | — | — | — | 2 |
| **Confirmados** (severidade depois da verificação) | 5 | 38 | 36 | 79 |
| Refutados ou inconclusivos | | | | 0 |

Nenhum achado foi refutado: a exigência de evidência reproduzível filtrou antes. Os verificadores rebaixaram a
severidade de parte deles (por exemplo, o e-mail com espaço em volta do `@`, que nunca chegou ao site publicado, foi
de alto para médio) e acharam dois problemas novos nos dados.

**O que foi feito:**

- **Código (backend, segurança, CLI):** os 11 achados do backend, os 8 de segurança e privacidade e os 4 de código da
  documentação, corrigidos com testes (branch `revisao-geral`). A re-revisão achou 8 problemas nas próprias
  correções, e seis checagens seguintes acharam mais 22, entre eles quatro caminhos pelos quais uma rodada de
  classificação podia apagar a anterior. Eles foram fechados por duas regras (só uma rodada que cobre o corpus
  substitui o resultado guardado; qualquer outra não tira documentos dele), conferidas em 32 sequências de rodadas.
- **Interface:** os 12 achados do frontend e 12 dos 13 de uso, com 28 testes e2e novos (branch `revisao-frontend`);
  o revisor das correções achou mais 6 problemas baixos, também corrigidos.
- **Textos:** os achados de texto da metodologia, da documentação e da abertura (branch `revisao-docs`), revistos por
  um revisor independente, que achou mais 5 frases a corrigir.
- **Dados do piloto:** 21 rótulos de tópico e os 7 macrotemas corrigidos à mão (`rotulos.yaml`), 5 siglas que o
  casamento mandava para universidades estrangeiras (a "USP" que ia para a Universidad San Pedro, no Peru) e a UF da
  FGV (`instituicoes.yaml`), aplicados na rodada final do piloto.
- **Recomendações, não aplicadas:** o quantil t e a marca de tendência frágil (mudariam a lista publicada de
  tendências e exigem um ADR), métricas de concordância por idioma e entre respostas informativas, a validação do
  resumo na coleta e a correção da UF da FGV na coleta (hoje um paliativo no `instituicoes.yaml`).
- **Para o autor decidir:** 7 rótulos de tópico com propostas, a caixa de 11 rótulos, as siglas de estilo, o que fazer
  com os encartes de dados que entraram como artigos, as fontes do Google e a API do GitHub no site da documentação.

## Os incrementos da v2.0 passaram pelo mesmo processo

Antes de cada merge, os incrementos passaram por validadores independentes:

- **Júri de modelos:** duas revisões de código (a segunda conferiu também o relatório do piloto contra os dados). A
  primeira achou 13 problemas (entre eles, uma resposta antiga do supervisor que caía
  sobre candidatos novos e um limite de gasto que a API podia ultrapassar); corrigidos, e a re-revisão achou mais 9,
  também corrigidos.
- **Redes:** três validadores (código, metodologia e uso). O revisor de código e o testador de uso reprovaram a
  primeira versão, e o auditor metodológico a aprovou com ressalvas; os três acharam, cada um por conta própria, a
  matriz de fluxo que usava o id do macrotema como posição, e dois deles os ids das instituições diferentes entre dois
  arquivos do contrato. Os testes com o exemplo sintético escondiam os dois bugs. O auditor metodológico recalculou todos os
  números do zero, e o revisor de código recuperou 58 dos 66 ORCIDs a partir dos ids publicados das pessoas (um hash
  sem segredo). As correções passaram por mais duas rodadas dos três validadores, e a última aprovou com ressalvas
  baixas: nenhuma fusão errada de pessoas em 80 julgadas à mão.

## Uma decisão na rodada final do piloto

A coleta com o código novo mudou quatro resumos que vêm do OpenAlex (a limpeza de texto nova tira deles uma vírgula
final), e refazer os tópicos com eles mudaria o agrupamento inteiro (62 tópicos em vez de 57, e 27 tópicos com mais de 5 documentos de diferença): o HDBSCAN é sensível a pequenas
mudanças na entrada. Para a 2.0.0, os tópicos do piloto continuam os da 1.0.1, calculados com os textos anteriores
(os mesmos embeddings do cache), com os rótulos corrigidos à mão. O corpus publicado já é o novo, sem os e-mails. Um
recálculo dos tópicos fica para quando o piloto for coletado de novo.

## Segunda rodada: a interface (2.1.0)

Depois da 2.0.0, o autor apontou três problemas ao usar o site: os grafos das redes, apertados e pouco interativos; o
conteúdo encostado à esquerda numa tela larga; e a vista Validação, que não carregava. Antes de corrigir, quatro
agentes independentes percorreram a demo do piloto e o painel local com o Playwright, cada um com um foco: erros em
tempo de execução (todas as rotas e modos, dois temas, de 375 a 2560 px, e uma varredura das chaves das listas
contra os dados do piloto), telas largas (medidas de 1440 a 3440 px), a vista Redes e o painel local (API, CLI e as
telas que só existem nele).

- **A Validação** parava em "Carregando…" porque uma lista repetia a chave com os seis modelos do júri, e o Svelte
  lança esse erro também em produção. O exemplo sintético tinha um modelo só: de novo, **os dados reais acharam o
  que o exemplo escondia**. Agora o exemplo tem vários pares por variável, e uma proteção em cada vista mostra
  "Tentar de novo" em vez de deixar a página parada.
- **A largura:** a casca tinha 76rem e ficava encostada no trilho (em 1920 px, sobravam 536 px à direita). Ela passa
  a ser centrada, com até 112rem, e as vistas põem painéis lado a lado a partir de 1600 px.
- **As redes:** o desenho novo (adendo do ADR 0014) foi escolhido entre seis candidatos por métricas e por um
  avaliador que não sabia qual era qual; as interações novas (destaque dos vizinhos, comunidades clicáveis, nomes
  pelo zoom, arrasto, teclado, tela cheia) vieram da lista do revisor da vista.

Os achados de severidade média ou maior do painel e dos erros de execução passaram por verificadores novos, que
tentaram reproduzi-los e refutá-los: dos 25 verificados, 22 se confirmaram e 3 só em parte, e dois verificadores
corrigiram a causa ou a correção proposta (a animação de entrada das vistas, que prendia os painéis de exportação
embaixo da barra do celular; e a limpeza do endereço com um `%` solto, que precisava testar cada sequência). Os
mais sérios do painel: um segundo `mapa painel` no mesmo projeto marcava como falha a etapa que o primeiro rodava;
a tela dizia que mudar um rótulo do codebook não refazia nada, quando o rótulo de uma variável refaz a classificação
inteira; e a codificação aceitava o nome do codificador de referência, mostrando as respostas dele.

Antes do merge, três agentes novos revisaram o resultado: o código (aprovado com ressalvas: 5 achados médios, todos
corrigidos, como o enquadramento do nó que deixava de funcionar depois de um clique no nó já aberto), o desenho das
redes (aprovado com ressalvas: o auditor recalculou as métricas do zero, confirmou que só as coordenadas mudaram e
mostrou que a frase "as comunidades muito ligadas ficam vizinhas" não valia, o que levou a um ajuste do arranjo e a
números em vez da frase) e o uso, em 200 cargas de 375 a 2560 px, nos dois temas (aprovado com ressalvas: os três
pedidos atendidos no computador, e 17 achados, entre eles dois altos que as mudanças criaram no celular, como os
rótulos das comunidades, que tomavam o toque dos nós embaixo deles; os altos e os médios foram corrigidos).

Uma re-revisão conferiu essas correções e reprovou a primeira tentativa: das 14 ressalvas, 6 estavam resolvidas, 6
só em parte e 2 não, e as próprias correções criaram dois problemas. No celular, a barra do grafo passou a ficar
acima dele, e o seletor das comunidades, com um rótulo de corpus real ("Federalismo, capacidades estatais…"),
alargava a página para 732 px. E o cartão, que agora acompanha a rolagem, cobria "A colaboração por ano" (com o
cartão de uma pessoa com muitos documentos, 96% da figura). O exemplo do contrato, com rótulos curtos ("Comunidade
1") e cartões pequenos, não pegava nenhum dos dois. Corrigidos com testes que imitam os dados do piloto (rótulos
longos por `page.route`), a re-revisão foi repetida antes do merge.

Ficaram para depois, registrados: a cor dos nós por comunidade (hoje é a do macrotema, e várias comunidades dividem
a mesma cor); o cartão do documento, que cobre parte do mapa numa tela de 1440 px; o kappa de uma pessoa, que conta
fichas ainda não confirmadas; o editor do codebook, que acrescenta listas vazias ao YAML; o histórico das etapas, que
mostra "na fila" durante a execução; e o júri, que ainda não aparece na linha das etapas nem no `mapa status`.

## Como repetir

Os prompts dos revisores e verificadores, a rubrica e os formatos de saída estão no plano da revisão; os pareceres, com
os scripts de reprodução, ficaram fora do repositório (alguns usam dados do piloto). Para a próxima revisão, a
lição principal: **testar com dados reais**. O exemplo sintético do contrato é bem-comportado demais (ids contíguos,
os mesmos identificadores em todos os arquivos), e os bugs mais graves da v2.0 só apareceram com o piloto.
