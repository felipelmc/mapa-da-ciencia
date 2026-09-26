# 0008. Geografia: afiliações casadas com as instituições do OpenAlex

- **Status:** proposta (M4)
- **Data:** 2026-09-26
- **Marco:** M4

## Contexto

A vista Geografia do M4 conta a produção por UF, país e instituição. A ArticleMeta traz a afiliação de cada autor, mas de dois jeitos:

- a **`v240`**, normalizada pelo SciELO: nome da instituição "mãe", cidade, UF por extenso e país em ISO-2. No piloto, quase só a partir de 2014: são 20 afiliações `v240` de 2010 a 2013 e 4.071 depois;
- a **`v70`**, como o autor escreveu: "USP", "PUC-Rio", "Universidade de Maryland", "Centro de Formação da Câmara dos Deputados", com o país às vezes errado ("Universidade de Cambridge, Brasil"). São 1.129 afiliações `v70` até 2013 e 1.552 depois.

Contar direto pelos textos daria dezenas de grafias para a mesma instituição. O Felipe decidiu usar o **OpenAlex/ROR como base**: a instituição canônica vem do OpenAlex, casada com a afiliação da ArticleMeta do mesmo artigo e conferida pelo país; uma tabela de apelidos editável corrige erros; `mapa geografia --revisar` lista o que não casou.

O OpenAlex tem, para cada autor, as instituições que reconheceu e o texto de afiliação de onde as tirou. Nos artigos antigos, esse texto muitas vezes é um pedaço do PDF raspado ("Em maio de 2007 o Ministério Público Federal ingressou…", "Falwell, de Susan Harding"), e a instituição que o OpenAlex liga a ele não tem relação com o autor (Harding University, Diversitech, a American Society of Safety Professionals para Edmund Burke).

## Decisão

1. **Registros das instituições na coleta.** A coleta busca no OpenAlex os registros das instituições das autorias e das que estão acima delas (siglas, nomes alternativos, país, região, cidade, tipo, linhagem), em lotes de 100, com cache em `brutos/`. A geografia roda sem rede.
2. **Autores alinhados** entre as duas fontes pela posição quando o sobrenome confere, depois pelo sobrenome. No piloto, 7.011 de 7.069 pares.
3. **Candidatos do mais próximo ao mais distante** (`geografia/casamento.py`):

    | Nível | Candidatos | Exigência |
    |---|---|---|
    | `apelido` | `apelidos.csv` do pacote e `instituicoes.yaml` do projeto | texto igual |
    | `autoria` | instituições que o OpenAlex deu ao mesmo autor | semelhança ≥ 0,5 |
    | `obra` | instituições de todos os autores da obra | ≥ 0,75 |
    | `corpus` | o mesmo texto já casado nos níveis acima em outros documentos | 2 casamentos, 80% de concordância |
    | `indice` | todas as instituições conhecidas | ≥ 0,9, com 0,1 de margem sobre a segunda |

    Um candidato do documento perde para um do índice que casa com 0,1 a mais (o OpenAlex deu "Universidade Cidade de São Paulo" a quem escreveu "Universidade de São Paulo"). No índice, um texto que não nomeia uma organização ("Estado de São Paulo") não casa, e um empate sem país na fonte é desfeito a favor do país mais comum do corpus ("USP" é a de São Paulo, não a San Pablo CEU).
4. **Semelhança**: Dice ponderado por IDF entre conjuntos de palavras, sem acentos e sem palavras vazias, com as palavras genéricas traduzidas para uma forma só ("university", "universidad" → "universidade"), os nomes compostos de UF juntados numa palavra ("Rio Grande do Sul") e as categorias "Instituto Federal" e "CEFET" juntadas também. Compara-se o texto inteiro e cada parte dele (separada por vírgula, parênteses, " - "), sem as partes que são só um lugar, e a organização que contém uma unidade ("… da Universidade de Brasília"). Uma sigla do registro que aparece no texto casa direto, se as outras palavras da mesma parte não contradizem o nome ("PUC Minas" não casa com a PUC do Chile, cuja sigla é "PUC").
5. **Vetos** contra nomes parecidos:
    - palavras **discriminantes** diferentes nos dois nomes: federal, estadual, municipal, católica, rural, tecnológica, nova, livre, aberta e os pontos cardeais (UERJ × UFRJ, UFMS × UFMT, UTFPR × UFPR);
    - **substituição**: cada nome tem uma palavra distintiva que o outro não tem (Paraná × Pará, Administração × Saúde, Campinas × Rio). Sobrar palavras de um lado só (o departamento no texto, "College Park" no nome) não é conflito;
    - só um **lugar** em comum ("London" × "SOAS University of London");
    - **país** diferente, quando a fonte informa o país. O veto vale mesmo quando a `v70` erra o país: aceitar nomes idênticos de outro país casaria a Escola Superior de Guerra com a da Colômbia.
6. **Subida na linhagem** até a organização de ensino "mãe", como faz a `v240`: hospitais, centros e escolas de uma universidade contam para ela (HC-Unicamp → Unicamp; EAESP → FGV). Sobe só quem não é ensino ou tem nome de unidade (Escola, Faculdade, Instituto…), e só quando há uma mãe mais próxima: King's College London não sobe para a University of London, e um laboratório de duas universidades fica como está. `instituicoes.yaml` mantém separada a que o pesquisador quiser.
7. **Instituições do OpenAlex sem texto da ArticleMeta** (autores sem afiliação na ArticleMeta, documentos só do OpenAlex) valem só quando o texto que as sustenta parece uma afiliação (sem ano, sem cara de frase, sem "Cidade: Editora") e casa com o nome dela com semelhança ≥ 0,9. Os textos que não sustentam nenhuma instituição passam pelos níveis `corpus` e `indice`.

## Evidência

`scripts/calibrar_geografia.py` no piloto (4.275 artigos, 967 instituições do OpenAlex), em 2026-09-26. Identificação por fonte:

| Fonte | Vínculos | Identificados |
|---|---:|---:|
| `v240` | 4.268 | 4.244 (99,4%) |
| `v70` | 2.773 | 2.323 (83,8%) |
| OpenAlex (autores sem afiliação na ArticleMeta) | 201 | 159 (79,1%) |
| **Total** | **7.242** | **6.726 (92,9%)** |

O casamento do corpus inteiro leva menos de um segundo.

**Precisão.** Quatro rodadas de uma amostra estratificada por nível (semente 7, 200 vínculos cada) foram lidas uma a uma, comparando o texto com a instituição casada e, para os não casados, com os três melhores candidatos do índice. Cada rodada achou erros que viraram regra: o veto de substituição, a conferência das instituições do OpenAlex pelo texto, a subida só por unidades, o "Pará" que era palavra vazia, o "college" de College Park tratado como lugar. Depois disso, uma amostra independente (semente 2024, 200 vínculos, `dados/0008-amostra-geografia.csv`) mediu:

| Nível | Rotulados | Certos | IC 95% (Wilson) | Vínculos no corpus |
|---|---:|---:|---|---:|
| `apelido` | 6 | 6 | 61–100% | 12 |
| `autoria` | 60 | 60 | 94–100% | 5.761 |
| `obra` | 20 | 20 | 84–100% | 117 |
| `corpus` | 24 | 24 | 86–100% | 438 |
| `indice` | 40 | 40 | 91–100% | 260 |
| `openalex` | 20 | 18 | 70–97% | 138 |

A precisão dos identificados, ponderada pelo tamanho de cada nível, é de 99,8%. Os erros restantes estão no nível `openalex`: textos raspados que citam uma organização ("Programa de Pós-Graduação … da Casa de Oswaldo Cruz", ligado pelo OpenAlex ao CNPq; "Movimento dos Trabalhadores Sem-Terra (MST) e da Comissão Pastoral da Terra (CPT)…", ligado à CPT). Depois da primeira leitura da amostra independente, duas regras desse nível mudaram (a exigência de 0,9 e o filtro "Cidade: Editora"); por isso a estimativa dele é um pouco otimista.

Dos 30 vínculos não casados da amostra, 26 não tinham a instituição certa entre os candidatos: INCTs, grupos de pesquisa, a Câmara Municipal de São Paulo, universidades que não aparecem em nenhuma autoria do OpenAlex. Os 4 que tinham ficaram de fora por uma trava: o país da fonte diferente do registro ("University of Macau" com o país "China", "Vanderbilt University" com "Brasil"), um empate sem margem (um centro do CONICET) e o nome em inglês de uma instituição que só tem apelido em português (IESP). Nas rodadas de desenvolvimento apareceram outros do mesmo tipo: "Universidade Católica do Rio de Janeiro" (PUC-Rio, 0,81), "Centro de Formação da Câmara dos Deputados" (Cefor, 0,76).

## Consequências

- A `v70` fica abaixo da meta de 85% do plano (83,8%). O que falta é, na maior parte, instituição que o índice não conhece: resolve-se pelo `instituicoes.yaml` do projeto, com `mapa geografia --revisar` listando os textos mais frequentes. O piloto recebe o seu.
- Autores com o país errado na `v70` ficam sem instituição e contam no país que a fonte escreveu.
- Os limiares ficam no topo de `casamento.py`. Mudá-los pede uma nova rodada de `scripts/calibrar_geografia.py`, que herda os rótulos já feitos (`--anteriores`) e mostra só os pares novos para rotular.
- A amostra rotulada é uma leitura do Claude, não de um especialista em instituições brasileiras. O Felipe pode conferir `dados/0008-amostra-geografia.csv` (coluna `rotulo`).

## Como reproduzir

```bash
uv run python scripts/calibrar_geografia.py projetos/cp-scielo
uv run python scripts/calibrar_geografia.py projetos/cp-scielo --rotulada docs/decisoes/dados/0008-amostra-geografia.csv
```
