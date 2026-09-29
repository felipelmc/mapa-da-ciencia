# mapa-da-ciencia

O **mapa-da-ciencia** é um observatório da literatura científica. Ele coleta milhares de artigos, começando pelo [SciELO](https://scielo.org), e responde, com modelos de linguagem que rodam **no seu próprio computador** onde eles são precisos, a quatro perguntas sobre um campo de pesquisa:

1. **Sobre o que se escreve, e como isso muda no tempo?** Os artigos viram pontos num mapa, agrupados por proximidade de assunto. Cada grupo é um tópico com nome e descrição, e dá para acompanhar como cada tópico cresce ou encolhe ano a ano.
2. **Como se pesquisa?** Um modelo lê cada resumo e o classifica segundo um *codebook* escrito por você (método, recorte geográfico, subárea...). Ele sempre copia o trecho do resumo que justifica cada resposta. Você codifica uma amostra, e o sistema mede o quanto o modelo concorda com você.
3. **Onde se produz?** O mapa das afiliações dos autores por UF, país e instituição, com contagem fracionária.
4. **Quem trabalha com quem?** As redes de coautoria, entre pessoas e entre instituições, e as citações entre os artigos do corpus.

Na amostra de validação, um [júri de modelos locais](explicacoes/juri.md) pode votar e deliberar, para comparar a decisão em conjunto com a de um modelo sozinho. Tudo aparece num painel interativo, que pode ser publicado como site estático para acompanhar um artigo ou uma apresentação: a [demo](https://felipelamarca.com/mapa-da-ciencia/demo/) é o piloto publicado.

## Por onde começar

<div class="grid cards" markdown>

- **Ver funcionando.** O tutorial [Explorar o exemplo em 5 minutos](tutoriais/explorar-exemplo.md) abre o painel com dados sintéticos.
- **Instalar.** O guia [Instalar e escolher os modelos](guias/instalacao.md) explica o Ollama, os perfis de modelo e `mapa diagnostico`.
- **Começar um projeto.** O guia [Criar um projeto](guias/criar-projeto.md) mostra `mapa novo`, `mapa.yaml` e a escolha das revistas.
- **Entender o método.** A seção [Explicações](explicacoes/index.md) cobre fontes, modelos locais, reprodutibilidade e licenças.

</div>

## Princípios

- **Modelos locais.** Nenhum resumo sai da sua máquina para ser processado: embeddings e classificação rodam no [Ollama](https://ollama.com). As únicas chamadas externas são as da coleta de metadados públicos.
- **Rastreável.** Cada classificação vem com o trecho literal que a justifica, e cada execução grava um manifesto com versões, modelos e parâmetros.
- **Validado.** A qualidade da classificação é medida contra codificação humana (kappa de Cohen, PABAK), e não presumida.
- **Aberto.** Código sob licença MIT. As decisões técnicas ficam registradas, com evidência, [no repositório](https://github.com/felipelmc/mapa-da-ciencia/tree/main/docs/decisoes).

## Sobre

O projeto sucede o [SciELO-Summarizer](https://github.com/felipelmc/SciELO-Summarizer), criado no [SICSS Brasil 2024](https://sicss.io/2024/fgv-ecmi-brazil/). É um projeto independente, **sem vínculo oficial** com o SciELO, o OpenAlex ou o IBGE, cujos dados públicos ele usa.
