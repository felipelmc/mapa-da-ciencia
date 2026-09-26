# Usar o painel

O painel é a interface do `mapa-da-ciencia`: um site que roda **só na sua máquina**, servido pelo próprio comando `mapa`, sem nada publicado na internet.

## Abrir

Dentro da pasta de um projeto:

```bash
mapa painel
```

Sem projeto, com os dados de exemplo:

```bash
mapa painel --exemplo
```

O navegador abre em `http://127.0.0.1:8765/`. Para encerrar, aperte ++ctrl+c++ no terminal.

| Opção | Para quê |
|---|---|
| `--exemplo` | Mostra o exemplo sintético, sem precisar de projeto |
| `--porta 8800` | Usa outra porta (a padrão, 8765, pode estar ocupada) |
| `--nao-abrir` | Não abre o navegador (útil em servidores e no Colab) |
| `--projeto`, `-P` | Indica a pasta do projeto quando você está fora dela |

## O que aparece

| Vista | Mostra | Disponível |
|---|---|---|
| Início | Números do corpus e macrotemas, com a participação de cada um por ano | agora |
| Mapa | Cada artigo como um ponto; artigos próximos tratam de assuntos próximos. Contornos e rótulos dos tópicos (dos macrotemas, de longe), colorir por tópico, macrotema, revista ou ano, e filtrar pela legenda ou pelos rótulos; busca, laço e linha do tempo com play. Clicar num ponto abre o cartão do documento, com o resumo e os 5 mais parecidos ([Ler o mapa](ler-o-mapa.md)) | agora |
| Tópicos | O fluxo dos macrotemas e dos tópicos no tempo, em três modos; os tópicos em alta e em queda; a gaveta de cada tópico; o perfil de cada revista ([Ler os tópicos no tempo](ler-os-topicos.md)) | agora |
| Classificação | Uma variável do codebook por vez: a distribuição por ano, o cruzamento com macrotemas, tópicos ou revistas, os selos de concordância e os documentos de cada célula com a evidência marcada no resumo ([Ler a classificação](ler-a-classificacao.md)) | agora |
| Geografia | Produção por UF, país e instituição, com contagem fracionária, e a cobertura das afiliações por ano ([Ler a geografia](ler-a-geografia.md)) | agora |
| Validação | A concordância do modelo com quem codificou a amostra, a matriz de confusão e as divergências; no painel local, a codificação da amostra pelo teclado ([Codificar a amostra](codificar-a-amostra.md), [Ler kappa e PABAK](ler-kappa-e-pabak.md)) | agora |
| Projeto | As etapas do pipeline numa linha de metrô (em dia, desatualizadas ou pendentes), rodar e cancelar cada uma com o progresso ao vivo, a estimativa da classificação e os modelos do Ollama (só no painel local) | agora |
| Redes | Coautoria e citação | v2 |

A interface tem dois temas: **Observatório** (escuro, bom para projetar) e **Prancha** (claro, bom para figuras de artigo). Ela segue o tema do sistema, e o botão na barra superior alterna entre os dois.

## Projeto novo, painel vazio

Logo depois do `mapa novo`, o painel abre, mas sem dados: a página inicial explica quais etapas rodar primeiro. Os números e as vistas aparecem conforme as etapas vão sendo concluídas:

- depois do `mapa coletar`, a página inicial mostra quantos documentos e revistas há e o período coberto;
- depois do `mapa topicos`, a página inicial mostra os tópicos e os macrotemas, a vista Mapa mostra cada documento como um ponto, e a vista Tópicos mostra os temas no tempo;
- depois do `mapa geografia`, a vista Geografia mostra de onde vêm os autores.
- depois do `mapa classificar`, a vista Classificação mostra as respostas do modelo, e o cartão do Mapa marca as evidências no resumo;
- depois do `mapa validar amostra` e da codificação, a vista Validação mostra a concordância.

Mapa, Tópicos, Classificação e Geografia dividem o **recorte**, a barra abaixo do título: período, revistas, tópicos, busca, laço, UFs, países e instituições. Ele vai junto quando você troca de vista pelo trilho, e fica no endereço da página, como tudo o que está na tela.

Cada etapa grava seus arquivos em `saida/dados/`. Basta recarregar a página, sem reiniciar o `mapa painel`.

## Rodar as etapas pelo painel

No painel local, a vista **Projeto** mostra as etapas numa linha, na ordem em que rodam: coleta, tópicos, geografia, classificação e validação. Cada estação diz se a etapa nunca rodou, se está em dia ou se ficou para trás (tracejada: o corpus, o codebook ou as correções mudaram depois da última execução), com a data, a duração e o que ela produziu.

- **Rodar** começa a etapa em segundo plano. O progresso aparece ao vivo, com as mensagens da etapa; você pode trocar de vista, fechar a aba ou recarregar a página, e ao voltar o acompanhamento continua de onde estava. Só uma etapa roda por vez.
- **Cancelar** para a etapa na próxima atualização de progresso. Como as etapas guardam o que já fizeram, rodar de novo continua de onde parou.
- Algumas etapas têm variações: a coleta e a classificação podem rodar como um **piloto com 20 documentos**, e a classificação pode **estimar o tempo** ou classificar **só a amostra** de validação.
- Quando a etapa termina, **Ver os dados novos** recarrega o painel com os arquivos que ela gerou.
- O bloco **Modelos** mostra se o Ollama está no ar e se os modelos do projeto estão instalados; o que faltar pode ser baixado dali, com o tamanho do download antes.

Na CLI, as mesmas etapas são `mapa coletar`, `mapa topicos`, `mapa geografia` e `mapa classificar`, e o que uma faz a outra enxerga: uma etapa rodada no terminal aparece em dia no painel.

## Como funciona

O `mapa painel` sobe um servidor local ([FastAPI](https://fastapi.tiangolo.com)) que entrega a interface compilada, os arquivos do [contrato de dados](../referencia/contrato.md) do projeto e uma API para o que só faz sentido localmente: rodar as etapas, editar o projeto e codificar a amostra de validação. As etapas rodam uma de cada vez numa fila do servidor, e o progresso chega ao navegador por *Server-Sent Events*, que se reconectam sozinhos se a conexão cair. O site publicado com `mapa publicar` (marco M7) é a mesma interface lendo os mesmos arquivos, só que sem a API: por isso ele é somente leitura.
