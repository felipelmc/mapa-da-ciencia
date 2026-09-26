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

## 3. Conferir

```bash
mapa status
```

O comando mostra o número de revistas e o período do recorte. Depois da coleta, ele mostra também quantos documentos entraram e quantos ficaram de fora por tipo ou ano.

## Dicas

- **Comece pequeno.** Uma revista e um ano bastam para conferir o caminho todo em poucos minutos, antes do corpus inteiro.
- **Áreas são amplas.** A grande área do SciELO ("Ciências Humanas") junta disciplinas muito diferentes. Para uma disciplina, prefira uma lista curada de revistas, como a do projeto piloto de ciência política.
- **Um projeto por pergunta.** Recortes diferentes pedem pastas diferentes: `mapa novo` cria outra em segundos.
