# Seu primeiro mapa, parte 3: tempo e geografia

Na [parte 2](primeiro-mapa-topicos.md) você descobriu os tópicos dos cerca de 400 artigos que a *Opinião Pública* publicou de 2010 a 2025. Nesta parte você vê **como esses temas mudam no tempo** e **de onde vêm os autores**: liga as afiliações a instituições, corrige o que não casou e explora as vistas Tópicos e Geografia do painel. Leva uns 15 minutos e não usa modelos de linguagem.

!!! info "Antes de começar"
    - Você precisa ter feito a parte 2, com os tópicos gerados em `projetos/op`.
    - Todos os comandos rodam na pasta do projeto. Se você está na pasta `mapa-da-ciencia`, entre nela:

        ```bash
        cd projetos/op
        ```

## 1. Atualize a coleta, se ela é antiga

A geografia usa os registros das instituições do OpenAlex, que a coleta busca desde a versão 0.4.0. Se você fez a parte 2 com uma versão anterior, colete de novo. As respostas da ArticleMeta vêm do cache, e o OpenAlex gasta uns 2 créditos:

```bash
uv run mapa coletar
```

## 2. Gere a geografia

```bash
uv run mapa geografia
```

A etapa leva menos de um segundo. A saída começa assim:

```text
Geografia pronta: 859 vínculos de 396 documentos, 94,4% ligados a uma de 145 instituições; país conhecido
em 99,8% do peso e UF em 97,1% do peso brasileiro, em 0,2 s.
```

Um **vínculo** é um autor ligado a uma afiliação. O `mapa` casou cada afiliação com uma instituição do OpenAlex: 98% das afiliações normalizadas pelo SciELO (`v240`) e 86% das escritas como texto livre (`v70`). Depois vem a tabela das instituições com mais **peso**:

```text
│ Universidade Federal de Minas Gerais (UFMG) │ MG, BR │ 50,1 │ 65 │
│ Universidade de São Paulo (USP)             │ SP, BR │ 37,8 │ 52 │
│ Universidade de Brasília (UnB)              │ DF, BR │ 31,6 │ 38 │
```

O peso é a **contagem fracionária**: cada artigo vale 1, dividido entre os autores e, para cada autor, entre as afiliações dele. A UFMG tem 50,1 de peso em 65 artigos: em muitos deles, divide a autoria com outras instituições. A página [Geografia da produção](../explicacoes/geografia.md) explica o casamento e a contagem.

## 3. Corrija o que não casou

```bash
uv run mapa geografia --revisar --limite 8
```

A revisão lista as afiliações sem instituição mais frequentes, com as instituições conhecidas mais parecidas:

```text
│ Centro de Formação da Câmara dos Deputados │ 6 │ 3 │ BR │ —                                 │
│ Instituto Nacional de Ciência e Tecnologia │ 3 │ 2 │ BR │ —                                 │
│ em Democracia Digital                      │   │   │    │                                   │
│ Instituto Universitário de Lisboa          │ 2 │ 2 │ PT │ Universidade de Lisboa (PT, 0,55) │
```

No fim vem um bloco para o arquivo `instituicoes.yaml`, com um modelo de instituição própria para cada texto sem sugestão. Crie o arquivo `instituicoes.yaml` na pasta do projeto com as duas primeiras:

```yaml
apelidos:
  "Centro de Formação da Câmara dos Deputados": cefor
  "Instituto Nacional de Ciência e Tecnologia em Democracia Digital": inct-dd
instituicoes:
  cefor:
    nome: Centro de Formação, Treinamento e Aperfeiçoamento da Câmara dos Deputados
    sigla: Cefor
    pais: BR
    uf: DF
  inct-dd:
    nome: Instituto Nacional de Ciência e Tecnologia em Democracia Digital
    sigla: INCT.DD
    pais: BR
    uf: BA
```

A terceira sugestão está errada: o Instituto Universitário de Lisboa é o Iscte, e não a Universidade de Lisboa. **Confira cada sugestão** antes de usá-la; o guia [Gerar a geografia](../guias/geografia.md#corrigir-o-que-nao-casou) mostra como.

Rode a etapa de novo, e os dois textos passam a contar para as instituições que você declarou:

```bash
uv run mapa geografia
```

## 4. Confira no status

```bash
uv run mapa status
```

A seção **Corpus** ganhou uma linha para a geografia, abaixo da dos tópicos:

```text
Geografia: 95,6% dos 859 vínculos ligados a uma de 147 instituições; país conhecido em 99,8% do peso, UF em
97,4% do peso brasileiro.
```

Se você coletar de novo ou mudar o `instituicoes.yaml`, essa linha avisa que a geografia ficou para trás até a próxima execução de `mapa geografia`.

## 5. Veja os tópicos no tempo

```bash
uv run mapa painel
```

Abra a vista **Tópicos**. O fluxo mostra os cinco macrotemas ano a ano; troque para o modo **100%** para ver a participação de cada um. Clique no macrotema de comunicação política e eleições para abrir os tópicos dele (o nome foi escrito pelo modelo de linguagem, e o seu pode ser outro).

Abaixo do fluxo, a lista **em alta e em queda** mostra os tópicos cuja participação mudou de forma distinguível do acaso. Na *Opinião Pública*, três estão em alta, todos ligados às eleições recentes: a direita radical e o voto bolsonarista (+15,8 pontos percentuais de 2010 a 2025), a comunicação política em redes sociais (+14,8) e a direita brasileira (+6,7). A deliberação em ambientes online está em queda (−8,1). Clique num deles para abrir a gaveta, com a série, as palavras-chave e os artigos representativos.

O guia [Ler os tópicos no tempo](../guias/ler-os-topicos.md) explica os modos e por que a lista pede cuidado.

## 6. Veja a geografia

Abra a vista **Geografia**:

- o **mapa das UFs** colore cada estado pelo peso; na *Opinião Pública*, São Paulo, Minas Gerais e o Distrito Federal vêm à frente;
- o **ranking** lista as instituições, com a UFMG no topo;
- o **mapa-múndi** mostra os coautores de fora do Brasil (Estados Unidos, Chile, Espanha, México, Portugal), com o Brasil fora da escala;
- a **cobertura por ano** mostra quanto do peso tem instituição identificada em cada ano.

Agora **clique em Minas Gerais**. A UF vai para a barra do recorte, e o ranking passa a mostrar só os artigos com algum autor mineiro, com os coautores de fora. Vá para a vista **Tópicos** pelo trilho: o recorte vai junto, e o fluxo mostra os temas dos artigos com autores de Minas. O × no chip tira a UF do recorte.

O guia [Ler a geografia](../guias/ler-a-geografia.md) explica cada gráfico e o que ele não diz. Para encerrar o painel, aperte ++ctrl+c++ no terminal.

## 7. Consulte em Python

A contagem fracionária fica na tabela `pesos` da [API Python](../referencia/api-python.md#tabelas-para-consulta). Abra o Python com `uv run python`:

```python
import mapa_da_ciencia.api as mapa

p = mapa.abrir()
por_uf = """
    SELECT uf, round(sum(peso), 1) AS peso, count(DISTINCT doc) AS documentos
    FROM pesos WHERE pais = 'BR' AND uf IS NOT NULL
    GROUP BY uf ORDER BY peso DESC LIMIT 5
"""
mapa.consultar(p, por_uf)
```

Na *Opinião Pública*, São Paulo soma 66,4 de peso em 88 artigos, Minas Gerais 57,6 em 74 e o Distrito Federal 53,0 em 70 (com o Cefor que você declarou). A tabela `vinculos` guarda cada autor ligado a uma instituição, com o texto da fonte e como o casamento foi feito, e `instituicoes` guarda os nomes, siglas e lugares.

## O que você fez

- Ligou as afiliações dos autores a instituições, com UF e país, e leu a contagem fracionária.
- Corrigiu as afiliações que não casaram com um `instituicoes.yaml`.
- Viu os tópicos que mais cresceram e a geografia da produção no painel, e levou um recorte de uma vista para outra.

## Próximos passos

- **O piloto inteiro.** Com as dez revistas, a geografia fica mais rica: 636 instituições, com a USP, a UnB e a UFMG à frente.

    ```bash
    cd ../..
    uv run mapa geografia -P projetos/cp-scielo
    ```

- **Por que estes limiares**, e como a precisão foi medida: [Geografia da produção](../explicacoes/geografia.md).
- A [parte 4](primeiro-mapa-classificacao.md) **classifica** os resumos com um codebook e mede a concordância numa amostra.
