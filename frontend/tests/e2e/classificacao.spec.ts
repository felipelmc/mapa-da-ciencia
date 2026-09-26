// A vista Classificação (M5), sobre o build servido com o exemplo sintético.
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import { h1, ler, TELAS, trilho, url, vigiar } from './comum';

const classificacoes = ler('classificacoes.json');
const codebook = ler('codebook.json');
const numero = (n: number) => new Intl.NumberFormat('pt-BR').format(n);

test.beforeEach(async ({ page }) => {
	await page.emulateMedia({ reducedMotion: 'reduce' });
});

for (const site of ['RAIZ', 'SUBCAMINHO'] as const) {
	test(`mostra as variáveis, as barras por ano e o cruzamento (${site === 'RAIZ' ? 'raiz' : 'subcaminho'})`, async ({
		page
	}) => {
		const problemas = vigiar(page);
		await page.goto(`${url(site)}#/classificacao`);
		await expect(h1(page)).toHaveText('Classificação');
		await expect(page.getByTestId('lide-classificacao')).toContainText(
			`${numero(classificacoes.classificados)} de ${numero(classificacoes.classificados)} documentos`
		);
		// uma aba por variável não textual, cada uma com o selo de kappa da validação
		const nTexto = codebook.variaveis.filter((v: { tipo: string }) => v.tipo === 'texto').length;
		await expect(page.getByTestId('variavel')).toHaveCount(codebook.variaveis.length - nTexto);
		await expect(page.getByTestId('selo-kappa').first()).toBeVisible();
		await expect(page.getByTestId('segmento').first()).toBeVisible();
		// sem recorte, a coluna "Classificados" do cruzamento soma o total
		await page.getByTestId('figura-cruzamento').getByRole('button', { name: 'Ver como tabela' }).click();
		const n = await page
			.getByTestId('tabela-cruzamento')
			.locator('tbody tr td:nth-child(2)')
			.evaluateAll((tds) => tds.reduce((s, td) => s + Number(td.textContent!.replace(/\./g, '')), 0));
		expect(n).toBe(classificacoes.classificados);
		if (site === 'RAIZ') await page.screenshot({ path: join(TELAS, 'classificacao-1440x900.png'), fullPage: true });
		expect(problemas).toEqual([]);
	});
}

test('trocar de variável e de cruzamento vai para a URL', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/classificacao`);
	const segunda = page.getByTestId('variavel').nth(1);
	await segunda.click();
	await expect(page).toHaveURL(new RegExp(`variavel=${codebook.variaveis[1].id}`));
	await expect(segunda).toHaveAttribute('aria-pressed', 'true');
	await page.getByRole('group', { name: 'Cruzar com' }).getByRole('button', { name: 'Revistas' }).click();
	await expect(page).toHaveURL(/cruzar=revista/);
	await expect(page.getByTestId('figura-cruzamento').locator('h2')).toHaveText('Por revistas');
});

test('uma célula lista os documentos com a evidência marcada no resumo', async ({ page }) => {
	const problemas = vigiar(page);
	await page.goto(`${url('RAIZ')}#/classificacao`);
	const celula = page.getByTestId('celula').and(page.locator(':not([disabled])')).first();
	const rotulo = (await celula.getAttribute('aria-label'))!;
	const n = Number(rotulo.match(/: ([\d.]+) documentos/)![1].replace(/\./g, ''));
	await celula.click();
	const lista = page.getByTestId('lista-documentos');
	await expect(lista).toContainText(`${numero(n)} ${n === 1 ? 'documento' : 'documentos'} no recorte`);
	await expect(lista.getByTestId('item-documento')).toHaveCount(Math.min(n, 10));
	// a primeira evidência está marcada dentro do resumo
	await expect(lista.getByTestId('trecho').first()).toBeVisible();
	await expect(lista.locator('mark').first()).not.toBeEmpty();
	// o título leva ao documento no mapa
	await lista.getByTestId('item-documento').first().getByRole('link').click();
	await expect(page).toHaveURL(/#\/mapa\?.*doc=/);
	expect(problemas).toEqual([]);
});

test('o recorte vale para a vista e segue pelo trilho', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/classificacao?anos=2015-2018`);
	await expect(page.getByTestId('lide-classificacao')).not.toContainText(
		`${numero(classificacoes.classificados)} de ${numero(classificacoes.classificados)}`
	);
	await trilho(page).getByRole('link', { name: 'Tópicos' }).click();
	await expect(page).toHaveURL(/#\/topicos\?anos=2015-2018/);
});
