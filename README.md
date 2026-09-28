# mapa-da-ciencia

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22998585.svg)](https://doi.org/10.5281/zenodo.22998585)

**Observatório da literatura científica com modelos de linguagem locais.** O `mapa-da-ciencia` coleta milhares de artigos, começando pelo SciELO, e mostra:

- **sobre o que se escreve**, com tópicos num mapa e a evolução deles no tempo;
- **como se pesquisa**, com a classificação de cada resumo segundo um codebook seu, com evidência textual e validação contra a sua codificação;
- **onde se produz**, com UF, país e instituição.

Os modelos rodam no seu computador, via [Ollama](https://ollama.com): nenhum texto sai da sua máquina, e não é preciso chave de API (a única exceção é opcional: o supervisor do júri pela API da Anthropic, com consentimento explícito).

*In English: [see below](#in-english).*

> **Status:** versão 2.1.0: a coleta, os tópicos no mapa e no tempo, a geografia, a classificação por codebook com validação, o júri de modelos locais com supervisor, as redes de coautoria e de citação, tudo também pela interface, a publicação como site estático, as figuras para artigo e a oficina no Colab.

![O painel do piloto: o mapa de 4.275 artigos de dez revistas de ciência política no SciELO Brasil acendendo ano a ano, de 2010 a 2025, e depois as vistas Tópicos, Geografia e Classificação](https://raw.githubusercontent.com/felipelmc/mapa-da-ciencia/main/docs/imagens/painel.gif)

## Veja

- **[Demo](https://felipelamarca.com/mapa-da-ciencia/demo/)**: o piloto, com os 4.275 artigos de ciência política do SciELO Brasil de 2010 a 2025, publicado com `mapa publicar`.
- **[Oficina no Colab](https://colab.research.google.com/github/felipelmc/mapa-da-ciencia/blob/main/notebooks/oficina_colab.ipynb)**: um mapa da *Opinião Pública* do zero, numa GPU gratuita do Google, em uns 30 minutos.
- **[O site do projeto](https://felipelamarca.com/mapa-da-ciencia/)**: os artigos do piloto como um céu que se forma, ano a ano, e as histórias que eles contam.

[![A abertura do site: "Sobre o que escreve a ciência política brasileira?", ao lado do céu de estrelas dos artigos do piloto, ligadas nas constelações dos macrotemas](https://raw.githubusercontent.com/felipelmc/mapa-da-ciencia/main/docs/imagens/abertura.png)](https://felipelamarca.com/mapa-da-ciencia/)

## Experimente

Com o [uv](https://docs.astral.sh/uv/) instalado, o *wheel* da última [*release*](https://github.com/felipelmc/mapa-da-ciencia/releases) traz a interface pronta:

```bash
uv tool install "https://github.com/felipelmc/mapa-da-ciencia/releases/download/v2.1.0/mapa_da_ciencia-2.1.0-py3-none-any.whl"
mapa painel --exemplo
```

O painel abre no navegador com um exemplo **sintético** (dados fictícios). Se o terminal responder `command not found: mapa`, rode `uv tool update-shell`, feche o terminal e abra outro. Para trabalhar no código, com a interface compilada a partir do fonte, veja [Explorar o exemplo em 5 minutos](https://felipelmc.github.io/mapa-da-ciencia/tutoriais/explorar-exemplo/).

Para mapear artigos de verdade, por exemplo os da *Opinião Pública* de 2010 a 2025 (os tópicos e a classificação pedem o [Ollama](https://felipelmc.github.io/mapa-da-ciencia/guias/instalacao/) com os modelos do perfil):

```bash
mapa novo projetos/op --revista op
mapa coletar -P projetos/op
mapa topicos -P projetos/op
mapa geografia -P projetos/op
mapa classificar -P projetos/op
mapa painel -P projetos/op
```

O passo a passo está em [Seu primeiro mapa](https://felipelmc.github.io/mapa-da-ciencia/tutoriais/primeiro-mapa/) (a coleta), na [parte 2](https://felipelmc.github.io/mapa-da-ciencia/tutoriais/primeiro-mapa-topicos/) (tópicos e mapa), na [parte 3](https://felipelmc.github.io/mapa-da-ciencia/tutoriais/primeiro-mapa-tempo-e-geografia/) (tempo e geografia) e na [parte 4](https://felipelmc.github.io/mapa-da-ciencia/tutoriais/primeiro-mapa-classificacao/) (classificação e validação). Sem o terminal, o mesmo percurso está em [Seu primeiro mapa pela interface](https://felipelmc.github.io/mapa-da-ciencia/tutoriais/primeiro-mapa-pela-interface/). Para publicar o seu como site estático, veja [Publicar o site](https://felipelmc.github.io/mapa-da-ciencia/guias/publicar/).

## Documentação

[felipelmc.github.io/mapa-da-ciencia](https://felipelmc.github.io/mapa-da-ciencia/) tem os tutoriais, os guias, a referência e a metodologia ([em uma página](https://felipelmc.github.io/mapa-da-ciencia/explicacoes/metodologia/), com as [limitações e vieses](https://felipelmc.github.io/mapa-da-ciencia/explicacoes/limitacoes/)). Para ler localmente, rode `uv run --group docs mkdocs serve` e abra `http://127.0.0.1:8000`.

## Como citar

Se usar o `mapa-da-ciencia` numa pesquisa, cite-o pelo DOI do Zenodo, [10.5281/zenodo.22998585](https://doi.org/10.5281/zenodo.22998585), que reúne todas as versões (a [página do Zenodo](https://doi.org/10.5281/zenodo.22998585) tem também o DOI de cada versão):

```bibtex
@software{lamarca_mapa_da_ciencia,
  author    = {Lamarca, Felipe},
  title     = {mapa-da-ciencia: observatório da literatura científica com modelos de linguagem locais},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.22998585},
  url       = {https://doi.org/10.5281/zenodo.22998585}
}
```

O [`CITATION.cff`](https://github.com/felipelmc/mapa-da-ciencia/blob/main/CITATION.cff) tem os mesmos dados, e o GitHub mostra a citação em outros formatos em *Cite this repository*, na coluna da direita.

## Sobre

Sucessor do [SciELO-Summarizer](https://github.com/felipelmc/SciELO-Summarizer), criado no SICSS Brasil 2024. Código sob licença [MIT](https://github.com/felipelmc/mapa-da-ciencia/blob/main/LICENSE). Para citar, veja [Como citar](#como-citar). Para contribuir, veja [`CONTRIBUTING.md`](https://github.com/felipelmc/mapa-da-ciencia/blob/main/CONTRIBUTING.md).

É um projeto independente e **não oficial**: não tem vínculo com o SciELO, o OpenAlex ou o IBGE, cujos dados públicos ele usa.

## In English

`mapa-da-ciencia` ("map of science") is a literature observatory built on local language models. It collects thousands of articles, starting with SciELO (the open-access library of Latin American journals) and OpenAlex, and shows:

- **what the literature is about**: topics from embeddings (UMAP and HDBSCAN), on a navigable map and over time, with trends estimated by quasi-binomial logistic regression;
- **how research is done**: every abstract is classified against a codebook you write, and each answer quotes the passage of the abstract that supports it; agreement is measured on a stratified sample coded blind (Cohen's kappa with bootstrap intervals, PABAK, Krippendorff's alpha, McNemar between models);
- **where it is produced**: author affiliations matched to OpenAlex/ROR institutions, with fractional counting by state, country and institution.

All models run on your computer through [Ollama](https://ollama.com) (by default `qwen3-embedding:0.6b` and `qwen3.5:9b`, which fit in a 16 GB laptop), so no text leaves your machine and no API key is needed. Everything runs from the command line, from Python (`mapa_da_ciencia.api`) or from a local web panel, and a project can be published as a static site, with abstracts only under Creative Commons licenses.

The pilot maps 4,275 political science articles from ten Brazilian journals, 2010–2025 ([live demo](https://felipelamarca.com/mapa-da-ciencia/demo/); the [project site](https://felipelamarca.com/mapa-da-ciencia/) tells its stories, in English too). The interface and the [documentation](https://felipelmc.github.io/mapa-da-ciencia/) are in Portuguese; the [methodology page](https://felipelmc.github.io/mapa-da-ciencia/explicacoes/metodologia/) summarizes the whole method with its parameters. To try it, install the wheel above and run `mapa painel --exemplo` (if the terminal says `command not found: mapa`, run `uv tool update-shell` and open a new terminal), or open the [Colab workshop notebook](https://colab.research.google.com/github/felipelmc/mapa-da-ciencia/blob/main/notebooks/oficina_colab.ipynb).

To cite it, use the Zenodo DOI [10.5281/zenodo.22998585](https://doi.org/10.5281/zenodo.22998585) (all versions; BibTeX in [Como citar](#como-citar)). MIT licensed. An independent project, not affiliated with SciELO, OpenAlex or IBGE.
