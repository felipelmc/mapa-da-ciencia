<!-- Página gerada por scripts/gerar_referencias.py a partir do código. Não edite à mão. -->

# API HTTP do painel

O `mapa painel` serve, além da interface e dos arquivos do contrato (`/dados/…`), uma API local em `/api/…`. Ela só existe no painel com um projeto aberto, só escuta em `127.0.0.1` e só responde a pedidos cujo `Host` seja desta máquina; as rotas de escrita recusam também um `Origin` de fora. O site publicado não tem API. Com o painel aberto, a documentação interativa fica em `/api/docs`.

O progresso das etapas chega por *Server-Sent Events* (`GET /api/jobs/{job}/eventos`): cada evento tem `id:` (a sequência), `event:` (`estado`, `etapa`, `avanco`, `mensagem`, `resumo`, `erro` ou `fim`) e `data:` em JSON; quem reconecta manda `Last-Event-ID` e recebe só o que perdeu. Veja o guia [Usar o painel](../guias/painel.md).

| Método | Rota | O que faz |
|---|---|---|
| `GET` | `/api/projeto` | O projeto aberto: nome, título, pasta e a última execução de cada etapa. |
| `GET` | `/api/saude` | Confere se o painel está no ar: a versão do pacote e o nome do projeto aberto (ou `null`, no exemplo). |
| `GET` | `/dados/manifesto.json` | O manifesto do contrato, com `api: true` no painel (a interface usa isso para mostrar o que só funciona localmente); sem exportação ainda, um manifesto mínimo do projeto. |
| `POST` | `/api/etapas/{etapa}` | Começa uma etapa do pipeline em segundo plano e devolve o job. |
| `GET` | `/api/jobs` | Os jobs mais recentes, do mais novo ao mais antigo. |
| `DELETE` | `/api/jobs/{job}` | Pede para o job parar; ele para na próxima atualização de progresso. |
| `GET` | `/api/jobs/{job}` | O estado de um job: etapa, opções, estado, início, fim, resumo e erro. |
| `GET` | `/api/jobs/{job}/eventos` | O progresso do job em Server-Sent Events, a partir do evento seguinte ao último recebido. |
| `GET` | `/api/codebook` | O `codebook.yaml` e o hash que identifica a versão. |
| `PUT` | `/api/codebook` | Troca o codebook inteiro, sem perder os comentários do que continua igual. |
| `GET` | `/api/configuracao` | O `mapa.yaml`, com os valores padrão preenchidos. |
| `PATCH` | `/api/configuracao` | Muda parte do `mapa.yaml` (os campos enviados), sem perder os comentários. |
| `GET` | `/api/estimativa/classificacao` | Quanto falta classificar, pelo tempo mediano por documento das execuções anteriores. |
| `GET` | `/api/modelos` | Memória, perfis, modelos instalados no Ollama e os modelos do projeto. |
| `POST` | `/api/modelos/baixar` | Baixa um modelo do Ollama em segundo plano (um job, com o progresso em MB). |
| `GET` | `/api/projeto/etapas` | O estado de cada etapa do pipeline, para a linha de metrô da vista Projeto. |
| `GET` | `/api/revistas` | As revistas correntes do SciELO Brasil (o retrato empacotado), por nome, acrônimo, ISSN ou área; com `issn`, só as desses ISSNs (separados por vírgula), na ordem pedida. |
| `POST` | `/api/validacao/amostra` | Sorteia a amostra de validação (como `mapa validar amostra`) e exporta os textos para codificar. Com uma amostra já sorteada, só `refazer` sorteia outra. |
| `PUT` | `/api/validacao/codificacoes/{doc}` | Grava as respostas de um codificador para um documento da amostra. |
| `GET` | `/api/validacao/fila` | A amostra na ordem da fila do codificador, com as respostas que ele já deu. |
| `GET` | `/api/validacao/metricas` | A concordância agora, com as divergências de todos os codificadores. |

## Painel

### `GET /api/projeto`

O projeto aberto: nome, título, pasta e a última execução de cada etapa.

### `GET /api/saude`

Confere se o painel está no ar: a versão do pacote e o nome do projeto aberto (ou `null`, no exemplo).

### `GET /dados/manifesto.json`

O manifesto do contrato, com `api: true` no painel (a interface usa isso para mostrar o que só funciona localmente); sem exportação ainda, um manifesto mínimo do projeto.

## Etapas e jobs

### `POST /api/etapas/{etapa}`

Começa uma etapa do pipeline em segundo plano e devolve o job.

| Parâmetro | Onde | Tipo | Obrigatório |
|---|---|---|---|
| `etapa` | caminho | texto | sim |

Corpo: um objeto JSON (ver a descrição).

### `GET /api/jobs`

Os jobs mais recentes, do mais novo ao mais antigo.

### `DELETE /api/jobs/{job}`

Pede para o job parar; ele para na próxima atualização de progresso.

| Parâmetro | Onde | Tipo | Obrigatório |
|---|---|---|---|
| `job` | caminho | texto | sim |

### `GET /api/jobs/{job}`

O estado de um job: etapa, opções, estado, início, fim, resumo e erro.

| Parâmetro | Onde | Tipo | Obrigatório |
|---|---|---|---|
| `job` | caminho | texto | sim |

### `GET /api/jobs/{job}/eventos`

O progresso do job em Server-Sent Events, a partir do evento seguinte ao último recebido.

| Parâmetro | Onde | Tipo | Obrigatório |
|---|---|---|---|
| `job` | caminho | texto | sim |
| `desde` | consulta | inteiro | não |
| `last-event-id` | cabeçalho | texto | não |

## Projeto

### `GET /api/codebook`

O `codebook.yaml` e o hash que identifica a versão.

### `PUT /api/codebook`

Troca o codebook inteiro, sem perder os comentários do que continua igual.

Corpo: um objeto JSON (ver a descrição).

### `GET /api/configuracao`

O `mapa.yaml`, com os valores padrão preenchidos.

### `PATCH /api/configuracao`

Muda parte do `mapa.yaml` (os campos enviados), sem perder os comentários.

Corpo: um objeto JSON (ver a descrição).

### `GET /api/estimativa/classificacao`

Quanto falta classificar, pelo tempo mediano por documento das execuções anteriores.

### `GET /api/modelos`

Memória, perfis, modelos instalados no Ollama e os modelos do projeto.

### `POST /api/modelos/baixar`

Baixa um modelo do Ollama em segundo plano (um job, com o progresso em MB).

Corpo (JSON, `PedidoDownload`):

| Campo | Tipo |
|---|---|
| `modelo` | texto |

### `GET /api/projeto/etapas`

O estado de cada etapa do pipeline, para a linha de metrô da vista Projeto.

### `GET /api/revistas`

As revistas correntes do SciELO Brasil (o retrato empacotado), por nome, acrônimo, ISSN ou área; com `issn`, só as desses ISSNs (separados por vírgula), na ordem pedida.

| Parâmetro | Onde | Tipo | Obrigatório |
|---|---|---|---|
| `busca` | consulta | texto | não |
| `area` | consulta | texto | não |
| `issn` | consulta | texto | não |

## Validação

### `POST /api/validacao/amostra`

Sorteia a amostra de validação (como `mapa validar amostra`) e exporta os textos para codificar. Com uma amostra já sorteada, só `refazer` sorteia outra.

Corpo (JSON, `PedidoAmostra`):

| Campo | Tipo |
|---|---|
| `n` | inteiro |
| `refazer` | booleano |

### `PUT /api/validacao/codificacoes/{doc}`

Grava as respostas de um codificador para um documento da amostra.

| Parâmetro | Onde | Tipo | Obrigatório |
|---|---|---|---|
| `doc` | caminho | texto | sim |

Corpo (JSON, `Codificacao`):

| Campo | Tipo |
|---|---|
| `codificador` | texto |
| `respostas` | objeto |
| `completa` | booleano |

### `GET /api/validacao/fila`

A amostra na ordem da fila do codificador, com as respostas que ele já deu.

| Parâmetro | Onde | Tipo | Obrigatório |
|---|---|---|---|
| `codificador` | consulta | texto | sim |

### `GET /api/validacao/metricas`

A concordância agora, com as divergências de todos os codificadores.
