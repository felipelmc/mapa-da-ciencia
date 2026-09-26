// A vista do mapa (M3), sobre o build servido com o exemplo sintético.
import { expect, test } from '@playwright/test';
import { esperarMapa, h1, inteiro, ler, trilho, url, vigiar } from './comum';

const documentos = ler('documentos.json');
const topicos = ler('topicos.json');
const n: number = documentos.n;

for (const site of ['RAIZ', 'SUBCAMINHO'] as const) {
	test(`desenha os documentos do exemplo (${site === 'RAIZ' ? 'raiz' : 'subcaminho'})`, async ({ page }) => {
		const problemas = vigiar(page);
		await page.goto(`${url(site)}#/mapa`);
		await expect(h1(page)).toHaveText('Mapa');
		const d = await esperarMapa(page);
		expect(d.erro).toBeNull();
		expect(d.pontos).toBe(n);
		expect(d.visiveis).toBe(n);
		await expect(page.getByTestId('contador-mapa')).toContainText(inteiro(n));
		console.log(`primeiro desenho: ${Math.round(d.msAtePrimeiroDesenho!)} ms`, d.etapasMs, d.renderer);
		// No Mac do desenvolvimento, o critério do M3; no CI (WebGL por software), só o registro acima.
		if (!process.env.CI) expect(d.msAtePrimeiroDesenho!).toBeLessThan(1500);
		expect(page.url()).not.toContain('vista='); // a câmera inicial não vai para o link
		expect(problemas).toEqual([]);
	});
}

test('a legenda filtra por tópico, e "Limpar filtros" volta ao todo', async ({ page }) => {
	const problemas = vigiar(page);
	await page.goto(`${url('RAIZ')}#/mapa`);
	await esperarMapa(page);
	const primeiro = topicos.topicos[0];
	await page.getByTestId('legenda-mapa').getByRole('button', { name: primeiro.rotulo }).click();
	await expect(page).toHaveURL(new RegExp(`topicos=${primeiro.id}(&|$)`));
	const doTopico = documentos.colunas.topico.filter((t: number) => t === primeiro.id).length;
	await expect(page.getByTestId('contador-mapa')).toContainText(inteiro(doTopico));
	await expect.poll(() => page.evaluate(() => window.__mapaDebug?.visiveis)).toBe(doTopico);

	await page.getByRole('button', { name: 'Limpar filtros' }).click();
	await expect.poll(() => page.evaluate(() => window.__mapaDebug?.visiveis)).toBe(n);
	await expect(page).toHaveURL(/#\/mapa$/);
	expect(problemas).toEqual([]);
});

test('colorir por revista muda a URL e a legenda', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/mapa`);
	await esperarMapa(page);
	await page.getByTestId('cor-por').selectOption('revista');
	await expect(page).toHaveURL(/cor=revista/);
	await expect(page.getByTestId('legenda-mapa').getByRole('listitem')).toHaveCount(documentos.dicionarios.revista.length);
	// a cor por ano não tem legenda por categoria: um degradê do primeiro ao último ano
	await page.getByTestId('cor-por').selectOption('ano');
	await expect(page.getByTestId('legenda-mapa')).toHaveCount(0);
});

test('projeto sem tópicos: o mapa explica o que fazer e não pede arquivos ausentes', async ({ page }) => {
	const problemas = vigiar(page);
	const dados: string[] = [];
	page.on('request', (r) => {
		const caminho = new URL(r.url()).pathname;
		if (caminho.startsWith('/dados/')) dados.push(caminho);
	});
	await page.goto(url('VAZIO'));
	await trilho(page).getByRole('link', { name: 'Mapa', exact: true }).click();
	await expect(h1(page)).toHaveText('Mapa');
	await expect(page.getByRole('heading', { name: 'Este projeto ainda não tem mapa.' })).toBeVisible();
	expect(dados).toEqual(['/dados/manifesto.json']);
	expect(problemas).toEqual([]);
});
