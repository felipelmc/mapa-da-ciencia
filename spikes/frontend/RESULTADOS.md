# Spike M0d: router por hash do SvelteKit e regl-scatterplot no Chromium headless

- **Data:** 2026-09-26
- **Máquina:** macOS 26.3 (Darwin 25.3.0), Apple M4 Pro, arm64
- **Ferramentas:** Node 24.14.0, npm 11.9.0, Python 3.13.12 (usado só como segundo servidor estático)
- **Protótipo:** este diretório (`spikes/frontend/`). É descartável e não é a base do frontend real.

## Resumo

| Pergunta | Resultado |
|---|---|
| TypeScript 7 no SvelteKit | **Não funciona.** O peer do `@sveltejs/kit@2.70.3` é `typescript ^5.3.3 \|\| ^6.0.0`, e o `npm install` falha com `ERESOLVE`. O spike usa o TS 6.0.3. |
| Build estático servido na **raiz**, sem reescrita | **Funciona**, em todas as variantes, exceto a `base-fixa`. |
| Build estático num **subcaminho**, sem reescrita | **Não funciona com a configuração padrão.** O `index.html` sai com caminhos absolutos (`/_app/...`), que dão 404. **Funciona com contorno**: relativizar o `index.html` depois do build, usar `bundleStrategy: 'inline'` ou fixar `paths.base`. |
| `page.url.searchParams` com `#/mapa?anos=...` | **Não funciona.** Devolve `{}`, porque o SvelteKit só lê a query real, a que vem antes do `#`. Há dois contornos testados: ler a parte `?...` de `page.url.hash` (4 linhas) ou pôr a query antes do hash (`?anos=...#/mapa`). Nesse segundo caso, `page.url.searchParams` funciona, inclusive com `goto()`. |
| `fallback: 'index.html'` | **Desnecessário.** Com router por hash, o adapter não exige fallback, e o build já gera `index.html`. Com o `fallback`, o adapter sobrescreve esse arquivo (com aviso) por um HTML equivalente. O comportamento é idêntico nos dois casos. |
| regl-scatterplot no Chromium headless | **Funciona sem nenhuma flag.** Desenhou nas 18 combinações de navegador e flags testadas. |
| Tempo até o primeiro desenho (10.000 pontos) | Mediana de **171 ms** no headless-shell padrão, **53 ms** com `--use-angle=swiftshader --enable-unsafe-swiftshader` e **59 ms** no novo headless com GPU (Metal). Foram 10 repetições de cada. |
| API: laço, `filter()`, cor por categoria | **Funcionam as três.** O laço foi testado de dois jeitos: programático e com Shift+arrastar o mouse. Há ressalvas de tipagem e de eventos assíncronos, descritas abaixo. |

## O que foi testado

Um app SvelteKit mínimo com `kit.router.type = 'hash'` e `adapter-static`, com duas rotas:

- `#/` (`src/routes/+page.svelte`): página inicial;
- `#/mapa` (`src/routes/mapa/+page.svelte`): um canvas com o regl-scatterplot, que desenha 10.000 pontos em 40 clusters gaussianos. As coordenadas vêm de um gerador determinístico (`src/lib/pontos.ts`), a cor é por cluster e o fundo é `#0A0E1F`.

O layout (`src/routes/+layout.svelte`) tem links e botões de `goto()` feitos de jeitos diferentes, e um painel que mostra `page.url.searchParams` ao lado dos parâmetros lidos à mão do hash. As duas rotas expõem o estado em `window.__rotaDebug` e `window.__mapaDebug`, e o script de teste lê daí.

O mesmo código gera cinco **variantes** de build (`svelte.config.js`, por `SPIKE_VARIANTE`):

| Variante | Configuração |
|---|---|
| `sem-fallback` | router por hash + adapter-static sem `fallback` (configuração mínima) |
| `com-fallback` | idem, com `fallback: 'index.html'` |
| `inline` | idem a `sem-fallback`, com `output.bundleStrategy: 'inline'` (JS e CSS dentro do HTML) |
| `base-fixa` | idem a `sem-fallback`, com `paths.base: '/base-fixa'` |
| `relativo` | cópia da `sem-fallback` com `"/_app/` trocado por `"./_app/` no `index.html` (`scripts/relativizar.mjs`) |

Cada variante foi servida de dois **modos**, por um servidor estático **sem regra de reescrita** (`tests/servidor.mjs`):

- **raiz:** serve `build/<variante>/` e abre `http://127.0.0.1:<porta>/`;
- **subcaminho:** serve a pasta pai `build/` e abre `http://127.0.0.1:<porta>/<variante>/`.

O servidor em Node tem a semântica de um estático comum: diretório com barra → `index.html`; diretório sem barra → 301 para a versão com barra; arquivo → 200; o resto → 404. A pergunta 1 também foi rodada com `python3 -m http.server`, que deu **o mesmo resultado** nas 10 combinações (`resultados/resultados-python-rotas.json`).

Em cada combinação, o script `tests/spike.mjs` (Playwright, Chromium headless) executa nove etapas: (a) carrega `#/`; (b, c) clica nos links feitos com `resolve()`; (d) clica no link literal `#/mapa?anos=2012-2020&cor=topico`; (e1–e3) troca os parâmetros com `goto()` de três jeitos; (f) usa o botão voltar; (g) abre o link profundo numa aba nova; (h) recarrega a página; (i) abre `?anos=...#/mapa`. Antes de cada ação, o script marca a `window`. Se a marca some, houve recarga completa da página, e não navegação no cliente. Uma combinação conta como "funciona" quando todas as etapas passam, o mapa desenha e não há 404 nem exceção.

## Como reproduzir

```bash
cd spikes/frontend
npm ci                                   # ~93 MB em node_modules/, nada global
npx playwright install chromium          # só o Chromium (e o headless shell); vai para ~/Library/Caches/ms-playwright
npm run check                            # svelte-check com TS 6.0.3: 0 erros, 0 avisos
npm run build                            # gera build/{sem-fallback,com-fallback,inline,base-fixa,relativo}/
node tests/spike.mjs --repeticoes=10     # tudo, com servidor em Node (~70 s)
node tests/spike.mjs --servidor=python --so-rotas   # pergunta 1 com python3 -m http.server (~35 s)
```

Outras opções: `--sem-matriz` pula a matriz de flags e `--so-rotas` roda só a pergunta 1. O script sobe e derruba os próprios servidores e navegadores e não deixa processo rodando. O código de saída é 1 se alguma combinação divergir das hipóteses registradas em `ESPERADO` ou se alguma chamada da API falhar.

As saídas ficam em `resultados/`: `mapa.png`, `resultados-node.json` (tudo), `resultados-python-rotas.json` e as saídas de terminal `saida-node.txt` e `saida-python.txt`.

Para conferir o conflito com o TS 7 (em qualquer diretório temporário):

```bash
npm install --dry-run @sveltejs/kit@2.70.3 @sveltejs/vite-plugin-svelte@7.3.1 svelte@5.57.1 vite@8.3.1 typescript@7.0.2
```

## Versões

Versões instaladas, conferidas com `npm ls --depth=0` e fixadas sem `^` no `package.json`:

| Pacote | Versão |
|---|---|
| `@sveltejs/kit` | 2.70.3 |
| `svelte` | 5.57.1 |
| `@sveltejs/adapter-static` | 3.0.10 |
| `@sveltejs/vite-plugin-svelte` | 7.3.1 |
| `vite` | 8.3.1 |
| `typescript` | 6.0.3 |
| `svelte-check` | 4.7.6 |
| `regl-scatterplot` | 1.16.0 (traz `regl` 2.1.1, `pub-sub-es` 3.0.0) |
| `playwright` | 1.63.0 (Chromium 153.0.8010.12, revisão 1243) |
| `pngjs` | 7.0.0 |

No dia do teste, o `latest` do TypeScript no npm era o 7.0.2, e a maior versão da linha 6 era a 6.0.3. O peer do SvelteKit exclui o 7, e o `svelte-check@4.7.6` também (`typescript ^5.0.0 || ^6.0.0`). Saída do `npm install --dry-run` com o TS 7:

```
npm error ERESOLVE could not resolve
npm error While resolving: @sveltejs/kit@2.70.3
npm error Found: typescript@7.0.2
npm error Could not resolve dependency:
npm error peerOptional typescript@"^5.3.3 || ^6.0.0" from @sveltejs/kit@2.70.3
```

A revisão 1243 do Chromium já estava no cache global do Playwright (`~/Library/Caches/ms-playwright`, de outro projeto), então o `npx playwright install chromium` não baixou nada. Numa máquina limpa, o download fica em torno de 550 MB (359 MB do Chromium + 195 MB do headless shell).

## Pergunta 1: router por hash

### 1.1 Raiz e subcaminho sem reescrita

Mesmo resultado com o servidor em Node e com `python3 -m http.server`:

| Variante | Raiz | Subcaminho |
|---|---|---|
| `sem-fallback` | funciona | **não funciona**: 8 × 404 em `/_app/...` |
| `com-fallback` | funciona | **não funciona**: 8 × 404 em `/_app/...` |
| `inline` | funciona | funciona, com a ressalva de 1.2 |
| `base-fixa` (`/base-fixa`) | **não funciona**: 404 em `/base-fixa/_app/...` | funciona, com a ressalva de 1.2 |
| `relativo` | funciona | funciona, com a ressalva de 1.2 |

**Causa.** Com `router.type = 'hash'`, o SvelteKit gera o `index.html` pela mesma rotina da página de fallback (`generate_fallback`, em `core/postbuild/prerender.js`). Essa rotina não usa caminhos relativos, mesmo com `paths.relative` ligado (o padrão). A `base` é calculada em tempo de execução (`new URL('.', location)`), mas os `<link>` e os `import()` do HTML saem absolutos:

```html
<link href="/_app/immutable/entry/start.CHdWiZKf.js" rel="modulepreload">
...
__sveltekit_si88vp = { base: new URL('.', location).pathname.slice(0, -1) };
...
import("/_app/immutable/entry/start.CHdWiZKf.js"),
```

Servido em `/sem-fallback/`, o navegador pede `/_app/...` à raiz do servidor, recebe 404 e o app não sobe:

```
TypeError: Failed to fetch dynamically imported module: http://127.0.0.1:64122/_app/immutable/entry/start.Cq_77ijt.js
```

Só o `index.html` tem esse problema. Os chunks JS se importam entre si por caminho relativo, e o CSS da rota `/mapa`, carregado sob demanda, também veio certo. Na variante `relativo`, bastou trocar 10 ocorrências de `"/_app/` por `"./_app/` para zerar os 404.

**Contornos**, todos testados na raiz e no subcaminho:

| Contorno | Raiz | Subcaminho | Custo |
|---|---|---|---|
| Relativizar o `index.html` após o build (`scripts/relativizar.mjs`) | ok | ok | Um passo de pós-build que depende do formato do HTML gerado pelo SvelteKit. Pode quebrar numa atualização, mas o teste detecta. |
| `output.bundleStrategy: 'inline'` | ok | ok | Um só `index.html` de 300 KB (104 KB gzip), sem code splitting. O Rolldown emite 4 avisos `EMPTY_IMPORT_META` (formato `iife`), sem efeito visível aqui. |
| `paths.base` fixo | **falha** | ok | O subcaminho precisa ser conhecido no build, e o mesmo build não serve na raiz. |

### 1.2 Links e `goto()` no subcaminho: não use `resolve()`

No subcaminho, `resolve('/mapa')` (de `$app/paths`) devolve `/relativo#/mapa`, **sem a barra antes do `#`**. O caminho `/relativo` é diferente do atual (`/relativo/`), então o clique vira uma navegação completa: o servidor responde 301 para `/relativo/`, a página recarrega e o mapa é recriado. O app continua funcionando, mas perde o estado e recria o contexto WebGL. Na raiz, `resolve()` devolve `#/mapa` e não há problema.

Variante `relativo`, servidor em Node (a `inline` e a `base-fixa` deram o mesmo resultado):

| Etapa | Destino | URL final | No cliente? | Mapa preservado? |
|---|---|---|---|---|
| b | `<a href={resolve('/mapa')}>` → `/relativo#/mapa` | `/relativo/#/mapa` | **não** (301 + recarga) | n/a |
| c | `<a href={resolve('/')}>` → `/relativo#/` | `/relativo/#/` | **não** | n/a |
| d | `<a href="#/mapa?anos=2012-2020&cor=topico">` | `/relativo/#/mapa?anos=...` | sim | n/a |
| e1 | `goto('#/mapa?anos=1990-1995&cor=area')` | `/relativo/#/mapa?anos=1990-1995&cor=area` | sim | sim |
| e2 | ``goto(`${resolve('/mapa')}?anos=2000-2005&cor=area`)`` | `/relativo/#/mapa?anos=2000-2005&cor=area` | **não** | **não** |
| e3 | `goto('?anos=1980-1985&cor=area#/mapa')` | `/relativo/?anos=1980-1985&cor=area#/mapa` | sim | sim |
| f | botão voltar | `/relativo/#/` | sim | n/a |

Na raiz, as sete etapas navegaram no cliente, e as três trocas de parâmetro (e1–e3) preservaram o mapa: o componente não foi remontado.

**Contorno:** montar hrefs e destinos de `goto()` como hash relativo (`'#/mapa?...'`), sem `resolve()`. Um helper trivial resolve isso no app real.

### 1.3 `page.url.searchParams` com parâmetros no hash

| URL | `page.url.searchParams` | `page.url.hash` |
|---|---|---|
| `/#/mapa?anos=2012-2020&cor=topico` | `{}` | `#/mapa?anos=2012-2020&cor=topico` |
| `/?anos=2012-2020&cor=topico#/mapa` | `{anos: '2012-2020', cor: 'topico'}` | `#/mapa` |

O roteador remove a parte `?...` do hash para achar a rota (`get_url_path` em `runtime/client/client.js`), então `#/mapa?anos=...` casa com `/mapa` normalmente. Mas `page.url` é a URL real do navegador, e sua `searchParams` só enxerga a query anterior ao `#`. Os dois formatos funcionaram em carga direta, recarga, voltar e `goto()` sem recarga, na raiz e no subcaminho:

- **Parâmetros dentro do hash** (`#/mapa?anos=...`): ler com `new URLSearchParams(page.url.hash.split('?')[1])`, como em `src/lib/url.ts`. O `$derived` reage à troca de parâmetros por `goto()`.
- **Query antes do hash** (`?anos=...#/mapa`): `page.url.searchParams` funciona direto, e `goto('?anos=...#/mapa')` trocou os parâmetros sem recarregar a página (etapa e3). Ressalva: a URL fica menos convencional, e um servidor que faça cache por URL completa trata cada combinação de filtros como um recurso diferente. Isso não afeta um servidor estático local.

### 1.4 `fallback: 'index.html'`

- **Não é necessário.** O `adapter-static@3.0.10` pula a checagem de rotas dinâmicas quando o router é por hash:
  `if (!options?.fallback && builder.config.kit.router?.type !== 'hash') { ... throw new Error('Encountered dynamic routes') }`.
  Sem `fallback` e com `strict: true`, o build passou e gerou `index.html`.
- **Não ajuda, e atrapalha um pouco.** Com `fallback: 'index.html'`, o adapter sobrescreve o `index.html` que o SvelteKit acabou de gerar e avisa:
  `Overwriting build/com-fallback/index.html with fallback page. Consider using a different name for the fallback.`
  O HTML resultante é equivalente, com os mesmos caminhos absolutos, e o comportamento foi idêntico nas 9 etapas. Não resolve o subcaminho e só acrescenta um aviso ao build.

## Pergunta 2: regl-scatterplot no Chromium headless

A pergunta 2 usa a variante `sem-fallback` servida na raiz, com viewport de 1280×800 e `devicePixelRatio` 1.

### 2.1 Renderiza? Com quais flags?

**Renderiza sem flag nenhuma.** Nas 18 combinações abaixo, o WebGL 1 e o WebGL 2 estavam disponíveis, o `draw()` resolveu e o screenshot do canvas passou do limiar. Os tempos desta tabela vêm de **uma medida só** por linha e servem de indicação. A série com 10 repetições está em 2.3.

| Navegador | Flags | Renderer (WebGL) | 1º desenho |
|---|---|---|---|
| headless-shell (padrão do Playwright) | (nenhuma) | ANGLE / SwiftShader (Vulkan) | 219 ms |
| headless-shell | `--use-gl=swiftshader` | SwiftShader | 211 ms |
| headless-shell | `--use-angle=swiftshader` | SwiftShader | 69 ms |
| headless-shell | `--enable-unsafe-swiftshader` | SwiftShader | 210 ms |
| headless-shell | `--use-angle=swiftshader --enable-unsafe-swiftshader` | SwiftShader | 67 ms |
| headless-shell | `--use-gl=angle --use-angle=swiftshader --enable-unsafe-swiftshader` | SwiftShader | 68 ms |
| headless-shell | `--disable-gpu` | SwiftShader | 209 ms |
| headless-shell | `--disable-gpu --enable-unsafe-swiftshader` | SwiftShader | 208 ms |
| headless-shell | `--disable-gpu --use-angle=swiftshader --enable-unsafe-swiftshader` | SwiftShader | 209 ms |
| novo headless (`channel: 'chromium'`) | (nenhuma) | **ANGLE Metal, Apple M4 Pro (GPU)** | 84 ms |
| novo headless | `--use-gl=swiftshader` | SwiftShader | 225 ms |
| novo headless | `--use-angle=swiftshader` | SwiftShader | 624 ms |
| novo headless | `--enable-unsafe-swiftshader` | ANGLE Metal (GPU) | 82 ms |
| novo headless | `--use-angle=swiftshader --enable-unsafe-swiftshader` | SwiftShader | 585 ms |
| novo headless | `--use-gl=angle --use-angle=swiftshader --enable-unsafe-swiftshader` | SwiftShader | 926 ms |
| novo headless | `--disable-gpu` | SwiftShader | 207 ms |
| novo headless | `--disable-gpu --enable-unsafe-swiftshader` | SwiftShader | 206 ms |
| novo headless | `--disable-gpu --use-angle=swiftshader --enable-unsafe-swiftshader` | SwiftShader | 208 ms |

O renderer SwiftShader aparece por inteiro como `ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (LLVM 10.0.0) (0x0000C0DE)), SwiftShader driver)`.

Leitura:

- No macOS, o headless-shell (o padrão do Playwright para `headless: true`) **sempre** usa SwiftShader, isto é, WebGL por software, sem GPU. Nesta versão do Chromium, o WebGL funcionou mesmo sem `--enable-unsafe-swiftshader`, inclusive com `--disable-gpu`.
- No headless-shell, `--use-angle=swiftshader` deixou o primeiro desenho cerca de 3× mais rápido (~52 ms contra ~170 ms), com o mesmo renderer. Uma hipótese, não verificada, é que o compositor passa a usar o caminho de GPU (via SwiftShader) em vez de copiar o canvas para a CPU a cada quadro. Com `--disable-gpu`, a vantagem some.
- O novo headless usa a GPU real (Metal) por padrão.
- **Não testado em Linux.** O CI provavelmente vai rodar em Linux sem GPU. A combinação `--use-angle=swiftshader --enable-unsafe-swiftshader` funcionou aqui em todos os casos e foi a mais rápida no headless-shell, então é a candidata natural para o CI. Mas isso precisa ser confirmado no primeiro job de CI, porque o comportamento do SwiftShader muda entre plataformas e versões do Chromium.

### 2.2 Como verificar que desenhou de fato

Usei três sinais independentes, todos no script:

1. **Contador em `window.__mapaDebug`.** Guarda `desenhado`, `pontos`, `eventosDraw`, `renderer`, `erro` e os tempos. O teste espera `desenhado || erro`.
2. **Screenshot do canvas com contagem de pixels.** O script esconde os painéis sobrepostos, fotografa só o `<canvas>` e decodifica o PNG com `pngjs`. Um pixel conta como desenhado se algum canal difere do fundo (`#0A0E1F`) em mais de 24 (de 255). O mapa conta como desenhado se ao menos 0,5% dos pixels passam desse limiar. Resultado típico: **52.995 de 1.024.000 pixels (5,18%)**, 94,7% dos pixels iguais ao fundo (o que confirma que o fundo foi aplicado) e 795 cores distintas, quantizadas em 4 bits por canal. Com o `filter()` o número cai para 7.260 e, depois do `unfilter()`, volta a 52.995, o que mostra que a medida responde ao que foi desenhado.
3. **`scatterplot.export()`.** Devolve um `ImageData` sem passar por screenshot. Ver a ressalva em "Problemas".

Esses números foram idênticos em todas as configurações que usam SwiftShader (52.995 px). Com Metal, deram 53.096 px, uma diferença de antialiasing.

### 2.3 Tempo até o primeiro desenho

O tempo vai do início do `onMount` da rota `/mapa` até o `await scatterplot.draw(10.000 pontos)` resolver, mais dois `requestAnimationFrame`. Inclui criar o contexto WebGL e compilar os shaders (`createScatterplot`), montar o índice espacial (KDBush, num Web Worker) e apresentar o quadro. "Desde a navegação" é o `performance.now()` no mesmo instante, contado a partir do início da navegação, com a página servida em localhost. Cada medida abre um contexto novo. Os três navegadores ficam abertos e as repetições se alternam entre eles.

| Configuração | Renderer | 1º desenho: mediana [mín–máx] | Desde a navegação: mediana [mín–máx] |
|---|---|---|---|
| headless-shell, sem flags | SwiftShader | **171 ms** [169–207] | 189 ms [188–238] |
| headless-shell, `--use-angle=swiftshader --enable-unsafe-swiftshader` | SwiftShader | **53 ms** [51–71] | 72 ms [70–91] |
| novo headless, sem flags | Metal (GPU) | **59 ms** [53–110] | 80 ms [76–141] |

São 10 repetições por linha (`resultados/resultados-node.json` → `mapa.tempos`). A primeira repetição de cada linha é a mais lenta (aquecimento).

### 2.4 API: laço, `filter()`, cor por categoria

Chamadas feitas via `page.evaluate` sobre a instância exposta em `window.__mapaDebug.scatterplot`:

| Recurso | Chamada | Resultado |
|---|---|---|
| Laço, programático | `scatterplot.lassoSelect([[x±0,08, y±0,08]...], { isGl: true })`, um quadrado em volta do centro do cluster 0 | 250 pontos selecionados, os 250 do cluster 0; 1 evento `select` |
| Laço com o mouse | Shift + arrastar num círculo de raio 45 px (`page.keyboard.down('Shift')` + `page.mouse`) | 250 pontos selecionados, os 250 do cluster-alvo (25); 1 `select` e 1 `lassoEnd` |
| `filter()` | `await scatterplot.filter(índices dos clusters 0–4)`, depois `unfilter()` | `filteredPoints.length` = 1.250 (o pedido), `isPointsFiltered` = true, 1 evento `filter`; pixels 52.995 → 7.260 → 52.995 |
| Cor por categoria | `createScatterplot({ colorBy: 'valueA', pointColor: [40 cores] })` + `draw(..., { zDataType: 'categorical' })`; depois `set({ pointColor: '#FFD58F' })` e volta à paleta | `pointColor` com 40 cores; cores distintas no screenshot: 795 → 62 → 795 |
| `export()` | `await scatterplot.export({ scale: 1, antiAliasing: 1, pixelAligned: false })` | `ImageData` 1280×800 com 5,5% dos pixels com alfa > 0 |

## Problemas encontrados e contornos

1. **O subcaminho quebra com a configuração padrão** (1.1). Os caminhos `/_app/...` do `index.html` são absolutos. Contornos: relativizar o `index.html` depois do build ou usar `bundleStrategy: 'inline'`.
2. **`resolve()` no subcaminho causa recarga completa** (1.2). Gera `/sub#/rota`, sem barra. Contorno: hrefs e `goto()` com hash relativo (`'#/rota?...'`).
3. **`page.url.searchParams` não lê a query dentro do hash** (1.3). Contorno: ler de `page.url.hash` ou pôr a query antes do `#`.
4. **`fallback` redundante com router por hash** (1.4). O adapter sobrescreve o `index.html` e emite um aviso. Contorno: não configurar.
5. **Tipagem do regl-scatterplot 1.16.0.** O evento `'filter'` é publicado pela lib, mas falta na união de nomes aceitos por `subscribe()`. O `svelte-check` acusou `Argument of type '"filter"' is not assignable to parameter of type '"view" | "select" | ...'`. Contorno: um cast local, feito em `src/routes/mapa/+page.svelte`. Os outros eventos da tabela do README estão tipados. `pointOver` funciona apesar de a lib publicar `pointover`, porque o `pub-sub-es` é criado com `caseInsensitive: true`.
6. **Eventos do regl-scatterplot são assíncronos por padrão** (`syncEvents: false`). Logo depois de `await sp.filter(...)`, o contador de eventos `filter` ainda estava em 0, e o evento chegou em seguida. Em teste, é preciso esperar a entrega ou criar o scatterplot com `syncEvents: true`.
7. **`colorBy: 'valueA'` volta como `'valueZ'`** em `get('colorBy')`. É um alias interno. Quem comparar o valor deve aceitar os dois nomes.
8. **O `export()` síncrono, sem opções, não é confiável.** Numa execução de depuração, logo depois do primeiro desenho, voltou com todos os pixels zerados (`0,0,0,0`), porque o canvas não preserva o buffer de desenho. Na execução final, depois de outras interações, veio preenchido (5,3%). A forma assíncrona (`await export({ ... })`) redesenha antes de ler e funcionou sempre. Nos dois casos o fundo sai transparente, então a contagem deve usar o alfa, não a cor de fundo.
9. **Avisos no console, inofensivos:**
   - `GL Driver Message (OpenGL, Performance, GL_CLOSE_PATH_NV, High): GPU stall due to ReadPixels`, que aparece nas configurações com SwiftShader quando o teste lê o canvas;
   - `Canvas2D: Multiple readback operations using getImageData are faster with the willReadFrequently attribute set to true`, um aviso de desempenho do Chromium sobre leituras repetidas de um canvas 2D;
   - o 404 do `/favicon.ico` no Chromium completo, filtrado pelo script.
10. **O regl-scatterplot cria o Worker a partir de um Blob** (`new Worker(URL.createObjectURL(new Blob(...)))`). Funcionou em todas as variantes, inclusive na `inline`. Se o app real adotar CSP, vai precisar de `worker-src blob:`.
11. **Coordenadas em NDC.** O regl-scatterplot espera x e y já em [-1, 1]. Com `aspectRatio` 1 (o padrão), a área de dados aparece como um quadrado centralizado no canvas de 1280×800 (ver `resultados/mapa.png`). O app real vai precisar normalizar as coordenadas da projeção (UMAP etc.) antes do `draw()`.

## Limitações do spike

- Só rodou em macOS arm64. O comportamento do WebGL headless em Linux sem GPU, o caso do CI, não foi medido.
- Os dados são sintéticos: 10.000 pontos, sem rótulos, sem hover e sem tooltip. Volumes maiores não foram testados.
- Os tempos da matriz de flags são de uma medida só. Só a tabela de 2.3 tem repetições.
- O servidor de produção do projeto, que deve servir o frontend a partir do pacote Python, não foi testado. Os dois servidores usados aqui são estáticos puros e servem de aproximação.

## Arquivos

```
spikes/frontend/
├── package.json, package-lock.json   versões fixadas; scripts build:* / check / spike
├── svelte.config.js                  variantes de build por SPIKE_VARIANTE
├── vite.config.ts, tsconfig.json
├── scripts/relativizar.mjs           contorno "relativo" (pós-build)
├── src/
│   ├── app.html, app.d.ts            tipos de window.__rotaDebug / __mapaDebug
│   ├── lib/pontos.ts                 10.000 pontos, 40 clusters gaussianos, paleta categórica
│   ├── lib/url.ts                    parametrosDoHash()
│   └── routes/
│       ├── +layout.svelte            links, botões de goto(), painel de parâmetros
│       ├── +page.svelte              #/
│       └── mapa/+page.svelte         #/mapa (regl-scatterplot)
├── tests/
│   ├── servidor.mjs                  servidores estáticos sem reescrita (Node e python3)
│   └── spike.mjs                     todas as verificações (Playwright, headless)
└── resultados/
    ├── mapa.png                      screenshot de #/mapa?anos=2012-2020&cor=topico
    ├── resultados-node.json          resultado completo (rotas, mapa, API, tempos, matriz)
    ├── resultados-python-rotas.json  rotas com python3 -m http.server
    └── saida-node.txt, saida-python.txt
```

`node_modules/`, `.svelte-kit/` e `build/` ficam fora do git (`.gitignore` da raiz).
