# Ler as redes

A vista **Redes** do painel e da demo tem quatro modos. Em todos, o recorte comum vale: anos, revistas e tópicos
escolhidos em outra vista chegam aqui, e o que fica de fora esmaece (o desenho não se move).

## Coautoria

Cada ponto é uma pessoa, e cada linha liga duas pessoas que escreveram juntas. O tamanho do ponto cresce com o número
de artigos; a cor é a da comunidade (o macrotema mais frequente nos artigos dela). A espessura da linha é o peso
fracionário: dois autores que escreveram vários artigos a dois têm uma linha forte; dez autores num único artigo formam
45 linhas fracas, de peso 1/9 cada.

- **O que dá para ler:** grupos que publicam juntos, pessoas que ligam grupos (pontes), o peso da colaboração ao
  longo do tempo (as séries ao lado: a fração de artigos com coautoria e o número médio de autores).
- **O que não dá:** importância ou qualidade. Mais coautores não é mais relevância, e a rede só vê o que está no
  corpus.

O maior grupo ligado (o componente principal, onde estão as comunidades, cada uma num espaço próprio) fica à esquerda;
à direita e embaixo, os grupos menores. As
duplas e os trios isolados ficam escondidos, para o desenho enquadrar o resto: "Mostrar as duplas e os trios
isolados" os traz de volta (a escolha vai para o link, com `duplas=1`, e o desenho se reenquadra). A lista embaixo do desenho dá o rótulo inteiro das maiores comunidades (no desenho sai
só o primeiro tópico).

Passe o mouse num nó: ele, os coautores dele e as ligações entre eles acendem, o resto esmaece, e os nomes dos
coautores aparecem. Um clique abre o cartão da pessoa, com os artigos dela no recorte e os coautores mais fortes, cada
um com o peso da parceria no recorte e os documentos em comum; a vizinhança fica acesa, e "Enquadrar o nó" leva o zoom
até ela. Esc (ou o ×) fecha o cartão e devolve o foco para onde ele estava. Aberto pela busca ou por um link, o nó já
vem enquadrado.

Clique numa comunidade (na lista da legenda ou no rótulo dela, no desenho) para acendê-la e enquadrá-la; a escolha vai
para o link (`comunidade=`), e "Todas" solta. Com zoom, os nomes das pessoas com mais artigos aparecem, sem se
cobrirem, e mais nomes aparecem quanto mais perto você chega.

Para aproximar: Ctrl (⌘ no Mac) + roda, a pinça do trackpad ou de dois dedos, o clique duplo ou os botões + e −. A roda
sozinha rola a página, para quem está lendo não ficar preso no grafo; em tela cheia (o botão "Tela cheia"), ela também
aproxima. Arrastar o fundo move o grafo; arrastar um nó o move de lugar, só na sua tela, para desembaraçar um trecho
("Reiniciar" devolve o desenho e o zoom). Com o grafo em foco, o teclado também serve: + e − aproximam e afastam, 0
volta ao desenho inteiro e as setas movem.

O link "Como ler as redes", ao lado do título da vista, leva à seção da Ajuda com o glossário (peso, componente,
agrupamento, modularidade).

## Instituições

O mesmo, com as instituições das afiliações. Duas instituições ficam ligadas quando aparecem juntas nas afiliações de
um artigo, mesmo que seja um autor só com duas afiliações: a ligação é entre instituições que dividem um artigo, e
não só entre equipes diferentes. O cartão tem "Filtrar por esta instituição", que leva o recorte para as
outras vistas.

## Estados

Arcos entre as UFs cujos pesquisadores escreveram juntos, e para o **Exterior** (qualquer afiliação fora do Brasil;
nos dados, `EX`). A espessura é o peso fracionário. Um clique numa UF filtra o recorte por ela.

## Citações

- **Cânone:** as obras de fora do corpus mais citadas pelos artigos do recorte, com a cor do macrotema de quem cita.
  Lembre que o cânone só vê obras que o OpenAlex indexa (cerca de metade das referências): livros e capítulos em
  português ficam de fora com frequência. Muitos livros chegam pelo registro de uma resenha. Quando há referências
  bastantes com o mesmo título (três ou mais, somando um quinto dos artigos que citam a obra), o autor e o ano
  mostrados são os das referências dos próprios artigos, e a coluna "Registro do OpenAlex" da tabela mostra o
  registro original (o resenhista e o ano da resenha); com menos, ficam os do OpenAlex.
- **Fluxo entre macrotemas:** cada célula conta as citações de artigos de um macrotema (linha) para artigos de outro
  (coluna), dentro do corpus. A diagonal é a citação dentro do próprio macrotema.

Cada figura tem "Ver como tabela" e pode ser exportada como as outras.
