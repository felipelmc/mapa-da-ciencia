// Spike M0d: verificações em Chromium headless (Playwright), sem test runner.
//
// Pré-requisitos (ver RESULTADOS.md):  npm ci && npx playwright install chromium && npm run build
//
// Uso:
//   node tests/spike.mjs                      # tudo, servidor estático em Node
//   node tests/spike.mjs --servidor=python    # rotas com `python3 -m http.server`
//   node tests/spike.mjs --sem-matriz         # pula a matriz de flags do Chromium
//   node tests/spike.mjs --so-rotas           # só a pergunta 1 (router por hash)
//   node tests/spike.mjs --repeticoes=10      # repetições da medida de tempo (padrão 5)
//
// Saídas: resultados/resultados-<servidor>[-rotas].json, resultados/mapa.png e um resumo no terminal.
// Tudo o que é iniciado aqui (servidores, navegadores) é encerrado no fim, inclusive em erro.
import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';
import { PNG } from 'pngjs';
import { servirComNode, servirComPython } from './servidor.mjs';

const RAIZ = fileURLToPath(new URL('..', import.meta.url));
const BUILD = join(RAIZ, 'build');
const RESULTADOS = join(RAIZ, 'resultados');

const args = new Map(
	process.argv.slice(2).map((a) => {
		const [k, v] = a.replace(/^--/, '').split('=');
		return [k, v ?? true];
	})
);
const SERVIDOR = args.get('servidor') ?? 'node';
const REPETICOES = Number(args.get('repeticoes') ?? 5);
const SO_ROTAS = args.has('so-rotas');
const SEM_MATRIZ = args.has('sem-matriz') || SO_ROTAS;

const VIEWPORT = { width: 1280, height: 800 };
const FUNDO = [0x0a, 0x0e, 0x1f];
// Um pixel conta como "desenhado" se algum canal difere do fundo em mais de 24 (de 255).
const LIMIAR_COR = 24;
// O mapa conta como desenhado se ao menos 0,5% dos pixels do canvas diferem do fundo.
const FRACAO_MINIMA = 0.005;

const VARIANTES = ['sem-fallback', 'com-fallback', 'inline', 'base-fixa', 'relativo'];
// Hipóteses registradas antes de rodar; o script avisa quando o observado diverge.
const ESPERADO = {
	'sem-fallback': { raiz: true, subcaminho: false },
	'com-fallback': { raiz: true, subcaminho: false },
	inline: { raiz: true, subcaminho: true },
	'base-fixa': { raiz: false, subcaminho: true },
	relativo: { raiz: true, subcaminho: true }
};

// Configurações do Chromium para a matriz de flags. `headless-shell` é o padrão do Playwright
// para `headless: true`; `chromium` (channel) é o "novo headless", com o binário completo.
const NAVEGADORES = [
	{ nome: 'headless-shell', opcoes: {} },
	{ nome: 'chromium-novo-headless', opcoes: { channel: 'chromium' } }
];
const CONJUNTOS_DE_FLAGS = [
	[],
	['--use-gl=swiftshader'],
	['--use-angle=swiftshader'],
	['--enable-unsafe-swiftshader'],
	['--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
	['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
	['--disable-gpu'],
	['--disable-gpu', '--enable-unsafe-swiftshader'],
	['--disable-gpu', '--use-angle=swiftshader', '--enable-unsafe-swiftshader']
];
// Configuração "tipo CI" (sem GPU), medida à parte junto com a padrão.
const FLAGS_CI = ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'];

// ---------------------------------------------------------------- utilitários

const esperar = (ms) => new Promise((r) => setTimeout(r, ms));

function mediana(xs) {
	const s = [...xs].sort((a, b) => a - b);
	const m = Math.floor(s.length / 2);
	return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

function resumoTempos(xs) {
	const v = xs.filter((x) => typeof x === 'number');
	if (!v.length) return null;
	const r = (x) => Math.round(x);
	return { n: v.length, mediana: r(mediana(v)), min: r(Math.min(...v)), max: r(Math.max(...v)), valores: v.map(r) };
}

/** Conta pixels diferentes do fundo num PNG (buffer) ou num ImageData-like ({data,width,height}). */
function contarPixels(imagem) {
	const { data, width, height } = Buffer.isBuffer(imagem) ? PNG.sync.read(imagem) : imagem;
	let diferentes = 0;
	let fundoExato = 0;
	const cores = new Set();
	for (let i = 0; i < data.length; i += 4) {
		const d = Math.max(
			Math.abs(data[i] - FUNDO[0]),
			Math.abs(data[i + 1] - FUNDO[1]),
			Math.abs(data[i + 2] - FUNDO[2])
		);
		if (d <= 2) fundoExato += 1;
		if (d > LIMIAR_COR) {
			diferentes += 1;
			cores.add((data[i] >> 4) * 256 + (data[i + 1] >> 4) * 16 + (data[i + 2] >> 4));
		}
	}
	const total = width * height;
	return {
		largura: width,
		altura: height,
		total,
		diferentes,
		fracao: Number((diferentes / total).toFixed(4)),
		fracaoFundo: Number((fundoExato / total).toFixed(4)),
		coresDistintas: cores.size,
		desenhou: diferentes / total >= FRACAO_MINIMA
	};
}

/** Registra erros de console, exceções e respostas com falha de uma página. */
function coletarProblemas(page) {
	const p = { console: [], excecoes: [], respostasComFalha: [], requisicoesFalhas: [] };
	page.on('console', (m) => {
		// O Chromium completo pede /favicon.ico sozinho; o 404 dele não interessa aqui.
		if (m.location()?.url?.endsWith('/favicon.ico')) return;
		if (m.type() === 'error' || m.type() === 'warning') p.console.push(`[${m.type()}] ${m.text()}`);
	});
	page.on('pageerror', (e) => p.excecoes.push(String(e)));
	page.on('response', (r) => {
		if (r.status() >= 400 && !r.url().endsWith('/favicon.ico')) {
			p.respostasComFalha.push(`${r.status()} ${new URL(r.url()).pathname}`);
		}
	});
	page.on('requestfailed', (r) => p.requisicoesFalhas.push(`${r.failure()?.errorText} ${r.url()}`));
	return p;
}

const rotaDebug = (page) => page.evaluate(() => window.__rotaDebug ?? null);

async function esperarRota(page, routeId, timeout = 8000) {
	await page.waitForFunction((id) => window.__rotaDebug?.routeId === id, routeId, { timeout });
}

async function esperarMapa(page, timeout = 30_000) {
	await page.waitForFunction(
		() => window.__mapaDebug && (window.__mapaDebug.desenhado || window.__mapaDebug.erro),
		null,
		{ timeout }
	);
	return page.evaluate(() => {
		const d = window.__mapaDebug;
		return {
			desenhado: d.desenhado,
			erro: d.erro,
			pontos: d.pontos,
			clusters: d.clusters,
			montagens: d.montagens,
			msAtePrimeiroDesenho: d.msAtePrimeiroDesenho,
			msDesdeNavegacao: d.msDesdeNavegacao,
			eventosDraw: d.eventosDraw,
			renderer: d.renderer
		};
	});
}

/** Screenshot só do canvas, com os painéis sobrepostos escondidos. */
async function screenshotCanvas(page) {
	const estilo = await page.addStyleTag({
		content: 'nav, aside, .status { visibility: hidden !important; }'
	});
	await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
	const png = await page.getByTestId('canvas-mapa').screenshot();
	await estilo.evaluate((e) => e.remove());
	return png;
}

async function medirPixels(page) {
	return contarPixels(await screenshotCanvas(page));
}

async function sondarWebGL(page) {
	return page.evaluate(() => {
		const sondar = (tipo) => {
			const gl = document.createElement('canvas').getContext(tipo);
			if (!gl) return null;
			const ext = gl.getExtension('WEBGL_debug_renderer_info');
			return {
				versao: gl.getParameter(gl.VERSION),
				vendor: ext ? gl.getParameter(ext.UNMASKED_VENDOR_WEBGL) : gl.getParameter(gl.VENDOR),
				renderer: ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER)
			};
		};
		return { webgl: sondar('webgl'), webgl2: sondar('webgl2') };
	});
}

async function passo(r, nome, fn) {
	try {
		r[nome] = { ok: true, ...(await fn()) };
	} catch (e) {
		r[nome] = { ok: false, erro: String(e?.message ?? e).split('\n')[0] };
	}
	return r[nome].ok;
}

// ------------------------------------------------------ pergunta 1: rotas

async function verificarRotas(browser, urlBase) {
	const contexto = await browser.newContext({ viewport: VIEWPORT });
	const r = { urlBase };
	const problemas = [];
	const novaPagina = async () => {
		const p = await contexto.newPage();
		problemas.push(coletarProblemas(p));
		return p;
	};

	try {
		const page = await novaPagina();

		// a) Carga inicial de #/
		const carregou = await passo(r, 'a_cargaInicio', async () => {
			await page.goto(urlBase + '#/');
			await page.getByTestId('pagina-inicial').waitFor({ timeout: 8000 });
			await page.evaluate(() => (window.__semRecarga = true));
			return { rota: await rotaDebug(page) };
		});
		if (!carregou) return r;

		// Marca a janela antes de cada ação; se a marca sumir, houve recarga completa da página.
		const marcar = () => page.evaluate(() => (window.__semRecarga = true));
		const semRecarga = () => page.evaluate(() => window.__semRecarga === true);
		const montagens = () => page.evaluate(() => window.__mapaDebug?.montagens ?? null);

		// b) Link feito com resolve('/mapa')
		await passo(r, 'b_linkResolveMapa', async () => {
			await marcar();
			const href = await page.getByTestId('link-mapa').getAttribute('href');
			await page.getByTestId('link-mapa').click();
			await esperarRota(page, '/mapa');
			return { href, urlNaBarra: page.url(), navegacaoNoCliente: await semRecarga() };
		});

		// c) Link feito com resolve('/')
		await passo(r, 'c_linkResolveInicio', async () => {
			await marcar();
			const href = await page.getByTestId('link-inicio').getAttribute('href');
			await page.getByTestId('link-inicio').click();
			await esperarRota(page, '/');
			return { href, urlNaBarra: page.url(), navegacaoNoCliente: await semRecarga() };
		});

		// d) Link literal "#/mapa?anos=2012-2020&cor=topico"
		await passo(r, 'd_linkComParametros', async () => {
			await marcar();
			await page.getByTestId('link-mapa-params').click();
			await esperarRota(page, '/mapa');
			const rota = await rotaDebug(page);
			const mapa = await esperarMapa(page);
			return {
				href: await page.getByTestId('link-mapa-params').getAttribute('href'),
				urlNaBarra: page.url(),
				navegacaoNoCliente: await semRecarga(),
				pageUrlSearchParams: rota.searchParams,
				pageUrlHash: rota.hash,
				parametrosLidosDoHash: rota.hashParams,
				searchParamsFunciona: rota.searchParams.anos === '2012-2020',
				hashManualFunciona: rota.hashParams.anos === '2012-2020' && rota.hashParams.cor === 'topico',
				mapaDesenhado: mapa.desenhado,
				mapaErro: mapa.erro
			};
		});

		// e) goto() trocando só os parâmetros (como um filtro faria), de três jeitos.
		const trocarParametros = async (testId, destino, confere) => {
			await marcar();
			const antes = await montagens();
			await page.getByTestId(testId).click();
			await page.waitForFunction(confere, null, { timeout: 8000 });
			await esperarMapa(page);
			const rota = await rotaDebug(page);
			const noCliente = await semRecarga();
			const depois = await montagens();
			return {
				destino,
				urlNaBarra: page.url(),
				routeId: rota.routeId,
				parametrosLidosDoHash: rota.hashParams,
				pageUrlSearchParams: rota.searchParams,
				navegacaoNoCliente: noCliente,
				mapaPreservado: noCliente && antes === depois
			};
		};
		await passo(r, 'e1_gotoHashRelativo', () =>
			trocarParametros(
				'botao-goto-hash',
				"goto('#/mapa?anos=1990-1995&cor=area')",
				() => window.__rotaDebug?.hashParams?.anos === '1990-1995'
			)
		);
		await passo(r, 'e2_gotoComResolve', () =>
			trocarParametros(
				'botao-goto',
				'goto(`${resolve("/mapa")}?anos=2000-2005&cor=area`)',
				() => window.__rotaDebug?.hashParams?.anos === '2000-2005'
			)
		);
		await passo(r, 'e3_gotoQueryAntesDoHash', () =>
			trocarParametros(
				'botao-goto-query',
				"goto('?anos=1980-1985&cor=area#/mapa')",
				() => window.__rotaDebug?.searchParams?.anos === '1980-1985'
			)
		);

		// f) Botão voltar do navegador
		await passo(r, 'f_voltar', async () => {
			await marcar();
			await page.goBack();
			await esperarRota(page, '/');
			return { urlNaBarra: page.url(), navegacaoNoCliente: await semRecarga() };
		});

		// g) Carga direta do link profundo, numa aba nova
		const page2 = await novaPagina();
		await passo(r, 'g_cargaDiretaLinkProfundo', async () => {
			await page2.goto(urlBase + '#/mapa?anos=2012-2020&cor=topico');
			await esperarRota(page2, '/mapa');
			const rota = await rotaDebug(page2);
			const mapa = await esperarMapa(page2);
			const pixels = await medirPixels(page2);
			return {
				pageUrlSearchParams: rota.searchParams,
				parametrosLidosDoHash: rota.hashParams,
				mapa,
				pixels
			};
		});

		// h) Recarregar (F5) no link profundo
		await passo(r, 'h_recarregar', async () => {
			await page2.reload();
			await esperarRota(page2, '/mapa');
			const mapa = await esperarMapa(page2);
			const rota = await rotaDebug(page2);
			return { mapaDesenhado: mapa.desenhado, parametrosLidosDoHash: rota.hashParams };
		});

		// i) Parâmetros na query "de verdade", antes do hash: ?anos=...#/mapa
		const page3 = await novaPagina();
		await passo(r, 'i_queryAntesDoHash', async () => {
			await page3.goto(urlBase + '?anos=2012-2020&cor=topico#/mapa');
			await esperarRota(page3, '/mapa');
			const rota = await rotaDebug(page3);
			return {
				urlNaBarra: page3.url(),
				pageUrlSearchParams: rota.searchParams,
				searchParamsFunciona: rota.searchParams.anos === '2012-2020'
			};
		});
	} finally {
		r.problemas = {
			console: problemas.flatMap((p) => p.console),
			excecoes: problemas.flatMap((p) => p.excecoes),
			respostasComFalha: problemas.flatMap((p) => p.respostasComFalha),
			requisicoesFalhas: problemas.flatMap((p) => p.requisicoesFalhas)
		};
		await contexto.close();
	}
	return r;
}

function avaliarRotas(r) {
	const etapas = Object.entries(r).filter(([k]) => /^[a-i]\d?_/.test(k));
	const todasOk = etapas.length === 11 && etapas.every(([, v]) => v.ok);
	const funciona =
		todasOk &&
		r.d_linkComParametros.hashManualFunciona &&
		r.d_linkComParametros.mapaDesenhado &&
		r.g_cargaDiretaLinkProfundo.pixels?.desenhou &&
		r.problemas.respostasComFalha.length === 0 &&
		r.problemas.excecoes.length === 0;
	return { funciona, etapasOk: etapas.filter(([, v]) => v.ok).map(([k]) => k), etapasFalhas: etapas.filter(([, v]) => !v.ok).map(([k]) => k) };
}

async function perguntaRotas(browser) {
	const servir = SERVIDOR === 'python' ? servirComPython : servirComNode;
	const resultados = [];
	for (const variante of VARIANTES) {
		const dir = join(BUILD, variante);
		if (!existsSync(join(dir, 'index.html'))) throw new Error(`faltou o build ${dir}; rode npm run build`);
		for (const modo of ['raiz', 'subcaminho']) {
			const servidor = await servir(modo === 'raiz' ? dir : BUILD);
			try {
				const urlBase = `${servidor.origem}/${modo === 'raiz' ? '' : variante + '/'}`;
				const t0 = performance.now();
				const r = await verificarRotas(browser, urlBase);
				const avaliacao = avaliarRotas(r);
				const esperado = ESPERADO[variante][modo];
				resultados.push({
					variante,
					modo,
					servidor: servidor.tipo,
					esperado,
					funciona: avaliacao.funciona,
					conformeEsperado: avaliacao.funciona === esperado,
					segundos: Number(((performance.now() - t0) / 1000).toFixed(1)),
					...avaliacao,
					detalhes: r,
					logServidorNao200: servidor.log.filter((l) => l.status !== 200).map((l) => `${l.status} ${l.caminho}`)
				});
				console.log(
					`  [rotas] ${variante.padEnd(12)} ${modo.padEnd(10)} ${avaliacao.funciona ? 'FUNCIONA' : 'FALHA   '}` +
						` (esperado: ${esperado ? 'funciona' : 'falha'})` +
						(avaliacao.etapasFalhas.length ? ` etapas com falha: ${avaliacao.etapasFalhas.join(', ')}` : '')
				);
			} finally {
				await servidor.fechar();
			}
		}
	}
	return resultados;
}

// ------------------------------------------------ pergunta 2: regl-scatterplot

async function abrirMapa(browser, urlBase, hash = '#/mapa') {
	const contexto = await browser.newContext({ viewport: VIEWPORT });
	const page = await contexto.newPage();
	const problemas = coletarProblemas(page);
	await page.goto(urlBase + hash);
	const mapa = await esperarMapa(page);
	return { contexto, page, problemas, mapa };
}

async function testarApi(page) {
	const r = {};

	// Seleção por laço, programática (coordenadas GL), em volta do centro do cluster 0.
	await passo(r, 'lassoSelectProgramatico', async () => {
		const res = await page.evaluate(async () => {
			const d = window.__mapaDebug;
			const sp = d.scatterplot;
			const pts = sp.get('points');
			const doCluster = pts.filter((_, i) => d.clusterDoPonto[i] === 0);
			const cx = doCluster.reduce((s, p) => s + p[0], 0) / doCluster.length;
			const cy = doCluster.reduce((s, p) => s + p[1], 0) / doCluster.length;
			const m = 0.08;
			const antes = d.eventosSelect;
			sp.lassoSelect(
				[
					[cx - m, cy - m],
					[cx + m, cy - m],
					[cx + m, cy + m],
					[cx - m, cy + m]
				],
				{ isGl: true }
			);
			await new Promise((r) => setTimeout(r, 200));
			const sel = sp.get('selectedPoints');
			const doZero = sel.filter((i) => d.clusterDoPonto[i] === 0).length;
			return {
				chamada: 'scatterplot.lassoSelect(quadrado GL em volta do cluster 0, { isGl: true })',
				selecionados: sel.length,
				doCluster0: doZero,
				eventosSelectNovos: d.eventosSelect - antes
			};
		});
		if (!(res.selecionados > 0)) throw new Error('lassoSelect não selecionou nada');
		return res;
	});

	// Seleção por laço com o mouse: Shift + arrastar (atalho padrão do regl-scatterplot).
	await passo(r, 'lassoComMouse', async () => {
		await page.evaluate(() => window.__mapaDebug.scatterplot.deselect());
		const alvo = await page.evaluate(() => {
			const d = window.__mapaDebug;
			const sp = d.scatterplot;
			const { width, height } = sp.get('canvas').getBoundingClientRect();
			// Escolhe o cluster cujo primeiro ponto está mais perto do centro da tela.
			let melhor = null;
			for (let c = 0; c < d.clusters; c++) {
				const i = d.clusterDoPonto.indexOf(c);
				const [x, y] = sp.getScreenPosition(i);
				const dist = Math.hypot(x - width / 2, y - height / 2);
				if (!melhor || dist < melhor.dist) melhor = { c, x, y, dist };
			}
			return melhor;
		});
		const antes = await page.evaluate(() => ({
			select: window.__mapaDebug.eventosSelect,
			lassoEnd: window.__mapaDebug.eventosLassoEnd
		}));
		const raio = 45;
		const passos = 32;
		await page.mouse.move(alvo.x + raio, alvo.y);
		await page.keyboard.down('Shift');
		await page.mouse.down();
		for (let k = 1; k <= passos; k++) {
			const a = (2 * Math.PI * k) / passos;
			await page.mouse.move(alvo.x + raio * Math.cos(a), alvo.y + raio * Math.sin(a));
			await esperar(20);
		}
		await page.mouse.up();
		await page.keyboard.up('Shift');
		await esperar(300);
		const res = await page.evaluate(
			({ antes, c }) => {
				const d = window.__mapaDebug;
				const sel = d.scatterplot.get('selectedPoints');
				return {
					chamada: 'Shift + arrastar o mouse num círculo de raio 45 px',
					clusterAlvo: c,
					selecionados: sel.length,
					doClusterAlvo: sel.filter((i) => d.clusterDoPonto[i] === c).length,
					eventosSelectNovos: d.eventosSelect - antes.select,
					eventosLassoEndNovos: d.eventosLassoEnd - antes.lassoEnd
				};
			},
			{ antes, c: alvo.c }
		);
		if (!(res.selecionados > 0)) throw new Error('o laço com mouse não selecionou nada');
		return res;
	});

	await page.evaluate(() => window.__mapaDebug.scatterplot.deselect());
	const pixelsBase = await medirPixels(page);

	// filter(): mantém só os clusters 0-4 (1/8 dos pontos).
	await passo(r, 'filter', async () => {
		const res = await page.evaluate(async () => {
			const d = window.__mapaDebug;
			const sp = d.scatterplot;
			const idx = d.clusterDoPonto.flatMap((c, i) => (c < 5 ? [i] : []));
			const antes = d.eventosFilter;
			await sp.filter(idx);
			// Os eventos do regl-scatterplot são assíncronos (syncEvents: false); espera a entrega.
			await new Promise((r) => setTimeout(r, 200));
			return {
				chamada: 'await scatterplot.filter(índices dos clusters 0–4)',
				pedidos: idx.length,
				filteredPoints: sp.get('filteredPoints').length,
				isPointsFiltered: sp.get('isPointsFiltered'),
				eventosFilterNovos: d.eventosFilter - antes
			};
		});
		const pixelsFiltrado = await medirPixels(page);
		await page.evaluate(() => window.__mapaDebug.scatterplot.unfilter());
		const pixelsDepois = await medirPixels(page);
		if (res.filteredPoints !== res.pedidos) throw new Error('filteredPoints não bate com o pedido');
		return {
			...res,
			pixelsAntes: pixelsBase.diferentes,
			pixelsFiltrado: pixelsFiltrado.diferentes,
			pixelsDepoisDoUnfilter: pixelsDepois.diferentes
		};
	});

	// Cor por categoria: `colorBy: 'valueA'` + paleta; troca por uma cor só e volta.
	await passo(r, 'corPorCategoria', async () => {
		const estado = await page.evaluate(() => {
			const sp = window.__mapaDebug.scatterplot;
			return { colorBy: sp.get('colorBy'), coresNaPaleta: sp.get('pointColor').length };
		});
		const comPaleta = await medirPixels(page);
		const paleta = await page.evaluate(() => window.__mapaDebug.scatterplot.get('pointColor'));
		await page.evaluate(() => window.__mapaDebug.scatterplot.set({ pointColor: '#FFD58F' }));
		const umaCor = await medirPixels(page);
		await page.evaluate((p) => window.__mapaDebug.scatterplot.set({ pointColor: p }), paleta);
		const restaurado = await medirPixels(page);
		return {
			chamada: "scatterplot.set({ colorBy: 'valueA', pointColor: [40 cores] }) / set({ pointColor: '#FFD58F' })",
			...estado,
			coresDistintasComPaleta: comPaleta.coresDistintas,
			coresDistintasComUmaCor: umaCor.coresDistintas,
			coresDistintasRestaurado: restaurado.coresDistintas
		};
	});

	// export(): segunda forma de verificar o desenho, sem screenshot. O export() síncrono (sem
	// opções) lê o buffer depois de apresentado e volta vazio; o assíncrono (com opções) redesenha.
	// Nos dois casos o fundo sai transparente, então aqui conta pixel com alfa > 0.
	await passo(r, 'export', async () => {
		const res = await page.evaluate(async () => {
			const sp = window.__mapaDebug.scatterplot;
			const contar = (im) => {
				let comAlfa = 0;
				for (let i = 3; i < im.data.length; i += 4) if (im.data[i] > 0) comAlfa += 1;
				const total = im.width * im.height;
				return { largura: im.width, altura: im.height, pixelsComAlfa: comAlfa, fracao: Number((comAlfa / total).toFixed(4)) };
			};
			return {
				sincrono: { chamada: 'scatterplot.export()', ...contar(sp.export()) },
				assincrono: {
					chamada: 'await scatterplot.export({ scale: 1, antiAliasing: 1, pixelAligned: false })',
					...contar(await sp.export({ scale: 1, antiAliasing: 1, pixelAligned: false }))
				}
			};
		});
		if (!(res.assincrono.fracao >= FRACAO_MINIMA)) throw new Error('export() assíncrono veio vazio');
		return res;
	});

	return r;
}

async function perguntaMapa(urlBase) {
	const saida = { urlBase };
	const browser = await chromium.launch({ headless: true });
	try {
		saida.versaoChromium = browser.version();
		// Screenshot de referência.
		{
			const { contexto, page, problemas, mapa } = await abrirMapa(
				browser,
				urlBase,
				'#/mapa?anos=2012-2020&cor=topico'
			);
			await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
			await page.screenshot({ path: join(RESULTADOS, 'mapa.png') });
			saida.screenshot = {
				arquivo: 'resultados/mapa.png',
				mapa,
				pixelsCanvas: await medirPixels(page),
				webgl: await sondarWebGL(page),
				problemas
			};
			saida.api = await testarApi(page);
			await contexto.close();
		}
	} finally {
		await browser.close();
	}

	// Tempo até o primeiro desenho em três configurações: headless-shell padrão, headless-shell com
	// SwiftShader explícito ("tipo CI") e novo headless (binário completo; no Mac usa a GPU).
	// Os navegadores ficam abertos e as repetições se alternam, para não misturar efeito de ordem.
	const configs = [
		{ nome: 'padrao', opcoes: {}, flags: [] },
		{ nome: 'swiftshader', opcoes: {}, flags: FLAGS_CI },
		{ nome: 'novo-headless', opcoes: { channel: 'chromium' }, flags: [] }
	];
	const abertos = [];
	try {
		for (const c of configs) {
			abertos.push({
				...c,
				browser: await chromium.launch({ headless: true, ...c.opcoes, args: c.flags }),
				primeiro: [],
				desdeNavegacao: [],
				renderers: new Set()
			});
		}
		for (let i = 0; i < REPETICOES; i++) {
			for (const c of abertos) {
				const { contexto, mapa } = await abrirMapa(c.browser, urlBase);
				c.primeiro.push(mapa.msAtePrimeiroDesenho);
				c.desdeNavegacao.push(mapa.msDesdeNavegacao);
				c.renderers.add(mapa.renderer);
				await contexto.close();
			}
		}
	} finally {
		for (const c of abertos) await c.browser.close();
	}
	saida.tempos = Object.fromEntries(
		abertos.map((c) => [
			c.nome,
			{
				navegador: c.opcoes.channel ? 'chromium-novo-headless' : 'headless-shell',
				flags: c.flags,
				renderer: [...c.renderers],
				msAtePrimeiroDesenho: resumoTempos(c.primeiro),
				msDesdeNavegacao: resumoTempos(c.desdeNavegacao)
			}
		])
	);
	return saida;
}

async function matrizFlags(urlBase) {
	const linhas = [];
	for (const nav of NAVEGADORES) {
		for (const flags of CONJUNTOS_DE_FLAGS) {
			const linha = { navegador: nav.nome, flags };
			let b;
			try {
				b = await chromium.launch({ headless: true, ...nav.opcoes, args: flags });
				linha.versao = b.version();
				const contexto = await b.newContext({ viewport: VIEWPORT });
				const page = await contexto.newPage();
				const problemas = coletarProblemas(page);
				await page.goto(urlBase + '#/mapa');
				linha.webgl = await sondarWebGL(page);
				const mapa = await esperarMapa(page, 20_000);
				linha.mapa = mapa;
				linha.pixels = mapa.desenhado ? await medirPixels(page) : null;
				linha.desenhou = Boolean(mapa.desenhado && linha.pixels?.desenhou);
				linha.msAtePrimeiroDesenho = mapa.msAtePrimeiroDesenho;
				linha.avisosConsole = [...new Set(problemas.console)].slice(0, 5);
				linha.respostasComFalha = problemas.respostasComFalha;
				linha.excecoes = problemas.excecoes;
				await contexto.close();
			} catch (e) {
				linha.desenhou = false;
				linha.erro = String(e?.message ?? e).split('\n')[0];
			} finally {
				await b?.close();
			}
			console.log(
				`  [flags] ${nav.nome.padEnd(22)} ${(flags.join(' ') || '(nenhuma)').padEnd(78)} ` +
					`${linha.desenhou ? 'DESENHOU' : 'NÃO DESENHOU'}  ${linha.mapa?.renderer ?? linha.mapa?.erro ?? linha.erro ?? ''}`
			);
			linhas.push(linha);
		}
	}
	return linhas;
}

// ------------------------------------------------------------------ main

async function main() {
	mkdirSync(RESULTADOS, { recursive: true });
	const resultado = {
		quando: new Date().toISOString(),
		servidor: SERVIDOR,
		node: process.version,
		plataforma: `${process.platform}-${process.arch}`,
		limiares: { LIMIAR_COR, FRACAO_MINIMA }
	};

	console.log(`Spike M0d — servidor estático: ${SERVIDOR}`);
	console.log('Pergunta 1: router por hash (variante x modo)');
	const browser = await chromium.launch({ headless: true });
	try {
		resultado.versaoChromium = browser.version();
		resultado.rotas = await perguntaRotas(browser);
	} finally {
		await browser.close();
	}

	if (!SO_ROTAS) {
		// A pergunta 2 usa a variante sem-fallback servida na raiz (o caso que funciona sem contorno).
		const servidor = await servirComNode(join(BUILD, 'sem-fallback'));
		try {
			const urlBase = `${servidor.origem}/`;
			console.log('Pergunta 2: regl-scatterplot');
			resultado.mapa = await perguntaMapa(urlBase);
			const t = resultado.mapa.tempos;
			for (const [nome, v] of Object.entries(t)) {
				console.log(
					`  [tempo] ${nome.padEnd(13)} primeiro desenho (onMount -> draw + 2 quadros): mediana ${v.msAtePrimeiroDesenho?.mediana} ms` +
						` [${v.msAtePrimeiroDesenho?.min}–${v.msAtePrimeiroDesenho?.max}]; desde a navegação: mediana ${v.msDesdeNavegacao?.mediana} ms` +
						`  (${v.renderer.join(' | ')})`
				);
			}
			for (const [nome, v] of Object.entries(resultado.mapa.api)) {
				console.log(`  [api] ${nome.padEnd(24)} ${v.ok ? 'OK' : 'FALHA: ' + v.erro}`);
			}
			if (!SEM_MATRIZ) {
				console.log('Matriz de flags do Chromium');
				resultado.matrizFlags = await matrizFlags(urlBase);
			}
		} finally {
			await servidor.fechar();
		}
	}

	const arquivo = join(RESULTADOS, `resultados-${SERVIDOR}${SO_ROTAS ? '-rotas' : ''}.json`);
	writeFileSync(arquivo, JSON.stringify(resultado, null, 2) + '\n');
	console.log(`\nResultados completos em ${arquivo}`);

	const divergencias = resultado.rotas.filter((r) => !r.conformeEsperado);
	const apiFalhou = resultado.mapa && Object.values(resultado.mapa.api).some((v) => !v.ok);
	if (divergencias.length || apiFalhou) {
		console.log(
			`ATENÇÃO: ${divergencias.length} combinação(ões) variante/modo divergiram do esperado` +
				(apiFalhou ? '; alguma chamada da API do regl-scatterplot falhou' : '')
		);
		process.exitCode = 1;
	}
}

main().catch((e) => {
	console.error(e);
	process.exitCode = 1;
});
