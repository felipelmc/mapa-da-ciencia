# Escrever um codebook

O codebook (`codebook.yaml`) define **o que o modelo vai responder sobre cada resumo**. É o mesmo instrumento de uma análise de conteúdo feita por pessoas: variáveis, categorias e definições. A diferença é que quem lê as definições é um modelo de linguagem, e depois você mede o quanto ele concorda com a sua própria codificação.

`mapa novo` cria um codebook de exemplo para ciência política, com seis variáveis: abordagem, técnica, recorte geográfico, Brasil como caso, subárea e período analisado. **Trate esse codebook como ponto de partida.** As variáveis certas dependem da sua pergunta de pesquisa.

## Anatomia

```yaml
nome: meu-codebook
versao: "0.1"
instrucoes: >
  Você é um assistente de pesquisa que codifica resumos de artigos científicos. Para cada
  variável, copie primeiro, como evidência, um trecho literal do resumo que justifique a
  escolha, e só então informe o valor.

variaveis:
  - id: abordagem
    rotulo: Abordagem metodológica
    tipo: categorica
    pergunta: Qual é a abordagem metodológica principal do estudo?
    categorias:
      - valor: quantitativa
        definicao: Análise baseada principalmente em dados numéricos e técnicas estatísticas.
      - valor: qualitativa
        definicao: Análise baseada principalmente em dados não numéricos.
      - valor: nao_informado
        rotulo: Não informado    # opcional: como a categoria aparece no painel
        definicao: O resumo não permite identificar a abordagem.
```

O `valor` de cada categoria é um identificador sem acentos nem espaços; o `rotulo`, opcional, é como ela aparece no painel e nos relatórios (sem ele, o painel mostra o `valor` com espaços no lugar dos `_`).

Há quatro tipos de variável:

| Tipo | Resposta | Exemplo |
|---|---|---|
| `categorica` | exatamente uma categoria | abordagem, subárea |
| `multipla` | uma ou mais categorias | fontes de dados usadas |
| `booleana` | sim ou não | o Brasil é um caso analisado? |
| `texto` | resposta livre e curta | período analisado ("1994–2018") |

Todos os campos estão na [referência do codebook](../referencia/codebook.md).

## Como o modelo responde

Para cada variável, o modelo devolve um par **evidência + valor**, nessa ordem. A evidência é um trecho copiado do resumo, e o `mapa` confere se o trecho existe de fato no texto (literal, aproximado ou ausente). Pedir a evidência antes do valor faz o modelo se ancorar no texto, e a conferência mostra quando ele inventa. No painel, a evidência aparece destacada no próprio resumo.

## Recomendações

- **Uma pergunta por variável.** "Qual é o método e o recorte?" vira duas variáveis.
- **Categorias mutuamente exclusivas** nas variáveis `categorica`. Se dois valores se sobrepõem, o modelo e as pessoas vão discordar justamente ali. Use `multipla` quando a sobreposição for real.
- **Definições operacionais, não só nomes.** Em vez de "quantitativa", escreva "análise baseada principalmente em dados numéricos e técnicas estatísticas (surveys, regressões, séries eleitorais...)". O modelo lê a definição, e não apenas o rótulo.
- **Inclua uma saída** como `nao_informado` ou `outra`. Resumos são curtos: sem uma categoria para "não dá para saber", o modelo é forçado a chutar.
- **Escreva para quem nunca viu o seu projeto.** Se uma pessoa da sua área não conseguiria codificar só com as definições, o modelo também não vai conseguir.
- **Poucas variáveis bem definidas** valem mais que muitas vagas. Cada variável é validada separadamente, e as de baixa concordância precisam de revisão.
- **Teste em poucos resumos antes do corpus todo:** `mapa classificar --limite 20` (veja [Classificar os resumos](classificar.md)).

## Versões e reprodutibilidade

Mude o campo `versao` sempre que alterar uma definição. O `mapa` calcula um *hash* do conteúdo inteiro do codebook, e toda classificação fica associada a esse hash. Assim, resultados de versões diferentes do codebook nunca se misturam, e o manifesto de cada execução registra qual versão foi usada (veja [Reprodutibilidade](../explicacoes/reprodutibilidade.md)).

As respostas do modelo ficam guardadas pelo que ele lê: as instruções e, de cada variável, o rótulo, a pergunta, as definições e os exemplos. Mudar só o que ele não lê (a `versao`, o `nome`, os rótulos das categorias) cria um resultado novo: até a próxima `mapa classificar`, a classificação fica desatualizada (o painel e o site deixam de mostrá-la), e essa próxima execução a monta a partir das respostas guardadas, em segundos. Mudar uma definição, uma pergunta ou o rótulo de uma variável refaz a classificação inteira (cerca de 10 horas no piloto, com 4.247 resumos). Nos dois casos, o júri precisa ser refeito (`mapa juri votar`, que também monta os votos das respostas guardadas quando pode).
