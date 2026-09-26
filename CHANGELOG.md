# Registro de mudanças

Todas as mudanças relevantes do projeto ficam registradas aqui. O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/), e as versões seguem o [versionamento semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

## [0.2.0] - 2026-09-26

A coleta: o `mapa` monta o corpus a partir do SciELO e do OpenAlex. No piloto (10 revistas de ciência política, 2010–2025), são 4.275 artigos, 99,6% com resumo e 99,4% casados com o OpenAlex, em menos de um minuto e cerca de 32 créditos do OpenAlex.

### Adicionado

- **Marco M2 (coleta)**:
  - `mapa coletar`: artigos das revistas do recorte pela ArticleMeta, com o ano tirado do PID e o filtro de tipos de documento; opções `--revista`, `--anos`, `--limite`, `--atualizar`, `--offline`, `--sem-openalex` e `--consulta`;
  - cache das respostas em `brutos/`, gravado de forma atômica: a segunda execução faz 0 requisições, e uma coleta interrompida continua de onde parou;
  - enriquecimento pelo OpenAlex (citações, licença por artigo, resumo de reserva), com a cascata de casamento conferida (DOI → PID na URL → DOI derivado → título e ano);
  - deduplicação entre fontes e dentro da ArticleMeta, com suspeitas marcadas em vez de apagadas;
  - `mapa importar`: exportações do search.scielo.org (RIS, CSV, BibTeX) e listas de DOIs ou PIDs, de qualquer coleção do SciELO;
  - busca por termo no título e no resumo, pelo OpenAlex (`--consulta` ou `fontes.openalex.consulta`);
  - `mapa revistas`: as 427 revistas correntes do SciELO Brasil, com busca por nome, ISSN e área; `mapa novo --revista --anos`;
  - corpus em `dados/documentos.parquet` via DuckDB (ADR 0006), com as views `documentos`, `textos`, `autores` e `afiliacoes`;
  - `mapa status` com a cobertura do corpus; o painel passa a mostrar os números do corpus depois da coleta;
  - fachada `mapa_da_ciencia.api` para notebooks, com consultas em SQL;
  - documentação: tutorial "Seu primeiro mapa, parte 1", guias "Montar um recorte" e "Importar uma busca do SciELO", explicação das fontes, ADR 0006 e adendo ao ADR 0003 com os números do piloto.

### Segurança

- Nenhum e-mail sai da ArticleMeta: extração por lista branca de campos e varredura final, com teste sobre o Parquet e `saida/`.
- A chave do OpenAlex nunca é gravada em `brutos/`.

## [0.1.0] - 2026-09-26

Primeira versão marcada: o esqueleto do projeto. Ainda não coleta nem analisa artigos (isso começa no M2).

### Adicionado

- **Marco M0 (spikes técnicos)**, com os resultados registrados em `docs/decisoes/`:
  - fontes, casamento ArticleMeta↔OpenAlex e licenças ([ADR 0003](docs/decisoes/0003-fontes-casamento-e-licencas.md));
  - modelo de embeddings e idioma de análise ([ADR 0004](docs/decisoes/0004-embeddings-e-idioma-de-analise.md));
  - frontend com router por hash e regl-scatterplot ([ADR 0002](docs/decisoes/0002-frontend-router-hash-e-regl-scatterplot.md));
  - certificados do sistema com `truststore` ([ADR 0001](docs/decisoes/0001-certificados-do-sistema-com-truststore.md));
  - modelo local de classificação e parâmetros ([ADR 0005](docs/decisoes/0005-modelo-de-classificacao.md)).
- **Marco M1 (esqueleto)**:
  - pacote Python e CLI `mapa` com os comandos `novo`, `status`, `diagnostico` e `painel`;
  - configuração do projeto (`mapa.yaml`) e do codebook (`codebook.yaml`), com erros explicados em português;
  - perfis de modelos locais por memória e checagem de memória antes de carregar modelos;
  - manifesto de execução para reprodutibilidade;
  - contrato de dados v1 com JSON Schemas e um exemplo sintético determinístico;
  - servidor local do painel (FastAPI) e `mapa painel --exemplo`;
  - site de documentação (Material for MkDocs), com referência gerada a partir do código.

[Não lançado]: https://github.com/felipelmc/mapa-da-ciencia/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/felipelmc/mapa-da-ciencia/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/felipelmc/mapa-da-ciencia/releases/tag/v0.1.0
