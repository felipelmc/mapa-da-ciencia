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
| Início | Números do corpus e macrotemas | agora |
| Mapa | Cada artigo como um ponto; artigos próximos tratam de assuntos próximos. Contornos e rótulos dos tópicos (dos macrotemas, de longe), colorir por tópico, macrotema, revista ou ano, e filtrar pela legenda ou pelos rótulos; busca, laço e linha do tempo com play. Clicar num ponto abre o cartão do documento, com o resumo e os 5 mais parecidos ([Ler o mapa](ler-o-mapa.md)) | agora |
| Tópicos | Evolução dos tópicos no tempo, em alta e em queda | M4 |
| Classificação | Distribuição das variáveis do codebook, com evidências | M5 |
| Geografia | Produção por UF, país e instituição | M4 |
| Validação | Codificação da amostra e concordância com o modelo | M5 |
| Projeto | Rodar as etapas e acompanhar o progresso (só no painel local) | M6 |
| Redes | Coautoria e citação | v2 |

A interface tem dois temas: **Observatório** (escuro, bom para projetar) e **Prancha** (claro, bom para figuras de artigo). Ela segue o tema do sistema, e o botão na barra superior alterna entre os dois.

## Projeto novo, painel vazio

Logo depois do `mapa novo`, o painel abre, mas sem dados: a página inicial explica quais etapas rodar primeiro. Os números e as vistas aparecem conforme as etapas vão sendo concluídas:

- depois do `mapa coletar`, a página inicial mostra quantos documentos e revistas há e o período coberto;
- depois do `mapa topicos`, a página inicial mostra os tópicos e os macrotemas, e a vista Mapa mostra cada documento como um ponto.

Cada etapa grava seus arquivos em `saida/dados/`. Basta recarregar a página, sem reiniciar o `mapa painel`.

## Como funciona

O `mapa painel` sobe um servidor local ([FastAPI](https://fastapi.tiangolo.com)) que entrega a interface compilada, os arquivos do [contrato de dados](../referencia/contrato.md) do projeto e uma API para as ações que só fazem sentido localmente (rodar etapas, codificar a amostra). O site publicado com `mapa publicar` (marco M7) é a mesma interface lendo os mesmos arquivos, só que sem a API: por isso ele é somente leitura.
