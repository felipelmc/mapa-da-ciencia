# Limitações e vieses

O `mapa-da-ciencia` descreve uma literatura a partir de títulos, resumos e afiliações, com modelos abertos que rodam num computador comum. Cada etapa tem limites próprios, documentados na página dela. Esta página junta os que pesam na leitura do conjunto, para a seção de limitações de um artigo que use o método.

## O corpus

- **O SciELO não é a ciência política brasileira.** O piloto cobre 10 revistas do SciELO Brasil. Ficam de fora os livros, as teses, os anais de congressos, as revistas fora do SciELO e o que pesquisadores brasileiros publicam no exterior. Um tópico "em queda" no SciELO pode estar migrando para revistas estrangeiras. Veja [Fontes de dados](fontes.md).
- **As revistas pesam de forma diferente.** Cada revista publica um número diferente de artigos por ano, e uma revista que muda de periodicidade ou abre um dossiê desloca as proporções do corpus inteiro. A vista Tópicos mostra os pequenos múltiplos por revista para separar o efeito de uma revista do da área.
- **Só artigos.** Resenhas, editoriais e erratas ficam de fora (670 registros no piloto). É uma escolha do recorte, que muda o que "a literatura" quer dizer.
- **Metadados com erros.** DOIs trocados, anos de publicação que não batem com o fascículo e afiliações incompletas existem nas fontes. A coleta confere o casamento entre fontes e marca as suspeitas de duplicata, mas não corrige a fonte.

## Resumos, não artigos

- Tópicos e classificação leem **só o título e o resumo**. Um resumo é o que o autor escolheu destacar, no espaço de umas 200 palavras. Uma técnica de pesquisa, um período ou um recorte que o artigo deixa claro, mas o resumo não menciona, sai como "não informado".
- **Idioma.** Os tópicos usam o resumo em inglês de 97% dos artigos do piloto; os outros entram pelo resumo em português ou espanhol (2,1%) ou só pelo título (0,7%), marcados. A classificação lê o resumo em português quando existe (82%) e, se não, o em inglês (18%, três quartos deles das três revistas que publicam só em inglês: BPSR, CINT e RBPI). Um resumo em inglês traduzido às pressas pode não dizer o mesmo que o original. Veja [Como os tópicos são construídos](topicos.md#1-o-texto-de-analise).
- **Resumos que não são resumos.** No piloto, cerca de 25 "resumos" (0,5%) são fragmentos da fonte (nomes, referências, cabeçalhos, textos de repositório), e cerca de 40 têm o idioma declarado errado. Eles entram nos 99,3% com resumo e são usados nos tópicos e na classificação como vieram.

## Tópicos

- **Os tópicos dependem dos parâmetros.** O número e o tamanho dos tópicos vêm do agrupamento (HDBSCAN) e dos seus parâmetros, calibrados no piloto ([ADR 0007](../decisoes/0007-parametros-dos-topicos.md)). Outra calibração daria outra granularidade: os tópicos são uma descrição útil do corpus, não categorias naturais.
- **Ruído.** No piloto, um terço dos documentos não entra no núcleo de nenhum tópico; 22,5% são reatribuídos por vizinhança e 11% ficam sem tópico. Os sem tópico tendem a ser os artigos mais singulares.
- **Estabilidade.** O ARI entre três sementes é 0,89 no núcleo (os 56% de documentos que estão no núcleo nas duas execuções comparadas) e 0,78 contando os reatribuídos: os tópicos grandes são estáveis, mas fronteiras entre tópicos vizinhos mudam com a semente.
- **Rótulos.** Os nomes dos tópicos foram escritos por um modelo de linguagem a partir de palavras-chave e títulos representativos. Leia o tópico pelos documentos, não só pelo nome, e corrija o que precisar no `rotulos.yaml`.
- **Tendências e comparações múltiplas.** Com dezenas de tópicos testados, alguns aparecem "em alta" ou "em queda" por acaso, mesmo com o intervalo de 95%. A vista avisa disso, e a tendência é uma inclinação média no período, que não vê mudanças de direção. Veja [Em alta e em queda](topicos.md#12-em-alta-e-em-queda).

## Geografia

- **Cobertura desigual no tempo.** Nos primeiros anos do piloto, as afiliações vêm quase só como texto livre e mais autores ficam sem afiliação. Comparar a geografia de 2010 com a de 2024 exige olhar a cobertura por ano, que a vista mostra.
- **O casamento das instituições erra pouco, mas erra.** 93,9% dos vínculos do piloto foram ligados a uma instituição, com precisão de 99,8% numa amostra lida à mão. Os erros medidos numa amostra independente vêm de textos raspados pelo OpenAlex que citam uma organização (CNPq, CPT), e os vínculos que deviam casar e não casaram ficaram de fora pela trava de país, por um empate ou por um nome traduzido. Veja [Geografia da produção](geografia.md#limitacoes-e-vieses).
- **Contagem fracionária é uma escolha.** Cada artigo vale 1, dividido entre autores e afiliações. A contagem inteira (cada instituição recebe 1 por artigo) favorece as instituições que publicam em equipes grandes; as duas estão no contrato.

## Classificação e validação

- **Modelos pequenos.** O modelo padrão (`qwen3.5:9b`) roda num notebook com 16 GB de memória. Modelos maiores podem concordar mais com uma leitura humana, ao preço do hardware; a comparação entre modelos (McNemar) mede isso no seu corpus. As métricas do piloto são do `qwen3.5:9b`; o `qwen3.5:4b` do perfil `leve` ainda não passou pela validação, e a do seu projeto mede o modelo que você usar.
- **A evidência mostra de onde, não se está certo.** O modelo cita o trecho que justifica a resposta, e a conferência diz se o trecho está mesmo no resumo (93,4% literal no piloto). Uma evidência literal com a categoria errada continua errada. Veja [Classificação ancorada em evidência](classificacao.md).
- **A referência do piloto não é uma pessoa.** No piloto, a amostra de 200 artigos foi codificada às cegas por outro modelo (Claude), como codificador de referência. O kappa mede a concordância com essa leitura, não com um especialista; ele varia de 0,37 (técnica de pesquisa) a 0,93 (Brasil como caso). Uma codificação humana da mesma amostra é o próximo passo, e o painel tem a vista para isso. Veja [Desenho da validação](validacao.md).
- **Uma rodada, um codebook.** As métricas valem para o codebook de exemplo, como ele está. Mudar uma definição pede classificar e medir de novo.
- **Variáveis fracas.** Uma variável com kappa baixo (a técnica, no piloto) não deve ser usada sozinha numa análise sem revisão: leia as divergências, reescreva as definições e meça de novo ([Ler kappa e PABAK](../guias/ler-kappa-e-pabak.md)).

## Reprodutibilidade

- O mesmo projeto, com o mesmo modelo (o *digest* do manifesto), a mesma semente e os mesmos parâmetros, reproduz a classificação a partir do cache. Rodar do zero em outra máquina pode mudar algumas respostas: a geração com temperatura 0 é determinística no mesmo hardware, mas não garantidamente entre GPUs diferentes. O UMAP também varia entre máquinas (o `numba` usa otimizações que dependem do processador), e por isso as posições no mapa não são comparadas entre máquinas, só os agrupamentos. Veja [Reprodutibilidade](reprodutibilidade.md).
- As fontes mudam: a ArticleMeta e o OpenAlex corrigem registros, e uma nova coleta pode trazer outros números. As respostas brutas ficam guardadas em `brutos/`, e o manifesto registra quando cada coleta foi feita.
