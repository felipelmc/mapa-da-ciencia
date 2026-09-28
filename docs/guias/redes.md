# Gerar as redes

As redes de coautoria, de instituições, de estados e de citação saem do corpus, dos tópicos, da geografia e das
referências do OpenAlex. Para entender como, veja [Redes de coautoria e citação](../explicacoes/redes.md).

## Antes

- A coleta traz as referências do OpenAlex (`fontes.openalex.referencias`, ligado por padrão): cerca de 1 crédito a
  cada 100 artigos, mais 5 créditos para as obras mais citadas, só na primeira coleta. Ela também guarda as
  referências que a ArticleMeta lista (autores, título e ano de cada uma), lidas do cache, sem pedido nenhum: servem
  para medir a cobertura e conferir a autoria do cânone. Se só o lote das obras mais citadas falhar, as citações
  dentro do corpus valem e o aviso diz que o cânone ficou de fora. Um projeto coletado antes da
  versão 2.0 precisa de uma nova `mapa coletar` (o resto vem do cache).
- Os tópicos em dia (`mapa topicos`). A geografia é opcional: sem ela, as redes de instituições e de estados ficam de
  fora.

## Rodar

```bash
mapa redes
```

A etapa leva segundos e não usa modelo de linguagem. No fim, ela diz quantas pessoas e instituições colaboram, o
tamanho do maior componente, as comunidades e o cânone, e quantos pares de homônimos ficaram separados.

As redes ficam **desatualizadas** quando o corpus, as referências, os tópicos, a geografia ou o conteúdo do
`pessoas.yaml` mudam (refazer uma etapa com as mesmas entradas, ou um comentário no `pessoas.yaml`, não conta). Aí o
contrato deixa as redes antigas de fora, a vista Redes diz que elas estão desatualizadas e o que mudou, e o
`mapa status` mostra a etapa como desatualizada. Basta rodar `mapa redes` de novo (no painel, pela estação Redes da
vista Projeto). Um `mapa publicar` com as redes desatualizadas avisa e publica o site sem a vista Redes.

## Revisar os homônimos

```bash
mapa redes --revisar
```

Lista as pessoas que a etapa deixou separadas mas podem ser a mesma: primeiro os homônimos (o mesmo nome), depois as
grafias variantes ("Maria Souza" e "Maria Lima Souza"), e também as pessoas que ficaram com dois ORCIDs e
as autorias que perderam um ORCID de outro nome. Cada lado vem com as evidências para decidir: documentos, anos,
revistas, instituições, coautores e um título. No fim sai um bloco para o `pessoas.yaml` do projeto, com uma linha
comentada por par; descomente a linha na lista certa:

```yaml
fundir:                 # são a mesma pessoa
  - [openalex:A1111111111, openalex:A2222222222]
nao_fundir:             # são pessoas diferentes: saem da revisão, e uma fusão automática se desfaz
  - [openalex:A3333333333, openalex:A4444444444]
  - [openalex:A5555555555, S0011-52582020000100201#1]
nomes:                  # o nome a mostrar
  openalex:A1111111111: Maria da Silva
```

Qualquer id de uma autoria da pessoa serve: `openalex:A…`, `orcid:…`, `nome:…` (o nome sem acentos e sem
partículas, como `nome:maria silva`) ou `<documento>#<posição>`, que aponta uma autoria só (a posição do autor no
documento, a partir de 0) e serve para tirá-la de uma pessoa. Um id que não existe no corpus não quebra a etapa, mas
aparece num aviso ("falta o prefixo openalex:?"). Depois de editar, rode `mapa redes` de novo.

## Ler o resultado

No painel, a vista **Redes** tem quatro modos (Coautoria, Instituições, Estados e Citações), com o mesmo recorte das
outras vistas: filtrar os anos ou um tópico esmaece o que ficou de fora, sem mexer no desenho. Para ler cada modo,
veja [Ler as redes](ler-as-redes.md). Os dados ficam em `dados/redes/` (Parquet), para análises próprias, e viram
views com o prefixo `redes_` (`redes_pessoas`, `redes_arestas`, `redes_comunidades`, `redes_citacoes`,
`redes_canone`…) na conexão da API, de qualquer pasta:

```python
import mapa_da_ciencia.api as mapa

p = mapa.abrir("meu-projeto")
mapa.consultar(p, "SELECT titulo, ano, autores, n FROM redes_canone ORDER BY n DESC LIMIT 10")
```
