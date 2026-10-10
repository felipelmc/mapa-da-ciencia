# Seu primeiro mapa, parte 4: classificação e validação

Na [parte 3](primeiro-mapa-tempo-e-geografia.md) você viu os tópicos no tempo e a geografia dos cerca de 400 artigos da *Opinião Pública* de 2010 a 2025. Nesta parte, um modelo de linguagem local lê o resumo de cada artigo e responde às perguntas de um **codebook**: a abordagem, a técnica, o recorte geográfico, a subárea. Cada resposta vem com o trecho do resumo que a justifica. Antes de confiar nas respostas, você **mede** quanto o modelo concorda com uma leitura cuidadosa de uma amostra. Leva uns 90 minutos, a maior parte com o modelo trabalhando sozinho.

!!! info "Antes de começar"
    - Você precisa ter feito as partes 2 e 3, no projeto `projetos/op`.
    - A classificação usa o modelo de `modelos.classificacao` do `mapa.yaml` (`qwen3.5:9b` no perfil padrão, que precisa de uns 8 GB de memória livre). Confira com `uv run mapa diagnostico`.
    - Todos os comandos rodam na pasta do projeto:

        ```bash
        cd projetos/op
        ```

## 1. Conheça o codebook

O `codebook.yaml` do projeto é o de exemplo, com seis variáveis: a abordagem metodológica, a técnica ou fonte de dados, o recorte geográfico, se o Brasil é um caso analisado, a subárea e o período analisado. Abra o arquivo: cada variável tem uma pergunta e, nas categóricas, a definição de cada categoria. É isso que o modelo lê. O guia [Escrever um codebook](../guias/codebook.md) explica como escrever o seu.

## 2. Sorteie a amostra de validação

```bash
uv run mapa validar amostra --n 40
```

A amostra é sorteada entre os artigos com resumo, espalhada pelos tópicos:

```text
Amostra sorteada: 40 documentos, estratificada por tópico (17 estratos), semente 7.
│ Confiança nas instituições democráticas            │ 4 │
│ Identificação Partidária e Polarização Eleitoral   │ 4 │
│ sem tópico                                         │ 3 │
```

Os textos para quem vai codificar ficam em `validacao/amostra.jsonl`. (Numa pesquisa de verdade, use uma amostra maior: o padrão é 200.)

## 3. Estime o tempo

```bash
uv run mapa classificar --estimar
```

O modelo classifica 5 artigos e mostra os resultados, a taxa de evidência literal (o trecho citado está no resumo tal como o modelo o copiou) e quanto falta:

```text
Classificação pronta: 5 de 388 documentos com resumo classificados por qwen3.5:9b; evidência literal em 96%; ...
JSON válido na primeira tentativa: 100,0%; 10,6 s por documento (mediana); 0 documento(s) sem resumo ficam de fora.
Estimativa: faltam 383 documentos, cerca de 1,1 h neste computador.
```

O tempo é o do computador do piloto (um Mac M4 Pro com 24 GB); o seu pode ser outro.

## 4. Classifique a amostra primeiro

```bash
uv run mapa classificar --somente-amostra
```

A amostra de validação vem primeiro na fila, e `--somente-amostra` classifica só ela: uns 7 minutos. Assim a validação pode começar antes de o corpus inteiro ficar pronto.

## 5. Codifique a amostra

Abra o painel e vá a **Validação › Codificar a amostra**:

```bash
uv run mapa painel
```

Escreva o seu nome (sem acentos nem espaços) e codifique as 40 fichas. Cada ficha mostra o título e o resumo; responda com o teclado (++1++ a ++9++ escolhem a opção e passam para a próxima variável, ++enter++ confirma a ficha). A ficha nunca mostra o que o modelo respondeu. Tudo é gravado sozinho; você pode parar e voltar. Veja [Codificar a amostra](../guias/codificar-a-amostra.md).

## 6. Meça a concordância

```bash
uv run mapa validar metricas
```

Para cada variável, a concordância entre você e o modelo: a fração de respostas iguais, o kappa com o intervalo de 95%, o PABAK e o alfa. Na nossa rodada, a amostra foi codificada por um **codificador de referência**, e não por uma pessoa: o Claude (`claude-opus`), um modelo muito maior, lendo às cegas os títulos e resumos da amostra, só para esta documentação (veja [Desenho da validação](../explicacoes/validacao.md)). Foi a única vez em que textos saíram da máquina; no seu projeto, quem codifica é você, no painel:

```text
claude-opus × qwen3.5:9b
│ abordagem          │ 39 │ 67%  │ 0,50 (0,29 a 0,70) │ 0,60 │ 0,49 │
│ tecnica_principal  │ 39 │ 77%  │ 0,70 (0,52 a 0,86) │ 0,74 │ 0,70 │
│ recorte_geografico │ 39 │ 82%  │ 0,71 (0,51 a 0,88) │ 0,78 │ 0,71 │
│ brasil_como_caso   │ 39 │ 100% │ 1,00 (1,00 a 1,00) │ 1,00 │ 1,00 │
│ subarea            │ 39 │ 69%  │ 0,62 (0,44 a 0,78) │ 0,65 │ 0,62 │
│ periodo_analisado  │ 39 │ 90%  │ —                  │ —    │ —    │
```

O n é 39, e não 40, porque um dos documentos que sorteamos era um encarte de dados sem autor, que a coleta passou a deixar de fora depois do sorteio. Com a sua codificação, os números serão outros. Com 40 documentos, os intervalos são largos: a abordagem pode ter um kappa entre 0,29 e 0,70. O guia [Ler kappa e PABAK](../guias/ler-kappa-e-pabak.md) explica cada número e o que fazer com uma variável fraca.

## 7. Classifique o resto

```bash
uv run mapa classificar
```

A etapa continua de onde parou: os 40 documentos da amostra (os 5 da estimativa estavam entre eles) vêm do cache, e o modelo classifica os outros 348. Neste computador, leva pouco mais de uma hora:

```text
Classificação pronta: 388 de 388 documentos com resumo classificados por qwen3.5:9b; evidência literal em 95%;
348 novos e 40 do cache, …
│ Abordagem metodológica      │ Quantitativa (161), Qualitativa (138), Mista (58)                     │ 96% │
│ Técnica ou fonte de dados   │ Dados observacionais agregados (106), Survey (99), Textos e docume…   │ 97% │
│ Recorte geográfico          │ Brasil (nacional) (187), Brasil (subnacional) (103), Outro país ou …  │ 94% │
│ Brasil como caso            │ Sim (305), Não (83)                                                   │ 96% │
│ Subárea                     │ Eleições e partidos (120), Comportamento e opinião (97), Políticas …  │ 94% │
│ Período analisado           │ não se aplica (124), 2010 (15), 2014 (12)                             │ 93% │
JSON válido na primeira tentativa: 100,0%; 10,0 s por documento (mediana); 0 documento(s) sem resumo ficam de fora.
```

A tabela mostra as três respostas mais frequentes de cada variável e a fração de evidências copiadas literalmente do título ou do resumo. Pode interromper a etapa (++ctrl+c++) e rodar de novo quando quiser: nada se perde.

## 8. Veja no painel

Com o painel aberto, a vista **Classificação** mostra uma variável por vez: a distribuição por ano, o cruzamento com os macrotemas e, numa célula, os artigos com o trecho do resumo marcado. Ao lado de cada variável, um selo mostra o kappa da validação. No **Mapa**, o cartão de cada artigo agora marca no resumo os trechos citados. Veja [Ler a classificação](../guias/ler-a-classificacao.md).

## 9. O relatório

```bash
uv run mapa validar relatorio
```

Grava em `validacao/` o relatório em Markdown (com todas as divergências e o trecho que o modelo citou), as tabelas em LaTeX, prontas para um artigo, e as métricas em JSON.

## 10. Consulte em Python

Abra o Python do projeto com `uv run python` e rode:

```python
import mapa_da_ciencia.api as mapa

por_abordagem = """
    SELECT valor, count(*) AS n
    FROM classificacoes
    WHERE variavel = 'abordagem'
    GROUP BY valor ORDER BY n DESC
"""
mapa.consultar(".", por_abordagem)
```

A view `classificacoes` tem uma linha por artigo e variável, com o valor, a evidência e o status da conferência (veja a [API Python](../referencia/api-python.md)).

## O que você fez

- Sorteou uma amostra de validação espalhada pelos tópicos.
- Estimou o tempo e classificou os resumos com um modelo local, primeiro a amostra e depois o resto, com uma evidência para cada resposta.
- Codificou a amostra às cegas e mediu a concordância.
- Viu a classificação no painel e gerou o relatório.

## Próximos passos

- Leia as divergências no relatório ou na vista Validação, revise as definições do codebook e classifique de novo.
- Para comparar com outro modelo local, classifique a amostra com `uv run mapa classificar --somente-amostra --modelo <outro>` e rode `uv run mapa validar metricas`: a comparação entre os dois (teste de McNemar) aparece no fim.
