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
- Com a **binomial pura**, 22 tópicos são marcados (11 em alta, 11 em queda). Entre eles, "Saúde global e covid-19" (φ = 5,48) aparece em alta por causa de um pico em 2020–2021, e "República conflitiva em Maquiavel", em queda, por causa de um dossiê no começo do período.
- Com a **quase-binomial**, que multiplica o erro-padrão por √φ, 13 são marcados (7 em alta, 6 em queda):
  - em alta: identificação partidária e polarização (+4,1 pontos percentuais no período), federalismo, capacidades estatais e implementação de políticas (+3,0), comunicação política nas redes sociais (+2,5), religião e política (+2,1), alocação de ministérios em coalizões, competição eleitoral municipal, pensamento político brasileiro e marxismo;
  - em queda: teoria social, modernidade e teoria crítica (−2,0), cobertura da imprensa (−2,0), democracia deliberativa (−1,8), representação na sociedade civil, Estado e bem-estar social, artes, cinema e crítica cultural.
- Dez desses 13 têm uma mudança que se sustenta: retirando um ano de cada vez, continuam marcados em pelo menos 12 das 16 retiradas. Três são marginais (teoria social, modernidade e teoria crítica; artes, cinema e crítica cultural; pensamento político brasileiro e marxismo): passam a estáveis com o quantil t(14) no lugar do z e, retirando um só ano, em 7 a 12 das 16 retiradas.

## Decisão

1. **Modelo:** regressão logística binomial da participação anual do tópico (documentos do tópico ÷ documentos do ano), com o ano como única variável, centrado na média dos anos usados. Anos sem nenhum documento ficam de fora.
2. **Dispersão quase-binomial:** o erro-padrão da inclinação é multiplicado por √φ, com φ = max(1, X² de Pearson ÷ (anos − 2)). A binomial pura continua disponível (`metodo_tendencia.dispersao` no contrato).
3. **Direção:** "em alta" se o intervalo de 95% (Wald, z = 1,96) da inclinação está todo acima de zero; "em queda" se está todo abaixo; "estável" nos demais casos.
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
