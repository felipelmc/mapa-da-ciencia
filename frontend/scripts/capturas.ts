// Gera as capturas usadas na documentação (docs/imagens/), a partir dos dados de um projeto: o Mapa, os Tópicos
// e, se o projeto tiver geografia, a Geografia.
//
// Uso (da pasta frontend/, depois de `npm run build`):
//   node scripts/capturas.ts ../projetos/cp-scielo
//
// Roda localmente, não no CI: o piloto não está no repositório. O build e a pasta saida/dados do projeto
// são copiados para uma pasta temporária e servidos pelo mesmo servidor estático dos testes e2e. O cartão
// mostra um documento representativo de um tópico grande, sempre com licença CC BY (o resumo vai para o
// site público da documentação).
import { chromium, type Page } from '@playwright/test';
import { cpSync, existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, statSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { servir } from '../tests/e2e/servidor.ts';

const FRONTEND = fileURLToPath(new URL('..', import.meta.url));
const DESTINO = join(FRONTEND, '..', 'docs', 'imagens');
const LARGURA = 1280;
const ALTURA = 800;

const projeto = resolve(process.argv[2] ?? join(FRONTEND, '..', 'projetos', 'cp-scielo'));
const dados = join(projeto, 'saida', 'dados');
for (const arquivo of ['documentos.json', 'topicos.json', 'detalhes']) {
	if (!existsSync(join(dados, arquivo))) {
		console.error(`Falta ${join(dados, arquivo)}: rode \`mapa topicos\` no projeto antes.`);
		process.exit(1);
	}
}
if (!existsSync(join(FRONTEND, 'build', 'index.html'))) {
	console.error('Falta o build da interface: rode `npm run build` antes.');
	process.exit(1);
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const ler = (caminho: string): any => JSON.parse(readFileSync(caminho, 'utf8'));
const documentos = ler(join(dados, 'documentos.json'));
const topicos = ler(join(dados, 'topicos.json'));
const detalhes: Record<string, { resumo: string | null; licenca: string; fonte_analise: string | null }> = {};
for (const arquivo of readdirSync(join(dados, 'detalhes'))) {
	Object.assign(detalhes, ler(join(dados, 'detalhes', arquivo)).documentos);
}

/** Um representativo de um dos maiores tópicos, com resumo curto e licença CC BY. */
function escolherDocumento(): string {
	const maiores = [...topicos.topicos].sort((a, b) => b.n - a.n);
	for (const t of maiores) {
		for (const id of t.representativos as string[]) {
			const d = detalhes[id];
			if (d?.resumo && d.licenca === 'cc-by' && d.fonte_analise === 'resumo' && d.resumo.length < 1100) return id;
		}
	}
	throw new Error('Nenhum representativo com licença CC BY e resumo curto.');
}

async function abrir(page: Page, hash: string) {
	await page.goto(`${origem}/#/mapa${hash}`);
	await page.waitForFunction(() => window.__mapaDebug?.desenhado || window.__mapaDebug?.erro, null, { timeout: 30_000 });
	const erro = await page.evaluate(() => window.__mapaDebug?.erro);
	if (erro) throw new Error(`O mapa não desenhou: ${erro}`);
	await page.waitForTimeout(600); // rótulos e contornos entram depois do primeiro desenho
}

async function capturar(page: Page, nome: string) {
	const arquivo = join(DESTINO, `${nome}.png`);
	await page.screenshot({ path: arquivo });
	console.log(`${arquivo} (${Math.round(statSync(arquivo).size / 1024)} KB)`);
}

const site = mkdtempSync(join(tmpdir(), 'mapa-capturas-'));
cpSync(join(FRONTEND, 'build'), site, { recursive: true });
cpSync(dados, join(site, 'dados'), { recursive: true });
mkdirSync(DESTINO, { recursive: true });
const servidor = await servir(site);
const origem = servidor.origem;
const navegador = await chromium.launch();

try {
	const contexto = await navegador.newContext({
		viewport: { width: LARGURA, height: ALTURA },
		deviceScaleFactor: 1.5,
		colorScheme: 'dark'
	});
	const page = await contexto.newPage();
	const id = escolherDocumento();
	const indice = (documentos.colunas.id as string[]).indexOf(id);

	// 1. o corpus inteiro, com os rótulos dos macrotemas
	await abrir(page, '');
	await capturar(page, 'mapa');

	// 2. um laço em volta da região do documento escolhido
	const canvas = page.getByTestId('canvas-mapa');
	const caixa = (await canvas.boundingBox())!;
	const [px, py] = (await page.evaluate((i) => window.__mapaDebug!.posicaoNaTela!(i), indice))!;
	const [nx, ny] = [(px / caixa.width) * 2 - 1, 1 - (py / caixa.height) * 2];
	const vertices = Array.from({ length: 16 }, (_, k): [number, number] => {
		const a = (2 * Math.PI * k) / 16;
		return [nx + 0.22 * Math.cos(a), ny + 0.3 * Math.sin(a)];
	});
	await page.evaluate((v) => window.__mapaDebug!.laco!(v), vertices);
	await page.getByTestId('chip-laco').waitFor();
	await page.waitForTimeout(400);
	await capturar(page, 'mapa-laco');

	// 3. o cartão do documento, com o zoom sobre o tópico dele (os rótulos passam a ser dos tópicos)
	await abrir(page, `?doc=${encodeURIComponent(id)}`);
	await page.getByTestId('cartao-documento').waitFor();
	const [qx, qy] = (await page.evaluate((i) => window.__mapaDebug!.posicaoNaTela!(i), indice))!;
	await page.mouse.move(caixa.x + qx, caixa.y + qy);
	for (let i = 0; i < 3; i += 1) await page.mouse.wheel(0, -300);
	await page.waitForFunction(() => (window.__mapaDebug?.zoom ?? 1) > 2.2);
	await page.waitForTimeout(800);
	await capturar(page, 'mapa-cartao');

	// 4. os Tópicos: o fluxo dos macrotemas e, abaixo, as listas em alta e em queda
	await page.goto(`${origem}/#/topicos`);
	await page.getByTestId('figura-fluxo').and(page.locator('[data-pronto="sim"]')).waitFor();
	await page.waitForTimeout(500);
	await capturar(page, 'topicos');
	await page.getByTestId('figura-tendencias').screenshot({ path: join(DESTINO, 'topicos-tendencias.png') });
	console.log(join(DESTINO, 'topicos-tendencias.png'));

	// 5. a gaveta do tópico que mais cresceu
	const emAlta = [...topicos.topicos]
		.filter((t) => t.tendencia?.direcao === 'alta')
		.sort((a, b) => (b.tendencia.pp_periodo ?? 0) - (a.tendencia.pp_periodo ?? 0))[0];
	if (emAlta) {
		await page.goto(`${origem}/#/topicos?topico=${emAlta.id}`);
		await page.getByTestId('gaveta-topico').waitFor();
		await page.waitForTimeout(400);
		await capturar(page, 'topicos-gaveta');
	}

	// 6. a Geografia: UFs e instituições, o mundo e a cobertura por ano
	if (existsSync(join(dados, 'afiliacoes.json'))) {
		await page.goto(`${origem}/#/geografia`);
		await page.getByTestId('figura-ufs').and(page.locator('[data-pronto="sim"]')).waitFor();
		await page.getByTestId('figura-mundo').and(page.locator('[data-pronto="sim"]')).waitFor();
		await page.waitForTimeout(400);
		await capturar(page, 'geografia');
		for (const figura of ['mundo', 'cobertura']) {
			const arquivo = join(DESTINO, `geografia-${figura}.png`);
			await page.getByTestId(`figura-${figura}`).screenshot({ path: arquivo });
			console.log(arquivo);
		}
	} else {
		console.log('Sem afiliacoes.json: rode `mapa geografia` no projeto para capturar a Geografia.');
	}
	await contexto.close();
} finally {
	await navegador.close();
	await servidor.fechar();
	rmSync(site, { recursive: true, force: true });
}
