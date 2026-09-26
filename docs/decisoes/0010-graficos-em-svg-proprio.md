# 0010. Gráficos em SVG próprio, com módulos pequenos do d3

- **Status:** aceita (M4)
- **Data:** 2026-09-26
- **Marco:** M4

## Contexto

O M4 traz as primeiras vistas com gráficos: o fluxo dos tópicos no tempo (com três modos e transição entre eles), as sparklines da lista "em alta / em queda", os pequenos múltiplos por revista, o coroplético por UF, o mapa-múndi e o ranking de instituições. O plano geral previa o `@observablehq/plot` para facetas e *heatmaps*, e o d3 para o resto.

Requisitos da interface que pesam na escolha:

- **tema por variáveis CSS** (Observatório e Prancha), trocado sem redesenhar;
- **acessibilidade por teclado**: faixas, UFs e barras clicáveis precisam de `role`, `tabindex` e teclas; o `svelte-check` do projeto falha com qualquer aviso de acessibilidade;
- **transição entre modos** do fluxo (fluxo, absoluto, proporção) respeitando `prefers-reduced-motion`;
- **testabilidade**: a lógica em TypeScript puro, testada no Vitest (sem navegador), e os gráficos com `data-testid` e valores para o Playwright;
- **peso**: o painel carrega por rota, e o site publicado deve abrir rápido em conexões modestas.

## Decisão

Gráficos em **SVG escrito em Svelte**, com módulos pequenos do d3 para a matemática:

| Pacote | Versão | Para quê |
|---|---|---|
| `d3-shape` | 3.2.0 | empilhamento (`stack`, `stackOffsetWiggle/None/Expand`, `stackOrderInsideOut`), áreas e curvas (`curveMonotoneX`) |
| `d3-array` | 3.2.4 | marcas dos eixos (`ticks`) |

Sem `@observablehq/plot` e sem `d3-scale`: o Plot traz o d3 inteiro (70 a 120 KB comprimidos a mais) e redesenha o SVG a cada mudança, o que impede a transição entre modos e complica a acessibilidade; o `d3-scale` traz interpolação, cores e formatação de datas que não usamos (a formatação é `Intl` em português, em `lib/formato.ts`).

A lógica fica em módulos puros (`lib/graficos/fluxo.ts`, `faixas.ts`), e os componentes (`Figura`, `Eixo`, `Sparkline`, `Dica`) só desenham. Todo gráfico vem numa `Figura`, com uma frase-resumo e "Ver como tabela".

## Consequências

- Os gráficos seguem o tema e o movimento reduzido sem código especial, e cada peça é testada isoladamente.
- Algumas coisas que o Plot faria de graça (facetas, legendas) são escritas à mão; a lista de componentes é curta e reaproveitada no M5 (classificação).
- Novas dependências de gráficos entram com versão fixa e com esta tabela atualizada.
