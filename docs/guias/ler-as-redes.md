# Ler as redes

A vista **Redes** do painel e da demo tem quatro modos. Em todos, o recorte comum vale: anos, revistas e tópicos
escolhidos em outra vista chegam aqui, e o que fica de fora esmaece (o desenho não se move).

## Coautoria

Cada ponto é uma pessoa, e cada linha liga duas pessoas que escreveram juntas. O tamanho do ponto cresce com o número
de artigos; a cor é a da comunidade (o macrotema mais frequente nos artigos dela). A espessura da linha é o peso
fracionário: dois autores que escreveram vários artigos a dois têm uma linha forte; dez autores num único artigo, dez
linhas fracas.

- **O que dá para ler:** grupos que publicam juntos, pessoas que ligam grupos (pontes), o peso da colaboração ao
  longo do tempo (as séries ao lado: a fração de artigos com coautoria e o número médio de autores).
- **O que não dá:** importância ou qualidade. Mais coautores não é mais relevância, e a rede só vê o que está no
  corpus.

Um clique abre o cartão da pessoa, com os artigos dela no recorte.

## Instituições

O mesmo, com as instituições das afiliações. O cartão tem "Filtrar por esta instituição", que leva o recorte para as
outras vistas.

## Estados

Arcos entre as UFs cujos pesquisadores escreveram juntos, e para o exterior (`EX`). A espessura é o peso fracionário.
Um clique numa UF filtra o recorte por ela.

## Citações

- **Cânone:** as obras de fora do corpus mais citadas pelos artigos do recorte, com a cor do macrotema de quem cita.
  Lembre que o cânone só vê obras que o OpenAlex indexa (cerca de metade das referências): livros e capítulos em
  português ficam de fora com frequência. Muitos livros chegam pelo registro de uma resenha; o autor e o ano
  mostrados são os das referências dos próprios artigos, e a coluna "Registro do OpenAlex" da tabela mostra o
  registro original (o resenhista e o ano da resenha) quando ele difere.
- **Fluxo entre macrotemas:** cada célula conta as citações de artigos de um macrotema (linha) para artigos de outro
  (coluna), dentro do corpus. A diagonal é a citação dentro do próprio macrotema.

Cada figura tem "Ver como tabela" e pode ser exportada como as outras.
