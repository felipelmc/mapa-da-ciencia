// A vista Tópicos (M4), sobre o build servido com o exemplo sintético.
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import { h1, inteiro, ler, TELAS, url, vigiar } from './comum';

const topicos = ler('topicos.json');
const documentos = ler('documentos.json');
const macros: { id: number; rotulo: string; topicos: number[] }[] = topicos.macrotemas;

test.beforeEach(async ({ page }) => {
	await page.emulateMedia({ reducedMotion: 'reduce' });
});

for (const site of ['RAIZ', 'SUBCAMINHO'] as const) {
	test(`desenha o fluxo dos macrotemas (${site === 'RAIZ' ? 'raiz' : 'subcaminho'})`, async ({ page }) => {
		const problemas = vigiar(page);
		await page.goto(`${url(site)}#/topicos`);
		await expect(h1(page)).toHaveText('Tópicos');
		await expect(page.getByTestId('figura-fluxo')).toHaveAttribute('data-pronto', 'sim');
		await expect(page.getByTestId('faixa')).toHaveCount(macros.length + 1); // + "sem tópico"
		await expect(page.getByTestId('resumo-fluxo')).toContainText(`${inteiro(documentos.n)} documentos`);
		if (site === 'RAIZ') await page.screenshot({ path: join(TELAS, 'topicos-1440x900.png'), fullPage: true });
		expect(problemas).toEqual([]);
	});
}

test('os modos mudam a URL, e a tabela bate com o topicos.json', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/topicos`);
	await page.getByTestId('modo-proporcao').click();
	await expect(page).toHaveURL(/modo=proporcao/);
	await expect(page.getByTestId('modo-proporcao')).toHaveAttribute('aria-pressed', 'true');
	await expect(page.getByTestId('figura-fluxo').getByText('100%').first()).toBeVisible();
	await page.getByTestId('figura-fluxo').getByRole('button', { name: 'Ver como tabela' }).click();
	const tabela = page.getByTestId('tabela-fluxo');
	await expect(tabela.locator('tbody tr')).toHaveCount(macros.length + 1);
	const doTopico = new Map(topicos.topicos.map((t: { id: number; n: number }) => [t.id, t.n]));
	const primeiro = macros[0];
	const total = primeiro.topicos.reduce((s, t) => s + (doTopico.get(t) as number), 0);
	await expect(tabela.locator('tbody tr', { hasText: primeiro.rotulo }).locator('td').last()).toHaveText(inteiro(total));
});

test('clicar num macrotema abre os tópicos dele, e a trilha volta', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/topicos`);
	const alvo = macros[2];
	await page.locator(`[data-testid="faixa"][data-id="${alvo.id}"]`).click({ force: true });
	await expect(page).toHaveURL(new RegExp(`macro=${alvo.id}`));
	await expect(page.getByTestId('macro-aberto')).toHaveText(alvo.rotulo);
	await expect(page.getByTestId('faixa')).toHaveCount(alvo.topicos.length);
	await page.getByRole('button', { name: 'Todos os macrotemas' }).click();
	await expect(page).not.toHaveURL(/macro=/);
	await expect(page.getByTestId('faixa')).toHaveCount(macros.length + 1);
});

test('o teclado escolhe a faixa', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/topicos`);
	await page.getByTestId('faixa').first().focus();
	await page.keyboard.press('Enter');
	await expect(page).toHaveURL(/macro=\d+/);
});

test('o recorte da barra filtra os documentos do fluxo', async ({ page }) => {
	const revista = documentos.dicionarios.revista[1];
	const i = documentos.dicionarios.revista.indexOf(revista);
	const n = documentos.colunas.revista.filter((r: number) => r === i).length;
	await page.goto(`${url('RAIZ')}#/topicos?revistas=${revista}`);
	await expect(page.getByTestId('resumo-fluxo')).toContainText(`${inteiro(n)} documentos`);
	await expect(page.getByTestId('contador-recorte')).toContainText(inteiro(n));
});

test('em alta e em queda: sem recorte, a lista é a do gabarito do Python', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/topicos`);
	const esperado = (direcao: string) =>
		topicos.topicos
			.filter((t: { tendencia: { direcao: string } }) => t.tendencia.direcao === direcao)
			.map((t: { id: number }) => String(t.id))
			.sort();
	for (const direcao of ['alta', 'queda']) {
		const itens = page.getByTestId(`lista-${direcao}`).locator('li');
		await expect(itens).toHaveCount(esperado(direcao).length);
		const ids = await itens.evaluateAll((els) => els.map((e) => e.getAttribute('data-id')!));
		expect(ids.sort()).toEqual(esperado(direcao));
	}
	await page.screenshot({ path: join(TELAS, 'topicos-tendencias-1440x900.png'), fullPage: true });
});

test('com menos de 5 anos no recorte, a lista pede um período maior', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/topicos?anos=2020-2022`);
	await expect(page.getByTestId('tendencias-poucos-anos')).toBeVisible();
});

test('projeto vazio: estado vazio, sem pedir arquivos ausentes', async ({ page }) => {
	const pedidos: string[] = [];
	page.on('request', (r) => pedidos.push(new URL(r.url()).pathname));
	await page.goto(`${url('VAZIO')}#/topicos`);
	await expect(page.getByText('Este projeto ainda não tem tópicos.')).toBeVisible();
	await expect(page.getByText('ainda não gerado').first()).toBeVisible();
	expect(pedidos.filter((p) => p.endsWith('.json') && !p.endsWith('manifesto.json'))).toEqual([]);
});
