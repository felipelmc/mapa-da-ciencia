# 0009. Tendência dos tópicos: em alta, em queda ou estável

- **Status:** aceita (M4)
- **Data:** 2026-09-26
- **Marco:** M4

## Contexto

A vista Tópicos do M4 mostra quais assuntos ganham e perdem espaço no corpus. É preciso uma regra para dizer que um tópico está "em alta" ou "em queda" que:

- seja interpretável para quem lê um artigo de ciência política;
- resista ao ruído: no piloto, um tópico tem em média 3 artigos por ano;
- possa ser recalculada no navegador, com os filtros do painel (revistas, período, laço), e conferida contra o Python.

O Felipe escolheu uma regressão logística da participação anual do tópico, marcando alta ou queda só quando o intervalo de 95% da inclinação não inclui zero.

## Evidência

`scripts/tendencias.py` no piloto (57 tópicos, 2010–2025, 241 a 300 artigos por ano), em 2026-09-26:

- A **dispersão** (X² de Pearson ÷ graus de liberdade) tem mediana de 1,47 e máximo de 5,48. As séries anuais variam mais do que uma binomial prevê, porque dossiês temáticos concentram artigos de um assunto num número só.
- Com a **binomial pura**, 22 tópicos são marcados (11 em alta, 11 em queda). Entre eles, "Saúde global e covid-19" (φ = 5,48) aparece em alta por causa de um pico em 2022, e "República conflitiva em Maquiavel", em queda, por causa de um dossiê no começo do período.
- Com a **quase-binomial**, que multiplica o erro-padrão por √φ, 13 são marcados (7 em alta, 6 em queda):
  - em alta: identificação partidária e polarização (+4,1 pontos percentuais no período), federalismo, capacidades estatais e implementação de políticas (+3,0), comunicação política nas redes sociais (+2,5), religião e política (+2,1), alocação de ministérios em coalizões, competição eleitoral municipal, pensamento político brasileiro e marxismo;
  - em queda: teoria social, modernidade e teoria crítica (−2,0), cobertura da imprensa (−2,0), democracia deliberativa (−1,8), representação na sociedade civil, Estado e bem-estar social, artes, cinema e crítica cultural.
- Dez desses 13 têm uma mudança que se sustenta: retirando um ano de cada vez, continuam marcados em pelo menos 12 das 16 retiradas. Três são marginais (teoria social, modernidade e teoria crítica; artes, cinema e crítica cultural; pensamento político brasileiro e marxismo): passam a estáveis com o quantil t(14) no lugar do z e, retirando um só ano, em 7 a 12 das 16 retiradas.

## Decisão

1. **Modelo:** regressão logística binomial da participação anual do tópico (documentos do tópico ÷ documentos do ano), com o ano como única variável, centrado na média dos anos usados. Anos sem nenhum documento ficam de fora.
2. **Dispersão quase-binomial:** o erro-padrão da inclinação é multiplicado por √φ, com φ = max(1, X² de Pearson ÷ (anos − 2)). A binomial pura continua disponível (`metodo_tendencia.dispersao` no contrato).
3. **Direção:** "em alta" se o intervalo de 95% (Wald, z = 1,96; desde a 2.3.0, com o quantil da t, veja o adendo) da inclinação está todo acima de zero; "em queda" se está todo abaixo; "estável" nos demais casos.
4. **Mínimos:** 5 anos com documentos e 10 documentos do tópico no período. Abaixo disso, ou quando a estimativa diverge (todos os documentos do tópico num ano extremo), a tendência é "insuficiente".
5. **Tamanho da mudança:** pontos percentuais entre as participações ajustadas no primeiro e no último ano (`pp_periodo`), e por ano (`pp_por_ano`). É o que a sparkline mostra, e é mais fácil de ler do que a inclinação no logit.
6. **Uma implementação de referência** em Python puro (`topicos/tendencia.py`), espelhada em TypeScript no navegador; os casos de `contrato/casos/tendencia.json` garantem que as duas dão o mesmo resultado, e o `topicos.json` traz o gabarito do período inteiro.

Alternativas descartadas: regressão linear na participação (ignora que a variância depende do tamanho do ano); Mann-Kendall (não dá o tamanho da mudança); Poisson ou binomial negativa nas contagens (o corpus cresce ou encolhe de ano para ano, e a participação já controla isso); *bootstrap* no navegador (lento e não reprodutível sem semente); correção para comparações múltiplas (a vista é descritiva; o aviso na interface basta).

## Consequências

- Com 57 tópicos testados a 5%, cerca de 3 marcações podem acontecer por acaso mesmo sem nenhuma tendência real. A interface e o guia avisam.
- Tópicos pequenos quase nunca são marcados: é o comportamento desejado, porque a série deles é dominada pelo ruído.
- Com filtros (uma revista, um período curto), menos tópicos passam dos mínimos, e a lista mostra "sem dados suficientes".
- Um dossiê no primeiro ou no último ano da janela (o período inteiro ou o filtrado no painel) ainda pode aparecer como tendência: a inclinação absorve o pico, e a dispersão não cresce o bastante para cobri-lo. Confira a série antes de citar.
- Uma tendência descreve o corpus coletado, não a produção da área: revistas que entram ou saem do recorte mudam as participações.

## Como reproduzir

    uv run python scripts/tendencias.py projetos/cp-scielo

## Adendo (2.3.0): o quantil t e a tendência frágil

A revisão de setembro de 2026 recomendou duas mudanças, que a seção Evidência já tinha medido: três das 13 marcações do piloto eram marginais, sumiam com o quantil t(14) no lugar do z e não resistiam à retirada de um ano.

### O quantil t

A dispersão φ é estimada com os resíduos de anos − 2 graus de liberdade (14 no período inteiro do piloto, menos num recorte do painel). Com a escala estimada, o intervalo de Wald com o quantil da normal fica estreito demais: o `summary.glm` do R e o `statsmodels` usam a t nesse caso. **Decisão:** com a dispersão quase-binomial, o intervalo usa o quantil 97,5% da t de Student com anos usados − 2 graus de liberdade (2,145 com 16 anos, 2,571 com 7); a binomial pura, que não estima a escala, continua com o da normal.

- **Implementação:** sem scipy, nos dois lados. P(|T| ≤ t) tem forma fechada para graus de liberdade inteiros (Abramowitz e Stegun, 26.7.3 e 26.7.4, só com `atan`, `sin` e `cos`), invertida por bisseção (`quantil_t` em Python, `quantilT` em `glm.ts`). O erro relativo contra o `scipy.stats.t.ppf` é de 6·10⁻¹⁴, de 1 a 500 graus de liberdade; `contrato/casos/quantil_t.json` confere os dois lados.
- **Contrato 1.7:** `metodo_tendencia.quantil` (`t` ou `normal`). Os dados até a 1.6 não trazem o campo e foram calculados com a normal: a interface usa a normal quando ele falta, e um site publicado antes continua batendo com o próprio gabarito.
- **Efeito nos tópicos da 2.2.0** (`scripts/tendencias.py`, que agora mostra as duas colunas): de 13 marcações, ficam 10 (6 em alta, 4 em queda). Saem as três marginais: teoria social, modernidade e teoria crítica; artes, cinema e crítica cultural; pensamento político brasileiro e marxismo.

Alternativas descartadas: continuar com o z (o intervalo fica estreito com 16 pontos e escala estimada) e corrigir para comparações múltiplas (a vista é descritiva, e o aviso na interface continua).

### A tendência frágil

Uma marcação pode depender de um ano só: um dossiê no começo ou no fim do período (a Consequência acima) ou um ano atípico no meio. **Decisão:** uma tendência em alta ou em queda é **frágil** quando, refeita pela mesma regra sem um dos anos usados, muda de direção (ou fica sem dados suficientes) em ao menos uma das retiradas. O contrato traz `Tendencia.fragil` e `anos_decisivos` (os anos cuja retirada muda a direção), e a interface marca a tendência com uma etiqueta "frágil" e diz de que anos ela depende.

- **Por que "ao menos uma retirada":** a regra não tem um corte arbitrário (uma fração das retiradas) e diz qual ano pesa, o que a pessoa pode conferir na série. Com o mínimo de 5 anos (um recorte curto no painel), toda marcação é frágil, porque sem qualquer um dos anos sobram 4: é o comportamento certo, e a interface diz isso.
- **Custo:** um ajuste por ano, só para os tópicos marcados. No pior caso do piloto (todos os 57 tópicos, 17 ajustes cada), 42 ms em Python puro; no navegador, com os filtros, só os marcados são refeitos.
- **Paridade:** a mesma conta em Python e em `glm.ts`. O gerador dos casos recusa uma série em que um limite do intervalo fique a menos de 10⁻⁶ de zero, no ajuste completo ou numa retirada, para que um arredondamento diferente nos dois lados não mude a fragilidade.
- **Efeito nos tópicos da 2.2.0, com o quantil t:** 4 das 10 marcações são frágeis. Federalismo, capacidades estatais e implementação de políticas depende de 2010 e 2012; cobertura da imprensa e política, de 2011; representação política na sociedade civil, de 2011 e 2013; competição eleitoral municipal, de 11 dos 16 anos. As outras 6 resistem a qualquer retirada.

Alternativas descartadas: marcar como frágil só quando mais de um quarto das retiradas muda a direção (no piloto, só a competição eleitoral municipal; um corte arbitrário que esconde a dependência de um ano) e o erro-padrão *jackknife* (outra regra de decisão, mais difícil de explicar que "sem 2011, fica estável").

