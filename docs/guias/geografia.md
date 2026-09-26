# Gerar a geografia

A etapa `mapa geografia` liga cada afiliação dos autores a uma instituição, com UF e país, e faz a contagem fracionária da produção. É ela que alimenta a vista Geografia do painel. Esta página mostra como rodar, como corrigir o que não casou e como consultar o resultado. Para entender o método, veja [Geografia da produção](../explicacoes/geografia.md).

## Antes de começar

- O projeto precisa de um corpus coletado com o OpenAlex ligado (o padrão). A coleta busca os registros das instituições que aparecem nas autorias, com uns 10 créditos do OpenAlex para 4 mil artigos; uma coleta feita antes da versão 0.4.0 não os tem, e basta rodar `mapa coletar` de novo (as outras respostas vêm do cache).
- A vista Geografia do painel também precisa dos tópicos (`mapa topicos`), porque a interface parte da lista de documentos do mapa.

## Rodar

```bash
uv run mapa geografia
```

A etapa leva segundos e não usa a rede nem modelos. A saída mostra:

- quantos **vínculos** (autor × afiliação) vieram de cada fonte e quantos foram ligados a uma instituição;
- as dez instituições com mais **peso** (a contagem fracionária) e o número de documentos de cada uma;
- quanto do peso ficou **sem afiliação** e como os vínculos casaram (os níveis estão explicados em [Geografia da produção](../explicacoes/geografia.md#qual-instituicao-e)).

O resultado fica em `dados/geografia/` e vai para o painel na hora. O `mapa status` ganha uma linha com a cobertura e avisa quando a geografia fica para trás: depois de uma coleta nova ou de uma mudança no `instituicoes.yaml`, rode `mapa geografia` de novo.

## Corrigir o que não casou

```bash
uv run mapa geografia --revisar
```

A revisão lista as afiliações sem instituição mais frequentes (use `--limite` para ver mais que 20), com as grafias agrupadas e as instituições conhecidas que mais se parecem com cada uma. No fim, imprime um bloco pronto para o arquivo `instituicoes.yaml`, na pasta do projeto:

- quando a instituição parecida é quase idêntica, o bloco já traz o **apelido** ativo;
- quando é só parecida, o apelido vem comentado, com o nome dela para você conferir;
- sem nenhuma parecida, vem comentado um modelo de **instituição própria**.

!!! warning "Confira cada sugestão"
    A instituição mais parecida nem sempre é a certa. No piloto, para "Brazilian Center for Analysis and Planning" (o Cebrap), a sugestão foi o Centro Universitário de Brasília. Descomente só o que você reconhecer.

Copie o que servir, descomente e rode `mapa geografia` de novo. Uma rodada costuma resolver os textos mais frequentes: no piloto, 22 apelidos e 6 instituições próprias levaram as afiliações em texto livre de 83,8% a 86,5% identificadas.

## O arquivo `instituicoes.yaml`

```yaml
apelidos:                           # texto de afiliação (como aparece) → instituição
  "PUC Minas": I170935008           # uma instituição do OpenAlex (o id I… aparece na revisão)
  "Centro de Estudos da Metrópole": cem
instituicoes:
  cem:                              # uma instituição que o OpenAlex não tem
    nome: Centro de Estudos da Metrópole
    sigla: CEM
    pais: BR
    uf: SP
  I44202434:                        # uma instituição do OpenAlex: corrige campos
    uf: RJ
    separada: true
```

- **`apelidos`** liga um texto de afiliação a uma instituição. O texto é comparado sem acentos, maiúsculas e pontuação, e vale também como parte de um texto maior ("Departamento de Ciência Política, PUC Minas").
- **`instituicoes`** declara instituições próprias (com `nome` e `pais` obrigatórios; `sigla`, `uf` e `cidade` opcionais) ou corrige as do OpenAlex. Para uma do OpenAlex, `uf` passa a valer para os vínculos sem UF na fonte, e `separada: true` impede que ela suba para a instituição "mãe" (útil para quem quer contar uma escola separada da universidade).
- O país e a UF aceitam o código ou o nome ("BR" ou "Brasil", "SP" ou "São Paulo").

Um apelido que aponta para um id desconhecido, ou uma instituição própria sem nome ou país, faz a etapa parar com uma mensagem que diz o que corrigir.

## Consultar o resultado

A [API Python](../referencia/api-python.md#tabelas-para-consulta) expõe três tabelas depois da etapa: `vinculos` (cada autor ligado a uma instituição, com o texto da fonte e o nível do casamento), `pesos` (a contagem fracionária) e `instituicoes`. Por exemplo, o peso de cada UF:

```sql
SELECT uf, round(sum(peso), 1) AS peso, count(DISTINCT doc) AS documentos
FROM pesos WHERE pais = 'BR' AND uf IS NOT NULL
GROUP BY uf ORDER BY peso DESC
```

E os textos que casaram pelo índice global, para conferir os casamentos menos certos:

```sql
SELECT texto, instituicao, semelhanca FROM vinculos WHERE nivel = 'indice' ORDER BY semelhanca
```

## Problemas comuns

**"Sem os registros das instituições do OpenAlex"**
: O corpus foi coletado antes da versão 0.4.0, ou com `--sem-openalex`. A etapa roda mesmo assim, só com os nomes que vêm nas autorias, mas casa menos. Rode `mapa coletar` para buscar os registros.

**Uma instituição conhecida não casa**
: Veja na revisão se ela aparece como parecida. Se não aparece, o OpenAlex não a associou a nenhum autor do corpus: declare-a como instituição própria.

**Um casamento errado**
: Um apelido no `instituicoes.yaml` tem prioridade sobre o casamento automático. Para conferir por que casou, procure o texto na tabela `vinculos` (colunas `nivel` e `semelhanca`).
