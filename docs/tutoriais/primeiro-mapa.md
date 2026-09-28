# Seu primeiro mapa, parte 1: a coleta

Neste tutorial você monta um corpus de verdade: os artigos da revista *Opinião Pública* publicados em 2024. No fim, você terá um projeto com 25 artigos, com títulos, resumos, autores, afiliações e licenças, e saberá conferir a cobertura desses dados. Leva uns 10 minutos.

A parte 1 não usa modelos de linguagem: só precisa de internet, para consultar a [ArticleMeta](../explicacoes/fontes.md) do SciELO e o OpenAlex. A [parte 2](primeiro-mapa-topicos.md) descobre os tópicos e monta o mapa; a [parte 3](primeiro-mapa-tempo-e-geografia.md) mostra os tópicos no tempo e a geografia; e a [parte 4](primeiro-mapa-classificacao.md) classifica os resumos com um codebook e mede a concordância.

!!! info "Antes de começar"
    Você precisa do `mapa-da-ciencia` instalado. Se ainda não instalou, siga os passos 1 e 2 de [Explorar o exemplo](explorar-exemplo.md) e volte para cá.

    Os comandos abaixo são os de quem instalou **pelo código**: começam com `uv run` e rodam dentro da pasta `mapa-da-ciencia` que você baixou. Quando o próprio `mapa` sugerir um próximo passo (por exemplo, `mapa status`), ponha `uv run` na frente. Se instalou **pelo *wheel***, digite só `mapa` (sem `uv run`), em qualquer pasta. Nos passos em Python, troque `uv run python` por `uv run --no-project --with "https://github.com/felipelmc/mapa-da-ciencia/releases/download/v1.0.1/mapa_da_ciencia-1.0.1-py3-none-any.whl" python`, que abre um Python com o pacote (o `uv tool install` deixa o `mapa` num ambiente só dele).

## 1. Escolha a revista

O `mapa` traz a lista das revistas correntes do SciELO Brasil. Procure pela revista:

```bash
uv run mapa revistas "opinião pública"
```

A linha da revista mostra o ISSN (`0104-6276`) e o acrônimo (`op`). Os dois servem para identificá-la nos próximos comandos.

## 2. Crie o projeto

```bash
uv run mapa novo projetos/op-2024 --revista op --anos 2024
```

O comando cria a pasta `projetos/op-2024` com dois arquivos de configuração:

- `mapa.yaml`: o recorte (revistas e anos), as fontes e os modelos;
- `codebook.yaml`: as variáveis da classificação, usadas na parte 4.

Abra o `mapa.yaml` num editor. As opções `--revista` e `--anos` já deixaram o recorte pronto:

```yaml
fontes:
  scielo:
    colecao: scl            # SciELO Brasil
    revistas:               # ISSN como aparece no SciELO
      - 0104-6276           # Opinião Pública
...
recorte:
  anos: [2024, 2024]
```

Entre na pasta do projeto. Daqui em diante, os comandos valem para ele:

```bash
cd projetos/op-2024
```

!!! tip "Identifique-se para as APIs (opcional)"
    A ArticleMeta e o OpenAlex pedem que quem faz muitas consultas se identifique. O `mapa novo` deixou na pasta do projeto um modelo, `.env.exemplo`. Copie-o para `.env` e preencha o seu e-mail:

    ```bash
    cp .env.exemplo .env
    ```

    Depois, abra o `.env` num editor de texto e complete a linha `MAPA_EMAIL=` (por exemplo, `MAPA_EMAIL=voce@exemplo.org`). O e-mail vai só no cabeçalho das requisições, e o `.env` fica fora do git (`mapa novo` já o colocou no `.gitignore`). Sem ele, a coleta funciona igual: é uma cortesia com as APIs, que respondem a quem se identifica.

## 3. Colete

```bash
uv run mapa coletar
```

Em alguns segundos, o `mapa`:

1. lista na ArticleMeta todos os artigos da revista e separa os de 2024 pelo identificador (o PID);
2. baixa o registro completo de cada um e o normaliza: títulos e resumos em cada idioma, palavras-chave, autores com ORCID e afiliações;
3. deixa de fora resenhas, editoriais e outros tipos que não são artigos;
4. liga cada artigo ao OpenAlex, que acrescenta as citações recebidas e a licença de cada artigo.

A saída termina assim:

```text
Coleta concluída em 7,2 s: 25 documento(s) de 1 revista(s), 2024.
┏━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Revista ┃ Documentos ┃
┡━━━━━━━━━╇━━━━━━━━━━━━┩
│ op      │ 25         │
└─────────┴────────────┘
Ficaram de fora — fora do período: 544.
ArticleMeta: 26 requisição(ões), 0 resposta(s) do cache.
OpenAlex: 25 de 25 casados; 2 requisição(ões), 2 crédito(s).
```

Os 544 "fora do período" são os artigos da revista de outros anos. O OpenAlex cobra créditos por consulta, e sem cadastro são mil por dia: esta coleta gastou 2, um pela lista de artigos da revista e outro pelos registros das instituições dos autores.

## 4. Rode de novo

```bash
uv run mapa coletar
```

Agora a coleta termina quase instantaneamente:

```text
ArticleMeta: 0 requisição(ões), 26 resposta(s) do cache.
OpenAlex: 25 de 25 casados; 0 requisição(ões), 0 crédito(s).
```

Cada resposta das APIs fica guardada em `brutos/`, e as próximas execuções leem de lá. É isso que torna a coleta **reproduzível** (o corpus não muda enquanto você não pedir) e **retomável** (se a internet cair no meio, a próxima execução busca só o que faltou). Para buscar artigos publicados depois da primeira coleta, use `mapa coletar --atualizar`.

## 5. Confira a cobertura

```bash
uv run mapa status
```

Além do recorte e das etapas, o `status` mostra a seção **Corpus**:

```text
Corpus: 25 documento(s), 2024
Cobertura                         Resumo por idioma
                   ┃  n ┃   %          ┃   n ┃    %
━━━━━━━━━━━━━━━━━━━╇━━━━╇━━━━     ━━━━━╇━━━━━╇━━━━━
com resumo         │ 25 │ 100     fr   │  25 │  100
com DOI            │ 25 │ 100     pt   │  25 │  100
com afiliação      │ 25 │ 100     en   │  25 │  100
possível duplicata │  0 │   0     es   │  25 │  100
```

Todos os 25 artigos têm resumo, DOI e afiliação, e a *Opinião Pública* publica resumos em quatro idiomas. Em outras revistas e períodos a cobertura é menor: o guia [Montar um recorte](../guias/recorte.md#4-conferir) explica o que cada tabela significa e o que conferir.

## 6. Explore os dados em Python

O corpus fica em `dados/documentos.parquet`, e a [API Python](../referencia/api-python.md) consulta esse arquivo em SQL. Abra o Python do projeto com `uv run python` e rode:

```python
import mapa_da_ciencia.api as mapa

p = mapa.abrir()
mais_citados = """
    SELECT titulos[1].texto AS titulo, citacoes
    FROM documentos
    ORDER BY citacoes DESC
    LIMIT 3
"""
mapa.consultar(p, mais_citados)
```

O resultado lista os três artigos mais citados da revista em 2024, segundo o OpenAlex. Para sair do Python, digite `exit()`. O mesmo código funciona num notebook do Jupyter.

## 7. Veja no painel

```bash
uv run mapa painel
```

A página inicial do painel agora mostra os números do seu corpus: 25 documentos, 1 revista, 2024. O mapa e os tópicos aparecem depois da etapa de tópicos, na [parte 2](primeiro-mapa-topicos.md). Para encerrar, aperte ++ctrl+c++ no terminal.

## O que você fez

- Criou um projeto com um recorte de uma revista e um ano.
- Coletou os artigos da ArticleMeta e os ligou ao OpenAlex, com cache em `brutos/`.
- Conferiu a cobertura com `mapa status` e consultou o corpus em SQL.

## Próximos passos

- **Um recorte maior.** O projeto piloto reúne dez revistas de ciência política e relações internacionais, de 2010 a 2025: cerca de 4.300 artigos. Na primeira vez, a coleta leva uns 30 minutos; depois, com o cache em `brutos/`, leva segundos:

    ```bash
    cd ../..
    uv run mapa novo projetos/cp-scielo
    uv run mapa coletar -P projetos/cp-scielo
    ```

- **Uma busca, em vez de revistas inteiras:** [Importar do search.scielo.org](../guias/importar.md) ou a busca por termo em [Montar um recorte](../guias/recorte.md).
- **De onde vêm os dados** e como as fontes são ligadas: [Fontes de dados](../explicacoes/fontes.md).
