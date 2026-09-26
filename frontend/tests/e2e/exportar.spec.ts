// Exportar figuras (M7): SVG com fontes e cabeçalho, PNG na largura do preset e CSV dos dados.
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test, type Page } from '@playwright/test';
import { TELAS, url, vigiar } from './comum';

test.beforeEach(async ({ page }) => {
	await page.emulateMedia({ reducedMotion: 'reduce' });
});

async function baixar(page: Page, figura: string, formato: 'SVG' | 'PNG' | 'CSV (dados)', preset?: string) {
	const f = page.getByTestId(`figura-${figura}`);
	await f.getByTestId('abrir-exportar').click();
	await f.getByLabel(formato).check();
	if (preset) await f.getByTestId('preset-exportar').selectOption(preset);
	const esperar = page.waitForEvent('download', { timeout: 15_000 });
	await f.getByTestId('baixar-figura').click();
	const download = await esperar.catch(async (e) => {
		throw new Error(`sem download (${await f.getByRole('alert').textContent().catch(() => 'sem alerta')}): ${e}`);
	});
	return { nome: download.suggestedFilename(), dados: readFileSync((await download.path())!) };
}

test('SVG com o título, o recorte, as fontes embutidas e o tamanho do artigo', async ({ page }) => {
	const problemas = vigiar(page);
	await page.goto(`${url('RAIZ')}#/geografia?anos=2015-2020`);
	await expect(page.getByTestId('figura-ufs')).toHaveAttribute('data-pronto', 'sim');
	const { nome, dados } = await baixar(page, 'ufs', 'SVG', 'artigo-2');
	const svg = dados.toString('utf8');
	expect(nome).toBe('por-uf.svg');
	expect(svg).toMatch(/^<svg xmlns="http:\/\/www.w3.org\/2000\/svg" width="174mm"/);
	expect(svg).toContain('>Por UF</text>');
	expect(svg).toContain('2015–2020');
	expect(svg).toContain('@font-face');
	expect(svg).toContain('Fonte: exemplo');
	expect(svg).not.toContain('var(--'); // as cores do tema já resolvidas
	const png = await baixar(page, 'ufs', 'PNG', 'artigo-1');
	expect(png.dados.readUInt32BE(16)).toBe(1004);
	writeFileSync(join(TELAS, 'exportado-ufs-artigo.png'), png.dados);
	expect(problemas).toEqual([]);
});

test('PNG na largura do preset e CSV com os dados', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/topicos`);
	const figuras = page.locator('[data-testid^="figura-"]');
	await expect(figuras.first()).toBeVisible();
	const id = (await figuras.first().getAttribute('data-testid'))!.replace('figura-', '');
	const png = await baixar(page, id, 'PNG', 'slide');
	expect(png.nome).toMatch(/\.png$/);
	expect(png.dados.subarray(1, 4).toString()).toBe('PNG');
	expect(png.dados.readUInt32BE(16)).toBe(1920); // largura no cabeçalho IHDR

	const csv = await baixar(page, id, 'CSV (dados)');
	expect(csv.nome).toMatch(/\.csv$/);
	const texto = csv.dados.toString('utf8');
	expect(texto.charCodeAt(0)).toBe(0xfeff);
	expect(texto.split('\r\n').length).toBeGreaterThan(2);
});

test('uma figura sem gráfico em SVG só exporta CSV', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/classificacao`);
	const f = page.getByTestId('figura-cruzamento');
	await f.getByTestId('abrir-exportar').click();
	await expect(f.getByLabel('SVG')).toBeDisabled();
	await expect(f.getByLabel('CSV (dados)')).toBeEnabled();
});
