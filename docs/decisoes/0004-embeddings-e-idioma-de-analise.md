# 0004. Modelo de embeddings e idioma de análise dos tópicos

- **Status:** aceita
- **Data:** 2026-09-26
- **Marco:** M0 (spike M0a)

## Contexto

Os tópicos saem de embeddings de título + resumo, reduzidos com UMAP e agrupados com HDBSCAN. No piloto, os resumos vêm em vários idiomas. Entre os 4.277 artigos:

- o inglês cobre 99,8% dos que têm resumo;
- o português cobre 81,9%;
- a BPSR publica só em inglês.

Se os embeddings refletirem o idioma mais que o assunto, os tópicos se separam por língua, um artefato que distorceria o mapa e as séries temporais. Era preciso escolher o modelo e a política de idioma.

## Opções consideradas

- **Modelo:** `qwen3-embedding:0.6b` (639 MB, contexto de 32K) × `bge-m3` (1,2 GB, contexto de 8K), ambos via Ollama.
- **Idioma:**
  - (a) cada artigo no idioma original (misto);
  - (b) tudo em português, com inglês quando faltar;
  - (c) tudo em inglês, com português quando faltar.

## Evidência

Script `spikes/s02_embeddings.py`, rodado nos 3.403 artigos que têm resumo em pt **e** en. Idioma original segundo o OpenAlex: 2.846 pt, 456 en, 98 es e 3 fr. UMAP com 5 dimensões e HDBSCAN com `min_cluster_size = N/200`.

| Métrica | qwen3-embedding:0.6b | bge-m3 |
|---|---|---|
| Recuperação cruzada pt→en, top-1 (o vizinho en mais próximo é o mesmo artigo) | 0,999 | 0,999 |
| Homofilia de idioma no corpus misto (vizinhos de mesmo idioma além do acaso, k=10) | +0,122 | +0,117 |
| AMI entre cluster e idioma no corpus misto | 0,050 | 0,062 |
| ARI entre os agrupamentos só-pt e só-en | **0,720** | 0,671 |
| Clusters (pt / en / misto) | 56 / 49 / 48 | 50 / 55 / 44 |
| Ruído do HDBSCAN (pt) | **27%** | 39% |
| Velocidade de embedding (M4 Pro) | 13–18 textos/s | 22–26 textos/s |

- Os dois modelos alinham português e inglês quase perfeitamente, e o idioma explica pouco dos clusters (AMI ≈ 0,05). Mesmo assim, no corpus misto os vizinhos compartilham o idioma 12 pontos acima do acaso, um viés pequeno mas real.
- O `qwen3-embedding` produz uma estrutura mais estável entre idiomas (ARI 0,72) e deixa menos documentos como ruído (27% contra 39%).
- A leitura dos 8 maiores clusters do `qwen3-embedding` (condição pt, palavras-chave por c-TF-IDF) mostrou tópicos coerentes e reconhecíveis:
  - teoria democrática e liberalismo;
  - pensamento social brasileiro;
  - desigualdades de renda e gênero;
  - segurança pública e polícia;
  - Judiciário e STF;
  - a própria ciência política como objeto;
  - teoria crítica e decolonial;
  - China e BRICS.

## Decisão

- **Modelo padrão: `qwen3-embedding:0.6b`.** O `bge-m3` fica como alternativa configurável.
- **Idioma de análise = inglês (opção c)**, configurável em `mapa.yaml` (`idioma_analise`). Todo artigo é embutido pelo título e resumo em inglês. Quando não houver inglês, usa-se o português, e o alinhamento cruzado de 0,999 garante que ele cai no lugar certo. Assim o viés residual de idioma desaparece e nenhuma revista monolíngue (como a BPSR) forma um grupo à parte por causa da língua.
- **Idioma de exibição = português.** As palavras-chave do c-TF-IDF são calculadas sobre os textos em português de cada cluster, com o inglês como reserva quando o cluster tiver poucos textos em português. Os rótulos e as descrições escritos pelo LLM saem sempre em português, e a interface mostra o resumo em português quando existe.

## Consequências

- `topicos/pipeline.py` separa o idioma de análise do idioma de exibição.
- **O ruído de 27% é alto.** No M3 é preciso calibrar `min_cluster_size` e `min_samples` e reatribuir os outliers ao centróide mais próximo, marcados como `atribuicao: "vizinho"`, como previsto no plano.
- **Tempo:** embutir 4,2 mil documentos leva cerca de 5 min na primeira vez; depois vem do cache. O critério do M3 passa a ser "menos de 10 min na primeira execução e menos de 2 min com embeddings em cache".
- **Pergunta em aberto para o M3:** no spike, só os clusters da condição pt foram lidos por uma pessoa. É preciso confirmar, lendo a lista completa de tópicos, que o agrupamento feito com embeddings em inglês é tão interpretável quanto o feito em português.

## Como reproduzir

    uv run spikes/s02_embeddings.py                 # ~15 min (os dois modelos, com UMAP)
    uv run spikes/s02_embeddings.py --limite 500    # rodada rápida

## Adendo (2026-09-26, marco M3)

A pergunta aberta sobre a legibilidade dos tópicos calculados em inglês foi respondida pela leitura dos 50 tópicos do piloto ([ADR 0007](0007-parametros-dos-topicos.md)): os tópicos são subáreas reconhecíveis, e o idioma não os separa (nenhum tópico tem mais de 80% de documentos em inglês). Os documentos sem resumo em inglês entram como "reserva marcada" (o resumo no idioma disponível, ou só o título), e a marca aparece no cartão do mapa. A meta de tempo ficou abaixo do previsto: com os embeddings em cache, a etapa de tópicos leva cerca de 20 segundos no piloto.

