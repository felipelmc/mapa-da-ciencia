# Oficina no Colab

Um roteiro para uma oficina de duas horas, com gente que nunca instalou Python. Cada participante roda o caderno [`oficina_colab.ipynb`](https://colab.research.google.com/github/felipelmc/mapa-da-ciencia/blob/main/notebooks/oficina_colab.ipynb) no Google Colab, numa máquina com GPU emprestada pelo Google, e sai com um mapa da *Opinião Pública* de 2020 a 2024: tópicos no tempo, geografia dos autores e uma amostra classificada por um modelo de linguagem, com a evidência de cada resposta.

!!! info "O que cada participante precisa"
    - Uma conta Google (o Colab é gratuito).
    - Um navegador. Nada é instalado no computador.

!!! warning "Tempos estimados"
    Os tempos do caderno e do roteiro são estimativas a partir do computador de desenvolvimento e do tamanho dos modelos. Rode o caderno uma vez antes da oficina para ver os tempos na T4 do dia.

## Antes da oficina

- Abra o caderno e rode tudo uma vez, uns dias antes: o Colab e o SciELO mudam, e é bom ver os tempos na prática.
- A GPU gratuita do Colab (T4) tem cota. Numa turma grande, alguns participantes podem ficar sem GPU; o caderno avisa na primeira célula. Sem GPU, os modelos rodam na CPU, bem mais devagar: forme duplas.
- Tenha à mão o painel do piloto publicado ([demo](https://felipelamarca.com/mapa-da-ciencia/demo/)), para mostrar enquanto os modelos trabalham.

## Roteiro

| Tempo | O quê |
|---|---|
| 0:00 | Apresentação: o que é um mapa da literatura e o que modelos abertos fazem (e não fazem) com resumos. Mostre a demo. |
| 0:15 | Abrir o caderno, escolher a GPU T4 e rodar a instalação e o download dos modelos (seções 1 e 2, uns 5 minutos). |
| 0:25 | Seção 3: o projeto e a coleta. Leia o `mapa.yaml` com a turma: no painel de arquivos do Colab (o ícone de pasta, à esquerda), um clique duplo em `oficina/mapa.yaml` o abre. |
| 0:35 | Seção 4: tópicos e geografia (uns 5 minutos). Enquanto roda, explique *embeddings* e agrupamento ([Como os tópicos são construídos](../explicacoes/topicos.md)). |
| 0:45 | Seção 5: o codebook e a classificação da amostra (uns 6 minutos). Leia o `codebook.yaml` com a turma: cada pergunta, cada categoria. |
| 1:00 | Seção 6: o painel. Cada um explora o mapa, os tópicos e a geografia; depois, a classificação, com os trechos citados. |
| 1:20 | Validação: cada um codifica 10 fichas às cegas (Validação › Codificar) e compara com o modelo. Discussão: onde o modelo erra? O codebook estava claro? |
| 1:45 | Encerramento: como levar para o próprio computador ([Seu primeiro mapa](primeiro-mapa.md)) e para outro recorte ([Montar um recorte](../guias/recorte.md)). |

## Se algo der errado

- **"Sem GPU"**: o Colab não tinha T4 disponível. Tente de novo mais tarde, ou siga na CPU com uma amostra menor: na célula da seção 5, troque `--n 30` por `--n 10` antes de rodá-la (se a amostra já foi sorteada, acrescente `--refazer`).
- **O download do modelo para no meio**: rode a célula de novo; o Ollama continua de onde parou.
- **Rodei uma célula duas vezes**: pode. A célula da seção 3 volta para `/content` antes de criar o projeto; o `mapa novo` avisa que o projeto já existe, e a coleta e as outras etapas continuam de onde pararam.
- **A coleta reclama da rede**: o SciELO ou o OpenAlex podem estar lentos. Rode `!mapa coletar` de novo; o que já veio fica guardado.
- **O painel não abre**: rode a célula do painel de novo. Ele abre numa janela nova do navegador; libere as janelas pop-up do Colab.
- **"O modelo não cabe na memória"**: a guarda de memória do `mapa` confere a memória da máquina antes de carregar um modelo. Se o Colab estiver com pouca memória livre, reinicie o ambiente de execução e rode de novo a partir da seção 1.
- **A sessão caiu**: o Colab apaga a máquina depois de um tempo parado. Os arquivos da pasta `oficina/` se perdem; para guardá-los, siga "Para ir além" no fim do caderno.

## Depois da oficina

O caderno termina com os caminhos para continuar: trocar o recorte, escrever o próprio codebook e levar o projeto para o computador. A [documentação](../documentacao.md) tem os guias de cada etapa.
