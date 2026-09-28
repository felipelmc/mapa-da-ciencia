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

(Preenchidos com a rodada do piloto.)

## Consequências

- A etapa `mapa juri` é opcional e roda na amostra de validação por padrão; no corpus inteiro, o custo é uma
  classificação completa por membro.
- A validação ganha a família dos codificadores e a marca `circular`, e o contrato vai para a versão 1.5.
- O teste sem circularidade continua dependendo de uma codificação humana da amostra.
