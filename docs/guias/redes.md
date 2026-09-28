# Gerar as redes

As redes de coautoria, de instituições, de estados e de citação saem do corpus, dos tópicos, da geografia e das
referências do OpenAlex. Para entender como, veja [Redes de coautoria e citação](../explicacoes/redes.md).

## Antes

- A coleta traz as referências do OpenAlex (`fontes.openalex.referencias`, ligado por padrão): cerca de 1 crédito a
  cada 100 artigos, mais 5 créditos para as obras mais citadas, só na primeira coleta. Um projeto coletado antes da
  versão 2.0 precisa de uma nova `mapa coletar` (o resto vem do cache).
- Os tópicos em dia (`mapa topicos`). A geografia é opcional: sem ela, as redes de instituições e de estados ficam de
  fora.

## Rodar

```bash
mapa redes
```

A etapa leva segundos e não usa modelo de linguagem. No fim, ela diz quantas pessoas e instituições colaboram, o
tamanho do maior componente, as comunidades e o cânone, e quantos pares de homônimos ficaram separados.

## Revisar os homônimos

```bash
mapa redes --revisar
```

Lista os pares de pessoas com o mesmo nome que a etapa manteve separadas, com um bloco para o `pessoas.yaml` do
projeto:

```yaml
fundir:                 # são a mesma pessoa
  - [orcid:0000-0000-0000-0000, nome:maria silva]
nao_fundir:             # são pessoas diferentes (não aparecem mais na revisão)
  - [openalex:A123, openalex:A456]
nomes:                  # o nome a mostrar
  orcid:0000-0000-0000-0000: Maria da Silva
```

Depois de editar, rode `mapa redes` de novo.

## Ler o resultado

No painel, a vista **Redes** tem quatro modos (Coautoria, Instituições, Estados e Citações), com o mesmo recorte das
outras vistas: filtrar os anos ou um tópico esmaece o que ficou de fora, sem mexer no desenho. Para ler cada modo,
veja [Ler as redes](ler-as-redes.md). Os dados ficam em `dados/redes/` (Parquet), para análises próprias:

```python
import mapa_da_ciencia.api as mapa

p = mapa.abrir("meu-projeto")
mapa.consultar(p, "SELECT titulo, ano, n FROM read_parquet('dados/redes/canone.parquet') ORDER BY n DESC LIMIT 10")
```
