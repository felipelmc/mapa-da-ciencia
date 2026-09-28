// Exportar figuras (M7): SVG com fontes e cabeçalho, PNG na largura do preset e CSV dos dados.
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test, type Page } from '@playwright/test';
import { ler, TELAS, url, vigiar } from './comum';

const agregados = ler('agregados.json');
const afiliacoes = ler('afiliacoes.json');

test.beforeEach(async ({ page }) => {
	await page.emulateMedia({ reducedMotion: 'reduce' });
});

/** Lê um CSV (vírgula, aspas duplas, CRLF, BOM), como o `read.csv` do R. */
function lerCsv(texto: string): string[][] {
	const linhas: string[][] = [];
	let campo = '';
	let linha: string[] = [];
	let aspas = false;
	const t = texto.replace(/^﻿/, '');
	for (let i = 0; i < t.length; i += 1) {
		const c = t[i];
		if (aspas && c === '"' && t[i + 1] === '"') {
			campo += '"';
			i += 1;
		} else if (c === '"') {
			aspas = !aspas;
		} else if (!aspas && c === ',') {
			linha.push(campo);
			campo = '';
		} else if (!aspas && c === '\r' && t[i + 1] === '\n') {
			linha.push(campo);
			linhas.push(linha);
			linha = [];
			campo = '';
			i += 1;
		} else {
			campo += c;
		}
	}
	return linhas;
}
const NUMERO = /^-?\d+(\.\d+)?(e-?\d+)?$/;

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

test('o CSV sai com números crus, que o R e o pandas leem sem limpeza', async ({ page }) => {
	const csvDe = async (figura: string) => lerCsv((await baixar(page, figura, 'CSV (dados)')).dados.toString('utf8'));

	// Geografia: o peso de cada UF é o do gabarito do Python; os documentos, os que têm alguma afiliação nela
	await page.goto(`${url('RAIZ')}#/geografia`);
	await expect(page.getByTestId('figura-ufs')).toHaveAttribute('data-pronto', 'sim');
	const [cabUf, ...ufs] = await csvDe('ufs');
	expect(cabUf).toEqual(['UF', 'Peso fracionário', 'Documentos']);
	for (const l of ufs) for (const c of l.slice(1)) expect(c, l.join(',')).toMatch(NUMERO);
	const pesos = Object.values(agregados.uf as Record<string, number>).sort((a, b) => b - a);
	expect(ufs.map((l) => Number(l[1]))).toEqual(pesos.map((p) => Number(p.toFixed(4))));
	const docsPorUf = afiliacoes.dicionarios.uf.map(
		(_: string, u: number) =>
			new Set(afiliacoes.colunas.doc.filter((_d: number, k: number) => afiliacoes.colunas.uf[k] === u)).size
	);
	const soma = (l: number[]) => l.reduce((a, b) => a + b, 0);
	expect(soma(ufs.map((l) => Number(l[2])))).toBe(soma(docsPorUf));

	// Classificação: as proporções vão como fração, e um ano sem classificados fica vazio
	await page.goto(`${url('RAIZ')}#/classificacao`);
	const [cabAno, ...anos] = await csvDe('por-ano');
	expect(cabAno.slice(0, 2)).toEqual(['Ano', 'Classificados']);
	for (const l of anos) {
		for (const c of l.slice(0, 2)) expect(c).toMatch(/^\d+$/);
		for (const c of l.slice(2)) {
			if (c === '') continue;
			expect(c, l.join(',')).toMatch(NUMERO);
			expect(Number(c)).toBeLessThanOrEqual(1);
		}
	}

	// Tópicos: a variação em pontos percentuais com sinal ASCII e o intervalo em duas colunas
	await page.goto(`${url('RAIZ')}#/topicos`);
	await expect(page.getByTestId('figura-tendencias')).toBeVisible();
	const [cabTend, ...tendencias] = await csvDe('tendencias');
	expect(cabTend).toContain('IC 95% da inclinação (inferior)');
	expect(tendencias.length).toBeGreaterThan(0);
	for (const l of tendencias) {
		expect(l[1]).toMatch(/^(alta|queda)$/);
		for (const c of l.slice(2)) expect(c, l.join(',')).toMatch(NUMERO);
		expect(Math.sign(Number(l[2]))).toBe(l[1] === 'alta' ? 1 : -1);
	}
});

test('uma figura sem gráfico em SVG só exporta CSV', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/classificacao`);
	const f = page.getByTestId('figura-cruzamento');
	await f.getByTestId('abrir-exportar').click();
	await expect(f.getByLabel('SVG')).toBeDisabled();
	await expect(f.getByLabel('CSV (dados)')).toBeEnabled();
});

test('modo apresentação: P esconde o trilho e as barras, Esc volta', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/topicos`);
	const trilho = page.getByRole('navigation', { name: /seções/i });
	await expect(trilho).toBeVisible();
	await page.keyboard.press('p');
	await expect(page.getByTestId('modo-apresentacao')).toBeVisible();
	await expect(trilho).toBeHidden();
	expect(await page.evaluate(() => document.documentElement.dataset.apresentacao)).toBe('sim');
	await page.keyboard.press('Escape');
	await expect(trilho).toBeVisible();
	// na codificação, P é só uma tecla
	await page.goto(`${url('PAINEL')}#/validacao/codificar`);
	await page.getByLabel(/Seu nome/).fill('p');
	await expect(page.getByTestId('modo-apresentacao')).toHaveCount(0);
});
