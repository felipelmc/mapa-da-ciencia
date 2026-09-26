# 0011. Classificação ancorada em evidência

- **Status:** proposta (M5)
- **Data:** 2026-09-26
- **Marco:** M5

## Contexto

O [ADR 0005](0005-modelo-de-classificacao.md) escolheu o modelo local (`qwen3.5:9b`, sem raciocínio, concorrência 1) e mediu, no spike, 100% de JSON válido, evidência literal em 71% das respostas e 12,5 s por resumo, cerca de 15 h para o piloto. Quem custava era a evidência: longa, ela dominava o tempo de geração. O ADR deixou três pendências para o M5: evidências curtas, retomada depois de uma interrupção e checagem de memória contínua.

A classificação precisa também servir à interface (destacar a evidência no resumo que o painel mostra) e à validação (comparar o modelo com codificadores).

## Decisão

1. **O texto classificado é o que o painel mostra**: o título e o resumo no idioma de exibição do projeto (português no piloto), com o de análise como reserva. Documentos sem resumo ficam fora e contam na cobertura.
2. **Uma mensagem de sistema fixa** (instruções do codebook, regras da evidência e as variáveis com definições e exemplos) e uma mensagem do usuário só com o documento: o Ollama reaproveita o processamento do prefixo.
3. **O esquema da resposta sai do codebook**: por variável, `{evidencia, valor}`, com a evidência antes; o valor é `enum`, lista sem repetição, booleano ou texto, conforme o tipo. **A evidência tem no máximo 200 caracteres** no esquema, e as regras pedem até 20 palavras, copiadas palavra por palavra; ela pode ficar vazia quando a resposta é "sem informação" (`nao_informado`, `nao_se_aplica` ou falso).
4. **Conferência** de cada evidência: `literal` (a menos de maiúsculas, espaços, aspas e travessões), `aproximada` (90% dos caracteres casando em blocos), `ausente` ou `dispensada` (vazia numa resposta sem informação). Os *offsets* apontam para o trecho no resumo original.
5. **Uma nova tentativa** por documento quando a resposta foge do codebook ou alguma evidência sai `ausente`, com uma mensagem que aponta as variáveis; fica a melhor das duas. Um documento sem resposta válida não vai para o cache, e a próxima execução tenta de novo.
6. **Cache e retomada.** Cada resposta válida vai para o `estado.sqlite` assim que chega, com a chave (texto, assinatura do que o modelo lê, modelo com o digest, versão do prompt, parâmetros). A assinatura é o *hash* da mensagem de sistema e do esquema: mudar uma definição, o modelo ou o prompt invalida o cache, mas mudar só a versão ou os rótulos de exibição das categorias não (o resultado muda de nome, pelo *hash* do codebook inteiro, e é remontado do cache). Uma interrupção não perde nada.
7. **Memória**: o modelo só é checado e carregado se houver algo a classificar; entre um documento e outro, se a memória acabar, a etapa para com uma explicação. No fim, o modelo é descarregado se foi a etapa que o carregou.
8. **Um resultado por modelo e codebook** em `dados/classificacao/`, para comparar modelos na amostra de validação; o painel mostra o do modelo principal.
9. `--estimar` classifica 5 documentos e projeta o tempo do resto; `--limite N` classifica os primeiros N.

## Evidência

A preencher com a rodada do piloto: tempo por resumo com a evidência curta, JSON válido na primeira tentativa, taxa de evidência literal por variável e quantas vezes a nova tentativa foi usada.

## Consequências

- A classificação do piloto deve ficar em torno de 7 h (ADR 0005), numa execução que pode ser interrompida e retomada.
- A evidência curta limita o que o modelo pode citar; uma variável que dependa de juntar duas partes do resumo sai com evidência aproximada ou ausente, e isso aparece nas taxas por variável.
- A acurácia contra codificação humana é medida na validação (ADR 0012).
