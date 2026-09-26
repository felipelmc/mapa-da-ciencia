# Modelos locais

O `mapa-da-ciencia` roda os modelos de linguagem **no seu computador**, via [Ollama](https://ollama.com), e não em serviços na nuvem.

## Por quê

- **Custo zero por uso.** Classificar milhares de resumos não gera conta no fim do mês, o que importa para quem pesquisa sem verba e para oficinas.
- **Privacidade.** Nenhum texto sai da máquina para ser processado.
- **Reprodutibilidade.** Um modelo aberto, identificado pelo *digest*, pode ser baixado de novo por qualquer pessoa daqui a anos. Modelos de nuvem mudam ou são descontinuados sem aviso.
- **Uma pergunta de pesquisa em si:** modelos abertos, rodando num notebook comum, classificam literatura acadêmica em português tão bem quanto uma pessoa? A validação do projeto mede exatamente isso.

Provedores na nuvem podem entrar depois como uma opção a mais, sem mudar o resto do sistema.

## Quais modelos, para quê

| Papel | Modelo padrão | Por quê |
|---|---|---|
| Embeddings (tópicos e mapa) | `qwen3-embedding:0.6b` | Multilíngue, com alinhamento quase perfeito entre português e inglês, e leve (0,6 GB). Venceu o `bge-m3` em estabilidade e em documentos deixados sem tópico ([ADR 0004](../decisoes/0004-embeddings-e-idioma-de-analise.md)) |
| Classificação dos resumos | `qwen3.5:9b` | Cabe numa máquina de 16 a 32 GB e segue um esquema JSON com evidência |
| Rótulos dos tópicos | `qwen3.5:9b` ou `gemma4:26b` | São poucas chamadas (uma por tópico), então vale um modelo maior quando a memória permite |

Os modelos foram escolhidos em testes com o corpus do piloto, registrados na seção [Decisões](../decisoes/README.md). A escolha do modelo de classificação sai do spike M0b (registro 0005, em andamento).

## Memória: o cuidado principal

Um modelo precisa caber na memória **livre** na hora de rodar, e não só na memória total. No desenvolvimento do projeto, carregar um modelo de 17 GB numa máquina de 24 GB com outros programas abertos esgotou o *swap* e travou o computador. Por isso:

- `mapa diagnostico` mostra memória livre, swap e o tamanho de cada modelo, e avisa quando um modelo não cabe agora;
- as etapas que carregam modelos (a partir do marco M3) conferem a memória antes de começar e param com uma mensagem clara se o modelo não couber;
- os modelos são descarregados ao fim de cada etapa.

## Velocidade

Embeddings são rápidos: os 4,2 mil resumos do piloto levam uns 5 minutos num Mac M4 Pro. A classificação é a etapa lenta, com cerca de 10 a 15 segundos por resumo no mesmo Mac. O piloto inteiro leva uma noite. Por isso a classificação (marco M5) vai:

- estimar o tempo antes de começar (`--estimar`);
- rodar numa amostra, se você pedir (`--limite`);
- ser **retomável**: se for interrompida, continua de onde parou, sem refazer nada.
