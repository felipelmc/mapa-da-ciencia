# Criar um projeto

Um projeto é uma **pasta** com a configuração do recorte (`mapa.yaml`), o codebook (`codebook.yaml`) e os dados de cada etapa. Cada pergunta de pesquisa ganha a sua própria pasta.

## Criar

```bash
mapa novo cp-scielo
```

O comando cria a pasta `cp-scielo/` a partir do modelo **ciencia-politica**: dez revistas brasileiras de ciência política e relações internacionais no SciELO, de 2010 a 2025. Esse é o piloto do projeto. Para começar com um arquivo mínimo, use `--modelo vazio`.

Os modelos de linguagem do `mapa.yaml` vêm do perfil sugerido para a sua máquina. Para escolher outro perfil, use `--perfil leve`, `padrao` ou `forte` (veja [Instalar e escolher os modelos](instalacao.md#3-escolha-um-perfil-de-modelos)).

## O que tem na pasta

```
cp-scielo/
  mapa.yaml        configuração do recorte (edite)
  codebook.yaml    variáveis da classificação (edite)
  .env.exemplo     modelo do .env, para e-mail de contato e chave do OpenAlex
  .gitignore       mantém dados e segredos fora do git
  brutos/          respostas das APIs, guardadas para não baixar de novo
  dados/           tabelas do corpus e embeddings
  execucoes/       um registro (manifesto) por execução de cada etapa
  saida/           arquivos que o painel lê e o site publicado
```

A configuração e o codebook podem ir para o git. Os dados ficam de fora: são grandes e podem ser recriados a partir das fontes e dos manifestos (veja [Reprodutibilidade](../explicacoes/reprodutibilidade.md)).

## Editar o `mapa.yaml`

O arquivo vem comentado. As partes que você mais vai mexer:

```yaml
fontes:
  scielo:
    colecao: scl            # SciELO Brasil
    revistas:               # ISSN como aparece no SciELO
      - 0104-6276           # Opinião Pública
      - 0011-5258           # Dados
recorte:
  anos: [2010, 2025]
```

- **Revistas:** use o ISSN da revista no SciELO. O comando `mapa revistas` procura revistas por título ou área e imprime as linhas prontas para colar (veja [Montar um recorte](recorte.md)).
- **Anos:** primeiro e último ano de publicação, inclusive.
- **Idiomas:** `idioma_analise: en` usa os resumos em inglês nos embeddings, porque eles cobrem quase todo o corpus. `idioma_exibicao: pt` mostra os resumos em português. O porquê está no registro de decisão [0004](../decisoes/0004-embeddings-e-idioma-de-analise.md).

A lista completa de campos está na [referência do `mapa.yaml`](../referencia/configuracao.md). Se algo estiver errado, os comandos dizem qual campo e por quê:

```
Erro: mapa.yaml tem 2 problema(s):
  - recorte.anos: use [ano_inicial, ano_final], com o inicial menor ou igual ao final
  - fontes.scielo.revistaz: campo desconhecido (erro de digitação?)
```

## Acompanhar

Dentro da pasta do projeto (ou em qualquer subpasta):

```bash
mapa status
```

O comando mostra o recorte, os modelos e em que ponto está cada etapa: coleta, embeddings, tópicos, classificação, geografia, validação e exportação. Fora da pasta, indique o projeto com `--projeto` (`-P`): `mapa status -P cp-scielo`.

## Próximo passo

Ajuste o [recorte](recorte.md) e rode `mapa coletar`. Antes de classificar, revise o [codebook](codebook.md).
