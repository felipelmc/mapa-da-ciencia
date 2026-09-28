# 0005. Modelo local de classificação e parâmetros

- **Status:** aceita
- **Data:** 2026-09-26
- **Marco:** M0 (spike M0b)

## Contexto

A classificação por codebook é a etapa mais cara do pipeline: um modelo de linguagem lê cada um dos cerca de 4,2 mil resumos do piloto e devolve um JSON com evidência e valor para cada variável. Era preciso escolher o modelo local e os parâmetros (modo de raciocínio, concorrência) numa máquina típica: M4 Pro com 24 GB de memória unificada, usada ao mesmo tempo para outros trabalhos pesados (jobs de R e de OCR em Python).

Os candidatos eram `qwen3.5:9b` (6,6 GB) e `gemma4:26b` (MoE com ~4B parâmetros ativos, 17 GB).

## Opções consideradas

- Modelo: `qwen3.5:9b` × `gemma4:26b`.
- Modo de raciocínio (`think`): desligado × ligado.
- Concorrência do cliente: 1 × 4 chamadas simultâneas.

## Evidência

Script `spikes/s03_llm.py`, com o codebook de exemplo (`spikes/codebook_exemplo.yaml`, 6 variáveis) e 50 resumos em português de artigos de pesquisa. A amostra é estratificada por revista, com 9 revistas, porque a BPSR não tem resumos em português. Saída estruturada por JSON Schema no Ollama 0.34, com `temperature: 0`, `seed: 7` e `num_ctx: 8192`.

**`gemma4:26b` ficou fora da classificação.** Ao carregá-lo (17 GB) com os outros trabalhos da máquina rodando, a memória livre caiu para 5% e o swap se esgotou. O teste foi interrompido para não travar a máquina, e a decisão foi usar só o `qwen3.5:9b` na classificação.

| Configuração | JSON válido | Evidência literal / aproximada / ausente | s por resumo (mediana) | Vazão | Projeção para 4,2 mil |
|---|---|---|---|---|---|
| `qwen3.5:9b`, sem raciocínio, 1 por vez | **100%** | 71% / 22% / 7% | 12,5 | 4,8 resumos/min | ~14,6 h |
| `qwen3.5:9b`, sem raciocínio, 4 simultâneas | **100%** | 71% / 22% / 7% | 50,7 (espera na fila) | 4,7 resumos/min | ~14,8 h |
| `qwen3.5:9b`, com raciocínio | não concluída: mais de 25 min sem terminar 15 resumos, ou seja, mais de 100 s por resumo | | | | inviável |

- **Determinismo:** as execuções com concorrência 1 e 4 concordaram em 100% das respostas, com kappa 1,00 nas 5 variáveis categóricas.
- **Paralelismo não aumenta a vazão nesta máquina.** O Ollama atendeu as chamadas uma de cada vez: com 4 simultâneas, cada uma esperou na fila.
- **Onde vai o tempo:** a mediana é de 1.211 tokens de entrada e 324 de saída. O processamento da entrada leva ~1,8 s, e a geração, a 31 tokens/s (100% na GPU), leva ~10,5 s. **Quem custa são as evidências longas**, e não o prompt.
- **Evidência literal por variável:**

  | Variável | Literal |
  |---|---|
  | abordagem | 86% |
  | técnica | 80% |
  | Brasil como caso | 74% |
  | recorte geográfico | 72% |
  | subárea | 60% |
  | período analisado | 54% |

  No período, 24% saem sem evidência, porque a resposta mais comum é "não se aplica" (35 de 50), e aí não há trecho a citar.
- **Rótulos de tópicos** com o `qwen3.5:9b`: 3,1 s por tópico, rótulos específicos e corretos ("Judicialização da política no Brasil", "China e BRICS na ordem internacional"). Houve dois deslizes: uma letra acentuada perdida ("Gnero" em vez de "Gênero") e uma concordância errada ("dos comissões").
- **Não medido no spike:** a *acurácia* em relação à codificação humana. O spike mediu formato, ancoragem e custo, não se as respostas estão certas. Isso é o trabalho da validação (M5).

## Decisão

- **Classificação:** `qwen3.5:9b` no perfil `padrao`, com `think: false`, `temperature: 0`, `seed` fixo, `num_ctx: 8192` e **concorrência 1 por padrão**.
- **Rótulos de tópicos:** `qwen3.5:9b` por padrão. O `gemma4:26b` fica no perfil `forte` (32 GB ou mais) e só é carregado se a checagem de memória permitir.
- **Checagem de memória:**
  - considera livre a memória já ocupada por um modelo carregado (um bug desse tipo interrompeu o spike e foi corrigido também no `mapa diagnostico`);
  - é feita antes de carregar o modelo **e durante a execução**. Um vigia simples, que parou o spike quando o swap livre caiu abaixo de 300 MB, protegeu os trabalhos do usuário. O produto terá o mesmo comportamento, pausando a etapa com uma mensagem clara.
- **Progresso gravado resumo a resumo:** uma interrupção no spike descartou a configuração que estava em andamento. O executor do M5 grava cada resposta no cache assim que ela chega e retoma de onde parou.

## Consequências e pendências para o M5

- **Reduzir a saída pela metade:**
  - pedir evidências curtas (até ~20 palavras);
  - aceitar evidência vazia quando o valor for `nao_informado`, "não se aplica" ou equivalente, sem contar isso como falha.

  A estimativa é de ~6 s por resumo, ou **~7 h para o piloto**.
- **Medir o `qwen3.5:4b`** (3,4 GB, cerca de 2× mais rápido) contra o `qwen3.5:9b` na amostra de validação humana. Se a concordância com humanos for equivalente, ele vira o padrão do perfil `leve` ou mesmo do `padrao`.
- **Rótulos:** checar a ortografia dos rótulos gerados (por exemplo, comparar com as palavras-chave do c-TF-IDF e pedir de novo quando uma palavra perder acentos) e permitir que o pesquisador edite os rótulos na interface.
- O critério do M5 "≥95% de JSON válido na 1ª tentativa" já foi atingido no spike (100%).
- Continua em aberto: a acurácia contra codificação humana (M5).

## Como reproduzir

    uv run spikes/s03_llm.py                                   # qwen3.5:9b: 1 e 4 simultâneas, e com raciocínio
    uv run spikes/s03_llm.py --configs --rotulos-com qwen3.5:9b  # só os rótulos e a página de leitura

A página `spikes/saida/s03_leitura.md` mostra as respostas lado a lado com os resumos, para leitura humana.

## Adendo (2026-09-28, versão 1.0.1): o perfil `leve`

O perfil `leve` (8 a 16 GB) usa o `qwen3.5:4b` na classificação e nos rótulos desde o primeiro perfil, porque o `qwen3.5:9b` precisa de uns 8 GB livres e não cabe com folga nessas máquinas. A medida que esta decisão pedia antes de adotá-lo (o `qwen3.5:4b` contra o `qwen3.5:9b` na amostra de validação) ainda não foi feita ([ADR 0012](0012-validacao-e-codificador-de-referencia.md)). Até lá, quem usa o perfil `leve` deve olhar a concordância da própria amostra (`mapa validar metricas`) antes de publicar.
