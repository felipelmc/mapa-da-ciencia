# 0015 · Júri de modelos locais e supervisor

- **Estado:** aceita
- **Data:** 2026-09-28
- **Marco:** v2.0

## Contexto

Na versão 1, um único modelo local (`qwen3.5:9b`) classifica o corpus. Contra a referência, ele vai bem nas variáveis
claras e mal nas ambíguas: a `tecnica_principal` fica com kappa 0,37 (ADR 0012). A pergunta do artigo metodológico é
se modelos abertos bastam, e duas saídas óbvias têm custo: um modelo maior não cabe no notebook de 24 GB, e mandar
tudo para um modelo comercial tira os textos da máquina e custa dinheiro. Um meio-termo é juntar vários modelos
locais pequenos, de famílias diferentes, e deixar para um supervisor mais forte só o que eles não resolvem.

## Decisões

1. **Votação por maioria estrita, com evidência.** Cada membro classifica pelo caminho de `mapa classificar
   --modelo` (mesmo prompt, mesma evidência obrigatória, mesmo cache). Uma maioria só decide se ao menos um voto dela
   trouxer evidência encontrada no texto. Múltipla escolha decide categoria a categoria; texto livre, pela forma
   normalizada, sem deliberação. Alternativa descartada: média ponderada pela confiança declarada, que os modelos
   pequenos não calibram.
2. **Uma rodada de deliberação, anônima, no mesmo prefixo.** Nas variáveis sem unanimidade, cada membro vê as
   respostas dos outros como "Modelo A/B" (em ordem de valor, sem nomes), com as evidências e a marca de trecho não
   encontrado, e é instruído a mudar só se a evidência de outro mostrar que a definição se cumpre melhor. A conversa
   repete o prefixo da classificação para o Ollama reaproveitar o cache. Alternativa descartada: várias rodadas, que
   aumentam a conformidade sem informação nova.
3. **Supervisor com escolha restrita aos candidatos.** O que continua sem maioria vai ao supervisor, que escolhe um
   dos valores dados pelos membros (numerados, sem os nomes), com evidência e justificativa, ou marca
   `nenhum_adequado`. Isso limita a circularidade: o supervisor não pode dar uma resposta que nenhum modelo local deu.
4. **Auditoria das unanimidades.** O supervisor confere 40 decisões unânimes sorteadas com a semente da validação; a
   taxa de erro sai com o intervalo de Wilson.
5. **Três fontes sintéticas** (`juri-r1`, `juri`, `juri-supervisor`) gravadas como resultados de classificação, para
   a validação medir o júri sem código novo.
6. **Circularidade declarada.** `validacao.familias` diz a família de cada codificador; um par da mesma família sai
   marcado `circular`. O **resultado principal é referência × `juri`**; referência × `juri-supervisor` é só um limite
   superior. Um codificador humano com pelo menos 50 documentos vira a referência automaticamente.
7. **Supervisor por arquivos, e pela API como opção.** O padrão grava pedidos em JSONL e lê as respostas no mesmo
   formato, sem rede. O modo `api` usa o SDK oficial da Anthropic (extra opcional `[anthropic]`), com consentimento
   explícito (`enviar_textos: true` e uma confirmação por execução), estimativa de custo antes de começar e um limite
   de gasto. Os testes usam um cliente falso: nenhum texto do piloto foi enviado a uma API.

## Números do piloto

Rodada de 28/09/2026 na amostra de validação (200 documentos), com `qwen3.5:9b` (o modelo principal),
`gemma4:12b-it-qat` e `qwen3.5:4b`, num Mac de 24 GB. A referência é `claude-opus`, lendo às cegas; o supervisor foram
três sessões novas do Claude Opus 5.5 pelo protocolo por arquivos, cada uma só com as instruções e um lote.

**Resultado principal** (kappa contra a referência, IC 95% *bootstrap*; McNemar entre o `juri` e o modelo principal):

| Variável | `qwen3.5:9b` | `gemma4:12b` | `qwen3.5:4b` | `juri-r1` | `juri` | McNemar |
|---|---|---|---|---|---|---|
| `abordagem` | 0,67 | 0,72 | 0,60 | 0,67 | 0,71 (0,63–0,79) | p = 0,557 |
| `tecnica_principal` | 0,37 | 0,65 | 0,48 | 0,50 | 0,61 (0,53–0,68) | p < 0,001 (47 × 3) |
| `recorte_geografico` | 0,74 | 0,78 | 0,74 | 0,77 | 0,77 (0,70–0,84) | p = 0,180 |
| `brasil_como_caso` | 0,93 | 0,95 | 0,79 | 0,95 | 0,96 (0,92–0,99) | p = 0,375 |
| `subarea` | 0,63 | 0,74 | 0,58 | 0,66 | 0,69 (0,62–0,75) | p = 0,027 (16 × 5) |

- **O júri tira a `tecnica_principal` do vermelho:** de 0,37 para 0,61, e o McNemar mostra que a diferença não é
  acaso (47 documentos que só o júri acerta, 3 que só o modelo principal acerta). Em `subarea`, 0,63 → 0,69.
- **Mas o melhor membro sozinho vai tão bem quanto:** o `gemma4:12b` tem o kappa mais alto em quatro das cinco
  variáveis (0,65 na técnica). O júri chega perto dele sem saber de antemão qual modelo é o melhor, o que só a
  referência revela; sem referência, o júri é a aposta mais segura, e com ela vale conferir se um membro sozinho
  não basta.
- **Deliberação:** muda a decisão em 80 das 322 decisões deliberadas. Os votos revistos vão mais para a referência
  do que contra ela no `qwen3.5:9b` (71 × 20) e no `qwen3.5:4b` (38 × 9), mas não no `gemma4:12b` (39 × 43): o membro
  mais forte às vezes cede à maioria dos outros dois, que são da mesma família (Qwen). Em 32 decisões de técnica, os
  dois Qwen venceram o Gemma, e em 26 delas o Gemma concordava com a referência.
- **A unanimidade é um sinal de confiança:** concorda com a referência em 92% das 720 decisões unânimes, contra 81%
  nas maiorias sem deliberação (só a variável de texto livre), 56% nas decididas na deliberação e 56% nas sem
  maioria.
- **Supervisor:** só 9 decisões categóricas ficaram sem maioria depois da deliberação (as outras 46 sem maioria são
  do período analisado, texto livre, que não vai ao supervisor). O supervisor marcou uma como `nenhum_adequado`.
  Com ele, o kappa quase não muda (`subarea` 0,69 → 0,70), e esse número é **circular** (supervisor e referência
  são Claude).
- **Auditoria:** das 40 decisões unânimes sorteadas, o supervisor julgou 2 erradas: 5,0% (IC 95% de Wilson,
  1,4%–16,5%). Uma delas é um ensaio teórico marcado `nao_informado` na técnica, o erro mais comum do modelo
  principal.
- **Custo:** rodada 1 com 111 minutos de modelo (40, 45 e 26 por membro), deliberação com 37 (13, 17 e 7), e o
  supervisor, três sessões de 1 a 2 minutos. São cerca de 2,5 h para 200 documentos, 3,7 vezes o modelo principal
  sozinho; no corpus inteiro (4.247 documentos), cerca de 50 h.

**O codebook também erra.** Um agente leu as 111 divergências da `tecnica_principal` e as 64 da `subarea` e
escreveu sugestões (no piloto, `validacao/sugestoes-codebook.md` e `codebook-sugerido.yaml`, que **não** foram
aplicadas: mudar o codebook reclassifica o corpus inteiro). Em resumo: 44 divergências da técnica são ensaios
teóricos que o modelo marca `nao_informado` e a referência `bibliografia`, e o prompt dispensa a evidência de
`nao_informado`, o que torna essa a resposta mais barata; a variável mistura desenho (estudo de caso) e fonte
(documentos); e a referência pôs 38 documentos de sociologia, antropologia e crítica cultural em `subarea: outra`,
categoria que os modelos locais evitam (sem eles, o kappa da subárea seria 0,79). A proposta é uma ordem de decisão
em cada pergunta e fronteiras explícitas nas definições, com metas de 0,55–0,65 (técnica) e 0,70–0,78 (subárea),
a validar numa amostra nova.

**Recomendações:** membros de três famílias diferentes (trocar o `qwen3.5:4b` por outra família que caiba na
memória); harmonizar a regra da evidência de `nao_informado` entre as instruções e o prompt; e codificar a amostra
por uma pessoa, o único teste sem circularidade.

## Consequências

- A etapa `mapa juri` é opcional e roda na amostra de validação, onde há referência para medir o ganho. Levá-la
  ao corpus inteiro (cerca de 50 h de modelo no piloto) fica para uma versão futura.
- A validação ganha a família dos codificadores e a marca `circular`, e o contrato vai para a versão 1.5.
- O teste sem circularidade continua dependendo de uma codificação humana da amostra.
