# Interface do mapa-da-ciencia

App estático em SvelteKit que visualiza o **contrato de dados**: os arquivos JSON que o pipeline em Python grava em `saida/dados/`. O mesmo build serve dois usos:

- o **painel local** (`mapa painel`), servido pelo Python em `/`, com os dados em `/dados/` e a API em `/api/`;
- o **site publicado** (GitHub Pages), servido num subcaminho como `/mapa-da-ciencia/demo/`, sem API e sem regra de reescrita.

> **Estado:** marco M4, em andamento. Já funcionam a casca (trilho, barra superior, dois temas, estado na URL), a capa (Início) com os números do corpus e os macrotemas, e o **Mapa** (regl-scatterplot, `src/lib/graficos/Nuvem.svelte` e `src/lib/mapa/`). As outras vistas mostram um estado vazio que diz em que marco chegam.

## Como rodar

Requisitos: Node 22.18 ou mais novo, que roda os scripts `.ts` de `scripts/` sem compilar, e npm. Nada é instalado globalmente.

```bash
cd frontend
npm ci
npm run dev          # http://localhost:5173, com o exemplo sintético
```

No `npm run dev`, um plugin do Vite (`vite.config.ts`) serve `../contrato/exemplo/dados` em `/dados/`. Para ver um projeto de verdade, aponte `MAPA_DADOS` para a pasta de dados dele:

```bash
MAPA_DADOS=~/meu-projeto/saida/dados npm run dev
```

Os testes de ponta a ponta usam o Chromium do Playwright. Numa máquina limpa, ele baixa cerca de 550 MB para `~/Library/Caches/ms-playwright` (macOS) ou `~/.cache/ms-playwright` (Linux):

```bash
npx playwright install chromium
```

## Scripts

| Comando | O que faz |
|---|---|
| `npm run dev` | Servidor de desenvolvimento, com os dados de exemplo em `/dados/`. |
| `npm run build` | Gera `build/` e relativiza o `index.html` (`"/_app/` → `"./_app/`), para servir também num subcaminho. |
| `npm run preview` | Serve o `build/`, também com `/dados/`. |
| `npm run check` | `svelte-check` com TypeScript 6. Falha com qualquer erro **ou aviso**. |
| `npm test` | Testes unitários (Vitest). |
| `npm run e2e` | Testes de ponta a ponta (Playwright, Chromium headless) sobre o `build/`. Rode `npm run build` antes; o teste recusa um build mais velho que `src/`. |
| `npm run tipos` | Regenera `src/lib/contrato/tipos.ts` a partir de `../contrato/schema/*.schema.json`. |
| `npm run tipos:checar` | Falha se `tipos.ts` estiver desatualizado em relação aos schemas. Roda no CI. |
| `npm run empacotar` | Faz o build e copia `build/` para `../src/mapa_da_ciencia/web/estatico/` (apaga o destino antes), de onde o `mapa painel` serve a interface. |
| `node scripts/baixar-malhas.ts` | Regrava as malhas da vista Geografia em `src/lib/geografia/malhas/`: as UFs do IBGE (1 requisição à API de malhas) e os países do Natural Earth (pacote `world-atlas`, sem rede). Com `--so-mundo`, só a do mundo. As malhas são versionadas; o painel não baixa nada. |
| `node scripts/captura-abertura.ts` | Gera a captura da abertura do site para o README (`../docs/imagens/abertura.png`), a partir do site montado pelo MkDocs em `../site`. |
| `node scripts/gif-readme.ts ../projetos/cp-scielo` | Gera o GIF do README (`../docs/imagens/painel.gif`): o Mapa ano a ano, os Tópicos, a Geografia e a Classificação, codificados em GIF pelo `gifenc` dentro do navegador. Roda só localmente, depois do `npm run build`. |
| `node scripts/capturas.ts ../projetos/cp-scielo` | Gera as capturas do mapa da documentação (`../docs/imagens/`) a partir dos dados de um projeto, com o Playwright. Roda só localmente, depois do `npm run build`: o piloto não está no repositório. O cartão mostra sempre um artigo com licença CC BY. |

A ordem do CI (`.github/workflows/ci.yml`) é: `npm ci`, `tipos:checar`, `check`, `test`, `build`, `e2e`.

## Estrutura

```
frontend/
├── package.json, package-lock.json   versões fixadas, sem ^
├── svelte.config.js                  router por hash, adapter-static sem fallback
├── vite.config.ts                    plugin que serve /dados/ no dev e no preview; config do Vitest
├── playwright.config.ts              e2e sobre o build, 1440×900, um worker
├── scripts/
│   ├── gerar-tipos.ts                schemas do contrato → src/lib/contrato/tipos.ts
│   ├── baixar-malhas.ts              IBGE e Natural Earth → src/lib/geografia/malhas/
│   ├── relativizar-index.ts          pós-build: "/_app/ → "./_app/ no index.html
│   └── empacotar.ts                  build/ → ../src/mapa_da_ciencia/web/estatico/
├── src/
│   ├── app.html                      lang="pt-BR" e o script que aplica o tema antes da 1ª pintura
│   ├── lib/
│   │   ├── contrato/tipos.ts         GERADO (npm run tipos); versionado
│   │   ├── dados/                    camada de dados (ver abaixo)
│   │   ├── estado/url.ts             rota() e filtros no hash
│   │   ├── estado/tema.svelte.ts     tema: sistema, botão, localStorage
│   │   ├── estilos/tokens.css        cores e fontes dos dois temas
│   │   ├── estilos/base.css          reset, tipografia, foco, fundo, movimento
│   │   ├── componentes/              casca (Trilho, BarraSuperior…), estados vazios, carta da capa
│   │   ├── recorte/                  barra do recorte (comum às vistas de análise) e linha do tempo
│   │   ├── geografia/                vista Geografia: mapas das UFs e do mundo, ranking, escala de cores, malhas
│   │   ├── secoes.ts                 as seções: rótulo, rota, ícone, resumo, marco, arquivos usados
│   │   └── formato.ts                números e datas em pt-BR
│   └── routes/                       uma pasta por seção; +layout.svelte abre o projeto
├── static/favicon.svg
└── tests/e2e/
    ├── preparar.ts                   globalSetup: monta e serve os cinco sites (tabela abaixo)
    ├── servidor.ts                   estático sem reescrita (como o GitHub Pages), com rotas de API opcionais
    ├── api-falsa.ts                  API falsa da codificação (fila, gravar, métricas)
    ├── api-falsa-painel.ts           API falsa do painel (etapas, jobs com SSE, modelos, configuração, codebook)
    ├── comum.ts                      ajudantes: vigiar o console, esperar o mapa, ler o exemplo
    ├── casca.spec.ts                 casca, capa, temas, projeto vazio
    ├── mapa.spec.ts                  a vista Mapa
    ├── topicos.spec.ts               a vista Tópicos
    ├── geografia.spec.ts             a vista Geografia
    ├── classificacao.spec.ts         a vista Classificação
    ├── validacao.spec.ts             a vista Validação
    ├── codificar.spec.ts             a codificação pelo teclado
    ├── projeto.spec.ts               a vista Projeto (linha de metrô, jobs ao vivo, assistente) e a Metodologia
    ├── exportar.spec.ts              exportar figuras e o modo apresentação
    └── publicado.spec.ts             o site gerado pelo `mapa publicar`
tests/pagina/                         a abertura do site da documentação, sobre ../site (`npm run e2e:pagina`)
```

Os testes unitários ficam ao lado do código (`*.test.ts`).

## Decisões

As decisões de base estão no [ADR 0002](../docs/decisoes/0002-frontend-router-hash-e-regl-scatterplot.md), com a evidência do spike em `spikes/frontend/RESULTADOS.md`. Em resumo:

- **Router por hash** (`router.type: 'hash'`) e **adapter-static sem `fallback`**. As rotas ficam em `#/mapa`, `#/topicos` etc., e o servidor só precisa entregar arquivos.
- **Relativização do `index.html` no pós-build.** Com router por hash, o SvelteKit escreve `/_app/...` absoluto no `index.html`, que quebra num subcaminho. O script troca por `./_app/...` e falha se não achar nada para trocar, o que indicaria uma mudança no formato do SvelteKit. A alternativa registrada é `output.bundleStrategy: 'inline'`.
- **Links internos só com `rota()`** (`src/lib/estado/url.ts`), que gera `#/caminho?params`. Nunca use `resolve()` de `$app/paths`: num subcaminho ele gera `/sub#/rota`, sem a barra, e força uma recarga completa. O teste `sem-resolve.test.ts` faz o papel de regra de lint: falha se algum arquivo de `src/` importar `resolve` de `$app/paths` ou usar `href="/..."` ou `goto('/...')`.
- **Estado dos filtros dentro do hash**: `#/mapa?anos=2012-2020&cor=macrotema`. O `page.url.searchParams` do SvelteKit não enxerga essa parte e devolve `{}`, então os filtros são lidos de `page.url.hash` por `lerFiltros(parametrosDoHash(page.url))`.
- **Flags do Chromium no CI.** Com `CI` definido, o Playwright usa `--use-angle=swiftshader --enable-unsafe-swiftshader`, como pede o ADR para o WebGL por software no Linux. Fora do CI, usa o headless padrão: no macOS as flags deixaram a suíte da casca de 5 a 6 vezes mais lenta, sem ganho enquanto não há WebGL.
- **Dados fora do `load` do SvelteKit.** O layout raiz abre o projeto com `abrirProjeto()` e passa o resultado às páginas por contexto (`usarProjeto()`). Assim, a camada de dados não depende do framework e é testada sozinha.

Links que só movem o foco dentro da página, como o "Pular para o conteúdo", não podem ser `href="#id"` puros, porque o router trataria `#id` como uma rota. Use um `onclick` com `preventDefault()`, como em `Casca.svelte`.

## Camada de dados

Toda vista fala com uma `FonteDeDados` (`src/lib/dados/fonte.ts`), nunca com `fetch` direto:

```ts
const { fonte, manifesto } = usarProjeto();
const topicos = await fonte.topicos();   // Topicos | null
const detalhe = await fonte.detalhe(id); // Detalhe | null (resumo, autores, evidências)
```

- **O manifesto vem primeiro.** Os outros arquivos só são pedidos se estiverem em `manifesto.arquivos`. Os ausentes dão `null` **sem requisição**. Um projeto recém-criado (`mapa novo`) tem só o manifesto, e toda vista precisa lidar com `null`. A Início mostra então um estado vazio que manda rodar `mapa coletar` e `mapa topicos`.
- **Cache.** Cada arquivo é pedido uma vez só. Se o pedido falhar, a promessa sai do cache e a próxima chamada tenta de novo. Os erros são `ErroDeDados`, com a URL e o status HTTP.
- **Versão.** Um arquivo com `versao_contrato` de outra versão maior (por exemplo, `2.0`) é recusado, com uma mensagem que explica o que fazer.
- **Fragmentos de detalhes.** Resumos e evidências ficam em `detalhes/{00..3f}.json`. `fragmentoDe(id)` (`fragmentos.ts`) calcula o fragmento de um documento: FNV-1a de 32 bits sobre os bytes UTF-8 do id, módulo 64, em dois dígitos hex. É a mesma função que `fragmento_de` em `src/mapa_da_ciencia/contrato/modelos.py`. O teste confere valores calculados no Python (inclusive ids com acento e emoji) e confere que **cada** documento do exemplo está no fragmento calculado.
- **Modo.** `abrirFonte()` lê o manifesto e escolhe a fonte por `manifesto.api`:
  - `FonteEstatica` (`api: false`, site publicado): lê `./dados/*.json` relativo à página, o que funciona na raiz e em subcaminhos;
  - `FonteApi` (`api: true`, painel local): por enquanto, herda a estática e declara `capacidades.escrita = true`. Os métodos de escrita e `aoVivo` chegam com a API.

A interface esconde o que a fonte não pode fazer. Por exemplo, a seção **Projeto** só aparece no trilho quando `manifesto.api` é verdadeiro.

## O cubo do filtro cruzado

`src/lib/dados/cubo.ts` responde, para o recorte da URL, quais documentos passam e quantos há por ano, tópico, revista e lugar. Cada dimensão (ano, revista, tópico, busca, laço, UF, país, instituição) tem um bit, e `falhas[i]` guarda as dimensões que o documento *não* atende. Cada vista agrega **excluindo a própria dimensão** (`exceto`): o fluxo por ano mostra o período inteiro com o intervalo destacado, e o mapa das UFs mantém as outras UFs clicáveis. Os filtros de lugar valem por documento (basta uma afiliação); o peso fracionário só entra nas somas geográficas.

`src/lib/dados/corpus.ts` abre o corpus uma vez por fonte (`abrirCubo`): tabela de documentos, tópicos, afiliações (se houver) e o cubo, compartilhado pelas vistas e pela barra de recorte. A busca (`dados/busca.ts`) monta o índice uma vez (`indiceDe`).

## Estado na URL

`src/lib/estado/url.ts` define o formato do endereço:

| Parâmetro | Exemplo | Padrão (omitido da URL) |
|---|---|---|
| `anos` | `2012-2020` ou `2015` | todo o período |
| `revistas` | `dados,op` | todas |
| `topicos` | `3,12` (`-1` = sem tópico) | todos |
| `cor` | `topico`, `macrotema`, `revista`, `ano` | `topico` |
| `busca` | `coalizão` | vazio |
| `laco` | `a1b2~0.1,0.2~0.3,0.1~…` (versão do mapa e vértices em coordenadas dos dados) | nenhum |
| `uf` | `SP,RJ` (documentos com alguma afiliação nessas UFs) | todas |
| `pais` | `AR,US` (ISO alfa-2) | todos |
| `inst` | `ror:036rp1748` | todas |
| `modo` | `fluxo`, `absoluto`, `proporcao` (vista Tópicos) | `fluxo` |
| `macro` | `3` (macrotema aberto na vista Tópicos) | nenhum |
| `vista` | `0.12,-0.3,2.5` (câmera do mapa: centro e zoom) | a câmera inicial |
| `topico` | `12` (gaveta do tópico; não confundir com `topicos`, que filtra) | nenhum |
| `doc` | `exemplo:00042` | nenhum |

O **recorte** (`CHAVES_RECORTE`: `anos`, `revistas`, `topicos`, `busca`, `laco`, `uf`, `pais`, `inst`) é o que as vistas de análise compartilham: o trilho o leva de uma seção a outra (seções com `recorte: true` em `secoes.ts`). Os demais parâmetros são de cada vista e ficam para trás.

`escreverFiltros()` omite os valores padrão e usa ordem fixa, então o mesmo estado gera sempre o mesmo link. `lerFiltros()` ignora valores inválidos sem erro. O teste de ida e volta (`url.test.ts`) cobre filtros → URL → filtros, URL canônica → filtros → mesma URL e 300 combinações aleatórias com semente fixa.

## Tipos do contrato

A fonte da verdade são os modelos Pydantic em `src/mapa_da_ciencia/contrato/modelos.py`. Quando eles mudam:

```bash
# na raiz do repositório
uv run python scripts/gerar_contrato.py   # modelos → contrato/schema/*.schema.json e exemplo
# em frontend/
npm run tipos                             # schemas → src/lib/contrato/tipos.ts
npm run check                             # o que o TypeScript acusar é o que precisa mudar na interface
```

`tipos.ts` é versionado, e o `npm run tipos:checar` do CI falha se ele não bater com os schemas. O gerador (`scripts/gerar-tipos.ts`) junta os schemas num só, para cada tipo aparecer uma vez. Ele também converte as tuplas (`prefixItems`) e tira os títulos por campo que o Pydantic emite, que virariam dezenas de tipos soltos. As descrições dos modelos viram comentários JSDoc.

## Identidade visual

Um só sistema de tokens (`src/lib/estilos/tokens.css`) com dois temas, escolhidos por `data-tema` no `<html>`:

| | Observatório (escuro, padrão) | Prancha (claro) |
|---|---|---|
| Ideia | céu noturno de observatório | papel de atlas |
| Fundo | `#0A0E1F`, com estrelas | `#F6F2E9`, com grade fina |
| Superfície | `#111733` | `#FBF8F2` |
| Texto | `#ECEAF4` | `#161A2B` |
| Linhas | `#232B55` | `#DCD3C2` |
| Acento | âmbar `#FFB547` | vermelhão `#C2410C` |

- **Fontes** locais (pacotes `@fontsource-variable`), sem requisição externa: Fraunces, com eixo óptico, para títulos e números grandes; Instrument Sans para a interface; JetBrains Mono para números tabulares e rótulos.
- **Tema.** Segue `prefers-color-scheme` até a pessoa usar o botão da barra superior. A escolha fica em `localStorage` (`mapa-da-ciencia:tema`), dentro de `try/catch`. O script inline do `app.html` aplica o tema antes da primeira pintura.
- **Contraste AA.** `contraste.test.ts` lê `tokens.css` e confere cada par de texto sobre fundo nos dois temas: 4,5:1 para texto, 3:1 para foco e itens desativados. As regras:
  - o acento só vira texto sobre `--fundo` ou `--superficie`;
  - `--texto-fraco` fica só em itens desativados e ornamentos.
- **Movimento.** As transições são curtas: troca de tema e entrada das páginas. Todas somem com `prefers-reduced-motion`.
- **Acessibilidade.** `lang="pt-BR"`, link "Pular para o conteúdo", foco sempre visível, marcos `header`/`nav`/`main`, `aria-current` no trilho. Ícones decorativos ficam com `aria-hidden`.
- **Tela estreita** (até 820 px): o trilho vira uma barra fixa embaixo, que rola na horizontal.

## Testes

**Unitários** (`npm test`, Vitest):

| Arquivo | Confere |
|---|---|
| `dados/fragmentos.test.ts` | `fragmentoDe` igual ao Python; os 64 fragmentos cobertos; cada documento do exemplo no fragmento certo |
| `dados/estatica.test.ts` | cache; detalhe no fragmento certo; escolha da fonte por `api`; projeto vazio sem nenhuma requisição além do manifesto (`fetch` falso); erro e nova tentativa; versão do contrato |
| `estatistica/glm.test.ts` | a tendência no navegador igual à referência em Python: os 13 casos de `contrato/casos/tendencia.json` e o gabarito de cada tópico e macrotema do exemplo |
| `graficos/fluxo.test.ts` | empilhamento do fluxo (proporção soma 1, absoluto soma o total, fluxo preserva as espessuras, ordem fixa entre os modos) e rótulos dentro das faixas só onde cabem |
| `formato.test.ts` | decimais, porcentagens e pontos percentuais em pt-BR |
| `dados/cubo.test.ts` | o filtro cruzado contra o gabarito do Python (`agregados.json`): tópico × ano × revista com e sem filtros, UFs, países e instituições fracionários, séries; 300 recortes aleatórios contra uma filtragem ingênua; exclusão de dimensões; lugares por documento; busca e laço |
| `dados/documentos.test.ts` | decodificação do `documentos.json`: NDC com a mesma escala nos dois eixos, enquadramento que resiste a ilhas, vizinhos, índice |
| `estado/url.test.ts` | `rota()`, `lerHash()` e a ida e volta dos filtros, inclusive `laco` e `vista` |
| `estado/sem-resolve.test.ts` | nenhum `resolve()` nem link absoluto em `src/` |
| `estilos/contraste.test.ts` | contraste AA dos tokens nos dois temas |
| `graficos/geometria.test.ts` | simplificação do laço (RDP) e ponto no polígono |
| `mapa/busca.test.ts` | busca por título e autor sem diferença de acentos |
| `mapa/contornos.test.ts` | contornos que envolvem o núcleo de cada tópico, banda adaptada, ~80% dentro |
| `mapa/cores.test.ts` | paletas de revista e de ano |
| `geografia/escala.test.ts` | classes de cor em escala logarítmica com limites redondos; a escala sequencial (`--seq-*`) muda de claridade sempre no mesmo sentido, com tons vizinhos distinguíveis e o mais forte com contraste 3:1 sobre o fundo, nos dois temas |
| `geografia/malhas.test.ts` | as 27 UFs do IBGE com a sigla, os países com ISO-2 único, projeções que cabem na área de desenho |

**De ponta a ponta** (`npm run e2e`). O `tests/e2e/preparar.ts` copia o build para uma pasta temporária, com os dados de exemplo em `dados/` ao lado do `index.html`, e serve cinco sites com um estático sem reescrita:

| Site | Serve |
|---|---|
| raiz | build + exemplo em `/` |
| subcaminho | build + exemplo em `/mapa-da-ciencia/demo/` |
| vazio | build + só um manifesto de projeto novo, com `api: true`, e a API falsa do painel |
| painel | build + exemplo com `api: true` e as duas APIs falsas (`api-falsa.ts` e `api-falsa-painel.ts`) |
| publicado | build + `contrato/exemplo-publicado/`, o exemplo passado pelas regras do `mapa publicar` (gerado pelo `scripts/gerar_contrato.py`; o job do frontend no CI não tem Python) |

Os testes cobrem:

- navegar por todas as seções clicando no trilho, na raiz e no subcaminho, sempre no cliente, sem recarga completa;
- nenhum 404, erro ou aviso no console;
- a Início com os números do `manifesto.json` e os 7 macrotemas;
- link com filtros aberto direto;
- troca de tema e memória da escolha;
- o link de pular;
- rota inexistente;
- tela estreita: nenhuma rota rola de lado a 375 px (celular emulado, com a barra de navegação na tela e o recorte do Mapa aberto), 768 e 1024 px;
- projeto vazio, sem pedir arquivos ausentes;
- no Mapa (`mapa.spec.ts`): o desenho dos pontos, contornos e rótulos pelo zoom, legenda, cor por revista, cartão pelo link e pelo clique, busca, laço pelo link e pelo mouse, play da linha do tempo e atalhos.
- na Geografia (`geografia.spec.ts`): o peso de cada UF igual ao gabarito do Python, o ranking pela instituição de maior peso, o Brasil fora da escala do mundo, o clique numa UF que vai para o recorte e dali para o Mapa, o teclado, "Ver como tabela", "Mostrar mais", a cobertura por ano (o aviso dos anos com muito peso sem afiliação) e o projeto vazio.
- na Classificação, na Validação e na codificação (`classificacao.spec.ts`, `validacao.spec.ts`, `codificar.spec.ts`): as barras e o cruzamento conferidos com o exemplo, a lista com a evidência marcada, os selos de kappa, a matriz de confusão e 20 fichas codificadas só pelo teclado que sobrevivem a um reload.
- no Projeto (`projeto.spec.ts`): a linha de metrô, o job ao vivo que sobrevive à queda proposital da primeira conexão SSE, cancelar, retomar depois de um reload, baixar um modelo, o assistente e o editor do codebook; no site estático, a Metodologia.
- na exportação (`exportar.spec.ts`): SVG com as fontes embutidas e a largura do artigo, PNG na largura do preset, CSV com BOM e o modo apresentação.
- no site publicado (`publicado.spec.ts`): nenhuma chamada à API, a Metodologia com o que a publicação retirou e o cartão de um artigo sem licença aberta, com os valores da classificação e sem o resumo nem os trechos citados.

As capturas ficam em `test-results/` (ignorado pelo git): `tema-observatorio-1440x900.png`, `tema-prancha-1440x900.png` e `estreita-observatorio-390x844.png`.

## Como acrescentar uma vista

1. Registre a seção em `src/lib/secoes.ts`: rótulo, caminho, ícone (`componentes/icones.ts`), resumo, marco e arquivos do contrato que ela usa.
2. Crie `src/routes/<caminho>/+page.svelte`. Enquanto a vista não existe, `<PaginaDeSecao secao={secao('id')} />` mostra o estado vazio com a lista dos arquivos presentes.
3. Leia os dados com `usarProjeto().fonte` e trate `null` (arquivo ainda não gerado).
4. Filtros vão para a URL com `rota(caminho, escreverFiltros(filtros))` e voltam com `lerFiltros(parametrosDoHash(page.url))`.
5. Acrescente a seção à lista `SECOES` de `tests/e2e/casca.spec.ts`.
