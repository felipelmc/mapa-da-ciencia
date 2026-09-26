# 0002. Frontend: router por hash do SvelteKit e regl-scatterplot

- **Status:** aceita
- **Data:** 2026-09-26
- **Marco:** M0 (spike M0d)

## Contexto

O frontend precisa de um só build que funcione em dois lugares:

- no servidor local do `mapa painel`, na raiz `/`;
- no GitHub Pages, num subcaminho como `/mapa-da-ciencia/demo/`, que não tem regra de reescrita.

O estado dos filtros vai na URL, para que links compartilhados abram a mesma vista. O mapa de documentos desenha cerca de 10 mil pontos em WebGL e precisa renderizar também no Chromium headless do CI. O Embedding Atlas foi descartado por exigir WebGPU (ver o plano).

## Opções consideradas

- **Subcaminho:**
  - relativizar o `index.html` depois do build;
  - `bundleStrategy: 'inline'`;
  - `paths.base` fixo.
- **Estado na URL:**
  - parâmetros dentro do hash (`#/mapa?anos=...`), lidos por código próprio;
  - query antes do hash (`?anos=...#/mapa`), lida por `page.url.searchParams`.

## Evidência

Protótipo em `spikes/frontend/`, com relatório completo em `spikes/frontend/RESULTADOS.md`. Foram testadas 5 variantes de build × raiz/subcaminho × 9 etapas de navegação, com servidor Node e com `python3 -m http.server`.

| Pergunta | Resultado |
|---|---|
| TypeScript 7 | Fora do peer do SvelteKit 2.70.3 e do svelte-check 4.7.6 (`ERESOLVE`). **TS 6.0.3** funciona. |
| Build na raiz | Funciona. |
| Build em subcaminho, configuração padrão | **Falha.** O `index.html` sai com `/_app/...` absoluto e gera 8 × 404. |
| Relativizar `index.html` (`"/_app/` → `"./_app/`) | Funciona na raiz e no subcaminho e mantém o code splitting. |
| `bundleStrategy: 'inline'` | Funciona nos dois, mas vira um só HTML de 300 KB (104 KB gzip), sem code splitting. |
| `paths.base` fixo | Funciona só no subcaminho declarado e quebra na raiz. |
| `resolve('/mapa')` em subcaminho | Gera `/sub#/mapa` sem a barra, o que causa 301, recarga e perda do contexto WebGL. |
| `href="#/..."` e `goto('#/...')` | Navegação no cliente em todos os casos, sem remontar o mapa. |
| `page.url.searchParams` com `#/mapa?anos=...` | Devolve `{}`. Ler de `page.url.hash` funciona e reage a `goto()`. |
| `fallback: 'index.html'` | Desnecessário com router por hash; só sobrescreve o `index.html` e gera um aviso. |
| regl-scatterplot, 10 mil pontos, headless | Renderiza **sem flags** nas 18 combinações testadas. Primeiro desenho (mediana de 10): 171 ms no padrão, 53 ms com `--use-angle=swiftshader --enable-unsafe-swiftshader`, 59 ms com GPU. |
| Laço, `filter()`, cor por categoria | Funcionam. Ressalvas: o evento `'filter'` falta nos tipos e os eventos são assíncronos. |

## Decisão

- **SvelteKit com `router.type: 'hash'` e `adapter-static` sem `fallback`**, com **TypeScript fixado em 6.0.x**.
- **Subcaminho:** um passo de pós-build (`scripts/relativizar-index.ts`) troca `"/_app/` por `"./_app/` no `index.html`. Um teste e2e roda o build servido **num subcaminho** e falha se aparecer algum 404. Isso protege contra mudanças no formato do HTML em atualizações do SvelteKit. Se esse passo quebrar, `bundleStrategy: 'inline'` fica como alternativa.
- **Links internos:** nunca usar `resolve()` de `$app/paths`. Um helper `rota(caminho, params)` gera sempre `#/caminho?params`, e uma regra de lint ou de revisão impede o uso de `resolve()` em links.
- **Estado na URL:** os parâmetros ficam **dentro do hash** (`#/mapa?anos=2012-2020&cor=topico`) e são lidos e escritos por `estado/url.ts`, com teste de ida e volta no Vitest. Assim o estado inteiro fica no fragmento, que o servidor nunca vê, e a URL fica convencional.
- **Mapa:** regl-scatterplot 1.16, como no plano. A verificação automatizada combina contagem de pixels no screenshot com um contador em `window.__mapaDebug`.
- **CI:** Chromium do Playwright com `--use-angle=swiftshader --enable-unsafe-swiftshader`. Em macOS basta o headless, mas no Linux do CI essa escolha ainda **precisa ser confirmada** no primeiro job (M1).

## Consequências

- O frontend real (M1) já nasce com o helper `rota()`, o módulo `estado/url.ts`, o script de relativização e o teste e2e no subcaminho.
- Numa máquina limpa, o Playwright baixa cerca de 550 MB (Chromium + headless shell). O CI deve fazer cache desse download.
- Continua aberto: a renderização no Linux do CI.

## Como reproduzir

    cd spikes/frontend
    npm ci
    npx playwright install chromium
    npm run build
    node tests/spike.mjs --repeticoes=10

## Adendo (2026-09-26, marco M3)

A escolha do CI está confirmada: do M1 ao M3, o Chromium do Playwright com `--use-angle=swiftshader --enable-unsafe-swiftshader` desenhou o mapa com o regl-scatterplot no Linux do GitHub Actions. O primeiro desenho leva cerca de 2,5 s no CI (WebGL por software), contra 0,3 a 0,5 s num Mac; por isso a meta de 1,5 s é conferida só fora do CI, e os testes esperam o desenho pelo `window.__mapaDebug`, com prazos folgados.
