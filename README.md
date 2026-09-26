# mapa-da-ciencia

**Observatório da literatura científica com modelos de linguagem locais.** O `mapa-da-ciencia` coleta milhares de artigos, começando pelo SciELO, e mostra:

- **sobre o que se escreve**, com tópicos num mapa e a evolução deles no tempo;
- **como se pesquisa**, com a classificação de cada resumo segundo um codebook seu, com evidência textual e validação contra a sua codificação;
- **onde se produz**, com UF, país e instituição.

Os modelos rodam no seu computador, via [Ollama](https://ollama.com).

*A literature observatory for scientific publishing, built on local language models: topic maps over time, codebook-based classification of abstracts with textual evidence and human validation, and the geography of research production. Documentation in Portuguese.*

> **Status:** versão 0.3.0, com a coleta de artigos e os tópicos num mapa navegável (marcos M2 e M3). Os tópicos no tempo e a geografia chegam no M4, e a classificação por codebook no M5. Ainda não há versão no PyPI.

![O mapa de 4.275 artigos de dez revistas de ciência política no SciELO Brasil, de 2010 a 2025, com os tópicos contornados e os rótulos dos macrotemas](docs/imagens/mapa.png)

## Experimente

```bash
git clone https://github.com/felipelmc/mapa-da-ciencia.git
cd mapa-da-ciencia
uv sync
uv run mapa painel --exemplo
```

O painel abre no navegador com um exemplo **sintético** (dados fictícios). Veja o tutorial completo, com a compilação da interface, em [Explorar o exemplo em 5 minutos](https://felipelmc.github.io/mapa-da-ciencia/tutoriais/explorar-exemplo/).

Para mapear artigos de verdade, por exemplo os da *Opinião Pública* de 2010 a 2025 (os tópicos pedem o [Ollama](https://felipelmc.github.io/mapa-da-ciencia/guias/instalacao/) com os modelos do perfil):

```bash
uv run mapa novo projetos/op --revista op
uv run mapa coletar -P projetos/op
uv run mapa topicos -P projetos/op
uv run mapa painel -P projetos/op
```

O passo a passo está em [Seu primeiro mapa](https://felipelmc.github.io/mapa-da-ciencia/tutoriais/primeiro-mapa/) (a coleta) e na [parte 2](https://felipelmc.github.io/mapa-da-ciencia/tutoriais/primeiro-mapa-topicos/) (tópicos e mapa).

## Documentação

[felipelmc.github.io/mapa-da-ciencia](https://felipelmc.github.io/mapa-da-ciencia/) tem os tutoriais, os guias, a referência e a metodologia. Para ler localmente, rode `uv run mkdocs serve` e abra `http://127.0.0.1:8000`.

## Sobre

Sucessor do [SciELO-Summarizer](https://github.com/felipelmc/SciELO-Summarizer), criado no SICSS Brasil 2024. Código sob licença [MIT](LICENSE). Para citar, veja [`CITATION.cff`](CITATION.cff). Para contribuir, veja [`CONTRIBUTING.md`](CONTRIBUTING.md).

É um projeto independente e **não oficial**: não tem vínculo com o SciELO, o OpenAlex ou o IBGE, cujos dados públicos ele usa.
