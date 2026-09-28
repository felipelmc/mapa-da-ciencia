# Exportar figuras

Cada gráfico do painel (e do site publicado) tem, embaixo, o botão **Exportar**. Ele baixa a figura como está na tela, com o recorte atual, em três formatos:

| Formato | Para quê | O que leva |
|---|---|---|
| **SVG** | Artigos e edição (Illustrator, Inkscape, LibreOffice) | O gráfico vetorial, com o título, o recorte, a fonte, o n e a data, e as fontes embutidas: abre igual em qualquer programa |
| **PNG** | Slides, redes, documentos de texto | O mesmo SVG em imagem, na resolução do tamanho escolhido |
| **CSV** | Refazer o gráfico em outro programa, conferir os números | Os números da tabela da figura ("Ver como tabela") sem formatação: ponto decimal, sem separador de milhar, proporções como fração (de 0 a 1), intervalos em duas colunas e célula vazia onde não há valor. Em UTF-8, separado por vírgulas: o `read.csv` do R e o `read_csv` do pandas leem sem limpeza; no Excel em português, abra por **Dados › De Texto/CSV** e escolha a vírgula como delimitador |

## Tamanhos

| Tamanho | Largura | Tema |
|---|---|---|
| Artigo, 1 coluna | 85 mm, 300 dpi | Prancha (claro) |
| Artigo, 2 colunas | 174 mm, 300 dpi | Prancha |
| Artigo, 2 colunas, 600 dpi | 174 mm, 600 dpi | Prancha |
| Slide | 1.920 px | o da tela |
| Telão | 3.840 px | Observatório (escuro) |

Os tamanhos de artigo usam sempre o tema **Prancha**, feito para papel, mesmo que a tela esteja no Observatório. No SVG, a largura vai em milímetros: ao inserir a figura no editor de texto, ela já entra no tamanho da coluna.

O fundo da figura é sempre opaco, na cor do tema, para o texto não sumir num slide escuro. As legendas das figuras das Redes (as cores dos macrotemas, o peso das ligações, as maiores comunidades, os macrotemas de quem cita no cânone) vão junto, embaixo do gráfico, e a figura se lê sozinha.

## O que não vai

- Os controles e as outras legendas feitas em HTML fora do gráfico (a escala de cores dos mapas, os botões de modo) não entram no SVG nem no PNG. Descreva a escala na legenda da figura, ou use o CSV.
- As redes de coautoria e de instituições são desenhadas num canvas, por causa dos milhares de nós: no SVG, os nós e as linhas entram como imagem (em dobro da resolução da tela), e só os rótulos, a legenda e os textos são vetoriais.
- Figuras que são tabelas (o cruzamento da vista Classificação, o ranking das instituições) só exportam o CSV.

## Citar

O rodapé da figura diz de onde vêm os dados, quantos documentos entraram e quando ela foi gerada. Numa publicação, cite também o projeto (o [CITATION.cff](https://github.com/felipelmc/mapa-da-ciencia/blob/main/CITATION.cff) do repositório) e informe o modelo e a versão do codebook, que estão na página Metodologia do site publicado ou no `mapa status`.
