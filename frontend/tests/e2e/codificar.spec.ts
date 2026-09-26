// Validação › Codificar (M5): a codificação cega pelo teclado, contra a API falsa do painel (api-falsa.ts).
import { expect, test, type Page } from '@playwright/test';
import { h1, ler, url, vigiar } from './comum';

const codebook = ler('codebook.json');
const nVars = codebook.variaveis.length;
const textos = codebook.variaveis.filter((v: { tipo: string }) => v.tipo === 'texto').length;

test.beforeEach(async ({ page }) => {
	await page.emulateMedia({ reducedMotion: 'reduce' });
});

async function entrar(page: Page, nome: string) {
	await page.goto(`${url('PAINEL')}#/validacao/codificar`);
	await page.getByLabel(/Seu nome/).fill(nome);
	await page.getByRole('button', { name: 'Começar' }).click();
	await expect(page.getByTestId('ficha')).toBeVisible();
}

/** Uma ficha só pelo teclado: a primeira opção em cada variável, um período nas de texto e Enter. */
async function codificarFicha(page: Page) {
	for (let i = 0; i < nVars - textos; i += 1) await page.keyboard.press('1');
	if (textos) {
		await page.keyboard.type('2010–2020');
		await page.keyboard.press('Enter');
	} else {
		await page.keyboard.press('Enter');
	}
}

test('no site estático, explica que a codificação é do painel', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/validacao/codificar`);
	await expect(h1(page)).toHaveText('Codificar a amostra');
	await expect(page.getByText('só funciona no painel local')).toBeVisible();
});

test('20 fichas só pelo teclado sobrevivem a um reload', async ({ page }) => {
	const problemas = vigiar(page);
	await entrar(page, 'maria');
	const progresso = page.getByTestId('progresso');
	await expect(progresso).toContainText('0 de 24 fichas completas');
	const primeira = await page.getByTestId('ficha').getAttribute('data-doc');
	for (let n = 1; n <= 20; n += 1) {
		await codificarFicha(page);
		await expect(progresso).toContainText(`${n} de 24 fichas completas`);
	}
	await expect(page.getByTestId('estado-gravacao')).toHaveText('Tudo gravado.');
	await page.reload();
	// o nome ficou lembrado, e a fila volta na primeira ficha incompleta
	await expect(progresso).toContainText('20 de 24 fichas completas · ficha 21');
	// a primeira ficha guardou as respostas
	for (let i = 0; i < 20; i += 1) await page.keyboard.press('ArrowLeft');
	await expect(page.getByTestId('ficha')).toHaveAttribute('data-doc', primeira!);
	await expect(page.locator('[data-testid="variavel-ficha"][data-respondida="sim"]')).toHaveCount(nVars);
	expect(problemas).toEqual([]);
});

test('Enter com variáveis faltando avisa; S marca incerto; ? mostra a ajuda', async ({ page }) => {
	await entrar(page, 'joao');
	await page.keyboard.press('1');
	await page.keyboard.press('Enter');
	await expect(page.getByRole('alert')).toContainText('Falta responder');
	await page.keyboard.press('ArrowUp');
	await page.keyboard.press('s');
	await expect(page.locator('.variavel.atual .incerto')).toHaveText('incerto');
	await page.keyboard.press('?');
	await expect(page.getByTestId('ajuda-codificar')).toBeVisible();
	await page.keyboard.press('Escape');
	await expect(page.getByTestId('ajuda-codificar')).toBeHidden();
	// cada pessoa tem a sua ordem na fila
	const minha = await page.getByTestId('ficha').getAttribute('data-doc');
	await page.getByRole('button', { name: 'Trocar de codificador' }).click();
	await page.getByLabel(/Seu nome/).fill('maria-2');
	await page.getByRole('button', { name: 'Começar' }).click();
	await expect(page.getByTestId('progresso')).toContainText('0 de 24');
	expect(await page.getByTestId('ficha').getAttribute('data-doc')).not.toBe(minha);
});
