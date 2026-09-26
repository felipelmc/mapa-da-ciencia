# Desenho da validação

Um modelo pequeno classificando milhares de resumos é útil só se soubermos quanto ele concorda com uma leitura cuidadosa dos mesmos textos. A validação mede isso numa amostra: pessoas (ou um anotador de referência) codificam os documentos às cegas, e o `mapa` compara as respostas, variável por variável. As decisões estão no [ADR 0012](../decisoes/0012-validacao-e-codificador-de-referencia.md); o passo a passo, em [Codificar a amostra](../guias/codificar-a-amostra.md); a leitura das métricas, em [Ler kappa e PABAK](../guias/ler-kappa-e-pabak.md).

## A amostra

- **200 documentos com resumo**, sorteados uma vez, com semente registrada (7 no piloto).
- **Estratificada por tópico:** cada tópico recebe uma parte proporcional ao seu tamanho, com pelo menos um documento; os documentos sem tópico formam um estrato. Assim a amostra cobre os assuntos do corpus, inclusive os pequenos. No piloto, são 58 estratos (57 tópicos e o "sem tópico").
- A amostra vem primeiro na fila da classificação, e `--somente-amostra` classifica só ela: a validação pode começar antes de o corpus inteiro ficar pronto.

## Codificação cega

Quem codifica vê só o codebook, o título e o resumo, nunca o que o modelo respondeu. Cada pessoa tem uma ordem própria na fila (tirada do nome), o que evita que todas cansem nos mesmos documentos. Pode marcar uma resposta como incerta e escrever uma nota, e isso aparece nas divergências.

## Quem responde

Cada participante tem um tipo, que acompanha os números em todo lugar:

- **pessoa** (`humano`): quem codificou pelo painel ou por um arquivo importado;
- **referência** (`referencia`): um anotador que não é uma pessoa, como um modelo muito maior lendo a amostra às cegas;
- **modelo**: cada modelo local que classificou a amostra.

No piloto, a amostra foi codificada por uma **referência**: subagentes do Claude (Opus), em 10 lotes de 20, cada um com acesso só ao codebook e aos textos do lote, sem ver o projeto, as respostas do modelo local nem os outros lotes. Os códigos foram importados como `claude-opus`. Ao revisar os lotes, apareceu um desvio da regra: alguns períodos analisados tinham sido deduzidos do ano embutido no identificador do artigo, fora do texto. Esses casos foram refeitos só com o título e o resumo antes da importação.

A concordância com uma referência responde a uma pergunta mais fraca que a validação humana: quanto o modelo local reproduz a leitura de um modelo muito maior, seguindo as mesmas definições. Ela é útil para achar definições ambíguas e comparar modelos locais, mas não autoriza dizer que a classificação "acerta". Quando uma pessoa codificar a amostra, o mesmo relatório passa a mostrar a comparação humana ao lado.

## As métricas

Para cada variável e cada par de participantes, sobre os documentos que os dois responderam: concordância simples, kappa de Cohen com intervalo de 95% por *bootstrap*, PABAK, alfa de Krippendorff nominal, matriz de confusão e precisão, revocação e F1 por categoria. Entre dois modelos comparados com a mesma referência, o teste de McNemar exato. O kappa e a precisão/revocação são conferidos com o scikit-learn nos testes, e o alfa com o exemplo publicado por Krippendorff.

## O que o piloto mostrou

Na amostra de 200 artigos, `qwen3.5:9b` contra a referência `claude-opus`:

| Variável | Concordância | Kappa (IC 95%) |
|---|---|---|
| Brasil como caso | 96% | 0,93 (0,87 a 0,98) |
| Recorte geográfico | 78% | 0,74 (0,67 a 0,80) |
| Abordagem metodológica | 77% | 0,67 (0,59 a 0,75) |
| Subárea | 68% | 0,63 (0,55 a 0,70) |
| Técnica ou fonte de dados | 44% | 0,37 (0,30 a 0,45) |
| Período analisado (texto) | 84% | — |

A técnica de pesquisa é a variável fraca, e a matriz de confusão mostra por quê: em 44 das 112 divergências, a referência respondeu "bibliografia" e o modelo, "não informado". São ensaios teóricos: o modelo entende que o resumo não informa uma técnica, e a referência lê a literatura como a fonte do estudo. A definição de "bibliografia" no codebook de exemplo ("a literatura ou autores clássicos são a fonte principal, típico de textos teóricos e revisões") não diz o que fazer quando o resumo não fala da fonte. É um problema do codebook, não só do modelo, e o caminho é reescrever as definições, classificar de novo e medir outra vez (veja [Ler kappa e PABAK](../guias/ler-kappa-e-pabak.md#o-que-fazer-com-uma-variavel-fraca)).

O período analisado, uma variável de texto livre, também mostrou uma ambiguidade: resumos que dizem "a partir dos anos 1990" ou "nos últimos vinte anos" não têm um período fechado, e o codebook não diz como responder nesses casos.

## Limitações

- **Uma referência, não pessoas.** Até que alguém codifique a amostra, os números do piloto medem concordância com outro modelo.
- **200 documentos.** Categorias raras têm pouco suporte: o intervalo do kappa e o suporte por categoria vêm sempre ao lado.
- **Uma rodada.** O modelo foi medido com o codebook de exemplo, como ele está; um codebook revisado pede uma nova medida.
- **Resumos, não artigos.** Tanto o modelo quanto quem codifica leem só o título e o resumo. Uma categoria que o artigo deixa clara, mas o resumo não, sai "não informado" para os dois, e a concordância não mede isso.
