// A abertura do site ("Céu que se forma"): o céu desenha uma estrela por artigo e forma as constelações, o
// movimento reduzido mostra o céu pronto, o idioma e o tema ficam guardados, cabe num celular, os links levam a
// páginas que existem, e o peso e o contraste ficam dentro do combinado.
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test, type Page } from '@playwright/test';
import { SITE } from './preparar';

const url = () => process.env.E2E_URL_PAGINA!;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const dados: any = JSON.parse(readFileSync(join(SITE, 'assets', 'pagina', 'dados.json'), 'utf8'));

/** Erros do console e respostas ≥ 400 do próprio site (as fontes do Google ficam de fora). */
function vigiar(page: Page) {
	const problemas: string[] = [];
	page.on('console', (m) => {
		if (m.type() === 'error') problemas.push(`console: ${m.text()}`);
	});
	page.on('pageerror', (e) => problemas.push(`exceção: ${e.message}`));
	page.on('response', (r) => {
		if (r.status() >= 400 && r.url().startsWith(url())) problemas.push(`${r.status()} ${r.url()}`);
	});
	return problemas;
}

const fase = (page: Page) => page.evaluate(() => (window as unknown as { __ceu: { fase: string } }).__ceu.fase);

test('o céu acende uma estrela por artigo e forma as constelações', async ({ page }) => {
	const problemas = vigiar(page);
	await page.goto(url());
	await expect.poll(() => fase(page), { timeout: 20_000 }).toBe('formado');
	const ceu = await page.evaluate(() => (window as unknown as { __ceu: Record<string, number> }).__ceu);
	expect(ceu.pontos).toBe(dados.ceu.n);
	expect(ceu.estrelas).toBe(dados.ceu.estrelas.length);
	await expect(page.locator('.ceu__rotulo')).toHaveCount(dados.ceu.constelacoes.length);
	await expect(page.locator('.ceu__rotulo').first()).toBeVisible();
	await expect(page.locator('#ceu-ano')).toHaveText(String(dados.ceu.anos.at(-1)));
	await expect(page.getByRole('button', { name: 'Ver de novo' })).toBeVisible();
	await expect(page.locator('.historia')).toHaveCount(await page.evaluate(() => (window as unknown as { __ceu: { historias: number } }).__ceu.historias));
	await expect(page.locator('#metodo li')).toHaveCount(6);
	expect(problemas).toEqual([]);
});

test('com movimento reduzido, o céu já aparece formado', async ({ page }) => {
	await page.emulateMedia({ reducedMotion: 'reduce' });
	await page.goto(url());
	await expect.poll(() => fase(page), { timeout: 3_000 }).toBe('formado');
	await expect(page.getByRole('button', { name: 'Ver de novo' })).toBeHidden();
	await expect(page.locator('#numeros dd').first()).toHaveText(new Intl.NumberFormat('pt-BR').format(dados.numeros.artigos));
});

test('o idioma e o tema ficam guardados', async ({ page }) => {
	await page.emulateMedia({ reducedMotion: 'reduce' });
	await page.goto(url());
	await page.getByRole('button', { name: 'EN', exact: true }).click();
	await expect(page.locator('#abertura-titulo')).toContainText('What does');
	await expect(page.locator('#ceu-pagina')).toHaveAttribute('lang', 'en');
	await expect(page.locator('#numeros dd').first()).toHaveText(new Intl.NumberFormat('en-US').format(dados.numeros.artigos));
	const antes = await page.evaluate(() => document.body.getAttribute('data-md-color-scheme'));
	await page.locator('form[data-md-component="palette"] label:visible').first().click();
	await expect.poll(() => page.evaluate(() => document.body.getAttribute('data-md-color-scheme'))).not.toBe(antes);
	const depois = await page.evaluate(() => document.body.getAttribute('data-md-color-scheme'));
	await page.reload();
	await expect(page.locator('#abertura-titulo')).toContainText('What does');
	expect(await page.evaluate(() => document.body.getAttribute('data-md-color-scheme'))).toBe(depois);
	await page.getByRole('button', { name: 'PT', exact: true }).click();
	await expect(page.locator('#abertura-titulo')).toContainText('Sobre o que escreve');
});

test('num celular: sem rolagem horizontal, e os rótulos cabem no céu', async ({ page }) => {
	await page.setViewportSize({ width: 375, height: 812 });
	await page.emulateMedia({ reducedMotion: 'reduce' });
	await page.goto(url());
	await expect.poll(() => fase(page)).toBe('formado');
	await page.evaluate(() => document.fonts.ready);
	const larguras = await page.evaluate(() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]);
	expect(larguras[0]).toBeLessThanOrEqual(larguras[1]);
	const caixa = (await page.locator('#ceu').boundingBox())!;
	for (const rotulo of await page.locator('.ceu__rotulo').all()) {
		const r = (await rotulo.boundingBox())!;
		expect(r.x).toBeGreaterThanOrEqual(caixa.x - 1);
		expect(r.x + r.width).toBeLessThanOrEqual(caixa.x + caixa.width + 1);
	}
});

test('os links da abertura levam a páginas do site ou às vistas da demo', async ({ page, request }) => {
	await page.emulateMedia({ reducedMotion: 'reduce' });
	await page.goto(url());
	await expect.poll(() => fase(page)).toBe('formado');
	await page.fill('#busca-campo', 'eleição');
	await expect(page.locator('#busca-resultados li').first()).toBeVisible();
	const hrefs = await page.locator('#ceu-pagina a[href]').evaluateAll((as) => as.map((a) => (a as HTMLAnchorElement).href));
	const internos = [...new Set(hrefs.filter((h) => h.startsWith(url()) && !h.includes('/demo/')).map((h) => h.split('#')[0]))];
	expect(internos.length).toBeGreaterThan(5);
	for (const h of internos) expect((await request.get(h)).status(), h).toBe(200);
	const demo = hrefs.filter((h) => h.includes('/demo/'));
	expect(demo.length).toBeGreaterThan(10);
	for (const h of demo) expect(h, h).toMatch(/\/demo\/(#\/(mapa|topicos|geografia|classificacao|validacao)(\?.*)?)?$/);
});

test('a abertura pesa menos de 400 KB, dados incluídos', () => {
	const pasta = join(SITE, 'assets', 'pagina');
	const total = readdirSync(pasta).reduce((s, f) => s + statSync(join(pasta, f)).size, 0);
	expect(total).toBeLessThan(400 * 1024);
});

test('o contraste dos textos passa do AA nos dois temas', async ({ page }) => {
	await page.goto(url());
	for (const tema of ['default', 'slate']) {
		const razoes = await page.evaluate((t) => {
			document.body.setAttribute('data-md-color-scheme', t);
			const estilo = getComputedStyle(document.getElementById('ceu-pagina')!);
			const cor = (v: string) => estilo.getPropertyValue(v).trim();
			const lum = (hex: string) => {
				const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
				return 0.2126 * r + 0.7152 * g + 0.0722 * b;
			};
			const razao = (a: string, b: string) => {
				const [x, y] = [lum(cor(a)), lum(cor(b))].sort((p, q) => q - p);
				return (x + 0.05) / (y + 0.05);
			};
			const fundos = ['--ceu-fundo', '--ceu-superficie'];
			const textos = ['--ceu-texto', '--ceu-suave', '--ceu-fraco', '--ceu-acento'];
			return [
				...textos.flatMap((t) => fundos.map((f) => ({ par: `${t} sobre ${f}`, r: razao(t, f) }))),
				{ par: '--ceu-sobre-acento sobre --ceu-acento', r: razao('--ceu-sobre-acento', '--ceu-acento') }
			];
		}, tema);
		for (const { par, r } of razoes) expect(r, `${tema}: ${par}`).toBeGreaterThanOrEqual(4.5);
	}
});
