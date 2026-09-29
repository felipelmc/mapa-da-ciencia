# Seu primeiro mapa, parte 2: tópicos e mapa

Na [parte 1](primeiro-mapa.md) você coletou os 25 artigos que a *Opinião Pública* publicou em 2024. Para descobrir tópicos, é pouco: a etapa pede pelo menos 50 documentos, e os tópicos só ficam firmes a partir de algumas centenas. Nesta parte você amplia o recorte para toda a revista, de 2010 a 2025 (cerca de 400 artigos), descobre os temas desses artigos e navega pelo mapa no painel. Leva uns 15 minutos, sem contar o download dos modelos.

Os tópicos são descobertos no seu computador, por modelos que rodam no [Ollama](../guias/instalacao.md#2-ollama): nenhum texto sai da máquina.

!!! info "Antes de começar"
    - Você precisa do `mapa-da-ciencia` instalado e do Ollama aberto. Se fez a parte 1, já tem o primeiro.
    - Todos os comandos começam na pasta `mapa-da-ciencia` que você baixou. Se acabou de fazer a parte 1, volte para ela com `cd ../..`.
    - O modelo que escreve os rótulos dos tópicos no perfil padrão (`qwen3.5:9b`) precisa de uns 8 GB de memória livre. Com menos, dá para seguir o tutorial com rótulos feitos de palavras-chave (passo 3).

## 1. Confira os modelos

```bash
uv run mapa diagnostico
```

A seção **Modelos do perfil** lista os modelos sugeridos para a memória do seu computador. No perfil padrão, para 16 a 32 GB, a etapa de tópicos usa dois:

- `qwen3-embedding:0.6b` transforma cada artigo num vetor de números (o *embedding*); artigos sobre o mesmo assunto ganham vetores próximos;
- `qwen3.5:9b` lê as palavras-chave e os títulos de cada tópico e escreve um rótulo em português.

Se algum aparecer como ausente, baixe-o. São 0,6 GB e 6,6 GB:

```bash
ollama pull qwen3-embedding:0.6b
ollama pull qwen3.5:9b
```

O `diagnostico` também avisa quando a memória livre não basta para o modelo de rótulos. Nesse caso, feche programas pesados ou siga com `--sem-rotulos` no passo 3. O guia [Instalar e escolher os modelos](../guias/instalacao.md#3-escolha-um-perfil-de-modelos) mostra modelos menores para máquinas com pouca memória.

## 2. Amplie o recorte

```bash
uv run mapa novo projetos/op --revista op
cd projetos/op
uv run mapa coletar
```

Sem `--anos`, o recorte vai de 2010 a 2025, o padrão do modelo de projeto. A coleta leva um ou dois minutos na primeira vez e deve reunir perto de 400 artigos: quando escrevemos este tutorial, foram 396. O número pode variar um pouco, porque a revista continua publicando e a ArticleMeta corrige registros de vez em quando.

## 3. Gere os tópicos

```bash
uv run mapa topicos
```

Na primeira vez leva alguns minutos. O `mapa`:

1. monta o **texto de análise** de cada artigo: o título e o resumo em inglês. Na *Opinião Pública*, 388 artigos têm resumo em inglês; 7 entram com o resumo em português e 1 só com o título. Esses 8 ficam marcados no cartão do mapa;
2. calcula os **embeddings** e os guarda em `dados/embeddings/`;
3. projeta os vetores em duas dimensões, para o mapa, e procura **regiões densas** de artigos parecidos: cada região é um tópico;
4. extrai as **palavras-chave** que distinguem cada tópico dos outros;
5. agrupa os tópicos próximos em **macrotemas**, que dão as cores do mapa;
6. pede ao modelo de linguagem um **rótulo** e uma descrição curta para cada tópico e macrotema.

A saída começa com os números principais, seguidos da tabela dos macrotemas com os rótulos escritos pelo modelo:

```text
Tópicos prontos: 15 tópicos em 5 macrotemas, 396 documentos: 278 no núcleo, 86 reatribuídos, 32 sem
tópico (ARI 0,77), …
```

Os números podem mudar um pouco de uma máquina para outra, mas a leitura é a mesma:

- **núcleo**: os 278 artigos que estão bem dentro de algum tópico. São eles que definem as palavras-chave e os contornos do mapa;
- **reatribuídos**: 86 artigos que ficaram entre regiões e foram postos no tópico da maioria dos seus vizinhos mais parecidos;
- **sem tópico**: 32 artigos que não se parecem o bastante com nenhum grupo. Não é erro: são temas raros no recorte e aparecem no mapa em cinza;
- **ARI**: a estabilidade dos tópicos, de 0 a 1, quando o cálculo é repetido com outras sementes aleatórias. Com 400 artigos ela fica em 0,77: os temas grandes se repetem, mas as fronteiras entre temas vizinhos mudam. No projeto piloto, com 4.300 artigos de dez revistas, ela chega a 0,89.

A página [Como os tópicos são construídos](../explicacoes/topicos.md) explica cada passo em detalhe.

!!! tip "Sem memória para o modelo de rótulos?"
    Rode `uv run mapa topicos --sem-rotulos`. Os tópicos são os mesmos; só os rótulos passam a ser as três primeiras palavras-chave:

    ```text
    ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━┓
    ┃ Macrotema                             ┃ Tópicos ┃ Documentos ┃
    ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━┩
    │ ● política, democracia, confiança     │ 4       │ 103        │
    │ ● campanha, campanhas, twitter        │ 5       │ 87         │
    │ ● pública, brasileira, folha paulo    │ 3       │ 42         │
    │ ● deputados, ministérios, legislativo │ 2       │ 35         │
    │ ● deliberação, critérios, teoria      │ 1       │ 11         │
    └───────────────────────────────────────┴─────────┴────────────┘
    ```

    Quando a memória permitir, rode `uv run mapa topicos` de novo: só os rótulos são refeitos.

## 4. Rode de novo

```bash
uv run mapa topicos
```

Agora a etapa termina em segundos, e a saída diz:

```text
15 tópico(s) mantiveram o número e a cor da execução anterior.
Embeddings novos: 0 (os demais vieram do cache).
```

Os embeddings, as projeções e as respostas do modelo ficam guardados no projeto, e cada tópico mantém o seu **número e a sua cor** entre execuções. Quando uma coleta nova acrescentar artigos, os tópicos que continuarem existindo guardam o número, e um permalink antigo do mapa continua apontando para o mesmo tema.

## 5. Confira no status

```bash
uv run mapa status
```

A seção **Corpus** ganhou uma linha para os tópicos:

```text
Tópicos: 15 em 5 macrotemas (ARI 0,77); núcleo 70%, reatribuídos 22%, sem tópico 8%; rótulos: llm.
```

Se você coletar de novo e o corpus mudar, essa linha avisa que os tópicos ficaram desatualizados até a próxima execução de `mapa topicos`.

## 6. Explore o mapa

```bash
uv run mapa painel
```

Abra a vista **Mapa**. Cada ponto é um artigo, e artigos parecidos ficam perto uns dos outros. A imagem abaixo é o mapa do projeto piloto, com dez revistas; o da *Opinião Pública* tem menos pontos e menos tópicos, mas se lê do mesmo jeito.

<figure markdown="span">
  ![O mapa do piloto, com os pontos coloridos por tópico, os contornos dos tópicos e os rótulos dos macrotemas](../imagens/mapa.png){ loading=lazy }
  <figcaption>O mapa do piloto de ciência política. Os contornos envolvem os tópicos; os rótulos, com o zoom afastado, são os dos macrotemas.</figcaption>
</figure>

Experimente:

- **Aproxime** com a roda do mouse ou com o gesto de pinça. Com o zoom afastado aparecem os rótulos dos macrotemas; ao aproximar, os dos tópicos.
- **Clique num ponto.** O cartão ao lado mostra o título, os autores, o resumo e os cinco artigos mais parecidos, que também são clicáveis.
- **Busque** com ++slash++, por exemplo "polarização". O mapa fica só com os artigos encontrados.
- **Desenhe um laço** com ++l++ em volta de um grupo de pontos. O mapa fica só com eles, e a barra do recorte, no alto, mostra quantos são.
- **Aperte Tocar na linha do tempo** para ver os artigos aparecerem ano a ano.
- **Copie o endereço da página.** Ele guarda a câmera, o laço, os filtros e o artigo aberto. Quem abrir o link vê exatamente a mesma tela.

O guia [Ler o mapa](../guias/ler-o-mapa.md) explica o que a distância entre os pontos significa e o que ela não significa. Para encerrar, aperte ++ctrl+c++ no terminal.

## 7. Consulte os tópicos em Python

Cada artigo ganhou um tópico, que a [API Python](../referencia/api-python.md) expõe na tabela `atribuicoes`. Abra o Python com `uv run python` e veja quais tópicos mais cresceram na segunda metade do período:

```python
import mapa_da_ciencia.api as mapa

p = mapa.abrir()
crescimento = """
    SELECT a.topico,
           count(*) FILTER (WHERE d.ano < 2018) AS ate_2017,
           count(*) FILTER (WHERE d.ano >= 2018) AS desde_2018
    FROM atribuicoes a JOIN documentos d USING (id)
    WHERE a.topico >= 0
    GROUP BY a.topico
    ORDER BY desde_2018 - ate_2017 DESC
"""
mapa.consultar(p, crescimento)
```

O número do tópico é o mesmo do painel (o tópico −1 reúne os artigos sem tópico). No nosso teste, o que mais cresceu foi o de campanhas nas redes sociais, com Twitter e Facebook entre as palavras-chave: 5 artigos até 2017 e 23 desde 2018. Logo atrás veio um tópico sobre a direita e o eleitorado de Jair Bolsonaro, que não existia antes de 2018 (12 artigos).

## 8. Corrija um rótulo (opcional)

Os rótulos do modelo são um ponto de partida. Se algum não descreve bem o tópico, crie o arquivo `rotulos.yaml` na pasta do projeto com o número do tópico que aparece no painel:

```yaml
topicos:
  3:
    rotulo: Campanhas nas redes sociais
    descricao: Campanhas eleitorais e comunicação política no Twitter e no Facebook.
```

Escreva também a descrição: uma entrada só com o rótulo deixa o tópico sem descrição. Rode `uv run mapa topicos` de novo: o rótulo escrito à mão tem prioridade sobre o do modelo e fica marcado como manual.

## O que você fez

- Ampliou o recorte para 16 anos de uma revista.
- Descobriu os tópicos com modelos locais e leu os números de núcleo, ruído e estabilidade.
- Navegou pelo mapa, com busca, laço e linha do tempo, e consultou os tópicos em SQL.

## Próximos passos

- **O piloto inteiro.** Com as dez revistas de ciência política e relações internacionais, os tópicos ficam mais estáveis. Depois de coletar o piloto (veja os próximos passos da [parte 1](primeiro-mapa.md#proximos-passos)), gere os tópicos; os embeddings dos 4.300 artigos levam uns 4 minutos:

    ```bash
    cd ../..
    uv run mapa topicos -P projetos/cp-scielo
    ```

- **Ajustar os tópicos** (mais ou menos tópicos, outro idioma de análise): o guia [Gerar os tópicos](../guias/topicos.md#ajustar).
- **Por que estes parâmetros**, e como foram calibrados: [Como os tópicos são construídos](../explicacoes/topicos.md).
- Na [parte 3](primeiro-mapa-tempo-e-geografia.md), você vê como os tópicos mudam no tempo e de onde vêm os autores.
