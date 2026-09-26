# mapa-da-ciencia

O **mapa-da-ciencia** é um observatório da literatura científica. Ele coleta milhares de artigos, começando pelo [SciELO](https://scielo.org), e usa modelos de linguagem que rodam **no seu próprio computador** para responder a três perguntas sobre um campo de pesquisa:

1. **Sobre o que se escreve, e como isso muda no tempo?** Os artigos viram pontos num mapa, agrupados por proximidade de assunto. Cada grupo é um tópico com nome e descrição, e dá para acompanhar como cada tópico cresce ou encolhe ano a ano.
2. **Como se pesquisa?** Um modelo lê cada resumo e o classifica segundo um *codebook* escrito por você (método, recorte geográfico, subárea...). Ele sempre copia o trecho do resumo que justifica cada resposta. Você codifica uma amostra, e o sistema mede o quanto o modelo concorda com você.
3. **Onde se produz?** O mapa das afiliações dos autores por UF, país e instituição, com contagem fracionária.

Tudo aparece num painel interativo, que pode ser publicado como site estático para acompanhar um artigo ou uma apresentação.

!!! warning "Em desenvolvimento"
    O projeto concluiu o **marco M3** (versão 0.3.0): a coleta de artigos do SciELO e do OpenAlex, os tópicos com rótulos em português escritos por um modelo local e o mapa navegável dos documentos. Os tópicos no tempo e a geografia chegam no M4, e a classificação por codebook no M5. Veja o [plano de marcos](desenvolvimento/index.md#marcos).

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
- **Aberto.** Código sob licença MIT. As decisões técnicas ficam registradas, com evidência, na seção [Decisões](decisoes/README.md).

## Sobre

O projeto sucede o [SciELO-Summarizer](https://github.com/felipelmc/SciELO-Summarizer), criado no [SICSS Brasil 2024](https://sicss.io/2024/fgv-ecmi-brazil/). É um projeto independente, **sem vínculo oficial** com o SciELO, o OpenAlex ou o IBGE, cujos dados públicos ele usa.
