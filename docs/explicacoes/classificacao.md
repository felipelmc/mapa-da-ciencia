# Classificação ancorada em evidência

A classificação responde, para cada resumo, às perguntas de um codebook: a abordagem do estudo, a técnica, o recorte geográfico e o que mais o pesquisador definir. Quem responde é um modelo de linguagem pequeno, rodando no notebook (`qwen3.5:9b` no perfil padrão). Esta página explica como a resposta é pedida, conferida e guardada, e o que isso garante e não garante. As decisões estão no [ADR 0011](../decisoes/0011-classificacao-ancorada-em-evidencia.md); o passo a passo, em [Classificar os resumos](../guias/classificar.md).

## O que o modelo lê

O modelo lê o **título e o resumo** de cada documento, no idioma em que o painel os mostra (português no piloto, com o inglês como reserva). É o mesmo texto do cartão do mapa, e por isso o trecho citado pode ser marcado ali. Documentos sem resumo não são classificados e aparecem na cobertura.

Cada pedido tem duas mensagens:

1. uma **mensagem de sistema fixa**, igual para todos os documentos: as instruções do codebook, as regras da evidência e, para cada variável, a pergunta e as categorias com as definições e os exemplos;
2. a **mensagem do documento**, só com "Título: …" e "Resumo: …".

Como a primeira mensagem não muda, o Ollama reaproveita o processamento dela de um documento para o outro, e só o documento é lido de novo.

## Evidência antes do valor

A resposta tem um formato fixo (um JSON Schema gerado do codebook). Para cada variável, o modelo escreve primeiro a **evidência**, um trecho de até 20 palavras copiado do título ou do resumo, e só depois o **valor**. Escrever o trecho antes ancora a resposta no texto: o modelo decide olhando para o que acabou de citar.

A evidência pode ficar vazia quando a resposta é "sem informação" (`nao_informado`, `nao_se_aplica` ou "não", nas booleanas): não há o que citar.

## A conferência

O `mapa` confere cada evidência contra o texto, sem depender do modelo:

| Status | Quando | No piloto (amostra de 200) |
|---|---|---|
| `literal` | o trecho está no título ou no resumo, a menos de maiúsculas, espaços, aspas e tipo de traço | 94,8% das evidências |
| `aproximada` | 90% dos caracteres do trecho casam em blocos com um pedaço do texto de tamanho parecido (o modelo trocou uma palavra), ou o trecho foi cortado com reticências e cada pedaço está no texto | 3,5% |
| `ausente` | o trecho não está no texto | 1,7% |
| `dispensada` | evidência vazia numa resposta sem informação | 258 das 1.200 respostas |

Nos dois primeiros casos, a posição do trecho no texto fica guardada, e o painel o marca no resumo. Uma evidência ausente não quer dizer que a resposta está errada, mas que ela não está ancorada: vale ler o resumo.

## Nova tentativa

Quando a resposta foge do codebook (uma categoria que não existe, uma variável faltando) ou alguma evidência sai ausente, o `mapa` pede de novo, uma vez, com uma mensagem que aponta o problema. Fica a melhor das duas respostas. No piloto, todas as respostas vieram em JSON válido já na primeira tentativa, e a segunda foi usada em 43 dos 200 documentos da amostra, quase sempre por uma evidência que não estava no texto.

## Cache e retomada

Cada resposta aceita vai para o `estado.sqlite` do projeto assim que chega. A chave junta o texto, o que o modelo lê (a mensagem de sistema e o esquema), o modelo com a versão exata (o *digest* do Ollama), a versão do prompt e os parâmetros. Por isso:

- uma interrupção (++ctrl+c++, falta de memória, `kill -9`) não perde nada, e a próxima execução continua de onde parou;
- mudar uma definição, o modelo ou os parâmetros refaz tudo, de propósito;
- mudar só o que o modelo não lê (a versão do codebook, os rótulos de exibição) reaproveita as respostas.

Com temperatura zero e semente fixa, o mesmo modelo tende a dar a mesma resposta, mas o cache é o que garante que um resultado publicado possa ser reconstruído.

## Tempo e memória

No Mac de desenvolvimento (M4 Pro, 24 GB), cada resumo levou 10,8 segundos (mediana) na amostra do piloto, e 16,6 s no 90º percentil. O tempo vem quase todo da escrita da resposta: seis variáveis, cada uma com um trecho citado. Para os 4.247 artigos com resumo do piloto, são cerca de 12 horas, numa execução que pode ser interrompida e retomada. `mapa classificar --estimar` mede o tempo na sua máquina antes.

O modelo ocupa uns 7 GB. A etapa só o carrega se houver algo a classificar, confere a memória entre um documento e outro (e para, com uma explicação, se ela acabar) e o descarrega no fim.

## O que a evidência não garante

A evidência mostra **de onde** o modelo tirou a resposta, não que a resposta está certa. O modelo pode citar o trecho certo e escolher a categoria errada, ou interpretar uma definição de outro jeito. Na amostra do piloto, a técnica de pesquisa teve evidência literal em 98% das respostas e, ainda assim, a concordância mais baixa com a leitura de referência (veja [Desenho da validação](validacao.md)). Por isso a classificação vem sempre com a validação.
