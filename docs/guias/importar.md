# Importar uma busca do search.scielo.org

Quando o recorte não é "estas revistas nestes anos", mas "os artigos que respondem a esta busca", monte a busca no [search.scielo.org](https://search.scielo.org), exporte o resultado e importe o arquivo no projeto. Também dá para importar uma lista de DOIs ou PIDs de qualquer origem.

!!! note "Por que não buscar direto pelo `mapa`?"
    O search.scielo.org bloqueia acessos automatizados com um desafio anti-robô. No navegador ele funciona normalmente, e a exportação traz tudo o que o `mapa` precisa: o identificador de cada artigo no SciELO e o DOI.

## 1. Exportar a busca

1. Faça a busca em [search.scielo.org](https://search.scielo.org), com os filtros que quiser (coleção, ano, área, idioma).
2. Na barra de resultados, clique em **Exportar**.
3. Escolha o formato: **RIS**, **CSV** ou **BibTeX**. Os três funcionam; o RIS e o BibTeX trazem também o DOI.
4. Escolha **Todos os registros**. A exportação vai até **2.000 artigos**. Para buscas maiores, divida por ano ou por coleção e exporte cada parte.

## 2. Importar no projeto

```bash
mapa importar ~/Downloads/export.ris
```

O `mapa` lê o arquivo, mostra quantos artigos reconheceu e roda a coleta:

```
✓ export.ris: 312 registro(s): 298 com PID, 10 só com DOI, 4 sem identificador
```

O arquivo é copiado para a pasta `importados/` do projeto e passa a entrar em **toda** coleta daquele projeto, junto com as revistas do `mapa.yaml` (se houver). Para só copiar, sem coletar agora, use `--nao-coletar`.

## O que acontece com cada artigo

- **Com identificador do SciELO** (a maioria): o registro completo vem da ArticleMeta, na coleção certa (Brasil, Argentina, Colômbia, Portugal, PePSIC...), com as mesmas regras da coleta por revista.
- **Só com DOI**: o `mapa` procura o DOI no OpenAlex. Se o OpenAlex apontar um artigo do SciELO, o registro completo vem da ArticleMeta. Senão, o documento é montado com os dados do próprio OpenAlex. É o caso dos preprints do SciELO Preprints.
- **Recorte:** os artigos importados também passam pelo recorte de anos e de tipos do `mapa.yaml`. Preprints, por exemplo, ficam de fora, a menos que você acrescente `preprint` em `fontes.scielo.tipos`.
- **Duplicatas:** um artigo que já veio da coleta por revista é reconhecido e fundido, e o documento passa a registrar as duas origens.

A busca no OpenAlex por DOI custa 1 crédito a cada 50 artigos (veja [Fontes de dados](../explicacoes/fontes.md)).

## Listas de DOIs ou PIDs

Um arquivo `.txt` com um identificador por linha também serve:

```text
# linhas começando com # são ignoradas
10.1590/1807-019120243011
https://doi.org/10.1590/SciELOPreprints.17844
S0104-62762024000100200
```

Planilhas em CSV também funcionam, com vírgula ou ponto e vírgula, inclusive as salvas pelo Excel. O `mapa` procura colunas chamadas ID, PID, DOI, URL, título e ano, e também encontra PIDs e DOIs em qualquer coluna.

## Projeto só com artigos importados

Se o recorte for só a busca, sem revistas, deixe a lista de revistas vazia no `mapa.yaml`:

```yaml
fontes:
  scielo:
    revistas: []
```
