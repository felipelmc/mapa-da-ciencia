# Montar um recorte

O recorte define **quais artigos entram no corpus**: de quais revistas, de quais anos e de quais tipos. Ele fica na seção `fontes` e `recorte` do `mapa.yaml` do projeto.

## 1. Escolher as revistas

O `mapa` traz um retrato das revistas correntes do SciELO Brasil. Para procurar:

```bash
mapa revistas politica                 # título, acrônimo ou categoria com "politica"
mapa revistas --area humanas           # todas as revistas de Ciências Humanas
mapa revistas saude --area "saude"     # combinando os dois
```

A busca ignora acentos e maiúsculas. A tabela mostra o acrônimo, o ISSN usado pelo SciELO, o título, a grande área e a licença da revista.

Quando tiver a lista, peça as linhas prontas para colar no `mapa.yaml`:

```bash
mapa revistas politica --yaml
```

```yaml
      - 0103-3352           # Revista Brasileira de Ciência Política
      - 0104-6276           # Opinião Pública
```

!!! note "Revistas descontinuadas"
    O retrato vem da ArticleMeta, que só lista revistas **correntes**. Uma revista que deixou o SciELO não aparece no `mapa revistas`. Se você souber o ISSN dela, pode colocá-lo no `mapa.yaml` mesmo assim.

## 2. Ajustar o `mapa.yaml`

```yaml
fontes:
  scielo:
    colecao: scl                       # SciELO Brasil
    revistas:
      - 0103-3352                      # Revista Brasileira de Ciência Política
      - 0104-6276                      # Opinião Pública
    tipos: [research-article, review-article]

recorte:
  anos: [2010, 2025]
```

- **`revistas`**: o ISSN impresso, o online ou o do SciELO. O `mapa` reconhece os três.
- **`anos`**: primeiro e último ano de publicação, inclusive. O ano sai do identificador do artigo no SciELO (o PID), porque a API não filtra por ano de publicação (veja [Fontes de dados](../explicacoes/fontes.md)).
- **`tipos`**: por padrão, artigos de pesquisa e de revisão. Resenhas (`book-review`), editoriais (`editorial`), erratas (`correction`) e outros tipos ficam de fora. Para incluí-los, acrescente o tipo à lista.

Para já criar o projeto com o recorte certo, sem editar o YAML:

```bash
mapa novo meu-projeto --revista op --revista dados --anos 2010-2025
```

## 3. Coletar

Dentro da pasta do projeto:

```bash
mapa coletar
```

O `mapa` lista os artigos de cada revista na ArticleMeta, baixa o registro de cada um, normaliza e grava o corpus em `dados/documentos.parquet`. No fim, mostra quantos documentos entraram por revista e quantos ficaram de fora (outros anos, outros tipos).

| Opção | Para quê |
|---|---|
| `--revista op` (repetível) | Coleta só estas revistas, nesta execução, sem mudar o `mapa.yaml` |
| `--anos 2024` ou `--anos 2010-2025` | Coleta só este período, nesta execução |
| `--limite 20` | Só os 20 primeiros artigos: bom para testar o caminho todo em segundos |
| `--atualizar` | Baixa de novo as listas de artigos, para pegar publicações novas |
| `--offline` | Não acessa a internet: monta o corpus só com o que já está guardado |

**Pode interromper.** Cada registro é guardado assim que chega (em `brutos/`). Se a coleta for interrompida (Ctrl+C, queda de rede), rodar `mapa coletar` de novo continua de onde parou. Rodar depois de terminada não faz nenhuma requisição: tudo vem do que já foi guardado.

**Quanto tempo leva:** a ArticleMeta responde uns 3 registros por segundo com 4 requisições simultâneas. Uma revista-ano leva segundos; o piloto inteiro (cerca de 5 mil artigos), uns 30 minutos na primeira vez.

## 4. Conferir

```bash
mapa status
```

O comando mostra o recorte e em que ponto está cada etapa. A tabela com a cobertura do corpus (resumos por idioma, DOI, afiliações, licenças) aparece depois da coleta.

## Dicas

- **Comece pequeno.** Uma revista e um ano bastam para conferir o caminho todo em poucos minutos, antes do corpus inteiro.
- **Áreas são amplas.** A grande área do SciELO ("Ciências Humanas") junta disciplinas muito diferentes. Para uma disciplina, prefira uma lista curada de revistas, como a do projeto piloto de ciência política.
- **Um projeto por pergunta.** Recortes diferentes pedem pastas diferentes: `mapa novo` cria outra em segundos.
