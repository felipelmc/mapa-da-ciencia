# Como os tópicos são construídos

Os tópicos do `mapa-da-ciencia` não vêm de uma lista pronta: eles saem dos próprios textos. Artigos que tratam de assuntos parecidos ficam perto uns dos outros num espaço de muitas dimensões, e o agrupamento encontra as regiões mais densas desse espaço. Esta página descreve cada passo e as escolhas por trás deles.

!!! note "Em construção no marco M3"
    Por enquanto, esta página descreve o texto de análise e os embeddings. O agrupamento, as palavras-chave, os rótulos, os macrotemas e a estabilidade entram ao longo do M3.

## 1. O texto de análise

Cada documento é representado por **título e resumo no mesmo idioma**. O idioma é o de `recorte.idioma_analise` no `mapa.yaml`: o inglês, por padrão, porque é o único presente em quase todo o corpus do SciELO ([ADR 0004](../decisoes/0004-embeddings-e-idioma-de-analise.md)).

Nem todo artigo tem resumo em inglês. O texto de análise nunca junta idiomas diferentes, e cada documento fica marcado com a fonte do texto:

| Marca | Quando | Texto usado |
|---|---|---|
| `resumo` | Há resumo no idioma de análise | Título e resumo nesse idioma (ou só o resumo, se o título não existir nesse idioma) |
| `reserva` | Não há resumo no idioma de análise | Título e resumo em outro idioma, na ordem: português, espanhol, inglês, francês |
| `so_titulo` | O documento não tem resumo | Só o título, de preferência no idioma de análise |

A reserva funciona porque o modelo de embeddings é multilíngue: no spike M0a, 99,9% dos resumos em português encontraram a própria versão em inglês como vizinho mais próximo. No piloto de ciência política (4.275 documentos), 4.161 entram com o resumo em inglês, 96 (2,2%) como reserva e 17 (0,4%) só pelo título. A marca aparece no cartão de cada documento no mapa e nas contagens da etapa. Um documento sem título nem resumo fica fora dos tópicos.

## 2. Embeddings

Um **embedding** é uma lista de números (1.024, no modelo padrão) que resume o sentido de um texto. Textos sobre assuntos parecidos têm embeddings parecidos, mesmo sem palavras em comum.

- O modelo padrão é o `qwen3-embedding:0.6b`, rodando no Ollama da sua máquina ([Modelos locais](modelos-locais.md)).
- Textos maiores que o contexto (`modelos.embeddings.num_ctx`, 2.048 tokens por padrão) são truncados. Título e resumo cabem com folga.
- Antes de carregar o modelo, o `mapa` confere se ele cabe na memória livre, e o descarrega ao terminar.

Os vetores ficam em `dados/embeddings/<modelo>@<digest>.npz`. Na segunda execução, só os textos novos ou alterados vão ao Ollama. O **digest** identifica o arquivo exato do modelo: se o Ollama baixar uma versão nova do mesmo nome, os embeddings são recalculados, e os antigos ficam guardados.

Com o modelo padrão, o piloto leva cerca de 4 minutos na primeira vez (18 documentos por segundo num Mac M4 Pro); nas seguintes, vem do cache, sem passar pelo Ollama.

