# 0012. Validação e codificador de referência

- **Status:** aceita (M5)
- **Data:** 2026-09-26
- **Marco:** M5

## Contexto

A classificação ([ADR 0011](0011-classificacao-ancorada-em-evidencia.md)) põe um modelo pequeno, rodando no notebook, para ler milhares de resumos. Antes de usar as proporções que ele produz, é preciso medir quanto ele concorda com uma leitura cuidadosa dos mesmos textos. O plano do projeto previa codificação humana; o pesquisador responsável vai codificar a amostra, mas não antes do fim do M5. A pergunta do artigo ("modelos abertos no notebook bastam?") também pede comparar modelos locais entre si.

## Decisão

1. **Amostra de 200 documentos com resumo, estratificada por tópico** (configurável: tópico, ano ou revista), com alocação proporcional e pelo menos um documento por estrato; os documentos sem tópico formam um estrato. Sorteada uma vez com semente registrada (7 no piloto) e guardada no `estado.sqlite`; só `--refazer` sorteia outra.
2. **Codificação cega:** quem codifica recebe só o codebook, o título e o resumo (`validacao/amostra.jsonl` ou a vista Codificar), nunca as respostas de um modelo. A fila da classificação começa pela amostra, e `--somente-amostra` classifica só ela.
3. **Participantes com tipo:** codificadores `humano` ou `referencia` e modelos (`modelo`). O tipo vai para as métricas, o relatório e a interface, e um codificador de referência nunca é chamado de humano.
4. **Codificador de referência:** enquanto a codificação humana não existe, a amostra do piloto é codificada por subagentes do Claude (Opus), importados como `claude-opus`, tipo `referencia`. Cada subagente recebe só o codebook e um lote de 20 textos, sem acesso ao projeto, às respostas do modelo local nem aos outros lotes; um conferidor checa o formato e se as evidências são literais. A concordância com essa referência responde a uma pergunta mais fraca que a validação humana: quanto o modelo local reproduz a leitura de um modelo muito maior, seguindo as mesmas definições.
5. **Métricas por variável e por par** (codificador × modelo, codificador × codificador, modelo × modelo), sobre os documentos que os dois responderam: concordância, kappa de Cohen com IC 95% por *bootstrap* percentil (1.000 reamostras dos documentos, semente do projeto), PABAK com `k` = categorias do codebook, alfa de Krippendorff nominal, matriz de confusão e precisão, revocação e F1 por classe. Múltipla escolha: uma variável sim/não por categoria; texto: só concordância, com normalização de maiúsculas, acentos, espaços e traços. O kappa e o P/R/F1 são conferidos com o scikit-learn nos testes; o alfa, com o exemplo publicado por Krippendorff (2011).
6. **Comparação entre modelos** pelo teste de McNemar exato contra a mesma referência.
7. **Relatório** em `validacao/`: Markdown (com as divergências e a evidência do modelo), tabelas LaTeX e JSON. As métricas vão também para o painel (vistas Classificação e Concordância).

## Evidência

Piloto, amostra de 200 artigos (58 estratos), `claude-opus` (referência) × `qwen3.5:9b`:

| Variável | Concordância | Kappa (IC 95%) | PABAK | Alfa |
|---|---|---|---|---|
| Brasil como caso | 96% | 0,93 (0,87 a 0,98) | 0,93 | 0,93 |
| Recorte geográfico | 78% | 0,74 (0,67 a 0,80) | 0,74 | 0,73 |
| Abordagem metodológica | 77% | 0,67 (0,59 a 0,75) | 0,72 | 0,67 |
| Subárea | 68% | 0,63 (0,55 a 0,70) | 0,63 | 0,62 |
| Técnica ou fonte de dados | 44% | 0,37 (0,30 a 0,45) | 0,37 | 0,34 |
| Período analisado (texto) | 84% | — | — | — |

A técnica é a variável fraca: 44 das 111 divergências são ensaios teóricos que a referência codificou como "bibliografia" e o modelo como "não informado". O codebook de exemplo não diz o que fazer quando o resumo não fala da fonte; é um problema de definição. No tutorial (*Opinião Pública*, 40 artigos, mais empíricos), a mesma variável teve kappa 0,71.

Os lotes do codificador de referência trouxeram um desvio: em alguns resumos sem ano final, o período analisado foi deduzido do ano embutido no identificador do artigo ou da data de publicação. Esses casos foram refeitos só com o título e o resumo antes da importação, e a instrução passou a proibir explicitamente o identificador e a data. O desvio mostra uma ambiguidade do codebook (períodos abertos ou relativos) que também afeta a codificação humana.

A comparação com outros modelos locais não foi feita: o `qwen3.5:4b` não está instalado (o plano não baixa modelos) e o `gemma4:26b` (17 GB) não cabe na memória livre ao lado do resto. O código da comparação (McNemar exato) está pronto e testado.

## Consequências

- As métricas contra `claude-opus` não autorizam dizer que a classificação "acerta"; o relatório e a documentação dizem isso explicitamente. Quando uma pessoa codificar a amostra, o mesmo relatório passa a mostrar a comparação humana ao lado, e a comparação `claude-opus` × pessoa mede a própria referência.
- Com 200 documentos, categorias raras têm pouco suporte: o IC do kappa e o suporte por classe aparecem sempre ao lado dos números.
- Mudar o codebook invalida a classificação (ADR 0011), mas não as codificações: elas continuam guardadas, e as de variáveis que mudaram de definição precisam ser refeitas à mão.
