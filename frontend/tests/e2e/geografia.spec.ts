// A vista Geografia (M4), sobre o build servido com o exemplo sintético.
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import { h1, ler, TELAS, trilho, url, vigiar } from './comum';

const agregados = ler('agregados.json');
const afiliacoes = ler('afiliacoes.json');

test.beforeEach(async ({ page }) => {
	await page.emulateMedia({ reducedMotion: 'reduce' });
});

for (const site of ['RAIZ', 'SUBCAMINHO'] as const) {
	test(`desenha as UFs, o mundo e o ranking (${site === 'RAIZ' ? 'raiz' : 'subcaminho'})`, async ({ page }) => {
		const problemas = vigiar(page);
		await page.goto(`${url(site)}#/geografia`);
		await expect(h1(page)).toHaveText('Geografia');
		await expect(page.getByTestId('figura-ufs')).toHaveAttribute('data-pronto', 'sim');
		await expect(page.getByTestId('figura-mundo')).toHaveAttribute('data-pronto', 'sim');
		// sem recorte, o peso de cada UF é o do gabarito do Python (agregados.json)
		const ufs = page.getByTestId('uf');
		await expect(ufs).toHaveCount(Object.keys(agregados.uf).length);
		const valores = await ufs.evaluateAll((els) =>
			Object.fromEntries(els.map((e) => [e.getAttribute('data-chave')!, Number(e.getAttribute('data-valor'))]))
		);
		for (const [sigla, peso] of Object.entries(agregados.uf)) expect(valores[sigla]).toBeCloseTo(peso as number, 3);
		// o ranking começa pela instituição de maior peso
		const maior = Object.entries(agregados.instituicao as Record<string, number>)
			.filter(([id]) => id !== 'nao-identificada')
			.sort((a, b) => b[1] - a[1])[0][0];
		await expect(page.getByTestId('instituicao').first()).toHaveAttribute('data-id', maior);
		// o Brasil fica fora da escala do mapa-múndi
		await expect(page.getByTestId('figura-mundo')).toContainText('fora da escala');
		if (site === 'RAIZ') await page.screenshot({ path: join(TELAS, 'geografia-1440x900.png'), fullPage: true });
		expect(problemas).toEqual([]);
	});
}

test('clicar numa UF põe no recorte, que vai para o Mapa pelo trilho', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/geografia`);
	const sp = page.locator('[data-testid="uf"][data-chave="SP"]');
	await sp.click();
	await expect(page).toHaveURL(/uf=SP/);
	await expect(sp).toHaveAttribute('aria-pressed', 'true');
	await expect(page.getByTestId('barra-recorte')).toContainText('SP');
	// o contador do recorte conta os documentos com alguma afiliação em SP
	const iSp = afiliacoes.dicionarios.uf.indexOf('SP');
	const docsSp = new Set(afiliacoes.colunas.doc.filter((_: number, k: number) => afiliacoes.colunas.uf[k] === iSp)).size;
	await expect(page.getByTestId('contador-recorte')).toContainText(new Intl.NumberFormat('pt-BR').format(docsSp));
	await trilho(page).getByRole('link', { name: 'Mapa' }).click();
	await expect(page).toHaveURL(/#\/mapa\?.*uf=SP/);
});

test('o teclado escolhe a UF e a instituição', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/geografia`);
	const primeira = page.getByTestId('uf').first();
	await primeira.focus();
	await page.keyboard.press('Enter');
	const sigla = await primeira.getAttribute('data-chave');
	await expect(page).toHaveURL(new RegExp(`uf=${sigla}`));
	await page.getByTestId('instituicao').first().click();
	await expect(page).toHaveURL(/inst=/);
});

test('ver como tabela e mostrar mais', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/geografia`);
	await page.getByTestId('figura-ufs').getByRole('button', { name: 'Ver como tabela' }).click();
	await expect(page.getByTestId('tabela-ufs').locator('tbody tr')).toHaveCount(Object.keys(agregados.uf).length);
	const total = afiliacoes.dicionarios.instituicao.length - 1; // sem a "não identificada"
	if (total > 20) {
		await page.getByTestId('mostrar-mais').click();
		await expect(page.getByTestId('instituicao')).toHaveCount(Math.min(40, total));
	}
});

test('projeto vazio: estado vazio, sem pedir arquivos ausentes', async ({ page }) => {
	const pedidos: string[] = [];
	page.on('request', (r) => pedidos.push(new URL(r.url()).pathname));
	await page.goto(`${url('VAZIO')}#/geografia`);
	await expect(page.getByText('Este projeto ainda não tem geografia.')).toBeVisible();
	expect(pedidos.filter((p) => p.endsWith('.json') && !p.endsWith('manifesto.json'))).toEqual([]);
});

test('a cobertura por ano avisa dos anos com muito peso sem afiliação', async ({ page }) => {
	const documentos = ler('documentos.json');
	const c = afiliacoes.colunas;
	const porAno = new Map<number, [number, number]>();
	c.doc.forEach((d: number, k: number) => {
		const ano = documentos.colunas.ano[d];
		const [sem, total] = porAno.get(ano) ?? [0, 0];
		porAno.set(ano, [sem + (c.instituicao[k] < 0 ? c.peso[k] : 0), total + c.peso[k]]);
	});
	const fracos = [...porAno.entries()].filter(([, [s, t]]) => s / t > 0.2).map(([a]) => a).sort();
	await page.goto(`${url('RAIZ')}#/geografia`);
	const resumo = page.getByTestId('resumo-cobertura');
	if (fracos.length) {
		await expect(resumo).toContainText(`Em ${fracos[0]}`);
		await expect(resumo).toContainText('pedem cuidado');
	} else {
		await expect(resumo).toContainText('Em todos os anos');
	}
	await page.getByTestId('figura-cobertura').getByRole('button', { name: 'Ver como tabela' }).click();
	await expect(page.getByTestId('tabela-cobertura').locator('tbody tr')).toHaveCount(ler('topicos.json').anos.length);
});
